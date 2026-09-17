from datetime import timedelta
import hmac
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from apps.integrations.models import OutboxEvent
from .serializers import NotificationClaimSerializer, AutomationCallbackSerializer


def verify_webhook_secret(request) -> bool:
    """
    Verifies that the incoming request contains the valid shared secret in either:
    - X-Webhook-Secret header
    - Authorization: Bearer <secret> header
    """
    configured_secret = getattr(settings, "AUTOMATION_WEBHOOK_SECRET", "")
    if not configured_secret:
        return False

    header_secret = request.headers.get("X-Webhook-Secret")
    if not header_secret:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            header_secret = auth_header[7:].strip()

    if not header_secret:
        return False

    return hmac.compare_digest(header_secret, configured_secret)


class NotificationClaimView(APIView):
    """
    POST /api/v1/integrations/notifications/claim/
    Atomically claims a PENDING notification (or recovers a stale PROCESSING notification)
    for delivery by an external orchestrator (n8n).

    Returns:
        200 OK with {"should_send": True/False, ...}
    """

    def post(self, request):
        if not verify_webhook_secret(request):
            return Response(
                {"error": "Unauthorized: invalid or missing webhook secret.", "should_send": False},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = NotificationClaimSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors, "should_send": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data
        notification_id = validated_data.get("notification_id")
        registration_id = validated_data.get("registration_id")
        event_id = validated_data.get("event_id")
        channel = validated_data["channel"]

        now = timezone.now()
        lease_seconds = getattr(settings, "REMINDER_LEASE_TIMEOUT_SECONDS", 300)
        stale_threshold = now - timedelta(seconds=lease_seconds)

        with transaction.atomic():
            # Resolve notification
            if notification_id:
                notification = (
                    Notification.objects.select_for_update()
                    .filter(id=notification_id)
                    .first()
                )
            elif event_id:
                outbox_event = OutboxEvent.objects.filter(id=event_id).first()
                if not outbox_event:
                    return Response(
                        {"error": f"OutboxEvent {event_id} not found.", "should_send": False},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                target_notif_type = (
                    NotificationType.REMINDER
                    if outbox_event.event_type == "registration.reminder"
                    else NotificationType.CONFIRMATION
                )
                notification = (
                    Notification.objects.select_for_update()
                    .filter(
                        registration_id=outbox_event.aggregate_id,
                        notification_type=target_notif_type,
                        channel=channel,
                    )
                    .first()
                )
            else:
                notification = (
                    Notification.objects.select_for_update()
                    .filter(
                        registration_id=registration_id,
                        notification_type=NotificationType.CONFIRMATION,
                        channel=channel,
                    )
                    .first()
                )

            if not notification:
                return Response(
                    {"error": "Notification not found.", "should_send": False},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if notification.channel != channel:
                return Response(
                    {
                        "error": f"Channel mismatch: expected {notification.channel}, received {channel}.",
                        "should_send": False,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            can_claim = False
            reason = None

            if notification.status == NotificationStatus.PENDING:
                can_claim = True
            elif notification.status == NotificationStatus.PROCESSING:
                if notification.processing_started_at and notification.processing_started_at < stale_threshold:
                    can_claim = True
                    reason = "Recovered stale PROCESSING lease."
                else:
                    can_claim = False
                    reason = "Notification is actively in PROCESSING state."
            elif notification.status == NotificationStatus.SENT:
                can_claim = False
                reason = "Notification has already been SENT."
            else:
                can_claim = False
                reason = f"Notification is in status {notification.status} and cannot be claimed."

            if can_claim:
                notification.status = NotificationStatus.PROCESSING
                notification.processing_started_at = now
                notification.save(update_fields=["status", "processing_started_at", "updated_at"])

                return Response(
                    {
                        "should_send": True,
                        "notification_id": str(notification.id),
                        "channel": notification.channel,
                        "status": notification.status,
                        "processing_started_at": notification.processing_started_at.isoformat(),
                        "message": reason or "Notification successfully claimed for processing.",
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        "should_send": False,
                        "notification_id": str(notification.id),
                        "channel": notification.channel,
                        "status": notification.status,
                        "reason": reason,
                    },
                    status=status.HTTP_200_OK,
                )


class AutomationCallbackView(APIView):
    """
    POST /api/v1/integrations/automation-callback/
    Receives delivery status confirmation from automation orchestrator (n8n)
    and transitions notification states idempotently.
    """

    def post(self, request):
        if not verify_webhook_secret(request):
            return Response(
                {"error": "Unauthorized: invalid or missing webhook secret."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = AutomationCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        notification_id = validated_data["notification_id"]
        target_status = validated_data["status"]
        external_id = validated_data.get("external_id")
        error_info = validated_data.get("error")

        with transaction.atomic():
            notification = (
                Notification.objects.select_for_update()
                .filter(id=notification_id)
                .first()
            )
            if not notification:
                return Response(
                    {"error": f"Notification {notification_id} not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Invariant: Never allow old/stale callback to downgrade SENT notification
            if notification.status == NotificationStatus.SENT:
                return Response(
                    {
                        "notification_id": str(notification.id),
                        "status": NotificationStatus.SENT,
                        "message": "Notification is already marked as SENT. No state change applied.",
                    },
                    status=status.HTTP_200_OK,
                )

            if target_status == NotificationStatus.SENT:
                notification.status = NotificationStatus.SENT
                notification.sent_at = timezone.now()
                if external_id:
                    notification.external_id = external_id
                notification.processing_started_at = None
                notification.last_error = None
                notification.save(
                    update_fields=[
                        "status",
                        "sent_at",
                        "external_id",
                        "processing_started_at",
                        "last_error",
                        "updated_at",
                    ]
                )
                return Response(
                    {
                        "notification_id": str(notification.id),
                        "status": notification.status,
                        "external_id": notification.external_id,
                        "sent_at": notification.sent_at.isoformat(),
                        "message": "Notification successfully transitioned to SENT.",
                    },
                    status=status.HTTP_200_OK,
                )

            elif target_status == NotificationStatus.FAILED:
                notification.status = NotificationStatus.FAILED
                notification.attempts += 1
                notification.last_error = error_info or "External automation delivery failed."
                notification.processing_started_at = None
                notification.save(
                    update_fields=[
                        "status",
                        "attempts",
                        "last_error",
                        "processing_started_at",
                        "updated_at",
                    ]
                )
                return Response(
                    {
                        "notification_id": str(notification.id),
                        "status": notification.status,
                        "attempts": notification.attempts,
                        "last_error": notification.last_error,
                        "message": "Notification transitioned to FAILED.",
                    },
                    status=status.HTTP_200_OK,
                )

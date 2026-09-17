from zoneinfo import ZoneInfo
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from apps.workshops.models import Workshop
from .serializers import (
    RegistrationCreateSerializer,
    RegistrationResponseSerializer,
)
from .services import (
    resolve_idempotency_key,
    register_attendee,
    IdempotencyConflictError,
)


class RegistrationCreateView(APIView):
    """
    POST /api/v1/registrations/
    Handles workshop registration with strict idempotency, validation,
    and atomic creation of Registration, Notifications, and OutboxEvent.
    """

    def post(self, request):
        # 1. Resolve active workshop
        workshop = Workshop.objects.filter(id="public-speaking-workshop", is_active=True).first()
        if not workshop:
            # Fallback to any active workshop if specific slug was modified
            workshop = Workshop.objects.filter(is_active=True).first()

        if not workshop:
            return Response(
                {"error": "Public Speaking Workshop is not active or available for registration."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Validate request body
        serializer = RegistrationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        full_name = validated_data["full_name"]
        email = validated_data["email"]
        phone_number = validated_data["phone_number"]

        # 3. Resolve and validate Idempotency-Key header
        header_key = request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY")
        try:
            idempotency_key = resolve_idempotency_key(header_key, workshop.id, email)
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        # 4. Atomically register attendee
        try:
            registration, created = register_attendee(
                workshop=workshop,
                full_name=full_name,
                email=email,
                phone_number=phone_number,
                idempotency_key=idempotency_key,
            )
        except IdempotencyConflictError as exc:
            return Response(
                {
                    "error": str(exc),
                    "code": "idempotency_conflict",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            return Response(
                {"error": f"An unexpected error occurred while processing registration: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 5. Build response with explicit workshop timezone offset
        tz = ZoneInfo(workshop.timezone)
        scheduled_at_local = workshop.scheduled_at.astimezone(tz).isoformat()

        if created:
            message = "Registration successful! Confirmation will be sent to your WhatsApp and Email."
            http_status = status.HTTP_201_CREATED
        else:
            message = "You are already registered for this workshop! Registration details confirmed."
            http_status = status.HTTP_200_OK

        response_data = {
            "registration_id": registration.id,
            "full_name": registration.full_name,
            "email": registration.normalized_email,
            "phone_number": registration.phone_number,
            "workshop": {
                "title": workshop.title,
                "scheduled_at": scheduled_at_local,
                "timezone": workshop.timezone,
            },
            "message": message,
        }

        return Response(response_data, status=http_status)

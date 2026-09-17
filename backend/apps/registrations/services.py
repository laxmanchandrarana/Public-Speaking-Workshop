import hashlib
import uuid
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import serializers

from zoneinfo import ZoneInfo

from apps.workshops.models import Workshop
from apps.notifications.models import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationStatus,
)
from apps.integrations.models import OutboxEvent, OutboxStatus
from .models import Registration, IdempotencyRecord


class IdempotencyConflictError(Exception):
    """Raised when an Idempotency-Key is reused with different request payload."""
    pass


def compute_request_fingerprint(full_name: str, normalized_email: str, phone_number: str) -> str:
    """Computes a SHA-256 fingerprint from the core registration input fields."""
    raw = f"{full_name.strip()}:{normalized_email.strip().lower()}:{phone_number.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def resolve_idempotency_key(header_key: str | None, workshop_id: str, normalized_email: str) -> str:
    """
    Validates the client-supplied Idempotency-Key header, or creates a deterministic
    hash fallback based on workshop ID and normalized email.
    """
    if header_key:
        cleaned_key = header_key.strip()
        if not (1 <= len(cleaned_key) <= 64):
            raise serializers.ValidationError(
                {"idempotency_key": "Idempotency-Key header must be between 1 and 64 characters long."}
            )
        if not cleaned_key.isprintable():
            raise serializers.ValidationError(
                {"idempotency_key": "Idempotency-Key header contains invalid non-printable characters."}
            )
        return cleaned_key

    # Fallback to deterministic SHA-256 hash
    seed = f"{workshop_id}:{normalized_email}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:64]


def build_registration_created_payload(registration: Registration, notifications: list[Notification] | None = None) -> dict:
    """
    Builds the standardized event payload for the transactional outbox.
    All workshop schedule timestamps are serialized explicitly in the workshop's timezone (Asia/Kolkata +05:30).
    Includes all 4 confirmation and reminder notification IDs for deterministic downstream claiming.
    """
    workshop = registration.workshop
    tz = ZoneInfo(workshop.timezone)
    scheduled_at_iso = workshop.scheduled_at.astimezone(tz).isoformat()
    reminder_at_iso = workshop.reminder_at.astimezone(tz).isoformat()

    if notifications is None:
        notifications = list(
            Notification.objects.filter(
                registration=registration,
            )
        )

    confirmation_email = next(
        (n for n in notifications if n.notification_type == NotificationType.CONFIRMATION and n.channel == NotificationChannel.EMAIL),
        None,
    )
    confirmation_wa = next(
        (n for n in notifications if n.notification_type == NotificationType.CONFIRMATION and n.channel == NotificationChannel.WHATSAPP),
        None,
    )
    reminder_email = next(
        (n for n in notifications if n.notification_type == NotificationType.REMINDER and n.channel == NotificationChannel.EMAIL),
        None,
    )
    reminder_wa = next(
        (n for n in notifications if n.notification_type == NotificationType.REMINDER and n.channel == NotificationChannel.WHATSAPP),
        None,
    )

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "registration.created",
        "version": "1.0",
        "occurred_at": timezone.now().isoformat(),
        "data": {
            "registration": {
                "id": str(registration.id),
                "full_name": registration.full_name,
                "email": registration.normalized_email,
                "phone_number": registration.phone_number,
                "registered_at": registration.created_at.isoformat(),
            },
            "workshop": {
                "id": workshop.id,
                "title": workshop.title,
                "scheduled_at_iso": scheduled_at_iso,
                "timezone": workshop.timezone,
                "reminder_at_iso": reminder_at_iso,
            },
            "notifications": {
                "confirmation_email_id": str(confirmation_email.id) if confirmation_email else None,
                "confirmation_whatsapp_id": str(confirmation_wa.id) if confirmation_wa else None,
                "reminder_email_id": str(reminder_email.id) if reminder_email else None,
                "reminder_whatsapp_id": str(reminder_wa.id) if reminder_wa else None,
            },
            "messages": {
                "whatsapp_text": (
                    f"Hi {registration.full_name}, your registration for {workshop.title} is confirmed! "
                    f"Date: 18 September 2026, 3:30 PM {workshop.timezone}. "
                    "We will send a reminder 15 minutes before the session starts."
                )
            },
        },
    }


def build_registration_reminder_payload(registration: Registration, notifications: list[Notification] | None = None) -> dict:
    """
    Builds the standardized event payload for the pre-workshop reminder outbox event.
    Workshop schedule timestamps are serialized explicitly in the workshop's timezone (Asia/Kolkata +05:30).
    Carries reminder_email_id and reminder_whatsapp_id for deterministic downstream claiming.
    """
    workshop = registration.workshop
    tz = ZoneInfo(workshop.timezone)
    scheduled_at_iso = workshop.scheduled_at.astimezone(tz).isoformat()
    reminder_at_iso = workshop.reminder_at.astimezone(tz).isoformat()

    if notifications is None:
        notifications = list(
            Notification.objects.filter(
                registration=registration,
                notification_type=NotificationType.REMINDER,
            )
        )

    reminder_email = next(
        (n for n in notifications if n.notification_type == NotificationType.REMINDER and n.channel == NotificationChannel.EMAIL),
        None,
    )
    reminder_wa = next(
        (n for n in notifications if n.notification_type == NotificationType.REMINDER and n.channel == NotificationChannel.WHATSAPP),
        None,
    )

    formatted_time = workshop.scheduled_at.astimezone(tz).strftime("%-I:%M %p")
    meeting_text = f" Join here: {workshop.meeting_link}" if workshop.meeting_link else ""

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "registration.reminder",
        "version": "1.0",
        "occurred_at": timezone.now().isoformat(),
        "data": {
            "registration": {
                "id": str(registration.id),
                "full_name": registration.full_name,
                "email": registration.normalized_email,
                "phone_number": registration.phone_number,
                "registered_at": registration.created_at.isoformat(),
            },
            "workshop": {
                "id": workshop.id,
                "title": workshop.title,
                "scheduled_at_iso": scheduled_at_iso,
                "timezone": workshop.timezone,
                "reminder_at_iso": reminder_at_iso,
            },
            "notifications": {
                "reminder_email_id": str(reminder_email.id) if reminder_email else None,
                "reminder_whatsapp_id": str(reminder_wa.id) if reminder_wa else None,
            },
            "messages": {
                "whatsapp_text": (
                    f"Hi {registration.full_name}, reminder: {workshop.title} starts in 15 minutes "
                    f"({formatted_time} {workshop.timezone})!{meeting_text}"
                )
            },
        },
    }


def register_attendee(
    workshop: Workshop,
    full_name: str,
    email: str,
    phone_number: str,
    idempotency_key: str,
) -> tuple[Registration, bool]:
    """
    Performs atomic, idempotent registration of an attendee:
    1. Checks IdempotencyRecord by key:
       - If exists and identical fingerprint -> return (registration, False) [Behavior B]
       - If exists and different fingerprint -> raise IdempotencyConflictError [Behavior C]
    2. Checks existing workshop/email registration:
       - If exists -> atomically persist IdempotencyRecord for this key pointing to the
         existing registration and return (existing_registration, False) [Behavior D]
    3. If both key and registration are new:
       - Atomically create Registration, IdempotencyRecord, 4 Notifications, and 1 OutboxEvent
         and return (registration, True) [Behavior A]
    4. Concurrency protection:
       - If a concurrent request creates the key or registration in a race, catch IntegrityError
         and safely resolve idempotency without duplicate writes.

    Returns:
        tuple[Registration, bool]: (registration, created)
    """
    normalized_email = email.strip().lower()
    fingerprint = compute_request_fingerprint(full_name, normalized_email, phone_number)

    # Step 1: Check existing IdempotencyRecord (Behavior B & C)
    existing_record = (
        IdempotencyRecord.objects.select_related("registration", "registration__workshop")
        .filter(key=idempotency_key)
        .first()
    )
    if existing_record:
        if existing_record.request_fingerprint != fingerprint:
            raise IdempotencyConflictError(
                "Idempotency-Key has already been used with different registration details."
            )
        return existing_record.registration, False

    # Step 2: Check existing business duplicate: (workshop, normalized_email) (Behavior D)
    existing_by_email = (
        Registration.objects.select_related("workshop")
        .filter(workshop=workshop, normalized_email=normalized_email)
        .first()
    )
    if existing_by_email:
        # Case D: New key + existing workshop/email registration
        # Return existing registration, but persist the new idempotency key mapped to that
        # existing registration so later reuse of that key cannot create a different registration.
        try:
            with transaction.atomic():
                IdempotencyRecord.objects.create(
                    key=idempotency_key,
                    request_fingerprint=fingerprint,
                    registration=existing_by_email,
                )
        except IntegrityError:
            # Race condition: concurrent request inserted this key
            existing_record = (
                IdempotencyRecord.objects.select_related("registration")
                .filter(key=idempotency_key)
                .first()
            )
            if existing_record:
                if existing_record.request_fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "Idempotency-Key has already been used with different registration details."
                    )
                return existing_record.registration, False
            raise

        return existing_by_email, False

    # Step 3: New key + new registration (Behavior A)
    now = timezone.now()
    reminder_scheduled_at = workshop.reminder_at

    try:
        with transaction.atomic():
            # 1. Create Registration
            registration = Registration.objects.create(
                workshop=workshop,
                full_name=full_name,
                email=email,
                normalized_email=normalized_email,
                phone_number=phone_number,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )

            # 2. Create IdempotencyRecord
            IdempotencyRecord.objects.create(
                key=idempotency_key,
                request_fingerprint=fingerprint,
                registration=registration,
            )

            # 3. Create Notifications (2 Confirmations, 2 Reminders)
            created_notifs = Notification.objects.bulk_create(
                [
                    # Instant Confirmation: WhatsApp
                    Notification(
                        registration=registration,
                        notification_type=NotificationType.CONFIRMATION,
                        channel=NotificationChannel.WHATSAPP,
                        status=NotificationStatus.PENDING,
                        scheduled_at=now,
                    ),
                    # Instant Confirmation: Email
                    Notification(
                        registration=registration,
                        notification_type=NotificationType.CONFIRMATION,
                        channel=NotificationChannel.EMAIL,
                        status=NotificationStatus.PENDING,
                        scheduled_at=now,
                    ),
                    # 15-Minute Reminder: WhatsApp (scheduled for 2026-09-18 15:15:00+05:30)
                    Notification(
                        registration=registration,
                        notification_type=NotificationType.REMINDER,
                        channel=NotificationChannel.WHATSAPP,
                        status=NotificationStatus.PENDING,
                        scheduled_at=reminder_scheduled_at,
                    ),
                    # 15-Minute Reminder: Email (scheduled for 2026-09-18 15:15:00+05:30)
                    Notification(
                        registration=registration,
                        notification_type=NotificationType.REMINDER,
                        channel=NotificationChannel.EMAIL,
                        status=NotificationStatus.PENDING,
                        scheduled_at=reminder_scheduled_at,
                    ),
                ]
            )

            # 4. Create OutboxEvent
            outbox_payload = build_registration_created_payload(registration, created_notifs)
            OutboxEvent.objects.create(
                event_type="registration.created",
                aggregate_type="Registration",
                aggregate_id=registration.id,
                payload=outbox_payload,
                status=OutboxStatus.PENDING,
            )

            return registration, True

    except IntegrityError:
        # Step 4: Concurrency handling
        # A concurrent request might have inserted the same idempotency key or (workshop, normalized_email)
        existing_record = (
            IdempotencyRecord.objects.select_related("registration")
            .filter(key=idempotency_key)
            .first()
        )
        if existing_record:
            if existing_record.request_fingerprint != fingerprint:
                raise IdempotencyConflictError(
                    "Idempotency-Key has already been used with different registration details."
                )
            return existing_record.registration, False

        existing_by_email = (
            Registration.objects.filter(workshop=workshop, normalized_email=normalized_email)
            .first()
        )
        if existing_by_email:
            try:
                with transaction.atomic():
                    IdempotencyRecord.objects.create(
                        key=idempotency_key,
                        request_fingerprint=fingerprint,
                        registration=existing_by_email,
                    )
            except IntegrityError:
                pass
            return existing_by_email, False

        raise

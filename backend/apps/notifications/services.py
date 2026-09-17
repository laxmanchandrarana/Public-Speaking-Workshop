import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone

from apps.notifications.models import (
    Notification,
    NotificationType,
    NotificationStatus,
)
from apps.integrations.models import OutboxEvent, OutboxStatus
from apps.registrations.models import Registration
from apps.registrations.services import build_registration_reminder_payload

logger = logging.getLogger(__name__)


@dataclass
class ReminderDispatchSummary:
    dispatched_count: int = 0
    skipped_count: int = 0
    expired_count: int = 0
    events: list[OutboxEvent] = field(default_factory=list)


def dispatch_workshop_reminders(
    now: datetime | None = None,
    workshop_id: str | None = None,
    registration_id: str | uuid.UUID | None = None,
    force: bool = False,
    past_due_threshold_minutes: int | None = None,
    batch_size: int = 50,
) -> ReminderDispatchSummary:
    """
    Identifies eligible registrations due for 15-minute workshop reminders and
    atomically generates 'registration.reminder' OutboxEvents.

    Delivery Model:
        Notification.scheduled_at <= now
                |
                ▼
        Reminder dispatcher (this service)
                |
                ▼
        Create registration.reminder OutboxEvent (idempotently)
                |
                ▼
        process_outbox
                |
                ▼
        n8n (external delivery)
                |
                ▼
        Django callback -> Notification = SENT

    Concurrency & Idempotency Guarantees:
    1. Uses PostgreSQL row-level locks (select_for_update) to prevent duplicate runs.
    2. Enforces database-level uniqueness on OutboxEvent (aggregate_id, event_type).
    3. Excludes registrations with existing 'registration.reminder' OutboxEvents or
       where reminder notifications are already marked SENT.
    4. Past-Due Protection: Workshops substantially past their start time are not sent;
       their pending reminder notifications are marked FAILED with clear diagnostic reasons,
       and a warning is logged (never silently discarded).

    Args:
        now: Optional explicit timestamp for testing or deterministic simulation. Defaults to timezone.now().
        workshop_id: Optional filter for a specific workshop ID.
        registration_id: Optional filter for a specific registration UUID.
        force: If True, bypasses the scheduled_at <= now check (useful for manual/immediate testing).
        past_due_threshold_minutes: Grace period in minutes after workshop.scheduled_at before considering
            the reminder expired. Defaults to settings.REMINDER_PAST_DUE_THRESHOLD_MINUTES (15 min).
        batch_size: Maximum registrations to evaluate per execution run.

    Returns:
        ReminderDispatchSummary containing dispatched, skipped, and expired counts.
    """
    current_time = now if now is not None else timezone.now()
    if past_due_threshold_minutes is None:
        past_due_threshold_minutes = getattr(settings, "REMINDER_PAST_DUE_THRESHOLD_MINUTES", 15)

    summary = ReminderDispatchSummary()

    # Step 1: Base query for pending reminder notifications
    notif_qs = Notification.objects.filter(
        notification_type=NotificationType.REMINDER,
        status=NotificationStatus.PENDING,
    )

    if not force:
        notif_qs = notif_qs.filter(scheduled_at__lte=current_time)

    if workshop_id:
        notif_qs = notif_qs.filter(registration__workshop_id=workshop_id)

    if registration_id:
        notif_qs = notif_qs.filter(registration_id=registration_id)

    # Exclude registrations that ALREADY have a registration.reminder OutboxEvent
    existing_outbox_reg_ids = OutboxEvent.objects.filter(
        event_type="registration.reminder"
    ).values_list("aggregate_id", flat=True)

    eligible_registration_ids = list(
        notif_qs.exclude(registration_id__in=existing_outbox_reg_ids)
        .order_by()
        .values_list("registration_id", flat=True)
        .distinct()[:batch_size]
    )

    if not eligible_registration_ids:
        logger.debug("No eligible registrations found for reminder dispatch at %s", current_time)
        return summary

    # Step 2: Process each eligible registration under concurrency-safe row lock
    for reg_id in eligible_registration_ids:
        with transaction.atomic():
            # Acquire row lock on Registration
            registration = (
                Registration.objects.select_for_update(skip_locked=True)
                .select_related("workshop")
                .filter(id=reg_id)
                .first()
            )
            if not registration:
                # Row was locked by another concurrent worker; skip cleanly
                summary.skipped_count += 1
                continue

            # Idempotency check 1: Has an outbox event already been created for this registration?
            if OutboxEvent.objects.filter(aggregate_id=registration.id, event_type="registration.reminder").exists():
                summary.skipped_count += 1
                continue

            # Fetch reminder notifications for this registration
            reminder_notifs = list(
                Notification.objects.select_for_update()
                .filter(registration=registration, notification_type=NotificationType.REMINDER)
            )
            if not reminder_notifs:
                summary.skipped_count += 1
                continue

            # Idempotency check 2: Are all reminder notifications already SENT?
            if all(n.status == NotificationStatus.SENT for n in reminder_notifs):
                summary.skipped_count += 1
                continue

            workshop = registration.workshop
            tz = ZoneInfo(workshop.timezone)
            past_due_cutoff = workshop.scheduled_at + timedelta(minutes=past_due_threshold_minutes)

            # Past-due check: If workshop is substantially past start time, do not dispatch
            if not force and current_time > past_due_cutoff:
                logger.warning(
                    "Skipping expired reminder for registration %s (%s): workshop '%s' scheduled at %s "
                    "is substantially past start time (cutoff=%s, now=%s).",
                    registration.id,
                    registration.normalized_email,
                    workshop.title,
                    workshop.scheduled_at.astimezone(tz).isoformat(),
                    past_due_cutoff.astimezone(tz).isoformat(),
                    current_time.astimezone(tz).isoformat(),
                )
                # Mark pending reminder notifications as FAILED so they are never silently lost
                Notification.objects.filter(
                    registration=registration,
                    notification_type=NotificationType.REMINDER,
                    status=NotificationStatus.PENDING,
                ).update(
                    status=NotificationStatus.FAILED,
                    last_error=(
                        f"Reminder expired: workshop started at {workshop.scheduled_at.astimezone(tz).isoformat()} "
                        f"(substantially past start time)."
                    ),
                    updated_at=current_time,
                )
                summary.expired_count += 1
                continue

            # Build standardized reminder payload conforming to n8n contract
            payload = build_registration_reminder_payload(registration, reminder_notifs)

            # Persist OutboxEvent protected by DB unique constraint
            try:
                outbox_event = OutboxEvent.objects.create(
                    event_type="registration.reminder",
                    aggregate_type="Registration",
                    aggregate_id=registration.id,
                    payload=payload,
                    status=OutboxStatus.PENDING,
                )
                summary.dispatched_count += 1
                summary.events.append(outbox_event)
                logger.info(
                    "Created registration.reminder OutboxEvent %s for registration %s (%s)",
                    outbox_event.id,
                    registration.id,
                    registration.normalized_email,
                )
            except IntegrityError:
                # Concurrent worker created the outbox event in a race condition
                logger.info(
                    "registration.reminder OutboxEvent already created concurrently for registration %s",
                    registration.id,
                )
                summary.skipped_count += 1

    return summary

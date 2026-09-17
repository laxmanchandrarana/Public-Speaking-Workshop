import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.notifications.services import dispatch_workshop_reminders
from apps.notifications.models import Notification, NotificationType, NotificationStatus
from apps.integrations.models import OutboxEvent
from apps.registrations.models import Registration

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Dispatches automatic 15-minute workshop reminders by generating "
        "'registration.reminder' OutboxEvents for eligible registrations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bypass the scheduled_at <= now check and immediately dispatch reminders (useful for testing).",
        )
        parser.add_argument(
            "--registration-id",
            type=str,
            default=None,
            help="Target a specific registration UUID.",
        )
        parser.add_argument(
            "--workshop-id",
            type=str,
            default=None,
            help="Target a specific workshop ID (e.g. 'public-speaking-workshop').",
        )
        parser.add_argument(
            "--now",
            type=str,
            default=None,
            help="Simulate execution at an explicit ISO-8601 timestamp (e.g. '2026-09-18T15:15:00+05:30').",
        )
        parser.add_argument(
            "--past-due-threshold",
            type=int,
            default=None,
            help="Minutes past workshop scheduled_at before considering reminder expired (default: 15).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Maximum number of registrations to process per run (default: 50).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Inspect and report eligible registrations without creating OutboxEvents or updating records.",
        )
        parser.add_argument(
            "--process-outbox",
            action="store_true",
            help="Immediately trigger the 'process_outbox' command after creating reminder events.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=None,
            help="Run continuously in a loop, sleeping for N seconds between runs (daemon mode).",
        )

    def parse_now_datetime(self, now_str: str | None) -> datetime | None:
        if not now_str:
            return None
        try:
            dt = datetime.fromisoformat(now_str)
            if timezone.is_naive(dt):
                default_tz = ZoneInfo(getattr(settings, "TIME_ZONE", "Asia/Kolkata"))
                dt = timezone.make_aware(dt, default_tz)
            return dt
        except ValueError as exc:
            raise CommandError(f"Invalid --now timestamp format: '{now_str}'. Must be ISO-8601 format. Error: {exc}")

    def run_once(self, options) -> int:
        now_dt = self.parse_now_datetime(options["now"])
        effective_now = now_dt or timezone.now()
        force = options["force"]
        registration_id = options["registration_id"]
        workshop_id = options["workshop_id"]
        past_due_threshold = options["past_due_threshold"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        process_outbox = options["process_outbox"]

        if dry_run:
            self.stdout.write(self.style.NOTICE("=== Running Reminder Dispatcher in DRY-RUN mode ==="))
            notif_qs = Notification.objects.filter(
                notification_type=NotificationType.REMINDER,
                status=NotificationStatus.PENDING,
            )
            if not force:
                notif_qs = notif_qs.filter(scheduled_at__lte=effective_now)
            if workshop_id:
                notif_qs = notif_qs.filter(registration__workshop_id=workshop_id)
            if registration_id:
                notif_qs = notif_qs.filter(registration_id=registration_id)

            existing_outbox_reg_ids = OutboxEvent.objects.filter(
                event_type="registration.reminder"
            ).values_list("aggregate_id", flat=True)

            eligible_reg_ids = list(
                notif_qs.exclude(registration_id__in=existing_outbox_reg_ids)
                .order_by()
                .values_list("registration_id", flat=True)
                .distinct()[:batch_size]
            )
            eligible_qs = Registration.objects.filter(id__in=eligible_reg_ids).select_related("workshop")
            count = eligible_qs.count()
            self.stdout.write(f"Effective evaluation time: {effective_now.isoformat()}")
            self.stdout.write(f"Found {count} eligible registration(s) for reminder dispatch:")
            threshold = past_due_threshold if past_due_threshold is not None else getattr(settings, "REMINDER_PAST_DUE_THRESHOLD_MINUTES", 15)
            for reg in eligible_qs:
                from datetime import timedelta
                ws = reg.workshop
                cutoff = ws.scheduled_at + timedelta(minutes=threshold)
                status_label = "[EXPIRED (past-due)]" if (not force and effective_now > cutoff) else "[ELIGIBLE FOR DISPATCH]"
                self.stdout.write(
                    f" - Registration: {reg.id} | Attendee: {reg.full_name} ({reg.normalized_email}) | Workshop: {ws.title} | {status_label}"
                )
            return count

        summary = dispatch_workshop_reminders(
            now=now_dt,
            workshop_id=workshop_id,
            registration_id=registration_id,
            force=force,
            past_due_threshold_minutes=past_due_threshold,
            batch_size=batch_size,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Reminder Dispatch Summary: "
                f"{summary.dispatched_count} created, "
                f"{summary.skipped_count} skipped, "
                f"{summary.expired_count} expired."
            )
        )

        for event in summary.events:
            self.stdout.write(
                f" [OK] Created OutboxEvent (id={event.id}, type={event.event_type}) for registration {event.aggregate_id}"
            )

        if process_outbox:
            call_command("process_outbox")

        return summary.dispatched_count

    def handle(self, *args, **options):
        interval = options.get("interval")
        if interval:
            self.stdout.write(self.style.NOTICE(f"Starting reminder dispatcher daemon (polling every {interval}s)..."))
            try:
                while True:
                    self.run_once(options)
                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Reminder dispatcher daemon stopped by user."))
        else:
            self.run_once(options)

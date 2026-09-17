from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q, F
from django.utils import timezone

from apps.integrations.models import OutboxEvent, OutboxStatus
from apps.integrations.services import (
    claim_outbox_events,
    process_claimed_event,
    validate_webhook_url,
    ConfigurationError,
)


class Command(BaseCommand):
    help = "Processes pending and eligible failed OutboxEvents and dispatches them to AUTOMATION_WEBHOOK_URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Maximum number of outbox events to claim and process in a single run.",
        )
        parser.add_argument(
            "--lease-seconds",
            type=int,
            default=getattr(settings, "OUTBOX_LEASE_TIMEOUT_SECONDS", 300),
            help="Number of seconds before a stuck PROCESSING event is considered abandoned and eligible for reclamation.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=10,
            help="HTTP request timeout in seconds.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Identify and report eligible events without claiming, modifying, or dispatching them.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        lease_seconds = options["lease_seconds"]
        timeout = options["timeout"]
        dry_run = options["dry_run"]

        webhook_url = getattr(settings, "AUTOMATION_WEBHOOK_URL", None)
        webhook_secret = getattr(settings, "AUTOMATION_WEBHOOK_SECRET", None)

        now = timezone.now()
        lease_cutoff = now - timedelta(seconds=lease_seconds)

        if dry_run:
            self.stdout.write(self.style.NOTICE("=== Running Outbox Dispatcher in DRY-RUN mode ==="))
            try:
                validate_webhook_url(webhook_url)
                self.stdout.write(f"Target URL: {webhook_url}")
            except ConfigurationError as exc:
                self.stdout.write(self.style.WARNING(f"Configuration Warning: {str(exc)}"))

            eligible_qs = OutboxEvent.objects.filter(
                (
                    Q(status=OutboxStatus.PENDING, next_retry_at__lte=now)
                    | Q(status=OutboxStatus.FAILED, next_retry_at__lte=now)
                    | Q(status=OutboxStatus.PROCESSING, processing_started_at__lte=lease_cutoff)
                )
                & Q(retry_count__lt=F("max_retries"))
            ).order_by("created_at")[:batch_size]

            count = eligible_qs.count()
            self.stdout.write(f"Found {count} eligible OutboxEvent(s) to process:")
            for event in eligible_qs:
                self.stdout.write(
                    f" - Event ID: {event.id} | Type: {event.event_type} | Current Status: {event.status} | Retries: {event.retry_count}/{event.max_retries}"
                )
            return

        # Normal execution: Claim events atomically with row locks
        try:
            validate_webhook_url(webhook_url)
        except ConfigurationError as exc:
            self.stdout.write(self.style.ERROR(f"Configuration Error: {str(exc)}"))
            return

        claimed_events = claim_outbox_events(
            batch_size=batch_size,
            lease_seconds=lease_seconds,
        )

        if not claimed_events:
            self.stdout.write("No eligible outbox events to process.")
            return

        self.stdout.write(f"Claimed {len(claimed_events)} outbox event(s) for dispatch.")

        success_count = 0
        failure_count = 0

        for event in claimed_events:
            result = process_claimed_event(
                event=event,
                webhook_url=webhook_url,
                webhook_secret=webhook_secret,
                timeout=timeout,
            )

            if result.is_success:
                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f" [OK] Dispatched {event.event_type} (id={event.id}) -> HTTP {result.status_code}"
                    )
                )
            else:
                failure_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f" [FAIL] Failed {event.event_type} (id={event.id}) -> {result.error_message}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {success_count} delivered, {failure_count} failed."
            )
        )

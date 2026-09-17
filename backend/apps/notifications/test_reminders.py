import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

from django.db import transaction
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
import requests

from apps.workshops.models import Workshop
from apps.registrations.models import Registration
from apps.registrations.services import register_attendee, build_registration_reminder_payload
from apps.notifications.models import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationStatus,
)
from apps.notifications.services import dispatch_workshop_reminders
from apps.integrations.models import OutboxEvent, OutboxStatus
from apps.integrations.services import process_claimed_event


class WorkshopReminderTests(TestCase):
    """
    Comprehensive test suite verifying all 12 required scenarios for the
    Automatic 15-Minute Workshop Reminder phase.
    """

    def setUp(self):
        # Workshop scheduled for 18 September 2026, 15:30:00 Asia/Kolkata (+05:30)
        self.workshop_tz = ZoneInfo("Asia/Kolkata")
        self.scheduled_time = datetime(2026, 9, 18, 15, 30, 0, tzinfo=self.workshop_tz)
        self.workshop = Workshop.objects.create(
            id="public-speaking-workshop",
            title="Public Speaking Workshop",
            scheduled_at=self.scheduled_time,
            timezone="Asia/Kolkata",
            reminder_lead_minutes=15,
            meeting_link="https://meet.google.com/xyz-workshop",
            is_active=True,
        )

        # Register a standard attendee
        self.registration, self.created = register_attendee(
            workshop=self.workshop,
            full_name="Aarav Sharma",
            email="aarav.sharma@example.com",
            phone_number="+919876543210",
            idempotency_key="test-reg-key-001",
        )

    # -------------------------------------------------------------------------
    # Test 1: Reminder scheduled exactly 15 minutes before workshop
    # -------------------------------------------------------------------------
    def test_1_reminder_scheduled_exactly_15_minutes_before_workshop(self):
        """
        Verify Workshop.reminder_at is computed dynamically as
        scheduled_at - 15 minutes.
        """
        expected_reminder_time = self.scheduled_time - timedelta(minutes=15)
        self.assertEqual(self.workshop.reminder_at, expected_reminder_time)
        # Check hour and minute in Asia/Kolkata
        reminder_local = self.workshop.reminder_at.astimezone(self.workshop_tz)
        self.assertEqual(reminder_local.year, 2026)
        self.assertEqual(reminder_local.month, 9)
        self.assertEqual(reminder_local.day, 18)
        self.assertEqual(reminder_local.hour, 15)
        self.assertEqual(reminder_local.minute, 15)
        self.assertEqual(reminder_local.second, 0)

    # -------------------------------------------------------------------------
    # Test 2: Correct timezone handling
    # -------------------------------------------------------------------------
    def test_2_correct_timezone_handling(self):
        """
        Verify that reminder_at and scheduled_at datetimes preserve the correct
        Asia/Kolkata timezone offset (+05:30) and match UTC conversion precisely.
        """
        tz = ZoneInfo("Asia/Kolkata")
        reminder_dt = self.workshop.reminder_at.astimezone(tz)
        scheduled_dt = self.workshop.scheduled_at.astimezone(tz)

        self.assertEqual(scheduled_dt.isoformat(), "2026-09-18T15:30:00+05:30")
        self.assertEqual(reminder_dt.isoformat(), "2026-09-18T15:15:00+05:30")

        # Verify UTC equivalent (15:15 IST is 09:45 UTC)
        utc_reminder = reminder_dt.astimezone(ZoneInfo("UTC"))
        self.assertEqual(utc_reminder.hour, 9)
        self.assertEqual(utc_reminder.minute, 45)

    # -------------------------------------------------------------------------
    # Test 3: Reminder email notification receives correct scheduled_at
    # -------------------------------------------------------------------------
    def test_3_reminder_email_notification_receives_correct_scheduled_at(self):
        """
        Verify that upon registration, the reminder EMAIL notification row
        is created with scheduled_at equal to workshop.reminder_at (15:15 IST).
        """
        reminder_email = Notification.objects.get(
            registration=self.registration,
            notification_type=NotificationType.REMINDER,
            channel=NotificationChannel.EMAIL,
        )
        self.assertEqual(reminder_email.status, NotificationStatus.PENDING)
        self.assertEqual(reminder_email.scheduled_at, self.workshop.reminder_at)

    # -------------------------------------------------------------------------
    # Test 4: Reminder WhatsApp notification receives correct scheduled_at
    # -------------------------------------------------------------------------
    def test_4_reminder_whatsapp_notification_receives_correct_scheduled_at(self):
        """
        Verify that upon registration, the reminder WHATSAPP notification row
        is created with scheduled_at equal to workshop.reminder_at (15:15 IST).
        """
        reminder_wa = Notification.objects.get(
            registration=self.registration,
            notification_type=NotificationType.REMINDER,
            channel=NotificationChannel.WHATSAPP,
        )
        self.assertEqual(reminder_wa.status, NotificationStatus.PENDING)
        self.assertEqual(reminder_wa.scheduled_at, self.workshop.reminder_at)

    # -------------------------------------------------------------------------
    # Test 5: registration.reminder OutboxEvent is created
    # -------------------------------------------------------------------------
    def test_5_registration_reminder_outbox_event_is_created(self):
        """
        Verify that when dispatch_workshop_reminders runs at reminder time,
        a 'registration.reminder' OutboxEvent is created with PENDING status.
        """
        reminder_time = self.workshop.reminder_at  # 2026-09-18 15:15:00 IST
        summary = dispatch_workshop_reminders(now=reminder_time)

        self.assertEqual(summary.dispatched_count, 1)
        self.assertEqual(summary.skipped_count, 0)
        self.assertEqual(summary.expired_count, 0)

        # Inspect database OutboxEvent
        outbox_event = OutboxEvent.objects.filter(
            aggregate_id=self.registration.id,
            event_type="registration.reminder",
        ).first()

        self.assertIsNotNone(outbox_event)
        self.assertEqual(outbox_event.status, OutboxStatus.PENDING)
        self.assertEqual(outbox_event.aggregate_type, "Registration")

        # Verify payload structure
        payload = outbox_event.payload
        self.assertEqual(payload["event_type"], "registration.reminder")
        self.assertEqual(payload["version"], "1.0")
        self.assertIn("event_id", payload)
        self.assertIn("occurred_at", payload)

        data = payload["data"]
        self.assertEqual(data["registration"]["id"], str(self.registration.id))
        self.assertEqual(data["registration"]["full_name"], "Aarav Sharma")
        self.assertEqual(data["registration"]["email"], "aarav.sharma@example.com")
        self.assertEqual(data["registration"]["phone_number"], "+919876543210")

        self.assertEqual(data["workshop"]["id"], "public-speaking-workshop")
        self.assertEqual(data["workshop"]["scheduled_at_iso"], "2026-09-18T15:30:00+05:30")
        self.assertEqual(data["workshop"]["reminder_at_iso"], "2026-09-18T15:15:00+05:30")
        self.assertEqual(data["workshop"]["timezone"], "Asia/Kolkata")

        # Verify notification IDs are present and resolve to actual reminder notification IDs
        rem_email = Notification.objects.get(
            registration=self.registration,
            notification_type=NotificationType.REMINDER,
            channel=NotificationChannel.EMAIL,
        )
        rem_wa = Notification.objects.get(
            registration=self.registration,
            notification_type=NotificationType.REMINDER,
            channel=NotificationChannel.WHATSAPP,
        )
        self.assertEqual(data["notifications"]["reminder_email_id"], str(rem_email.id))
        self.assertEqual(data["notifications"]["reminder_whatsapp_id"], str(rem_wa.id))

    # -------------------------------------------------------------------------
    # Test 6: Duplicate scheduler execution does not create duplicate reminder events
    # -------------------------------------------------------------------------
    def test_6_duplicate_scheduler_execution_does_not_create_duplicate_events(self):
        """
        Verify idempotency: Running the scheduler multiple times sequentially
        only creates a single OutboxEvent for the registration.
        """
        reminder_time = self.workshop.reminder_at

        # First run: dispatches 1 event
        summary1 = dispatch_workshop_reminders(now=reminder_time)
        self.assertEqual(summary1.dispatched_count, 1)

        # Second run: detects existing outbox event, skips without duplicating
        summary2 = dispatch_workshop_reminders(now=reminder_time)
        self.assertEqual(summary2.dispatched_count, 0)
        self.assertEqual(summary2.skipped_count, 0)  # Excluded from candidate query

        # Third run: same result
        summary3 = dispatch_workshop_reminders(now=reminder_time)
        self.assertEqual(summary3.dispatched_count, 0)

        # Assert exactly ONE registration.reminder OutboxEvent in DB
        self.assertEqual(
            OutboxEvent.objects.filter(
                aggregate_id=self.registration.id,
                event_type="registration.reminder",
            ).count(),
            1,
        )

    # -------------------------------------------------------------------------
    # Test 7: Multiple concurrent workers do not create duplicate reminder events
    # -------------------------------------------------------------------------
    def test_7_multiple_concurrent_workers_do_not_create_duplicate_events(self):
        """
        Verify database-level and concurrency safety:
        Even if two workers evaluate the same registration concurrently,
        only 1 OutboxEvent is created, and the unique constraint / lock handles it cleanly.
        """
        from django.db import IntegrityError

        reminder_time = self.workshop.reminder_at

        # Worker 1 succeeds
        summary1 = dispatch_workshop_reminders(now=reminder_time)
        self.assertEqual(summary1.dispatched_count, 1)

        # Simulate Worker 2 attempting to insert an OutboxEvent with the same (aggregate_id, event_type)
        payload = build_registration_reminder_payload(self.registration)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                OutboxEvent.objects.create(
                    event_type="registration.reminder",
                    aggregate_type="Registration",
                    aggregate_id=self.registration.id,
                    payload=payload,
                    status=OutboxStatus.PENDING,
                )

        # Still exactly 1 event in database
        self.assertEqual(
            OutboxEvent.objects.filter(
                aggregate_id=self.registration.id,
                event_type="registration.reminder",
            ).count(),
            1,
        )

    # -------------------------------------------------------------------------
    # Test 8: process_outbox dispatches registration.reminder
    # -------------------------------------------------------------------------
    @override_settings(AUTOMATION_WEBHOOK_URL="https://n8n.atmakriti.com/webhook/public-speaking-workshop")
    def test_8_process_outbox_dispatches_registration_reminder(self):
        """
        Verify that process_outbox management command claims and dispatches
        the registration.reminder OutboxEvent to the automation webhook.
        """
        # Create the reminder event
        dispatch_workshop_reminders(now=self.workshop.reminder_at)

        reminder_event = OutboxEvent.objects.get(
            aggregate_id=self.registration.id,
            event_type="registration.reminder",
        )
        self.assertEqual(reminder_event.status, OutboxStatus.PENDING)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"accepted": true, "message": "Reminder event received"}'

        with patch("requests.post", return_value=mock_resp) as mock_post:
            call_command("process_outbox")

            mock_post.assert_called()
            # Verify the event status transitioned to DELIVERED
            reminder_event.refresh_from_db()
            self.assertEqual(reminder_event.status, OutboxStatus.DELIVERED)
            self.assertIsNotNone(reminder_event.delivered_at)

    # -------------------------------------------------------------------------
    # Test 9: n8n receives the expected reminder event payload
    # -------------------------------------------------------------------------
    def test_9_n8n_receives_expected_reminder_event_payload(self):
        """
        Verify the exact JSON structure and values posted to n8n over HTTP:
        event_type, registration details, workshop timestamps in +05:30,
        and reminder notification UUIDs.
        """
        dispatch_workshop_reminders(now=self.workshop.reminder_at)
        reminder_event = OutboxEvent.objects.get(
            aggregate_id=self.registration.id,
            event_type="registration.reminder",
        )

        captured_request = {}

        def capture_post(url, data=None, headers=None, **kwargs):
            captured_request["url"] = url
            captured_request["data"] = json.loads(data.decode("utf-8") if isinstance(data, bytes) else data)
            captured_request["headers"] = headers
            mock = MagicMock()
            mock.status_code = 200
            mock.text = '{"accepted": true}'
            return mock

        with patch("requests.post", side_effect=capture_post):
            process_claimed_event(
                reminder_event,
                webhook_url="https://n8n.atmakriti.com/webhook/public-speaking-workshop",
            )

        self.assertEqual(captured_request["headers"]["X-Event-Type"], "registration.reminder")

        sent_body = captured_request["data"]
        self.assertEqual(sent_body["event_type"], "registration.reminder")
        self.assertEqual(sent_body["version"], "1.0")

        data = sent_body["data"]
        self.assertEqual(data["registration"]["id"], str(self.registration.id))
        self.assertEqual(data["registration"]["full_name"], "Aarav Sharma")
        self.assertEqual(data["registration"]["email"], "aarav.sharma@example.com")
        self.assertEqual(data["registration"]["phone_number"], "+919876543210")

        self.assertEqual(data["workshop"]["id"], "public-speaking-workshop")
        self.assertEqual(data["workshop"]["title"], "Public Speaking Workshop")
        self.assertEqual(data["workshop"]["scheduled_at_iso"], "2026-09-18T15:30:00+05:30")
        self.assertEqual(data["workshop"]["reminder_at_iso"], "2026-09-18T15:15:00+05:30")
        self.assertEqual(data["workshop"]["timezone"], "Asia/Kolkata")

        self.assertIsNotNone(data["notifications"]["reminder_email_id"])
        self.assertIsNotNone(data["notifications"]["reminder_whatsapp_id"])
        self.assertIn("15 minutes", data["messages"]["whatsapp_text"])

    # -------------------------------------------------------------------------
    # Test 10: Existing registration.created behavior remains unchanged
    # -------------------------------------------------------------------------
    def test_10_existing_registration_created_behavior_remains_unchanged(self):
        """
        Verify that attendee registration still creates a registration.created
        OutboxEvent with all expected confirmation details without interference.
        """
        reg2, created2 = register_attendee(
            workshop=self.workshop,
            full_name="Bhavna Joshi",
            email="bhavna.joshi@example.com",
            phone_number="+919876543211",
            idempotency_key="test-reg-key-002",
        )
        self.assertTrue(created2)

        # Verify registration.created OutboxEvent was generated
        created_event = OutboxEvent.objects.filter(
            aggregate_id=reg2.id,
            event_type="registration.created",
        ).first()

        self.assertIsNotNone(created_event)
        self.assertEqual(created_event.payload["event_type"], "registration.created")
        self.assertEqual(created_event.payload["data"]["registration"]["email"], "bhavna.joshi@example.com")
        self.assertIsNotNone(created_event.payload["data"]["notifications"]["confirmation_email_id"])
        self.assertIsNotNone(created_event.payload["data"]["notifications"]["confirmation_whatsapp_id"])

        # Exactly 4 notifications created
        self.assertEqual(reg2.notifications.count(), 4)

    # -------------------------------------------------------------------------
    # Test 11: Already-sent reminder is not sent again
    # -------------------------------------------------------------------------
    def test_11_already_sent_reminder_is_not_sent_again(self):
        """
        Verify that if reminder notifications are already in SENT status
        (or reminder OutboxEvent is DELIVERED), no new reminder event is generated.
        """
        # Mark reminder notifications as SENT
        Notification.objects.filter(
            registration=self.registration,
            notification_type=NotificationType.REMINDER,
        ).update(
            status=NotificationStatus.SENT,
            sent_at=timezone.now(),
        )

        reminder_time = self.workshop.reminder_at
        summary = dispatch_workshop_reminders(now=reminder_time)

        self.assertEqual(summary.dispatched_count, 0)
        self.assertEqual(
            OutboxEvent.objects.filter(
                aggregate_id=self.registration.id,
                event_type="registration.reminder",
            ).count(),
            0,
        )

    # -------------------------------------------------------------------------
    # Test 12: Failed outbox delivery remains retryable
    # -------------------------------------------------------------------------
    def test_12_failed_outbox_delivery_remains_retryable(self):
        """
        Verify that if n8n is temporarily down or returns 500 when dispatching
        registration.reminder, the OutboxEvent status becomes FAILED with
        retry_count incremented and next_retry_at scheduled for subsequent retry.
        """
        dispatch_workshop_reminders(now=self.workshop.reminder_at)
        reminder_event = OutboxEvent.objects.get(
            aggregate_id=self.registration.id,
            event_type="registration.reminder",
        )

        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.text = "Internal Server Error"

        with patch("requests.post", return_value=mock_500):
            result = process_claimed_event(
                reminder_event,
                webhook_url="https://n8n.atmakriti.com/webhook/public-speaking-workshop",
            )

            self.assertFalse(result.is_success)
            self.assertTrue(result.is_retryable)

            reminder_event.refresh_from_db()
            self.assertEqual(reminder_event.status, OutboxStatus.FAILED)
            self.assertEqual(reminder_event.retry_count, 1)
            self.assertGreater(reminder_event.next_retry_at, timezone.now())
            self.assertIn("HTTP 500", reminder_event.last_error)

    # -------------------------------------------------------------------------
    # Test 13: Past-due workshop reminders are expired and logged
    # -------------------------------------------------------------------------
    def test_13_past_due_workshop_reminders_marked_failed_and_not_dispatched(self):
        """
        Verify past-due handling: If the worker runs long after the workshop start time
        (past the grace cutoff), it logs why, marks pending reminder notifications FAILED,
        and does not dispatch outbox events.
        """
        # Workshop scheduled for 15:30. Evaluate at 16:00 (30 min past start, past default 15 min cutoff)
        substantially_late_time = self.scheduled_time + timedelta(minutes=30)

        with self.assertLogs("apps.notifications.services", level="WARNING") as cm:
            summary = dispatch_workshop_reminders(
                now=substantially_late_time,
                past_due_threshold_minutes=15,
            )

        self.assertEqual(summary.dispatched_count, 0)
        self.assertEqual(summary.expired_count, 1)
        self.assertTrue(any("substantially past start time" in msg for msg in cm.output))

        # Check reminder notifications transitioned to FAILED
        reminder_notifs = Notification.objects.filter(
            registration=self.registration,
            notification_type=NotificationType.REMINDER,
        )
        for notif in reminder_notifs:
            self.assertEqual(notif.status, NotificationStatus.FAILED)
            self.assertIn("Reminder expired", notif.last_error)

        # No OutboxEvent was created
        self.assertEqual(
            OutboxEvent.objects.filter(
                aggregate_id=self.registration.id,
                event_type="registration.reminder",
            ).count(),
            0,
        )

    # -------------------------------------------------------------------------
    # Test 14: Future reminders not dispatched prior to reminder_at unless forced
    # -------------------------------------------------------------------------
    def test_14_future_reminders_not_dispatched_prior_to_reminder_at_unless_forced(self):
        """
        Verify that prior to reminder_at, reminders are not dispatched.
        With force=True, they are dispatched immediately.
        """
        # Current time: 1 hour before reminder time
        before_reminder = self.workshop.reminder_at - timedelta(hours=1)

        # Without force -> 0 dispatched
        summary_normal = dispatch_workshop_reminders(now=before_reminder, force=False)
        self.assertEqual(summary_normal.dispatched_count, 0)

        # With force=True -> immediately dispatched
        summary_forced = dispatch_workshop_reminders(now=before_reminder, force=True)
        self.assertEqual(summary_forced.dispatched_count, 1)
        self.assertEqual(
            OutboxEvent.objects.filter(
                aggregate_id=self.registration.id,
                event_type="registration.reminder",
            ).count(),
            1,
        )

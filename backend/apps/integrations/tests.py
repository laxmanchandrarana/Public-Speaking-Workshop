import hmac
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
import requests
from rest_framework.test import APIClient

from apps.workshops.models import Workshop
from apps.registrations.models import Registration
from apps.notifications.models import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationStatus,
)
from .models import OutboxEvent, OutboxStatus
from .services import (
    claim_outbox_events,
    dispatch_single_event,
    process_claimed_event,
    compute_backoff_delay,
    generate_webhook_signature,
    ConfigurationError,
)


class OutboxDispatcherTests(TestCase):
    def setUp(self):
        self.webhook_url = "https://n8n.atmakriti.com/webhook/test"
        self.webhook_secret = "test-super-secret-key-12345"
        self.reg_id = uuid.uuid4()
        self.stable_event_id = str(uuid.uuid4())
        self.event = OutboxEvent.objects.create(
            event_type="registration.created",
            aggregate_type="Registration",
            aggregate_id=self.reg_id,
            payload={
                "event_id": self.stable_event_id,
                "event_type": "registration.created",
                "data": {"registration_id": str(self.reg_id), "name": "Priya"},
            },
            status=OutboxStatus.PENDING,
        )

    # 1. Successful 2xx Delivery
    @override_settings(AUTOMATION_WEBHOOK_URL="https://n8n.atmakriti.com/webhook/test")
    def test_successful_2xx_delivery(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status": "success"}'

        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = process_claimed_event(self.event, webhook_url="https://n8n.atmakriti.com/webhook/test")

            self.assertTrue(result.is_success)
            self.assertEqual(result.status_code, 200)

            self.event.refresh_from_db()
            self.assertEqual(self.event.status, OutboxStatus.DELIVERED)
            self.assertIsNotNone(self.event.delivered_at)
            self.assertIsNone(self.event.processing_started_at)
            self.assertIsNone(self.event.last_error)
            mock_post.assert_called_once()

    # 2. 400 Bad Request Permanent Failure (No Retry)
    def test_400_permanent_failure_no_retry(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "Invalid format"}'

        with patch("requests.post", return_value=mock_resp):
            result = process_claimed_event(
                self.event,
                webhook_url=self.webhook_url,
            )

            self.assertFalse(result.is_success)
            self.assertEqual(result.status_code, 400)
            self.assertFalse(result.is_retryable)

            self.event.refresh_from_db()
            self.assertEqual(self.event.status, OutboxStatus.FAILED)
            # Retries exhausted so it is not re-claimed
            self.assertEqual(self.event.retry_count, self.event.max_retries)
            self.assertIn("Permanent Failure", self.event.last_error)
            self.assertIsNone(self.event.processing_started_at)

            # Assert claim_outbox_events does NOT claim this permanently failed event
            claimed = claim_outbox_events(batch_size=10)
            self.assertNotIn(self.event.id, [e.id for e in claimed])

    def test_404_and_410_permanent_failures(self):
        # 404 (workflow disabled) and 410 (workflow deleted)
        for code in (404, 410):
            mock_resp = MagicMock()
            mock_resp.status_code = code
            mock_resp.text = "Workflow unavailable"

            ev = OutboxEvent.objects.create(
                event_type="registration.created",
                aggregate_type="Registration",
                aggregate_id=uuid.uuid4(),
                payload={"test": "data"},
                status=OutboxStatus.PROCESSING,
                processing_started_at=timezone.now(),
            )
            with patch("requests.post", return_value=mock_resp):
                result = process_claimed_event(ev, webhook_url=self.webhook_url)
                self.assertFalse(result.is_retryable)
                ev.refresh_from_db()
                self.assertEqual(ev.status, OutboxStatus.FAILED)
                self.assertEqual(ev.retry_count, ev.max_retries)
                self.assertIn("Permanent Failure", ev.last_error)

    def test_408_and_429_are_retryable(self):
        for code in (408, 429):
            mock_resp = MagicMock()
            mock_resp.status_code = code
            mock_resp.text = "Too many requests or timeout"

            ev = OutboxEvent.objects.create(
                event_type="registration.created",
                aggregate_type="Registration",
                aggregate_id=uuid.uuid4(),
                payload={"test": "data"},
                status=OutboxStatus.PROCESSING,
                processing_started_at=timezone.now(),
            )
            with patch("requests.post", return_value=mock_resp):
                result = process_claimed_event(ev, webhook_url=self.webhook_url)
                self.assertTrue(result.is_retryable)
                ev.refresh_from_db()
                self.assertEqual(ev.status, OutboxStatus.FAILED)
                self.assertEqual(ev.retry_count, 1)
                self.assertGreater(ev.next_retry_at, timezone.now())

    # 3. 500 Internal Server Error Response
    def test_500_response_failure_and_retry(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("requests.post", return_value=mock_resp):
            result = process_claimed_event(
                self.event,
                webhook_url=self.webhook_url,
            )

            self.assertFalse(result.is_success)
            self.assertEqual(result.status_code, 500)

            self.event.refresh_from_db()
            self.assertEqual(self.event.status, OutboxStatus.FAILED)
            self.assertEqual(self.event.retry_count, 1)
            self.assertIn("HTTP 500", self.event.last_error)

    # 4. Timeout Handling
    def test_timeout_failure(self):
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")):
            result = process_claimed_event(
                self.event,
                webhook_url=self.webhook_url,
                timeout=5,
            )

            self.assertFalse(result.is_success)
            self.assertIn("Request timeout after 5s", result.error_message)

            self.event.refresh_from_db()
            self.assertEqual(self.event.status, OutboxStatus.FAILED)
            self.assertEqual(self.event.retry_count, 1)
            self.assertIn("Request timeout", self.event.last_error)

    # 5. Connection Failure
    def test_connection_failure(self):
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Failed to connect")):
            result = process_claimed_event(
                self.event,
                webhook_url=self.webhook_url,
            )

            self.assertFalse(result.is_success)
            self.assertIn("Connection failure", result.error_message)

            self.event.refresh_from_db()
            self.assertEqual(self.event.status, OutboxStatus.FAILED)
            self.assertEqual(self.event.retry_count, 1)
            self.assertIn("Connection failure", self.event.last_error)

    # 6. Retry Exponential Backoff Calculation
    def test_exponential_backoff_calculation(self):
        self.assertEqual(compute_backoff_delay(1, base_seconds=30).total_seconds(), 30)
        self.assertEqual(compute_backoff_delay(2, base_seconds=30).total_seconds(), 60)
        self.assertEqual(compute_backoff_delay(3, base_seconds=30).total_seconds(), 120)
        self.assertEqual(compute_backoff_delay(4, base_seconds=30).total_seconds(), 240)
        self.assertEqual(compute_backoff_delay(10, base_seconds=30, max_seconds=3600).total_seconds(), 3600)

    # 7. Max Retries Exhaustion
    def test_max_retries_exhaustion(self):
        self.event.retry_count = 5
        self.event.max_retries = 5
        self.event.status = OutboxStatus.FAILED
        self.event.save()

        # Should not be claimed because retry_count >= max_retries
        claimed = claim_outbox_events(batch_size=10)
        self.assertNotIn(self.event.id, [e.id for e in claimed])

    # 8. Stale PROCESSING Crash Recovery (Lease Expiry)
    def test_stale_processing_recovery(self):
        stale_time = timezone.now() - timedelta(seconds=400)
        self.event.status = OutboxStatus.PROCESSING
        self.event.processing_started_at = stale_time
        self.event.save()

        # Lease timeout is 300s. Event was started 400s ago, so it's stale
        claimed = claim_outbox_events(batch_size=10, lease_seconds=300)
        self.assertIn(self.event.id, [e.id for e in claimed])

        self.event.refresh_from_db()
    # 9. Concurrent Dispatcher Safety
    def test_concurrent_dispatcher_safety(self):
        # Worker 1 claims eligible events
        claimed_first = claim_outbox_events(batch_size=10)
        self.assertEqual(len(claimed_first), 1)
        self.assertEqual(claimed_first[0].id, self.event.id)

        # Worker 2 immediately queries - cannot claim already claimed events
        claimed_second = claim_outbox_events(batch_size=10)
        self.assertEqual(len(claimed_second), 0)

    # 10. Stable Event ID Across Retries
    def test_stable_event_id_across_retries(self):
        sent_event_ids = []

        def capture_headers(*args, **kwargs):
            headers = kwargs.get("headers", {})
            sent_event_ids.append(headers.get("X-Event-ID"))
            mock_fail = MagicMock()
            mock_fail.status_code = 502
            mock_fail.text = "Bad Gateway"
            return mock_fail

        with patch("requests.post", side_effect=capture_headers):
            # Attempt 1
            process_claimed_event(self.event, webhook_url=self.webhook_url)
            # Attempt 2
            process_claimed_event(self.event, webhook_url=self.webhook_url)

        self.assertEqual(len(sent_event_ids), 2)
        # Verify both attempts carried the EXACT same stable event_id
        self.assertEqual(sent_event_ids[0], self.stable_event_id)
        self.assertEqual(sent_event_ids[1], self.stable_event_id)

    # 10. Correct HMAC Signature Generation
    def test_correct_hmac_signature_generation(self):
        captured_headers = {}

        def capture_call(*args, **kwargs):
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            mock = MagicMock()
            mock.status_code = 200
            mock.text = "OK"
            return mock

        with patch("requests.post", side_effect=capture_call):
            dispatch_single_event(
                self.event,
                webhook_url=self.webhook_url,
                webhook_secret=self.webhook_secret,
            )

        self.assertIn("X-Signature", captured_headers)
        sig = captured_headers["X-Signature"]
        self.assertTrue(sig.startswith("sha256="))

        # Validate signature matches payload
        payload_bytes = json.dumps(self.event.payload, separators=(",", ":"), default=str).encode("utf-8")
        expected_sig = generate_webhook_signature(self.webhook_secret, payload_bytes)
        self.assertEqual(sig, expected_sig)

    # 11. No External Call When AUTOMATION_WEBHOOK_URL is Unconfigured
    @override_settings(AUTOMATION_WEBHOOK_URL="")
    def test_no_external_call_when_url_not_configured(self):
        with patch("requests.post") as mock_post:
            with self.assertRaises(ConfigurationError):
                dispatch_single_event(self.event, webhook_url="")

            with self.assertRaises(ConfigurationError):
                dispatch_single_event(self.event, webhook_url=None)

            mock_post.assert_not_called()

    # 12. Malformed Automation URL Configuration
    def test_malformed_automation_url(self):
        with patch("requests.post") as mock_post:
            with self.assertRaises(ConfigurationError):
                dispatch_single_event(self.event, webhook_url="ftp://invalid-protocol.com/webhook")

            with self.assertRaises(ConfigurationError):
                dispatch_single_event(self.event, webhook_url="just-a-string-without-scheme")

            mock_post.assert_not_called()

    # 13. Dry-Run Mode in Management Command
    @override_settings(AUTOMATION_WEBHOOK_URL="https://n8n.atmakriti.com/webhook/dryrun")
    def test_process_outbox_command_dry_run(self):
        with patch("requests.post") as mock_post:
            call_command("process_outbox", "--dry-run")
            mock_post.assert_not_called()

        self.event.refresh_from_db()
        self.assertEqual(self.event.status, OutboxStatus.PENDING)
        self.assertIsNone(self.event.processing_started_at)

    # 14. Management Command Execution with Successful Delivery
    @override_settings(
        AUTOMATION_WEBHOOK_URL="https://n8n.atmakriti.com/webhook/live",
        AUTOMATION_WEBHOOK_SECRET="cmd-secret"
    )
    def test_process_outbox_command_live_execution(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"result": "success"}'

        with patch("requests.post", return_value=mock_resp):
            call_command("process_outbox")

        self.event.refresh_from_db()
        self.assertEqual(self.event.status, OutboxStatus.DELIVERED)
        self.assertIsNotNone(self.event.delivered_at)


class NotificationClaimAndCallbackTests(TestCase):
    """
    Comprehensive tests for the provider-agnostic internal notification claim
    and automation callback endpoints:
    - Atomicity & claiming lifecycle
    - Concurrency safety
    - Stale lease recovery
    - Callback idempotency
    - Secret authentication
    """

    def setUp(self):
        self.client = APIClient()
        self.secret = "test-webhook-secret-999"
        self.claim_url = reverse("notification-claim")
        self.callback_url = reverse("automation-callback")

        self.workshop = Workshop.objects.create(
            id="public-speaking-workshop",
            title="Public Speaking Workshop",
            scheduled_at=datetime(2026, 9, 18, 15, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
            timezone="Asia/Kolkata",
            reminder_lead_minutes=15,
            is_active=True,
        )

        self.registration = Registration.objects.create(
            workshop=self.workshop,
            full_name="Priya Sharma",
            email="priya.sharma@example.com",
            normalized_email="priya.sharma@example.com",
            phone_number="+919876543210",
        )

        self.notification = Notification.objects.create(
            registration=self.registration,
            notification_type=NotificationType.CONFIRMATION,
            channel=NotificationChannel.WHATSAPP,
            status=NotificationStatus.PENDING,
            scheduled_at=timezone.now(),
        )

    # 1. PENDING notification can be claimed once
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_pending_notification_can_be_claimed_once(self):
        resp = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["should_send"])
        self.assertEqual(data["status"], "PROCESSING")
        self.assertEqual(data["notification_id"], str(self.notification.id))

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, NotificationStatus.PROCESSING)
        self.assertIsNotNone(self.notification.processing_started_at)

    # 2. Second simultaneous claim cannot claim it
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_second_claim_cannot_claim_it(self):
        # First claim succeeds
        resp1 = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.json()["should_send"])

        # Immediate second claim must be rejected (should_send=False)
        resp2 = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.json()["should_send"])
        self.assertIn("PROCESSING", resp2.json()["reason"])

    # 3. SENT notification cannot be claimed again
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_sent_notification_cannot_be_claimed_again(self):
        self.notification.status = NotificationStatus.SENT
        self.notification.sent_at = timezone.now()
        self.notification.save()

        resp = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["should_send"])
        self.assertEqual(resp.json()["status"], "SENT")
        self.assertIn("already been SENT", resp.json()["reason"])

    # 4. PROCESSING notification cannot be claimed again
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_processing_notification_cannot_be_claimed_again(self):
        self.notification.status = NotificationStatus.PROCESSING
        self.notification.processing_started_at = timezone.now()
        self.notification.save()

        resp = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["should_send"])

    # 5. Stale PROCESSING notification can be reclaimed
    @override_settings(
        AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999",
        REMINDER_LEASE_TIMEOUT_SECONDS=300,
    )
    def test_stale_processing_notification_can_be_reclaimed(self):
        # Lease expired 10 minutes ago
        past_time = timezone.now() - timedelta(minutes=10)
        self.notification.status = NotificationStatus.PROCESSING
        self.notification.processing_started_at = past_time
        self.notification.save()

        resp = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["should_send"])
        self.assertIn("Recovered stale PROCESSING lease", data["message"])

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, NotificationStatus.PROCESSING)
        self.assertGreater(self.notification.processing_started_at, past_time)

    # 6. Successful callback marks SENT
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_successful_callback_marks_sent(self):
        self.notification.status = NotificationStatus.PROCESSING
        self.notification.processing_started_at = timezone.now()
        self.notification.save()

        callback_payload = {
            "notification_id": str(self.notification.id),
            "channel": "WHATSAPP",
            "status": "SENT",
            "external_id": "evo_msg_12345678",
            "error": None,
        }
        resp = self.client.post(
            self.callback_url,
            data=callback_payload,
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "SENT")

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, NotificationStatus.SENT)
        self.assertEqual(self.notification.external_id, "evo_msg_12345678")
        self.assertIsNotNone(self.notification.sent_at)
        self.assertIsNone(self.notification.processing_started_at)
        self.assertIsNone(self.notification.last_error)

    # 7. Failed callback marks FAILED
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_failed_callback_marks_failed(self):
        self.notification.status = NotificationStatus.PROCESSING
        self.notification.processing_started_at = timezone.now()
        self.notification.save()

        callback_payload = {
            "notification_id": str(self.notification.id),
            "channel": "WHATSAPP",
            "status": "FAILED",
            "error": "Recipient number not registered on WhatsApp",
        }
        resp = self.client.post(
            self.callback_url,
            data=callback_payload,
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "FAILED")

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, NotificationStatus.FAILED)
        self.assertEqual(self.notification.attempts, 1)
        self.assertEqual(self.notification.last_error, "Recipient number not registered on WhatsApp")
        self.assertIsNone(self.notification.processing_started_at)

    # 8. Duplicate callback is harmless and cannot downgrade SENT
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_duplicate_callback_is_harmless_and_cannot_downgrade_sent(self):
        self.notification.status = NotificationStatus.SENT
        self.notification.sent_at = timezone.now()
        self.notification.external_id = "original_msg_001"
        self.notification.save()

        # Duplicate SENT callback
        resp1 = self.client.post(
            self.callback_url,
            data={
                "notification_id": str(self.notification.id),
                "status": "SENT",
                "external_id": "original_msg_001",
            },
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("already marked as SENT", resp1.json()["message"])

        # Stale/delayed FAILED callback arriving after SENT must NOT revert to FAILED
        resp2 = self.client.post(
            self.callback_url,
            data={
                "notification_id": str(self.notification.id),
                "status": "FAILED",
                "error": "Late network timeout",
            },
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("already marked as SENT", resp2.json()["message"])

        self.notification.refresh_from_db()
        self.assertEqual(self.notification.status, NotificationStatus.SENT)
        self.assertEqual(self.notification.external_id, "original_msg_001")

    # 9. Unauthorized claim and callback is rejected
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_unauthorized_claim_and_callback_is_rejected(self):
        # Claim without secret
        resp_claim_no_auth = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
        )
        self.assertEqual(resp_claim_no_auth.status_code, 401)
        self.assertFalse(resp_claim_no_auth.json()["should_send"])

        # Claim with wrong secret
        resp_claim_bad_auth = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET="wrong-secret-value",
        )
        self.assertEqual(resp_claim_bad_auth.status_code, 401)

        # Callback without secret
        resp_cb_no_auth = self.client.post(
            self.callback_url,
            data={"notification_id": str(self.notification.id), "status": "SENT"},
            format="json",
        )
        self.assertEqual(resp_cb_no_auth.status_code, 401)

        # Callback with Bearer token authentication (valid)
        resp_cb_bearer = self.client.post(
            self.callback_url,
            data={"notification_id": str(self.notification.id), "status": "SENT"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self.secret}",
        )
        self.assertEqual(resp_cb_bearer.status_code, 200)

    # 10. Concurrent claims are safe (Row-level locking)
    @override_settings(AUTOMATION_WEBHOOK_SECRET="test-webhook-secret-999")
    def test_concurrent_claims_are_safe(self):
        # Claim by notification_id
        resp1 = self.client.post(
            self.claim_url,
            data={"notification_id": str(self.notification.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.json()["should_send"])

        # Concurrent claim by registration_id
        resp2 = self.client.post(
            self.claim_url,
            data={"registration_id": str(self.registration.id), "channel": "WHATSAPP"},
            format="json",
            HTTP_X_WEBHOOK_SECRET=self.secret,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.json()["should_send"])
        self.assertIn("PROCESSING", resp2.json()["reason"])

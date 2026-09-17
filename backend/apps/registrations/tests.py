import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
from django.test import TestCase
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.workshops.models import Workshop
from apps.notifications.models import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationStatus,
)
from apps.integrations.models import OutboxEvent, OutboxStatus
from .models import Registration, IdempotencyRecord
from .services import register_attendee, IdempotencyConflictError


class RegistrationDomainAndApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("registration-create")
        self.scheduled_time = datetime(2026, 9, 18, 15, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.workshop = Workshop.objects.create(
            id="public-speaking-workshop",
            title="Public Speaking Workshop",
            scheduled_at=self.scheduled_time,
            timezone="Asia/Kolkata",
            reminder_lead_minutes=15,
            is_active=True,
        )

    # 1. Successful Registration (HTTP 201)
    def test_successful_registration(self):
        payload = {
            "full_name": "Priya Sharma",
            "email": "priya.sharma@example.com",
            "phone_number": "+919876543210",
        }
        idempotency_key = "idemp-" + str(uuid.uuid4())
        response = self.client.post(self.url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY=idempotency_key)

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("registration_id", data)
        self.assertEqual(data["full_name"], "Priya Sharma")
        self.assertEqual(data["email"], "priya.sharma@example.com")
        self.assertEqual(data["phone_number"], "+919876543210")
        self.assertEqual(data["workshop"]["title"], "Public Speaking Workshop")
        self.assertEqual(data["workshop"]["timezone"], "Asia/Kolkata")
        self.assertEqual(data["workshop"]["scheduled_at"], "2026-09-18T15:30:00+05:30")
        self.assertIn("Registration successful", data["message"])

        # Check DB
        reg = Registration.objects.get(id=data["registration_id"])
        self.assertEqual(reg.normalized_email, "priya.sharma@example.com")
        self.assertEqual(reg.idempotency_key, idempotency_key)

    # 2. Email Normalization (strip and lowercase)
    def test_email_normalization(self):
        payload = {
            "full_name": "Priya Sharma",
            "email": "   PRIYA.Sharma@EXAMPLE.Com   ",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 201)

        reg = Registration.objects.get(id=response.json()["registration_id"])
        self.assertEqual(reg.normalized_email, "priya.sharma@example.com")

    # 3. Phone Normalization (E.164 format)
    def test_phone_normalization_local_indian_number(self):
        payload = {
            "full_name": "Rahul Verma",
            "email": "rahul@example.com",
            "phone_number": "9876543210",  # Standard 10-digit Indian number without country code
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 201)

        reg = Registration.objects.get(id=response.json()["registration_id"])
        self.assertEqual(reg.phone_number, "+919876543210")

    def test_phone_normalization_formatted_number(self):
        payload = {
            "full_name": "Rahul Verma",
            "email": "rahul.v@example.com",
            "phone_number": "+91 98765 43210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 201)

        reg = Registration.objects.get(id=response.json()["registration_id"])
        self.assertEqual(reg.phone_number, "+919876543210")

    # 4. Invalid Email Validation
    def test_invalid_email(self):
        payload = {
            "full_name": "Priya Sharma",
            "email": "invalid-email-address",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    # 5. Invalid Phone Validation
    def test_invalid_phone(self):
        payload = {
            "full_name": "Priya Sharma",
            "email": "priya@example.com",
            "phone_number": "12345",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.json())

    # 6. Missing or Invalid Name
    def test_missing_or_too_short_name(self):
        payload = {
            "full_name": "A",  # Less than 2 characters
            "email": "priya@example.com",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("full_name", response.json())

    # 7. Repeated Same Idempotency-Key
    def test_repeated_same_idempotency_key_returns_200(self):
        payload = {
            "full_name": "Priya Sharma",
            "email": "priya@example.com",
            "phone_number": "+919876543210",
        }
        idem_key = "unique-key-12345"

        # First request: 201 Created
        resp1 = self.client.post(self.url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY=idem_key)
        self.assertEqual(resp1.status_code, 201)
        reg_id1 = resp1.json()["registration_id"]

        # Second request with SAME Idempotency-Key: 200 OK
        resp2 = self.client.post(self.url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY=idem_key)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["registration_id"], reg_id1)
        self.assertIn("already registered", resp2.json()["message"])

        # DB must still have only 1 registration
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 4)
        self.assertEqual(OutboxEvent.objects.count(), 1)

    def test_same_idempotency_key_with_different_payload_returns_409_conflict(self):
        # Initial request
        payload1 = {
            "full_name": "Priya Sharma",
            "email": "priya@example.com",
            "phone_number": "+919876543210",
        }
        shared_key = "idemp-shared-key-1"
        resp1 = self.client.post(self.url, data=payload1, format="json", HTTP_IDEMPOTENCY_KEY=shared_key)
        self.assertEqual(resp1.status_code, 201)

        # Re-using the same Idempotency-Key with DIFFERENT details (e.g. different name / email)
        payload2 = {
            "full_name": "Another User",
            "email": "another@example.com",
            "phone_number": "+919876543211",
        }
        resp2 = self.client.post(self.url, data=payload2, format="json", HTTP_IDEMPOTENCY_KEY=shared_key)
        self.assertEqual(resp2.status_code, 409)
        self.assertEqual(resp2.json()["code"], "idempotency_conflict")
        self.assertIn("already been used", resp2.json()["error"])

    # 8. Duplicate Request with Different Idempotency-Key but Same Email
    def test_duplicate_email_with_different_idempotency_key_returns_200(self):
        payload = {
            "full_name": "Priya Sharma",
            "email": "priya@example.com",
            "phone_number": "+919876543210",
        }

        # First request: 201 Created
        resp1 = self.client.post(self.url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY="key-alpha")
        self.assertEqual(resp1.status_code, 201)
        reg_id1 = resp1.json()["registration_id"]

        # Second request with DIFFERENT Idempotency-Key but SAME Email: 200 OK
        resp2 = self.client.post(self.url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY="key-beta")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["registration_id"], reg_id1)

        # Database rows must NOT duplicate
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 4)
        self.assertEqual(OutboxEvent.objects.count(), 1)

    # 9. Exactly 4 Notification Rows Created
    def test_exactly_four_notification_rows_created(self):
        payload = {
            "full_name": "Aditi Roy",
            "email": "aditi@example.com",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 201)
        reg_id = response.json()["registration_id"]

        notifications = Notification.objects.filter(registration_id=reg_id)
        self.assertEqual(notifications.count(), 4)

        # Verify types and channels
        types_and_channels = list(notifications.values_list("notification_type", "channel", "status"))
        expected = [
            ("CONFIRMATION", "WHATSAPP", "PENDING"),
            ("CONFIRMATION", "EMAIL", "PENDING"),
            ("REMINDER", "WHATSAPP", "PENDING"),
            ("REMINDER", "EMAIL", "PENDING"),
        ]
        self.assertCountEqual(types_and_channels, expected)

    # 10. Correct Confirmation Scheduled_At (now)
    def test_correct_confirmation_scheduled_at(self):
        now_before = timezone.now()
        payload = {
            "full_name": "Aditi Roy",
            "email": "aditi@example.com",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 201)
        now_after = timezone.now()

        conf_notifs = Notification.objects.filter(
            registration_id=response.json()["registration_id"],
            notification_type=NotificationType.CONFIRMATION,
        )
        for notif in conf_notifs:
            self.assertGreaterEqual(notif.scheduled_at, now_before - timedelta(seconds=2))
            self.assertLessEqual(notif.scheduled_at, now_after + timedelta(seconds=2))

    # 11. Correct Reminder Scheduled_At (2026-09-18 15:15:00+05:30)
    def test_correct_reminder_scheduled_at(self):
        payload = {
            "full_name": "Aditi Roy",
            "email": "aditi@example.com",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 201)

        expected_reminder_at = datetime(2026, 9, 18, 15, 15, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        reminder_notifs = Notification.objects.filter(
            registration_id=response.json()["registration_id"],
            notification_type=NotificationType.REMINDER,
        )
        for notif in reminder_notifs:
            self.assertEqual(notif.scheduled_at, expected_reminder_at)

    # 12. Exactly 1 registration.created OutboxEvent with Status PENDING
    def test_exactly_one_outbox_event_created(self):
        payload = {
            "full_name": "Kavita Nair",
            "email": "kavita@example.com",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 201)
        reg_id = response.json()["registration_id"]

        events = OutboxEvent.objects.filter(aggregate_id=reg_id)
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "registration.created")
        self.assertEqual(event.aggregate_type, "Registration")
        self.assertEqual(event.status, OutboxStatus.PENDING)
        self.assertEqual(event.payload["data"]["registration"]["email"], "kavita@example.com")
        self.assertEqual(event.payload["data"]["workshop"]["title"], "Public Speaking Workshop")
        # Verify exact +05:30 Asia/Kolkata ISO 8601 timestamps
        self.assertEqual(event.payload["data"]["workshop"]["scheduled_at_iso"], "2026-09-18T15:30:00+05:30")
        self.assertEqual(event.payload["data"]["workshop"]["reminder_at_iso"], "2026-09-18T15:15:00+05:30")

        # Verify all 4 notification IDs are present and resolve to actual Notification UUIDs
        notifs_payload = event.payload["data"]["notifications"]
        self.assertIn("confirmation_email_id", notifs_payload)
        self.assertIn("confirmation_whatsapp_id", notifs_payload)
        self.assertIn("reminder_email_id", notifs_payload)
        self.assertIn("reminder_whatsapp_id", notifs_payload)

        conf_email = Notification.objects.get(registration_id=reg_id, notification_type=NotificationType.CONFIRMATION, channel=NotificationChannel.EMAIL)
        conf_wa = Notification.objects.get(registration_id=reg_id, notification_type=NotificationType.CONFIRMATION, channel=NotificationChannel.WHATSAPP)
        rem_email = Notification.objects.get(registration_id=reg_id, notification_type=NotificationType.REMINDER, channel=NotificationChannel.EMAIL)
        rem_wa = Notification.objects.get(registration_id=reg_id, notification_type=NotificationType.REMINDER, channel=NotificationChannel.WHATSAPP)

        self.assertEqual(notifs_payload["confirmation_email_id"], str(conf_email.id))
        self.assertEqual(notifs_payload["confirmation_whatsapp_id"], str(conf_wa.id))
        self.assertEqual(notifs_payload["reminder_email_id"], str(rem_email.id))
        self.assertEqual(notifs_payload["reminder_whatsapp_id"], str(rem_wa.id))

    # 13. Transaction Rollback Behavior
    def test_transaction_rollback_behavior(self):
        # Simulate an unhandled database error during notification creation inside atomic block
        with patch("apps.registrations.services.Notification.objects.bulk_create", side_effect=RuntimeError("Database write error")):
            with self.assertRaises(RuntimeError):
                register_attendee(
                    workshop=self.workshop,
                    full_name="Failed User",
                    email="failed@example.com",
                    phone_number="+919876543210",
                    idempotency_key="fail-key-001",
                )

        # Verify nothing was committed: all-or-nothing atomicity
        self.assertFalse(Registration.objects.filter(email="failed@example.com").exists())
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(OutboxEvent.objects.count(), 0)

    # 14. Concurrent Duplicate Registration Safety
    def test_concurrent_duplicate_registration_safety(self):
        # We simulate the concurrent scenario where Registration.objects.filter(...) returns None,
        # but create() raises IntegrityError due to a concurrent write.
        reg1, created1 = register_attendee(
            workshop=self.workshop,
            full_name="Rohan Mehta",
            email="rohan@example.com",
            phone_number="+919876543210",
            idempotency_key="concur-key-1",
        )
        self.assertTrue(created1)

        # Simulate second request running register_attendee with same email
        reg2, created2 = register_attendee(
            workshop=self.workshop,
            full_name="Rohan Mehta",
            email="rohan@example.com",
            phone_number="+919876543210",
            idempotency_key="concur-key-2",
        )
        self.assertFalse(created2)
        self.assertEqual(reg1.id, reg2.id)

    # 15. Inactive Workshop Rejection
    def test_inactive_workshop_returns_400(self):
        self.workshop.is_active = False
        self.workshop.save()

        payload = {
            "full_name": "Priya Sharma",
            "email": "priya@example.com",
            "phone_number": "+919876543210",
        }
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    # 16. Malformed Idempotency-Key Rejection
    def test_malformed_idempotency_key_returns_400(self):
        payload = {
            "full_name": "Priya Sharma",
            "email": "priya@example.com",
            "phone_number": "+919876543210",
        }
        invalid_key = "x" * 65  # Exceeds 64 characters
        response = self.client.post(self.url, data=payload, format="json", HTTP_IDEMPOTENCY_KEY=invalid_key)
        self.assertEqual(response.status_code, 400)
        self.assertIn("idempotency_key", response.json())


class IdempotencyEdgeCaseTests(TestCase):
    """
    Direct unit and integration tests for the real-world idempotency edge case:
    Ensuring IdempotencyRecord cleanly decouples API idempotency key binding
    from business duplicate detection (workshop, normalized_email).
    """

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("registration-create")
        self.scheduled_time = datetime(2026, 9, 18, 15, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.workshop = Workshop.objects.create(
            id="public-speaking-workshop",
            title="Public Speaking Workshop",
            scheduled_at=self.scheduled_time,
            timezone="Asia/Kolkata",
            reminder_lead_minutes=15,
            is_active=True,
        )

        # Base existing attendee
        self.existing_payload = {
            "full_name": "Laxman Chandra Rana",
            "email": "lcrana002@gmail.com",
            "phone_number": "+918167749719",
        }
        self.initial_resp = self.client.post(
            self.url,
            data=self.existing_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="initial-key-001",
        )
        self.assertEqual(self.initial_resp.status_code, 201)
        self.existing_registration_id = self.initial_resp.json()["registration_id"]

    # 1. New key + existing email -> 200 existing registration
    def test_1_new_key_plus_existing_email_returns_200_existing_registration(self):
        new_key = "n8n-email-e2e-001"
        resp = self.client.post(
            self.url,
            data=self.existing_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["registration_id"], self.existing_registration_id)
        self.assertIn("already registered", resp.json()["message"])

        # Verify new idempotency record was persisted and mapped to existing registration
        record = IdempotencyRecord.objects.filter(key=new_key).first()
        self.assertIsNotNone(record)
        self.assertEqual(str(record.registration_id), self.existing_registration_id)

        # Verify no duplicate registration or extra notification writes
        self.assertEqual(Registration.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 4)
        self.assertEqual(OutboxEvent.objects.count(), 1)

    # 2. Reuse that same key with same payload -> 200 same registration
    def test_2_reuse_that_same_key_with_same_payload_returns_200_same_registration(self):
        new_key = "n8n-email-e2e-001"
        # First use with existing email (case D)
        self.client.post(
            self.url,
            data=self.existing_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )

        # Reuse same key with exact same payload
        resp_reused = self.client.post(
            self.url,
            data=self.existing_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )
        self.assertEqual(resp_reused.status_code, 200)
        self.assertEqual(resp_reused.json()["registration_id"], self.existing_registration_id)
        self.assertEqual(Registration.objects.count(), 1)

    # 3. Reuse that same key with different email -> 409
    def test_3_reuse_that_same_key_with_different_email_returns_409(self):
        new_key = "n8n-email-e2e-001"
        # First use with lcrana002@gmail.com
        self.client.post(
            self.url,
            data=self.existing_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )

        # Reuse same key with DIFFERENT email (lcr.acw@gmail.com)
        different_email_payload = {
            "full_name": "Laxman Chandra Rana",
            "email": "lcr.acw@gmail.com",
            "phone_number": "+918167749719",
        }
        resp_conflict = self.client.post(
            self.url,
            data=different_email_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )
        self.assertEqual(resp_conflict.status_code, 409)
        self.assertEqual(resp_conflict.json()["code"], "idempotency_conflict")
        self.assertIn("already been used", resp_conflict.json()["error"])

        # Ensure NO new registration was created for lcr.acw@gmail.com
        self.assertFalse(Registration.objects.filter(email="lcr.acw@gmail.com").exists())
        self.assertEqual(Registration.objects.count(), 1)

    # 4. Reuse that same key with different name/phone -> 409
    def test_4_reuse_that_same_key_with_different_name_or_phone_returns_409(self):
        new_key = "n8n-email-e2e-001"
        # First use with existing attendee
        self.client.post(
            self.url,
            data=self.existing_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )

        # Reuse same key with different name
        diff_name_payload = {
            "full_name": "Completely Different Name",
            "email": "lcrana002@gmail.com",
            "phone_number": "+918167749719",
        }
        resp_diff_name = self.client.post(
            self.url,
            data=diff_name_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )
        self.assertEqual(resp_diff_name.status_code, 409)
        self.assertEqual(resp_diff_name.json()["code"], "idempotency_conflict")

        # Reuse same key with different phone number
        diff_phone_payload = {
            "full_name": "Laxman Chandra Rana",
            "email": "lcrana002@gmail.com",
            "phone_number": "+919999999999",
        }
        resp_diff_phone = self.client.post(
            self.url,
            data=diff_phone_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=new_key,
        )
        self.assertEqual(resp_diff_phone.status_code, 409)
        self.assertEqual(resp_diff_phone.json()["code"], "idempotency_conflict")

    # 5. New key + same existing email -> 200 existing registration
    def test_5_new_key_plus_same_existing_email_returns_200_existing_registration(self):
        another_new_key = "n8n-email-e2e-002"
        resp = self.client.post(
            self.url,
            data=self.existing_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=another_new_key,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["registration_id"], self.existing_registration_id)

        # Both keys must now be recorded in IdempotencyRecord
        records = IdempotencyRecord.objects.filter(
            key__in=["initial-key-001", "n8n-email-e2e-002"]
        )
        self.assertEqual(records.count(), 2)
        for r in records:
            self.assertEqual(str(r.registration_id), self.existing_registration_id)

    # 6. New key + new email -> 201 new registration
    def test_6_new_key_plus_new_email_returns_201_new_registration(self):
        brand_new_key = "n8n-email-e2e-003"
        new_attendee_payload = {
            "full_name": "Sunil Kumar",
            "email": "sunil.kumar@example.com",
            "phone_number": "+919876543299",
        }
        resp = self.client.post(
            self.url,
            data=new_attendee_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=brand_new_key,
        )
        self.assertEqual(resp.status_code, 201)
        new_reg_id = resp.json()["registration_id"]
        self.assertNotEqual(new_reg_id, self.existing_registration_id)

        # DB checks
        self.assertEqual(Registration.objects.count(), 2)
        self.assertTrue(IdempotencyRecord.objects.filter(key=brand_new_key).exists())
        self.assertEqual(Notification.objects.filter(registration_id=new_reg_id).count(), 4)
        self.assertEqual(OutboxEvent.objects.filter(aggregate_id=new_reg_id).count(), 1)

    # 7. Concurrent requests with same key remain safe
    def test_7_concurrent_requests_with_same_key_remain_safe(self):
        concur_key = "concurrent-key-999"
        payload = {
            "full_name": "Concurrent Attendee",
            "email": "concurrent@example.com",
            "phone_number": "+919876543210",
        }

        # First registration succeeds
        reg1, created1 = register_attendee(
            workshop=self.workshop,
            full_name=payload["full_name"],
            email=payload["email"],
            phone_number=payload["phone_number"],
            idempotency_key=concur_key,
        )
        self.assertTrue(created1)

        # Second concurrent invocation with same key and identical details
        reg2, created2 = register_attendee(
            workshop=self.workshop,
            full_name=payload["full_name"],
            email=payload["email"],
            phone_number=payload["phone_number"],
            idempotency_key=concur_key,
        )
        self.assertFalse(created2)
        self.assertEqual(reg1.id, reg2.id)

        # Concurrent invocation with same key but DIFFERENT details raises conflict
        with self.assertRaises(IdempotencyConflictError):
            register_attendee(
                workshop=self.workshop,
                full_name="Different Attendee",
                email="different@example.com",
                phone_number="+919876543210",
                idempotency_key=concur_key,
            )

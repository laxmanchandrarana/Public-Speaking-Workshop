from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.test import TestCase
from django.utils import timezone
from apps.workshops.models import Workshop
from apps.registrations.models import Registration
from .models import Notification, NotificationType, NotificationChannel, NotificationStatus


class NotificationModelTests(TestCase):
    def setUp(self):
        self.scheduled_time = datetime(2026, 9, 18, 15, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.workshop = Workshop.objects.create(
            id="public-speaking-workshop",
            title="Public Speaking Workshop",
            scheduled_at=self.scheduled_time,
            timezone="Asia/Kolkata",
        )
        self.registration = Registration.objects.create(
            workshop=self.workshop,
            full_name="Arjun Verma",
            email="arjun@example.com",
            phone_number="+919876543210",
            idempotency_key="key-notif-001",
        )

    def test_confirmation_and_reminder_notification_creation(self):
        conf_whatsapp = Notification.objects.create(
            registration=self.registration,
            notification_type=NotificationType.CONFIRMATION,
            channel=NotificationChannel.WHATSAPP,
            status=NotificationStatus.PENDING,
            scheduled_at=timezone.now(),
        )
        rem_whatsapp = Notification.objects.create(
            registration=self.registration,
            notification_type=NotificationType.REMINDER,
            channel=NotificationChannel.WHATSAPP,
            status=NotificationStatus.PENDING,
            scheduled_at=self.workshop.reminder_at,
        )

        self.assertEqual(conf_whatsapp.status, NotificationStatus.PENDING)
        self.assertEqual(rem_whatsapp.scheduled_at, self.workshop.reminder_at)
        self.assertEqual(self.registration.notifications.count(), 2)

    def test_notification_status_lifecycle(self):
        notif = Notification.objects.create(
            registration=self.registration,
            notification_type=NotificationType.CONFIRMATION,
            channel=NotificationChannel.WHATSAPP,
            status=NotificationStatus.PENDING,
            scheduled_at=timezone.now(),
        )

        # Worker leases the notification
        now = timezone.now()
        notif.status = NotificationStatus.PROCESSING
        notif.processing_started_at = now
        notif.attempts += 1
        notif.save()
        notif.refresh_from_db()
        self.assertEqual(notif.status, NotificationStatus.PROCESSING)
        self.assertEqual(notif.attempts, 1)

        # Worker completes dispatch
        notif.status = NotificationStatus.SENT
        notif.sent_at = timezone.now()
        notif.external_id = "evo_msg_98765"
        notif.save()
        notif.refresh_from_db()
        self.assertEqual(notif.status, NotificationStatus.SENT)
        self.assertEqual(notif.external_id, "evo_msg_98765")
        self.assertIsNotNone(notif.sent_at)

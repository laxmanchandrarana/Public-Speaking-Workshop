from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from .models import Workshop


class WorkshopModelTests(TestCase):
    def setUp(self):
        self.scheduled_time = datetime(2026, 9, 18, 15, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.workshop = Workshop.objects.create(
            id="public-speaking-workshop",
            title="Public Speaking Workshop",
            scheduled_at=self.scheduled_time,
            timezone="Asia/Kolkata",
            reminder_lead_minutes=15,
            meeting_link=None,
            is_active=True,
        )

    def test_workshop_creation_and_string_representation(self):
        self.assertEqual(self.workshop.title, "Public Speaking Workshop")
        self.assertEqual(self.workshop.timezone, "Asia/Kolkata")
        self.assertEqual(self.workshop.reminder_lead_minutes, 15)
        self.assertIn("Public Speaking Workshop", str(self.workshop))

    def test_reminder_at_calculation(self):
        expected_reminder = self.scheduled_time - timedelta(minutes=15)
        self.assertEqual(self.workshop.reminder_at, expected_reminder)
        self.assertEqual(self.workshop.reminder_at.hour, 15)
        self.assertEqual(self.workshop.reminder_at.minute, 15)

    def test_workshop_api_detail_view(self):
        client = APIClient()
        response = client.get(reverse("workshop-detail"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "public-speaking-workshop")
        self.assertEqual(data["title"], "Public Speaking Workshop")
        self.assertEqual(data["timezone"], "Asia/Kolkata")
        self.assertEqual(data["reminder_lead_minutes"], 15)
        self.assertIn("2026-09-18T15:30:00", data["scheduled_at"])
        self.assertIn("2026-09-18T15:15:00", data["reminder_at"])

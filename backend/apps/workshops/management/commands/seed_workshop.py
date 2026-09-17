from datetime import datetime
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand
from apps.workshops.models import Workshop


class Command(BaseCommand):
    help = "Seed the database with the initial Public Speaking Workshop record."

    def handle(self, *args, **options):
        scheduled_time = datetime(2026, 9, 18, 15, 30, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        
        workshop, created = Workshop.objects.update_or_create(
            id="public-speaking-workshop",
            defaults={
                "title": "Public Speaking Workshop",
                "scheduled_at": scheduled_time,
                "timezone": "Asia/Kolkata",
                "reminder_lead_minutes": 15,
                "meeting_link": None,
                "is_active": True,
            },
        )
        
        status = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully {status.lower()} workshop: '{workshop.title}' scheduled for {workshop.scheduled_at} ({workshop.timezone}). "
                f"Reminder set for {workshop.reminder_at}."
            )
        )

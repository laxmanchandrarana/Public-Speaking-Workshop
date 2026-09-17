from datetime import timedelta
from django.db import models


class Workshop(models.Model):
    id = models.SlugField(
        primary_key=True,
        max_length=50,
        default="public-speaking-workshop",
        help_text="Unique identifier for the workshop",
    )
    title = models.CharField(
        max_length=200,
        default="Public Speaking Workshop",
        help_text="Exact title of the workshop",
    )
    scheduled_at = models.DateTimeField(
        db_index=True,
        help_text="Scheduled date and time in Asia/Kolkata timezone (18 Sept 2026, 3:30 PM IST)",
    )
    timezone = models.CharField(
        max_length=50,
        default="Asia/Kolkata",
        help_text="IANA Timezone name",
    )
    reminder_lead_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Minutes before workshop to trigger reminder (e.g. 15 minutes)",
    )
    meeting_link = models.URLField(
        blank=True,
        null=True,
        help_text="Optional meeting link for the session",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether registrations are actively accepted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Workshop"
        verbose_name_plural = "Workshops"
        ordering = ["-scheduled_at"]

    def __str__(self):
        return f"{self.title} ({self.scheduled_at.strftime('%Y-%m-%d %H:%M %Z')})"

    @property
    def reminder_at(self):
        """Returns the exact scheduled datetime for the pre-workshop reminder."""
        return self.scheduled_at - timedelta(minutes=self.reminder_lead_minutes)

from zoneinfo import ZoneInfo
from rest_framework import serializers
from .models import Workshop


class WorkshopSerializer(serializers.ModelSerializer):
    scheduled_at = serializers.SerializerMethodField()
    reminder_at = serializers.SerializerMethodField()

    class Meta:
        model = Workshop
        fields = [
            "id",
            "title",
            "scheduled_at",
            "timezone",
            "reminder_lead_minutes",
            "reminder_at",
            "meeting_link",
            "is_active",
        ]

    def get_scheduled_at(self, obj) -> str:
        tz = ZoneInfo(obj.timezone)
        return obj.scheduled_at.astimezone(tz).isoformat()

    def get_reminder_at(self, obj) -> str:
        tz = ZoneInfo(obj.timezone)
        return obj.reminder_at.astimezone(tz).isoformat()

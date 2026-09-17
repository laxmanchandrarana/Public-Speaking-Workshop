from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "registration",
        "notification_type",
        "channel",
        "status",
        "scheduled_at",
        "sent_at",
        "attempts",
        "created_at",
    )
    list_filter = ("notification_type", "channel", "status", "scheduled_at")
    search_fields = (
        "id",
        "registration__full_name",
        "registration__normalized_email",
        "registration__phone_number",
        "external_id",
        "last_error",
    )
    readonly_fields = ("id", "created_at", "updated_at")

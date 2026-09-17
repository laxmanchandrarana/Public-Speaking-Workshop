from django.contrib import admin
from .models import OutboxEvent


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "status",
        "retry_count",
        "next_retry_at",
        "processing_started_at",
        "created_at",
        "delivered_at",
    )
    list_filter = ("event_type", "status", "aggregate_type")
    search_fields = ("id", "event_type", "aggregate_id", "last_error")
    readonly_fields = ("id", "created_at", "delivered_at")

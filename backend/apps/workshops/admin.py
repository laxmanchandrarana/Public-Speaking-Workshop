from django.contrib import admin
from .models import Workshop


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = ("title", "scheduled_at", "timezone", "reminder_lead_minutes", "is_active", "created_at")
    list_filter = ("is_active", "timezone")
    search_fields = ("title", "id")
    readonly_fields = ("created_at", "updated_at", "reminder_at")

    def reminder_at(self, obj):
        return obj.reminder_at
    reminder_at.short_description = "Reminder At"

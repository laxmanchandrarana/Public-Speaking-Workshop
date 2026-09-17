from django.contrib import admin
from .models import Registration, IdempotencyRecord


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "normalized_email", "phone_number", "workshop", "created_at")
    list_filter = ("workshop", "created_at")
    search_fields = ("full_name", "email", "normalized_email", "phone_number", "idempotency_key")
    readonly_fields = ("id", "normalized_email", "created_at", "updated_at")


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ("key", "registration", "request_fingerprint", "created_at")
    search_fields = ("key", "request_fingerprint", "registration__full_name", "registration__normalized_email")
    readonly_fields = ("id", "created_at")

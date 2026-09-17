import uuid
from django.db import models


class Registration(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique registration identifier",
    )
    workshop = models.ForeignKey(
        "workshops.Workshop",
        on_delete=models.PROTECT,
        related_name="registrations",
        help_text="The workshop this registration is for",
    )
    full_name = models.CharField(
        max_length=150,
        help_text="Full name of the attendee",
    )
    email = models.EmailField(
        max_length=254,
        help_text="Raw email address as provided by attendee",
    )
    normalized_email = models.EmailField(
        max_length=254,
        db_index=True,
        help_text="Trimmed and lowercased email for deduplication",
    )
    phone_number = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Normalized E.164 formatted phone number (e.g. +919876543210)",
    )
    idempotency_key = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text="Original idempotency key from initial registration submission",
    )
    request_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text="SHA-256 fingerprint of request parameters for idempotency conflict detection",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Registration"
        verbose_name_plural = "Registrations"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workshop", "normalized_email"],
                name="unique_workshop_normalized_email",
            )
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.normalized_email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.normalized_email}) - {self.workshop.title}"


class IdempotencyRecord(models.Model):
    """
    Dedicated idempotency registry separating API request idempotency from
    workshop business duplicate detection.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique idempotency record identifier",
    )
    key = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unique idempotency key identifying an API operation",
    )
    request_fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 fingerprint of request parameters for conflict detection",
    )
    registration = models.ForeignKey(
        "registrations.Registration",
        on_delete=models.CASCADE,
        related_name="idempotency_records",
        help_text="The registration associated with this idempotency key",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Idempotency Record"
        verbose_name_plural = "Idempotency Records"
        ordering = ["-created_at"]

    def __str__(self):
        return f"IdempotencyRecord({self.key} -> {self.registration_id})"

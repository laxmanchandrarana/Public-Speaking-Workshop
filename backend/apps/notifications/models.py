import uuid
from django.db import models


class NotificationType(models.TextChoices):
    CONFIRMATION = "CONFIRMATION", "Confirmation"
    REMINDER = "REMINDER", "Reminder"


class NotificationChannel(models.TextChoices):
    WHATSAPP = "WHATSAPP", "WhatsApp"
    EMAIL = "EMAIL", "Email"


class NotificationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class Notification(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique notification record identifier",
    )
    registration = models.ForeignKey(
        "registrations.Registration",
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="Associated attendee registration",
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        db_index=True,
        help_text="Type of message (confirmation or reminder)",
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        db_index=True,
        help_text="Delivery communication channel",
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
        db_index=True,
        help_text="Current state in the notification lifecycle",
    )
    scheduled_at = models.DateTimeField(
        db_index=True,
        help_text="Timestamp when this notification is eligible to be dispatched",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when message was successfully delivered or acknowledged",
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of delivery attempts performed",
    )
    last_error = models.TextField(
        blank=True,
        null=True,
        help_text="Most recent error message if delivery or processing failed",
    )
    external_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="External identifier from automation platform or provider (e.g. Evolution API message ID)",
    )
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when a worker claimed this notification for crash recovery lease timeout",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["scheduled_at", "created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"], name="idx_notif_status_sched"),
            models.Index(fields=["status", "processing_started_at"], name="idx_notif_status_proc"),
        ]

    def __str__(self):
        return f"{self.notification_type} ({self.channel}) - {self.status} for {self.registration.normalized_email}"

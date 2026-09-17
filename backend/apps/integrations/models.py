import uuid
from django.db import models
from django.utils import timezone


class OutboxStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"


class OutboxEvent(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique event identifier for transactional outbox pattern",
    )
    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Event name (e.g. registration.created, workshop.reminder)",
    )
    aggregate_type = models.CharField(
        max_length=50,
        help_text="Aggregate model name (e.g. Registration, Notification)",
    )
    aggregate_id = models.UUIDField(
        db_index=True,
        help_text="ID of the aggregate this event pertains to",
    )
    payload = models.JSONField(
        default=dict,
        help_text="JSON payload to dispatch to the automation webhook",
    )
    status = models.CharField(
        max_length=20,
        choices=OutboxStatus.choices,
        default=OutboxStatus.PENDING,
        db_index=True,
        help_text="Current delivery state",
    )
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when worker leased/claimed this event for processing",
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts executed",
    )
    max_retries = models.PositiveIntegerField(
        default=5,
        help_text="Maximum allowed dispatch attempts before permanent failure",
    )
    next_retry_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Next scheduled attempt timestamp with exponential backoff",
    )
    last_error = models.TextField(
        blank=True,
        null=True,
        help_text="Error message from the last failed dispatch attempt",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when automation webhook acknowledged receipt (HTTP 2xx)",
    )

    class Meta:
        verbose_name = "Outbox Event"
        verbose_name_plural = "Outbox Events"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "next_retry_at"], name="idx_outbox_status_retry"),
            models.Index(fields=["status", "processing_started_at"], name="idx_outbox_status_proc"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["aggregate_id", "event_type"],
                name="unique_outbox_aggregate_event_type",
            )
        ]

    def __str__(self):
        return f"{self.event_type} [{self.status}] (id={self.id})"

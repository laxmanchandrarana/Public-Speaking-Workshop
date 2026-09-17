import hmac
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse
from django.conf import settings
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
import requests

from .models import OutboxEvent, OutboxStatus

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when webhook integration settings are invalid or missing."""
    pass


@dataclass
class DispatchResult:
    is_success: bool
    status_code: int | None
    response_body: str | None
    error_message: str | None
    is_retryable: bool = False


def is_retryable_failure(status_code: int | None) -> bool:
    """
    HTTP retry policy:
    - 408 (Request Timeout) -> retryable
    - 429 (Too Many Requests / Rate Limit) -> retryable
    - 5xx (500, 502, 503, 504, etc.) -> retryable
    - None (connection errors, timeouts, network failures) -> retryable
    - 4xx (400, 404, 410, 413, 422, etc.) -> permanent failure (do NOT retry)
      Automation webhook notes:
      200 = webhook captured successfully
      404 = workflow disabled or not found
      410 = workflow deleted
      413 = payload too large
    """
    if status_code is None:
        return True
    if status_code in (408, 429):
        return True
    if 500 <= status_code <= 599:
        return True
    return False


def compute_backoff_delay(retry_count: int, base_seconds: int = 30, max_seconds: int = 3600) -> timedelta:
    """
    Computes exponential backoff delay: base * 2^(retry_count - 1), capped at max_seconds.
    """
    delay = min(max_seconds, base_seconds * (2 ** max(0, retry_count - 1)))
    return timedelta(seconds=delay)


def generate_webhook_signature(secret: str, payload_bytes: bytes) -> str:
    """
    Generates HMAC-SHA256 hex digest signature for the payload.
    """
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def validate_webhook_url(url: str | None) -> str:
    """
    Validates that the webhook URL is configured and uses http/https.
    """
    if not url or not str(url).strip():
        raise ConfigurationError("AUTOMATION_WEBHOOK_URL is not configured.")
    
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConfigurationError(f"Invalid AUTOMATION_WEBHOOK_URL: '{url}'. Must be a valid HTTP or HTTPS URL.")
    
    return url.strip()


def claim_outbox_events(
    batch_size: int = 50,
    lease_seconds: int | None = None,
) -> list[OutboxEvent]:
    """
    Atomically claims eligible outbox events for processing using PostgreSQL row-level locks
    with `skip_locked=True`.
    
    Eligible events include:
    1. status='PENDING' and next_retry_at <= now
    2. status='FAILED' and retry_count < max_retries and next_retry_at <= now
    3. status='PROCESSING' and processing_started_at <= now - lease_seconds (crash recovery)
    
    Transitions claimed records to status='PROCESSING' and updates processing_started_at.
    """
    if lease_seconds is None:
        lease_seconds = getattr(settings, "OUTBOX_LEASE_TIMEOUT_SECONDS", 300)

    now = timezone.now()
    lease_cutoff = now - timedelta(seconds=lease_seconds)

    with transaction.atomic():
        eligible_qs = (
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(
                (
                    Q(status=OutboxStatus.PENDING, next_retry_at__lte=now)
                    | Q(status=OutboxStatus.FAILED, next_retry_at__lte=now)
                    | Q(status=OutboxStatus.PROCESSING, processing_started_at__lte=lease_cutoff)
                )
                & Q(retry_count__lt=F("max_retries"))
            )
            .order_by("created_at")[:batch_size]
        )

        claimed_events = list(eligible_qs)
        if not claimed_events:
            return []

        claimed_ids = [event.id for event in claimed_events]
        OutboxEvent.objects.filter(id__in=claimed_ids).update(
            status=OutboxStatus.PROCESSING,
            processing_started_at=now,
        )

        # Update local objects
        for event in claimed_events:
            event.status = OutboxStatus.PROCESSING
            event.processing_started_at = now

    return claimed_events


def dispatch_single_event(
    event: OutboxEvent,
    webhook_url: str | None = None,
    webhook_secret: str | None = None,
    timeout: int = 10,
) -> DispatchResult:
    """
    Dispatches a single OutboxEvent via HTTP POST to the webhook endpoint.
    Carries stable event_id and X-Signature header where configured.
    """
    if webhook_url is None:
        webhook_url = getattr(settings, "AUTOMATION_WEBHOOK_URL", None)
    if webhook_secret is None:
        webhook_secret = getattr(settings, "AUTOMATION_WEBHOOK_SECRET", None)

    # Validate URL
    target_url = validate_webhook_url(webhook_url)

    # Encode payload
    payload = event.payload or {}
    payload_bytes = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")

    # Stable event_id across retries
    stable_event_id = str(payload.get("event_id") or event.id)

    headers = {
        "Content-Type": "application/json",
        "X-Event-Type": event.event_type,
        "X-Event-ID": stable_event_id,
        "X-Timestamp": timezone.now().isoformat(),
    }

    if webhook_secret and str(webhook_secret).strip():
        headers["X-Signature"] = generate_webhook_signature(str(webhook_secret).strip(), payload_bytes)

    try:
        response = requests.post(
            target_url,
            data=payload_bytes,
            headers=headers,
            timeout=timeout,
        )

        is_2xx = 200 <= response.status_code < 300
        if is_2xx:
            return DispatchResult(
                is_success=True,
                status_code=response.status_code,
                response_body=response.text[:500],
                error_message=None,
                is_retryable=False,
            )
        else:
            retryable = is_retryable_failure(response.status_code)
            prefix = "Retryable" if retryable else "Permanent"
            error_msg = f"{prefix} HTTP {response.status_code}: {response.text[:300]}"
            return DispatchResult(
                is_success=False,
                status_code=response.status_code,
                response_body=response.text[:500],
                error_message=error_msg,
                is_retryable=retryable,
            )

    except requests.exceptions.Timeout as exc:
        return DispatchResult(
            is_success=False,
            status_code=None,
            response_body=None,
            error_message=f"Request timeout after {timeout}s: {str(exc)}",
            is_retryable=True,
        )
    except requests.exceptions.RequestException as exc:
        return DispatchResult(
            is_success=False,
            status_code=None,
            response_body=None,
            error_message=f"Connection failure: {str(exc)}",
            is_retryable=True,
        )
    except Exception as exc:
        return DispatchResult(
            is_success=False,
            status_code=None,
            response_body=None,
            error_message=f"Unexpected error during dispatch: {str(exc)}",
            is_retryable=True,
        )


def process_claimed_event(
    event: OutboxEvent,
    webhook_url: str | None = None,
    webhook_secret: str | None = None,
    timeout: int = 10,
    base_backoff_seconds: int = 30,
) -> DispatchResult:
    """
    Dispatches a claimed event and updates its database state:
    - 2xx: DELIVERED, delivered_at=now, processing_started_at=None
    - Permanent 4xx failure (400, 404, 410, 413, 422): status=FAILED, retry_count=max_retries (no retries scheduled)
    - Retryable failure (408, 429, 5xx, timeout, network): retry_count incremented, backoff applied, next_retry_at scheduled
    """
    result = dispatch_single_event(
        event=event,
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
        timeout=timeout,
    )

    now = timezone.now()
    with transaction.atomic():
        # Re-fetch event inside atomic block to prevent stale overwrites
        event.refresh_from_db()

        if result.is_success:
            event.status = OutboxStatus.DELIVERED
            event.delivered_at = now
            event.processing_started_at = None
            event.last_error = None
            event.save(update_fields=["status", "delivered_at", "processing_started_at", "last_error"])
        elif not result.is_retryable:
            # Permanent failure: Do not repeatedly retry permanent automation configuration/payload errors
            event.status = OutboxStatus.FAILED
            event.retry_count = event.max_retries  # Exhaust retries so claim_outbox_events never claims it again
            event.processing_started_at = None
            event.last_error = f"[Permanent Failure] {result.error_message}"
            event.save(update_fields=["status", "retry_count", "processing_started_at", "last_error"])
        else:
            # Retryable failure: increment retry count, compute backoff, schedule next_retry_at
            event.retry_count += 1
            event.last_error = result.error_message
            event.processing_started_at = None
            backoff = compute_backoff_delay(event.retry_count, base_seconds=base_backoff_seconds)
            event.next_retry_at = now + backoff
            event.status = OutboxStatus.FAILED
            event.save(update_fields=["status", "retry_count", "last_error", "processing_started_at", "next_retry_at"])

    return result

# Phase 4A: Pabbly Connect Webhook Integration Guide [DEPRECATED]

> [!WARNING]
> **HISTORICAL REFERENCE ONLY — DEPRECATED**:
> Automation has been completely migrated from Pabbly Connect to self-hosted n8n (`https://n8n.atmakriti.com`).
> This document is preserved for historical reference only.
> Active workflow configuration resides in `n8n/public-speaking-workshop-workflow.json`.

This guide details the legacy steps previously used for connecting the Django Outbox Dispatcher to Pabbly Connect for Phase 4A.

---

## 1. How to Create the Initial Pabbly Workflow

> [!IMPORTANT]
> Create the workflow manually in Pabbly Connect. Do NOT attempt JSON import.
> Do NOT configure WhatsApp (Evolution API) or Email actions in this phase.

1. Log into your **Pabbly Connect** dashboard ([https://connect.pabbly.com](https://connect.pabbly.com)).
2. Click **Create Workflow** in the top-right corner.
3. Name the workflow: `Public Speaking Workshop - Registrations`.
4. In the **Trigger** step:
   * **Choose App:** Search for and select **Webhook**.
   * **Trigger Event:** `Catch Webhook`.
5. Pabbly will display a unique **Webhook URL** looking like:
   ```text
   https://connect.pabbly.com/workflow/sendwebhookdata/IjU3NjYwNTZjMDYzZjA0MzM1MjY0NTUzNSI_3_pc
   ```
6. Leave the Pabbly tab open on **Waiting for Webhook Response...**.

---

## 2. Where to Configure the Pabbly Webhook URL in Django

1. Open the `.env` file in the project root (`/home/ubuntu/apps/public-speaking-workshop/.env`).
2. Set `AUTOMATION_WEBHOOK_URL` to the exact URL copied from Pabbly:
   ```bash
   AUTOMATION_WEBHOOK_URL=https://connect.pabbly.com/workflow/sendwebhookdata/<YOUR_ACTUAL_PABBLY_WORKFLOW_ID>
   ```
3. (Optional) Set `AUTOMATION_WEBHOOK_SECRET` if you want HMAC verification enabled:
   ```bash
   AUTOMATION_WEBHOOK_SECRET=your-shared-secret-token
   ```

---

## 3. Expected Django Webhook Payload

When Django dispatches a `registration.created` event, Pabbly will receive an HTTP `POST` request with the following JSON structure:

```json
{
  "event_id": "8f219159-8664-4e4f-b649-14a5202ee2b4",
  "event_type": "registration.created",
  "version": "1.0",
  "occurred_at": "2026-09-17T14:39:40.407985+00:00",
  "data": {
    "registration": {
      "id": "093b93e1-be82-434d-9303-fe4ebbf68d36",
      "full_name": "Priya Sharma",
      "email": "priya.sharma@example.com",
      "phone_number": "+919876543210",
      "registered_at": "2026-09-17T14:39:40.404451+00:00"
    },
    "workshop": {
      "id": "public-speaking-workshop",
      "title": "Public Speaking Workshop",
      "scheduled_at_iso": "2026-09-18T15:30:00+05:30",
      "timezone": "Asia/Kolkata",
      "reminder_at_iso": "2026-09-18T15:15:00+05:30"
    },
    "messages": {
      "whatsapp_text": "Hi Priya Sharma, your registration for Public Speaking Workshop is confirmed! Date: 18 September 2026, 3:30 PM Asia/Kolkata. We will send a reminder 15 minutes before the session starts."
    }
  }
}
```

### HTTP Headers Sent by Django
* `Content-Type: application/json`
* `X-Event-Type: registration.created`
* `X-Event-ID: <stable_event_id>` (Remains identical across retries)
* `X-Timestamp: <iso_utc_timestamp>`
* `X-Signature: sha256=<hmac_sha256>` (Sent if `AUTOMATION_WEBHOOK_SECRET` is configured)

---

## 4. Expected Response Behavior & Pabbly HTTP Status Codes

| HTTP Status | Meaning in Pabbly | Django Retry Policy |
| :--- | :--- | :--- |
| **200 OK** | Webhook successfully captured by Pabbly | **Success:** OutboxEvent marked `DELIVERED`, `delivered_at` set. |
| **404 Not Found** | Workflow is disabled or paused | **Permanent Failure:** Marked `FAILED`. No retries scheduled. |
| **410 Gone** | Workflow URL deleted or expired | **Permanent Failure:** Marked `FAILED`. No retries scheduled. |
| **413 Too Large** | Request body exceeds Pabbly limits | **Permanent Failure:** Marked `FAILED`. No retries scheduled. |
| **408 / 429** | Timeout or Rate Limiting | **Retryable:** Retried with exponential backoff. |
| **5xx Server Error**| Pabbly or Cloudflare upstream error | **Retryable:** Retried with exponential backoff. |
| **Timeout/Network** | Network connection failure or drop | **Retryable:** Retried with exponential backoff. |

---

## 5. How to Run the Outbox Dispatcher

### Dry-Run Mode (Inspect pending events without dispatching)
```bash
python backend/manage.py process_outbox --dry-run
```

### Live Dispatch Execution
```bash
python backend/manage.py process_outbox
```

### With Custom Batch Size or Timeout
```bash
python backend/manage.py process_outbox --batch-size 20 --timeout 15
```

---

## 6. How to Inspect OutboxEvent Status in Database

### Via PostgreSQL CLI (`psql`)
```sql
psql -U ubuntu -d public_speaking_workshop -P pager=off -c \
"SELECT id, event_type, status, retry_count, last_error, delivered_at, created_at FROM integrations_outboxevent ORDER BY created_at DESC LIMIT 5;"
```

### Expected State Progression
1. **Immediately upon user registration:**
   * `status = PENDING`
   * `delivered_at = NULL`
   * `retry_count = 0`
2. **While worker is dispatching:**
   * `status = PROCESSING`
   * `processing_started_at = <timestamp>`
3. **Upon HTTP 200 from Pabbly:**
   * `status = DELIVERED`
   * `delivered_at = <timestamp>`
   * `processing_started_at = NULL`
   * `last_error = NULL`

---

## 7. Troubleshooting

* **Pabbly returns HTTP 410 / 404:**
  * Verify that the workflow in Pabbly is turned **ON** (toggle in upper right).
  * Re-copy the exact Webhook URL from the Trigger step into `.env`.
* **Events remain in PENDING:**
  * Verify `AUTOMATION_WEBHOOK_URL` is non-empty.
  * Run `python backend/manage.py process_outbox --dry-run` to check if `next_retry_at` is in the future.
* **Worker crashed during dispatch:**
  * The lease timeout (`OUTBOX_LEASE_TIMEOUT_SECONDS`, default 300s) automatically recovers any event stranded in `PROCESSING`.

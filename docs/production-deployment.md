# Production Deployment Guide: Public Speaking Workshop

This guide documents the production containerized deployment for the **Public Speaking Workshop** platform.

---

## 1. Production Architecture Overview

```
                      INTERNET / CLIENTS
                              │
               ┌──────────────┴──────────────┐
               │    Cloudflare Zero Trust    │
               │            Edge             │
               └──────────────┬──────────────┘
                              │
                    Cloudflare Tunnel (Host)
                              │
         ┌────────────────────┴────────────────────┐
         │ (HTTP localhost:8088)                   │ (HTTP localhost:8000)
         ▼                                         ▼
   ┌──────────────┐                         ┌──────────────┐
   │ psw-frontend │                         │ psw-backend  │
   │ (Nginx SPA)  │                         │ (Gunicorn)   │
   │ Container:80 │                         │Container:8000│
   └──────────────┘                         └──────┬───────┘
                                                   │
                                   ┌───────────────┼───────────────┐
                                   │               │               │
                            (UNIX Socket)      (HTTPS)          (HTTPS)
                                   ▼               ▼               ▼
                              PostgreSQL          n8n         Evolution API
                            (Host DB 16)      Webhook         (WhatsApp)
```

---

## 2. Container Specifications

### Frontend Container (`psw-frontend`)
* **Base Image**: Multi-stage `node:22-alpine` ➔ `nginx:1.27-alpine`
* **Internal Port**: `80`
* **Host Port Binding**: `127.0.0.1:8088:80`
* **SPA Routing**: `try_files $uri $uri/ /index.html;`
* **Cache Policy**:
  * `/assets/*`: 1-year immutable caching (`max-age=31536000, immutable`).
  * `/index.html`: Instant update revalidation (`no-cache, no-store, must-revalidate`).
* **API Base URL**: Baked at build-time to `https://psw-api.lcrana.in`.

### Backend Container (`psw-backend`)
* **Base Image**: `python:3.12-slim`
* **Application Server**: Gunicorn WSGI (`config.wsgi:application`) with 3 workers.
* **Internal Port**: `8000`
* **Host Port Binding**: `127.0.0.1:8000:8000`
* **User**: Non-root `appuser` (UID 1001 / GID 1001 matching host `ubuntu` user).
* **Database Connection**: Mounted host UNIX socket `/var/run/postgresql:/var/run/postgresql` (peer authentication, zero network overhead, no plain text credentials).
* **Allowed Hosts**: `psw-api.lcrana.in,localhost,127.0.0.1,backend`
* **CORS Allowed Origins**: `https://psw.lcrana.in` (plus local development ports).
* **CSRF Trusted Origins**: `https://psw.lcrana.in,https://psw-api.lcrana.in`

---

## 3. Cloudflare Tunnel Ingress Mapping

The host runs Cloudflare Tunnel via `cloudflared.service`. Because this tunnel is managed remotely via the **Cloudflare Zero Trust Dashboard**, add the following two public hostnames to the existing tunnel configuration:

| Public Hostname | Service Type | URL / Target | Notes |
|---|---|---|---|
| `psw.lcrana.in` | `HTTP` | `http://localhost:8088` | Serves the React landing page |
| `psw-api.lcrana.in` | `HTTP` | `http://localhost:8000` | Serves the Django API & health check |

*Note: No other hostnames or configurations need to be changed.*

---

## 4. Production Scheduler (15-Minute Workshop Reminders)

* **Timer Unit**: `public-speaking-workshop-reminders.timer` (runs every 1 minute).
* **Service Unit**: `public-speaking-workshop-reminders.service` (Type=oneshot).
* **Script**: [`backend/scripts/run_scheduler.sh`](file:///home/ubuntu/apps/public-speaking-workshop/backend/scripts/run_scheduler.sh)
  * Seamlessly executes inside the running Docker container:
    ```bash
    docker compose exec -T backend python manage.py dispatch_reminders --process-outbox
    ```
  * Ensures exactly **one** scheduler architecture runs (no duplicate runs between host and Docker).

---

## 5. Operations & Management Commands

### Build & Deploy
```bash
# Build both frontend and backend images
docker compose build

# Start or restart containers in background
docker compose up -d

# Run database migrations
docker compose exec -T backend python manage.py migrate

# Inspect container health
docker compose ps
```

### View Logs
```bash
# Backend logs (Gunicorn / Django)
docker compose logs -f backend

# Frontend logs (Nginx access / error)
docker compose logs -f frontend

# Reminder scheduler logs (systemd journal)
journalctl -u public-speaking-workshop-reminders.service -n 50 -f
```

### Run Tests Inside Container
```bash
docker compose exec -T backend python manage.py test apps config
```

### Health Check Verification
```bash
# Backend Health
curl -s http://127.0.0.1:8000/api/v1/health/

# Frontend Health
curl -sI http://127.0.0.1:8088/
```

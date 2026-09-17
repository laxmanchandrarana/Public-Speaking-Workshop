# Public Speaking Workshop Platform

A production-grade, event landing and registration platform featuring a React (Vite + TypeScript + Tailwind CSS) frontend, Django REST Framework backend with a Transactional Outbox engine, self-hosted n8n automation for multi-channel notifications (SMTP Email and Evolution API WhatsApp), and an automated 15-minute pre-workshop reminder scheduler.

---

## 🏛️ System Architecture

```
                                  CLIENT BROWSER
                                        │
                     ┌──────────────────┴──────────────────┐
                     │        Cloudflare Zero Trust        │
                     └──────────────────┬──────────────────┘
                                        │
                             Cloudflare Tunnel (Host)
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 │ (localhost:8088)                            │ (localhost:8000)
                 ▼                                             ▼
         ┌───────────────┐                             ┌───────────────┐
         │ psw-frontend  │                             │  psw-backend  │
         │ (Nginx 1.27)  │                             │(Gunicorn 23.0)│
         │ Container: 80 │                             │Container: 8000│
         └───────────────┘                             └───────┬───────┘
                                                               │
                                               ┌───────────────┼───────────────┐
                                               │               │               │
                                      (UNIX Socket)         (HTTPS)         (HTTPS)
                                               ▼               ▼               ▼
                                          PostgreSQL          n8n        Evolution API
                                         (Host DB 16)       Webhook        (WhatsApp)
```

---

## 🌐 Production Endpoints

| Service | Production URL | Description |
|---|---|---|
| **Frontend** | [https://psw.lcrana.in](https://psw.lcrana.in) | Responsive React/Vite Landing Page & Registration |
| **Backend API** | [https://psw-api.lcrana.in](https://psw-api.lcrana.in) | Django REST Framework API & Health Checks |
| **Automation** | [https://n8n.atmakriti.com](https://n8n.atmakriti.com) | Self-Hosted n8n Workflow Automation |
| **WhatsApp API** | [https://evolution.lcrana.in](https://evolution.lcrana.in) | Evolution API WhatsApp Gateway |

---

## ✨ Key Features

- **High-Converting Landing Page**: Editorial typography, dark-first styling, glassmorphism card surfaces, live timezone-aware countdown, and smooth animations powered by Framer Motion.
- **Strict Idempotency**: Built-in client-generated `Idempotency-Key` tracking and database-level unique constraints preventing duplicate attendee registrations and race conditions.
- **Transactional Outbox Pattern**: Guaranteed at-least-once notification dispatch decoupled from external network latency. Failed webhook attempts automatically retry using exponential backoff.
- **Multi-Channel Delivery**:
  - **Email**: Responsive HTML templates dispatched via SMTP with session calendar details.
  - **WhatsApp**: Direct message delivery via Evolution API.
- **Automated 15-Minute Reminders**: Pre-scheduled workshop notifications triggered exactly 15 minutes before session start time (`2026-09-18 15:15:00 IST`).
- **Production Scheduler**: Host `systemd` timer executing every 60 seconds directly inside the running Docker backend container.
- **Zero-Password Host Database Integration**: Backend container mounts `/var/run/postgresql` to communicate directly with native PostgreSQL 16 via UNIX domain socket peer authentication.

---

## 📁 Repository Structure

```
.
├── docker-compose.yml              # Production Docker Compose orchestration
├── package.json                    # Root scripts forwarding commands to frontend
├── .env.example                    # Template for production and development environment variables
├── backend/
│   ├── Dockerfile                  # Production Python 3.12-slim / Gunicorn container
│   ├── requirements.txt            # Python dependencies (Django 5.1, DRF, psycopg, gunicorn, etc.)
│   ├── config/                     # Django core settings (base, development, production, urls)
│   ├── apps/
│   │   ├── workshops/              # Workshop scheduling & metadata models, serializers, views
│   │   ├── registrations/          # Attendee registration, E.164 normalization, and validation
│   │   ├── notifications/          # Notification lifecycle & pre-workshop reminder engine
│   │   └── integrations/           # Transactional Outbox models, dispatcher & webhook callback views
│   ├── deploy/                     # Systemd service and timer templates
│   └── scripts/
│       ├── run_scheduler.sh        # Production scheduler runner (invokes docker compose exec)
│       └── mock_n8n_server.py      # Local mock automation server for isolated testing
├── frontend/
│   ├── Dockerfile                  # Multi-stage build (Node 22 builder ➔ Nginx 1.27 runner)
│   ├── nginx.conf                  # Production SPA routing, asset caching & security headers
│   ├── package.json                # React 19, Vite 8, TypeScript, Tailwind CSS v4, Framer Motion
│   └── src/
│       ├── api.ts                  # Typed client for Django endpoints with error mapping
│       ├── types.ts                # TypeScript interfaces for Workshop, Registration, Countdown
│       ├── hooks/useCountdown.ts   # Accurate countdown calculation with interval cleanup
│       └── components/             # Modular React components (Hero, Countdown, Benefits, Form, etc.)
└── docs/                           # Architecture documentation and deployment guides
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.12+
- Node.js 20+ & npm
- PostgreSQL 16
- Docker & Docker Compose v2+

### 2. Environment Configuration

Copy the example environment file and configure secrets:

```bash
cp .env.example .env
```

---

## 💻 Local Development

### Backend Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run migrations
python backend/manage.py migrate

# Seed or verify workshop
python backend/manage.py shell -c "
from apps.workshops.models import Workshop
from datetime import datetime
from zoneinfo import ZoneInfo
Workshop.objects.get_or_create(
    id='public-speaking-workshop',
    defaults={
        'title': 'Public Speaking Workshop',
        'scheduled_at': datetime(2026, 9, 18, 15, 30, 0, tzinfo=ZoneInfo('Asia/Kolkata')),
        'timezone': 'Asia/Kolkata',
        'reminder_lead_minutes': 15,
        'is_active': True,
    }
)
"

# Start development server
PYTHONPATH=backend python backend/manage.py runserver 127.0.0.1:8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server starts at `http://localhost:5173` and automatically proxies `/api` requests to the Django backend on port 8000.

---

## 🐳 Production Deployment (Docker Compose)

### 1. Build and Run Containers

```bash
# Build production images
docker compose build

# Start services in background
docker compose up -d

# Verify container health
docker compose ps
```

### 2. Run Database Migrations

```bash
docker compose exec -T backend python manage.py migrate
```

### 3. Verify Container Status

```bash
# Check backend health
curl -s http://127.0.0.1:8000/api/v1/health/

# Check frontend Nginx root
curl -sI http://127.0.0.1:8088/
```

---

## ⏰ Production Reminder Scheduler

Workshop reminders are dispatched automatically 15 minutes prior to the workshop start via a native `systemd` timer executing inside the Docker container:

### Systemd Configuration
- **Timer Unit**: `/etc/systemd/system/public-speaking-workshop-reminders.timer`
- **Service Unit**: `/etc/systemd/system/public-speaking-workshop-reminders.service`
- **Execution Target**: Runs `backend/scripts/run_scheduler.sh` every minute.

```bash
# Check timer status
systemctl status public-speaking-workshop-reminders.timer

# View live scheduler execution logs
journalctl -u public-speaking-workshop-reminders.service -n 25 -f

# Manually trigger a scheduler run
sudo systemctl start public-speaking-workshop-reminders.service
```

---

## 🧪 Testing & Verification

### Running Backend Unit & Integration Tests

```bash
# In local virtual environment
PYTHONPATH=backend .venv/bin/python backend/manage.py test apps config

# Or inside running Docker container
docker compose exec -T backend python manage.py test apps config
```
*All 72 Django tests verify idempotency, outbox events, phone normalization, timezones, and reminder logic.*

### Running Frontend Checks

```bash
# From repository root
npm run lint
npm run build
```

---

## 🛡️ Security & Observability

- **Non-Root Execution**: Backend runs as `appuser` (UID 1001); Frontend runs on minimal Nginx Alpine.
- **Strict Allowed Hosts**: `ALLOWED_HOSTS = psw-api.lcrana.in,localhost,127.0.0.1,backend` (unauthorized hosts return `400 Bad Request`).
- **Strict CORS Policy**: `CORS_ALLOWED_ORIGINS` restricts API access to `https://psw.lcrana.in`. Preflight explicitly verifies `idempotency-key`.
- **Zero Secrets in Frontend**: Client bundles contain zero database, evolution, or webhook tokens.
- **Clean Logging**: All sensitive headers, phone numbers, and keys are masked or suppressed in application and systemd logs.

---

## 📄 License

Proprietary — All rights reserved.

# Real-Time Cloud-Based Event Planning & RSVP Tracker

A virtual, student-friendly cloud-computing project for event publishing, invitations, attendee responses, capacity control, announcements, notifications and organizer analytics.

> **Deployment status (2026-11-24):** the app is deployed as a Render Docker web service and uses Supabase PostgreSQL through its session pooler. The React frontend now supports Supabase Auth when `SUPABASE_URL` and `SUPABASE_ANON_KEY` are configured on Render; existing custom-token accounts remain supported during migration. The dashboard still uses two-second polling; Supabase Realtime, WebSockets, and external notifications are not deployed. See [`cloud/README.md`](cloud/README.md) for setup and limitations.

## Problem and objectives

Event details, guest replies and announcements often live across messages and spreadsheets. This app centralizes the event record and attendee response behind an API so participants can use separate devices and the organizer can see updated counts. It demonstrates REST, authentication, role authorization, relational constraints, transaction safety, polling-based live updates, notifications and an upgrade path to managed cloud services.

## Features

- Attendee and organizer registration/login through Supabase Auth when configured; FastAPI validates Supabase sessions and maps identities to app profiles. Legacy PBKDF2 accounts and signed tokens remain supported during migration.
- Event create, read, update and soft-cancel; date/time, online meeting link, event type, deadline and capacity fields.
- Invitations recorded by email; registered invitees receive an in-app invitation notice.
- One RSVP per event/user; Going, Maybe and Not Going updates; attendee cancellation and organizer-only guest list.
- Transaction-protected local capacity checks, FIFO waitlist and automatic first-in-line promotion when a Going attendee cancels or changes response.
- Announcements and persistent in-app notifications with read state.
- Organizer metrics for invite response rate, capacity utilization, open seats, waitlist and response history.
- Browser polls the API every two seconds so other profiles see new counts without a manual page refresh.
- Docker image, health route, environment configuration, CI workflow and automated tests.

## Architecture

```mermaid
flowchart LR
 Browser[Organizer / Attendee browser] -->|JSON REST + bearer token| API[FastAPI]
 API --> Auth[Authentication, RBAC, ownership]
 Auth --> DB[(SQLite local / SQL database URL)]
 API --> TX[Transactional RSVP and capacity check]
 Browser -->|2-second polling| API
 API --> Counts[Counts, announcements, in-app notifications]
 CDN[Optional cloud CDN] --> Browser
```

SQLite is the default local database; the deployed service selects Supabase PostgreSQL through `DATABASE_URL`. The backend applies an idempotent compatibility migration for the Supabase user-profile columns at startup. Versioned app-wide schema migrations and PostgreSQL reservation concurrency locking still need follow-up. Polling is the implemented realtime simulation. SSE, WebSockets, a managed realtime database, queues, external email/push delivery and autoscaling are architecture extensions, not current implementations. Full mapping is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Technology choices

| Option | Stack | Difficulty and cost | Tradeoffs |
|---|---|---|---|
| A: local simulation (implemented) | HTML/CSS/JS, FastAPI, SQLite, polling | Easy; free on your computer | Works offline; single-host database and polling only |
| B: student cloud (deployed) | React + FastAPI Docker service on Render, Supabase Auth (configurable), Supabase PostgreSQL, polling | Deployed for a student demo; provider costs and quotas vary | Set Supabase Auth URL/key on Render; PostgreSQL reservation locking and production operations need follow-up |
| C: advanced cloud | CDN, API gateway, serverless/container API, managed DB, WebSocket, queue, monitoring | Advanced; may incur charges | More scalable and operationally complex |

Cloud provider availability and free tiers change, so verify pricing, regional availability, retention and payment requirements before provisioning. Architecture alternatives are in the deployment guide.

## Roles and workflow

| Capability | Attendee | Organizer |
|---|---:|---:|
| Register/sign in, discover events, see announcements | Yes | Yes |
| Create/edit/cancel event, invite attendees | No | Own events |
| RSVP, update/cancel own RSVP, join waitlist | Yes | Yes |
| Guest roster and event analytics | No | Own events |
| Publish announcement | No | Own events |

Registration allows organizer self-selection for the synthetic local demonstration. Restrict organizer provisioning in any public deployment. Authentication answers who the user is; authorization checks role, ownership and record owner at each protected action.

## Real-time and capacity behavior

After an attendee submits a response, the backend validates deadline and capacity, writes within a transaction, and the organizer's browser picks up the authoritative aggregate on its next two-second poll. Polling is simple but repeats requests; SSE is a one-way server stream; WebSockets support two-way communication and fanout. A managed realtime subscription is another cloud option.

The naive sequence `if going_count < capacity: insert RSVP` can oversell because concurrent requests may both observe the last seat. SQLite uses `BEGIN IMMEDIATE` around the count/check/upsert, and `(event_id, user_id)` is unique. PostgreSQL should lock the event row or use an atomic reservation transaction; do not assume SQLite's file lock is a production multi-instance solution.

## Install and run locally

Python 3.11+ and pip:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:APP_SECRET = "replace-with-a-long-random-secret"
python -m uvicorn backend.app:app --reload
```

The React frontend runs through Vite on `http://127.0.0.1:5173`; keep FastAPI running on port 8000 for API requests. In a second terminal, change to `frontend`, run `npm ci`, then `node ./node_modules/vite/bin/vite.js --host 127.0.0.1`. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env` to enable Supabase Auth. For a production build, Docker builds the React bundle and FastAPI serves it. Interactive API docs are `/docs`; health is `/health`. The database defaults to `events.db` in this folder. To run the synthetic walkthrough, use a separate browser profile per user: create an organizer; create “Cloud Computing Workshop” with a future registration deadline and capacity 100; register attendees and test RSVP, announcements, cancellation, capacity, waitlist and unauthorized event edits. Never use real personal data.

For a three-window view, open the same URL in organizer, attendee A and attendee B profiles. Browser local storage is profile-specific; server database state is shared.

## Configuration and deployment

`.env.example` documents `DATABASE_URL`, `APP_SECRET`, `CORS_ORIGINS`, `SUPABASE_URL` and `SUPABASE_ANON_KEY`. Never commit `.env`. The deployed Render service builds this repository's Dockerfile, reads its port from Render's `PORT` setting, and connects to Supabase PostgreSQL using `DATABASE_URL`. Set the Supabase project URL and anon key on Render to enable Supabase Auth; the service-role key must remain server-side and is not used by this app. Set `APP_SECRET` to a strong non-default value before sharing the service publicly. See [`cloud/README.md`](cloud/README.md) for the setup summary. Check provider pricing and usage limits; cloud resources can incur costs.

## API, data and errors

The API has endpoints for auth, events, invitations, RSVPs, waitlists, attendee's RSVPs, guest lists, analytics, announcements and notifications. Read [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) for request shape, access rules and status codes. Relational records include users, events, RSVPs, waitlist entries, invitations, announcements, notifications and revoked session tokens. Unique constraints cover user email, `(event_id,user_id)` RSVP, waitlist membership, invitations and token signatures. The backend is the source of truth; UI counts are never accepted from clients.

## Testing

```powershell
python -m pytest -q
python -m compileall -q backend tests\test_app.py
node --check frontend/app.js
```

Tests cover assets, auth/passwords, role checks, event ownership/edit/cancel, RSVP changes and capacity, deadlines, invitation/announcement notifications, waitlist promotion, token logout and analytics. See [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md). Browser multi-user behavior and cloud restoration remain manual checks.

## Security, resilience and scale

Local controls include Supabase Auth token validation (when configured), legacy password hashing, HMAC-signed expiring sessions, server-side revocation, Pydantic validation, event ownership checks, notification ownership checks, parameterized SQLAlchemy queries and database uniqueness. Configure strict CORS, HTTPS, a secret manager, API rate limiting, backups, structured monitoring and least-privilege database accounts before public exposure. In-memory errors are returned through FastAPI; RSVP writes roll back on failure; polling retries on the next interval after transient network failure. External notification retry queues and idempotency keys are future work.

At higher volume, place stateless API replicas behind a gateway/load balancer, use managed database connections and indexes, cache public event detail, queue notifications, rate-limit RSVP bursts, and use a strongly consistent reservation transaction for hot events. Realtime fanout needs a shared broker rather than per-process memory. Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Project structure

```text
backend/                     FastAPI routes, SQLAlchemy models and local services
frontend/                    Browser HTML, CSS, JavaScript and polling refresh
tests/                       Automated route-logic tests
cloud/                       Container/cloud deployment notes
docs/                        Architecture, API, test and evidence guides
reports/                     Course report and placement materials
sample_data/                 Synthetic walkthrough data
screenshots/                 Genuine evidence screenshots (capture yourself)
.github/workflows/           Test CI
Dockerfile                   Container image
```

## Limitations and future improvements

The local default uses SQLite; the deployed service uses Supabase PostgreSQL. Both use polling, and organizer self-registration is still enabled, so the deployment is for a controlled student demo rather than public production use. Managed cloud auth/realtime, actual email/SMS/push, invitation delivery, automatic reminders, PostgreSQL-safe concurrent seat reservations, admin role, full migration tooling, load/stress tests and automated browser tests remain future work. No deployment URL or screenshot is recorded in this repository.

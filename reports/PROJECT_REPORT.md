# Real-Time Cloud-Based Event Planning & RSVP Tracker — Project Report

## Abstract

This project provides a virtual event planning and RSVP application. An organizer creates and manages an event, records invitees, monitors responses, shares announcements and reviews attendance metrics. Attendees discover events, respond Going/Maybe/Not Going, cancel or join a FIFO waitlist, and receive in-app updates. The app uses a React frontend, FastAPI, SQLAlchemy and PostgreSQL in its Render/Supabase student deployment; the dashboard uses two-second polling. Supabase Auth is supported when configured, with existing custom-token accounts retained during migration.

## Current deployment status

As of 2026-11-24, the application is deployed from this GitHub repository to a Render Docker web service. Render receives the Supabase session-pooler connection URL through a service environment variable; database credentials are not stored in the repository. The user reported that the `/health` database check and an app walkthrough completed successfully. Confirm in Render that `APP_SECRET` is set to a strong non-default value before sharing the service publicly. No public service URL or deployment screenshot is recorded here.

The deployment is a student demonstration, not a production-ready service. The app's capacity-write path uses `BEGIN IMMEDIATE` only with SQLite; PostgreSQL RSVP and waitlist operations still need database-level locking or atomic reservation logic and concurrency tests. The schema is initialized with SQLAlchemy `create_all` rather than a versioned production migration system. Organizer self-registration remains enabled, and the app still needs Supabase Auth credentials configured in Render before the managed sign-in flow is active there.

## Introduction and problem statement

Event coordination often spreads schedules, guest replies and last-minute announcements across separate tools. This makes it hard to maintain one authoritative attendee list or detect a capacity limit. The project centralizes event and response state behind an API so an organizer and attendees can view the same server-owned records.

## Objectives

1. Build a complete virtual demo using synthetic data.
2. Implement attendee/organizer authentication and authorization.
3. Manage event details and RSVP lifecycle.
4. prevent duplicate responses and protect capacity under local concurrency.
5. Show updated counts across browser profiles without manual refresh.
6. Demonstrate invitations, FIFO waitlist, notifications and analytics.
7. Document secure cloud deployment and its limitations accurately.

## Existing and proposed systems

The existing manual approach uses separate messages or spreadsheets and requires organizers to reconcile replies. The proposed application stores event data, invitations, RSVPs, waitlist records, announcements and notices in relational tables behind REST endpoints. The browser displays state and submits intent; it does not calculate or write authoritative counters.

## Industry relevance

Event platforms, conferences, college festivals, webinars, workshops, meetups, training programs, weddings, community events, ticketing and professional networking all use central schedules, capacity tracking, attendee communications and analytics. Centralization reduces manual coordination; remote access supports users on multiple devices; a queue and managed database can help scale bursts.

## Cloud computing concepts

Hosted deployment provides a SaaS-style experience. A managed app and DB are PaaS; virtual-machine and network management is IaaS. The deployed Render service and Supabase database demonstrate hosted compute, managed relational storage, environment-based secrets, REST, auth, RBAC, health checks and polling-based state synchronization. Managed identity, WebSockets/SSE, external notification functions, queues, a CDN, stronger production monitoring and tested backups remain possible extensions; they are not part of the current deployment.

## Architecture and technology

The client uses HTML, CSS and JavaScript; FastAPI exposes JSON; SQLAlchemy maps records; SQLite is local. `DATABASE_URL` is the DB adapter setting. The cloud target is a static CDN plus a hosted API, managed PostgreSQL, identity provider, realtime broker and notification queue. A complete component diagram and cloud concept mapping are in `docs/ARCHITECTURE.md`.

## Database design

Entities: USERS; EVENTS (organizer foreign key); RSVPS (event/user foreign keys and unique pair); WAITLIST (unique event/user, timestamp and queue status); INVITATIONS (unique event/email); ANNOUNCEMENTS; NOTIFICATIONS; REVOKED_TOKENS. Keys and indexes support lookups by email, owner, event, recipient and queue. Relational databases are appropriate because RSVP uniqueness and seat allocation require transactional consistency. A document DB could model event subcollections, but capacity updates must still use a transaction or conditional write.

```text
USER 1 ── N EVENT (organizer_id)
USER 1 ── N RSVP N ── 1 EVENT       unique(event_id, user_id)
USER 1 ── N WAITLIST N ── 1 EVENT   FIFO joined_at/id
EVENT 1 ── N INVITATION / ANNOUNCEMENT / NOTIFICATION
```

## Authentication and authorization

The React sign-in flow uses Supabase Auth when configured. FastAPI validates Supabase access tokens against the Auth user endpoint and maps the authenticated email and metadata to the app's relational user record. Legacy local accounts still use salted PBKDF2 hashes and 24-hour HMAC-signed bearer tokens with server-side logout revocation during migration. Organizer-only operations check role and ownership; attendees can change only their own RSVP and notification. Organizer self-selection is allowed only in this synthetic local demo and must be restricted in a public deployment.

## Event, RSVP and real-time workflow

An organizer publishes an event with date/time, venue or online URL, capacity and RSVP deadline. An attendee submits a status. The backend validates the input, checks deadline and capacity, upserts a single event/user response, and emits an in-app confirmation. The browser polls every two seconds and renders the aggregate. If a Going attendee cancels or switches status, the FIFO waitlist promotes the first eligible attendee and creates a notice.

Polling is simple and reconnects through the next request, but it uses repeated reads. SSE streams one-way server events; WebSockets are bidirectional; a cloud realtime DB can publish row changes. Those are possible replacements and are not implemented here.

## Capacity and concurrency

For capacity 100 with 99 Going, two independent requests could both read 99 and insert, producing 101. SQLite's `BEGIN IMMEDIATE` serializes write attempts before the current count/check/upsert. A database unique constraint blocks duplicate RSVP rows. A production PostgreSQL service needs an event-row lock or conditional atomic reservation inside one transaction, and a simultaneous-request test. SQLite's lock is not the cloud multi-instance concurrency strategy.

## Announcements, notifications and analytics

Organizer announcements are persisted and copied into in-app notices for current respondents and registered invitees. RSVP confirmation, invitation, cancellation and waitlist promotion also generate notices. The user can mark their own notice read. External email/SMS/push is future work. Analytics include invited/response totals, response rate when invitation denominator is available, Going capacity utilization, open seats, waitlist size and response updates over time.

## API, implementation and testing

The API endpoint/method/body/access/status-code table is in `docs/API_REFERENCE.md`. Tests cover assets, password/login, role and ownership rules, capacity, waitlist promotion, cancellation, notifications and metrics using isolated SQLite databases. Run `python -m pytest -q`, `python -m compileall -q backend tests/test_app.py`, and `node --check frontend/app.js`. The user reported completing the deployed `/health` check and app walkthrough; cloud database restore, PostgreSQL concurrency behavior and production load have not been tested.

## Deployment, security and failure handling

The `Dockerfile` runs the app on the port supplied by the hosting platform, and `requirements.txt` includes PostgreSQL drivers. Render supplies the Supabase `DATABASE_URL` outside source control. Verify that `APP_SECRET` is set to a strong value rather than the local default before sharing the service publicly. The host provides HTTPS; production operation still needs a security review, restricted organizer provisioning, rate limits, audit logging, a versioned migration process, monitored error rates, tested backups and restore drills. RSVP transactions roll back on failure, but PostgreSQL seat allocation is not yet protected against concurrent oversubscription. Polling resumes after transient disconnection. External notification queue retries and idempotency keys are future work.

## Scalability

At small scale, one API and DB work for a class demonstration. At medium scale, add stateless replicas, DB pooling/indexes, CDN and realtime broker. At flash-crowd scale, rate-limit requests, queue side effects, shard read traffic and carefully serialize reservations for hot events. Seat decisions must remain strongly consistent; cached counters are display-only.

## Results, advantages, limitations and future scope

The application exercises event create/edit/cancel, RSVP update/cancel, capacity, waitlist, invitation, in-app notification, analytics and polling. Its current student deployment runs on Render with Supabase PostgreSQL and has a reported successful health check and walkthrough. Limitations include polling, organizer self-registration, no managed cloud auth/realtime/email service, no mature schema migration stack, and no PostgreSQL concurrency or load-test evidence. Future steps: restrict organizer provisioning, implement and test PostgreSQL reservation locking, add WebSockets/SSE or external notification delivery if needed, add audit history and admin moderation, and verify backup restoration.

## Conclusion

This is a runnable cloud-computing teaching project with a student-demo deployment on Render and Supabase. The deployment demonstrates a hosted API and managed PostgreSQL, while the report identifies the consistency, security and operations work still required before treating it as a public production service.

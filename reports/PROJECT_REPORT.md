# Real-Time Cloud-Based Event Planning & RSVP Tracker — Project Report

## Abstract

This project provides a virtual event planning and RSVP application. An organizer creates and manages an event, records invitees, monitors responses, shares announcements and reviews attendance metrics. Attendees discover events, respond Going/Maybe/Not Going, cancel or join a FIFO waitlist, and receive in-app updates. The local implementation uses FastAPI, SQLAlchemy, SQLite, signed sessions and a browser client with two-second polling. It demonstrates core cloud application patterns without requiring paid services. Managed cloud services are documented as a deployment target and are not represented as already deployed.

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

Hosted deployment provides a SaaS-style experience. A managed app and DB are PaaS; virtual-machine and network management is IaaS. The local app demonstrates REST, auth, RBAC, relational constraints, transaction logic, environment-based configuration and health checks. Polling demonstrates state synchronization. A production evolution can add a CDN, gateway/load balancer, managed database, provider auth, WebSockets/SSE, serverless notification functions, queues, secret manager, logs/metrics, backups and CI/CD. Those cloud resources are design targets, not currently provisioned.

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

Registration hashes passwords using PBKDF2 with a random salt. Login returns an HMAC-signed bearer token with a 24-hour expiry. Logout revokes the token signature in the database. API dependencies resolve the user for protected calls. Organizer-only operations check role and ownership; attendees can change only their own RSVP and notification. Organizer self-selection is allowed only in this synthetic local demo and must be restricted in a public deployment.

## Event, RSVP and real-time workflow

An organizer publishes an event with date/time, venue or online URL, capacity and RSVP deadline. An attendee submits a status. The backend validates the input, checks deadline and capacity, upserts a single event/user response, and emits an in-app confirmation. The browser polls every two seconds and renders the aggregate. If a Going attendee cancels or switches status, the FIFO waitlist promotes the first eligible attendee and creates a notice.

Polling is simple and reconnects through the next request, but it uses repeated reads. SSE streams one-way server events; WebSockets are bidirectional; a cloud realtime DB can publish row changes. Those are possible replacements and are not implemented here.

## Capacity and concurrency

For capacity 100 with 99 Going, two independent requests could both read 99 and insert, producing 101. SQLite's `BEGIN IMMEDIATE` serializes write attempts before the current count/check/upsert. A database unique constraint blocks duplicate RSVP rows. A production PostgreSQL service needs an event-row lock or conditional atomic reservation inside one transaction, and a simultaneous-request test. SQLite's lock is not the cloud multi-instance concurrency strategy.

## Announcements, notifications and analytics

Organizer announcements are persisted and copied into in-app notices for current respondents and registered invitees. RSVP confirmation, invitation, cancellation and waitlist promotion also generate notices. The user can mark their own notice read. External email/SMS/push is future work. Analytics include invited/response totals, response rate when invitation denominator is available, Going capacity utilization, open seats, waitlist size and response updates over time.

## API, implementation and testing

The API endpoint/method/body/access/status-code table is in `docs/API_REFERENCE.md`. Tests cover assets, password/login, role and ownership rules, capacity, waitlist promotion, cancellation, notifications and metrics using isolated SQLite databases. Run `python -m pytest -q`, `python -m compileall -q backend tests/test_app.py`, and `node --check frontend/app.js`. Multi-profile browser simulation is a manual check; cloud deployment and restore have not been tested.

## Deployment, security and failure handling

The `Dockerfile` and `cloud/README.md` document a container deployment. The operator must set a strong `APP_SECRET`, managed `DATABASE_URL`, strict CORS origins, TLS, least-privilege credentials, backups and budget alerts. SQLAlchemy parameterizes DB operations. Production also needs rate limits, audit logging, migrations, monitored error rates and restore drills. Transactions roll back on RSVP failure; polling resumes after transient disconnection. External notification queue retries and idempotency keys are future work.

## Scalability

At small scale, one API and DB work for a class demonstration. At medium scale, add stateless replicas, DB pooling/indexes, CDN and realtime broker. At flash-crowd scale, rate-limit requests, queue side effects, shard read traffic and carefully serialize reservations for hot events. Seat decisions must remain strongly consistent; cached counters are display-only.

## Results, advantages, limitations and future scope

The local implementation exercises event create/edit/cancel, RSVP update/cancel, capacity, waitlist, invitation, in-app notification, analytics and polling. Advantages include no hardware/cloud requirement, clear role boundaries and reproducible synthetic data. Limitations: single-process local app, polling, demo organizer self-registration, no actual cloud auth/realtime/email service, no mature schema migration stack or stress/browser suite. Future steps: managed identity, PostgreSQL row-lock implementation, WebSockets/SSE, external notification provider, audit history, admin moderation, load testing, automated browser tests and a verified deployment.

## Conclusion

This is a runnable cloud-computing teaching project, not a claim of an already-hosted production service. It demonstrates centralized application design and transactional RSVP fundamentals locally, while identifying the concrete infrastructure and consistency work required before public deployment.

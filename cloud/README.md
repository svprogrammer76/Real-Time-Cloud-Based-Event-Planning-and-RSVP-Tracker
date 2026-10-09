# Cloud deployment guide

## What is implemented locally

The checked-in app is FastAPI + SQLAlchemy + SQLite by default. `DATABASE_URL` selects the database; `APP_SECRET` signs and revokes sessions. The container build uses environment variables and a non-root user. This repository does not contain cloud credentials, a live cloud project, a managed auth provider integration, WebSockets, or proof of a deployment. Do not claim those resources were deployed.

## Student cloud path

Use an architecture with static frontend/CDN, a container-capable API host, managed PostgreSQL, secret environment variables, TLS, logs, backup and a budget alert. Verify each provider's current free eligibility, sleeping/retention limits, region, database availability, and payment requirements before choosing it; free tiers and policies change.

1. Create a managed PostgreSQL instance and a private database user with only app-level permissions.
2. Apply the SQLAlchemy schema/migrations. For a first clean database, starting the app creates tables; production should use versioned migrations before release.
3. Build and deploy this Dockerfile to a container host. Set `DATABASE_URL` to the provider's private connection URL and `APP_SECRET` to a long randomly generated secret in the host's secret store.
4. Restrict inbound database connections to the application, require TLS for public traffic, and set allowed origins if the frontend is hosted on a separate origin (CORS configuration is a production follow-up).
5. Check `/health`, create synthetic organizer/attendee accounts, verify the two-browser RSVP flow and capacity limit, and inspect host logs.
6. Enable database backups and test a restore. Configure usage alerts and document teardown.

Current cloud-app limitation: event capacity uses SQLite `BEGIN IMMEDIATE` only when the selected SQL dialect is SQLite. PostgreSQL requires an explicit event-row lock or atomic conditional update before production use; change this implementation and run concurrency tests before switching the database. The `create_all` startup plus additive SQLite migrations are suitable for this local student demo, not a multi-instance production migration process.

## Advanced AWS reference

CloudFront → static frontend; Cognito → managed identity; API Gateway or App Runner → API; RDS PostgreSQL/DynamoDB → persistent data; API Gateway WebSocket API → realtime fanout; SNS/SES → notifications; CloudWatch → logs/alarms; Secrets Manager → credentials. Use private subnets and least-privilege IAM. Equivalent Azure components include Static Web Apps, Functions/App Service, Azure Database for PostgreSQL, Entra External ID, Service Bus, Monitor and Key Vault. GCP equivalents include Firebase Hosting/Cloud Run, Cloud SQL/Firestore, Identity Platform, Pub/Sub, Cloud Monitoring and Secret Manager.

These are target architectures only. Pricing, quota and current free eligibility must be checked in provider documentation before provisioning; creating cloud resources can incur charges.

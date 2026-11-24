# Cloud deployment guide

## Current deployment status

As of 2026-11-24, the app is deployed as a Render Docker web service built from this GitHub repository and connected to a Supabase PostgreSQL database through the Supabase session pooler. `DATABASE_URL` is configured in the Render environment and is not stored in source control. Verify that `APP_SECRET` is set to a strong non-default value before sharing the service publicly. The user reported a successful `/health` check and app walkthrough. The public service URL is not recorded here.

Local development still uses SQLite by default. The deployed service uses PostgreSQL. The Docker image builds and serves the React frontend, runs as a non-root user and honors the platform-provided `PORT`. The React auth form supports Supabase Auth when its project URL and anon key are configured; existing custom-token accounts remain valid during migration. Event updates still use polling; Supabase Realtime/WebSockets and external email/push delivery are not implemented.

## Student cloud path

The current student setup uses one Render Docker web service for both the FastAPI API and browser assets, plus Supabase PostgreSQL. Render builds from the GitHub repository and deploys on pushed changes. Supabase's session-pooler URL is supplied as `DATABASE_URL`; `APP_SECRET` is a separate Render secret. The service's `/health` route checks database reachability. Verify provider pricing, quotas, sleep/retention limits and backups in the provider dashboards; terms and costs can change.

1. Connect the GitHub repository to a Render Docker web service; the root `Dockerfile` builds the app.
2. Set `DATABASE_URL` to the session-pooler connection string copied from Supabase's Connect dialog. Keep its host and project-qualified username exactly as supplied; do not commit the URL.
3. Set a long random `APP_SECRET` in Render's environment-variable settings. Do not use the local default; verify the value in the service settings.
4. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` from the Supabase project settings in Render. Set the Supabase Auth site URL to the Render service URL and allow that URL as a redirect. Never put the service-role key in the browser or use it for this setting.
5. Deploy and check `/health`; it should return `{"ok":true,"database":"reachable"}`. Test the browser app with synthetic accounts and event data.
6. Review Supabase backup/retention options and provider usage limits. The service URL is intentionally not embedded in this repository.

Important limitation: event capacity uses SQLite `BEGIN IMMEDIATE` only when the selected dialect is SQLite. The deployed PostgreSQL RSVP flow does not yet use an event-row lock or atomic conditional reservation, so concurrent requests may oversubscribe an event. This deployment is appropriate for a controlled student demo, not high-concurrency public production. Add PostgreSQL locking and concurrency tests before relying on strict capacity enforcement. Startup `create_all` and additive SQLite migrations are not a versioned production migration process.

## Advanced AWS reference

CloudFront → static frontend; Cognito → managed identity; API Gateway or App Runner → API; RDS PostgreSQL/DynamoDB → persistent data; API Gateway WebSocket API → realtime fanout; SNS/SES → notifications; CloudWatch → logs/alarms; Secrets Manager → credentials. Use private subnets and least-privilege IAM. Equivalent Azure components include Static Web Apps, Functions/App Service, Azure Database for PostgreSQL, Entra External ID, Service Bus, Monitor and Key Vault. GCP equivalents include Firebase Hosting/Cloud Run, Cloud SQL/Firestore, Identity Platform, Pub/Sub, Cloud Monitoring and Secret Manager.

These are target architectures only. Pricing, quota and current free eligibility must be checked in provider documentation before provisioning; creating cloud resources can incur charges.

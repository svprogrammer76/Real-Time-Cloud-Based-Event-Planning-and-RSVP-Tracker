# API reference

All `/api` routes require `Authorization: Bearer <token>` except registration and login. JSON errors use FastAPI's standard `detail`; malformed fields return 422. The app uses synthetic accounts and local SQLite by default.

| Method | Route | Body / result | Access | Typical errors |
|---|---|---|---|---|
| POST | `/api/register` | name, email, password, role → token/user | Public; organizer self-selection is local demo only | 409 duplicate, 422 invalid |
| POST | `/api/login` | email, password → token/user | Public | 401 invalid credentials |
| POST | `/api/logout` | none → logged_out | Signed in; revokes current token | 401 invalid/revoked |
| GET | `/api/me` | current user | Signed in | 401 |
| GET | `/api/events` | published events and counters | Signed in | 401 |
| GET | `/api/events/{id}` | event detail | Signed in | 404 missing/cancelled |
| POST | `/api/events` | name, description, date, time, end_time, venue, online_link, capacity, deadline, event_type | Organizer | 403 role; 422 invalid |
| PUT | `/api/events/{id}` | same event body | Owning organizer | 403 owner; 404 missing; 409 capacity below Going |
| DELETE | `/api/events/{id}` | soft cancel result | Owning organizer | 403 owner; 404 missing |
| POST | `/api/events/{id}/invitations` | `{"emails":[...]}` | Owning organizer | 403 owner; 422 invalid email |
| PUT | `/api/events/{id}/rsvp` | `{"status":"GOING|MAYBE|NOT_GOING"}` | Signed-in attendee | 404 missing; 409 deadline/full; 422 status |
| DELETE | `/api/events/{id}/rsvp` | delete own RSVP; FIFO promotion if seat freed | Signed in; own record only | 404 no RSVP |
| POST | `/api/events/{id}/waitlist` | optional empty body → queue position | Signed in attendee | 409 not full/deadline/already RSVP |
| DELETE | `/api/events/{id}/waitlist` | Leave own active queue entry | Signed in attendee; own record only | 404 no active entry |
| GET | `/api/rsvps/me` | own RSVP rows and event summary | Signed in | 401 |
| GET | `/api/events/{id}/rsvps` | counts, attendee guest list, FIFO waitlist | Owning organizer | 403 owner; 404 missing |
| GET | `/api/events/{id}/analytics` | invite response, capacity and growth metrics | Owning organizer | 403 owner; 404 missing |
| POST | `/api/events/{id}/announcements` | title, message | Owning organizer | 403 owner; 404 missing |
| POST | `/api/events/{id}/reminders` | none → number of targeted registered users | Owning organizer | 403 owner; 404 missing |
| GET | `/api/events/{id}/announcements` | event update list | Signed in | 401 |
| GET | `/api/notifications` | current user's in-app notices | Signed in | 401 |
| PUT | `/api/notifications/{id}/read` | `{"is_read":true}` | Notification owner | 403 owner; 404 missing |
| GET | `/api/analytics` | organizer's event totals | Signed in | 401 |

The frontend should send the API base domain in `CORS_ORIGINS` when hosted separately. For local same-origin hosting, the default allows localhost development origins.

Session tokens last 24 hours and are revoked on logout. `DELETE /events/{id}` is a soft cancellation; the event remains in the database for notification/history purposes.

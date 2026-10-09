# Test plan and execution record

Run `python -m pytest -q`, `python -m compileall -q backend tests/test_app.py`, and `node --check frontend/app.js`. Automated tests invoke route logic against per-test SQLite DB files. They do not claim cloud, multi-process load, browser rendering, or provider integration tests.

| ID | Scenario | Current automated coverage | Expected |
|---|---|---|---|
| T01 | Static page assets | Yes | HTML, CSS, JS present |
| T02 | Registration/login/password | Yes | Valid login; duplicate rejected |
| T03 | Role protection | Yes | Attendee cannot publish |
| T04 | Event creation/read/edit/cancel | Yes | Owner controls; cancelled hidden |
| T05 | Event ownership | Yes | Other organizer receives 403 |
| T06 | Valid RSVP and update | Yes | Unique record updates status |
| T07 | Capacity limit | Yes | Additional Going returns 409 |
| T08 | RSVP cancellation | Yes | Own RSVP removed |
| T09 | Deadline and invalid status | Yes | Rejects with 409/422 |
| T10 | Invitations | Yes | Unique invite and registered user notice |
| T11 | FIFO waitlist promotion | Yes | First waiting user promoted after seat release |
| T12 | Announcements/notifications/read ownership | Yes | Notice created; only recipient can mark read |
| T12a | Venue/time update and manual reminder | Yes | RSVP holders and registered invitees receive in-app notices |
| T13 | Analytics | Yes | Response, capacity, growth and event totals |
| T14 | Token logout revocation | Yes | Revoked token rejected |
| T15 | Simultaneous final-seat contention | Yes | Two parallel requests for one seat yield one success and one full response |
| T16 | DB outage, API timeout, browser offline | Manual/future | Graceful error/retry, no partial write |
| T17 | Browser two-profile polling | Manual | Organizer view reflects attendee change within 2 seconds |
| T18 | Cloud deployment/restore | Not run | Verify only after real provider deployment |

Current run status is reported from the latest local execution, not pre-filled into a fabricated pass/fail log. Keep screenshots in `screenshots/` only after capturing the real application.

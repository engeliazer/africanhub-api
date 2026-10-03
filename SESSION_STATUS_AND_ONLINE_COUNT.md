# Session status and online count

One active login per user. The frontend polls every 10 seconds. If that user logs in somewhere else, the older screen signs out. A user counts as online when their last successful poll was within 60 seconds.

Who may see the online number is decided in the frontend. The count endpoint does not check roles.

## Table changes

Add two columns to `users`. Run this before deploying, or login fails because the query selects columns that are not there yet.

```sql
ALTER TABLE users
  ADD COLUMN active_session_id VARCHAR(36) NULL AFTER remember_token;

ALTER TABLE users
  ADD COLUMN last_seen_at DATETIME NULL AFTER active_session_id,
  ADD INDEX ix_users_last_seen_at (last_seen_at);

ALTER TABLE users
  ADD COLUMN last_page VARCHAR(500) NULL AFTER last_seen_at;

ALTER TABLE users
  ADD COLUMN last_login DATETIME NULL AFTER active_session_id;
```

| Column | Type | Purpose |
| --- | --- | --- |
| `active_session_id` | `VARCHAR(36) NULL` | UUID of the latest login. The next login replaces it. |
| `last_login` | `DATETIME NULL` | UTC time of that login. Set on login, not on each status check. |
| `last_seen_at` | `DATETIME NULL` | UTC time of the latest valid status check. |
| `last_page` | `VARCHAR(500) NULL` | Route the user was on at that check, sent by the frontend as `page`. |

```sql
SELECT COUNT(*)
FROM users
WHERE deleted_at IS NULL
  AND last_seen_at IS NOT NULL
  AND last_seen_at >= UTC_TIMESTAMP() - INTERVAL 60 SECOND;
```

## Login

`POST /api/auth/login`

On success the server:

1. Creates a new UUID and saves it as `users.active_session_id`.
2. Puts that same id in the JWT as `sid`. The subject `sub` is the user id.
3. Returns `token` and `session_id`.

```json
{
  "status": "success",
  "message": "Login successful",
  "data": {
    "token": "<jwt>",
    "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "user": { "id": 12 }
  }
}
```

Self-registration returns `session_id` the same way. A later login replaces it.

Store `data.token` and `data.session_id`.

## Session status

`GET /api/auth/session-status` or `POST /api/auth/session-status`

Call it every 10 seconds while the user is logged in. Send either:

```http
GET /api/auth/session-status?page=/dashboard
Authorization: Bearer <token>
```

or:

```http
GET /api/auth/session-status?user_id=12&session_id=<session_id from login>&page=/dashboard
```

`page` is the route the user is on right now, such as `/dashboard` or `/courses/12`. Send it on every check. `user_id` alone is not enough. Every device shares it, so send `session_id` with it. `POST` accepts the same fields in JSON. A raw JWT can also be sent as `token`.

The server compares the caller's session id with `users.active_session_id`.

Still the active login (`200`):

```json
{
  "status": "success",
  "message": "This session is still the active login.",
  "data": {
    "user_id": 12,
    "another_login_detected": false,
    "session_valid": true
  }
}
```

The server then sets `last_seen_at` to now (UTC) and `last_page` to `page` if `last_seen_at` is empty or older than 15 seconds. A changed `page` is saved immediately, and `last_seen_at` is updated with it. The write is skipped when the session was replaced. If `page` is omitted, `last_page` is left as it was.

Replaced by a newer login (`200`):

```json
{
  "status": "success",
  "message": "Another login was detected on a different device or browser.",
  "data": {
    "user_id": 12,
    "another_login_detected": true,
    "session_valid": false
  }
}
```

When `another_login_detected` is true, stop the timer, clear the stored token and session id, and show `message`.

`401` means the token cannot be read. Sign out, and do not show the another-login message.

Other errors: `400` if the token's user and `user_id` disagree, if `session_id` is missing, or if `user_id` is not a number. `404` if the user does not exist.

Tokens from before this feature have no `sid`. They stay valid until the next login. That login sets `active_session_id`, and the older token then reports another login.

Stop polling after logout.

## Online count

`GET /api/auth/online-count`

No login or role check. The frontend decides who can open the screen that calls it.

```json
{
  "status": "success",
  "data": {
    "online_users": 12,
    "window_seconds": 60
  }
}
```

`online_users` is how many non-deleted users have `last_seen_at` within the last 60 seconds. One person is one user, even though their app calls session status every 10 seconds.

Poll this about every 10–30 seconds on the screen that shows the number. This call does not mark anyone online. Only a valid session-status check does that.

## Online users

`GET /api/auth/online-users`

Same 60-second window and no role check. Returns each online user:

```json
{
  "status": "success",
  "data": {
    "window_seconds": 60,
    "users": [
      {
        "id": 12,
        "first_name": "Amina",
        "middle_name": null,
        "last_name": "Juma",
        "phone": "255700000000",
        "email": "amina@example.com",
        "last_login": "2026-10-03T10:15:00",
        "last_page": "/dashboard"
      }
    ]
  }
}
```

`last_login` is when this session started. It stays empty until the user logs in again after the column is added. `last_page` is the route from the latest status check.

## Rebuild on another system

1. Add `active_session_id`, `last_login`, `last_seen_at`, and `last_page` to the user table.
2. On login, save a new UUID and the current time as `last_login`, return the id as `session_id`, and put it in the token as `sid`.
3. Every 10 seconds, send the current route as `page` and compare the session id with the stored one. Return `another_login_detected: true` with HTTP 200 when they differ, and sign the client out.
4. When they match, set `last_seen_at` and `last_page` if the last check is older than 15 seconds, or immediately when `page` changed.
5. Count users whose `last_seen_at` is within the last 60 seconds. Leave access control to the frontend.

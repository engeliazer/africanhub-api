# Mail worker (Redis + Celery) — operations

Invitation bulk send needs **Redis** and a **Celery worker** on the `mail_processing` queue.

## Automatic ensure (recommended)

When a user calls **`POST /api/invitations/{id}/send/start`**, the API tries to start services if they are down (when `MAIL_WORKER_AUTO_ENSURE=true`, default).

### One-time server setup

1. Install Redis (if missing): `sudo apt install -y redis-server`
2. Install systemd unit:
   ```bash
   sudo cp scripts/africanhub-celery-mail.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now africanhub-celery-mail.service
   ```
3. Allow the app user to start/restart without a password (for API ensure):
   ```bash
   sudo tee /etc/sudoers.d/africanhub-mail-worker <<'EOF'
   africanhub ALL=NOPASSWD: /bin/systemctl start redis-server.service, /bin/systemctl start africanhub-celery-mail.service, /bin/systemctl restart africanhub-celery-mail.service
   EOF
   sudo chmod 440 /etc/sudoers.d/africanhub-mail-worker
   ```

### `.env` (optional)

```env
APP_ROOT=/var/www/africanhub-api.africanhub.ac.tz
MAIL_WORKER_AUTO_ENSURE=true
MAIL_WORKER_SYSTEMD_UNIT=africanhub-celery-mail.service
REDIS_SYSTEMD_UNIT=redis-server.service
MAIL_WORKER_USE_SUDO=true
# Fallback if systemd/sudo not configured (spawns detached worker — use only on small setups):
# MAIL_WORKER_SPAWN_IF_MISSING=true
```

## API endpoints (JWT)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/invitations/mail-worker/status` | Redis + worker health |
| POST | `/api/invitations/mail-worker/ensure` | Start Redis/worker if down |
| POST | `/api/invitations/mail-worker/restart` | Restart mail worker (admin) |

**Send/start response** includes `mail_worker` with the result of the last ensure attempt.

## Frontend

- On **Send / Resume**, call `POST .../send/start` as today — no extra step if ops setup is done.
- Optional: `GET .../mail-worker/status` before send; if `ready: false`, show “Starting mail services…” then call `POST .../mail-worker/ensure`, then send/start.
- If `queued_via_celery: false` and `mail_worker.ready: false`, show: contact support / mail services could not be started.

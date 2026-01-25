# SMS (mShastra) troubleshooting on deployment

Deployment path: `/var/www/africanhub-api.africanhub.ac.tz`  
Gunicorn service: `gunicorn-api` (or whatever runs the Flask app)

---

## Test SMS to a specific number

To send a **test SMS** (e.g. to `255717098911`) and see the API response:

```bash
cd /var/www/africanhub-api.africanhub.ac.tz
```

**Option A – use venv** (recommended; has `requests`):

```bash
# If you have venv or .venv:
bash scripts/run_send_test_sms.sh 255717098911 "Test from AfricanHub API"
# or
venv/bin/python3 scripts/send_test_sms.py 255717098911 "Test from AfricanHub API"
```

**Option B – system python** (requires `requests`: `pip install requests`):

```bash
python3 scripts/send_test_sms.py 255717098911 "Test from AfricanHub API"
```

With no args, it uses `255717098911` and a default message:

```bash
python3 scripts/send_test_sms.py
```

Ensure `MSHASTRA_PWD` is set in `.env`. The script prints config and the raw mShastra API response (status + body).

---

## 1. Run the troubleshoot script

```bash
cd /var/www/africanhub-api.africanhub.ac.tz
bash scripts/troubleshoot_sms.sh
```

This checks:
- `MSHASTRA_*` env vars in `.env`
- Where logs are written
- Recent SMS-related log lines
- **`SMS API says:`** — the raw mShastra API response
- Gunicorn process
- A quick `curl` test to the mShastra API URL

## 2. Inspect logs manually

**Live Gunicorn logs (follow):**
```bash
sudo journalctl -u gunicorn-api -f
```

**SMS-related lines only:**
```bash
sudo journalctl -u gunicorn-api -n 500 --no-pager | grep -E "SMS API|SMS send|MSHASTRA"
```

**Raw API response (what mShastra returned):**
```bash
sudo journalctl -u gunicorn-api -n 500 --no-pager | grep "SMS API says:"
```

## 3. Confirm env vars

```bash
cd /var/www/africanhub-api.africanhub.ac.tz
grep MSHASTRA .env
```

Ensure you have:
- `MSHASTRA_USER=AFRICANHUB`
- `MSHASTRA_PWD=AfricanHub@2026`
- `MSHASTRA_SENDER=AFRICANHUB`

If you change `.env`, restart Gunicorn:
```bash
sudo systemctl restart gunicorn-api
```

## 4. Reproduce and watch logs

1. In one terminal:
   ```bash
   sudo journalctl -u gunicorn-api -f | grep -E "SMS|MSHASTRA"
   ```
2. In another (or from your app): trigger registration (or call `POST /api/sms/send`).
3. Check the first terminal for `SMS API says:` and any errors.

## 5. If the service name differs

If your systemd unit is not `gunicorn-api`:

```bash
# Find the app unit
systemctl list-units --type=service | grep -E gunicorn|flask|africanhub|python
```

Then use that name, e.g.:
```bash
sudo journalctl -u your-service-name -n 500 --no-pager | grep "SMS API says:"
```

Or run the script with:
```bash
GUNICORN_SVC=your-service-name bash scripts/troubleshoot_sms.sh
```

# SMS sending with Mastercodes

All sends use `SMSService` in `public/controllers/sms_controller.py`, including registration, password resets, payments, custom sends and broadcasts. Existing HTTP route names and service method arguments remain supported.

## Server configuration

Set these values in the server environment or project `.env`:

```dotenv
MASTERCODES_SMS_SENDER_KEY=your_sender_key
MASTERCODES_SMS_SENDER_SECRET=your_sender_secret
# Optional audit label; gateway credentials determine the actual sender:
MASTERCODES_SMS_SENDER=AFRICANHUB
# Optional gateway base URL (without /send):
MASTERCODES_SMS_API_URL=https://api.mastercodes.co.tz/api/v1/gateway/sms
```

Use sender credentials issued by Mastercodes. mShastra credentials are no longer used. Restart the application's Gunicorn service after deploying code and configuring credentials. Apply the audit metadata migration described below before restarting; no new dependencies are needed. Existing audit records retain their historical provider values.

## Gateway contract

The service posts to `/send` with `X-Sender-Key` and `X-Sender-Secret` headers and JSON fields `request_id` (UUID), `recipient` (international number with `+`), and `message`. Local Tanzanian numbers get `+255`; explicit international numbers are preserved. `sender` arguments remain audit labels and cannot override the sender selected by the credentials.

Success requires both HTTP 2xx and `data.messages[0].status == "sent"`. This means gateway acceptance, not confirmed handset delivery. Invalid JSON, rejected statuses and missing credentials fail. Connection errors, timeouts and HTTP 5xx get one retry after 200 ms using the same request ID and payload. Connect/read timeouts are 5/10 seconds and redirects are disabled. Manually resending creates a new ID and can duplicate a message whose outcome was uncertain.

Every attempted message writes a `sms_logs` row with provider `mastercodes`, acceptance status, raw response and error. Audit write failures are logged without breaking the send result. Gateway IDs are stored when an `id` or `message_id` is returned. Request logs exclude credentials and message content.

`send_messages` sends individual messages so each recipient retains its own text and audit row. Overall success requires all recipients to succeed; `data` includes `results`, `accepted`, and `failed`. This path does not use the asynchronous bulk gateway endpoint.

Registration still returns HTTP 201 for a created account, with an additional `data.sms` object containing `success` and `message`. A failed SMS does not undo registration. The frontend can show a notification failure using this object.

## Balance and top-up

The supplied integration reference describes Mastercodes balance and portal access. AfricanHub now exposes authenticated `GET /api/sms/sms-balance` and `POST /api/sms/portal-access` routes. Both return `{ "success": true, "data": { ... } }` on success and HTTP 502 with a safe error message when the gateway response cannot be confirmed. Portal responses use `Cache-Control: no-store, private`. Sender credentials remain on the server. Deploy the updated API before using these frontend controls.

### Checking the gateway balance

From a backend, call:

```http
GET https://api.mastercodes.co.tz/api/v1/gateway/sms/balance
X-Sender-Key: YOUR_SENDER_KEY
X-Sender-Secret: YOUR_SENDER_SECRET
Accept: application/json
```

Use the same credentials as sending. Keep them on the server. The reference describes these fields under the response's `data` object:

```json
{
  "sender_id_registration_id": 7,
  "available_units": 1500,
  "reserved_units": 0,
  "sender_name": "AFRICANHUB",
  "service_provider": "MASTERCODES",
  "top_up_url": "https://mastercodes.co.tz/account/home/sms?tab=purchase"
}
```

These values are illustrative. Display `available_units` as available SMS units, optionally with `reserved_units` and `sender_name`. A balance of zero is a valid result. An upstream error or malformed response should show a lookup failure, rather than a zero balance. The AfricanHub proxy requires authentication and returns HTTP 502 when the lookup cannot be confirmed.

### Adding SMS credit

The balance response's `top_up_url` points to the regular Mastercodes account purchase page. Open that URL, sign in as needed, and complete the purchase in Mastercodes. Refresh the balance afterwards to confirm the available units. Use the actual provider-returned URL rather than assuming the example is permanent.

For a short-lived authenticated portal link, the reference describes this backend gateway request:

```http
POST https://api.mastercodes.co.tz/api/v1/gateway/sms/portal-access
X-Sender-Key: YOUR_SENDER_KEY
X-Sender-Secret: YOUR_SENDER_SECRET
Accept: application/json
```

No request body is required. Expected response data:

```json
{
  "url": "https://www.mastercodes.co.tz/sms/access#ticket=ONE_TIME_TICKET",
  "expires_in": 60
}
```

The AfricanHub proxy requires authentication, validates an HTTPS Mastercodes portal URL and a positive integer expiry, and returns `Cache-Control: no-store, private`. Request a link when the user clicks **Top up**, open it immediately, and avoid storing or logging the ticket URL. The frontend should open a blank tab synchronously on the click, then navigate it once the backend returns the link, to avoid popup blocking. After payment, refresh the balance when the user returns or clicks **Refresh**.

The regular purchase URL and the one-time portal link are separate mechanisms. The reference records a previous HTTP 404 from the gateway's portal-access route; its current availability has not been verified. If portal access fails, show a clear error and offer the regular purchase page when available. Never expose sender credentials to the browser.

## Verification

Run the mocked gateway checks locally:

```bash
python3 -m unittest discover -s tests -p test_sms_service.py
```

After deployment, intentionally send a real message to a phone you control:

```bash
bash scripts/run_send_test_sms.sh 255700000001 "Mastercodes test from AfricanHub"
```

Replace the example number. Run `bash scripts/troubleshoot_sms.sh` for credential-presence and journal checks. Inspect `sms_logs.api_response_raw` and `error_message` for provider details; do not share message bodies containing passwords. A `sent` row indicates provider acceptance only. No delivery webhook or automatic replay of historical failures is implemented.

The supplied `mastercodes_sms_integration.md` is the reference for the gateway contract; its Laravel frontend routes and deployment commands belong to a separate application.

## Registration and password-reset email

Registration and password reset send the same six-digit temporary password through SMS and email. This temporary login credential is delivered only by SMS and email and is omitted from both API responses. The registration session JWT remains in the response for signing in. Both paths use `auth/services/credential_notifications.py`; email reuses `send_batch_email` from the invitation mailing service with a plain-text body and no attachments.

The existing `MAIL_TRANSPORT` configuration selects SES, SendGrid or SMTP. Set the default sender with `MAIL_FROM` (or the existing `MAIL_SMTP_USER` fallback), because these messages do not supply an invitation-specific source address. No separate email credentials or worker are required; these notifications are sent during the API request.

Both responses expose channel results as `data.sms` and `data.email`, each containing `success` and `message`. A channel failure does not prevent attempting the other channel or undo a committed registration/password reset. Success means provider acceptance; users should check their inbox and spam folder. The frontend should use the channel results when displaying delivery feedback.

## Bulk SMS with named recipients

Submit `POST /api/sms/send-batch` with a shared message and named recipients:

```json
{
  "message": "Dear [NAME], welcome to AfricanHub.",
  "recipients": [
    {"number": "+255712345678", "name": "Hamis"},
    {"number": "+255787654321", "name": "Asha"}
  ]
}
```

The frontend submits JSON containing each recipient’s `number` and `name`, plus the shared message template. No Excel file is required by this API.
The backend replaces every `[NAME]` with the recipient's name before sending and auditing.
A message without `[NAME]` is sent unchanged to everyone. Invalid numbers or missing names
reject the whole request before sending. The legacy per-recipient `{phone, message}` format
remains supported when the shared `message` field is absent.

## SMS audit records and batch references

Each attempted SMS stores the final message text, normalized `recipient` number, optional `recipient_name`, provider response (`api_response_raw`), `error_message`, `status`, `external_id`, sender, creator, timestamp, `message_length` and estimated `sms_count`. The current count is one segment per 160 characters, rounded up with a minimum of one; it is an estimate rather than the provider's final billing count.

New sends record `category` as `single` or `bulk`. Batch, broadcast and custom sends are `bulk`, even when there is only one recipient. Other callers default to `single`. A failed provider attempt is also logged. Database audit write failures are currently logged as warnings and do not undo provider acceptance.

For a single send, include optional `name` alongside `phone` and `message`. For a batch send, include an optional top-level `batch_name` (up to 255 characters):

```json
{
  "batch_name": "November welcome messages",
  "message": "Dear [NAME], welcome to AfricanHub.",
  "recipients": [
    {"number": "+255712345678", "name": "Hamis"},
    {"number": "+255787654321", "name": "Asha"}
  ]
}
```

Each recipient has a separate audit row with the same batch name and their personalized message. Batch names are reference labels, not unique IDs or deduplication keys. Broadcast/custom routes also accept optional `batch_name`. Registration/reset notifications store the user's name when available.

`GET /api/sms/logs` returns `recipient_name`, `category` and `batch_name` alongside the existing fields. Optional `category=single|bulk` and exact `batch_name` filters apply to both rows and SMS-count totals.

### Deploying the audit metadata

Run the migration before restarting the updated application, using the project environment with dependencies installed:

```bash
alembic upgrade head
```

Revision `gg7b8c9d0e1f` adds the three audit fields and category/batch indexes. Known historical registration/reset/direct sends are marked single, and known batch/broadcast/custom sends are marked bulk. Unclassified historical categories remain NULL; historical names and batch labels remain NULL. No historical message or provider response is changed.

## SMS reports endpoint

`GET /api/sms/reports` requires `Authorization: Bearer <access_token>`. The frontend calls AfricanHub, not Mastercodes. Reports read local audit records and do not require a provider request.

Supported optional query parameters:

- `from_date`, `to_date`: inclusive UTC calendar dates in `YYYY-MM-DD`. Either boundary can be supplied alone.
- `batch_name`: exact batch reference.
- `category`: `single` or `bulk`.
- `recipient_name`: partial recipient name.
- `recipient`: partial phone number.
- `status`: `sent` or `failed`.
- `process_name`, `provider`: exact values.
- `page`: positive integer, default 1.
- `per_page`: positive integer, default 20, capped at 100.

Example (URL-encode query values):

```http
GET /api/sms/reports?from_date=2026-11-01&to_date=2026-11-30&category=bulk&batch_name=November%20welcome%20messages&recipient_name=Hamis&page=1&per_page=20
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Response structure:

```json
{
  "status": "success",
  "message": "SMS report retrieved successfully",
  "data": {
    "summary": {
      "total_messages": 2,
      "total_sms_count": 3,
      "sent": 1,
      "failed": 1,
      "unique_recipients": 2,
      "sent_sms_count": 2,
      "failed_sms_count": 1
    },
    "logs": [],
    "pagination": {"total": 2, "page": 1, "per_page": 20, "total_pages": 1}
  }
}
```

`logs` above is abbreviated; actual entries have the same fields as `/api/sms/logs`, including message, recipient, recipient_name, category, batch_name, response and SMS count. Summary totals cover every matching row, independent of pagination. `total_sms_count` includes failed attempts; `sent_sms_count` and `failed_sms_count` separate their segment estimates. `sent` means gateway acceptance, not handset delivery or confirmed billing. Empty matches return zero totals and an empty list. Invalid filters return HTTP 400; unexpected report failures return HTTP 500 with a generic message. Successful responses use `Cache-Control: no-store, private`.

As with the existing logs endpoint, access requires a valid JWT and has no additional role restriction. Audit messages may contain temporary credentials; expose the report only in the appropriate authenticated administration interface.

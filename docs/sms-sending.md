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

Use sender credentials issued by Mastercodes. mShastra credentials are no longer used. Restart the application's Gunicorn service after deploying code and configuring credentials. No schema migration or new dependencies are needed. Existing audit records retain their historical provider values.

## Gateway contract

The service posts to `/send` with `X-Sender-Key` and `X-Sender-Secret` headers and JSON fields `request_id` (UUID), `recipient` (international number with `+`), and `message`. Local Tanzanian numbers get `+255`; explicit international numbers are preserved. `sender` arguments remain audit labels and cannot override the sender selected by the credentials.

Success requires both HTTP 2xx and `data.messages[0].status == "sent"`. This means gateway acceptance, not confirmed handset delivery. Invalid JSON, rejected statuses and missing credentials fail. Connection errors, timeouts and HTTP 5xx get one retry after 200 ms using the same request ID and payload. Connect/read timeouts are 5/10 seconds and redirects are disabled. Manually resending creates a new ID and can duplicate a message whose outcome was uncertain.

Every attempted message writes a `sms_logs` row with provider `mastercodes`, acceptance status, raw response and error. Audit write failures are logged without breaking the send result. Gateway IDs are stored when an `id` or `message_id` is returned. Request logs exclude credentials and message content.

`send_messages` sends individual messages so each recipient retains its own text and audit row. Overall success requires all recipients to succeed; `data` includes `results`, `accepted`, and `failed`. This path does not use the asynchronous bulk gateway endpoint.

Registration still returns HTTP 201 for a created account, with an additional `data.sms` object containing `success` and `message`. A failed SMS does not undo registration. The frontend can show a notification failure using this object.

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

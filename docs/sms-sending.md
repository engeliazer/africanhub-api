# How SMS is sent

Every SMS in this API goes through one public method: `SMSService.send_message` in `public/controllers/sms_controller.py`. Registration, password reset, payment approval, broadcasts, and the HTTP send routes all call it. The method talks to mShastra, then writes a row in `sms_logs`.

Call it from any Python module. Do not post to mShastra yourself.

```python
from public.controllers.sms_controller import SMSService

result = SMSService.send_message(
    phone="0712001002",
    message="Your African Hub code is 482913.",
    process_name="password_reset",
    created_by=42,  # optional user id for the audit log
)

if result["success"]:
    # provider body is in result["data"]["response"]
    pass
else:
    # result["message"] explains the failure
    pass
```

## Method

```python
SMSService.send_message(
    phone: str,
    message: str,
    sender: str | None = None,
    use_last_nine: bool = True,
    process_name: str = "unknown",
    created_by: int | None = None,
) -> dict
```

| Argument | Required | Meaning |
| --- | --- | --- |
| `phone` | Yes | `0712001002`, `712001002`, or `255712001002` |
| `message` | Yes | Text the recipient sees |
| `sender` | No | Sender ID. Empty uses `MSHASTRA_SENDER` |
| `use_last_nine` | No | `True` keeps the last 9 digits and prefixes `255` |
| `process_name` | No | Label stored on `sms_logs`, such as `registration` |
| `created_by` | No | User id stored on `sms_logs` |

### Return value

Success:

```json
{
  "success": true,
  "data": { "response": "[{\"msg_id\":\"...\",\"str_response\":\"Send Successful\"}]" },
  "message": "SMS sent"
}
```

Failure:

```json
{
  "success": false,
  "data": null,
  "message": "Invalid or empty phone number"
}
```

A provider failure uses the same shape, with `message` set to `SMS sending failed: …` and the provider body included. The method does not raise for a bad number or a rejected send. It raises only if logging or the HTTP client hits an unexpected error outside that handling. Callers should branch on `result["success"]`.

## What the method does

1. Read `MSHASTRA_USER`, `MSHASTRA_PWD`, and `MSHASTRA_SENDER` from the environment.
2. Normalize the phone. With `use_last_nine=True` (the default), digits are stripped, the last 9 are kept, and `255` is added. `0712001002` becomes `255712001002`.
3. Reject an empty result and log `status=failed` with `Invalid or empty phone number`.
4. `POST` a one-item JSON array to `MSHASTRA_API_URL`, which defaults to `https://mshastra.com/sendsms_api_json.aspx`:

```json
[
  {
    "user": "AFRICANHUB",
    "pwd": "<MSHASTRA_PWD>",
    "number": "255712001002",
    "msg": "Your African Hub code is 482913.",
    "sender": "AFRICANHUB",
    "language": "English"
  }
]
```

5. Treat HTTP 200 as sent. Read `msg_id` from the JSON body into `sms_logs.external_id`.
6. Insert one `sms_logs` row. A logging failure is swallowed so the send result still returns.

`sms_count` is the billing segment count: 1 segment per 160 characters, rounded up. A message of 161 characters is 2 SMS.

## Several messages at once

`SMSService.send_messages` posts one JSON array for the whole list and logs each recipient.

```python
SMSService.send_messages(
    recipients=[
        {"phone": "0712001002", "message": "Hello Amina"},
        {"phone": "255755344162", "message": "Hello John", "sender": "AFRICANHUB"},
    ],
    process_name="api_send_batch",
    created_by=42,
)
```

Each item needs `phone` (or `number`) and `message` (or `msg`). Items that fail validation are logged as failed and left out of the provider payload. If none are valid, the return is `success: false` and `No valid recipients`.

## HTTP routes

These routes are the HTTP front for the same methods. `sms_bp` is registered in `app.py` with no extra prefix.

| Method | Path | Auth | Calls |
| --- | --- | --- | --- |
| `POST` | `/api/sms/send` | None | `SMSService.send_message` with `process_name=api_send` |
| `POST` | `/api/sms/send-batch` | None | `SMSService.send_messages` with `process_name=api_send_batch` |
| `POST` | `/api/sms/send-broadcast` | Bearer JWT | `send_message` once per user, `process_name=broadcast` |
| `POST` | `/api/sms/send-custom` | Bearer JWT | `send_message` once per recipient, `process_name=custom` |
| `GET` | `/api/sms/logs` | Bearer JWT | Reads `sms_logs` |

### Send one

`POST /api/sms/send`

```json
{
  "phone": "0712001002",
  "message": "Your African Hub code is 482913.",
  "sender": "AFRICANHUB"
}
```

`sender` is optional. Missing `phone` or `message` returns `400`. A provider or number failure also returns `400` with the method's `success: false` body. Success returns `200` and the method body.

### Send a batch

`POST /api/sms/send-batch`

```json
{
  "sender": "AFRICANHUB",
  "recipients": [
    { "phone": "0712001002", "message": "Hello Amina" },
    { "phone": "255755344162", "message": "Hello John" }
  ]
}
```

`recipients` must be an array. `sender` is optional and applies when an item has no sender of its own.

### Broadcast

`POST /api/sms/send-broadcast` requires `Authorization: Bearer <token>`.

```json
{
  "category": "active_subscribers",
  "message": "Hi [SINGLENAME], your materials are open."
}
```

`category` is one of `all_users`, `active_subscribers`, or `inactive_no_application`.

| Category | Who is included |
| --- | --- |
| `all_users` | Users with a phone and `deleted_at` empty |
| `active_subscribers` | Those users who have an active approved application |
| `inactive_no_application` | Those users who have no application row |

`[FULLNAME]` becomes `first last`. `[SINGLENAME]` becomes the first name. Each user is one call to `send_message`. The response counts `sent` and `failed` and lists each result. HTTP status stays `200` when the loop finishes, including when some sends fail.

### Custom recipients

`POST /api/sms/send-custom` requires a bearer token.

```json
{
  "message": "Hi [FULLNAME], class starts Monday.",
  "recipients": [42, "0712001002"]
}
```

A number below one billion is treated as a user id. The user's phone is loaded and the name placeholders are filled. Anything else with digits is treated as a phone, and the message is sent unchanged. Unknown users and users without a phone are counted as failed.

### Logs

`GET /api/sms/logs` requires a bearer token.

| Query | Meaning |
| --- | --- |
| `page` | Default `1` |
| `per_page` | Default `20`, maximum `100` |
| `process_name` | Exact process label |
| `status` | `sent` or `failed` |
| `recipient` | Partial match on the stored number |
| `from_date` | `YYYY-MM-DD`, inclusive start |
| `to_date` | `YYYY-MM-DD`, inclusive end of that day |

## Who already calls `send_message`

| Caller | `process_name` | When |
| --- | --- | --- |
| `POST /api/self-registration` | `registration` | Welcome SMS with the first password |
| `POST /api/api/auth/reset-password` | `password_reset` | New 6-digit password |
| Payment reconciliation approved | `payment_approved` | Applicant is told study materials are open |
| Event letter phone verification | `event_letter_phone_verify` | Verification code |
| Certificate attendance notify | `certificate_attendance_notify` | Attendance thank-you |
| `POST /api/sms/send` | `api_send` | Direct HTTP send |
| `POST /api/sms/send-batch` | `api_send_batch` | Direct HTTP batch |
| `POST /api/sms/send-broadcast` | `broadcast` | Category broadcast |
| `POST /api/sms/send-custom` | `custom` | Chosen users or numbers |

Use a new `process_name` for a new feature so the log can be filtered later.

## Configuration

| Variable | Role | Default |
| --- | --- | --- |
| `MSHASTRA_USER` | Provider profile id | `AFRICANHUB` |
| `MSHASTRA_PWD` | Provider password | empty, and the provider will reject the send |
| `MSHASTRA_SENDER` | Sender ID shown to the recipient | `AFRICANHUB` |
| `MSHASTRA_API_URL` | JSON send URL | `https://mshastra.com/sendsms_api_json.aspx` |

Passwords are masked in the application log. The provider response is logged as `SMS API says: [status=…] …`.

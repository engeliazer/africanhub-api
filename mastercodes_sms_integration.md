Mastercodes SMS integration

This guide describes the implemented backend contract and the frontend workflow. Examples use synthetic recipients and response values. Production availability depends on deployment and Mastercodes route availability.

## Configuration and authentication

Frontend requests go to the HMS API, with production base URL:

```text
https://mastermauzo-api.bwamidubaihotel.com/api
```

All endpoints below require Sanctum authentication:

```http
Authorization: Bearer YOUR_HMS_TOKEN
Accept: application/json
Content-Type: application/json
```

The backend reads these server environment variables through Laravel configuration:

```dotenv
MASTERCODES_SMS_SENDER_KEY=
MASTERCODES_SMS_SENDER_SECRET=
```

The backend sends them to Mastercodes as `X-Sender-Key` and `X-Sender-Secret`. Credentials select the sender automatically. Keep both values on the server. The frontend supplies its HMS token.

The Mastercodes gateway base URL is `https://api.mastercodes.co.tz/api/v1/gateway/sms`. Connections have a five-second connection timeout and ten-second request timeout. Redirects are disabled.

## Sending to database categories

Frontend endpoint:

```http
POST /api/send-sms
```

```json
{
  "message": "Hello [NAME], please keep your password private.",
  "recipient": "staff",
  "created_by": 5
}
```

All three fields are required. The message and category must be strings, and `created_by` must be an integer. Supply the current user's ID.

Supported categories:

- `staff` selects users whose status equals the string `'1'`, excluding user ID 1. The current query spans the users table across stores and subscribers.
- `all-customers` selects every customer.
- `accommodation-customers` selects customers referenced in `leases`.
- `chocha-special` selects rows in `temp_special_sms` whose phone value has at least nine characters.

The backend creates a campaign record with its reference, message, category, selected row count, creator, and estimated segments. It substitutes `[NAME]` with each recipient's name, converted to title case, and sends sequential individual requests through Mastercodes' `POST /send` endpoint. The campaign recipient count measures selected records. Shared phone numbers can receive multiple messages.

The string status comparison matters for this database. Production diagnostics showed numeric comparison matched 63 records while string comparison matched 21, excluding system user ID 1.

A completed campaign response uses HTTP 200:

```json
{
  "success": true,
  "data": {
    "status": 101,
    "message": "SMS accepted by provider for 21 of 21 recipients"
  },
  "message": "Success",
  "status": 100
}
```

Frontend campaign handling must inspect `data.status` and `data.message`:

- `101` means every selected record was accepted and the selected count was greater than zero.
- `105` means at least one record failed or the category selected zero records.
- `102` means validation failed or the category was invalid.
- `0` means the campaign record could not be saved.

These handled campaign results all use HTTP 200 and the outer `success: true` envelope. An unhandled server exception can still produce an HTTP error. Campaign logs do not provide a per-recipient delivery history.

## Individual SMS behavior

Internal callers use `SMSService::sendMessage(phone, message)`, which delegates to `SMSSender::sendSms`. Booking welcome and checkout messages and password messages use this path.

The backend normalizes local Tanzanian numbers to `+255...`, preserves explicitly international destinations, and validates the normalized format. It submits:

```json
{
  "request_id": "GENERATED_UUID",
  "recipient": "+255700000001",
  "message": "Your message"
}
```

A successful HTTP response counts as accepted only when `data.messages[0].status` is `sent`. The internal returned array includes a calculated `successful` boolean. Gateway acceptance does not confirm handset delivery.

There is currently no dedicated frontend endpoint accepting an arbitrary single phone number and message. The category endpoint sends individual gateway requests, and the bulk endpoint accepts a one-element recipients array if needed.

## Bulk SMS from frontend Excel extraction

Frontend endpoint:

```http
POST /api/send-sms/bulk
```

The frontend reads the spreadsheet and builds a JSON recipients array. Submit the extracted data:

```json
{
  "request_id": "school-notices-001",
  "batch_name": "School notices",
  "message_template": "Hello [NAME], registration opens on Monday.",
  "recipients": [
    { "number": "255700000001", "name": "Jane" },
    { "number": "255700000002", "name": "John" }
  ]
}
```

Validation requires:

- String `request_id`, `batch_name`, and `message_template` fields.
- A nonempty sequential `recipients` array.
- Each recipient object contains only `number` and `name`, both required strings.
- Numbers contain 8–15 digits, start with a nonzero digit, and include the country code. Convert spreadsheet numeric cells to strings and remove formatting before submission.

The backend forwards this payload to Mastercodes `POST /send/bulk`. Mastercodes handles template substitution and queues the batch. The backend passes through gateway batch data under `data`; individual batch fields depend on the provider response.

HTTP 202 response envelope:

```json
{
  "success": true,
  "message": "Bulk SMS batch accepted for processing",
  "data": {}
}
```

Here `data` represents the actual batch object returned by Mastercodes. Show a queued/accepted state in the frontend. Delivery requires later provider status information.

Local validation errors use Laravel's HTTP 422 response:

```json
{
  "message": "The recipients.0.number field format is invalid.",
  "errors": {
    "recipients.0.number": ["The recipients.0.number field format is invalid."]
  }
}
```

Exact validation wording can vary. Display field errors from the top-level `errors` object.

Mastercodes HTTP 409 or 422 rejection responses preserve that HTTP status. The backend appends a supplied provider message and includes provider validation details when available:

```json
{
  "success": false,
  "message": "Mastercodes rejected the bulk SMS submission. Invalid recipients.",
  "data": {
    "errors": {
      "recipients.0.number": ["Number is invalid."]
    }
  }
}
```

A missing provider reason produces the generic rejection message. Empty provider errors omit `data`.

Missing credentials, connection failures, other unsuccessful provider responses, or invalid/empty successful JSON responses produce HTTP 502:

```json
{
  "success": false,
  "message": "Could not confirm the bulk SMS submission. Retry with the same request ID and payload."
}
```

Preserve the request ID and entire payload until the outcome is known. A timeout may occur after the provider accepted the batch. Retry the identical request using the original ID. Generate a new ID for each intentionally new batch.

Both individual and bulk gateway sends allow two total attempts with a 200 ms delay for connection errors or HTTP 5xx responses. Each retry preserves the original payload and request ID. Submitting the category endpoint again creates a new campaign and new individual IDs, which can send duplicates.

## Balance check

Frontend endpoint:

```http
GET /api/sms/sms-balance
```

The backend calls Mastercodes `GET /balance` and wraps the returned `data`:

```json
{
  "success": true,
  "data": {
    "sender_id_registration_id": 7,
    "available_units": 1500,
    "reserved_units": 0,
    "sender_name": "JANETRADING",
    "service_provider": "MASTERCODES",
    "top_up_url": "https://mastercodes.co.tz/account/home/sms?tab=purchase"
  },
  "message": "SMS balance retrieved",
  "status": 100
}
```

Display `data.available_units` as available SMS units, and optionally show `reserved_units` and `sender_name`. Zero available units is a valid successful response.

A failed balance lookup returns HTTP 502:

```json
{
  "success": false,
  "message": "Unable to retrieve SMS balance"
}
```

## Top-up portal access

Frontend endpoint, with no request body required:

```http
POST /api/sms/portal-access
```

The backend calls Mastercodes `POST /portal-access` with server credentials. It validates the HTTPS URL and positive integer expiry before returning HTTP 200:

```json
{
  "success": true,
  "data": {
    "url": "https://www.mastercodes.co.tz/sms/access#ticket=ONE_TIME_TICKET",
    "expires_in": 60
  },
  "message": "Mastercodes portal access granted",
  "status": 100
}
```

Responses include `Cache-Control: no-store, private`. Request a ticket when the user clicks Top up and open the supplied URL immediately in a new tab. Avoid retaining ticket URLs in application storage or logs.

Example using an Axios client whose base URL ends in `/api` and whose authorization header is configured:

```js
async function openMastercodesPortal() {
  const tab = window.open("about:blank", "_blank");
  if (!tab) throw new Error("Allow popups to open Mastercodes.");
  tab.opener = null;

  try {
    const response = await api.post("/sms/portal-access");
    tab.location.replace(response.data.data.url);
  } catch (error) {
    tab.close();
    throw error;
  }
}
```

Opening the blank tab synchronously from the click handler helps avoid popup blocking. Display an API error if the request fails. The user completes payment in Mastercodes. Refresh balance when they return or click Refresh.

The balance response also supplies a regular `top_up_url`. This is a separate account purchase page; authenticated portal access uses the one-time ticket URL.

Portal failures return HTTP 502:

```json
{
  "success": false,
  "message": "Unable to request Mastercodes portal access"
}
```

During prior live checks, Mastercodes returned HTTP 404 for its portal-access route. This external dependency must be active for the ticket workflow to succeed. That observation has not been reverified for this guide.

## Frontend response handling and current limits

Use the HTTP status first, then the operation-specific response fields described above. Sanctum rejects unauthenticated JSON requests with HTTP 401. HTTP 404 for an HMS route indicates a deployment, URL, or route registration issue. HTTP 502 from these controllers indicates the upstream operation could not be confirmed.

With Axios, the JSON body is `response.data`, so provider data is `response.data.data`. API rejection details are usually in `error.response.data`. Campaign HTTP 200 failures require inspecting `response.data.data.status`.

The current backend has these operational limits:

- Mastercodes documents `GET /batches/{batch}`, but this application currently exposes no batch-status proxy or delivery webhook.
- Bulk submissions have no local campaign record or per-recipient log in this controller. Retain returned batch information in the frontend as needed.
- Recipients are sent as supplied for bulk requests. Duplicate phone numbers are retained.
- Category campaign segment estimates use PHP byte length, with 160 bytes for a single segment and 153 bytes per concatenated segment. Unicode encoding and personalization can change actual provider billing.
- Existing route protection requires authentication. These SMS controllers add no role-specific authorization.
- Sender credentials are configured globally for this backend deployment.

## Deployment and troubleshooting

After deploying the relevant commits and installing locked dependencies, rebuild Laravel configuration and routes using the server's PHP-FPM account. On the production server previously used in this project:

```bash
cd /var/www/mastermauzo-api.bwamihotel.com
sudo -u www-data php artisan config:cache
sudo -u www-data php artisan route:cache
sudo -u www-data php artisan route:list --path=sms -v
```

Use the actual PHP-FPM account if it differs. Ensure that account can write `storage` and `bootstrap/cache`. Environment changes require refreshing Laravel configuration. Verify both the HMS route and the matching Mastercodes route when troubleshooting a 404.
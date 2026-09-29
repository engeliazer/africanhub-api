LMS Integration Guide — For Source Systems

This is for developers on a source system (the platform that owns your users, payments, and enrollments) integrating with the Library Management System (LMS) API to give your users access to books.

Division of responsibility, so this doesn't get confused later:

Your system owns: user identity, login, payment, enrollment/entitlement logic.
The LMS owns: the book catalog, secure storage, and controlled, watermarked, rate-limited delivery of book pages.
The LMS trusts your system completely once you're authenticated — it does not re-check payment or enrollment. If you call POST /access-tokens, the LMS assumes you've already decided this user should have access. Getting that decision right is entirely on your side.
0. Prerequisites

An LMS admin registers your system and gives you a client_id and client_secret once — there is no way to retrieve the secret again if lost, only to have it rotated by an admin. Store it in your secrets manager, not in code or logs.

1. Authenticate your system
POST /oauth/token
Content-Type: application/json

{
  "grant_type": "client_credentials",
  "client_id": "...",
  "client_secret": "..."
}

Returns a system JWT — short-lived (currently 15 min). Cache it and re-authenticate before it expires rather than calling this on every request; every other endpoint below (except this one) requires it as Authorization: Bearer <system-jwt>.

2. List books available to issue
GET /books?published_only=true
Authorization: Bearer <system-jwt>

Returns the catalog of books currently published (i.e. eligible to grant). Use this to populate your own product/catalog UI, or just to validate a book_id before granting. Books not in this list — drafts, still processing, or unpublished — cannot be granted; attempting to will 409.

3. Run your own internal controls

Before granting anything: confirm the user paid, is enrolled, has an active subscription — whatever your business logic requires. This step happens entirely on your side. The LMS has no visibility into it and doesn't need to.

4. Grant access (the main call)

Once your controls pass, request a content token on the user's behalf:

POST /access-tokens
Authorization: Bearer <system-jwt>
Content-Type: application/json

{
  "user_id": "user-123",
  "user_email": "reader@example.com",
  "book_id": 6,
  "ttl_seconds": 1800
}
user_id — your own internal user identifier. The LMS never learns anything else about this user, so this can be an opaque ID rather than anything identifying.
user_email — optional, but recommended: it's burned into the page watermark, which matters if you ever need to trace a leaked page back to who accessed it.
ttl_seconds — how long the returned token is valid. Pick this to match your actual reading session length, not the length of the user's entitlement — see the TTL note below.

Response — this is what you hand to the user's client, unmodified:

json
{
  "success": true,
  "data": {
    "access_token": "<content-jwt>",
    "token_type": "bearer",
    "expires_in": 1800,
    "expires_at": "2026-08-18T12:00:00Z",
    "grant": {
      "id": 42,
      "user_id": "user-123",
      "user_email": "reader@example.com",
      "book_id": 6,
      "book_title": "Advanced Excel",
      "status": "active",
      "issued_at": "...",
      "expires_at": "..."
    },
    "reader": {
      "book_id": 6,
      "cover_url": "/books/6/cover",
      "first_page_url": "/books/6/pages/1",
      "search_url": "/books/6/search"
    }
  }
}

Error cases to handle:

409 — book isn't published. Don't show this raw to the user; treat it as "this book isn't available right now" in your UI, and alert yourselves — it usually means a catalog sync issue on your side (offering a book the LMS has since unpublished).
401 — your system JWT expired or is invalid. Re-authenticate via Step 1 and retry once.
5. Hand the content token to the user's client

Your user's app/browser uses access_token from the grant response as Authorization: Bearer <content-jwt> on every subsequent call directly to the LMS:

GET /books/6/pages/1
Authorization: Bearer <content-jwt>

and similarly for /render and /search variants, and the reader.* URLs from the grant response. Your backend does not proxy these calls — the content token lets the user's client talk to the LMS directly, so book pages never pass through your servers. Treat the content token as a bearer credential: don't log it, don't put it in a URL query string, don't store it longer than the session needs it.

6. Avoid re-issuing unnecessarily

Before granting, you can check whether the user already has active access:

GET /access-tokens/status?user_id=user-123&book_id=6
Authorization: Bearer <system-jwt>

Returns has_access: true/false and the grant's status (active, expired, revoked). Useful on session resume — don't blindly re-call POST /access-tokens every time a user opens a book if they were already reading it five minutes ago.

That said, re-calling the grant endpoint for the same user_id + book_id is safe either way: if an active token still has more than 2 minutes left, the LMS reuses it instead of issuing a new one. This is a race-avoidance measure, not a caching convenience — don't rely on it as your only access check for high-frequency calls, use the status endpoint above for that.

7. List or inspect grants
GET /access-tokens?user_id=user-123&book_id=6      # list, filterable
GET /access-tokens/{id}                              # single grant detail
Authorization: Bearer <system-jwt>

Useful for your own support tooling — "does this user currently have access to this book, and when was it granted."

8. Revoke access

When a subscription ends, a refund happens, or you otherwise need to cut off access immediately:

DELETE /access-tokens/active?user_id=user-123&book_id=6
Authorization: Bearer <system-jwt>

or, if you already have the grant ID from Step 4 or 7:

DELETE /access-tokens/{id}
Authorization: Bearer <system-jwt>

Revocation is near-immediate — the next content-page request with that token will 401, even if the token's expires_at hasn't been reached yet.

Choosing ttl_seconds

This is a session length, not an entitlement length. Even if the user paid for a year-long subscription, don't issue a token valid for a year — issue one valid for a reading session (e.g. 30–60 minutes), and re-grant (or rely on token reuse, Step 6) as they keep reading. Keeping this short limits how much damage a leaked token can do, independent of how long the user is actually entitled to the book.

Integration checklist
 client_id/client_secret stored in a secrets manager, not in code
 System JWT cached and refreshed before expiry, not fetched per-request
 Your own payment/enrollment checks run before every POST /access-tokens call
 user_email passed when available, for watermark traceability
 ttl_seconds set to a reading-session length, not an entitlement length
 Content token passed straight through to the user's client — never logged, never proxied through your backend
 DELETE /access-tokens/active wired into your subscription-cancellation / refund flow, not left as a manual step
 409 from POST /access-tokens handled gracefully in your UI, and monitored — it signals a catalog mismatch between your system and the LMS
# Books & Book Store — Frontend Integration Guide

**Short web guide (catalog, covers, reader):** [`BooksWeb.md`](BooksWeb.md).

This document describes how the frontend should integrate with the African Hub API for:

1. **Library / reading** — LMS catalog, access tokens, in-app reader (course-linked entitlement).
2. **Book store / sales** — listed editions, pricing, checkout orders, purchase history.

The API is the single integration point. The frontend must **not** call the LMS directly for OAuth or system credentials. After a reading grant, the browser **may** call the LMS directly using the **content JWT** returned by this API.

---

## Base URL & authentication

| Item | Value |
|------|--------|
| API base | Your deployed API origin (e.g. `https://africanhub-api.africanhub.ac.tz`) |
| Path prefix | `/api` |
| Auth header | `Authorization: Bearer <user_jwt>` where required |
| Content-Type | `application/json` |

### Standard JSON envelope

Most endpoints return:

```json
{
  "status": "success",
  "data": { }
}
```

Errors:

```json
{
  "status": "error",
  "message": "Human-readable reason",
  "details": "Optional extra detail",
  "code": "Optional machine code e.g. book_unpublished"
}
```

| HTTP code | Typical meaning |
|-----------|-----------------|
| `200` | OK |
| `201` | Created |
| `400` | Validation / bad request |
| `403` | Not entitled / not admin |
| `404` | Not found |
| `409` | Conflict (already listed, unpublished book, etc.) |
| `502` / `503` | LMS unavailable or misconfigured |

### Roles

| Role codes | Access |
|------------|--------|
| `SYSADMIN`, `SUPADM` | Admin book links, sales pricing, listings, all orders |
| Authenticated student | Own books, reading, store checkout, own orders |
| Anonymous | Public store catalog (`GET /api/public/store/books`; no JWT) |

---

## Architecture (what the frontend owns)

```text
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
├─────────────────────────────────────────────────────────────┤
│  Store UI          │  My Library / Reader                   │
│  - merge store +   │  - grant access via API                │
│    LMS metadata    │  - call LMS pages with content JWT     │
│  - server price    │  - never log or persist content JWT    │
│  - create order    │    in localStorage longer than session │
└──────────┬───────────────────────────────┬──────────────────┘
           │ Bearer: user JWT               │ Bearer: user JWT (grant)
           ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   African Hub API                            │
│  /api/books*          reading + LMS catalog proxy            │
│  /api/store/*         sales listings & customer price        │
│  /api/book-editions/* admin pricing & listing                │
│  /api/orders          book orders                            │
└─────────────────────────────────────────────────────────────┘
```

**Important identifiers**

| Context | ID type | Example |
|---------|---------|---------|
| LMS reading access | Numeric LMS `book_id` | `6` |
| Book store / sales | String edition reference | `ED-000125-02` |
| Parent book (orders, history) | String book reference | `BK-000125` |

Do not assume one ID format works for both reading and store flows.

---

# Part A — Library & reading (LMS)

Use these for **course-linked reading** (paid enrollment on a linked subject) and **opening the reader**.

### A.1 List LMS catalog (authenticated)

```http
GET /api/books?published_only=true
Authorization: Bearer <user_jwt>
```

Query:

| Param | Default | Description |
|-------|---------|-------------|
| `published_only` | `true` | When `false`, includes unpublished (admin-style catalog) |

**Response `200`**

```json
{
  "status": "success",
  "data": [
    {
      "id": 6,
      "title": "Advanced Excel",
      "author": "...",
      "description": "...",
      "cover_url": "...",
      "subject_id": 12,
      "subject_name": "Financial Reporting",
      "is_linked": true
    }
  ]
}
```

Fields merged by the API:

| Field | Notes |
|-------|--------|
| `id` | LMS book id (use for `/api/books/{id}/access`) |
| `subject_id`, `subject_name`, `is_linked` | Present when admin linked book → subject for entitlement |

Additional keys from the LMS may appear on each object; treat them as opaque presentation fields.

### A.2 Books the user may read (entitlement filter)

```http
GET /api/books/my
Authorization: Bearer <user_jwt>
```

Same item shape as **A.1**, but only books the user is allowed to open (paid enrollment on linked subject). Admins receive the full published catalog.

### A.3 Open reading session (content token)

Before opening the reader, prefer checking existing access (**A.4**). If no active session, request a grant:

```http
POST /api/books/{book_id}/access
Authorization: Bearer <user_jwt>
Content-Type: application/json
```

`book_id` is the **numeric** LMS book id.

**Request body (optional)**

```json
{
  "ttl_seconds": 1800
}
```

| Field | Rules |
|-------|--------|
| `ttl_seconds` | Optional, 300–7200. Reading **session** length, not subscription length. Default ~30 min server-side. |

**Response `200`**

```json
{
  "status": "success",
  "data": {
    "access_token": "<content-jwt>",
    "token_type": "bearer",
    "expires_in": 1800,
    "expires_at": "2026-09-30T14:30:00Z",
    "grant": {
      "id": 42,
      "user_id": "123",
      "user_email": "reader@example.com",
      "book_id": 6,
      "book_title": "Advanced Excel",
      "status": "active",
      "issued_at": "...",
      "expires_at": "..."
    },
    "reader": {
      "book_id": 6,
      "cover_url": "https://lms.example.com/books/6/cover",
      "first_page_url": "https://lms.example.com/books/6/pages/1",
      "search_url": "https://lms.example.com/books/6/search"
    },
    "lms_base_url": "https://lms.example.com"
  }
}
```

**Frontend reader responsibilities**

1. Pass `access_token` as `Authorization: Bearer <content-jwt>` on **direct** LMS requests (pages, search, render).
2. Do **not** send book page requests through the African Hub API.
3. Do **not** log the token, put it in query strings, or store it longer than the session.
4. Use absolute URLs from `reader.*` or prefix paths with `lms_base_url`.

**Errors**

| Status | `message` / `code` | UI action |
|--------|-------------------|-----------|
| `403` | Enrollment / link message | Show “not included in your course” |
| `409` | `book_unpublished`, code `book_unpublished` | “This book isn’t available right now” (not raw 409) |
| `503` | LMS not configured | Maintenance message |

### A.4 Check existing reading access

```http
GET /api/books/{book_id}/access/status
Authorization: Bearer <user_jwt>
```

Use on reader resume to avoid unnecessary `POST /access` calls.

**Response `200`** — shape follows LMS; typically includes whether the user `has_access` and grant status (`active`, `expired`, `revoked`).

### A.5 Revoke reading access (admin or self)

```http
DELETE /api/books/{book_id}/access
Authorization: Bearer <user_jwt>
```

Admins may pass `?user_id=<id>` to revoke another user.

### A.6 Grant audit log (support)

```http
GET /api/books/access/grants?book_id=6
Authorization: Bearer <user_jwt>
```

Admins may add `user_id`. Students see only their own grants.

---

# Part B — Book store (sales)

Store flows use **edition reference ids** (UUIDs from LMS). `GET /api/store/books` merges **commercial** fields with LMS **title, cover, author**, and nested `book` / `edition` objects when the LMS is reachable.

### B.1 Public store catalog (listed editions + list prices)

**Visitors (recommended for landing pages):**

```http
GET /api/public/store/books
GET /api/public/store/books/{editionReferenceId}
```

No auth; JWT is not read (always guest catalog).

**Logged-in store (optional JWT on same response shape):**

```http
GET /api/store/books
GET /api/store/books/{editionReferenceId}
```

**Response `200`**

```json
{
  "status": "success",
  "data": [
    {
      "edition_reference_id": "bca85208-74ba-49e1-8c0e-9fa75e9a09de",
      "new_buyer_price": 70000,
      "previous_buyer_price": 45000,
      "currency": "TZS",
      "status": "LISTED",
      "book_reference_id": "book-uuid",
      "title": "Advanced Excel",
      "author": "Jane Author",
      "cover_url": "https://lms-api.example.com/books/.../cover",
      "edition_label": "2025 Edition",
      "book": { },
      "edition": { }
    }
  ]
}
```

| Field | Notes |
|-------|--------|
| `title`, `author`, `cover_url`, `edition_label` | Convenience fields from LMS for store cards |
| `book`, `edition` | Full LMS payloads when catalog sync succeeds; may be `null` if LMS is down |

**Optional auth:** Send `Authorization: Bearer <user_jwt>` on the same request to get per-user fields (one round trip for the store grid).

| Field | Logged in | Guest |
|-------|-----------|--------|
| `user_owns_edition` | `true` if this **edition** is already purchased | `null` |
| `already_purchased` | Alias of `user_owns_edition` | `null` |
| `can_purchase` | `false` when owned, else `true` | `null` |
| `store_presentation` | `OWNED` \| `BUY` \| `BUY_RETURNING` | `GUEST` |
| `your_price` | Checkout price, or `null` if owned | `null` |

List responses also include `meta.authenticated`, `meta.store_edition_policy`, and `meta.user_owned_edition_ids` when logged in.

**Edition visibility (server-filtered):** For each book, guests and new buyers only receive the **current** listed edition; returning buyers receive **owned edition(s) + current**. Rows include `is_current_edition` and `edition_display_role` (`CURRENT`, `OWNED`, `OWNED_CURRENT`).

**Frontend:** Branch on `store_presentation` or `user_owns_edition`. When `OWNED`, link to My Books; do not show Buy. Checkout can still call **B.3** to re-verify before order create.

### B.2 Store edition detail

```http
GET /api/store/books/{editionReferenceId}
```

Example: `GET /api/store/books/ED-000125-02`

**Response `200`**

```json
{
  "status": "success",
  "data": {
    "edition_reference_id": "ED-000125-02",
    "new_buyer_price": 70000,
    "previous_buyer_price": 45000,
    "currency": "TZS",
    "status": "LISTED",
    "edition": { }
  }
}
```

`edition` is optional LMS payload when the backend can fetch it; may be `null`. Prefer your existing edition API for rich UI when available.

### B.3 Customer-specific price (required for checkout display)

The frontend **must not** decide new vs previous buyer price. Always ask the server:

```http
GET /api/store/books/{editionReferenceId}/price
Authorization: Bearer <user_jwt>
```

**Response `200` — new buyer**

```json
{
  "status": "success",
  "data": {
    "edition_reference_id": "ED-000125-02",
    "customer_type": "NEW_BUYER",
    "price": 70000,
    "currency": "TZS"
  }
}
```

**Response `200` — previous buyer** (any prior **completed** purchase of another edition of the same book)

```json
{
  "status": "success",
  "data": {
    "edition_reference_id": "ED-000125-02",
    "customer_type": "PREVIOUS_BUYER",
    "price": 45000,
    "currency": "TZS"
  }
}
```

Show `customer_type` in UI if helpful (“Returning reader discount”).

### B.4 Create book order

After payment UI collects confirmation, create the order (payment gateway wiring may complete the order separately):

```http
POST /api/orders
Authorization: Bearer <user_jwt>
Content-Type: application/json
```

**Request**

```json
{
  "items": [
    {
      "edition_reference_id": "ED-000125-02",
      "quantity": 1
    }
  ]
}
```

| Field | Rules |
|-------|--------|
| `edition_reference_id` | Must be `LISTED` with active price |
| `quantity` | Integer ≥ 1 |

Prices on the order are computed **server-side** and stored on line items (do not send `unit_price` from the client).

**Response `201`**

```json
{
  "status": "success",
  "data": {
    "id": 15,
    "order_number": "BO-20260930-A1B2C3D4",
    "status": "pending",
    "total_amount": 45000,
    "currency": "TZS",
    "created_at": "2026-09-30T12:00:00",
    "completed_at": null,
    "items": [
      {
        "book_reference_id": "BK-000125",
        "edition_reference_id": "ED-000125-02",
        "quantity": 1,
        "unit_price": 45000,
        "total_price": 45000
      }
    ]
  }
}
```

Order statuses: `pending`, `completed`, `cancelled`, `failed`. Only `completed` orders count for previous-buyer pricing and purchase history.

### B.5 List / get orders

```http
GET /api/orders
Authorization: Bearer <user_jwt>
```

Admins: optional `?user_id=123`.

```http
GET /api/orders/{orderId}
Authorization: Bearer <user_jwt>
```

### B.6 Purchase history

```http
GET /api/purchases
Authorization: Bearer <user_jwt>
```

Returns flattened line items from **completed** orders only.

**Response `200`**

```json
{
  "status": "success",
  "data": [
    {
      "order_id": 15,
      "order_number": "BO-20260930-A1B2C3D4",
      "book_reference_id": "BK-000125",
      "edition_reference_id": "ED-000125-02",
      "quantity": 1,
      "unit_price": 45000,
      "total_price": 45000,
      "currency": "TZS",
      "completed_at": "2026-09-30T12:05:00"
    }
  ]
}
```

---

# Part C — Admin (sales management)

Requires `SYSADMIN` or `SUPADM`.

### C.1 Set edition price (creates new price version)

```http
POST /api/book-editions/{editionReferenceId}/price
Authorization: Bearer <admin_jwt>
Content-Type: application/json
```

**Request**

```json
{
  "new_buyer_price": 70000,
  "previous_buyer_price": 45000,
  "currency": "TZS"
}
```

**Response `201`**

```json
{
  "status": "success",
  "data": {
    "edition_reference_id": "ED-000125-02",
    "new_buyer_price": 70000,
    "previous_buyer_price": 45000,
    "currency": "TZS",
    "status": "ACTIVE",
    "effective_from": "2026-09-30T12:00:00",
    "effective_to": null
  }
}
```

Updating price always adds a new active row and closes the previous one (historical orders keep old `unit_price`).

### C.2 Get active edition price

```http
GET /api/book-editions/{editionReferenceId}/price
Authorization: Bearer <admin_jwt>
```

### C.3 List edition for sale

Validates: edition exists in LMS, is published, has active price, not already listed.

```http
POST /api/book-editions/{editionReferenceId}/listing
Authorization: Bearer <admin_jwt>
```

**Response `201`**

```json
{
  "status": "success",
  "data": {
    "edition_reference_id": "ED-000125-02",
    "status": "LISTED",
    "listed_at": "2026-09-30T15:30:00",
    "unlisted_at": null
  }
}
```

### C.4 Unlist edition

```http
DELETE /api/book-editions/{editionReferenceId}/listing
Authorization: Bearer <admin_jwt>
```

or

```http
PATCH /api/book-editions/{editionReferenceId}/listing
Authorization: Bearer <admin_jwt>
Content-Type: application/json
```

```json
{
  "status": "UNLISTED"
}
```

### C.5 Manage all listings

```http
GET /api/listings?status=LISTED
Authorization: Bearer <admin_jwt>
```

```http
PATCH /api/listings/{listingId}
DELETE /api/listings/{listingId}
Authorization: Bearer <admin_jwt>
```

**PATCH body**

```json
{
  "status": "LISTED"
}
```

or

```json
{
  "status": "UNLISTED"
}
```

### C.6 Complete order (until payment webhooks are wired)

After successful payment, backend/admin marks order completed (enables previous-buyer pricing):

```http
PATCH /api/orders/{orderId}
Authorization: Bearer <admin_jwt>
Content-Type: application/json
```

```json
{
  "status": "completed"
}
```

Production: replace manual step with payment confirmation callback.

---

# Part D — Admin (course-linked reading)

Link LMS books to **subjects** so paid enrollments unlock reading via **A.3**.

### D.1 List links

```http
GET /api/books/links
Authorization: Bearer <admin_jwt>
```

### D.2 Create link

```http
POST /api/books/links
Authorization: Bearer <admin_jwt>
Content-Type: application/json
```

```json
{
  "lms_book_id": 6,
  "subject_id": 12,
  "title": "Advanced Excel",
  "description": "Optional note for admins"
}
```

### D.3 Update / delete link

```http
PUT /api/books/links/{linkId}
DELETE /api/books/links/{linkId}
Authorization: Bearer <admin_jwt>
```

---

# Recommended user flows

### Store browse → checkout

1. Visitors: `GET /api/public/store/books` (or logged-in: `GET /api/store/books` with JWT)
2. Load edition/book metadata from existing LMS catalog UI data layer (keyed by `edition_reference_id` / book reference).
3. On product page (logged in): `GET /api/store/books/{editionRef}/price` → show `price` and `customer_type`.
4. `POST /api/orders` with selected editions.
5. Run existing payment flow; on success ensure order becomes `completed` (API or admin PATCH until automated).
6. Optional: grant reading via store purchase flow when product rules require it (future payment hook).

### Course library → reader

1. `GET /api/books/my`
2. User selects book → `GET /api/books/{id}/access/status`
3. If no active access → `POST /api/books/{id}/access`
4. Open reader with `access_token` against LMS URLs from `data.reader`

### Admin: put an edition on sale

1. Confirm edition in LMS catalog (existing screens).
2. `POST /api/book-editions/{editionRef}/price`
3. `POST /api/book-editions/{editionRef}/listing`
4. Verify `GET /api/store/books` includes the edition.

---

# Frontend checklist

- [ ] Use **user JWT** for all `/api/*` calls except public `GET /api/public/store/books` (and edition cover proxy when listed).
- [ ] Use **numeric `book_id`** for reading; **string `edition_reference_id`** for store.
- [ ] Never compute new vs previous buyer price in the client — use `GET .../price`.
- [ ] Never expose or log LMS **content** JWT from reading grants.
- [ ] Merge store API rows with LMS metadata for display.
- [ ] Handle `409` / `book_unpublished` with friendly copy on reading grant.
- [ ] On reader reopen, call access **status** before re-granting.
- [ ] Show order `unit_price` from order response/history, not current catalog price.

---

# Health

```http
GET /api/health/lms
```

No auth. Use for admin diagnostics only.

```json
{
  "status": "healthy",
  "lms_api": "reachable",
  "response_time_ms": 120.5
}
```

---

# Related backend docs

| File | Purpose |
|------|---------|
| `books.md` | LMS source-system integration (tokens, TTL, revocation) |
| `booklisting.md` | Sales module specification (pricing, listings, orders) |
| `purchasingBooks.md` | Backend purchase specification |
| [`BookPurchaseFrontend.md`](BookPurchaseFrontend.md) | **User purchase flow (store → pay → My Books → reader)** |

---

# Part E — Purchase & paid access

**Full frontend guide:** [`BookPurchaseFrontend.md`](BookPurchaseFrontend.md) (recommended for checkout, payment, and My Books UI).

Summary below; keep in sync with that file.

**Rule:** Submitting payment does **not** grant access. Only **admin approval** does.

### E.1 Create order (multi-edition)

```http
POST /api/book-orders
Authorization: Bearer <user_jwt>
Content-Type: application/json
```

```json
{
  "edition_reference_ids": [
    "bca85208-74ba-49e1-8c0e-9fa75e9a09de",
    "another-edition-uuid"
  ]
}
```

Already-owned editions are **skipped** (returned in `skipped_already_owned`). Server calculates each `unit_price`.

Status: `PENDING_PAYMENT`.

### E.2 Submit payment (reference + provider — same as applications)

Load providers from the same endpoint used for course applications:

```http
GET /api/accounting/payment-methods
Authorization: Bearer <user_jwt>
```

```http
POST /api/book-orders/{orderId}/payment
Authorization: Bearer <user_jwt>
Content-Type: application/json
```

```json
{
  "service_provider_id": 2,
  "payment_reference": "OCPA-WBDRJSN4-20250404222213",
  "mobile_number": "255755344162",
  "amount": 125000
}
```

| Field | Required |
|-------|----------|
| `service_provider_id` | Yes (or legacy `payment_method_id` / `payment_method` string) |
| `payment_reference` | Yes (`bank_reference` or `reference` accepted as aliases) |
| `mobile_number` | Yes |
| `amount` | Optional (defaults to order total; must match) |

No receipt upload. Reference is stored on `payments.bank_reference` for admin reconciliation.

Creates a row in existing `payments` with `pending_payment`. Order → `PAYMENT_SUBMITTED`.

### E.3 Admin approve / reject

```http
POST /api/book-orders/payments/{paymentId}/approve
POST /api/book-orders/payments/{paymentId}/reject
Authorization: Bearer <admin_jwt>
```

Reject body (optional): `{ "reason": "..." }`.

On **approve**: payment → `paid`, order → `PAID`, entitlements created.

### E.4 My Books (paid editions only)

```http
GET /api/my/books
GET /api/my/paid-editions
GET /api/my/paid-editions/{editionReferenceId}
```

Response merges purchase data + LMS `book` / `edition` metadata.

### E.5 Open reader (purchased edition)

```http
POST /api/my/paid-editions/{editionReferenceId}/access
Authorization: Bearer <user_jwt>
```

Optional body: `{ "ttl_seconds": 1800 }`.

Returns LMS **content JWT** + `reader` URLs (same pattern as Part A.3). Use token directly against LMS — do not proxy through this API.

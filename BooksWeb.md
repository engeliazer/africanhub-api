# Books on the web — access & display

Short guide for the **public site and logged-in app**: which API to call, what to show, and how reading works.

**More detail:** [`BookPurchaseFrontend.md`](BookPurchaseFrontend.md) (checkout, payment, orders) · [`BooksFrontend.md`](BooksFrontend.md) (admin, full field reference)

---

## Setup

| Item | Value |
|------|--------|
| API | `https://africanhub-api.africanhub.ac.tz` (or your env) + prefix `/api` |
| Hub auth header | `Authorization: Bearer <login_jwt>` from `POST /api/auth/login` |
| JSON envelope | Success: `{ "status": "success", "data": … }` · Error: `{ "status": "error", "message": "…" }` |

**Edition id:** use `edition_reference_id` (LMS version UUID) everywhere in the store, cart, orders, reader, and covers — not the parent book UUID.

---

## 1. Show the book catalog

### Visitors (no account)

No `Authorization` header.

```http
GET /api/public/store/books
GET /api/public/store/books/{editionReferenceId}
```

**Display on each card**

| Field | Use |
|-------|-----|
| `title`, `author`, `edition_label` | Headline and subtitle |
| `cover_url` | Card image (hub proxy URL; see below) |
| `new_buyer_price`, `currency` | “From …” / list price for guests |
| `store_presentation` | Always `GUEST` here |
| `categories`, `category_ids` | LMS book categories on this edition (for chips / filters) |

List response **`meta.book_categories`**: full LMS category taxonomy (id, name, slug, …) for sidebar or filter UI. Match row `category_ids` to filter the grid client-side.

**Actions:** **Buy** or **View** → registration / login. Do not call checkout APIs until the user has a Hub JWT.

### Logged-in users

```http
GET /api/store/books
Authorization: Bearer <login_jwt>
```

Same rows, plus ownership and personal price. Drive the card with **`store_presentation`**:

| Value | UI |
|-------|-----|
| `GUEST` | (should not appear when JWT is valid) |
| `BUY` | Show `your_price`; Add to cart |
| `BUY_RETURNING` | Show `your_price` + “Returning reader” |
| `OWNED` | Badge “Owned”; link to **My Books** — hide Buy |

The API returns **one current edition per book** for new guests/buyers; returning buyers may see **owned + current** editions.

---

## 2. Covers (images)

Always use **`cover_url` from the API** (per edition):

```text
GET {API}/api/books/editions/{editionUuid}/cover
```

Use a normal `<img src={cover_url} />` when possible (no `Authorization`). Do **not** load covers from `lms-api…` (CORS). Do **not** use `parent_book_reference_id` in cover paths.

Listed editions: cover is public. Unlisted purchased editions: Hub login JWT on the cover request if the UI loads cover via `fetch`.

---

## 3. Buy (after login)

1. **Price for checkout** (server decides new vs returning buyer):  
   `GET /api/store/books/{editionUuid}/price` + login JWT  
2. **Create order:** `POST /api/book-orders`  
3. **Submit payment** (reference + provider, like applications):  
   `POST /api/book-orders/{orderId}/payment`  

Payment approval is **admin-side**. Until status is paid/approved, do **not** show “Open book” for that purchase.

Full payloads: [`BookPurchaseFrontend.md`](BookPurchaseFrontend.md).

---

## 4. Library & reader (after payment approved)

| Step | Request |
|------|---------|
| List purchased editions | `GET /api/my/books` or `GET /api/my/paid-editions` + login JWT |
| Open reader session | `POST /api/my/paid-editions/{editionUuid}/access` + login JWT (body `{}` ok) |

**Reader UI** from access `data`:

| Field | Use |
|-------|-----|
| `title`, `author`, `edition_label`, `cover_url` | Chrome / header |
| `access_token` | LMS **content** JWT — pages only |
| `reader.first_page_url` | Start reading: `GET` this URL with `Authorization: Bearer {access_token}` |
| Further pages | Same LMS host: `/books/{editionUuid}/pages/{n}` + content JWT |

### Two tokens (critical)

| Token | Where |
|-------|--------|
| **Hub login JWT** | Hub API: store (logged-in), orders, My Books, `POST …/access`, covers when needed |
| **LMS `access_token`** | **Only** LMS page/search URLs — never on `africanhub-api` |

Do not attach the reader token to global HTTP clients that also call the Hub API (causes `Signature verification failed`).

---

## 5. Endpoint cheat sheet

| Who | Purpose | Method & path |
|-----|---------|----------------|
| Visitor | Catalog | `GET /api/public/store/books` |
| Visitor | Edition detail | `GET /api/public/store/books/{editionUuid}` |
| User | Catalog + owned/price | `GET /api/store/books` |
| User | Checkout price | `GET /api/store/books/{editionUuid}/price` |
| User | My library | `GET /api/my/books` |
| User | Reader token | `POST /api/my/paid-editions/{editionUuid}/access` |
| Anyone* | Cover image | `GET /api/books/editions/{editionUuid}/cover` |

\*Listed editions: no auth. Purchased-only unlisted: login JWT if required.

---

## 6. Suggested page flow

```text
Landing / shop
  → GET /api/public/store/books
  → cards: cover_url, title, new_buyer_price

Login
  → GET /api/store/books (JWT)
  → OWNED → My Books; BUY → cart

Checkout
  → GET …/price per line → POST /api/book-orders → payment

My Books (paid)
  → GET /api/my/books
  → Open → POST …/access
  → Reader: img cover_url; pages via LMS + access_token
```

# Book Purchase and Paid Editions API

## 1. Overview

The Source System already provides book sales functionality, including:

* Book edition pricing
* New-buyer and previous-buyer pricing
* Edition sales listings
* Unlisting of editions

The Source System also already has a **payment mechanism for courses**.

This specification extends the existing payment architecture to support **book edition purchases**.

The implementation should **reuse existing course payment components, payment workflows, attachment handling, payment approval mechanisms, and related infrastructure wherever possible**.

A separate payment system should not be created for books unless an existing component cannot support the required book-payment workflow.

---

# 2. Objective

The new functionality shall allow an authenticated user to:

1. Select one or more book editions for purchase.
2. Submit one payment covering one or more editions.
3. Attach proof of payment.
4. View the submitted payment and its approval status.
5. Access the purchased editions only after the payment has been approved.
6. View a list of editions they have successfully paid for.
7. View the LMS book metadata associated with each paid edition.

The key rule is:

> **Submitting a payment does not grant access to the book edition. Only an approved payment grants access.**

---

# 3. Existing LMS Integration

The Source System already has an LMS integration for retrieving:

* Books
* Book editions/versions
* Book metadata
* Edition metadata
* Publication status

This existing integration remains unchanged.

The purchase module should store the relevant LMS references, such as:

```text
book_reference_id
edition_reference_id
```

The Source System should use the existing LMS API to retrieve the actual book and edition metadata when presenting purchased editions to the user.

The purchase module must not create a duplicate book catalogue.

---

# 4. Existing Payment Infrastructure

The Source System already supports course payments.

The book-payment implementation should reuse existing components such as:

* Payment records
* Payment reference numbers
* Payment methods
* Payment attachments
* Proof-of-payment uploads
* Payment approval workflow
* Payment status
* Payment audit trail
* Payment notifications
* User payment history

Where the existing course payment model is generic enough, books should use the same payment tables and components.

The payment system should distinguish the payment purpose/type, for example:

```text
COURSE
BOOK
```

or another equivalent mechanism already used by the API.

---

# 5. Purchase Model

A user may purchase:

```text
One edition
```

or:

```text
Multiple editions
```

in a single payment.

For example:

```text
Payment #PAY-00125

Book A - Edition 2       TZS 45,000
Book B - Edition 1       TZS 30,000
Book C - Edition 3       TZS 50,000
------------------------------------
Total                    TZS 125,000
```

One payment therefore represents a transaction containing one or more book editions.

---

# 6. Recommended Data Relationship

The logical structure should be:

```text
User
  │
  │
  ▼
Purchase / Order
  │
  ├──────── Edition 1
  ├──────── Edition 2
  └──────── Edition 3
          │
          ▼
       Payment
          │
          ▼
   Payment Approval
          │
          ▼
    Paid Editions
```

If the existing course system already uses `orders`, `order_items`, and `payments`, those structures should be reused or extended.

---

# 7. Book Order

A book order represents the user's intention to purchase one or more editions.

Recommended conceptual structure:

```text
book_orders
--------------------------------
id
user_id
order_number
status
subtotal
total_amount
currency
created_at
updated_at
```

Possible order statuses:

```text
PENDING_PAYMENT
PAYMENT_SUBMITTED
PAID
CANCELLED
```

However, if the existing course payment system already has a suitable order/status model, reuse its terminology and structure.

---

# 8. Book Order Items

Each order may contain one or more editions.

```text
book_order_items
--------------------------------
id
order_id
book_reference_id
edition_reference_id
unit_price
quantity
total_price
created_at
```

For book editions, `quantity` will normally be `1`.

Example:

```text
Order #ORD-00125

Item 1
Book:     BK-100
Edition:  ED-100-02
Price:    45,000

Item 2
Book:     BK-200
Edition:  ED-200-01
Price:    30,000
```

---

# 9. Price Must Be Captured at Purchase Time

When the order is created, the API must determine the applicable price from the current edition pricing configuration.

The frontend must not be trusted to provide the final price.

For each edition:

```text
1. Verify that the edition is currently listed.
2. Determine whether the user is a new or previous buyer.
3. Determine the applicable price.
4. Store the calculated price in the order item.
```

Once the order is created, the order item retains the price used for that transaction.

If the edition price later changes, the existing order must not change.

---

# 10. Purchasing Multiple Editions

The API should provide an endpoint for creating a purchase containing multiple editions.

Example:

```http
POST /api/book-orders
```

Request:

```json
{
    "edition_reference_ids": [
        "ED-100-02",
        "ED-200-01",
        "ED-300-03"
    ]
}
```

The API should then:

1. Authenticate the user.
2. Validate all editions.
3. Confirm that all editions are currently listed for sale.
4. Determine the applicable price for each edition.
5. Check whether the user already owns any of the editions.
6. Calculate the total amount.
7. Create the order and order items.

Example response:

```json
{
    "order_number": "BOOK-ORD-00125",
    "currency": "TZS",
    "items": [
        {
            "edition_reference_id": "ED-100-02",
            "unit_price": 45000
        },
        {
            "edition_reference_id": "ED-200-01",
            "unit_price": 30000
        },
        {
            "edition_reference_id": "ED-300-03",
            "unit_price": 50000
        }
    ],
    "total_amount": 125000,
    "status": "PENDING_PAYMENT"
}
```

---

# 11. Prevent Duplicate Purchases

Before creating an order, the API should check whether the user already owns the requested edition.

If an edition has already been successfully paid for, the user should not be required to purchase it again.

For example:

```text
User owns:

ED-100-01
ED-100-02
```

The user selects:

```text
ED-100-02
ED-100-03
```

The API should reject or exclude:

```text
ED-100-02
```

because it has already been purchased.

The user should only be charged for:

```text
ED-100-03
```

The exact behaviour should follow the existing course purchase conventions where applicable.

---

# 12. Payment Submission

After creating the order, the user submits payment using the existing payment mechanism.

The existing course payment workflow should be reused.

Example:

```http
POST /api/payments
```

Conceptually:

```json
{
    "payment_for": "BOOK_ORDER",
    "reference": "BOOK-ORD-00125",
    "amount": 125000,
    "payment_method": "BANK_TRANSFER"
}
```

The actual request structure should follow the existing payment API.

The book module should not introduce a completely separate payment implementation.

---

# 13. Payment Reference (no receipt upload)

Book payments follow the **same submission pattern as course applications**:

* User selects a **service provider** (`payment_methods.id` — exposed as `service_provider_id` in the book order payment API).
* User enters the **payment reference** from the bank or mobile-money transaction (`payment_reference`, stored as `payments.bank_reference`).
* User provides **mobile_number** (required, as for application payments).

No proof-of-payment file upload is required for books.

---

# 14. Payment Status

Payment status should clearly distinguish between submission and approval.

Recommended lifecycle:

```text
PENDING
   │
   │ User submits proof
   ▼
SUBMITTED
   │
   ├───────────────┐
   │               │
Approve           Reject
   │               │
   ▼               ▼
APPROVED         REJECTED
```

If the existing payment system already uses different status names, reuse those statuses.

---

# 15. Payment Approval

A payment must be approved by an authorized user before it can grant access to the purchased editions.

This is a critical business rule:

```text
Payment submitted
        ≠
Edition paid
```

Instead:

```text
Payment submitted
        ↓
Payment reviewed
        ↓
Payment approved
        ↓
Editions become PAID
```

---

# 16. Payment Rejection

If a payment is rejected:

```text
Payment
    = REJECTED
```

the associated editions must **not** become paid.

The user should be able to see that the payment was rejected and, where supported by the existing payment system, submit a new payment/proof.

---

# 17. Payment Approval Effect

When a payment is approved, the API should identify all book editions covered by that payment/order.

For example:

```text
Payment #PAY-00125
        │
        ├── ED-100-02
        ├── ED-200-01
        └── ED-300-03
```

After approval:

```text
ED-100-02 → PAID
ED-200-01 → PAID
ED-300-03 → PAID
```

Only the editions belonging to that approved transaction should be affected.

---

# 18. Purchased Editions

The system should maintain a reliable record that the user has successfully purchased an edition.

This can be implemented using an existing purchase/order structure if it already provides this capability.

Conceptually:

```text
user_book_editions
--------------------------------
id
user_id
book_reference_id
edition_reference_id
order_id
payment_id
paid_amount
currency
paid_at
created_at
```

This record represents the user's entitlement to the edition.

The important state is:

```text
PAID
```

or an equivalent successful-purchase condition.

---

# 19. Get User's Paid Editions

The API shall provide an endpoint allowing the authenticated user to retrieve all book editions they have successfully paid for.

Example:

```http
GET /api/my/books
```

or:

```http
GET /api/my/paid-editions
```

The endpoint should return only editions for which the user has a successfully approved/paid transaction.

---

# 20. Paid Editions Response

The response should include both:

1. Purchase information from the Source System.
2. Book and edition metadata retrieved from the LMS using the existing LMS integration.

Example:

```json
{
    "data": [
        {
            "edition_reference_id": "ED-100-02",
            "book_reference_id": "BK-100",
            "paid_amount": 45000,
            "currency": "TZS",
            "paid_at": "2026-09-30T16:45:00+03:00",
            "book": {
                "reference_id": "BK-100",
                "title": "Introduction to Accounting",
                "author": "John Doe"
            },
            "edition": {
                "reference_id": "ED-100-02",
                "edition_number": 2,
                "publication_status": "PUBLISHED"
            }
        }
    ]
}
```

The exact metadata fields should follow what the existing LMS API already provides.

---

# 21. Retrieve Book Metadata

The Source System should not duplicate the LMS book metadata in the purchase tables.

When returning paid editions:

```text
Purchase Record
       │
       │ edition_reference_id
       ▼
Existing LMS API
       │
       ▼
Book + Edition Metadata
```

The API can combine the two sources into a single response for the frontend.

This allows the user's "My Books" page to display meaningful information such as:

```text
Introduction to Accounting
Edition 2
John Doe
Published: 2026
Purchased: 30 September 2026
```

---

# 22. Get a Specific Paid Edition

The API should also support retrieving a specific edition that the authenticated user owns.

Example:

```http
GET /api/my/paid-editions/{editionReferenceId}
```

The API must first verify that the authenticated user has a successful approved purchase for that edition.

If the user has not purchased the edition:

```http
403 Forbidden
```

or the equivalent authorization response.

The API must not expose paid-edition access merely because the edition is listed publicly.

---

# 23. Access Control Rule

The core authorization rule is:

```text
USER
 │
 ▼
Does user have APPROVED payment
for this edition?
 │
 ├── YES → Allow access
 │
 └── NO  → Deny access
```

The following must **not** grant access:

```text
Listing exists
Price exists
Order exists
Payment submitted
Payment pending
Payment rejected
```

Only successful payment approval grants the entitlement.

---

# 24. Payment and Edition Relationship

The system should maintain traceability:

```text
User
 │
 ▼
Order
 │
 ├── Order Item → Edition 1
 ├── Order Item → Edition 2
 └── Order Item → Edition 3
 │
 ▼
Payment
 │
 ▼
Payment Approval
 │
 ▼
User Edition Entitlements
```

This allows administrators to answer:

* Who purchased this edition?
* Which payment paid for it?
* What amount was paid?
* When was it paid?
* Who approved the payment?
* Which editions were included in the payment?

---

# 25. Payment Approval Audit

The existing payment approval audit mechanism should be reused.

At minimum, the system should retain:

```text
payment_id
approved_by
approved_at
approval_status
approval_comment
```

For rejected payments:

```text
rejected_by
rejected_at
rejection_reason
```

---

# 26. Important Transaction Rule

Payment approval should be handled transactionally.

When an administrator approves a payment:

```text
BEGIN TRANSACTION

1. Approve payment
2. Mark associated order as PAID
3. Create/update paid-edition entitlements
4. Commit transaction

```

If any required operation fails, the transaction should roll back.

This prevents situations such as:

```text
Payment = APPROVED
Order = PAID
Edition entitlement = missing
```

---

# 27. Recommended API Structure

The new functionality can be organized as:

```text
/api
    /book-orders
        POST /
        GET /
        GET /{orderId}

    /book-payments
        POST /
        GET /
        GET /{paymentId}

    /my
        /paid-editions
            GET /
            GET /{editionReferenceId}
```

However, if the existing course payment API is already generic, the book module should **reuse those payment endpoints** rather than creating `/book-payments`.

For example:

```text
Existing:

POST /api/payments
GET  /api/payments/{id}

New:

payment_for = BOOK_ORDER
```

This is preferred where the existing architecture supports it.

---

# 28. Reuse Existing Course Components

Before implementing new components, inspect the existing course payment implementation and reuse:

```text
✓ Payment model
✓ Payment service
✓ Payment status
✓ Payment approval workflow
✓ Payment attachment model
✓ File upload mechanism
✓ Payment reference generation
✓ Payment validation
✓ Payment audit
✓ Payment notification
✓ Payment history
```

Only book-specific components should be introduced where necessary:

```text
✓ Book order
✓ Book order items
✓ Book edition entitlement
✓ Book-specific purchase queries
```

---

# 29. User Journey

The complete user journey should be:

```text
User views listed books
        │
        ▼
Selects one or more editions
        │
        ▼
System calculates applicable prices
        │
        ▼
User confirms purchase
        │
        ▼
Book Order Created
        │
        ▼
User makes payment
        │
        ▼
User uploads proof of payment
        │
        ▼
Payment = SUBMITTED
        │
        ▼
Administrator reviews payment
        │
        ├───────────────┐
        │               │
      Approve         Reject
        │               │
        ▼               ▼
Payment Approved     Payment Rejected
        │
        ▼
Order = PAID
        │
        ▼
Book Editions = PAID
        │
        ▼
User sees editions
under "My Books"
```

---

# 30. My Books

The Source System should provide a user-facing "My Books" endpoint.

Example:

```http
GET /api/my/books
```

The endpoint returns only editions that have been successfully paid for.

Example response:

```json
{
    "data": [
        {
            "book_reference_id": "BK-100",
            "edition_reference_id": "ED-100-02",
            "title": "Introduction to Accounting",
            "edition_number": 2,
            "paid_amount": 45000,
            "currency": "TZS",
            "paid_at": "2026-09-30T16:45:00+03:00"
        },
        {
            "book_reference_id": "BK-200",
            "edition_reference_id": "ED-200-01",
            "title": "Business Management",
            "edition_number": 1,
            "paid_amount": 30000,
            "currency": "TZS",
            "paid_at": "2026-09-30T16:45:00+03:00"
        }
    ]
}
```

The title, edition information, author, cover image, and other presentation metadata should come from the existing LMS integration rather than being duplicated in the sales database.

---

# 31. Summary of Business Rules

The implementation must enforce the following rules:

| #  | Rule                                                                             |
| -- | -------------------------------------------------------------------------------- |
| 1  | A user can purchase one or more editions in a single order.                      |
| 2  | Each order item represents one book edition.                                     |
| 3  | The server determines the applicable edition price.                              |
| 4  | The price charged is stored in the order item.                                   |
| 5  | A payment may cover multiple editions.                                           |
| 6  | Proof of payment must be attached where required by the payment method/workflow. |
| 7  | Existing course payment components should be reused.                             |
| 8  | A submitted payment does not grant access.                                       |
| 9  | Payment must be approved before editions become paid.                            |
| 10 | Rejected payments must not grant edition access.                                 |
| 11 | Only successfully paid editions appear in "My Books".                            |
| 12 | Paid-edition metadata is retrieved from the existing LMS API.                    |
| 13 | A user cannot purchase an edition they already own.                              |
| 14 | Historical transaction prices must not change when current prices change.        |
| 15 | Payment approval and entitlement creation should be transactional.               |
| 16 | Every paid edition must be traceable to its order and payment.                   |

---

# 32. Final Architecture

The resulting architecture should be:

```text
                         LMS
                          │
                          │ Existing API
                          ▼
              ┌──────────────────────┐
              │    SOURCE SYSTEM     │
              │                      │
              │ Existing:            │
              │ • Books              │
              │ • Editions           │
              │ • Book presentation  │
              │                      │
              │ Sales:               │
              │ • Pricing            │
              │ • Listings           │
              │ • Orders             │
              │ • Payments           │
              │ • Approvals          │
              │ • Purchases          │
              │ • Entitlements       │
              └──────────┬───────────┘
                         │
                         ▼
                    User's Books
                         │
                         ▼
                  Existing LMS API
                         │
                         ▼
                Book + Edition Metadata
```

The central principle is:

> **A book edition becomes part of the user's "My Books" collection only after the payment associated with that edition has been approved.**

The LMS continues to provide the authoritative book and edition information, while the Source System manages the user's commercial transaction and entitlement.

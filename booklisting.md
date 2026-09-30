# Source System Book Sales API

## 1. Overview

The Source System already integrates with the **Library Management System (LMS)** and can retrieve books and their editions/versions using the existing LMS API.

This specification covers only the **book sales functionality** to be implemented in the Source System.

The LMS remains responsible for library-related information such as:

* Books
* Book editions/versions
* Publication status
* Storage
* Issuance

The Source System is responsible for the commercial aspects of books, including:

* Edition pricing
* Sales listings
* Customer price eligibility
* Orders
* Purchase history
* Sales transactions

The existing LMS book/edition retrieval API is **outside the scope of this specification**.

---

# 2. Existing LMS Integration

The Source System already has the capability to retrieve:

* Books
* Book editions/versions
* Book publication status
* Other book metadata

using the existing LMS API.

The sales module should therefore **reuse the existing book and edition references**.

The sales module must not create another book catalogue or duplicate the existing LMS integration.

Conceptually:

```text
                    LMS
                     │
                     │ Existing API
                     ▼
              ┌───────────────┐
              │ Source System │
              └───────┬───────┘
                      │
              Existing book API
                      │
                      ▼
             Book / Edition Data
                      │
                      │
             ┌────────▼────────┐
             │   SALES MODULE  │
             └─────────────────┘
```

---

# 3. Scope of the Sales Module

The new functionality consists of:

```text
1. Edition Pricing
2. Edition Sales Listings
3. Unlisting
4. Customer Price Resolution
5. Orders
6. Purchase History
```

---

# 4. Book and Edition References

The Source System already receives book and edition information from the LMS.

The sales tables should reference the existing LMS identifiers rather than creating another master book structure.

For example:

```text
Book
    reference_id = BK-000125

Edition
    reference_id = ED-000125-02
```

The sales module uses these identifiers when maintaining:

* Prices
* Listings
* Orders
* Purchase records

The LMS remains the authoritative source for the actual book and edition information.

---

# 5. Edition Pricing

Each book edition/version can have two prices:

### New Buyer Price

The price charged to a customer who has **never previously purchased an edition of that book**.

### Previous Buyer Price

The price charged to a customer who has **previously purchased an earlier edition of the same book**.

Example:

```text
Book: Introduction to Accounting

Edition 2

New Buyer Price:
TZS 70,000

Previous Buyer Price:
TZS 45,000
```

Pricing is maintained **per edition**.

---

# 6. Edition Price Table

Recommended table:

```text
edition_prices
-----------------------------
id
edition_reference_id
new_buyer_price
previous_buyer_price
currency
is_active
effective_from
effective_to
created_by
created_at
updated_at
```

Example:

```json
{
    "edition_reference_id": "ED-000125-02",
    "new_buyer_price": 70000,
    "previous_buyer_price": 45000,
    "currency": "TZS",
    "is_active": true
}
```

There is no need for the sales module to store the complete edition details because those are already available through the existing LMS integration.

---

# 7. Price Configuration API

## Create Price

```http
POST /api/book-editions/{editionReferenceId}/price
```

Request:

```json
{
    "new_buyer_price": 70000,
    "previous_buyer_price": 45000,
    "currency": "TZS"
}
```

Response:

```json
{
    "edition_reference_id": "ED-000125-02",
    "new_buyer_price": 70000,
    "previous_buyer_price": 45000,
    "currency": "TZS",
    "status": "ACTIVE"
}
```

---

# 8. Updating Prices

Prices may change over time.

Where historical sales must remain accurate, the system should maintain price versions rather than overwriting the previous price.

Example:

```text
Price Version 1

New Buyer:       70,000
Previous Buyer:  45,000

Effective:
01-Jan-2026 → 30-Sep-2026
```

Then:

```text
Price Version 2

New Buyer:       75,000
Previous Buyer:  50,000

Effective:
01-Oct-2026 → NULL
```

Historical orders must always retain the actual price charged at the time of purchase.

---

# 9. Sales Listings

A listing determines whether a specific edition is currently available for sale.

Listing is performed **per edition/version**.

For example:

```text
Book: Business Management

Edition 1
    UNLISTED

Edition 2
    LISTED

Edition 3
    LISTED
```

The parent book itself does not need to have a separate sales listing.

---

# 10. Listing Requirements

An edition can only be listed when:

```text
1. The edition exists in the LMS
2. The edition is PUBLISHED
3. A valid active price exists
4. The edition is not already listed
```

The Source System should use its existing LMS integration to determine whether the edition is published.

---

# 11. Listing Table

Recommended table:

```text
book_listings
-----------------------------
id
edition_reference_id
status
listed_at
listed_by
unlisted_at
unlisted_by
created_at
updated_at
```

Possible statuses:

```text
LISTED
UNLISTED
```

An edition should have only one active listing.

---

# 12. List an Edition

```http
POST /api/book-editions/{editionReferenceId}/listing
```

The API should:

1. Retrieve/validate the edition using the existing LMS integration.
2. Confirm that the edition is published.
3. Confirm that an active price exists.
4. Confirm that the edition is not already listed.
5. Create the listing.

Response:

```json
{
    "edition_reference_id": "ED-000125-02",
    "status": "LISTED",
    "listed_at": "2026-09-30T15:30:00+03:00"
}
```

---

# 13. Unlist an Edition

An edition can be removed from sale without deleting its listing history.

```http
DELETE /api/book-editions/{editionReferenceId}/listing
```

or:

```http
PATCH /api/book-editions/{editionReferenceId}/listing
```

Request:

```json
{
    "status": "UNLISTED"
}
```

The preferred approach is to mark the listing as `UNLISTED` rather than deleting the record.

This preserves the audit history.

---

# 14. Get Current Sales Listings

```http
GET /api/store/books
```

The API returns only editions currently listed for sale.

Example:

```json
{
    "data": [
        {
            "edition_reference_id": "ED-000125-02",
            "new_buyer_price": 70000,
            "previous_buyer_price": 45000,
            "currency": "TZS",
            "status": "LISTED"
        }
    ]
}
```

The Source System can then use its **existing LMS API** to obtain the book and edition presentation information.

---

# 15. Customer Price Resolution

When a customer wants to purchase a listed edition, the Source System determines which price applies.

The API should not rely on the frontend to determine this.

The API checks whether the authenticated customer has previously purchased an edition of the **same book**.

Example:

```text
Current edition:
Edition 3

Customer purchase history:

Edition 1 → Purchased
Edition 2 → Not purchased
```

The customer qualifies for:

```text
PREVIOUS_BUYER_PRICE
```

because they previously purchased an edition of the same book.

---

# 16. New Buyer

If the customer has never purchased any edition of the book:

```json
{
    "customer_type": "NEW_BUYER",
    "price": 80000,
    "currency": "TZS"
}
```

---

# 17. Previous Buyer

If the customer has previously purchased an edition of the same book:

```json
{
    "customer_type": "PREVIOUS_BUYER",
    "price": 50000,
    "currency": "TZS"
}
```

The final price must always be determined server-side.

---

# 18. Purchase History

The Source System needs purchase history to support the previous-buyer pricing rule.

Recommended tables:

```text
orders
    |
    └── order_items
```

Example:

```text
orders
-----------------------------
id
user_id
order_number
status
total_amount
currency
created_at
completed_at
```

```text
order_items
-----------------------------
id
order_id
book_reference_id
edition_reference_id
quantity
unit_price
total_price
```

The `book_reference_id` and `edition_reference_id` correspond to the identifiers already provided by the LMS integration.

---

# 19. Determining Previous-Buyer Eligibility

The eligibility check can conceptually be implemented as:

```text
Current Edition
      │
      ▼
Get Parent Book Reference
      │
      ▼
Search completed purchases
for the same book
      │
      ├── Purchase found
      │       │
      │       ▼
      │   PREVIOUS BUYER
      │
      └── No purchase
              │
              ▼
          NEW BUYER
```

The system should normally consider only **successful/completed purchases** when determining eligibility.

Cancelled, failed, or unpaid orders should not qualify a customer for the previous-buyer price.

---

# 20. Price Must Be Stored in the Order

When an order is created, the actual price calculated by the server must be stored in the order item.

Example:

```text
Edition Price Configuration:

New Buyer:       80,000
Previous Buyer:  50,000
```

Customer qualifies as previous buyer.

The order item stores:

```text
unit_price = 50,000
```

If the edition price is later changed to:

```text
New Buyer:       90,000
Previous Buyer:  60,000
```

the old order remains:

```text
unit_price = 50,000
```

This preserves transaction history.

---

# 21. Sales API Structure

Since book retrieval is already implemented, the new API can be limited to:

```text
/api
    /book-editions
        /{editionReferenceId}/price

    /listings
        GET /
        POST /
        PATCH /{listingId}
        DELETE /{listingId}

    /store
        GET /books
        GET /books/{editionReferenceId}
        GET /books/{editionReferenceId}/price

    /orders
        POST /
        GET /
        GET /{orderId}

    /purchases
        GET /
```

The existing LMS book/edition endpoints remain unchanged.

---

# 22. Responsibility Boundary

The final responsibility boundary is:

| Function             | System                       |
| -------------------- | ---------------------------- |
| Retrieve books       | Existing LMS API integration |
| Retrieve editions    | Existing LMS API integration |
| Book metadata        | LMS                          |
| Edition metadata     | LMS                          |
| Publication status   | LMS                          |
| Storage              | LMS                          |
| Issuance             | LMS                          |
| Sales pricing        | Source System                |
| Sales listing        | Source System                |
| Unlisting            | Source System                |
| Buyer eligibility    | Source System                |
| Orders               | Source System                |
| Payments             | Source System                |
| Purchase history     | Source System                |
| Actual price charged | Source System                |

---

# 23. Core Principle

The Source System should **not duplicate the LMS book management functionality**.

The relationship should remain:

```text
                 LMS
                  │
                  │ Existing integration
                  ▼
        ┌─────────────────────┐
        │    SOURCE SYSTEM    │
        │                     │
        │ Existing:           │
        │ Book presentation   │
        │ Edition presentation│
        │                     │
        │ New:                │
        │ Pricing             │
        │ Listings            │
        │ Orders              │
        │ Purchases           │
        └─────────────────────┘
```

The LMS answers:

> **What is the book and what editions exist?**

The Source System answers:

> **Is this edition for sale, what does it cost, and what price does this customer qualify for?**

This keeps the sales implementation isolated from the existing LMS integration and allows the Source System to control its own commercial rules without changing the LMS.

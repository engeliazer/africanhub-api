# Events / Public Invitations — Frontend Integration Guide

Simple API for listing training events on the website and letting visitors download personalized invitation letter PDFs (same attachment style as the invitation mail batches).

---

## Recommended setup workflow (steps)

Guide the admin through these steps in order. Each admin event response includes a `setup` object showing progress and **what is still missing**.

```mermaid
flowchart LR
  A[1. Event details] --> B[2. Payment & bank]
  B --> C[3. Assign trainers]
  C --> D[4. Invitation template]
  D --> E[5. Publish]
  E --> F[Live on website]
```

| Step | Key | Screen | API |
|------|-----|--------|-----|
| 1 | `event_info` | Course info, venue, dates, times, outcomes | `POST/PUT /api/events` |
| 2 | `payment` | Fee, deposit, deadline, bank details | `PUT /api/events/{id}` (payment fields) |
| 3 | `trainers` | Pick/create trainers | `GET/POST /api/events/trainers`, `PUT /api/events/{id}` with `trainer_ids` |
| 4 | `invitation_letter` | Custom HTML template *(optional)* | `POST /api/events/{id}/template` |
| 5 | `publish` | Go live on website | `PUT /api/events/{id}` `{ "is_published": true }` |

**Poll progress:** `GET /api/events/{id}/setup` or `GET /api/events/{id}` (includes full `setup.steps`).

Publishing is **blocked** until steps 1–3 are complete. Step 4 is optional (built-in default letter is used if skipped).

### Setup object (admin)

```json
{
  "setup": {
    "ready_to_publish": false,
    "is_published": false,
    "current_step": "payment",
    "current_step_label": "Payment & bank details",
    "completed_steps": 1,
    "total_steps": 5,
    "required_steps_complete": false,
    "blocking_publish": ["payment", "course_fee", "bank_account_name"],
    "steps": [
      {
        "key": "event_info",
        "label": "Event details",
        "order": 1,
        "required": true,
        "completed": true,
        "missing": [],
        "hint": "Add course description, learning outcomes, and session times."
      },
      {
        "key": "payment",
        "label": "Payment & bank details",
        "order": 2,
        "required": true,
        "completed": false,
        "missing": ["course_fee", "deposit_amount", "reservation_deadline", "bank_account_name", "bank_account_number", "bank_name"],
        "hint": "Set course fee, deposit, reservation deadline, and bank account details."
      },
      {
        "key": "trainers",
        "label": "Assign trainers",
        "order": 3,
        "required": true,
        "completed": false,
        "missing": ["trainer_ids"],
        "trainer_count": 0,
        "hint": "Assign at least one active trainer via trainer_ids."
      },
      {
        "key": "invitation_letter",
        "label": "Invitation letter template",
        "order": 4,
        "required": false,
        "completed": false,
        "skipped": true,
        "missing": ["template"],
        "uses_default_template": true,
        "hint": "Optional — upload a custom HTML template or use the built-in default."
      },
      {
        "key": "publish",
        "label": "Publish to website",
        "order": 5,
        "required": true,
        "completed": false,
        "missing": ["is_published"],
        "hint": "Set is_published to true when all required steps above are complete."
      }
    ]
  }
}
```

**List view** (`GET /api/events`) returns a compact `setup` summary (`current_step`, `ready_to_publish`, etc.) without the full `steps` array.

**Publish blocked (`400`):**
```json
{
  "status": "error",
  "message": "Cannot publish yet — complete step: Payment & bank details.",
  "data": {
    "setup": { "...": "..." }
  }
}
```

---

## Base URL & authentication

| Endpoint group | Auth |
|----------------|------|
| `POST/GET /api/events` | JWT required |
| `GET /api/events/{id}` | JWT required |
| `GET /api/events/{id}/setup` | JWT required |
| `GET/POST/PUT/DELETE /api/events/trainers` | JWT required |
| `GET /api/events/public` | **No auth** |
| `POST /api/events/public/{id}/letter` | **No auth** |
| `POST /api/events/{id}/template` | JWT required |

### Standard JSON envelope

```json
{
  "status": "success" | "error",
  "message": "Human-readable message (optional)",
  "data": { }
}
```

**Exception:** `POST /api/events/public/{id}/letter` returns a raw `application/pdf` file download on success.

---

## 1. Create event (admin)

`POST /api/events`

**Auth:** Bearer JWT

**Body (JSON):**

```json
{
  "title": "June 2026 IFRS Workshop",
  "course_title": "IFRS FOR SMEs",
  "course_description": "A practical workshop covering key IFRS standards…",
  "venue": "Dar es Salaam, Tanzania",
  "start_date": "2026-06-15",
  "end_date": "2026-06-17",
  "start_time": "08:30",
  "end_time": "16:30",
  "learning_outcomes": "Understand IFRS recognition…",
  "course_fee": 150000,
  "deposit_amount": 50000,
  "reservation_deadline": "2026-06-01",
  "bank_account_name": "The African Hub",
  "bank_account_number": "0123456789",
  "bank_name": "NMB Bank",
  "trainer_ids": [1, 2],
  "is_published": false
}
```

| Field | Required |
|-------|----------|
| title | Yes |
| course_title | Yes |
| venue | Yes |
| start_date | Yes (YYYY-MM-DD) |
| end_date | Yes (must be ≥ start_date) |
| course_description | No |
| start_time / end_time | No (HH:MM or HH:MM:SS) |
| learning_outcomes | No |
| course_fee | No (TZS amount) |
| deposit_amount | No (TZS amount) |
| reservation_deadline | No (YYYY-MM-DD) |
| bank_account_name | No |
| bank_account_number | No |
| bank_name | No |
| trainer_ids | No — array of IDs from `GET /api/events/trainers` |
| is_published | No (default `false`) |

**Alternative:** `multipart/form-data` with the same fields plus optional `template` (HTML file).

Template placeholders (if uploading custom HTML): `[NAME]`, `[ADDRESS]`, `[ORGANIZATION]`. Without a template, the built-in African Hub letter is used.

**Response `201`:**

```json
{
  "status": "success",
  "message": "Event created",
  "data": {
    "id": 1,
    "title": "June 2026 IFRS Workshop",
    "course_title": "IFRS FOR SMEs",
    "course_description": "…",
    "venue": "Dar es Salaam, Tanzania",
    "start_date": "2026-06-15",
    "end_date": "2026-06-17",
    "start_time": "08:30:00",
    "end_time": "16:30:00",
    "learning_outcomes": "…",
    "payment": {
      "course_fee": 150000.0,
      "deposit_amount": 50000.0,
      "reservation_deadline": "2026-06-01",
      "bank_account_name": "The African Hub",
      "bank_account_number": "0123456789",
      "bank_name": "NMB Bank"
    },
    "trainers": [
      {
        "id": 1,
        "full_name": "Dr. Jane Mwangi",
        "designation": "Lead Facilitator",
        "bio": "20 years in public sector accounting…",
        "qualifications": "CPA, PhD",
        "photo": "https://…/jane.jpg",
        "display_order": 0
      }
    ],
    "is_published": false,
    "has_template": false,
    "invitation_template_filename": null,
    "uses_default_template": true,
    "created_by": 5,
    "updated_by": 5,
    "created_at": "2026-08-10T20:00:00",
    "updated_at": "2026-08-10T20:00:00"
  }
}
```

---

## 2. List upcoming events (admin)

`GET /api/events`

**Auth:** Bearer JWT

Returns all events where `end_date >= today`, ordered by start date ascending.

**Response `200`:**

```json
{
  "status": "success",
  "data": [
    { "id": 1, "title": "…", "course_title": "…", "start_date": "2026-06-15", "end_date": "2026-06-17", "is_published": true, "…": "…" }
  ]
}
```

Past events (ended before today) are excluded.

---

## 3. Public event list (website)

`GET /api/events/public`

**Auth:** None

Same as admin list, but:

- Only `is_published === true` events
- Only events not yet ended
- Response includes `payment` and `trainers` (with bios)
- Response omits admin fields (`is_published`, `created_by`, template paths, etc.)

**Trainers:** Manage via `/api/events/trainers` (see section 7 below).

**Response `200`:**

```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "title": "June 2026 IFRS Workshop",
      "course_title": "IFRS FOR SMEs",
      "course_description": "…",
      "venue": "Dar es Salaam, Tanzania",
      "start_date": "2026-06-15",
      "end_date": "2026-06-17",
      "start_time": "08:30:00",
      "end_time": "16:30:00",
      "learning_outcomes": "…",
      "payment": {
        "course_fee": 150000.0,
        "deposit_amount": 50000.0,
        "reservation_deadline": "2026-06-01",
        "bank_account_name": "The African Hub",
        "bank_account_number": "0123456789",
        "bank_name": "NMB Bank"
      },
      "trainers": [
        {
          "id": 1,
          "full_name": "Dr. Jane Mwangi",
          "designation": "Lead Facilitator",
          "bio": "20 years in public sector accounting…",
          "qualifications": "CPA, PhD",
          "photo": "https://…/jane.jpg",
          "display_order": 0
        }
      ]
    }
  ]
}
```

---

## 4. Request invitation letter (public download)

`POST /api/events/public/{event_id}/letter`

**Auth:** None

**Body:**

```json
{
  "full_name": "John Doe",
  "organization": "Ministry of Finance",
  "address": "P.O. Box 123\nDodoma, Tanzania",
  "email": "john@example.com"
}
```

| Field | Required |
|-------|----------|
| full_name | Yes |
| organization | Yes |
| address | Yes |
| email | No |

**Success:** `200` with `Content-Type: application/pdf` — browser file download (same personalized PDF used in invitation mail attachments).

**Errors:**

| HTTP | When |
|------|------|
| 400 | Missing/invalid fields |
| 404 | Event not found or not published |
| 410 | Event has already ended |

---

## 5. Update event (admin)

`PUT /api/events/{event_id}`

**Auth:** Bearer JWT

Partial update — e.g. publish an event:

```json
{ "is_published": true }
```

---

## 6. Upload template (admin, optional)

`POST /api/events/{event_id}/template`

**Auth:** Bearer JWT

**Body:** `multipart/form-data`, field `template` (HTML file with `[NAME]`, `[ADDRESS]`, `[ORGANIZATION]`).

Use after create if you did not attach a template in step 1.

---

## 7. Trainers (admin)

Profiles are stored in `invitation_trainers` (shared with full invitation campaigns).

### List trainers

`GET /api/events/trainers?active_only=true`

### Create trainer

`POST /api/events/trainers`

**JSON:**
```json
{
  "full_name": "Dr. Jane Mwangi",
  "designation": "Lead Facilitator",
  "bio": "20 years in public sector accounting…",
  "qualifications": "CPA, PhD"
}
```

**Or** `multipart/form-data` with the fields above plus optional `photo` file (jpg, png, gif, webp).

**Response `201`:** returns trainer object including `id` — use in `trainer_ids` when creating/updating events.

### Get / update / deactivate

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/events/trainers/{id}` | Single trainer |
| `PUT` | `/api/events/trainers/{id}` | Partial update; supports photo upload |
| `DELETE` | `/api/events/trainers/{id}` | Soft delete (`is_active = false`) |

---

## Suggested website flow

```mermaid
flowchart LR
  A[Load GET /api/events/public] --> B[Show event cards]
  B --> C[User clicks Request letter]
  C --> D[Form: name, org, address]
  D --> E[POST .../letter]
  E --> F[Browser downloads PDF]
```

---

## Admin flow

1. `POST /api/events` — step 1 (basic info; leave `is_published: false`)
2. `GET /api/events/{id}/setup` — show wizard / highlight missing fields
3. `PUT /api/events/{id}` — complete payment, assign `trainer_ids`
4. `POST /api/events/{id}/template` — optional custom letter
5. `PUT /api/events/{id}` `{ "is_published": true }` — publish when `ready_to_publish` is true
6. `GET /api/events/public` — verify on website

---

## Related systems

- **Full invitation campaigns** (`/api/invitations`) — batch email, trainers, invitees, scheduling
- **Invitation mail batches** (`/api/mail/invitation-batches`) — bulk email with PDF attachments

This events API is the lightweight public-facing layer for the website.

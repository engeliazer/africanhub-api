# Subjects — Frontend Integration Guide (Create & Edit)

This document describes how the React (or other) frontend should integrate with the **Subjects API** when **creating** or **editing** a subject, including **badge flags** and **code-based list ordering**.

---

## Base URL & authentication

| Item | Value |
|------|--------|
| Base path | `/api/subjects` |
| Auth | **JWT required** (`Authorization: Bearer <token>`) |
| Content-Type | `application/json` **or** `multipart/form-data` when uploading a details document |

### Standard JSON envelope

```json
{
  "status": "success" | "error",
  "message": "Human-readable message (optional on success)",
  "data": { }
}
```

| HTTP code | Meaning |
|-----------|---------|
| `201` | Subject created |
| `200` | Subject updated / fetched |
| `400` | Validation error (e.g. duplicate `code`) |
| `404` | Subject not found |
| `500` | Server error |

---

## Endpoints used by create/edit screens

| Action | Method | Endpoint |
|--------|--------|----------|
| List subjects (admin table) | `GET` | `/api/subjects` |
| Load one subject (edit form) | `GET` | `/api/subjects/{id}` |
| Create subject | `POST` | `/api/subjects` |
| Create subject + topic + subtopic (wizard) | `POST` | `/api/subjects/with-topic-subtopic` |
| Update subject | `PUT` | `/api/subjects/{id}` |

---

## Subject object shape

### Full subject (response)

```json
{
  "id": 12,
  "name": "Financial Reporting",
  "code": "FR-101",
  "description": "Covers IFRS reporting standards",
  "current_price": 150000,
  "duration_days": 90,
  "trial_duration_days": 7,
  "is_most_popular": true,
  "is_best_price": false,
  "is_most_recent": false,
  "flags": ["most_popular"],
  "is_active": true,
  "details_document_url": "https://africanhub-api.africanhub.ac.tz/storage/subject_documents/fr-101-a1b2c3d4.pdf",
  "created_by": 5,
  "updated_by": 5,
  "created_at": "2026-08-10T08:00:00",
  "updated_at": "2026-08-10T08:00:00",
  "deleted_at": null
}
```

When fetched via `GET /api/subjects/{id}` or list endpoints, topics may also be nested under `topics`.

### Details document

| Field | Type | Notes |
|-------|------|-------|
| `details_document_url` | `string \| null` | Public URL to an uploaded syllabus/details file (PDF, DOC, DOCX, or TXT). Set by the API on upload; not sent as JSON on create/update. |

---

## List ordering & badge flags

### Sort order — use `code`

Subjects are ordered by **`code` ascending** (A→Z) on all list endpoints. There is **no separate rank field** in the UI.

**Admin guidance:** choose subject codes that sort in the desired display order, e.g.:

| Code | Appears |
|------|---------|
| `CPA-01` | Before `CPA-02` |
| `CPA-02` | Before `CPA-10` |
| `FR-101` | Before `FR-102` |

Use zero-padding or consistent prefixes so lexical sort matches intended order (`CPA-09` before `CPA-10`).

The `display_rank` column may still exist in the database/API response but is **ignored for sorting** — do not expose it in create/edit forms.

### Badge flags (independent checkboxes)

Each badge is a **separate boolean**. A subject can have **none, one, or several** at once.

| Field | Label (suggested) | UI chip color (suggestion) |
|-------|-------------------|----------------------------|
| `is_most_popular` | Most Popular | Primary / gold |
| `is_best_price` | Best Price | Green |
| `is_most_recent` | Most Recent | Blue |

| Property | Value |
|----------|--------|
| Type | `boolean` |
| Default | `false` |
| Required on create | No |

Responses also include a derived **`flags`** array — active badge keys only, e.g. `["most_popular", "best_price"]`. Use `flags` for simple chip rendering, or the booleans when you need individual toggles.

**UI recommendation**

- Three checkboxes or toggle switches in a **“Catalog badges”** section
- On the public catalog card, render a small pill/chip for each flag that is `true`
- Order chips consistently: Most Popular → Best Price → Most Recent

---

## Create subject

### `POST /api/subjects`

Supports **JSON** (no file) or **multipart/form-data** (with optional details document).

#### Option A — JSON only (no document)

**Request body**

```json
{
  "name": "Financial Reporting",
  "code": "FR-101",
  "description": "Optional description",
  "current_price": 150000,
  "duration_days": 90,
  "trial_duration_days": 7,
  "is_most_popular": true,
  "is_best_price": false,
  "is_most_recent": false,
  "is_active": true,
  "created_by": 5,
  "updated_by": 5
}
```

#### Option B — multipart with details document

Use `Content-Type: multipart/form-data`.

| Form field | Type | Required | Notes |
|------------|------|----------|-------|
| `name` | text | yes | |
| `code` | text | yes | Must be unique |
| `description` | text | no | |
| `current_price` | text/number | no | |
| `duration_days` | text/number | no | |
| `trial_duration_days` | text/number | no | |
| `is_most_popular` | text | no | `"true"` / `"false"` (default `false`) |
| `is_best_price` | text | no | |
| `is_most_recent` | text | no | |
| `is_active` | text | no | default `true` |
| `created_by` | text/number | yes | Current user id |
| `updated_by` | text/number | yes | Same as `created_by` on create |
| `details_document` | file | no | PDF, DOC, DOCX, or TXT — max 15 MB |

**Example (fetch)**

```typescript
const form = new FormData();
form.append("name", "Financial Reporting");
form.append("code", "FR-101");
form.append("current_price", "150000");
form.append("created_by", String(userId));
form.append("updated_by", String(userId));
if (file) form.append("details_document", file);

await fetch("/api/subjects", {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },
  body: form,
});
```

Do **not** set `Content-Type: application/json` when sending `FormData` — the browser sets the multipart boundary automatically.

**Required fields**

| Field | Notes |
|-------|-------|
| `name` | string |
| `code` | string, must be unique |
| `created_by` | current user id from JWT |
| `updated_by` | same as `created_by` on create |

**Optional fields (with defaults)**

| Field | Default if omitted |
|-------|---------------------|
| `description` | `null` |
| `current_price` | `null` |
| `duration_days` | `null` |
| `trial_duration_days` | `null` |
| `is_most_popular` | `false` |
| `is_best_price` | `false` |
| `is_most_recent` | `false` |
| `is_active` | `true` |

**Success response (`201`)** includes `details_document_url` when a file was uploaded.

```json
{
  "status": "success",
  "data": { /* SubjectInDB — see shape above */ }
}
```

**Typical errors**

| Condition | HTTP | Message |
|-----------|------|---------|
| Duplicate `code` | `500` / `400` | Subject code already exists |
| Invalid document type | `400` | Invalid document type. Allowed: PDF, DOC, DOCX, TXT |
| File too large | `400` | Document must be 15MB or smaller |

---

## Create subject with topic & subtopic (wizard)

### `POST /api/subjects/with-topic-subtopic`

Use when the admin creates subject, first topic, and first subtopic in one step.

Supports **JSON** or **multipart/form-data** (when including a details document).

#### JSON body

```json
{
  "subject": {
    "name": "Financial Reporting",
    "code": "FR-101",
    "description": "Optional",
    "current_price": 150000,
    "duration_days": 90,
    "trial_duration_days": 7,
    "is_most_popular": true,
    "is_best_price": false,
    "is_most_recent": false,
    "is_active": true,
    "created_by": 5,
    "updated_by": 5
  },
  "topic": {
    "name": "Introduction",
    "code": "FR-101-T1",
    "description": "Optional",
    "is_active": true
  },
  "subtopic": {
    "name": "Overview",
    "code": "FR-101-T1-S1",
    "description": "Optional",
    "is_active": true
  }
}
```

#### Multipart (with details document)

| Form field | Type | Required |
|------------|------|----------|
| `subject` | text (JSON string) | yes |
| `topic` | text (JSON string) | yes |
| `subtopic` | text (JSON string) | yes |
| `details_document` | file | no |

```typescript
const form = new FormData();
form.append("subject", JSON.stringify(subjectPayload));
form.append("topic", JSON.stringify(topicPayload));
form.append("subtopic", JSON.stringify(subtopicPayload));
if (file) form.append("details_document", file);
```

Include the same display fields inside `subject` as in the plain create endpoint.

---

## Edit subject

### Load form — `GET /api/subjects/{id}`

1. Fetch subject by id.
2. Map response into form state, including badge checkboxes.

**Example form state (TypeScript)**

```typescript
type SubjectFormState = {
  name: string;
  code: string;
  description: string;
  current_price: number | "";
  duration_days: number | "";
  trial_duration_days: number | "";
  is_most_popular: boolean;
  is_best_price: boolean;
  is_most_recent: boolean;
  is_active: boolean;
  detailsDocumentUrl: string | null;
  detailsDocumentFile: File | null;
};
```

**Map API → form**

```typescript
function subjectToForm(subject: Subject): SubjectFormState {
  return {
    name: subject.name,
    code: subject.code,
    description: subject.description ?? "",
    current_price: subject.current_price ?? "",
    duration_days: subject.duration_days ?? "",
    trial_duration_days: subject.trial_duration_days ?? "",
    is_most_popular: subject.is_most_popular,
    is_best_price: subject.is_best_price,
    is_most_recent: subject.is_most_recent,
    is_active: subject.is_active,
    detailsDocumentUrl: subject.details_document_url ?? null,
    detailsDocumentFile: null,
  };
}
```

Show a **Details document** file input on create/edit. If `detailsDocumentUrl` is set, show a link to open/download the current file and a “Remove document” control.

### Save — `PUT /api/subjects/{id}`

Send **JSON** for field-only updates, or **multipart** when uploading or replacing the details document.

#### JSON (no file change)

Send **only changed fields** plus **required** `updated_by`, or send the full form — both work because the API uses partial update (`exclude_unset`).

**Request body (full update example)**

```json
{
  "name": "Financial Reporting",
  "code": "FR-101",
  "description": "Updated description",
  "current_price": 160000,
  "duration_days": 90,
  "trial_duration_days": 7,
  "is_most_popular": true,
  "is_best_price": true,
  "is_most_recent": false,
  "is_active": true,
  "updated_by": 5
}
```

#### Multipart — replace details document

Same form fields as create (only fields you want to change), plus:

| Form field | Notes |
|------------|-------|
| `details_document` | New file replaces the existing one |
| `remove_details_document` | `"true"` to delete the current file without uploading a new one |

```typescript
const form = new FormData();
form.append("name", formState.name);
form.append("updated_by", String(userId));
if (formState.detailsDocumentFile) {
  form.append("details_document", formState.detailsDocumentFile);
} else if (removeDocument) {
  form.append("remove_details_document", "true");
}
```

**Partial update example (badges only)**

```json
{
  "is_most_popular": false,
  "is_best_price": true,
  "updated_by": 5
}
```

**Required on every update**

| Field | Notes |
|-------|-------|
| `updated_by` | current user id from JWT |

**Success response (`200`)**

```json
{
  "status": "success",
  "message": "Subject updated successfully",
  "data": { /* updated SubjectInDB */ }
}
```

**Map form → API**

```typescript
function formToPayload(form: SubjectFormState, userId: number): Record<string, unknown> {
  return {
    name: form.name,
    code: form.code,
    description: form.description || null,
    current_price: form.current_price === "" ? null : Number(form.current_price),
    duration_days: form.duration_days === "" ? null : Number(form.duration_days),
    trial_duration_days: form.trial_duration_days === "" ? null : Number(form.trial_duration_days),
    is_most_popular: form.is_most_popular,
    is_best_price: form.is_best_price,
    is_most_recent: form.is_most_recent,
    is_active: form.is_active,
    updated_by: userId,
  };
}
```

---

## Suggested form layout (admin UI)

```text
┌─────────────────────────────────────────────────┐
│  Create / Edit Subject                          │
├─────────────────────────────────────────────────┤
│  Name *          [________________________]   │
│  Code *          [________________________]   │
│  Description     [________________________]   │
│  Price           [________________________]   │
│  Duration (days) [____]  Trial (days) [____]   │
│  Active          [x] Active                     │
├─────────────────────────────────────────────────┤
│  Badges                                          │
│  [ ] Most Popular   [ ] Best Price              │
│  [ ] Most Recent                                 │
├─────────────────────────────────────────────────┤
│                        [Cancel]  [Save Subject] │
└─────────────────────────────────────────────────┘
```

Place **Catalog display** below core fields so admins set name/code/price first, then optional presentation metadata.

---

## Client-side validation (recommended)

| Field | Rule |
|-------|------|
| `name` | Required, non-empty |
| `code` | Required, non-empty, unique — **also controls list order** (ascending) |
| `current_price` | If provided: integer ≥ 0 |
| `duration_days` | If provided: integer > 0 |
| `trial_duration_days` | If provided: integer ≥ 0 |
| Badge flags | No mutual exclusivity — any combination allowed |

---

## Public website endpoints (no login)

These endpoints power the marketing/catalog site. Subjects are always returned **`code` ascending** — same rule as authenticated lists.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/courses/public` | Full subject catalog with topics/subtopics |
| `GET /api/schedules/public` | Active seasons, each with nested subjects |

**Frontend:** render subjects in API response order; do not re-sort client-side.

Badge fields (`is_most_popular`, `is_best_price`, `is_most_recent`) and a derived **`flags`** array are included on public responses for catalog chips.

---

## How lists are sorted (read-only / catalog)

After save, subjects appear in list endpoints sorted by:

1. `code` ascending (A→Z)

Applies to:

- `GET /api/subjects`
- `GET /api/available-subjects`
- `GET /api/courses/public` (public catalog, no auth)
- `GET /api/schedules/public`
- `GET /api/subject-structure`

**Frontend:** rely on API order — do not re-sort unless the admin table adds its own column sort. To change display order, update the subject **`code`** (or create subjects with codes that sort correctly).

---

## TypeScript types (copy-paste)

```typescript
export type Subject = {
  id: number;
  name: string;
  code: string;
  description: string | null;
  current_price: number | null;
  duration_days: number | null;
  trial_duration_days: number | null;
  is_most_popular: boolean;
  is_best_price: boolean;
  is_most_recent: boolean;
  flags: string[];
  is_active: boolean;
  created_by: number;
  updated_by: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  topics?: Topic[];
};

export type SubjectCreatePayload = {
  name: string;
  code: string;
  description?: string | null;
  current_price?: number | null;
  duration_days?: number | null;
  trial_duration_days?: number | null;
  is_most_popular?: boolean;
  is_best_price?: boolean;
  is_most_recent?: boolean;
  is_active?: boolean;
  created_by: number;
  updated_by: number;
};

export type SubjectUpdatePayload = Partial<Omit<SubjectCreatePayload, "created_by">> & {
  updated_by: number;
};
```

---

## Example: create flow (React)

```typescript
async function createSubject(form: SubjectFormState, token: string, userId: number) {
  const res = await fetch("/api/subjects", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ...formToPayload(form, userId),
      created_by: userId,
    }),
  });

  const json = await res.json();
  if (json.status !== "success") {
    throw new Error(json.message ?? "Failed to create subject");
  }
  return json.data as Subject;
}
```

---

## Example: edit flow (React)

```typescript
async function updateSubject(
  id: number,
  form: SubjectFormState,
  token: string,
  userId: number
) {
  const res = await fetch(`/api/subjects/${id}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(formToPayload(form, userId)),
  });

  const json = await res.json();
  if (json.status !== "success") {
    throw new Error(json.message ?? "Failed to update subject");
  }
  return json.data as Subject;
}
```

---

## Public catalog badge rendering

When consuming `GET /api/courses/public` or subject list data on the marketing site:

```tsx
function SubjectBadges({ subject }: { subject: Subject }) {
  const badges = subject.flags ?? [];
  if (!badges.length) return null;

  const labels: Record<string, string> = {
    most_popular: "Most Popular",
    best_price: "Best Price",
    most_recent: "Most Recent",
  };

  return (
    <div className="flex gap-2">
      {badges.map((key) => (
        <span key={key} className="badge">{labels[key] ?? key}</span>
      ))}
    </div>
  );
}
```

---

## Checklist for frontend team

- [ ] Add three **badge checkboxes** to create & edit forms
- [ ] Use **`code`** to control catalog order (no display-rank field)
- [ ] Set `created_by` / `updated_by` from authenticated user id
- [ ] Prefill edit form from `GET /api/subjects/{id}`
- [ ] Show badge chips on catalog cards when flags are `true`
- [ ] Use API sort order in list views (do not override with `created_at`)
- [ ] If using the wizard endpoint, put display fields inside `subject` object

# Certificate Generation System — Backend Implementation Instructions

## 1. Purpose

Build a backend system that automates generation of training/participation certificates
(e.g. "Application of Microsoft Excel on Financial Statements Preparation", "Advanced
Microsoft Excel for Financial Statements Preparation and Automation (Master Class)").

Reference samples provided (attached separately to the AI):
- A blank template with placeholder `«Name»` and `«SN»` fields — shows the raw template structure.
- Issued certificates showing real data: participant name, subject, host organization, venue,
  date range, certificate number (e.g. `AHBT/DCRC/08/24/00051`), CPD hours line
  ("qualified for the award of 24 hours of Continuing Professional Development"),
  and two signatory blocks (e.g. "Managing Director" / "Training Coordinator" or "Trainer").
- A dual-branding sample showing two organization logos on one certificate (home + invited/collaborating center).

Use these samples to infer the exact visual placeholder positions (name, signatures, dates, cert number)
when building the template-mapping engine described in Section 6.

---

## 2. Core Entities / Data Model

### 2.1 Organization (Training Center)
Represents any center that can host or co-host trainings.
- `id`
- `name` (e.g. "Dar es Salaam CPA Review Center (DCRC)")
- `short_code` (used in certificate numbering, e.g. "DCRC")
- `logo_url`
- `default_signatories`: list of `{name, title}` (e.g. "Dr. CPA, David Kiwia — Managing Director")

### 2.2 User
- `id`, `name`, `email`, `role`
- `organization_ids`: organizations this user has access to (supports the "user may belong to
  multiple training centers" requirement). All training-creation actions must scope to one
  organization selected by the user at creation time (see Section 4.1).

### 2.3 Subject (Course / Training Topic)
A reusable definition of a training topic, decoupled from any single running of it.
- `id`
- `title` (e.g. "Advanced Microsoft Excel for Financial Statements Preparation and Automation")
- `default_certificate_template_id` (FK to CertificateTemplate — see 2.4)
- `grants_cpd_hours`: boolean — whether this subject is eligible to carry CPD/professional hours
  at all (a subject can be CPD-eligible but a specific training instance may still choose the hour count, or 0)
- `default_cpd_hours`: integer, optional (pre-fill convenience, editable per training)

### 2.4 CertificateTemplate
A saved, reusable visual background/layout.
- `id`, `name`
- `background_image_url` or `background_svg`
- `field_layout`: coordinates/anchors for dynamic fields (name, subject, dates, venue, cert number,
  CPD hours line, signatory blocks, home-org logo slot, invited-org logo slot). Store as JSON, e.g.:
  ```json
  {
    "participant_name": {"x":..., "y":..., "font":..., "align":"center"},
    "subject_title": {"x":..., "y":..., "font":...},
    "venue_line": {"x":..., "y":...},
    "date_range": {"x":..., "y":...},
    "cert_number": {"x":..., "y":..., "align":"right"},
    "cpd_hours_line": {"x":..., "y":..., "optional": true},
    "logo_home": {"x":..., "y":..., "slot":"left-or-primary"},
    "logo_invited": {"x":..., "y":..., "slot":"right", "optional": true},
    "signatory_1": {"name_x":..., "name_y":..., "title_x":..., "title_y":...},
    "signatory_2": {"name_x":..., "name_y":..., "title_x":..., "title_y":...}
  }
  ```
- Multiple templates can exist; a Subject maps to exactly one default template, but allow override
  at Training level (rare case: same subject rendered on a different background).

### 2.5 Training (a scheduled run of a Subject)
- `id`
- `subject_id`
- `home_organization_id` — the organization running/owning the training (required; user must select
  from the organizations they belong to)
- `invited_organization_id` — optional; set when co-hosted. When present, render home org's branding
  on the left/primary position and invited org's branding on the right, per Section 5.2.
- `venue_text` (free text, e.g. "held at the Institute of Finance Management located in Dar es Salaam
  Region-Tanzania")
- `start_date`, `end_date`
- `cpd_hours` — integer, defaults from `Subject.default_cpd_hours`, editable by the user per training.
  0 or null means "no CPD hours awarded for this run."
- `certificate_template_id` — defaults to `Subject.default_certificate_template_id`, overridable
- `cert_number_prefix` — pattern for numbering, e.g. `{invited_code}/{home_code}/{yy}/{seq}` or
  `{home_code}/{seq}` depending on org convention; make this configurable per training/org rather
  than hardcoded, since observed samples use different formats
  (`AHBT/DCRC/08/24/00051` vs a design with only `«SN»`).
- `status`: draft → roster_uploaded → confirmed → certificates_generated

### 2.6 Participant (per Training)
- `id`, `training_id`
- `full_name`
- `salutation`: enum or free text (e.g. "CPA", "Dr.", "Mr.", "Ms.", none). This drives eligibility
  logic — see Section 5.1.
- `is_eligible`: boolean, computed but overridable by the user before final confirmation
  (accommodate edge cases the auto-rule gets wrong)
- `confirmation_status`: pending → confirmed → excluded
- `certificate_id`: set once generated

### 2.7 Certificate
- `id`, `training_id`, `participant_id`
- `cert_number` (final, unique, immutable once issued)
- `rendered_file_url` (PDF/image)
- `issued_at`
- `access_token` or participant-linked auth for self-service download (Section 7)

---

## 3. Business Rules

### 3.1 Multi-organization access
A user may belong to several organizations. Every training must be explicitly created under
one `home_organization_id` chosen by the user from their accessible org list — never inferred
or defaulted silently.

### 3.2 Collaboration / co-hosting
If a training has an `invited_organization_id`:
- Home organization's logo/name renders in the primary (left) branding slot.
- Invited organization's logo/name renders in the secondary (right) branding slot.
- If no invited organization, only the home slot renders; do not leave a visible empty placeholder.

### 3.3 CPD / professional hours
- Each Training has its own `cpd_hours` value, independent per run of the same Subject.
- The certificate template's CPD-hours line only renders if `cpd_hours` is set and > 0 **and**
  the participant is eligible (see 3.4) — some samples show certificates with no hours line at all
  ("has successfully participated in a training on...") vs. others with the explicit
  "qualified for the award of 24 hours of Continuing Professional Development" line. This is a
  per-certificate conditional block, not just a per-template one.

### 3.4 CPA / accountant eligibility
- A participant is treated as an accountant **only if** their `salutation` indicates CPA
  (e.g. starts with or contains "CPA"). Titles like "Dr.", "Mr.", "Ms." alone do not qualify.
- CPD hours may only be awarded to participants who are (a) recorded as CPA **and** (b) the
  Training itself has `cpd_hours` > 0. Non-CPA participants still receive a normal participation
  certificate (no hours line), even in a training that awards hours to CPA attendees.
- Implement this as a computed field `participant.qualifies_for_cpd = is_cpa AND training.cpd_hours > 0`,
  and expose it as an editable override, not a hard rule, since salutation data entry can be messy
  (e.g. "CPA. Dr. David D Kiwia" — should still match "CPA").

### 3.5 Template selection
- Each Subject has a default CertificateTemplate. When a Training is created for that Subject, the
  template is pre-selected but the user can override it at the Training level.
- Template library must support adding new backgrounds/layouts without code changes — treat this as
  admin-managed data, not hardcoded assets.

### 3.6 Roster confirmation gate
- Certificates must never be generated directly from an uploaded roster. Flow is strictly:
  upload/enter participants → system computes eligibility → user reviews table and confirms/excludes
  each row → only `confirmed` participants become eligible for certificate generation.
- Store the confirmed list as its own artifact (don't just filter the raw roster at generation time),
  so there's an auditable record of who was confirmed and when.

---

## 4. Workflows

### 4.1 Setup (admin-side, one-time / occasional)
1. Create Organizations, assign Users to Organizations.
2. Create/upload CertificateTemplate backgrounds and define field layouts.
3. Create Subjects, map each to a default CertificateTemplate, mark `grants_cpd_hours`.

### 4.2 Create a Training
1. User selects home organization (from their accessible orgs).
2. User optionally selects an invited/collaborating organization.
3. User selects Subject → template pre-fills (overridable).
4. User enters venue text, start/end dates, cert number pattern, and CPD hours for this run
   (0 if not applicable).

### 4.3 Roster & Eligibility
1. User adds participants (bulk import or manual entry) with `full_name` and `salutation`.
2. System computes `is_eligible` / `qualifies_for_cpd` per Section 3.4.
3. User reviews the participant table, can toggle/override any row, then clicks "Confirm list."
4. Confirmed list is locked as the source of truth for generation.

### 4.4 Generate Certificates
1. For each confirmed participant, render the assigned CertificateTemplate with:
   name, subject title, venue text, date range, cert number (per pattern, sequential),
   CPD-hours line (conditional per 3.3/3.4), home/invited branding, signatories.
2. Persist each as a Certificate record with a stored file and a unique access mechanism.

### 4.5 Participant Access
1. Only participants with a generated Certificate can preview/download.
2. Provide a lookup (e.g. by cert number + name, or a shareable tokenized link, or participant login)
   — decide based on whatever auth model the rest of the platform uses; do not require a full account
   system if a signed link is sufficient.
3. Preview shows a watermarked/rendered view; download serves the final PDF/image.

---

## 5. Rendering Details

### 5.1 Conditional blocks per certificate
- CPD-hours sentence: render only if applicable (3.3/3.4).
- Invited-org branding: render only if `invited_organization_id` present.
- Signatory blocks: pull from `Organization.default_signatories` at Training level (allow override
  per Training in case a different signatory is used for one run).

### 5.2 Layout for co-branded certificates
- Home organization logo/name: left position.
- Invited organization logo/name: right position.
- Confirm this against the dual-logo sample provided — replicate its exact relative positioning.

### 5.3 Certificate numbering
- Make the numbering pattern configurable per organization or per training (observed formats differ:
  plain serial vs. `ORG/ORG/YY/SEQ`). Sequence counters should be scoped per organization (or per
  organization+year, matching the `08/24/00051` style) to avoid collisions.

---

## 6. Suggested API Surface (adjust to existing platform conventions)

- `GET /organizations` — orgs the current user can act on behalf of
- `POST /trainings` — create training (home org, invited org, subject, template, dates, venue, cpd_hours)
- `POST /trainings/{id}/participants` — bulk add participants
- `GET /trainings/{id}/participants` — table with computed eligibility for review
- `PATCH /trainings/{id}/participants/{pid}` — override eligibility/CPD flag
- `POST /trainings/{id}/confirm` — lock confirmed list
- `POST /trainings/{id}/generate-certificates` — generate for all confirmed participants
- `GET /certificates/{id}` — fetch a single certificate (preview)
- `GET /certificates/{id}/download`
- `GET /certificate-templates`, `POST /certificate-templates` — template library management

---

## 7. Open Decisions for the Implementer

- Exact participant-facing auth model for downloads (public token link vs. account login).
- File format for generated certificates (PDF recommended for print quality; also generate a
  preview image/thumbnail).
- Whether salutation should be a constrained enum or free text with fuzzy CPA matching — free text
  with matching is safer given real data like "CPA. Dr. David D Kiwia".
- Bulk roster import format (CSV/XLSX) and required columns.

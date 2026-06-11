# Invitation Management System

## Overview

The system shall enable users to create invitation campaigns, upload invitees, generate personalized PDF invitation letters, and send them via email.

## Workflow

1. Create Invitation
2. Configure Course Information
3. Select Trainer(s)
4. Configure Payment Information
5. Upload Invitees Excel File
6. Validate Invitees
7. Generate HTML
8. Convert HTML to PDF
9. Send Emails
10. Track Delivery Status

---

# Frontend Responsibilities

## Create Invitation Screen

### Course Information

- Course Title
- Course Description
- Venue
- Start Date
- End Date
- Start Time
- End Time
- Learning Outcomes

### Trainer Information

- Select Existing Trainer
- Create New Trainer

### Payment Information

- Course Fee
- Deposit Amount
- Reservation Deadline
- Bank Account

### Email Information

- Email Subject
- Email Introduction Message

---

## Upload Invitees

Supported formats:

- XLSX
- XLS

Expected columns:

| Column | Required |
|----------|----------|
| Full Name | Yes |
| Email | Yes |
| Address | No |
| Organization | No |

---

## Invitee Validation Screen

Display:

- Total Records
- Valid Records
- Invalid Records
- Duplicate Records

Provide invitee preview table.

---

## PDF Preview

Allow users to:

- Preview invitation
- Download sample PDF
- Verify formatting

---

## Sending Options

Allow users to:

- Send Test Email
- Send Immediately
- Schedule Sending

---

## Campaign Dashboard

Display:

- Total Invitees
- Emails Sent
- Delivered
- Failed
- Pending

Display email activity log.

---

# Backend Responsibilities

## Campaign Management

Create and manage invitation campaigns.

### invitations

```sql
id
title
course_title
course_description
venue
start_date
end_date
start_time
end_time
email_subject
email_message
status
created_at
updated_at
```

## Trainer Management

### trainers

```sql
id
full_name
designation
bio
qualifications
photo
```

Provide APIs for:

- Create Trainer
- Update Trainer
- Delete Trainer
- List Trainers

---

## Invitee Processing

Read uploaded Excel file.

Validate:

- Required columns
- Email format
- Duplicate emails

### invitation_invitees

```sql
id
invitation_id
full_name
email
address
organization
status
```

---

## HTML Generation

Generate invitation using 7 sections:

1. Header
2. Recipient Information
3. Invitation Section
4. About the Course
5. About the Trainer
6. Payment Details
7. Footer

Use Jinja2 templates.

---

## PDF Generation

Convert HTML to PDF.

Recommended:

- WeasyPrint

Alternative:

- wkhtmltopdf

File naming:

```text
Invitation_John_Doe.pdf
```

---

## Email Sending

Send personalized email with PDF attachment.

Support:

- Zoho SMTP
- Gmail SMTP
- Microsoft 365 SMTP

Use queue processing.

Recommended:

- Celery
- Redis

---

## Email Tracking

### email_logs

```sql
id
invitation_id
invitee_id
email
status
sent_at
delivered_at
opened_at
error_message
```

Statuses:

- Pending
- Sending
- Sent
- Delivered
- Opened
- Failed

---

## Background Jobs

Run asynchronously:

1. Excel Processing
2. PDF Generation
3. Email Sending
4. Email Tracking

---

# Recommended Stack

## Frontend

- ReactJS
- Material UI
- Axios

## Backend

- Flask
- SQLAlchemy
- Marshmallow

## Document Generation

- Jinja2
- WeasyPrint

## Database

- MySQL

## Queue

- Celery
- Redis

## Email

- Zoho SMTP

---

# Future Enhancements

- Multiple Invitation Templates
- QR Code on Invitation
- WhatsApp Delivery
- SMS Notifications
- Attendance Confirmation
- Certificate Generation
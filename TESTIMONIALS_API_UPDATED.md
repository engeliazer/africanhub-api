# Testimonials API Documentation (Updated)

This document explains how to manage testimonials in the OCPA system with user linking and approval workflow.

## Table of Contents
- [Overview](#overview)
- [Database Setup](#database-setup)
- [API Endpoints](#api-endpoints)
- [Frontend Integration](#frontend-integration)
- [Workflow Examples](#workflow-examples)

## Overview

The Testimonials system allows you to:
- **Manage student testimonials** (admin only)
- **Display approved testimonials** on public website
- **Review and approve testimonials** before they go public
- **Link testimonials to existing users** (ex-students only)
- **Store testimonial photos** and credentials
- **Track testimonial activity** and approval status

### Key Features
- **User-linked testimonials**: Testimonials are linked to existing users in the system
- **Approval workflow**: All testimonials require admin approval before going public
- **Review tracking**: Track who reviewed and when testimonials were approved
- **Public display**: Only approved testimonials are shown on the website

## Database Setup

### 1. Create the Testimonials Table

Run this SQL query in your MySQL database:

```sql
-- Create the testimonials table
CREATE TABLE IF NOT EXISTS testimonials (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role VARCHAR(255),
    text TEXT NOT NULL,
    photo VARCHAR(500),
    rating INT NOT NULL DEFAULT 5,
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by BIGINT NULL,
    reviewed_at DATETIME NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT NOT NULL,
    updated_by BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    INDEX idx_testimonials_user (user_id),
    INDEX idx_testimonials_approved (is_approved),
    INDEX idx_testimonials_active (is_active),
    INDEX idx_testimonials_deleted (deleted_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2. Insert Sample Data

```sql
-- Insert sample testimonial data (assuming users with IDs 1 and 2 exist)
INSERT INTO testimonials (user_id, role, text, photo, rating, is_approved, reviewed_by, reviewed_at, is_active, created_by, updated_by) VALUES
(1, 'CPA Graduate, 2024', 'DCRC provided me with the best CPA review experience. The instructors are knowledgeable, the materials are comprehensive, and the support is exceptional. I passed all my exams on the first attempt!', 'https://api.ocpac.dcrc.ac.tz/storage/testimonials/james-mwenda.jpg', 5, TRUE, 1, '2024-01-15 10:00:00', TRUE, 1, 1),
(2, 'CPA Graduate, 2023', 'The structured approach to teaching and the practical examples made complex topics easy to understand. I highly recommend DCRC to anyone serious about becoming a CPA.', 'https://api.ocpac.dcrc.ac.tz/storage/testimonials/amina-hassan.jpg', 5, TRUE, 1, '2024-01-15 10:00:00', TRUE, 1, 1);
```

## API Endpoints

### Public Endpoint (No Authentication Required)

#### Get All Approved Testimonials
```http
GET /api/testimonials/public
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "James Mwenda",
      "role": "CPA Graduate, 2024",
      "photo": "https://api.ocpac.dcrc.ac.tz/storage/testimonials/james-mwenda.jpg",
      "rating": 5,
      "text": "DCRC provided me with the best CPA review experience. The instructors are knowledgeable, the materials are comprehensive, and the support is exceptional. I passed all my exams on the first attempt!"
    },
    {
      "id": 2,
      "name": "Amina Hassan",
      "role": "CPA Graduate, 2023",
      "photo": "https://api.ocpac.dcrc.ac.tz/storage/testimonials/amina-hassan.jpg",
      "rating": 5,
      "text": "The structured approach to teaching and the practical examples made complex topics easy to understand. I highly recommend DCRC to anyone serious about becoming a CPA."
    }
  ]
}
```

### Admin Endpoints (Authentication Required)

#### Get All Testimonials (Pending + Approved)
```http
GET /api/testimonials
Authorization: Bearer <jwt_token>
```

#### Get Pending Testimonials
```http
GET /api/testimonials/pending
Authorization: Bearer <jwt_token>
```

#### Get Specific Testimonial
```http
GET /api/testimonials/{id}
Authorization: Bearer <jwt_token>
```

#### Create New Testimonial (Student Submission)
```http
POST /api/testimonials
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

Form Data:
- user_id: "123" (current user's ID)
- role: "CPA Graduate, 2024"
- text: "Excellent training program that prepared me well for my career."
- rating: "5"
- is_active: "true"
- photo: [image file]
```

#### Create New Testimonial (with photo URL)
```http
POST /api/testimonials
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "user_id": 123,
  "role": "CPA Graduate, 2024",
  "text": "Excellent training program that prepared me well for my career.",
  "photo": "https://api.ocpac.dcrc.ac.tz/storage/testimonials/jane-smith.jpg",
  "rating": 5,
  "is_active": true
}
```

#### Review Testimonial (Approve/Reject)
```http
PUT /api/testimonials/{id}/review
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "is_approved": true,
  "reviewed_by": 1,
  "updated_by": 1
}
```

#### Update Testimonial
```http
PUT /api/testimonials/{id}
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "role": "CPA Graduate, 2024",
  "text": "Updated testimonial with additional details.",
  "photo": "https://api.ocpac.dcrc.ac.tz/storage/testimonials/jane-smith-updated.jpg",
  "rating": 5,
  "is_active": true
}
```

#### Delete Testimonial (Soft Delete)
```http
DELETE /api/testimonials/{id}
Authorization: Bearer <jwt_token>
```

## Frontend Integration

### 1. Public Website Display

For displaying testimonials on your public website:

```javascript
// Fetch approved testimonials for public display
async function fetchTestimonials() {
  try {
    const response = await fetch('https://api.ocpac.dcrc.ac.tz/api/testimonials/public');
    const data = await response.json();
    
    if (data.status === 'success') {
      displayTestimonials(data.data);
    }
  } catch (error) {
    console.error('Error fetching testimonials:', error);
  }
}

// Display testimonials in your UI
function displayTestimonials(testimonials) {
  const container = document.getElementById('testimonials-container');
  
  testimonials.forEach(testimonial => {
    const testimonialCard = `
      <div class="testimonial-card">
        <img src="${testimonial.photo}" alt="${testimonial.name}" class="testimonial-photo">
        <h3>${testimonial.name}</h3>
        <p class="role">${testimonial.role}</p>
        <p class="text">"${testimonial.text}"</p>
        <div class="rating">${'★'.repeat(testimonial.rating)}${'☆'.repeat(5-testimonial.rating)}</div>
      </div>
    `;
    container.innerHTML += testimonialCard;
  });
}
```

### 2. Student Testimonial Submission

For students to submit testimonials:

```javascript
// Submit testimonial (student)
async function submitTestimonial(testimonialData, photoFile) {
  try {
    const formData = new FormData();
    formData.append('user_id', getCurrentUserId()); // Current logged-in user
    formData.append('role', testimonialData.role);
    formData.append('text', testimonialData.text);
    formData.append('rating', testimonialData.rating);
    formData.append('is_active', 'true');
    if (photoFile) {
      formData.append('photo', photoFile);
    }

    const response = await fetch('https://api.ocpac.dcrc.ac.tz/api/testimonials', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      },
      body: formData
    });
    
    const result = await response.json();
    if (result.status === 'success') {
      alert('Testimonial submitted successfully! It will be reviewed before going public.');
    }
    return result;
  } catch (error) {
    console.error('Error submitting testimonial:', error);
  }
}
```

### 3. Admin Review Interface

For admins to review testimonials:

```javascript
// Fetch pending testimonials (admin)
async function fetchPendingTestimonials() {
  try {
    const response = await fetch('https://api.ocpac.dcrc.ac.tz/api/testimonials/pending', {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      }
    });
    const data = await response.json();
    return data.data;
  } catch (error) {
    console.error('Error fetching pending testimonials:', error);
  }
}

// Approve testimonial (admin)
async function approveTestimonial(testimonialId) {
  try {
    const response = await fetch(`https://api.ocpac.dcrc.ac.tz/api/testimonials/${testimonialId}/review`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        is_approved: true,
        reviewed_by: getCurrentUserId(),
        updated_by: getCurrentUserId()
      })
    });
    return await response.json();
  } catch (error) {
    console.error('Error approving testimonial:', error);
  }
}

// Reject testimonial (admin)
async function rejectTestimonial(testimonialId) {
  try {
    const response = await fetch(`https://api.ocpac.dcrc.ac.tz/api/testimonials/${testimonialId}/review`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        is_approved: false,
        reviewed_by: getCurrentUserId(),
        updated_by: getCurrentUserId()
      })
    });
    return await response.json();
  } catch (error) {
    console.error('Error rejecting testimonial:', error);
  }
}
```

## Workflow Examples

### Student Workflow
1. **Student logs in** to their account
2. **Student submits testimonial** via form with photo upload
3. **Testimonial is created** with `is_approved = false`
4. **Admin receives notification** of pending testimonial
5. **Admin reviews testimonial** and approves/rejects
6. **If approved**, testimonial appears on public website

### Admin Workflow
1. **Admin logs in** to admin panel
2. **Admin views pending testimonials** via `/api/testimonials/pending`
3. **Admin reviews testimonial** content and user details
4. **Admin approves or rejects** via `/api/testimonials/{id}/review`
5. **If approved**, testimonial becomes visible on public website

### Public Website Workflow
1. **Website fetches testimonials** via `/api/testimonials/public`
2. **Only approved testimonials** are returned
3. **User names are populated** from users table
4. **Testimonials are displayed** with photos and ratings

## Error Handling

### Common Error Responses

```json
// 404 - Testimonial not found
{
  "status": "error",
  "message": "Testimonial not found"
}

// 400 - Validation error
{
  "status": "error",
  "message": "Validation error details"
}

// 500 - Server error
{
  "status": "error",
  "message": "Internal server error"
}
```

## Testing the API

### Test Public Endpoint
```bash
curl https://api.ocpac.dcrc.ac.tz/api/testimonials/public
```

### Test Admin Endpoints (with authentication)
```bash
# Get all testimonials
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     https://api.ocpac.dcrc.ac.tz/api/testimonials

# Get pending testimonials
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     https://api.ocpac.dcrc.ac.tz/api/testimonials/pending

# Approve testimonial
curl -X PUT \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"is_approved": true, "reviewed_by": 1, "updated_by": 1}' \
     https://api.ocpac.dcrc.ac.tz/api/testimonials/1/review
```

## Deployment Checklist

1. ✅ Create testimonials table in database
2. ✅ Insert sample data
3. ✅ Deploy code to production
4. ✅ Restart Flask application
5. ✅ Test public endpoint
6. ✅ Test admin endpoints
7. ✅ Upload testimonial photos
8. ✅ Test approval workflow

## Support

For any issues or questions regarding the Testimonials API, please contact the development team or check the application logs for detailed error information.

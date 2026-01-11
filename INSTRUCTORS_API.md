# Instructors API Documentation

This document explains how to manage instructors in the OCPA system, including both admin management and public display functionality.

## Table of Contents
- [Overview](#overview)
- [Database Setup](#database-setup)
- [API Endpoints](#api-endpoints)
- [Frontend Integration](#frontend-integration)
- [Sample Data](#sample-data)

## Overview

The Instructors system allows you to:
- **Manage instructor profiles** (admin only)
- **Display instructor information** on public website
- **Store instructor photos** and credentials
- **Track instructor activity** and status

## Database Setup

### 1. Create the Instructors Table

Run this SQL query in your MySQL database:

```sql
-- Create the instructors table
CREATE TABLE IF NOT EXISTS instructors (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    bio TEXT,
    photo VARCHAR(500),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT NOT NULL,
    updated_by BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    INDEX idx_instructors_active (is_active),
    INDEX idx_instructors_deleted (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2. Insert Sample Data

```sql
-- Insert sample instructor data
INSERT INTO instructors (name, title, bio, photo, is_active, created_by, updated_by) VALUES
('Dr. John Mwangi', 'CPA, PhD in Accounting', 'Dr. Mwangi is a seasoned accounting professional with extensive experience in financial reporting and auditing.', 'https://api.ocpac.dcrc.ac.tz/storage/instructors/dr-john-mwangi.jpg', TRUE, 1, 1),
('Ms. Sarah Kimani', 'CPA, MSc Finance', 'Ms. Kimani specializes in management accounting and has helped hundreds of students excel in their exams.', 'https://api.ocpac.dcrc.ac.tz/storage/instructors/sarah-kimani.jpg', TRUE, 1, 1),
('Mr. David Omondi', 'CPA, LLM Taxation', 'Mr. Omondi is a tax expert with a strong background in both taxation and business law.', 'https://api.ocpac.dcrc.ac.tz/storage/instructors/david-omondi.jpg', TRUE, 1, 1);
```

## API Endpoints

### Public Endpoint (No Authentication Required)

#### Get All Active Instructors
```http
GET /api/instructors/public
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "Dr. John Mwangi",
      "title": "CPA, PhD in Accounting",
      "bio": "Dr. Mwangi is a seasoned accounting professional with extensive experience in financial reporting and auditing.",
      "photo": "https://api.ocpac.dcrc.ac.tz/storage/instructors/dr-john-mwangi.jpg"
    },
    {
      "id": 2,
      "name": "Ms. Sarah Kimani",
      "title": "CPA, MSc Finance",
      "bio": "Ms. Kimani specializes in management accounting and has helped hundreds of students excel in their exams.",
      "photo": "https://api.ocpac.dcrc.ac.tz/storage/instructors/sarah-kimani.jpg"
    }
  ]
}
```

### Admin Endpoints (Authentication Required)

#### Get All Instructors
```http
GET /api/instructors
Authorization: Bearer <jwt_token>
```

#### Get Specific Instructor
```http
GET /api/instructors/{id}
Authorization: Bearer <jwt_token>
```

#### Create New Instructor (with photo upload)
```http
POST /api/instructors
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

Form Data:
- name: "Dr. Jane Smith"
- title: "CPA, PhD in Finance"
- bio: "Dr. Smith is an expert in corporate finance and investment analysis."
- is_active: "true"
- photo: [image file]
```

#### Create New Instructor (with photo URL)
```http
POST /api/instructors
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "Dr. Jane Smith",
  "title": "CPA, PhD in Finance",
  "bio": "Dr. Smith is an expert in corporate finance and investment analysis.",
  "photo": "https://api.ocpac.dcrc.ac.tz/storage/instructors/jane-smith.jpg",
  "is_active": true
}
```

#### Update Instructor (with photo upload)
```http
PUT /api/instructors/{id}
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

Form Data:
- name: "Dr. Jane Smith Updated"
- title: "CPA, PhD in Finance, CFA"
- bio: "Updated bio with additional qualifications."
- is_active: "true"
- photo: [image file]
```

#### Update Instructor (with photo URL)
```http
PUT /api/instructors/{id}
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "Dr. Jane Smith Updated",
  "title": "CPA, PhD in Finance, CFA",
  "bio": "Updated bio with additional qualifications.",
  "photo": "https://api.ocpac.dcrc.ac.tz/storage/instructors/jane-smith-updated.jpg",
  "is_active": true
}
```

#### Delete Instructor (Soft Delete)
```http
DELETE /api/instructors/{id}
Authorization: Bearer <jwt_token>
```

## Frontend Integration

### 1. Public Website Display

For displaying instructors on your public website:

```javascript
// Fetch instructors for public display
async function fetchInstructors() {
  try {
    const response = await fetch('https://api.ocpac.dcrc.ac.tz/api/instructors/public');
    const data = await response.json();
    
    if (data.status === 'success') {
      displayInstructors(data.data);
    }
  } catch (error) {
    console.error('Error fetching instructors:', error);
  }
}

// Display instructors in your UI
function displayInstructors(instructors) {
  const container = document.getElementById('instructors-container');
  
  instructors.forEach(instructor => {
    const instructorCard = `
      <div class="instructor-card">
        <img src="${instructor.photo}" alt="${instructor.name}" class="instructor-photo">
        <h3>${instructor.name}</h3>
        <p class="title">${instructor.title}</p>
        <p class="bio">${instructor.bio}</p>
      </div>
    `;
    container.innerHTML += instructorCard;
  });
}
```

### 2. Admin Management Interface

For managing instructors in your admin panel:

```javascript
// Fetch all instructors (admin)
async function fetchAllInstructors() {
  try {
    const response = await fetch('https://api.ocpac.dcrc.ac.tz/api/instructors', {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      }
    });
    const data = await response.json();
    return data.data;
  } catch (error) {
    console.error('Error fetching instructors:', error);
  }
}

// Create new instructor with photo upload
async function createInstructorWithPhoto(instructorData, photoFile) {
  try {
    const formData = new FormData();
    formData.append('name', instructorData.name);
    formData.append('title', instructorData.title);
    formData.append('bio', instructorData.bio);
    formData.append('is_active', instructorData.is_active);
    if (photoFile) {
      formData.append('photo', photoFile);
    }

    const response = await fetch('https://api.ocpac.dcrc.ac.tz/api/instructors', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
        // Don't set Content-Type for FormData - browser will set it with boundary
      },
      body: formData
    });
    return await response.json();
  } catch (error) {
    console.error('Error creating instructor:', error);
  }
}

// Create new instructor with photo URL
async function createInstructor(instructorData) {
  try {
    const response = await fetch('https://api.ocpac.dcrc.ac.tz/api/instructors', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(instructorData)
    });
    return await response.json();
  } catch (error) {
    console.error('Error creating instructor:', error);
  }
}

// Update instructor
async function updateInstructor(id, instructorData) {
  try {
    const response = await fetch(`https://api.ocpac.dcrc.ac.tz/api/instructors/${id}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(instructorData)
    });
    return await response.json();
  } catch (error) {
    console.error('Error updating instructor:', error);
  }
}

// Delete instructor
async function deleteInstructor(id) {
  try {
    const response = await fetch(`https://api.ocpac.dcrc.ac.tz/api/instructors/${id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
        'Content-Type': 'application/json'
      }
    });
    return await response.json();
  } catch (error) {
    console.error('Error deleting instructor:', error);
  }
}
```

## Sample Data

The system comes with 3 sample instructors:

1. **Dr. John Mwangi** - CPA, PhD in Accounting
2. **Ms. Sarah Kimani** - CPA, MSc Finance  
3. **Mr. David Omondi** - CPA, LLM Taxation

## Photo Management

### Image Upload Support

The API now supports **direct image uploads** for instructor photos:

#### **Supported Formats:**
- JPG/JPEG
- PNG  
- GIF

#### **File Specifications:**
- **Recommended size**: 300x300px (square)
- **Max file size**: 5MB
- **Auto-generated filenames**: `instructor-name-uuid.jpg`

#### **Two Upload Methods:**

1. **Direct File Upload (Recommended):**
   ```javascript
   const formData = new FormData();
   formData.append('name', 'Dr. Jane Smith');
   formData.append('title', 'CPA, PhD');
   formData.append('bio', 'Expert in finance');
   formData.append('photo', photoFile); // File object
   
   fetch('/api/instructors', {
     method: 'POST',
     headers: { 'Authorization': `Bearer ${token}` },
     body: formData
   });
   ```

2. **Photo URL (Alternative):**
   ```javascript
   fetch('/api/instructors', {
     method: 'POST',
     headers: { 
       'Authorization': `Bearer ${token}`,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       name: 'Dr. Jane Smith',
       photo: 'https://example.com/photo.jpg'
     })
   });
   ```

### Directory Setup

1. **Create photo directory:**
   ```bash
   mkdir -p /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/instructors
   chmod 755 /var/www/ocpac/api.ocpac.dcrc.ac.tz/storage/instructors
   ```

2. **Photo URLs:**
   - Base URL: `https://api.ocpac.dcrc.ac.tz/storage/instructors/`
   - Auto-generated: `https://api.ocpac.dcrc.ac.tz/storage/instructors/dr-jane-smith-a1b2c3d4.jpg`

## Error Handling

### Common Error Responses

```json
// 404 - Instructor not found
{
  "status": "error",
  "message": "Instructor not found"
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
curl https://api.ocpac.dcrc.ac.tz/api/instructors/public
```

### Test Admin Endpoint (with authentication)
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     https://api.ocpac.dcrc.ac.tz/api/instructors
```

## Deployment Checklist

1. ✅ Create instructors table in database
2. ✅ Insert sample data
3. ✅ Deploy code to production
4. ✅ Restart Flask application
5. ✅ Test public endpoint
6. ✅ Upload instructor photos
7. ✅ Test admin endpoints with authentication

## Support

For any issues or questions regarding the Instructors API, please contact the development team or check the application logs for detailed error information.

# Cancel Application API Endpoint

## Overview
This endpoint allows users to cancel their own applications by updating the application status to "withdrawn".

## Endpoint Details

### **PUT** `/api/my-applications/{application_id}/cancel`

**Authentication:** Required (JWT token)

**Description:** Cancels an application by updating its status to "withdrawn". Users can only cancel their own applications.

---

## Request Format

### URL Parameters
- `application_id` (integer, required): The ID of the application to cancel

### Headers
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

### Request Body
No request body required - this is a simple status update operation.

---

## Response Formats

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Application cancelled successfully",
  "data": {
    "id": 123,
    "user_id": 1,
    "payment_status": "pending_payment",
    "total_fee": 150.0,
    "status": "withdrawn",
    "is_active": true,
    "created_by": 1,
    "updated_by": 1,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T14:45:00Z",
    "deleted_at": null
  }
}
```

### Error Responses

#### 404 Not Found
```json
{
  "status": "error",
  "message": "Application not found or you don't have permission to cancel this application"
}
```

#### 400 Bad Request
```json
{
  "status": "error",
  "message": "Application cannot be cancelled. Current status: withdrawn"
}
```

#### 401 Unauthorized
```json
{
  "status": "error",
  "message": "Missing or invalid authentication token"
}
```

#### 500 Internal Server Error
```json
{
  "status": "error",
  "message": "Internal server error occurred"
}
```

---

## Business Rules

### Applications That Can Be Cancelled
- Applications with status: `pending`, `approved`, `waitlisted`
- Applications belonging to the authenticated user
- Applications that are not soft-deleted (`deleted_at` is null)

### Applications That Cannot Be Cancelled
- Applications with status: `withdrawn` (already cancelled)
- Applications with status: `rejected` (already processed)
- Applications with status: `verified` (already processed)
- Applications belonging to other users
- Soft-deleted applications

---

## Example Usage

### cURL Example
```bash
curl -X PUT "https://api.ocpac.dcrc.ac.tz/api/my-applications/123/cancel" \
  -H "Authorization: Bearer your_jwt_token_here" \
  -H "Content-Type: application/json"
```

### JavaScript/Fetch Example
```javascript
const cancelApplication = async (applicationId) => {
  try {
    const response = await fetch(`/api/my-applications/${applicationId}/cancel`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      }
    });
    
    const result = await response.json();
    
    if (result.status === 'success') {
      console.log('Application cancelled successfully:', result.data);
      return result.data;
    } else {
      console.error('Error cancelling application:', result.message);
      throw new Error(result.message);
    }
  } catch (error) {
    console.error('Network error:', error);
    throw error;
  }
};

// Usage
cancelApplication(123)
  .then(application => {
    console.log('Cancelled application:', application);
  })
  .catch(error => {
    console.error('Failed to cancel application:', error);
  });
```

### React/Axios Example
```javascript
import axios from 'axios';

const cancelApplication = async (applicationId) => {
  try {
    const response = await axios.put(
      `/api/my-applications/${applicationId}/cancel`,
      {},
      {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      }
    );
    
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.message);
    } else {
      throw new Error('Network error occurred');
    }
  }
};

// Usage in component
const handleCancelApplication = async (applicationId) => {
  try {
    const result = await cancelApplication(applicationId);
    console.log('Application cancelled:', result.data);
    // Update UI or refresh application list
  } catch (error) {
    console.error('Failed to cancel application:', error.message);
    // Show error message to user
  }
};
```

---

## Frontend Integration

### UI Considerations
1. **Cancel Button**: Show a "Cancel Application" button for eligible applications
2. **Confirmation Dialog**: Ask for confirmation before cancelling
3. **Status Check**: Only show cancel button for applications that can be cancelled
4. **Loading State**: Show loading indicator during the request
5. **Success/Error Feedback**: Display appropriate messages to the user

### Status-Based UI Logic
```javascript
const canCancelApplication = (application) => {
  const cancellableStatuses = ['pending', 'approved', 'waitlisted'];
  return cancellableStatuses.includes(application.status);
};

// In your component
{canCancelApplication(application) && (
  <button 
    onClick={() => handleCancelApplication(application.id)}
    className="cancel-btn"
  >
    Cancel Application
  </button>
)}
```

---

## Related Endpoints

- **GET** `/api/my-applications` - Get user's applications
- **GET** `/api/applications/{id}` - Get specific application details
- **PUT** `/api/applications/{id}` - Update application (admin only)

---

## Notes

- This endpoint only allows users to cancel their own applications
- The application status is updated to "withdrawn" immediately
- No additional confirmation or approval is required
- The operation is logged with the current user as the updater
- Cancelled applications remain in the system but are marked as withdrawn

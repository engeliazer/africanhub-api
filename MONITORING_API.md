# Celery Monitoring API Documentation

## Overview
The monitoring API provides endpoints to track Celery background tasks, queue status, and video processing progress. All endpoints require JWT authentication.

## Base URL
```
http://your-api-domain/api/monitoring
```

## Authentication
All endpoints require JWT token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

## Endpoints

### 1. Queue Status
**GET** `/api/monitoring/queue-status`

Returns current Redis queue status.

**Response:**
```json
{
  "queue_length": 0,
  "active_tasks": 0,
  "timestamp": "2025-09-26T21:34:31.256760",
  "status": "healthy"
}
```

### 2. Processing Materials
**GET** `/api/monitoring/processing-materials`

Returns materials currently being processed.

**Response:**
```json
{
  "materials": [
    {
      "id": 169,
      "name": "Video_Test_20250926_210827.mp4",
      "status": "processing",
      "progress": 75,
      "storage_location": "local",
      "created_at": "2025-09-26T21:00:00",
      "updated_at": "2025-09-26T21:15:00",
      "minutes_processing": 15,
      "is_stuck": false
    }
  ],
  "count": 1,
  "stuck_count": 0,
  "timestamp": "2025-09-26T21:34:31.256760"
}
```

### 3. Recent Completed
**GET** `/api/monitoring/recent-completed?limit=10`

Returns recently completed materials.

**Query Parameters:**
- `limit` (optional): Number of results to return (default: 10)

**Response:**
```json
{
  "materials": [
    {
      "id": 168,
      "name": "Sample_Video.mp4",
      "status": "completed",
      "progress": 100,
      "storage_location": "local",
      "completed_at": "2025-09-26T21:30:00"
    }
  ],
  "count": 1,
  "timestamp": "2025-09-26T21:34:31.256760"
}
```

### 4. Stuck Tasks
**GET** `/api/monitoring/stuck-tasks`

Returns tasks that have been processing for more than 30 minutes.

**Response:**
```json
{
  "stuck_tasks": [
    {
      "id": 170,
      "name": "Long_Video.mp4",
      "status": "processing",
      "progress": 100,
      "updated_at": "2025-09-26T20:00:00",
      "minutes_processing": 95
    }
  ],
  "count": 1,
  "timestamp": "2025-09-26T21:34:31.256760"
}
```

### 5. Clear Stuck Tasks
**POST** `/api/monitoring/clear-stuck-tasks`

Clears stuck tasks and marks them as failed.

**Response:**
```json
{
  "message": "Cleared 2 stuck tasks",
  "affected_count": 2,
  "timestamp": "2025-09-26T21:34:31.256760"
}
```

### 6. Clear Queue
**POST** `/api/monitoring/clear-queue`

Clears the entire Redis queue.

**Response:**
```json
{
  "message": "Cleared 5 tasks from queue",
  "cleared_count": 5,
  "timestamp": "2025-09-26T21:34:31.256760"
}
```

### 7. Dashboard (Complete Overview)
**GET** `/api/monitoring/dashboard`

Returns complete monitoring data including queue status, processing materials, recent completions, and stuck tasks.

**Response:**
```json
{
  "queue": {
    "length": 0,
    "active_tasks": 0,
    "status": "healthy"
  },
  "materials": {
    "processing": [...],
    "recent_completed": [...],
    "counts": {
      "processing": 0,
      "completed": 2,
      "failed": 0
    }
  },
  "stuck_tasks": {
    "count": 0,
    "tasks": []
  },
  "timestamp": "2025-09-26T21:34:31.256760"
}
```

## Frontend Integration Examples

### React/JavaScript Example
```javascript
// Get monitoring dashboard
const getMonitoringDashboard = async () => {
  const response = await fetch('/api/monitoring/dashboard', {
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    }
  });
  return await response.json();
};

// Clear stuck tasks
const clearStuckTasks = async () => {
  const response = await fetch('/api/monitoring/clear-stuck-tasks', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    }
  });
  return await response.json();
};
```

### Real-time Monitoring
```javascript
// Poll monitoring data every 5 seconds
const startMonitoring = () => {
  setInterval(async () => {
    const data = await getMonitoringDashboard();
    updateUI(data);
  }, 5000);
};
```

## Status Indicators

### Queue Status
- `healthy`: Queue length < 10
- `busy`: Queue length >= 10

### Material Status
- `pending`: Waiting to be processed
- `processing`: Currently being processed
- `completed`: Successfully processed
- `failed`: Processing failed

### Stuck Task Detection
- Tasks processing for > 30 minutes are considered stuck
- `is_stuck`: Boolean flag for easy filtering
- `minutes_processing`: Time in minutes since last update

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `401`: Unauthorized (missing/invalid JWT)
- `500`: Server error

Error responses include:
```json
{
  "error": "Error message description"
}
```

## Best Practices

1. **Polling Frequency**: Don't poll more than once every 5 seconds
2. **Error Handling**: Always handle 401 and 500 responses
3. **Stuck Tasks**: Monitor for stuck tasks and provide clear actions
4. **User Feedback**: Show progress indicators for processing materials
5. **Queue Management**: Provide options to clear stuck tasks when needed

## Testing

Test endpoint (no authentication required):
```
GET /api/monitoring/test
```

Response:
```json
{
  "message": "Monitoring API is working!",
  "timestamp": "2025-09-26T21:34:31.256760"
}
```

# Video Tracking API

Student-facing endpoints for recording and reading video study progress.

All routes require `Authorization: Bearer <jwt>`.

**Important:** `material_id` is always `subtopic_materials.id` (numeric), not the VdoCipher video ID.

---

## Concepts

| Field | Meaning |
|-------|---------|
| `total_watched_seconds` | Cumulative watch time across all sessions |
| `completion_percentage` | `(total_watched_seconds / video_duration) × 100`, capped at 100 |
| `status` | `not_started` → `in_progress` → `completed` (≥ 90%, never reverts) |
| `max_position_seconds` | Furthest playback position reached (for resume UX) |

`SubtopicMaterial.processing_progress` is unrelated — that tracks video encoding, not user study progress.

---

## Write endpoints (during playback)

### Start session

Called when the user presses play.

```
POST /api/video-tracking/sessions/start
```

**Request body:**
```json
{ "material_id": 42 }
```

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "session_token": "550e8400-e29b-41d4-a716-446655440000",
    "material_id": 42,
    "video_duration": 3600
  }
}
```

**Errors:**
- `400` — missing `material_id`, or material has no `video_duration`
- `404` — material not found or not a video type

---

### Heartbeat

Called about every 30 seconds while the video is playing.

```
POST /api/video-tracking/sessions/{session_token}/heartbeat
```

**Request body:**
```json
{
  "current_position": 542.5,
  "watched_delta": 30.0
}
```

| Field | Description |
|-------|-------------|
| `current_position` | Player `currentTime` in seconds |
| `watched_delta` | Seconds actually watched since the last heartbeat |

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "session_token": "550e8400-e29b-41d4-a716-446655440000",
    "watched_delta_applied": 30.0,
    "completion_percentage": 15.08,
    "status": "in_progress",
    "total_watched_seconds": 542.5
  }
}
```

The backend clamps `watched_delta` to a maximum of ~35 seconds and validates it against wall-clock elapsed time.

---

### End session

Called on pause, video end, or page unload.

```
POST /api/video-tracking/sessions/{session_token}/end
```

Same request body and response shape as heartbeat. Marks the session inactive.

---

## Read endpoints

### One material

```
GET /api/video-tracking/progress/{material_id}
```

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "material_id": 42,
    "material_name": "Introduction to Algebra",
    "subtopic_id": 7,
    "video_duration": 3600,
    "total_watched_seconds": 1800,
    "max_position_seconds": 1750,
    "completion_percentage": 50.0,
    "status": "in_progress",
    "session_count": 3,
    "first_watched_at": "2026-08-01T10:00:00",
    "last_watched_at": "2026-08-09T14:30:00",
    "completed_at": null
  }
}
```

If the user has never watched, returns zeros with `status: "not_started"`.

---

### All video materials in a subject

```
GET /api/video-tracking/progress/subject/{subject_id}
```

Returns per-material progress plus a **derived** subject summary (computed on demand, not stored).

**Success (200):**
```json
{
  "status": "success",
  "data": {
    "subject_id": 5,
    "summary": {
      "video_count": 12,
      "videos_completed": 4,
      "videos_in_progress": 5,
      "videos_not_started": 3,
      "total_video_duration": 43200,
      "total_watched_seconds": 18500,
      "completion_percentage": 42.8,
      "status": "in_progress",
      "first_watched_at": "2026-08-01T10:00:00",
      "last_watched_at": "2026-08-09T14:30:00",
      "completed_at": null
    },
    "materials": [
      {
        "material_id": 42,
        "material_name": "Introduction to Algebra",
        "subtopic_id": 7,
        "video_duration": 3600,
        "total_watched_seconds": 1800,
        "max_position_seconds": 1750,
        "completion_percentage": 50.0,
        "status": "in_progress",
        "session_count": 3,
        "first_watched_at": "2026-08-01T10:00:00",
        "last_watched_at": "2026-08-09T14:30:00",
        "completed_at": null
      }
    ]
  }
}
```

**Subject summary rules:**
- `completion_percentage` = duration-weighted: `sum(total_watched_seconds) / sum(video_duration) × 100`
- `status` = `completed` when every video in the subject is `completed`; `in_progress` if any watch activity; otherwise `not_started`
- Only video materials (`mp4`, `webm`, `avi`, `mov`, `wmv`, `mkv`) are included

---

## Frontend integration checklist

1. On **play** → `POST /sessions/start` with `subtopic_materials.id`
2. Store `session_token` from the response
3. Every **~30s while playing** → `POST /heartbeat` with `current_position` and `watched_delta`
4. On **pause / ended / beforeunload** → `POST /end` with final delta, clear heartbeat interval
5. For progress bars → `GET /progress/{material_id}` or `GET /progress/subject/{subject_id}`

### Example player flow

```javascript
let sessionToken = null;
let heartbeatInterval = null;
let lastHeartbeatAt = Date.now();

async function onPlay(materialId) {
  const { data } = await api.post('/api/video-tracking/sessions/start', { material_id: materialId });
  sessionToken = data.data.session_token;
  lastHeartbeatAt = Date.now();

  heartbeatInterval = setInterval(async () => {
    const now = Date.now();
    const elapsed = (now - lastHeartbeatAt) / 1000;
    const delta = Math.min(elapsed, 30);
    lastHeartbeatAt = now;

    await api.post(`/api/video-tracking/sessions/${sessionToken}/heartbeat`, {
      current_position: player.currentTime,
      watched_delta: delta,
    });
  }, 30000);
}

async function onPauseOrEnd() {
  clearInterval(heartbeatInterval);
  if (!sessionToken) return;

  const elapsed = (Date.now() - lastHeartbeatAt) / 1000;
  await api.post(`/api/video-tracking/sessions/${sessionToken}/end`, {
    current_position: player.currentTime,
    watched_delta: Math.min(elapsed, 30),
  });
  sessionToken = null;
}
```

---

## Database migration

Run the Alembic migration:

```bash
alembic upgrade head
```

Revision: `d0e1f2a3b4c5_add_video_watch_tracking_tables`

Creates:
- `video_watch_sessions`
- `video_watch_progress`

---

## Courses catalog integration (Phase 2)

`GET /api/courses/approved` includes:
- `watch_progress` on each video file
- `summary` on each subject (derived on demand from those material rows)

Each subject:

```json
{
  "id": 5,
  "name": "Mathematics",
  "code": "MATH",
  "summary": {
    "video_count": 12,
    "videos_completed": 4,
    "videos_in_progress": 5,
    "videos_not_started": 3,
    "total_video_duration": 43200,
    "total_watched_seconds": 18500,
    "completion_percentage": 42.8,
    "status": "in_progress",
    "first_watched_at": "2026-08-01T10:00:00",
    "last_watched_at": "2026-08-09T14:30:00",
    "completed_at": null
  },
  "topics": []
}
```

Video materials (`mp4`, `webm`, `avi`, `mov`, `wmv`, `mkv`) include a progress object on each file:

```json
{
  "id": 42,
  "name": "Introduction to Algebra",
  "extension_type": "mp4",
  "video_duration": 3600,
  "watch_progress": {
    "total_watched_seconds": 1800,
    "max_position_seconds": 1750,
    "completion_percentage": 50.0,
    "status": "in_progress",
    "session_count": 3,
    "first_watched_at": "2026-08-01T10:00:00",
    "last_watched_at": "2026-08-09T14:30:00",
    "completed_at": null
  }
}
```

Non-video materials (PDFs, documents) have `"watch_progress": null`.

The dedicated progress endpoints remain available for refresh after playback without reloading the full catalog.

---

## Future work

- Admin drill-down and reports
- SMS segmentation by study progress
- Document/PDF read tracking

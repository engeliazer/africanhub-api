# VdoCipher Video Upload API

## Overview

This document describes how to upload videos to VdoCipher for DRM-protected streaming.

---

## Upload Endpoint

### POST `/api/study-materials/subtopic-materials/upload-vdocipher`

Upload a video file to VdoCipher and create a material record.

**Authentication:** Required (JWT token)

**Content-Type:** `multipart/form-data`

---

## Request

### Headers

```
Authorization: Bearer {JWT_TOKEN}
Content-Type: multipart/form-data
```

### Form Data

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video` | File | Yes | Video file (mp4, mov, avi, mkv, webm, flv, wmv) |
| `subtopic_id` | Integer | Yes | Subtopic ID |
| `material_category_id` | Integer | Yes | Material category ID |
| `name` | String | No | Material name (defaults to filename) |

### File Requirements

- **Formats:** mp4, mov, avi, mkv, webm, flv, wmv
- **Max Size:** 5GB
- **Recommended:** H.264 video codec, AAC audio, MP4 container

---

## Response

### Success Response (201 Created)

```json
{
  "status": "success",
  "data": {
    "material_id": 123,
    "video_id": "d79887007d3247c681207a85edd1735f",
    "video_status": "processing",
    "message": "Video uploaded successfully and is being processed by VdoCipher"
  }
}
```

### Error Responses

**400 Bad Request - No file provided:**
```json
{
  "error": "No video file provided"
}
```

**400 Bad Request - Invalid file type:**
```json
{
  "error": "Invalid file type. Allowed: mp4, mov, avi, mkv, webm, flv, wmv"
}
```

**400 Bad Request - File too large:**
```json
{
  "error": "File too large. Maximum size: 5GB"
}
```

**503 Service Unavailable - VdoCipher error:**
```json
{
  "error": "Failed to initialize video upload",
  "details": "VdoCipher API error message"
}
```

---

## Frontend Integration

### React Example with Ant Design

```jsx
import { Upload, Button, message, Progress, Form, Input, Select } from 'antd';
import { UploadOutlined, VideoCameraOutlined } from '@ant-design/icons';
import axios from '../utils/axios';
import { useState } from 'react';

const VdoCipherUpload = ({ subtopicId, onUploadComplete }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [form] = Form.useForm();

  const handleUpload = async (values) => {
    const { video, name, material_category_id } = values;
    
    if (!video || !video[0]) {
      message.error('Please select a video file');
      return;
    }

    const formData = new FormData();
    formData.append('video', video[0].originFileObj);
    formData.append('subtopic_id', subtopicId);
    formData.append('material_category_id', material_category_id);
    formData.append('name', name || video[0].name);

    try {
      setUploading(true);
      
      const response = await axios.post(
        '/study-materials/subtopic-materials/upload-vdocipher',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            const percent = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            setUploadProgress(percent);
          },
        }
      );

      if (response.data.status === 'success') {
        message.success('Video uploaded successfully! Processing will take a few minutes.');
        form.resetFields();
        
        // Callback to parent component
        if (onUploadComplete) {
          onUploadComplete(response.data.data);
        }
      }
    } catch (error) {
      console.error('Upload error:', error);
      message.error(error.response?.data?.error || 'Failed to upload video');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <Form form={form} onFinish={handleUpload} layout="vertical">
      <Form.Item
        name="name"
        label="Video Name"
        rules={[{ required: true, message: 'Please enter video name' }]}
      >
        <Input placeholder="e.g. Introduction to Accounting" />
      </Form.Item>

      <Form.Item
        name="material_category_id"
        label="Category"
        rules={[{ required: true, message: 'Please select category' }]}
      >
        <Select placeholder="Select category">
          <Select.Option value={1}>Lectures</Select.Option>
          <Select.Option value={2}>Tutorials</Select.Option>
          {/* Add your categories */}
        </Select>
      </Form.Item>

      <Form.Item
        name="video"
        label="Video File"
        valuePropName="fileList"
        getValueFromEvent={(e) => e.fileList}
        rules={[{ required: true, message: 'Please select a video file' }]}
      >
        <Upload
          beforeUpload={() => false}
          maxCount={1}
          accept="video/*"
        >
          <Button icon={<UploadOutlined />}>
            Select Video File (Max 5GB)
          </Button>
        </Upload>
      </Form.Item>

      {uploading && (
        <Progress 
          percent={uploadProgress} 
          status="active"
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
      )}

      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          loading={uploading}
          icon={<VideoCameraOutlined />}
        >
          {uploading ? 'Uploading...' : 'Upload to VdoCipher (DRM Protected)'}
        </Button>
      </Form.Item>
    </Form>
  );
};

export default VdoCipherUpload;
```

---

### Simple Vanilla JavaScript Example

```javascript
const uploadToVdoCipher = async (videoFile, subtopicId, categoryId, name) => {
  const formData = new FormData();
  formData.append('video', videoFile);
  formData.append('subtopic_id', subtopicId);
  formData.append('material_category_id', categoryId);
  formData.append('name', name);

  try {
    const response = await fetch(
      'https://api.online.dcrc.ac.tz/api/study-materials/subtopic-materials/upload-vdocipher',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
          // Don't set Content-Type - browser will set it with boundary
        },
        body: formData
      }
    );

    const data = await response.json();
    
    if (data.status === 'success') {
      console.log('Upload successful!', data.data);
      return data.data;
    } else {
      throw new Error(data.error);
    }
  } catch (error) {
    console.error('Upload failed:', error);
    throw error;
  }
};

// Usage
const fileInput = document.getElementById('videoFile');
const file = fileInput.files[0];

uploadToVdoCipher(file, 123, 1, 'My Video')
  .then(result => {
    alert(`Video uploaded! Material ID: ${result.material_id}`);
  })
  .catch(error => {
    alert(`Upload failed: ${error.message}`);
  });
```

---

## Video Processing Status

After upload, the video status will be `processing`. Use this endpoint to check when it's ready:

### GET `/api/videos/{video_id}/status`

```bash
curl -X GET https://api.online.dcrc.ac.tz/api/videos/d79887007d3247c681207a85edd1735f/status \
  -H "Authorization: Bearer {JWT_TOKEN}"
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "video_id": "d79887007d3247c681207a85edd1735f",
    "status": "ready",
    "duration": 3600,
    "thumbnail": "https://...",
    "poster": "https://..."
  }
}
```

**Possible statuses:**
- `processing` - Video is being transcoded
- `ready` - Video is ready for playback
- `failed` - Processing failed

---

## Webhook Configuration

For automatic status updates, configure webhook in VdoCipher dashboard:

1. Go to **Settings** → **Webhooks**
2. Add webhook URL: `https://api.online.dcrc.ac.tz/api/webhooks/vdocipher`
3. Select events:
   - ✅ video.ready
   - ✅ video.failed
   - ✅ video.deleted

When VdoCipher finishes processing, it will automatically update the video status in your database.

---

## Complete Upload Flow

```
1. User selects video file
   ↓
2. Frontend uploads to /upload-vdocipher
   ↓
3. Backend gets VdoCipher upload credentials
   ↓
4. Backend uploads file to VdoCipher
   ↓
5. Backend creates material record (status: "processing")
   ↓
6. VdoCipher processes video (5-15 minutes)
   ↓
7. VdoCipher sends webhook (video.ready)
   ↓
8. Backend updates status to "ready"
   ↓
9. Video available for playback with DRM protection
```

---

## Testing

### Test Upload

```bash
# Using curl
curl -X POST https://api.online.dcrc.ac.tz/api/study-materials/subtopic-materials/upload-vdocipher \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "video=@/path/to/video.mp4" \
  -F "subtopic_id=1" \
  -F "material_category_id=1" \
  -F "name=Test Upload"
```

### Expected Timeline

- Upload to backend: 1-5 minutes (depending on file size)
- VdoCipher processing: 5-15 minutes (automatic)
- Total time: 6-20 minutes until video is ready

---

## Error Handling

### Frontend Should Handle:

1. **File size validation** (before upload)
   ```javascript
   if (file.size > 5 * 1024 * 1024 * 1024) {
     message.error('File too large. Maximum: 5GB');
     return;
   }
   ```

2. **File type validation**
   ```javascript
   const allowedTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo'];
   if (!allowedTypes.includes(file.type)) {
     message.error('Invalid file type');
     return;
   }
   ```

3. **Upload progress** (show percentage)

4. **Processing status** (poll or use websocket)

---

## Comparison: HLS vs VdoCipher Upload

| Feature | HLS Upload | VdoCipher Upload |
|---------|------------|------------------|
| Endpoint | `/upload` | `/upload-vdocipher` |
| DRM Protection | ❌ No | ✅ Yes |
| Screen Recording | ✅ Possible | ❌ Blocked |
| Processing | Your server (FFmpeg) | VdoCipher |
| Storage | Your server/B2 | VdoCipher CDN |
| Cost | Server costs | $50+/month |
| Use Case | Free content | Premium content |

---

## Best Practices

1. **Compress videos before upload** (save bandwidth)
   ```bash
   ffmpeg -i input.mp4 -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k output.mp4
   ```

2. **Use descriptive names** for videos

3. **Set `requires_drm = TRUE`** for premium content

4. **Monitor bandwidth usage** weekly

5. **Delete old/unused videos** to save storage

---

**Last Updated:** November 2025  
**Status:** Production Ready


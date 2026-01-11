# VdoCipher DRM Video Integration Guide

## Overview

This guide provides comprehensive instructions for integrating VdoCipher DRM video streaming into the OCPAC application. VdoCipher provides enterprise-grade video security with DRM encryption, preventing unauthorized downloads, screen recording, and piracy.

---

## Table of Contents

1. [Why VdoCipher?](#why-vdocipher)
2. [Architecture Overview](#architecture-overview)
3. [Migration Strategy](#migration-strategy)
4. [Backend Integration](#backend-integration)
5. [Frontend Integration](#frontend-integration)
6. [Video Upload Workflow](#video-upload-workflow)
7. [Webhooks & Event Handling](#webhooks--event-handling)
8. [Video Analytics](#video-analytics)
9. [Security Features](#security-features)
10. [Error Handling & Retry Logic](#error-handling--retry-logic)
11. [Testing](#testing)
12. [Monitoring & Maintenance](#monitoring--maintenance)
13. [Pricing & Cost Optimization](#pricing--cost-optimization)
14. [Troubleshooting](#troubleshooting)

---

## Why VdoCipher?

### Key Benefits:
- ✅ **DRM Protection**: Widevine, FairPlay, PlayReady encryption
- ✅ **Screen Recording Block**: OS-level protection on mobile devices
- ✅ **Dynamic Watermarking**: User-specific watermarks to deter piracy
- ✅ **Global CDN**: Fast video delivery worldwide
- ✅ **Automatic Encoding**: Multiple quality levels (360p, 480p, 720p, 1080p)
- ✅ **Analytics**: View tracking, engagement metrics, device info
- ✅ **Mobile SDKs**: Native iOS and Android support
- ✅ **Easy Integration**: Simple API and player libraries

### Use Cases:
- Educational content (study materials, lectures)
- Premium course videos
- Exam preparation materials
- Instructor training videos

---

## Architecture Overview

```
┌─────────────────┐
│   VdoCipher     │
│   Dashboard     │◄─── Upload videos manually or via API
└────────┬────────┘
         │
         │ Video ID
         ▼
┌─────────────────┐
│   Backend API   │
│  (Flask/Django) │
│                 │
│  - Store video  │
│    metadata     │
│  - Generate OTP │
│  - Control      │
│    access       │
└────────┬────────┘
         │
         │ OTP + Playback Info
         ▼
┌─────────────────┐
│   Frontend      │
│   (React)       │
│                 │
│  - VdoCipher    │
│    Player       │
│  - DRM playback │
└─────────────────┘
```

---

## Migration Strategy

### Current System vs. VdoCipher

**Current System:**
- Videos uploaded to your server
- FFmpeg processing for HLS
- Stored in local/B2 storage
- Custom video player
- ❌ No DRM protection
- ❌ Screen recording possible

**VdoCipher System:**
- Videos uploaded to VdoCipher
- Automatic transcoding
- Stored in VdoCipher's CDN
- VdoCipher player
- ✅ DRM protection
- ✅ Screen recording blocked

---

### Migration Options

#### Option 1: Full Migration (Recommended for New Projects)

**Pros:**
- Complete DRM protection
- Simplified infrastructure
- Better security

**Cons:**
- Need to re-upload all videos
- Higher monthly costs
- Vendor lock-in

**Steps:**
1. Upload all existing videos to VdoCipher
2. Update database with VdoCipher video IDs
3. Update frontend to use VdoCipher player
4. Deprecate old HLS system
5. Clean up old video files

---

#### Option 2: Hybrid Approach (Recommended for Cost Optimization)

**Strategy:**
- **Premium/Paid Content** → VdoCipher (DRM protected)
- **Free/Preview Content** → Your HLS system (cheaper)

**Implementation:**
```python
# Add field to subtopic_materials table
ALTER TABLE subtopic_materials ADD COLUMN requires_drm BOOLEAN DEFAULT FALSE;

# In your video player logic
def get_video_player_config(material_id):
    material = SubtopicMaterial.query.get(material_id)
    
    if material.requires_drm and material.vdocipher_video_id:
        return {
            'player_type': 'vdocipher',
            'video_id': material.vdocipher_video_id
        }
    else:
        return {
            'player_type': 'hls',
            'video_url': material.material_path
        }
```

**Frontend:**
```jsx
// VideoPlayer.jsx
const VideoPlayer = ({ material }) => {
  if (material.requires_drm && material.vdocipher_video_id) {
    return <VdoCipherPlayer videoId={material.vdocipher_video_id} />;
  } else {
    return <HLSPlayer videoUrl={material.material_path} />;
  }
};
```

---

#### Option 3: Gradual Migration

**Timeline:**
1. **Month 1**: Set up VdoCipher, upload 10 test videos
2. **Month 2**: Migrate premium courses (high-value content)
3. **Month 3**: Migrate remaining paid content
4. **Month 4**: Evaluate costs, decide on free content

**Tracking:**
```sql
-- Track migration progress
CREATE TABLE video_migration_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    material_id BIGINT NOT NULL,
    old_video_path VARCHAR(500),
    vdocipher_video_id VARCHAR(255),
    migration_status ENUM('pending', 'in_progress', 'completed', 'failed'),
    migrated_at DATETIME,
    migrated_by BIGINT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES subtopic_materials(id)
);
```

---

## Backend Integration

### 1. Setup & Configuration

#### Install VdoCipher Python SDK:
```bash
pip install vdocipher
```

#### Environment Variables:
```bash
# .env file
VDOCIPHER_API_SECRET=your_api_secret_here
VDOCIPHER_CLIENT_ID=your_client_id_here
```

---

### 2. Database Schema

Add video fields to your `subtopic_materials` or `study_materials` table:

```sql
ALTER TABLE subtopic_materials ADD COLUMN vdocipher_video_id VARCHAR(255);
ALTER TABLE subtopic_materials ADD COLUMN video_duration INTEGER;
ALTER TABLE subtopic_materials ADD COLUMN video_status VARCHAR(50) DEFAULT 'processing';
ALTER TABLE subtopic_materials ADD COLUMN video_thumbnail_url TEXT;
ALTER TABLE subtopic_materials ADD COLUMN video_poster_url TEXT;

-- Video status values: 'processing', 'ready', 'failed'
```

---

### 3. Backend API Endpoints

#### **3.1. Upload Video to VdoCipher**

```python
# services/vdocipher_service.py
import requests
import os
from typing import Dict, Optional

class VdoCipherService:
    BASE_URL = "https://dev.vdocipher.com/api"
    
    def __init__(self):
        self.api_secret = os.getenv('VDOCIPHER_API_SECRET')
        self.headers = {
            'Authorization': f'Apisecret {self.api_secret}',
            'Content-Type': 'application/json'
        }
    
    def upload_video(self, title: str, folder_id: Optional[str] = None) -> Dict:
        """
        Get upload credentials for a new video
        
        Args:
            title: Video title
            folder_id: Optional VdoCipher folder ID
            
        Returns:
            Upload credentials including videoId and upload URL
        """
        url = f"{self.BASE_URL}/videos"
        payload = {
            "title": title,
            "folderId": folder_id
        }
        
        response = requests.put(url, json=payload, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_video_details(self, video_id: str) -> Dict:
        """
        Get video details including status, duration, thumbnails
        
        Args:
            video_id: VdoCipher video ID
            
        Returns:
            Video details
        """
        url = f"{self.BASE_URL}/videos/{video_id}"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def generate_otp(self, video_id: str, user_id: int, user_email: str, 
                     user_name: str, ip_address: str = None) -> Dict:
        """
        Generate OTP and playback info for video playback
        
        Args:
            video_id: VdoCipher video ID
            user_id: Application user ID
            user_email: User email for watermarking
            user_name: User name for watermarking
            ip_address: Optional IP address restriction
            
        Returns:
            OTP and playback info
        """
        url = f"{self.BASE_URL}/videos/{video_id}/otp"
        
        payload = {
            "annotate": json.dumps([
                {
                    "type": "rtext",
                    "text": f"{user_name} ({user_email})",
                    "alpha": "0.60",
                    "color": "0xFF0000",
                    "size": "15",
                    "interval": "5000"
                }
            ])
        }
        
        # Optional: Restrict to specific IP
        if ip_address:
            payload["ip"] = ip_address
        
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def delete_video(self, video_id: str) -> bool:
        """
        Delete video from VdoCipher
        
        Args:
            video_id: VdoCipher video ID
            
        Returns:
            Success status
        """
        url = f"{self.BASE_URL}/videos/{video_id}"
        
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()
        
        return True
```

---

#### **3.2. Flask API Routes**

```python
# routes/videos.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.vdocipher_service import VdoCipherService
from models import SubtopicMaterial, db

videos_bp = Blueprint('videos', __name__)
vdocipher = VdoCipherService()

@videos_bp.route('/api/videos/upload-credentials', methods=['POST'])
@jwt_required()
def get_upload_credentials():
    """
    Get VdoCipher upload credentials
    
    Request Body:
    {
        "title": "Introduction to Accounting",
        "subtopic_id": 123,
        "material_id": 456
    }
    
    Response:
    {
        "videoId": "abc123xyz",
        "clientPayload": {...},
        "uploadLink": "https://..."
    }
    """
    data = request.get_json()
    title = data.get('title')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    try:
        # Get upload credentials from VdoCipher
        upload_data = vdocipher.upload_video(title)
        
        # Store video metadata in database
        material_id = data.get('material_id')
        if material_id:
            material = SubtopicMaterial.query.get(material_id)
            if material:
                material.vdocipher_video_id = upload_data['videoId']
                material.video_status = 'processing'
                db.session.commit()
        
        return jsonify({
            'status': 'success',
            'data': upload_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@videos_bp.route('/api/videos/<video_id>/otp', methods=['POST'])
@jwt_required()
def get_video_otp(video_id):
    """
    Generate OTP for video playback
    
    Response:
    {
        "otp": "20160313versASE323lhsgYHwdh",
        "playbackInfo": "eyJ2aWRlb0lkIjoiM2Y...",
        "user": {
            "id": 123,
            "name": "John Doe",
            "email": "john@example.com"
        }
    }
    """
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user has access to this video
        material = SubtopicMaterial.query.filter_by(
            vdocipher_video_id=video_id
        ).first()
        
        if not material:
            return jsonify({'error': 'Video not found'}), 404
        
        # Check user enrollment/payment status
        if not user.has_access_to_material(material.id):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get user IP address
        ip_address = request.remote_addr
        
        # Generate OTP
        otp_data = vdocipher.generate_otp(
            video_id=video_id,
            user_id=user.id,
            user_email=user.email,
            user_name=f"{user.first_name} {user.last_name}",
            ip_address=ip_address
        )
        
        # Log video access
        log_video_access(user.id, video_id, material.id)
        
        return jsonify({
            'status': 'success',
            'data': {
                'otp': otp_data['otp'],
                'playbackInfo': otp_data['playbackInfo'],
                'user': {
                    'id': user.id,
                    'name': f"{user.first_name} {user.last_name}",
                    'email': user.email
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@videos_bp.route('/api/videos/<video_id>/status', methods=['GET'])
@jwt_required()
def get_video_status(video_id):
    """
    Get video processing status
    
    Response:
    {
        "status": "ready",
        "duration": 3600,
        "thumbnail": "https://...",
        "poster": "https://..."
    }
    """
    try:
        # Get video details from VdoCipher
        video_data = vdocipher.get_video_details(video_id)
        
        # Update database
        material = SubtopicMaterial.query.filter_by(
            vdocipher_video_id=video_id
        ).first()
        
        if material:
            material.video_status = video_data.get('status', 'processing')
            material.video_duration = video_data.get('length', 0)
            material.video_thumbnail_url = video_data.get('thumbnail')
            material.video_poster_url = video_data.get('poster')
            db.session.commit()
        
        return jsonify({
            'status': 'success',
            'data': {
                'status': video_data.get('status'),
                'duration': video_data.get('length'),
                'thumbnail': video_data.get('thumbnail'),
                'poster': video_data.get('poster')
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@videos_bp.route('/api/videos/<int:material_id>', methods=['DELETE'])
@jwt_required()
def delete_video(material_id):
    """
    Delete video from VdoCipher and database
    """
    try:
        material = SubtopicMaterial.query.get(material_id)
        
        if not material:
            return jsonify({'error': 'Material not found'}), 404
        
        if not material.vdocipher_video_id:
            return jsonify({'error': 'No video associated'}), 400
        
        # Delete from VdoCipher
        vdocipher.delete_video(material.vdocipher_video_id)
        
        # Update database
        material.vdocipher_video_id = None
        material.video_status = None
        material.video_duration = None
        material.video_thumbnail_url = None
        material.video_poster_url = None
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Video deleted successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

#### **3.3. Access Control Helper**

```python
# models/user.py
class User(db.Model):
    # ... existing fields ...
    
    def has_access_to_material(self, material_id: int) -> bool:
        """
        Check if user has access to a specific study material
        
        Args:
            material_id: Study material ID
            
        Returns:
            True if user has access, False otherwise
        """
        material = SubtopicMaterial.query.get(material_id)
        
        if not material:
            return False
        
        # Check if user has an approved and paid application for this subject
        application = SeasonApplication.query.filter_by(
            user_id=self.id,
            status='approved',
            payment_status='paid'
        ).join(
            SeasonApplicationDetail
        ).filter(
            SeasonApplicationDetail.subject_id == material.subject_id
        ).first()
        
        return application is not None
```

---

## Frontend Integration

### 1. Install VdoCipher React Player

```bash
npm install @vdocipher/react-player
```

---

### 2. Create VdoCipher Player Component

```jsx
// src/components/VdoCipherPlayer.jsx
import React, { useEffect, useState } from 'react';
import VdoPlayer from '@vdocipher/react-player';
import { Spin, Alert, message } from 'antd';
import axios from '../utils/axios';

const VdoCipherPlayer = ({ videoId, materialId, onVideoEnd }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [otp, setOtp] = useState(null);
  const [playbackInfo, setPlaybackInfo] = useState(null);

  useEffect(() => {
    fetchVideoOTP();
  }, [videoId]);

  const fetchVideoOTP = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await axios.post(`/api/videos/${videoId}/otp`);

      if (response.data.status === 'success') {
        setOtp(response.data.data.otp);
        setPlaybackInfo(response.data.data.playbackInfo);
      } else {
        throw new Error('Failed to get video credentials');
      }
    } catch (err) {
      console.error('Error fetching video OTP:', err);
      setError(err.response?.data?.error || 'Failed to load video');
      message.error('Failed to load video. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVideoEnd = () => {
    console.log('Video ended');
    if (onVideoEnd) {
      onVideoEnd();
    }
  };

  const handleTimeUpdate = (currentTime) => {
    // Track video progress
    console.log('Current time:', currentTime);
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>Loading video...</div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        message="Error Loading Video"
        description={error}
        type="error"
        showIcon
      />
    );
  }

  return (
    <div className="vdocipher-player-container">
      <VdoPlayer
        otp={otp}
        playbackInfo={playbackInfo}
        theme="9ae8bbe8dd964ddc9bdb932cca1cb59a"
        onEnded={handleVideoEnd}
        onTimeUpdate={handleTimeUpdate}
        controls={true}
        autoplay={false}
      />
      
      <style jsx>{`
        .vdocipher-player-container {
          width: 100%;
          max-width: 100%;
          margin: 0 auto;
          background: #000;
          border-radius: 8px;
          overflow: hidden;
        }
        
        @media (max-width: 768px) {
          .vdocipher-player-container {
            border-radius: 0;
          }
        }
      `}</style>
    </div>
  );
};

export default VdoCipherPlayer;
```

---

### 3. Integrate into Study Materials Page

```jsx
// src/pages/studies/SubtopicMaterialsList.jsx
import VdoCipherPlayer from '../../components/VdoCipherPlayer';

const SubtopicMaterialsList = () => {
  // ... existing code ...

  const handleViewVideo = (material) => {
    setSelectedMaterial(material);
    setVideoModalVisible(true);
  };

  return (
    <>
      {/* ... existing code ... */}
      
      {/* Video Modal */}
      <Modal
        title={selectedMaterial?.title}
        open={videoModalVisible}
        onCancel={() => setVideoModalVisible(false)}
        footer={null}
        width="90%"
        style={{ top: 20 }}
        bodyStyle={{ padding: 0 }}
      >
        {selectedMaterial?.vdocipher_video_id && (
          <VdoCipherPlayer
            videoId={selectedMaterial.vdocipher_video_id}
            materialId={selectedMaterial.id}
            onVideoEnd={() => {
              message.success('Video completed!');
              // Track completion
            }}
          />
        )}
      </Modal>
    </>
  );
};
```

---

## Video Upload Workflow

### Option 1: Manual Upload via VdoCipher Dashboard

1. **Login** to VdoCipher dashboard
2. **Upload** video files
3. **Copy** video ID
4. **Update** database with video ID

```sql
UPDATE subtopic_materials 
SET vdocipher_video_id = 'abc123xyz',
    video_status = 'ready'
WHERE id = 123;
```

---

### Option 2: Programmatic Upload via API

#### Backend Upload Endpoint:

```python
@videos_bp.route('/api/videos/upload', methods=['POST'])
@jwt_required()
def upload_video_file():
    """
    Upload video file to VdoCipher
    
    This is a two-step process:
    1. Get upload credentials
    2. Upload file using credentials
    """
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    video_file = request.files['video']
    title = request.form.get('title')
    material_id = request.form.get('material_id')
    
    try:
        # Step 1: Get upload credentials
        upload_data = vdocipher.upload_video(title)
        video_id = upload_data['videoId']
        upload_link = upload_data['uploadLink']
        
        # Step 2: Upload file to VdoCipher
        files = {'file': video_file}
        upload_response = requests.put(
            upload_link,
            files=files,
            headers={'x-amz-acl': 'private'}
        )
        upload_response.raise_for_status()
        
        # Step 3: Update database
        if material_id:
            material = SubtopicMaterial.query.get(material_id)
            if material:
                material.vdocipher_video_id = video_id
                material.video_status = 'processing'
                db.session.commit()
        
        return jsonify({
            'status': 'success',
            'data': {
                'videoId': video_id,
                'status': 'processing'
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Webhooks & Event Handling

VdoCipher sends webhooks when video processing completes, fails, or other events occur.

### 1. Configure Webhook URL

In VdoCipher Dashboard:
1. Go to **Settings** → **Webhooks**
2. Add webhook URL: `https://api.online.dcrc.ac.tz/api/webhooks/vdocipher`
3. Select events to receive

---

### 2. Implement Webhook Handler

```python
# routes/webhooks.py
from flask import Blueprint, request, jsonify
import hmac
import hashlib
from models import SubtopicMaterial, db
from datetime import datetime

webhooks_bp = Blueprint('webhooks', __name__)

def verify_vdocipher_signature(payload, signature):
    """
    Verify webhook signature from VdoCipher
    
    Args:
        payload: Request body as bytes
        signature: X-VdoCipher-Signature header value
        
    Returns:
        True if signature is valid
    """
    secret = os.getenv('VDOCIPHER_WEBHOOK_SECRET')
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@webhooks_bp.route('/api/webhooks/vdocipher', methods=['POST'])
def handle_vdocipher_webhook():
    """
    Handle webhooks from VdoCipher
    
    Events:
    - video.ready: Video processing completed
    - video.failed: Video processing failed
    - video.deleted: Video was deleted
    """
    # Verify signature
    signature = request.headers.get('X-VdoCipher-Signature')
    if not verify_vdocipher_signature(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json()
    event_type = data.get('event')
    video_id = data.get('videoId')
    
    try:
        material = SubtopicMaterial.query.filter_by(
            vdocipher_video_id=video_id
        ).first()
        
        if not material:
            return jsonify({'error': 'Material not found'}), 404
        
        if event_type == 'video.ready':
            # Video processing completed successfully
            material.video_status = 'ready'
            material.video_duration = data.get('length', 0)
            material.video_thumbnail_url = data.get('thumbnail')
            material.video_poster_url = data.get('poster')
            
            # Log event
            print(f"✅ Video {video_id} is ready for material {material.id}")
            
        elif event_type == 'video.failed':
            # Video processing failed
            material.video_status = 'failed'
            error_message = data.get('error', 'Unknown error')
            
            # Log error
            print(f"❌ Video {video_id} processing failed: {error_message}")
            
            # Optionally notify admin
            # send_admin_notification(f"Video processing failed: {material.title}")
            
        elif event_type == 'video.deleted':
            # Video was deleted from VdoCipher
            material.vdocipher_video_id = None
            material.video_status = None
            
            print(f"🗑️ Video {video_id} was deleted")
        
        material.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        print(f"Error handling webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```

---

### 3. Register Webhook Blueprint

```python
# app.py
from routes.webhooks import webhooks_bp

app.register_blueprint(webhooks_bp)
```

---

### 4. Test Webhook

```bash
# Test webhook locally with ngrok
ngrok http 5000

# Update VdoCipher webhook URL to ngrok URL
# Upload a test video and watch for webhook events
```

---

## Video Analytics

Track video views, watch time, and completion rates.

### 1. Database Schema

```sql
CREATE TABLE video_analytics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    material_id BIGINT NOT NULL,
    video_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    watch_duration INTEGER DEFAULT 0,
    total_duration INTEGER,
    completion_percentage INTEGER DEFAULT 0,
    last_position INTEGER DEFAULT 0,
    device_type VARCHAR(50),
    browser VARCHAR(100),
    ip_address VARCHAR(45),
    started_at DATETIME NOT NULL,
    last_updated_at DATETIME NOT NULL,
    completed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_video (user_id, video_id),
    INDEX idx_material (material_id),
    INDEX idx_session (session_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (material_id) REFERENCES subtopic_materials(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 2. Analytics Model

```python
# models/video_analytics.py
from database.db_connector import Base
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey
from datetime import datetime

class VideoAnalytics(Base):
    __tablename__ = 'video_analytics'
    
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    material_id = Column(BigInteger, ForeignKey('subtopic_materials.id'), nullable=False)
    video_id = Column(String(255), nullable=False)
    session_id = Column(String(255), nullable=False)
    watch_duration = Column(Integer, default=0)
    total_duration = Column(Integer)
    completion_percentage = Column(Integer, default=0)
    last_position = Column(Integer, default=0)
    device_type = Column(String(50))
    browser = Column(String(100))
    ip_address = Column(String(45))
    started_at = Column(DateTime, nullable=False)
    last_updated_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

### 3. Analytics API Endpoints

```python
# routes/video_analytics.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import VideoAnalytics, db
from datetime import datetime
import uuid

analytics_bp = Blueprint('video_analytics', __name__)

@analytics_bp.route('/api/analytics/video/start', methods=['POST'])
@jwt_required()
def start_video_session():
    """
    Track video session start
    
    Request:
    {
        "video_id": "abc123",
        "material_id": 456,
        "total_duration": 3600
    }
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    session_id = str(uuid.uuid4())
    
    analytics = VideoAnalytics(
        user_id=user_id,
        material_id=data['material_id'],
        video_id=data['video_id'],
        session_id=session_id,
        total_duration=data.get('total_duration', 0),
        device_type=request.user_agent.platform,
        browser=request.user_agent.browser,
        ip_address=request.remote_addr,
        started_at=datetime.utcnow(),
        last_updated_at=datetime.utcnow()
    )
    
    db.session.add(analytics)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'session_id': session_id
    }), 200


@analytics_bp.route('/api/analytics/video/progress', methods=['POST'])
@jwt_required()
def update_video_progress():
    """
    Update video watch progress
    
    Request:
    {
        "session_id": "uuid",
        "current_position": 1800,
        "watch_duration": 1800
    }
    """
    data = request.get_json()
    session_id = data['session_id']
    
    analytics = VideoAnalytics.query.filter_by(
        session_id=session_id
    ).first()
    
    if not analytics:
        return jsonify({'error': 'Session not found'}), 404
    
    analytics.last_position = data['current_position']
    analytics.watch_duration = data['watch_duration']
    
    if analytics.total_duration > 0:
        analytics.completion_percentage = int(
            (data['current_position'] / analytics.total_duration) * 100
        )
    
    analytics.last_updated_at = datetime.utcnow()
    
    # Mark as completed if watched 90% or more
    if analytics.completion_percentage >= 90 and not analytics.completed_at:
        analytics.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'status': 'success'}), 200


@analytics_bp.route('/api/analytics/video/stats/<int:material_id>', methods=['GET'])
@jwt_required()
def get_video_stats(material_id):
    """
    Get video statistics for a material
    
    Response:
    {
        "total_views": 150,
        "unique_viewers": 45,
        "avg_watch_duration": 2400,
        "completion_rate": 75.5,
        "total_watch_time": 360000
    }
    """
    from sqlalchemy import func
    
    stats = db.session.query(
        func.count(VideoAnalytics.id).label('total_views'),
        func.count(func.distinct(VideoAnalytics.user_id)).label('unique_viewers'),
        func.avg(VideoAnalytics.watch_duration).label('avg_watch_duration'),
        func.avg(VideoAnalytics.completion_percentage).label('avg_completion'),
        func.sum(VideoAnalytics.watch_duration).label('total_watch_time')
    ).filter(
        VideoAnalytics.material_id == material_id
    ).first()
    
    return jsonify({
        'status': 'success',
        'data': {
            'total_views': stats.total_views or 0,
            'unique_viewers': stats.unique_viewers or 0,
            'avg_watch_duration': int(stats.avg_watch_duration or 0),
            'completion_rate': round(stats.avg_completion or 0, 2),
            'total_watch_time': stats.total_watch_time or 0
        }
    }), 200
```

---

### 4. Frontend Analytics Integration

```jsx
// VdoCipherPlayer.jsx
import { useEffect, useRef, useState } from 'react';
import axios from '../utils/axios';

const VdoCipherPlayer = ({ videoId, materialId, totalDuration }) => {
  const [sessionId, setSessionId] = useState(null);
  const progressIntervalRef = useRef(null);
  
  useEffect(() => {
    // Start analytics session
    startAnalyticsSession();
    
    return () => {
      // Cleanup on unmount
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, [videoId]);
  
  const startAnalyticsSession = async () => {
    try {
      const response = await axios.post('/api/analytics/video/start', {
        video_id: videoId,
        material_id: materialId,
        total_duration: totalDuration
      });
      
      setSessionId(response.data.session_id);
    } catch (error) {
      console.error('Failed to start analytics session:', error);
    }
  };
  
  const updateProgress = async (currentTime, watchDuration) => {
    if (!sessionId) return;
    
    try {
      await axios.post('/api/analytics/video/progress', {
        session_id: sessionId,
        current_position: Math.floor(currentTime),
        watch_duration: Math.floor(watchDuration)
      });
    } catch (error) {
      console.error('Failed to update progress:', error);
    }
  };
  
  const handleTimeUpdate = (currentTime) => {
    // Update progress every 30 seconds
    if (!progressIntervalRef.current) {
      let watchDuration = 0;
      
      progressIntervalRef.current = setInterval(() => {
        watchDuration += 30;
        updateProgress(currentTime, watchDuration);
      }, 30000);
    }
  };
  
  const handleVideoEnd = () => {
    // Final progress update
    updateProgress(totalDuration, totalDuration);
    
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }
  };
  
  return (
    <VdoPlayer
      otp={otp}
      playbackInfo={playbackInfo}
      onTimeUpdate={handleTimeUpdate}
      onEnded={handleVideoEnd}
    />
  );
};
```

---

## Security Features

### 1. Dynamic Watermarking

VdoCipher automatically adds user-specific watermarks to videos:

```python
# In generate_otp method
payload = {
    "annotate": json.dumps([
        {
            "type": "rtext",  # Rolling text
            "text": f"{user_name} ({user_email})",
            "alpha": "0.60",  # Transparency
            "color": "0xFF0000",  # Red color
            "size": "15",  # Font size
            "interval": "5000"  # Show every 5 seconds
        }
    ])
}
```

### 2. IP Restriction (Optional)

Restrict video playback to specific IP addresses:

```python
payload["ip"] = user_ip_address
```

### 3. Time-Limited Access

OTP expires after a certain time (default: 20 minutes):

```python
# OTP is automatically time-limited by VdoCipher
# No additional configuration needed
```

### 4. Domain Whitelisting

Configure in VdoCipher dashboard:
- Go to Settings → Security
- Add allowed domains: `online.dcrc.ac.tz`

---

## Error Handling & Retry Logic

### 1. VdoCipher Service with Retry

```python
# services/vdocipher_service.py
import requests
import time
from typing import Dict, Optional
from functools import wraps

def retry_on_failure(max_retries=3, delay=2):
    """
    Decorator to retry failed API calls
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        print(f"All {max_retries} attempts failed")
            
            raise last_exception
        return wrapper
    return decorator


class VdoCipherService:
    BASE_URL = "https://dev.vdocipher.com/api"
    
    def __init__(self):
        self.api_secret = os.getenv('VDOCIPHER_API_SECRET')
        if not self.api_secret:
            raise ValueError("VDOCIPHER_API_SECRET not set in environment")
        
        self.headers = {
            'Authorization': f'Apisecret {self.api_secret}',
            'Content-Type': 'application/json'
        }
    
    @retry_on_failure(max_retries=3, delay=2)
    def upload_video(self, title: str, folder_id: Optional[str] = None) -> Dict:
        """Upload video with retry logic"""
        url = f"{self.BASE_URL}/videos"
        payload = {
            "title": title,
            "folderId": folder_id
        }
        
        try:
            response = requests.put(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise Exception("VdoCipher API timeout")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Invalid VdoCipher API credentials")
            elif e.response.status_code == 429:
                raise Exception("VdoCipher rate limit exceeded")
            else:
                raise Exception(f"VdoCipher API error: {e.response.text}")
    
    @retry_on_failure(max_retries=3, delay=2)
    def generate_otp(self, video_id: str, user_id: int, user_email: str, 
                     user_name: str, ip_address: str = None) -> Dict:
        """Generate OTP with retry logic"""
        url = f"{self.BASE_URL}/videos/{video_id}/otp"
        
        payload = {
            "annotate": json.dumps([
                {
                    "type": "rtext",
                    "text": f"{user_name} ({user_email})",
                    "alpha": "0.60",
                    "color": "0xFF0000",
                    "size": "15",
                    "interval": "5000"
                }
            ])
        }
        
        if ip_address:
            payload["ip"] = ip_address
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Video {video_id} not found in VdoCipher")
            else:
                raise Exception(f"Failed to generate OTP: {e.response.text}")
```

---

### 2. Error Handling in Routes

```python
# routes/videos.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest, NotFound, Forbidden
import logging

logger = logging.getLogger(__name__)
videos_bp = Blueprint('videos', __name__)

@videos_bp.errorhandler(Exception)
def handle_error(error):
    """Global error handler for videos blueprint"""
    logger.error(f"Error in videos route: {str(error)}", exc_info=True)
    
    if isinstance(error, BadRequest):
        return jsonify({'error': str(error)}), 400
    elif isinstance(error, NotFound):
        return jsonify({'error': 'Resource not found'}), 404
    elif isinstance(error, Forbidden):
        return jsonify({'error': 'Access denied'}), 403
    else:
        return jsonify({'error': 'Internal server error'}), 500


@videos_bp.route('/api/videos/<video_id>/otp', methods=['POST'])
@jwt_required()
def get_video_otp(video_id):
    """Generate OTP with comprehensive error handling"""
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            raise NotFound('User not found')
        
        # Find material
        material = SubtopicMaterial.query.filter_by(
            vdocipher_video_id=video_id
        ).first()
        
        if not material:
            raise NotFound('Video not found')
        
        # Check video status
        if material.video_status != 'ready':
            return jsonify({
                'error': 'Video is not ready for playback',
                'status': material.video_status
            }), 425  # Too Early
        
        # Check access
        if not user.has_access_to_material(material.id):
            raise Forbidden('You do not have access to this video')
        
        # Generate OTP
        try:
            otp_data = vdocipher.generate_otp(
                video_id=video_id,
                user_id=user.id,
                user_email=user.email,
                user_name=f"{user.first_name} {user.last_name}",
                ip_address=request.remote_addr
            )
        except Exception as e:
            logger.error(f"Failed to generate OTP for video {video_id}: {str(e)}")
            return jsonify({
                'error': 'Failed to generate video credentials',
                'details': str(e)
            }), 503  # Service Unavailable
        
        # Log access
        log_video_access(user.id, video_id, material.id)
        
        return jsonify({
            'status': 'success',
            'data': {
                'otp': otp_data['otp'],
                'playbackInfo': otp_data['playbackInfo']
            }
        }), 200
        
    except (NotFound, Forbidden) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_video_otp: {str(e)}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500
```

---

### 3. Frontend Error Handling

```jsx
// VdoCipherPlayer.jsx
const VdoCipherPlayer = ({ videoId, materialId }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const MAX_RETRIES = 3;
  
  const fetchVideoOTP = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.post(`/api/videos/${videoId}/otp`);
      
      if (response.data.status === 'success') {
        setOtp(response.data.data.otp);
        setPlaybackInfo(response.data.data.playbackInfo);
        setRetryCount(0);
      }
    } catch (err) {
      console.error('Error fetching video OTP:', err);
      
      const errorMessage = err.response?.data?.error || 'Failed to load video';
      const statusCode = err.response?.status;
      
      // Handle specific error codes
      if (statusCode === 403) {
        setError('You do not have access to this video. Please check your enrollment status.');
      } else if (statusCode === 404) {
        setError('Video not found. Please contact support.');
      } else if (statusCode === 425) {
        setError('Video is still processing. Please try again in a few minutes.');
        // Retry after delay
        if (retryCount < MAX_RETRIES) {
          setTimeout(() => {
            setRetryCount(retryCount + 1);
            fetchVideoOTP();
          }, 10000); // Retry after 10 seconds
        }
      } else if (statusCode === 503) {
        setError('Video service temporarily unavailable. Please try again later.');
      } else {
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };
  
  if (error) {
    return (
      <Alert
        message="Error Loading Video"
        description={
          <div>
            <p>{error}</p>
            {retryCount < MAX_RETRIES && (
              <Button onClick={() => fetchVideoOTP()} type="primary">
                Retry
              </Button>
            )}
          </div>
        }
        type="error"
        showIcon
      />
    );
  }
  
  // ... rest of component
};
```

---

## Testing

### 1. Test Video Upload

```bash
# Get upload credentials
curl -X POST https://api.online.dcrc.ac.tz/api/videos/upload-credentials \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Video",
    "material_id": 123
  }'
```

### 2. Test OTP Generation

```bash
# Get OTP for video playback
curl -X POST https://api.online.dcrc.ac.tz/api/videos/VIDEO_ID/otp \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. Test Video Status

```bash
# Check video processing status
curl -X GET https://api.online.dcrc.ac.tz/api/videos/VIDEO_ID/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Monitoring & Maintenance

### 1. Health Check Endpoint

```python
# routes/health.py
from flask import Blueprint, jsonify
from services.vdocipher_service import VdoCipherService
import requests

health_bp = Blueprint('health', __name__)

@health_bp.route('/api/health/vdocipher', methods=['GET'])
def check_vdocipher_health():
    """
    Check VdoCipher API connectivity
    
    Response:
    {
        "status": "healthy",
        "vdocipher_api": "reachable",
        "response_time_ms": 150
    }
    """
    import time
    
    try:
        start_time = time.time()
        
        # Test API connection
        vdocipher = VdoCipherService()
        response = requests.get(
            f"{vdocipher.BASE_URL}/videos",
            headers=vdocipher.headers,
            params={'limit': 1},
            timeout=5
        )
        
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return jsonify({
                'status': 'healthy',
                'vdocipher_api': 'reachable',
                'response_time_ms': round(response_time, 2)
            }), 200
        else:
            return jsonify({
                'status': 'degraded',
                'vdocipher_api': 'error',
                'error': f'Status code: {response.status_code}'
            }), 503
            
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'vdocipher_api': 'unreachable',
            'error': str(e)
        }), 503
```

---

### 2. Monitoring Dashboard Metrics

Track these metrics in your admin dashboard:

```python
# routes/admin_analytics.py
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from models import SubtopicMaterial, VideoAnalytics, db
from sqlalchemy import func
from datetime import datetime, timedelta

admin_analytics_bp = Blueprint('admin_analytics', __name__)

@admin_analytics_bp.route('/api/admin/video-metrics', methods=['GET'])
@jwt_required()
def get_video_metrics():
    """
    Get comprehensive video metrics for admin dashboard
    
    Response:
    {
        "total_videos": 150,
        "videos_by_status": {
            "ready": 140,
            "processing": 8,
            "failed": 2
        },
        "total_views_today": 450,
        "total_views_this_month": 12500,
        "avg_completion_rate": 78.5,
        "top_videos": [...]
    }
    """
    today = datetime.utcnow().date()
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    
    # Total videos count
    total_videos = SubtopicMaterial.query.filter(
        SubtopicMaterial.vdocipher_video_id.isnot(None)
    ).count()
    
    # Videos by status
    videos_by_status = db.session.query(
        SubtopicMaterial.video_status,
        func.count(SubtopicMaterial.id)
    ).filter(
        SubtopicMaterial.vdocipher_video_id.isnot(None)
    ).group_by(SubtopicMaterial.video_status).all()
    
    # Views today
    views_today = VideoAnalytics.query.filter(
        func.date(VideoAnalytics.started_at) == today
    ).count()
    
    # Views this month
    views_this_month = VideoAnalytics.query.filter(
        VideoAnalytics.started_at >= month_start
    ).count()
    
    # Average completion rate
    avg_completion = db.session.query(
        func.avg(VideoAnalytics.completion_percentage)
    ).scalar() or 0
    
    # Top 10 most viewed videos
    top_videos = db.session.query(
        SubtopicMaterial.id,
        SubtopicMaterial.title,
        func.count(VideoAnalytics.id).label('view_count')
    ).join(
        VideoAnalytics,
        VideoAnalytics.material_id == SubtopicMaterial.id
    ).group_by(
        SubtopicMaterial.id,
        SubtopicMaterial.title
    ).order_by(
        func.count(VideoAnalytics.id).desc()
    ).limit(10).all()
    
    return jsonify({
        'status': 'success',
        'data': {
            'total_videos': total_videos,
            'videos_by_status': dict(videos_by_status),
            'total_views_today': views_today,
            'total_views_this_month': views_this_month,
            'avg_completion_rate': round(avg_completion, 2),
            'top_videos': [
                {
                    'id': v[0],
                    'title': v[1],
                    'views': v[2]
                }
                for v in top_videos
            ]
        }
    }), 200
```

---

### 3. Automated Monitoring Script

```python
# scripts/monitor_videos.py
"""
Cron job to monitor video processing status
Run every 5 minutes: */5 * * * * python scripts/monitor_videos.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_connector import db_session
from models import SubtopicMaterial
from services.vdocipher_service import VdoCipherService
from datetime import datetime, timedelta

def check_stuck_videos():
    """Check for videos stuck in processing state"""
    vdocipher = VdoCipherService()
    
    # Find videos in processing state for more than 2 hours
    two_hours_ago = datetime.utcnow() - timedelta(hours=2)
    
    stuck_videos = SubtopicMaterial.query.filter(
        SubtopicMaterial.video_status == 'processing',
        SubtopicMaterial.updated_at < two_hours_ago
    ).all()
    
    for material in stuck_videos:
        try:
            # Check actual status from VdoCipher
            video_data = vdocipher.get_video_details(material.vdocipher_video_id)
            
            # Update status
            material.video_status = video_data.get('status', 'processing')
            material.video_duration = video_data.get('length', 0)
            material.video_thumbnail_url = video_data.get('thumbnail')
            material.video_poster_url = video_data.get('poster')
            material.updated_at = datetime.utcnow()
            
            db_session.commit()
            
            print(f"✅ Updated video {material.id}: {material.video_status}")
            
        except Exception as e:
            print(f"❌ Error checking video {material.id}: {str(e)}")
            continue

if __name__ == "__main__":
    print(f"🔍 Checking stuck videos at {datetime.utcnow()}")
    check_stuck_videos()
    print("✅ Monitoring complete")
```

---

### 4. Bandwidth Usage Tracking

```python
# scripts/track_bandwidth.py
"""
Track bandwidth usage for cost monitoring
Run daily: 0 0 * * * python scripts/track_bandwidth.py
"""

import requests
import os
from datetime import datetime

def get_vdocipher_usage():
    """Fetch bandwidth usage from VdoCipher API"""
    api_secret = os.getenv('VDOCIPHER_API_SECRET')
    
    headers = {
        'Authorization': f'Apisecret {api_secret}',
        'Content-Type': 'application/json'
    }
    
    # Get usage stats
    response = requests.get(
        'https://dev.vdocipher.com/api/usage',
        headers=headers
    )
    
    if response.status_code == 200:
        usage_data = response.json()
        
        print(f"📊 VdoCipher Usage Report - {datetime.utcnow().date()}")
        print(f"Bandwidth used: {usage_data.get('bandwidth_gb', 0)} GB")
        print(f"Storage used: {usage_data.get('storage_gb', 0)} GB")
        print(f"Total videos: {usage_data.get('total_videos', 0)}")
        
        # Alert if approaching limit
        bandwidth_limit = 500  # GB for starter plan
        bandwidth_used = usage_data.get('bandwidth_gb', 0)
        
        if bandwidth_used > bandwidth_limit * 0.8:
            print(f"⚠️  WARNING: Bandwidth usage at {(bandwidth_used/bandwidth_limit)*100:.1f}%")
            # Send alert email/notification
            
        return usage_data
    else:
        print(f"❌ Failed to fetch usage: {response.text}")
        return None

if __name__ == "__main__":
    get_vdocipher_usage()
```

---

## Pricing & Cost Optimization

### VdoCipher Pricing (2024)

| Plan | Price | Bandwidth | Storage | Features |
|------|-------|-----------|---------|----------|
| Starter | $50/month | 500 GB | 100 GB | DRM, Watermark, Analytics |
| Growth | $150/month | 2 TB | 500 GB | + API Access, Priority Support |
| Business | $500/month | 10 TB | 2 TB | + White Label, Custom Domain |
| Enterprise | Custom | Custom | Custom | + Dedicated Support, SLA |

**Additional Costs:**
- Overage: $0.10/GB bandwidth, $0.05/GB storage
- API calls: Included in all plans

---

### Cost Optimization Strategies

#### 1. Video Compression

**Before uploading to VdoCipher:**

```bash
# Use FFmpeg to compress videos
ffmpeg -i input.mp4 \
  -c:v libx264 \
  -crf 23 \
  -preset medium \
  -c:a aac \
  -b:a 128k \
  -movflags +faststart \
  output.mp4

# Recommended settings:
# - Resolution: 1280x720 (720p) for most content
# - CRF: 23 (good quality/size balance)
# - Audio: 128kbps AAC
```

**Expected savings:**
- Original 1080p video: ~500 MB/hour
- Compressed 720p video: ~200 MB/hour
- **60% bandwidth savings**

---

#### 2. Hybrid Approach (Recommended)

```python
# Cost comparison example:
# 100 students × 10 hours video/month = 1,000 viewing hours

# Full VdoCipher:
# 1,000 hours × 200 MB = 200 GB bandwidth
# Cost: $50/month (within Starter plan)

# Hybrid (50% free content on your server):
# 500 hours × 200 MB = 100 GB on VdoCipher
# 500 hours × 200 MB = 100 GB on your server (free)
# Cost: $50/month VdoCipher + $5/month server bandwidth = $55/month
# But: Free content has no DRM protection

# Recommendation: Use VdoCipher only for premium paid content
```

---

#### 3. Delete Old/Unused Videos

```python
# Script to identify unused videos
# scripts/cleanup_old_videos.py

from datetime import datetime, timedelta
from models import SubtopicMaterial, VideoAnalytics
from services.vdocipher_service import VdoCipherService

def find_unused_videos(days=90):
    """Find videos not viewed in X days"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get videos with no recent views
    unused_videos = SubtopicMaterial.query.filter(
        SubtopicMaterial.vdocipher_video_id.isnot(None),
        ~SubtopicMaterial.id.in_(
            db.session.query(VideoAnalytics.material_id).filter(
                VideoAnalytics.started_at >= cutoff_date
            )
        )
    ).all()
    
    print(f"Found {len(unused_videos)} videos not viewed in {days} days")
    
    for video in unused_videos:
        print(f"- {video.title} (ID: {video.id}, Last updated: {video.updated_at})")
    
    return unused_videos

# Run monthly to identify candidates for deletion
```

---

#### 4. Bandwidth Usage Estimation

**Calculate your expected costs:**

```python
# Monthly bandwidth calculator

def estimate_monthly_bandwidth(
    num_students=100,
    avg_hours_per_student=10,
    video_quality_mb_per_hour=200
):
    """
    Estimate monthly bandwidth usage
    
    Args:
        num_students: Number of active students
        avg_hours_per_student: Average viewing hours per student
        video_quality_mb_per_hour: MB per hour (200 for 720p, 500 for 1080p)
    
    Returns:
        Estimated bandwidth in GB
    """
    total_hours = num_students * avg_hours_per_student
    bandwidth_mb = total_hours * video_quality_mb_per_hour
    bandwidth_gb = bandwidth_mb / 1024
    
    print(f"📊 Bandwidth Estimation:")
    print(f"Students: {num_students}")
    print(f"Avg hours/student: {avg_hours_per_student}")
    print(f"Total viewing hours: {total_hours}")
    print(f"Estimated bandwidth: {bandwidth_gb:.2f} GB")
    
    # Determine plan needed
    if bandwidth_gb <= 500:
        plan = "Starter ($50/month)"
    elif bandwidth_gb <= 2048:
        plan = "Growth ($150/month)"
    elif bandwidth_gb <= 10240:
        plan = "Business ($500/month)"
    else:
        plan = "Enterprise (Custom pricing)"
    
    print(f"Recommended plan: {plan}")
    
    return bandwidth_gb

# Example usage:
# estimate_monthly_bandwidth(num_students=200, avg_hours_per_student=15)
# Output: ~586 GB → Growth plan needed
```

---

#### 5. Adaptive Bitrate Streaming

VdoCipher automatically provides adaptive bitrate streaming, which reduces bandwidth:

- User on slow connection → Lower quality (saves bandwidth)
- User on fast connection → Higher quality
- **Average savings: 20-30% bandwidth**

---

#### 6. Content Delivery Strategy

```python
# Prioritize DRM for high-value content

class ContentStrategy:
    """Determine which content needs DRM"""
    
    @staticmethod
    def requires_drm(material):
        """
        Decide if material needs VdoCipher DRM
        
        Criteria:
        - Paid/premium content: YES
        - Exam prep materials: YES
        - Free preview/intro: NO
        - Public lectures: NO
        """
        # Premium subjects
        if material.subject.is_premium:
            return True
        
        # Free preview content
        if material.is_preview or material.is_free:
            return False
        
        # Exam-related content
        if 'exam' in material.title.lower() or 'test' in material.title.lower():
            return True
        
        # Default: use DRM for paid content
        return material.requires_payment
```

---

## Troubleshooting

### Common Issues & Solutions

#### 1. Video Stuck in "Processing" Status

**Problem:** Video uploaded but status remains "processing" for hours

**Solutions:**

```python
# Check video status directly from VdoCipher
from services.vdocipher_service import VdoCipherService

vdocipher = VdoCipherService()
video_data = vdocipher.get_video_details('VIDEO_ID')
print(f"Status: {video_data.get('status')}")
print(f"Error: {video_data.get('error')}")

# Common causes:
# 1. Video file corrupted
# 2. Unsupported codec
# 3. File too large (>5GB)
# 4. VdoCipher service issue

# Fix: Re-upload video with correct format
# Recommended: H.264 video, AAC audio, MP4 container
```

---

#### 2. OTP Generation Fails

**Problem:** `generate_otp` returns 404 or 500 error

**Solutions:**

```python
# Check if video exists in VdoCipher
try:
    video_data = vdocipher.get_video_details(video_id)
    print(f"Video found: {video_data.get('title')}")
except Exception as e:
    print(f"Video not found: {str(e)}")
    # Video might have been deleted or ID is incorrect

# Check API credentials
if not os.getenv('VDOCIPHER_API_SECRET'):
    print("❌ VDOCIPHER_API_SECRET not set")

# Test API connection
response = requests.get(
    'https://dev.vdocipher.com/api/videos',
    headers={'Authorization': f'Apisecret {api_secret}'},
    params={'limit': 1}
)
print(f"API Status: {response.status_code}")
```

---

#### 3. Player Not Loading

**Problem:** VdoCipher player shows blank screen or error

**Solutions:**

```jsx
// Check browser console for errors

// Common issues:
// 1. OTP expired (20 min lifetime)
// 2. Domain not whitelisted
// 3. CORS issues
// 4. DRM not supported on device

// Debug:
console.log('OTP:', otp);
console.log('PlaybackInfo:', playbackInfo);

// Test on different browsers:
// - Chrome/Edge: Full DRM support
// - Firefox: Full DRM support
// - Safari: FairPlay DRM support
// - Mobile browsers: Check device compatibility

// Whitelist domain in VdoCipher dashboard:
// Settings → Security → Allowed Domains
// Add: online.dcrc.ac.tz
```

---

#### 4. High Bandwidth Usage

**Problem:** Bandwidth usage higher than expected

**Investigation:**

```python
# Check top bandwidth consumers
from sqlalchemy import func

top_users = db.session.query(
    VideoAnalytics.user_id,
    func.count(VideoAnalytics.id).label('views'),
    func.sum(VideoAnalytics.watch_duration).label('total_seconds')
).group_by(
    VideoAnalytics.user_id
).order_by(
    func.sum(VideoAnalytics.watch_duration).desc()
).limit(20).all()

for user_id, views, total_seconds in top_users:
    hours = total_seconds / 3600
    print(f"User {user_id}: {views} views, {hours:.1f} hours")

# Check for:
# 1. Users repeatedly watching same video
# 2. Bots/scrapers
# 3. Shared accounts
# 4. Video quality too high (use 720p instead of 1080p)
```

---

#### 5. Webhook Not Received

**Problem:** Video processing completes but database not updated

**Solutions:**

```bash
# Test webhook endpoint
curl -X POST https://api.online.dcrc.ac.tz/api/webhooks/vdocipher \
  -H "Content-Type: application/json" \
  -H "X-VdoCipher-Signature: test" \
  -d '{
    "event": "video.ready",
    "videoId": "test123",
    "status": "ready"
  }'

# Check webhook logs
tail -f /var/log/nginx/access.log | grep webhook

# Verify webhook URL in VdoCipher dashboard
# Settings → Webhooks → Check URL is correct

# Test with ngrok for local development
ngrok http 5000
# Update webhook URL to ngrok URL temporarily
```

---

#### 6. Access Denied Error

**Problem:** User gets "Access denied" when trying to watch video

**Debug:**

```python
# Check user access
user = User.query.get(user_id)
material = SubtopicMaterial.query.get(material_id)

print(f"User: {user.email}")
print(f"Material: {material.title}")

# Check enrollment
has_access = user.has_access_to_material(material.id)
print(f"Has access: {has_access}")

# Check application status
applications = Application.query.filter_by(
    user_id=user.id,
    status='approved',
    payment_status='paid'
).all()

print(f"Active applications: {len(applications)}")

for app in applications:
    print(f"- Subject: {app.subject.name}, Status: {app.status}")
```

---

### Debug Mode

Enable detailed logging for troubleshooting:

```python
# config.py
import logging

if os.getenv('FLASK_ENV') == 'development':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Enable VdoCipher request logging
    logging.getLogger('urllib3').setLevel(logging.DEBUG)
```

---

### Support Contacts

**VdoCipher Support:**
- Email: support@vdocipher.com
- Dashboard: https://www.vdocipher.com/dashboard
- Documentation: https://www.vdocipher.com/docs/

**Response Time:**
- Starter plan: 24-48 hours
- Growth plan: 12-24 hours
- Business/Enterprise: Priority support

---

## Additional Resources

### VdoCipher Documentation:
- **API Docs**: https://www.vdocipher.com/docs/api/
- **React Player**: https://www.vdocipher.com/docs/player/react/
- **Security Guide**: https://www.vdocipher.com/docs/security/

### Support:
- **Email**: support@vdocipher.com
- **Dashboard**: https://www.vdocipher.com/dashboard

---

## Implementation Checklist

### Phase 1: Planning & Setup (Week 1)
- [ ] Review migration strategy options
- [ ] Calculate expected bandwidth costs
- [ ] Decide: Full migration vs. Hybrid approach
- [ ] Create VdoCipher account
- [ ] Get API credentials (API secret, Client ID)
- [ ] Configure domain whitelist in dashboard
- [ ] Set up billing alerts

### Phase 2: Backend Development (Week 2)
- [ ] Install VdoCipher Python SDK (`pip install vdocipher`)
- [ ] Add environment variables (`.env` file)
  - [ ] `VDOCIPHER_API_SECRET`
  - [ ] `VDOCIPHER_CLIENT_ID`
  - [ ] `VDOCIPHER_WEBHOOK_SECRET`
- [ ] Update database schema
  - [ ] Add `vdocipher_video_id` column
  - [ ] Add `video_status` column
  - [ ] Add `video_duration` column
  - [ ] Add `video_thumbnail_url` column
  - [ ] Add `video_poster_url` column
  - [ ] Add `requires_drm` column (for hybrid approach)
  - [ ] Create `video_analytics` table
  - [ ] Create `video_migration_log` table (optional)
- [ ] Implement `VdoCipherService` class
  - [ ] `upload_video()` method
  - [ ] `generate_otp()` method
  - [ ] `get_video_details()` method
  - [ ] `delete_video()` method
  - [ ] Add retry logic decorator
- [ ] Create API endpoints
  - [ ] `POST /api/videos/upload-credentials`
  - [ ] `POST /api/videos/<video_id>/otp`
  - [ ] `GET /api/videos/<video_id>/status`
  - [ ] `DELETE /api/videos/<material_id>`
  - [ ] `POST /api/webhooks/vdocipher`
  - [ ] `POST /api/analytics/video/start`
  - [ ] `POST /api/analytics/video/progress`
  - [ ] `GET /api/analytics/video/stats/<material_id>`
  - [ ] `GET /api/health/vdocipher`
- [ ] Implement access control logic
  - [ ] `user.has_access_to_material()` method
  - [ ] Check enrollment status
  - [ ] Check payment status
- [ ] Add error handling
  - [ ] Global error handler
  - [ ] Specific error codes (403, 404, 425, 503)
  - [ ] Logging
- [ ] Test API endpoints with Postman/curl

### Phase 3: Frontend Development (Week 3)
- [ ] Install VdoCipher React player
  ```bash
  npm install @vdocipher/react-player
  ```
- [ ] Create `VdoCipherPlayer` component
  - [ ] OTP fetching logic
  - [ ] Loading states
  - [ ] Error handling with retry
  - [ ] Analytics integration
- [ ] Create hybrid `VideoPlayer` component (if using hybrid approach)
  - [ ] Detect player type (VdoCipher vs. HLS)
  - [ ] Conditional rendering
- [ ] Integrate into study materials page
  - [ ] Replace existing video player
  - [ ] Add video modal/fullscreen
- [ ] Add user feedback
  - [ ] Loading spinner
  - [ ] Error messages
  - [ ] Retry button
  - [ ] Video processing status indicator
- [ ] Test video playback
  - [ ] Desktop browsers (Chrome, Firefox, Safari, Edge)
  - [ ] Mobile browsers (iOS Safari, Android Chrome)
  - [ ] Different network speeds
- [ ] Test DRM protection
  - [ ] Try screen recording (should be blocked)
  - [ ] Check watermark visibility

### Phase 4: Testing & QA (Week 4)
- [ ] Unit tests
  - [ ] VdoCipherService methods
  - [ ] API endpoints
  - [ ] Access control logic
- [ ] Integration tests
  - [ ] Video upload flow
  - [ ] OTP generation flow
  - [ ] Webhook handling
- [ ] End-to-end tests
  - [ ] User enrollment → Video access
  - [ ] Video upload → Processing → Playback
- [ ] Security testing
  - [ ] Test unauthorized access
  - [ ] Test expired OTP
  - [ ] Test domain whitelist
- [ ] Performance testing
  - [ ] Concurrent video playback
  - [ ] API response times
  - [ ] Database query optimization
- [ ] User acceptance testing
  - [ ] Test with real students
  - [ ] Gather feedback

### Phase 5: Deployment (Week 5)
- [ ] Update production environment variables
- [ ] Run database migrations
- [ ] Deploy backend code
- [ ] Deploy frontend code
- [ ] Configure webhook URL in VdoCipher dashboard
- [ ] Test in production environment
  - [ ] Upload test video
  - [ ] Generate OTP
  - [ ] Play video
  - [ ] Check webhook received
- [ ] Set up monitoring
  - [ ] Health check endpoint
  - [ ] Bandwidth usage alerts
  - [ ] Error logging
  - [ ] Analytics dashboard
- [ ] Set up cron jobs
  - [ ] Video status monitoring (`*/5 * * * *`)
  - [ ] Bandwidth tracking (`0 0 * * *`)
  - [ ] Cleanup old videos (`0 2 * * 0`)

### Phase 6: Migration (Week 6+)
- [ ] **If Full Migration:**
  - [ ] Upload all existing videos to VdoCipher
  - [ ] Update database with video IDs
  - [ ] Verify all videos processed
  - [ ] Switch frontend to VdoCipher player
  - [ ] Deprecate old HLS system
  - [ ] Clean up old video files
- [ ] **If Hybrid Approach:**
  - [ ] Identify premium content
  - [ ] Mark materials with `requires_drm = TRUE`
  - [ ] Upload premium videos to VdoCipher
  - [ ] Keep free content on existing system
  - [ ] Deploy hybrid video player
- [ ] **If Gradual Migration:**
  - [ ] Month 1: Migrate 10 test videos
  - [ ] Month 2: Migrate premium courses
  - [ ] Month 3: Migrate remaining paid content
  - [ ] Month 4: Evaluate and decide on free content

### Phase 7: Monitoring & Optimization (Ongoing)
- [ ] Monitor bandwidth usage weekly
- [ ] Review video analytics monthly
- [ ] Optimize video compression
- [ ] Delete unused videos
- [ ] Review and optimize costs
- [ ] Gather user feedback
- [ ] Update documentation

### Rollback Plan
- [ ] Document rollback procedure
- [ ] Keep old video system running for 1 month
- [ ] Test rollback in staging environment
- [ ] Have backup of all video IDs and metadata

---

## Summary & Recommendations

### ✅ Recommended Approach: Hybrid Strategy

Based on the comprehensive analysis, here's what we recommend:

**Phase 1 (Month 1-2): Pilot Program**
- Start with VdoCipher Starter plan ($50/month)
- Migrate 10-20 premium videos
- Test with real students
- Monitor bandwidth usage
- Gather feedback

**Phase 2 (Month 3-4): Expand Premium Content**
- Migrate all exam prep materials
- Migrate high-value course content
- Keep free previews on existing system
- Implement hybrid video player

**Phase 3 (Month 5+): Optimize & Scale**
- Review costs vs. value
- Optimize video compression
- Delete unused content
- Consider upgrading plan if needed

### 💰 Expected Costs

**Scenario 1: 100 Students, 10 hours/month each**
- Bandwidth: ~195 GB
- Plan: Starter ($50/month)
- **Total: $50/month**

**Scenario 2: 200 Students, 15 hours/month each**
- Bandwidth: ~586 GB
- Plan: Growth ($150/month)
- **Total: $150/month**

**Scenario 3: Hybrid (50% premium, 50% free)**
- Premium bandwidth: ~293 GB
- Plan: Starter ($50/month)
- Free content: Your server (minimal cost)
- **Total: ~$55/month**

### 🎯 Key Success Metrics

Track these to measure success:

1. **Security**: Screen recording attempts blocked
2. **User Experience**: Video load time < 3 seconds
3. **Completion Rate**: Target > 75%
4. **Bandwidth Efficiency**: Stay within plan limits
5. **Cost per Student**: Target < $0.50/student/month

### 📋 Quick Start Guide

**Week 1:**
1. Create VdoCipher account
2. Get API credentials
3. Upload 1 test video
4. Test playback

**Week 2:**
1. Implement backend API
2. Set up webhooks
3. Test OTP generation

**Week 3:**
1. Integrate frontend player
2. Test on multiple devices
3. Verify DRM protection

**Week 4:**
1. Deploy to production
2. Migrate first batch of videos
3. Monitor and optimize

---

## Questions or Issues?

**For VdoCipher:**
- Email: support@vdocipher.com
- Dashboard: https://www.vdocipher.com/dashboard
- Documentation: https://www.vdocipher.com/docs/

**For Implementation:**
- Refer to this guide
- Check troubleshooting section
- Review code examples

---

**Document Version**: 2.0  
**Last Updated**: November 2025  
**Author**: OCPAC Development Team  
**Status**: Production Ready

---

## Changelog

**v2.0 (November 2025)**
- Added migration strategy section
- Added webhooks & event handling
- Added video analytics tracking
- Added error handling & retry logic
- Added monitoring & maintenance
- Added cost optimization strategies
- Added comprehensive troubleshooting
- Updated implementation checklist
- Added phase-by-phase deployment plan

**v1.0 (October 2025)**
- Initial guide created
- Basic VdoCipher integration
- Frontend player component
- Backend API endpoints


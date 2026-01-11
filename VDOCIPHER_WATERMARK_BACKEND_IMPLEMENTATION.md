# VdoCipher Watermark Backend Implementation Guide

## Overview

This document provides instructions for implementing VdoCipher watermarking in the backend API. The frontend has been updated to send watermark information, and the backend needs to include this in the VdoCipher OTP generation request.

## Frontend Changes (Already Implemented)

The frontend now sends a `watermark` object in the OTP request payload:

```json
{
  "watermark": {
    "userName": "John Doe",
    "userEmail": "john@example.com",
    "userId": "123",
    "includeImage": true,
    "imageUrl": "https://yourdomain.com/dcrc.jpg"
  }
}
```

## Backend Implementation

### Step 1: Update OTP Endpoint to Accept Watermark Payload

Modify your `/api/videos/{materialId}/otp` endpoint to:

1. Accept the watermark payload from the request body
2. Extract user information
3. Generate the `annotate` parameter for VdoCipher's API

### Step 2: Generate Annotate Parameter

The `annotate` parameter is a JSON string that contains an array of watermark objects. VdoCipher supports:

- **Text watermarks** (`type: "rtext"` or `type: "text"`)
- **Image watermarks** (`type: "image"`)

### Example Implementation

#### Python/Flask Example:

```python
from flask import request, jsonify
import json

@videos_bp.route('/api/videos/<material_id>/otp', methods=['POST'])
@jwt_required()
def get_video_otp(material_id):
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get watermark info from request (if provided)
        request_data = request.get_json() or {}
        watermark_info = request_data.get('watermark', {})
        
        # Get material and verify access
        material = SubtopicMaterial.query.filter_by(
            id=material_id,
            vdocipher_video_id=material.vdocipher_video_id
        ).first()
        
        if not material:
            return jsonify({'error': 'Video not found'}), 404
        
        # Build annotate parameter for VdoCipher
        annotate_params = []
        
        # 1. Add text watermark with user information
        if watermark_info:
            user_name = watermark_info.get('userName') or f"{user.first_name} {user.last_name}"
            user_email = watermark_info.get('userEmail') or user.email
            user_id = watermark_info.get('userId') or str(user.id)
            
            # Rotating text watermark with user info
            annotate_params.append({
                "type": "rtext",  # Rotating text (moves across screen)
                "text": f"{user_name} ({user_email}) - ID: {user_id}",
                "alpha": "0.60",  # Transparency (0.0 to 1.0)
                "color": "0xFFFFFF",  # White color in hex
                "size": "15",  # Font size
                "interval": "5000",  # Move every 5 seconds (milliseconds)
                "skip": "5000"  # Wait 5 seconds before reappearing
            })
            
            # Optional: Add static text watermark in corner
            annotate_params.append({
                "type": "text",  # Static text
                "text": f"{user_name}",
                "alpha": "0.70",
                "color": "0xFFFFFF",
                "size": "12",
                "x": "10",  # Position from left
                "y": "10"   # Position from top
            })
        
        # 2. Add image watermark (DCRC logo) - if requested
        if watermark_info.get('includeImage') and watermark_info.get('imageUrl'):
            image_url = watermark_info.get('imageUrl')
            
            # Center the logo
            annotate_params.append({
                "type": "image",
                "url": image_url,  # Full URL to the image
                "alpha": "0.15",  # Very transparent
                "x": "50%",  # Center horizontally (can use percentage or pixels)
                "y": "50%",  # Center vertically
                "width": "150",  # Width in pixels
                "height": "150",  # Height in pixels
                "fit": "contain"  # Maintain aspect ratio
            })
        
        # Prepare VdoCipher API request payload
        vdocipher_payload = {}
        
        # Add annotate parameter if we have watermarks
        if annotate_params:
            # VdoCipher requires annotate as a JSON string
            vdocipher_payload["annotate"] = json.dumps(annotate_params)
        
        # Optional: Add IP restriction
        ip_address = request.remote_addr
        if ip_address:
            vdocipher_payload["ip"] = ip_address
        
        # Call VdoCipher API to generate OTP
        vdocipher_response = vdocipher_service.generate_otp(
            video_id=material.vdocipher_video_id,
            payload=vdocipher_payload  # Include annotate parameter
        )
        
        return jsonify({
            'status': 'success',
            'data': {
                'otp': vdocipher_response['otp'],
                'playbackInfo': vdocipher_response['playbackInfo'],
                'video': {
                    'id': material.id,
                    'name': material.name,
                    'duration': material.video_duration
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

#### Node.js/Express Example:

```javascript
router.post('/api/videos/:materialId/otp', authenticateToken, async (req, res) => {
  try {
    const { materialId } = req.params;
    const { watermark } = req.body || {};
    
    // Get current user
    const userId = req.user.id;
    const user = await User.findById(userId);
    
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    
    // Get material
    const material = await SubtopicMaterial.findOne({
      where: { id: materialId }
    });
    
    if (!material || !material.vdocipher_video_id) {
      return res.status(404).json({ error: 'Video not found' });
    }
    
    // Build annotate parameter
    const annotateParams = [];
    
    // Add text watermark
    if (watermark) {
      const userName = watermark.userName || `${user.first_name} ${user.last_name}`;
      const userEmail = watermark.userEmail || user.email;
      const userId = watermark.userId || user.id;
      
      // Rotating text watermark
      annotateParams.push({
        type: 'rtext',
        text: `${userName} (${userEmail}) - ID: ${userId}`,
        alpha: '0.60',
        color: '0xFFFFFF',
        size: '15',
        interval: '5000',
        skip: '5000'
      });
      
      // Static corner watermark
      annotateParams.push({
        type: 'text',
        text: userName,
        alpha: '0.70',
        color: '0xFFFFFF',
        size: '12',
        x: '10',
        y: '10'
      });
    }
    
    // Add image watermark
    if (watermark?.includeImage && watermark?.imageUrl) {
      annotateParams.push({
        type: 'image',
        url: watermark.imageUrl,
        alpha: '0.15',
        x: '50%',
        y: '50%',
        width: '150',
        height: '150',
        fit: 'contain'
      });
    }
    
    // Prepare VdoCipher request
    const vdocipherPayload = {};
    
    if (annotateParams.length > 0) {
      vdocipherPayload.annotate = JSON.stringify(annotateParams);
    }
    
    // Add IP restriction
    const ipAddress = req.ip || req.connection.remoteAddress;
    if (ipAddress) {
      vdocipherPayload.ip = ipAddress;
    }
    
    // Call VdoCipher API
    const vdocipherResponse = await vdocipherService.generateOTP(
      material.vdocipher_video_id,
      vdocipherPayload
    );
    
    return res.json({
      status: 'success',
      data: {
        otp: vdocipherResponse.otp,
        playbackInfo: vdocipherResponse.playbackInfo,
        video: {
          id: material.id,
          name: material.name,
          duration: material.video_duration
        }
      }
    });
    
  } catch (error) {
    console.error('Error generating OTP:', error);
    return res.status(500).json({ error: error.message });
  }
});
```

## VdoCipher Annotate Parameter Reference

### Text Watermark Options

```json
{
  "type": "rtext",  // or "text" for static
  "text": "User Name (email@example.com)",
  "alpha": "0.60",  // Transparency: 0.0 (transparent) to 1.0 (opaque)
  "color": "0xFFFFFF",  // Color in hex format (0xRRGGBB)
  "size": "15",  // Font size
  "interval": "5000",  // Movement interval in milliseconds (for rtext)
  "skip": "5000",  // Time before reappearing in milliseconds
  "x": "10",  // X position (pixels or percentage like "50%")
  "y": "10"   // Y position (pixels or percentage like "50%")
}
```

### Image Watermark Options

```json
{
  "type": "image",
  "url": "https://yourdomain.com/dcrc.jpg",  // Full URL to image
  "alpha": "0.15",  // Transparency
  "x": "50%",  // Horizontal position
  "y": "50%",  // Vertical position
  "width": "150",  // Width in pixels
  "height": "150",  // Height in pixels
  "fit": "contain"  // Image fit: "contain", "cover", or "fill"
}
```

## Important Notes

1. **JSON String Format**: The `annotate` parameter must be a JSON string, not a JSON object. Use `json.dumps()` (Python) or `JSON.stringify()` (JavaScript).

2. **Image URL**: The image URL must be:
   - Accessible from the internet (publicly accessible)
   - Served over HTTPS
   - CORS-enabled if needed
   - A valid image format (JPG, PNG, etc.)

3. **Multiple Watermarks**: You can include multiple watermark objects in the annotate array.

4. **Dynamic Placeholders**: VdoCipher supports placeholders like `{name}`, `{email}`, `{ip}`, `{date}` in text watermarks, but we're passing the actual values.

5. **Fullscreen Support**: Watermarks added via the `annotate` parameter will work in fullscreen mode, unlike client-side overlays.

## Testing

### Test the Implementation

1. **Test OTP Endpoint with Watermark**:
```bash
curl -X POST https://api.ocpac.co.tz/api/videos/1/otp \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "watermark": {
      "userName": "Test User",
      "userEmail": "test@example.com",
      "userId": "123",
      "includeImage": true,
      "imageUrl": "https://ocpac.co.tz/dcrc.jpg"
    }
  }'
```

2. **Verify Response**: The OTP should be generated successfully.

3. **Test Video Playback**: 
   - Open the video in the frontend
   - Check that watermarks appear on the video
   - Enter fullscreen mode
   - Verify watermarks are still visible

### Expected Behavior

- ✅ User name and email appear as rotating text watermark
- ✅ DCRC logo appears centered on video (if image URL is valid)
- ✅ Watermarks are visible in normal playback
- ✅ Watermarks are visible in fullscreen mode
- ✅ Watermarks persist throughout video playback

## Troubleshooting

### Watermarks Not Appearing

1. **Check VdoCipher API Response**: Verify the OTP request includes the `annotate` parameter
2. **Verify Image URL**: Ensure the image URL is publicly accessible and returns a valid image
3. **Check Annotate Format**: Ensure it's a properly formatted JSON string
4. **Review VdoCipher Dashboard**: Check if there are any errors in the VdoCipher dashboard

### Image Watermark Not Showing

1. **URL Accessibility**: Test the image URL in a browser - it should load directly
2. **HTTPS Requirement**: Ensure the image is served over HTTPS
3. **CORS Headers**: If the image is on a different domain, ensure CORS headers are set
4. **Image Format**: Verify the image is in a supported format (JPG, PNG)

### Text Watermark Issues

1. **Special Characters**: Escape special characters in the text
2. **Text Length**: Very long text might not display properly
3. **Color Format**: Ensure color is in hex format (0xRRGGBB)

## Additional Resources

- **VdoCipher Annotate Documentation**: https://www.vdocipher.com/docs/server/playbackauth/anno/
- **VdoCipher API Documentation**: https://www.vdocipher.com/docs/api/
- **VdoCipher Support**: support@vdocipher.com

## Summary

The frontend is ready and will send watermark information in the OTP request. The backend needs to:

1. ✅ Accept the `watermark` object from the request body
2. ✅ Build the `annotate` parameter array with text and/or image watermarks
3. ✅ Include the `annotate` parameter (as JSON string) in the VdoCipher OTP API request
4. ✅ Return the OTP and playbackInfo to the frontend

Once implemented, watermarks will work seamlessly in both normal and fullscreen modes!


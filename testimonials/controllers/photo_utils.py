import os
import uuid
import re
from config import UPLOAD_FOLDER

def handle_testimonial_photo_upload(photo_file, user_id):
    """
    Handle testimonial photo upload and return the URL
    """
    try:
        # Check file extension
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
        if '.' not in photo_file.filename:
            return None
        
        file_ext = photo_file.filename.rsplit('.', 1)[1].lower()
        if file_ext not in allowed_extensions:
            return None
        
        # Create testimonials directory
        testimonials_dir = os.path.join(UPLOAD_FOLDER, 'testimonials')
        os.makedirs(testimonials_dir, exist_ok=True)
        
        # Generate unique filename using user_id
        unique_id = str(uuid.uuid4())[:8]
        filename = f"user-{user_id}-{unique_id}.{file_ext}"
        
        # Save file
        file_path = os.path.join(testimonials_dir, filename)
        photo_file.save(file_path)
        
        # Return URL
        return f"https://api.ocpac.dcrc.ac.tz/storage/testimonials/{filename}"
        
    except Exception as e:
        print(f"Error uploading testimonial photo: {str(e)}")
        return None

import os
import uuid
import re
from config import UPLOAD_FOLDER

def handle_instructor_photo_upload(photo_file, instructor_name):
    """
    Handle instructor photo upload and return the URL
    """
    try:
        # Check file extension
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
        if '.' not in photo_file.filename:
            return None
        
        file_ext = photo_file.filename.rsplit('.', 1)[1].lower()
        if file_ext not in allowed_extensions:
            return None
        
        # Create instructors directory
        instructors_dir = os.path.join(UPLOAD_FOLDER, 'instructors')
        os.makedirs(instructors_dir, exist_ok=True)
        
        # Generate unique filename
        safe_name = re.sub(r'[^a-zA-Z0-9]', '-', instructor_name.lower())
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{safe_name}-{unique_id}.{file_ext}"
        
        # Save file
        file_path = os.path.join(instructors_dir, filename)
        photo_file.save(file_path)
        
        # Return URL
        return f"https://api.ocpac.dcrc.ac.tz/storage/instructors/{filename}"
        
    except Exception as e:
        print(f"Error uploading instructor photo: {str(e)}")
        return None

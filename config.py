import os

# Base directory of the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# File upload settings
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'storage', 'uploads'))
ALLOWED_EXTENSIONS = {
    # Documents
    'pdf', 'doc', 'docx', 'txt', 
    # Images
    'png', 'jpg', 'jpeg', 'gif',
    # Videos
    'mp4', 'webm', 'avi', 'mov', 'wmv', 'mkv'
}

# Ensure upload directories exist
os.makedirs(os.path.join(UPLOAD_FOLDER, 'materials'), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 
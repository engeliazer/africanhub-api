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

# Public URLs for uploaded assets served at /storage/... on the API host
API_BASE_URL = os.getenv('API_BASE_URL', 'https://africanhub-api.africanhub.ac.tz').rstrip('/')
PUBLIC_STORAGE_BASE_URL = os.getenv(
    'PUBLIC_STORAGE_BASE_URL',
    f'{API_BASE_URL}/storage',
).rstrip('/')


def public_storage_url(*path_parts: str) -> str:
    """Build a public URL for a file under /storage/<subdir>/<filename>."""
    return '/'.join([PUBLIC_STORAGE_BASE_URL, *[p.strip('/') for p in path_parts if p]])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 
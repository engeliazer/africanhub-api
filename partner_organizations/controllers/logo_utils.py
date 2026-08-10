import os
import uuid
import re
from config import UPLOAD_FOLDER

ALLOWED_LOGO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "svg"}
PUBLIC_STORAGE_BASE = os.getenv(
    "PUBLIC_STORAGE_BASE_URL",
    "https://api.ocpac.dcrc.ac.tz/storage",
)


def handle_partner_logo_upload(logo_file, organization_name: str):
    """Save partner organization logo and return its public URL."""
    try:
        if not logo_file or not logo_file.filename or "." not in logo_file.filename:
            return None

        file_ext = logo_file.filename.rsplit(".", 1)[1].lower()
        if file_ext not in ALLOWED_LOGO_EXTENSIONS:
            return None

        logos_dir = os.path.join(UPLOAD_FOLDER, "partner_organizations")
        os.makedirs(logos_dir, exist_ok=True)

        safe_name = re.sub(r"[^a-zA-Z0-9]", "-", organization_name.lower()).strip("-") or "org"
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{safe_name}-{unique_id}.{file_ext}"

        file_path = os.path.join(logos_dir, filename)
        logo_file.save(file_path)

        return f"{PUBLIC_STORAGE_BASE}/partner_organizations/{filename}"
    except Exception as e:
        print(f"Error uploading partner organization logo: {str(e)}")
        return None

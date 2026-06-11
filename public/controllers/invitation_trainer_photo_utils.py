import os
import re
import uuid

from config import UPLOAD_FOLDER


def handle_invitation_trainer_photo_upload(photo_file, trainer_name: str):
    allowed_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
    if not photo_file or not photo_file.filename or "." not in photo_file.filename:
        return None
    ext = photo_file.filename.rsplit(".", 1)[1].lower()
    if ext not in allowed_extensions:
        return None
    directory = os.path.join(UPLOAD_FOLDER, "invitation_trainers")
    os.makedirs(directory, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9]", "-", (trainer_name or "trainer").lower())
    filename = f"{safe_name}-{uuid.uuid4().hex[:8]}.{ext}"
    path = os.path.join(directory, filename)
    photo_file.save(path)
    base_url = os.getenv("PUBLIC_STORAGE_BASE_URL", "").rstrip("/")
    if base_url:
        return f"{base_url}/storage/invitation_trainers/{filename}"
    return f"/storage/invitation_trainers/{filename}"

import os
import uuid
from datetime import datetime
from typing import Optional, Tuple

from config import UPLOAD_FOLDER, public_storage_url

CERTIFICATES_DIR = "certificates"


def save_certificate_pdf(
    pdf_bytes: bytes,
    training_id: int,
    certificate_id: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Persist certificate PDF under storage/uploads/certificates/{training_id}/.
    Returns (public_url, local_path).
    """
    directory = os.path.join(UPLOAD_FOLDER, CERTIFICATES_DIR, str(training_id))
    os.makedirs(directory, exist_ok=True)

    suffix = certificate_id if certificate_id is not None else uuid.uuid4().hex[:8]
    filename = f"{suffix}.pdf"
    local_path = os.path.join(directory, filename)

    with open(local_path, "wb") as handle:
        handle.write(pdf_bytes)

    public_url = public_storage_url(CERTIFICATES_DIR, str(training_id), filename)
    return public_url, local_path

"""Optional Hub JWT: invalid or foreign tokens are treated as anonymous."""

from typing import Optional

from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request


def optional_authenticated_user_id() -> Optional[int]:
    """
    Return Hub user id when Authorization carries a valid African Hub login JWT.

    Missing Authorization → None. Invalid signature, wrong issuer, or LMS content
    JWT → None (does not 401). Required for cover/store routes used alongside the reader.
    """
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity is None:
            return None
        return int(identity)
    except Exception:
        return None

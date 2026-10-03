"""Single active login per user.

Each successful login replaces ``users.active_session_id``. The id is embedded
in the JWT as ``sid`` and returned to the client. A later check compares the
caller's session with the stored one so an older browser can be signed out.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from flask_jwt_extended import create_access_token

from auth.models.models import User


def assign_login_session(user: User) -> str:
    """Replace the user's active session id. Caller must commit."""
    session_id = str(uuid.uuid4())
    user.active_session_id = session_id
    user.updated_at = datetime.utcnow()
    return session_id


def create_login_token(user: User, session_id: str) -> str:
    return create_access_token(
        identity=str(user.id),
        additional_claims={"sid": session_id},
    )


# Frontend polls about every 10 seconds. A user counts as online for this long
# after the latest accepted check. Writes are skipped inside the shorter interval
# so the 60-second window still covers them without a row update on every poll.
ONLINE_WINDOW = timedelta(seconds=60)
HEARTBEAT_WRITE_INTERVAL = timedelta(seconds=15)


def touch_last_seen(user: User, now: Optional[datetime] = None) -> bool:
    """Record that this user's session is still active. Caller must commit."""
    now = now or datetime.utcnow()
    last_seen = user.last_seen_at
    if last_seen is not None and now - last_seen < HEARTBEAT_WRITE_INTERVAL:
        return False
    user.last_seen_at = now
    return True


def session_was_replaced(stored_session_id: Optional[str], presented_session_id: Optional[str]) -> bool:
    """
    True when this client is no longer the latest login.

    Tokens issued before session tracking have no sid. Those stay valid until
    the user logs in again, which is what first sets ``active_session_id``.
    """
    if not stored_session_id and not presented_session_id:
        return False
    return stored_session_id != presented_session_id

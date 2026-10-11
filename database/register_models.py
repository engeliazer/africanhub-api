"""
Import all SQLAlchemy model modules so relationship strings resolve in Celery workers.

Gunicorn loads app.py (which pulls in chat, auth, etc.). Celery only loads
celery_config + tasks unless we register models explicitly.
"""


def register_all_models() -> None:
    import auth.models.models  # noqa: F401
    import chat.models.models  # noqa: F401
    import applications.models.models  # noqa: F401
    import subjects.models.models  # noqa: F401
    import studies.models.models  # noqa: F401
    import books.models.models  # noqa: F401
    import certificates.models.models  # noqa: F401
    import events.models.models  # noqa: F401
    import instructors.models.models  # noqa: F401
    import partner_organizations.models.models  # noqa: F401
    import testimonials.models.models  # noqa: F401
    import video_tracking.models.models  # noqa: F401

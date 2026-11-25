"""Date rules for study periods.

The end date is inclusive: a student who starts on day 0 with N allocated days
can study through start + N days, and is blocked on the following day.
"""

from datetime import date, timedelta
from typing import Any, Optional, Sequence


PERIOD_INITIAL = "initial"
PERIOD_EXTENSION = "extension"

STUDY_NOT_STARTED = "study_not_started"
STUDY_PERIOD_ENDED = "study_period_ended"
EXTENSION_LIMIT_REACHED = "extension_limit_reached"
MAX_EXTENSIONS = 3


def root_application_id(application_id: int, original_application_id: Optional[int]) -> int:
    """The enrollment application that extensions stay linked to."""
    return original_application_id or application_id


def extensions_remaining(existing_count: int, maximum: int = MAX_EXTENSIONS) -> int:
    if existing_count < 0:
        existing_count = 0
    return max(0, maximum - existing_count)


class StudyAccessError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def expected_end_date(start_date: date, allocated_days: int) -> date:
    if allocated_days is None or allocated_days <= 0:
        raise StudyAccessError("Allocated days must be greater than zero")
    return start_date + timedelta(days=int(allocated_days))


def period_covers(start_date: date, end_date: date, on_date: date) -> bool:
    return start_date <= on_date <= end_date


def extension_start_date(latest_end: Optional[date], today: date) -> date:
    """Where an approved extension window begins.

    The new window starts the day after a period that is still open, so
    remaining days are kept. A period that has already ended starts today.
    """
    if latest_end is not None and latest_end >= today:
        return latest_end + timedelta(days=1)
    return today


def _field(period: Any, name: str):
    if isinstance(period, dict):
        return period[name]
    return getattr(period, name)


def classify_study_window(
    periods: Sequence[Any],
    today: date,
    duration_days: Optional[int],
) -> dict:
    """Describe whether the student can study from the logged periods."""
    covering = [
        period for period in periods
        if period_covers(_field(period, "start_date"), _field(period, "expected_end_date"), today)
    ]
    if covering:
        period = max(covering, key=lambda item: _field(item, "expected_end_date"))
        return {
            "status": "active",
            "can_study": True,
            "period": period,
            "days_remaining": (_field(period, "expected_end_date") - today).days,
            "access_expired": False,
        }

    if periods:
        period = max(periods, key=lambda item: _field(item, "expected_end_date"))
        return {
            "status": "expired",
            "can_study": False,
            "period": period,
            "days_remaining": 0,
            "access_expired": True,
        }

    return {
        "status": "not_started",
        "can_study": False,
        "period": None,
        "days_remaining": duration_days,
        "access_expired": False,
    }

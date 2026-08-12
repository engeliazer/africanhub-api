from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EventParticipantUserInput(BaseModel):
    user_id: int
    organization: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class EventParticipantGuestInput(BaseModel):
    full_name: str
    salutation_id: Optional[int] = None
    organization: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("full_name is required for walk-in participants")
        return normalized


class EventParticipantInput(BaseModel):
    user_id: Optional[int] = None
    full_name: Optional[str] = None
    salutation_id: Optional[int] = None
    organization: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_identity(self):
        has_user = self.user_id is not None
        has_guest_name = bool((self.full_name or "").strip())
        if has_user and has_guest_name:
            raise ValueError("Provide either user_id or full_name, not both")
        if not has_user and not has_guest_name:
            raise ValueError("Either user_id or full_name is required")
        if has_guest_name:
            self.full_name = self.full_name.strip()
        return self


class EventParticipantBulkInput(BaseModel):
    participants: List[EventParticipantInput] = Field(min_length=1)


class EventParticipantUpdateInput(BaseModel):
    full_name: Optional[str] = None
    salutation_id: Optional[int] = None
    organization: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("full_name cannot be empty")
        return normalized


def event_participant_payload(
    participant: Any,
    *,
    user: Any = None,
    salutation: Any = None,
    display_full_name: Optional[str] = None,
    core_name: Optional[str] = None,
) -> Dict[str, Any]:
    is_walk_in = participant.user_id is None
    return {
        "participant_id": participant.id,
        "event_id": participant.event_id,
        "participant_type": "walk_in" if is_walk_in else "user",
        "user_id": participant.user_id,
        "full_name": display_full_name,
        "core_name": core_name,
        "salutation_id": participant.salutation_id if is_walk_in else (
            user.salutation_id if user is not None else None
        ),
        "salutation": salutation.label if salutation else None,
        "organization": participant.organization,
        "email": participant.email,
        "phone": participant.phone,
        "notes": participant.notes,
        "created_at": participant.created_at.isoformat() if participant.created_at else None,
        "updated_at": participant.updated_at.isoformat() if participant.updated_at else None,
    }

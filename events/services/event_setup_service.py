"""
Event setup wizard — step completion and publish readiness.
"""

from typing import Any, Dict, List

from applications.models.models import InvitationTrainer
from events.models.models import Event


def _missing_event_info_fields(event: Event) -> List[str]:
    missing = []
    if not (event.course_description or "").strip():
        missing.append("course_description")
    if not (event.learning_outcomes or "").strip():
        missing.append("learning_outcomes")
    if not event.start_time:
        missing.append("start_time")
    if not event.end_time:
        missing.append("end_time")
    return missing


def _missing_payment_fields(event: Event) -> List[str]:
    missing = []
    if event.course_fee is None:
        missing.append("course_fee")
    if not (event.bank_account_name or "").strip():
        missing.append("bank_account_name")
    if not (event.bank_account_number or "").strip():
        missing.append("bank_account_number")
    if not (event.bank_name or "").strip():
        missing.append("bank_name")
    return missing


def _active_trainer_count(event: Event, db) -> int:
    if not event.trainer_assignments:
        return 0
    trainer_ids = [a.trainer_id for a in event.trainer_assignments]
    return (
        db.query(InvitationTrainer)
        .filter(InvitationTrainer.id.in_(trainer_ids))
        .filter(InvitationTrainer.is_active == True)
        .count()
    )


def _step_event_info(event: Event) -> Dict[str, Any]:
    missing = _missing_event_info_fields(event)
    return {
        "key": "event_info",
        "label": "Event details",
        "order": 1,
        "required": True,
        "completed": len(missing) == 0,
        "missing": missing,
        "hint": "Add course description, learning outcomes, and session times.",
    }


def _step_payment(event: Event) -> Dict[str, Any]:
    missing = _missing_payment_fields(event)
    return {
        "key": "payment",
        "label": "Payment & bank details",
        "order": 2,
        "required": True,
        "completed": len(missing) == 0,
        "missing": missing,
        "hint": "Set course fee and bank account details (deposit and deadline are optional).",
    }


def _step_trainers(event: Event, db) -> Dict[str, Any]:
    count = _active_trainer_count(event, db)
    missing = [] if count > 0 else ["trainer_ids"]
    return {
        "key": "trainers",
        "label": "Assign trainers",
        "order": 3,
        "required": True,
        "completed": count > 0,
        "missing": missing,
        "trainer_count": count,
        "hint": "Assign at least one active trainer via trainer_ids.",
    }


def _step_invitation_letter(event: Event) -> Dict[str, Any]:
    has_custom = bool(event.invitation_template_path)
    return {
        "key": "invitation_letter",
        "label": "Invitation letter template",
        "order": 4,
        "required": False,
        "completed": has_custom,
        "skipped": not has_custom,
        "missing": [] if has_custom else ["template"],
        "uses_default_template": not has_custom,
        "hint": "Optional — upload a custom HTML template or use the built-in default.",
    }


def _step_publish(event: Event) -> Dict[str, Any]:
    return {
        "key": "publish",
        "label": "Publish to website",
        "order": 5,
        "required": True,
        "completed": bool(event.is_published),
        "missing": [] if event.is_published else ["is_published"],
        "hint": "Set is_published to true when all required steps above are complete.",
    }


def build_event_setup(event: Event, db, *, detailed: bool = True) -> Dict[str, Any]:
    steps = [
        _step_event_info(event),
        _step_payment(event),
        _step_trainers(event, db),
        _step_invitation_letter(event),
        _step_publish(event),
    ]

    required_steps = [s for s in steps if s["required"] and s["key"] != "publish"]
    required_complete = all(s["completed"] for s in required_steps)
    current = next((s for s in steps if s["required"] and not s["completed"]), None)
    if not current and not event.is_published:
        current = _step_publish(event)

    completed_count = sum(1 for s in steps if s["completed"])

    setup: Dict[str, Any] = {
        "ready_to_publish": required_complete and not event.is_published,
        "is_published": bool(event.is_published),
        "current_step": current["key"] if current else None,
        "current_step_label": current["label"] if current else None,
        "completed_steps": completed_count,
        "total_steps": len(steps),
        "required_steps_complete": required_complete,
    }

    if detailed:
        setup["steps"] = steps
        if not required_complete:
            setup["blocking_publish"] = [
                field
                for step in required_steps
                if not step["completed"]
                for field in ([step["key"]] + step.get("missing", []))
            ]
    else:
        setup["next_missing"] = current["missing"] if current else []

    return setup

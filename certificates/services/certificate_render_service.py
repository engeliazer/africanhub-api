from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from certificates.models.models import (
    Certificate,
    CertificateParticipant,
    CertificateTemplate,
    CertificateTrainingContext,
)
from certificates.services.certificate_renderer import (
    CertificateRenderer,
    format_cert_number,
    format_display_date,
)
from certificates.services.participant_service import (
    ParticipantIdentity,
    compute_qualifies_for_cpd,
    get_salutation_by_id,
    get_salutation_for_user,
    get_training_context_or_error,
    get_user_or_error,
    resolve_certificate_participant_identity,
)
from events.models.models import EventParticipant
from events.services.event_participant_service import participant_display_names


def get_participant_or_error(
    db: Session,
    context_id: int,
    participant_id: int,
) -> Tuple[Optional[CertificateParticipant], Optional[str]]:
    row = (
        db.query(CertificateParticipant)
        .filter(
            CertificateParticipant.id == participant_id,
            CertificateParticipant.training_context_id == context_id,
            CertificateParticipant.deleted_at.is_(None),
        )
        .first()
    )
    if not row:
        return None, "Participant not found on this training context"
    return row, None


def get_event_participant_or_error(
    db: Session,
    event_id: int,
    event_participant_id: int,
) -> Tuple[Optional[EventParticipant], Optional[str]]:
    row = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.id == event_participant_id,
            EventParticipant.event_id == event_id,
            EventParticipant.deleted_at.is_(None),
        )
        .first()
    )
    if not row:
        return None, "Event participant not found on this training calendar event"
    return row, None


def resolve_event_participant_identity(
    db: Session,
    event_participant: EventParticipant,
) -> Tuple[Optional[ParticipantIdentity], Optional[str]]:
    user = None
    salutation = None
    if event_participant.user_id is not None:
        user, user_error = get_user_or_error(db, event_participant.user_id)
        if user_error:
            return None, user_error
        salutation = get_salutation_for_user(db, user)
    else:
        salutation = get_salutation_by_id(db, event_participant.salutation_id)
        if event_participant.salutation_id and salutation is None:
            return None, f"Salutation {event_participant.salutation_id} not found or inactive"
        if not (event_participant.full_name or "").strip():
            return None, "Walk-in event participant is missing full_name"

    _, display_name = participant_display_names(event_participant, user, salutation)
    return ParticipantIdentity(
        display_name=display_name,
        salutation=salutation,
        qualifies_for_cpd_override=None,
        user_id=event_participant.user_id,
        source="event",
        source_id=event_participant.id,
    ), None


def resolve_render_participant(
    db: Session,
    context: CertificateTrainingContext,
    participant_id: int,
    *,
    source: Optional[str] = None,
) -> Tuple[Optional[ParticipantIdentity], Optional[CertificateParticipant], Optional[str]]:
    normalized_source = (source or "certificate").strip().lower()

    if normalized_source == "event":
        if context.training_type != "event":
            return None, None, "source=event is only valid for event training contexts"
        event_participant, event_error = get_event_participant_or_error(
            db,
            context.training_id,
            participant_id,
        )
        if event_error:
            return None, None, event_error
        identity, identity_error = resolve_event_participant_identity(db, event_participant)
        return identity, None, identity_error

    certificate_participant, participant_error = get_participant_or_error(
        db,
        context.id,
        participant_id,
    )
    if certificate_participant:
        identity, identity_error = resolve_certificate_participant_identity(
            db,
            certificate_participant,
            context,
        )
        return identity, certificate_participant, identity_error

    if context.training_type == "event":
        event_participant, event_error = get_event_participant_or_error(
            db,
            context.training_id,
            participant_id,
        )
        if event_participant:
            identity, identity_error = resolve_event_participant_identity(db, event_participant)
            if identity_error:
                return None, None, identity_error
            return identity, None, None

    return None, None, (
        "Participant not found on this certificate roster. "
        "For events, either import the training calendar roster "
        "(POST .../participants/import-event-roster) or preview with "
        "?source=event using the event participant id."
    )


def get_template_with_signatories(
    db: Session,
    template_id: int,
) -> Tuple[Optional[CertificateTemplate], Optional[str]]:
    row = (
        db.query(CertificateTemplate)
        .options(joinedload(CertificateTemplate.signatories))
        .filter(
            CertificateTemplate.id == template_id,
            CertificateTemplate.deleted_at.is_(None),
            CertificateTemplate.is_active == True,
        )
        .first()
    )
    if not row:
        return None, "Certificate template not found or inactive"
    return row, None


def _resolve_signatories(
    template: CertificateTemplate,
    context: CertificateTrainingContext,
) -> List[Dict[str, Any]]:
    override = context.signatory_override or []
    if override:
        return [
            {
                "display_order": int(item.get("display_order", index + 1)),
                "full_name": item.get("full_name") or "",
                "title": item.get("title") or "",
                "signature_url": item.get("signature_url"),
            }
            for index, item in enumerate(override)
        ]

    return [
        {
            "display_order": row.display_order,
            "full_name": row.full_name,
            "title": row.title,
            "signature_url": row.signature_url,
        }
        for row in sorted(template.signatories, key=lambda item: (item.display_order, item.id))
    ]


def _next_certificate_sequence(db: Session, context_id: int) -> int:
    count = (
        db.query(Certificate.id)
        .filter(
            Certificate.training_context_id == context_id,
            Certificate.deleted_at.is_(None),
        )
        .count()
    )
    return count + 1


def build_render_data(
    db: Session,
    context: CertificateTrainingContext,
    identity: ParticipantIdentity,
    *,
    certificate_participant: Optional[CertificateParticipant] = None,
    preview: bool = False,
    sequence: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    template, template_error = get_template_with_signatories(
        db,
        context.certificate_template_id,
    )
    if template_error:
        return None, template_error

    override = None
    if certificate_participant is not None:
        override = certificate_participant.qualifies_for_cpd_override

    qualifies_for_cpd = compute_qualifies_for_cpd(
        identity.salutation,
        context,
        override if override is not None else identity.qualifies_for_cpd_override,
    )

    start_text = format_display_date(context.start_date)
    end_text = format_display_date(context.end_date)
    venue_line = (template.venue_template or "held at {venue}").format(
        venue=context.venue_text,
    )

    if qualifies_for_cpd:
        date_line = ""
        cpd_line = (template.cpd_template or "").format(
            start_date=start_text,
            end_date=end_text,
            cpd_hours=context.cpd_hours,
            venue=context.venue_text,
        )
    else:
        date_line = (template.date_template or "from {start_date} to {end_date}").format(
            start_date=start_text,
            end_date=end_text,
            venue=context.venue_text,
            cpd_hours=context.cpd_hours,
        )
        cpd_line = ""

    seq = sequence if sequence is not None else _next_certificate_sequence(db, context.id)
    cert_number = format_cert_number(
        context.cert_number_pattern,
        home_code=context.home_code,
        invited_code=context.invited_code,
        start_date=context.start_date,
        training_id=context.training_id,
        sequence=seq,
        preview=preview,
    )

    is_collaboration = context.host_mode == "collaboration"

    render_data = {
        "preview": preview,
        "certificate_title": template.certificate_title,
        "participant_name": identity.display_name,
        "participation_line": template.participation_prefix or "Participated in the training on",
        "subject_title": context.subject_title,
        "venue_line": venue_line,
        "date_line": date_line,
        "cpd_line": cpd_line,
        "qualifies_for_cpd": qualifies_for_cpd,
        "cert_number": cert_number,
        "show_home_logo": bool(context.home_logo_url),
        "show_invited_logo": bool(is_collaboration and context.invited_logo_url),
        "home_logo_url": context.home_logo_url,
        "invited_logo_url": context.invited_logo_url,
        "signatories": _resolve_signatories(template, context),
        "template": {
            "background_url": template.background_url,
            "field_layout": template.field_layout,
        },
        "meta": {
            "training_context_id": context.id,
            "training_id": context.training_id,
            "training_type": context.training_type,
            "participant_id": certificate_participant.id if certificate_participant else None,
            "participant_source": identity.source,
            "participant_source_id": identity.source_id,
            "user_id": identity.user_id,
            "qualifies_for_cpd": qualifies_for_cpd,
            "cert_number": cert_number,
        },
    }
    return render_data, None


def render_participant_certificate_pdf(
    db: Session,
    context_id: int,
    participant_id: int,
    *,
    preview: bool = False,
    source: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[Dict[str, Any]], Optional[str]]:
    context, context_error = get_training_context_or_error(db, context_id)
    if context_error:
        return None, None, context_error

    identity, certificate_participant, resolve_error = resolve_render_participant(
        db,
        context,
        participant_id,
        source=source,
    )
    if resolve_error:
        return None, None, resolve_error

    if preview and certificate_participant is None and identity.source == "event":
        pass

    render_data, build_error = build_render_data(
        db,
        context,
        identity,
        certificate_participant=certificate_participant,
        preview=preview,
    )
    if build_error:
        return None, None, build_error

    pdf_bytes = CertificateRenderer(render_data).render_pdf_bytes()
    return pdf_bytes, render_data.get("meta"), None

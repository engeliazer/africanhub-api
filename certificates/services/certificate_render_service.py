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
    compute_qualifies_for_cpd,
    format_user_full_name,
    get_salutation_for_user,
    get_training_context_or_error,
    get_user_or_error,
)


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
    participant: CertificateParticipant,
    *,
    preview: bool = False,
    sequence: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    template, template_error = get_template_with_signatories(
        db,
        context.certificate_template_id,
    )
    if template_error:
        return None, template_error

    user, user_error = get_user_or_error(db, participant.user_id)
    if user_error:
        return None, user_error

    salutation = get_salutation_for_user(db, user)
    participant_name = format_user_full_name(user, salutation)
    qualifies_for_cpd = compute_qualifies_for_cpd(
        salutation,
        context,
        participant.qualifies_for_cpd_override,
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
        "participant_name": participant_name,
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
            "participant_id": participant.id,
            "user_id": participant.user_id,
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
) -> Tuple[Optional[bytes], Optional[Dict[str, Any]], Optional[str]]:
    context, context_error = get_training_context_or_error(db, context_id)
    if context_error:
        return None, None, context_error

    participant, participant_error = get_participant_or_error(db, context_id, participant_id)
    if participant_error:
        return None, None, participant_error

    render_data, build_error = build_render_data(
        db,
        context,
        participant,
        preview=preview,
    )
    if build_error:
        return None, None, build_error

    pdf_bytes = CertificateRenderer(render_data).render_pdf_bytes()
    return pdf_bytes, render_data.get("meta"), None

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import SQLAlchemyError
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
    format_display_date_prose,
    layout_text_overrides,
    layout_watermark_config,
    template_watermark_settings,
)
from certificates.services.certificate_styles import (
    DEFAULT_CERTIFICATE_HEADING,
    DEFAULT_CERTIFICATE_SUBHEADING,
    DEFAULT_CERT_INTRO,
)
from certificates.services.participant_service import (
    ParticipantIdentity,
    compute_qualifies_for_cpd,
    get_training_context_or_error,
    resolve_certificate_participant_identity,
)
from certificates.services.certificate_verify_urls import build_verification_view_url
from certificates.services.serial_no_service import (
    build_participant_serial_no,
    participant_confirmation_error,
)


def get_participant_or_error(
    db: Session,
    context_id: int,
    participant_id: int,
) -> Tuple[Optional[CertificateParticipant], Optional[str]]:
    try:
        row = (
            db.query(CertificateParticipant)
            .filter(
                CertificateParticipant.id == participant_id,
                CertificateParticipant.training_context_id == context_id,
                CertificateParticipant.deleted_at.is_(None),
            )
            .first()
        )
    except SQLAlchemyError as exc:
        db.rollback()
        return None, f"Certificate roster query failed: {exc}"
    if not row:
        return None, "Participant not found on this training context"
    return row, None


def get_confirmed_participant_or_error(
    db: Session,
    context_id: int,
    participant_id: int,
) -> Tuple[Optional[CertificateParticipant], Optional[str]]:
    participant, error = get_participant_or_error(db, context_id, participant_id)
    if error:
        return None, error

    confirmation_error = participant_confirmation_error(participant)
    if confirmation_error:
        return None, confirmation_error

    return participant, None


def resolve_confirmed_certificate_participant(
    db: Session,
    context: CertificateTrainingContext,
    participant_id: int,
) -> Tuple[Optional[ParticipantIdentity], Optional[CertificateParticipant], Optional[str]]:
    participant, participant_error = get_confirmed_participant_or_error(
        db,
        context.id,
        participant_id,
    )
    if participant_error:
        return None, None, participant_error

    identity, identity_error = resolve_certificate_participant_identity(
        db,
        participant,
        context,
    )
    return identity, participant, identity_error


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
    try:
        count = (
            db.query(Certificate.id)
            .filter(
                Certificate.training_context_id == context_id,
                Certificate.deleted_at.is_(None),
            )
            .count()
        )
        return count + 1
    except Exception:
        db.rollback()
        return 1


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

    start_text = format_display_date_prose(context.start_date)
    end_text = format_display_date_prose(context.end_date)
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

    seq = 1 if preview else (sequence if sequence is not None else _next_certificate_sequence(db, context.id))
    if certificate_participant is not None and certificate_participant.serial_no:
        cert_number = certificate_participant.serial_no
    elif certificate_participant is not None:
        cert_number = build_participant_serial_no(db, context, certificate_participant.id)
    else:
        cert_number = "PREVIEW" if preview else format_cert_number(
            context.cert_number_pattern,
            home_code=context.home_code,
            invited_code=context.invited_code,
            start_date=context.start_date,
            training_id=context.training_id,
            sequence=seq,
            preview=False,
        )

    is_collaboration = context.host_mode == "collaboration"
    text_overrides = layout_text_overrides(template.field_layout)
    watermark_settings = template_watermark_settings(template)

    verification_url = None
    if cert_number and cert_number != "PREVIEW":
        verification_url = build_verification_view_url(cert_number)

    render_data = {
        "preview": preview,
        **watermark_settings,
        "certificate_heading": text_overrides.get("certificate_heading") or DEFAULT_CERTIFICATE_HEADING,
        "certificate_subheading": (
            text_overrides.get("certificate_subheading") or DEFAULT_CERTIFICATE_SUBHEADING
        ),
        "cert_intro": text_overrides.get("cert_intro") or DEFAULT_CERT_INTRO,
        "participant_name": identity.display_name,
        "participation_line": template.participation_prefix or "Participated in the training on",
        "subject_title": context.subject_title,
        "venue_line": venue_line,
        "date_line": date_line,
        "cpd_line": cpd_line,
        "qualifies_for_cpd": qualifies_for_cpd,
        "cert_number": cert_number,
        "verification_url": verification_url,
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
            "serial_no": certificate_participant.serial_no if certificate_participant else None,
            "participant_source": identity.source,
            "participant_source_id": identity.source_id,
            "participant_display_name": identity.display_name,
            "user_id": identity.user_id,
            "qualifies_for_cpd": qualifies_for_cpd,
            "cert_number": cert_number,
            "verification_url": verification_url,
            "watermark_logo_url": watermark_settings.get("watermark_logo_url"),
            "watermark_enabled": watermark_settings.get("watermark_enabled"),
            "watermark_opacity": watermark_settings.get("watermark_opacity"),
            "watermark_style": watermark_settings.get("watermark_style"),
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

    if source and source.strip().lower() not in {"", "certificate"}:
        return None, None, (
            "Preview and issuance use confirmed rows from certificate_participants only"
        )

    identity, certificate_participant, resolve_error = resolve_confirmed_certificate_participant(
        db,
        context,
        participant_id,
    )
    if resolve_error:
        return None, None, resolve_error

    render_data, build_error = build_render_data(
        db,
        context,
        identity,
        certificate_participant=certificate_participant,
        preview=preview,
    )
    if build_error:
        return None, None, build_error

    try:
        pdf_bytes = CertificateRenderer(render_data).render_pdf_bytes()
    except ValueError as exc:
        return None, None, str(exc)
    except Exception as exc:
        return None, None, f"Certificate render failed: {exc}"

    return pdf_bytes, render_data.get("meta"), None


def diagnose_certificate_preview(
    db: Session,
    context_id: int,
    participant_id: int,
    *,
    source: Optional[str] = None,
    try_render: bool = False,
) -> Dict[str, Any]:
    """JSON diagnostics for preview failures (no PDF unless try_render=true)."""
    from certificates.services.storage_path_utils import (
        read_storage_asset_bytes,
        storage_url_to_local_path,
    )

    report: Dict[str, Any] = {
        "context_id": context_id,
        "participant_id": participant_id,
        "source": "certificate",
        "checks": {},
        "ready": False,
    }

    deps = {}
    for module_name in ("pypdf", "reportlab", "PIL", "qrcode"):
        try:
            __import__(module_name)
            deps[module_name] = "ok"
        except ImportError as exc:
            deps[module_name] = f"missing: {exc}"
    report["checks"]["python_deps"] = deps

    context, context_error = get_training_context_or_error(db, context_id)
    if context_error:
        report["checks"]["training_context"] = context_error
        return report
    report["checks"]["training_context"] = "ok"
    report["training_type"] = context.training_type
    report["training_id"] = context.training_id
    report["resolved_source"] = "certificate"

    identity, certificate_participant, resolve_error = resolve_confirmed_certificate_participant(
        db,
        context,
        participant_id,
    )
    if resolve_error:
        report["checks"]["participant"] = resolve_error
        return report
    report["checks"]["participant"] = "ok"
    report["participant_source"] = identity.source
    report["participant_display_name"] = identity.display_name
    report["serial_no"] = certificate_participant.serial_no
    report["certificate_id"] = certificate_participant.certificate_id

    template, template_error = get_template_with_signatories(
        db,
        context.certificate_template_id,
    )
    if template_error:
        report["checks"]["template"] = template_error
        return report
    report["checks"]["template"] = "ok"
    report["background_url"] = template.background_url
    report["background_local_path"] = storage_url_to_local_path(template.background_url)
    wm = template_watermark_settings(template)
    report["watermark_logo_url"] = wm.get("watermark_logo_url")
    report["watermark_enabled"] = wm.get("watermark_enabled")
    report["watermark_opacity"] = wm.get("watermark_opacity")
    report["watermark_style"] = wm.get("watermark_style")
    report["watermark_local_path"] = storage_url_to_local_path(wm.get("watermark_logo_url"))
    report["checks"]["watermark_file"] = "skipped"
    if wm.get("watermark_logo_url"):
        _, wm_error = read_storage_asset_bytes(wm["watermark_logo_url"])
        if wm_error:
            report["checks"]["watermark_file"] = wm_error
            report["watermark_hint"] = (
                "Set watermark_logo_url to a real uploaded file under "
                "/storage/certificate_templates/watermarks/ — not a placeholder path."
            )
        else:
            report["checks"]["watermark_file"] = "ok"
    elif wm.get("watermark_enabled"):
        report["checks"]["watermark_file"] = "watermark_logo_url is empty"

    _, bg_error = read_storage_asset_bytes(template.background_url)
    report["checks"]["background_file"] = bg_error or "ok"

    render_data, build_error = build_render_data(
        db,
        context,
        identity,
        certificate_participant=certificate_participant,
        preview=False,
    )
    if build_error:
        report["checks"]["render_data"] = build_error
        return report
    report["checks"]["render_data"] = "ok"
    report["watermark_enabled"] = render_data.get("watermark_enabled")
    report["verification_url"] = render_data.get("verification_url")
    report["checks"]["verification_qr"] = (
        "ok"
        if render_data.get("verification_url") and deps.get("qrcode") == "ok"
        else (
            "missing qrcode package — pip install 'qrcode>=7.4.2'"
            if deps.get("qrcode") != "ok"
            else "no verification_url (participant missing serial_no)"
        )
    )

    if try_render:
        try:
            pdf_bytes = CertificateRenderer(render_data).render_pdf_bytes()
            report["checks"]["pdf_render"] = "ok"
            report["pdf_bytes"] = len(pdf_bytes)
        except Exception as exc:
            report["checks"]["pdf_render"] = str(exc)
            return report

    report["ready"] = report["checks"].get("background_file") == "ok"
    if not try_render:
        report["ready"] = report["ready"] and report["checks"].get("render_data") == "ok"
    else:
        report["ready"] = report["ready"] and report["checks"].get("pdf_render") == "ok"
    return report

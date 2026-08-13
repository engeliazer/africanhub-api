"""Issue and retrieve stored certificate PDFs for confirmed roster participants."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from certificates.controllers.certificate_file_utils import save_certificate_pdf
from certificates.models.models import (
    Certificate,
    CertificateParticipant,
    CertificateTrainingContext,
)
from certificates.services.certificate_render_service import (
    build_render_data,
    resolve_confirmed_certificate_participant,
)
from certificates.services.certificate_renderer import CertificateRenderer
from certificates.services.storage_path_utils import storage_url_to_local_path


def participant_is_issueable(participant: CertificateParticipant) -> bool:
    return (participant.confirmation_status or "").strip().lower() == "confirmed"


def get_participant_certificate(
    db: Session,
    participant: CertificateParticipant,
) -> Optional[Certificate]:
    if not participant.certificate_id:
        return None
    return (
        db.query(Certificate)
        .filter(
            Certificate.id == participant.certificate_id,
            Certificate.deleted_at.is_(None),
        )
        .first()
    )


def read_certificate_pdf_bytes(certificate: Certificate) -> Tuple[Optional[bytes], Optional[str]]:
    if not certificate.pdf_url:
        return None, "Certificate PDF file reference is missing"
    local_path = storage_url_to_local_path(certificate.pdf_url)
    if not local_path or not os.path.isfile(local_path):
        return None, "Certificate file not found"
    with open(local_path, "rb") as handle:
        return handle.read(), None


def issue_certificate_for_participant(
    db: Session,
    context: CertificateTrainingContext,
    participant: CertificateParticipant,
    current_user_id: int,
    *,
    regenerate: bool = False,
) -> Tuple[Optional[Certificate], Optional[bytes], Optional[str]]:
    if not participant_is_issueable(participant):
        return None, None, "Participant must be confirmed before a certificate can be issued"

    existing = get_participant_certificate(db, participant)
    if existing and existing.pdf_url and not regenerate:
        pdf_bytes, read_error = read_certificate_pdf_bytes(existing)
        if read_error:
            return existing, None, read_error
        return existing, pdf_bytes, None

    identity, _, identity_error = resolve_confirmed_certificate_participant(
        db,
        context,
        participant.id,
    )
    if identity_error:
        return None, None, identity_error

    render_data, build_error = build_render_data(
        db,
        context,
        identity,
        certificate_participant=participant,
        preview=False,
    )
    if build_error:
        return None, None, build_error

    meta = render_data["meta"]
    pdf_bytes = CertificateRenderer(render_data).render_pdf_bytes()

    if existing:
        certificate = existing
        certificate.cert_number = meta["cert_number"]
        certificate.qualifies_for_cpd = meta["qualifies_for_cpd"]
        certificate.updated_by = current_user_id
    else:
        certificate = Certificate(
            training_context_id=context.id,
            participant_id=participant.id,
            training_id=context.training_id,
            cert_number=meta["cert_number"],
            qualifies_for_cpd=meta["qualifies_for_cpd"],
            pdf_url="",
            created_by=current_user_id,
            updated_by=current_user_id,
        )
        db.add(certificate)
        db.flush()
        participant.certificate_id = certificate.id

    pdf_url, _ = save_certificate_pdf(
        pdf_bytes,
        context.training_id,
        certificate_id=certificate.id,
    )
    certificate.pdf_url = pdf_url
    participant.updated_by = current_user_id
    return certificate, pdf_bytes, None


def ensure_participant_certificate_issued(
    db: Session,
    context: CertificateTrainingContext,
    participant: CertificateParticipant,
    current_user_id: int,
    *,
    regenerate: bool = False,
) -> Tuple[Optional[Certificate], Optional[bytes], Optional[str]]:
    if not participant_is_issueable(participant):
        return None, None, "Participant must be confirmed before a certificate can be issued"
    return issue_certificate_for_participant(
        db,
        context,
        participant,
        current_user_id,
        regenerate=regenerate,
    )


def issue_certificates_for_participants(
    db: Session,
    context: CertificateTrainingContext,
    participants: List[CertificateParticipant],
    current_user_id: int,
) -> Tuple[List[Certificate], Optional[str]]:
    issued: List[Certificate] = []
    for participant in participants:
        if not participant_is_issueable(participant):
            continue
        if get_participant_certificate(db, participant) and participant.certificate_id:
            continue
        certificate, _, error = issue_certificate_for_participant(
            db,
            context,
            participant,
            current_user_id,
        )
        if error:
            return issued, error
        issued.append(certificate)
    return issued, None


def certificate_meta(
    certificate: Certificate,
    participant: CertificateParticipant,
    render_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = dict(render_meta or {})
    meta.update({
        "certificate_id": certificate.id,
        "cert_number": certificate.cert_number,
        "qualifies_for_cpd": certificate.qualifies_for_cpd,
        "pdf_url": certificate.pdf_url,
        "issued_at": certificate.created_at.isoformat() if certificate.created_at else None,
        "participant_id": participant.id,
        "serial_no": participant.serial_no,
    })
    return meta


def get_participant_certificate_pdf(
    db: Session,
    context_id: int,
    participant_id: int,
    current_user_id: int,
    *,
    source: Optional[str] = None,
    auto_issue: bool = True,
) -> Tuple[Optional[bytes], Optional[Dict[str, Any]], Optional[str]]:
    """
    Return the official certificate PDF for a confirmed roster participant.

    When auto_issue is true (default), issues or regenerates the certificate from the
    current template before returning the PDF bytes.
    """
    from certificates.services.certificate_render_service import (
        build_render_data,
        get_training_context_or_error,
        resolve_confirmed_certificate_participant,
    )

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

    certificate, pdf_bytes, issue_error = issue_certificate_for_participant(
        db,
        context,
        certificate_participant,
        current_user_id,
        regenerate=auto_issue,
    )
    if issue_error:
        return None, None, issue_error
    if certificate is None or pdf_bytes is None:
        return None, None, "Certificate has not been issued for this participant"

    render_data, build_error = build_render_data(
        db,
        context,
        identity,
        certificate_participant=certificate_participant,
        preview=False,
    )
    if build_error:
        return None, None, build_error

    meta = certificate_meta(
        certificate,
        certificate_participant,
        render_data.get("meta"),
    )
    return pdf_bytes, meta, None

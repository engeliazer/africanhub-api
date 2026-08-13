"""Build public certificate verification URLs and lookup issued certificates."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from sqlalchemy.orm import Session, joinedload

from certificates.models.models import (
    Certificate,
    CertificateParticipant,
    CertificateTrainingContext,
)
from certificates.services.participant_service import (
    resolve_certificate_participant_identity,
)
from certificates.services.certificate_issue_service import issue_certificate_for_participant
from certificates.services.storage_path_utils import storage_url_to_local_path
from config import API_BASE_URL, CERTIFICATE_VERIFY_BASE_URL


def build_verification_view_url(serial_no: str) -> str:
    encoded = quote((serial_no or "").strip(), safe="")
    return f"{CERTIFICATE_VERIFY_BASE_URL}?serial_no={encoded}"


def build_verification_pdf_url(serial_no: str) -> str:
    encoded = quote((serial_no or "").strip(), safe="")
    return f"{API_BASE_URL}/api/certificates/public/verify/pdf?serial_no={encoded}"


def _participant_summary(
    db: Session,
    participant: CertificateParticipant,
    context: CertificateTrainingContext,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    identity, error = resolve_certificate_participant_identity(db, participant, context)
    if error:
        return None, error

    return {
        "certificate_participant_id": participant.id,
        "participant_name": identity.display_name,
        "serial_no": participant.serial_no,
        "subject_title": context.subject_title,
        "venue_text": context.venue_text,
        "start_date": context.start_date.isoformat() if context.start_date else None,
        "end_date": context.end_date.isoformat() if context.end_date else None,
        "host_organization_name": context.host_organization_name,
        "invited_organization_name": context.invited_organization_name,
        "training_type": context.training_type,
        "confirmation_status": participant.confirmation_status,
    }, None


def lookup_certificate_by_serial(
    db: Session,
    serial_no: str,
) -> Tuple[Optional[CertificateParticipant], Optional[Certificate], Optional[CertificateTrainingContext], Optional[str]]:
    normalized = (serial_no or "").strip()
    if not normalized:
        return None, None, None, "serial_no is required"

    participant = (
        db.query(CertificateParticipant)
        .options(joinedload(CertificateParticipant.training_context))
        .filter(
            CertificateParticipant.serial_no == normalized,
            CertificateParticipant.deleted_at.is_(None),
        )
        .first()
    )
    if not participant:
        return None, None, None, "Certificate not found"

    context = participant.training_context
    if context is None or context.deleted_at is not None:
        return participant, None, None, "Training context not found"

    certificate = None
    if participant.certificate_id:
        certificate = (
            db.query(Certificate)
            .filter(
                Certificate.id == participant.certificate_id,
                Certificate.deleted_at.is_(None),
            )
            .first()
        )

    return participant, certificate, context, None


def build_verification_payload(
    db: Session,
    serial_no: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    participant, certificate, context, error = lookup_certificate_by_serial(db, serial_no)
    if error and participant is None:
        return None, error

    summary, summary_error = _participant_summary(db, participant, context)
    if summary_error:
        return None, summary_error

    issued = certificate is not None
    payload: Dict[str, Any] = {
        "valid": issued,
        "status": "issued" if issued else "not_issued",
        "message": (
            "Certificate verified successfully"
            if issued
            else "Participant found on roster; official certificate has not been issued yet"
        ),
        "serial_no": participant.serial_no,
        "verification_url": build_verification_view_url(participant.serial_no or ""),
        "pdf_url": build_verification_pdf_url(participant.serial_no or "") if issued else None,
        "issued_at": certificate.issued_at.isoformat() if certificate and certificate.issued_at else None,
        "certificate_id": certificate.id if certificate else None,
        **summary,
    }
    return payload, None


def resolve_verification_pdf_path(
    db: Session,
    serial_no: str,
    *,
    regenerate: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    participant, certificate, context, error = lookup_certificate_by_serial(db, serial_no)
    if error:
        return None, error
    if certificate is None:
        return None, "Official certificate PDF is not available until issuance"
    if not certificate.pdf_url and not regenerate:
        return None, "Certificate PDF file reference is missing"

    if regenerate and context is not None and participant is not None:
        actor_id = (
            certificate.updated_by
            or certificate.created_by
            or participant.updated_by
            or participant.created_by
            or 1
        )
        certificate, _, regen_error = issue_certificate_for_participant(
            db,
            context,
            participant,
            int(actor_id),
            regenerate=True,
        )
        if regen_error:
            return None, regen_error

    if not certificate.pdf_url:
        return None, "Certificate PDF file reference is missing"

    local_path = storage_url_to_local_path(certificate.pdf_url)
    if not local_path:
        return None, "Could not resolve certificate PDF path"
    return local_path, None

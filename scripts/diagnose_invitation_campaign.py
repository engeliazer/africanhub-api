#!/usr/bin/env python3
"""
Forensics for a stuck invitation campaign send (Celery vs thread is not stored in DB).

Usage (on server, from repo root):
  venv/bin/python3 scripts/diagnose_invitation_campaign.py 10
"""

import sys
from datetime import datetime

from sqlalchemy import func

from database.db_connector import SessionLocal
from applications.models.models import (
    Invitation,
    InvitationEmailLog,
    InvitationInvitee,
    InviteeSendStatus,
    InviteeValidationStatus,
)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: diagnose_invitation_campaign.py <invitation_id>", file=sys.stderr)
        return 1

    invitation_id = int(sys.argv[1])
    session = SessionLocal()
    try:
        inv = session.query(Invitation).filter(Invitation.id == invitation_id).first()
        if not inv:
            print(f"Invitation {invitation_id} not found.")
            return 1

        print("=" * 60)
        print(f"INVITATION CAMPAIGN id={invitation_id}")
        print("=" * 60)
        print(f"title:            {inv.title}")
        print(f"status:           {inv.status.value if inv.status else None}")
        print(f"started_at:       {inv.started_at}")
        print(f"completed_at:     {inv.completed_at}")
        print(f"scheduled_at:     {inv.scheduled_at}")
        print(f"updated_at:       {inv.updated_at}")
        print(f"interval_seconds: {inv.interval_seconds}")
        print(f"interval_limit:   {inv.interval_limit}")
        print(f"source_email:     {inv.source_email}")
        print()

        rows = (
            session.query(InvitationInvitee.send_status, func.count())
            .filter(InvitationInvitee.invitation_id == invitation_id)
            .group_by(InvitationInvitee.send_status)
            .all()
        )
        print("INVITEE send_status counts:")
        for status, count in rows:
            label = status.value if status else str(status)
            print(f"  {label}: {count}")

        valid_pending = (
            session.query(func.count())
            .filter(
                InvitationInvitee.invitation_id == invitation_id,
                InvitationInvitee.validation_status == InviteeValidationStatus.valid,
                InvitationInvitee.send_status == InviteeSendStatus.pending,
            )
            .scalar()
        )
        print(f"  (valid + PENDING): {valid_pending}")
        print()

        sent_stats = (
            session.query(
                func.min(InvitationInvitee.sent_at),
                func.max(InvitationInvitee.sent_at),
                func.count(),
            )
            .filter(
                InvitationInvitee.invitation_id == invitation_id,
                InvitationInvitee.send_status == InviteeSendStatus.sent,
            )
            .one()
        )
        print("SENT invitees:")
        print(f"  count:      {sent_stats[2]}")
        print(f"  first_sent: {sent_stats[0]}")
        print(f"  last_sent:  {sent_stats[1]}")
        if sent_stats[1]:
            delta = datetime.utcnow() - sent_stats[1]
            print(f"  idle since last_sent (UTC): {delta}")
        print()

        sending_count = (
            session.query(func.count())
            .filter(
                InvitationInvitee.invitation_id == invitation_id,
                InvitationInvitee.send_status == InviteeSendStatus.sending,
            )
            .scalar()
        )
        if sending_count:
            print(f"WARNING: {sending_count} invitee(s) stuck in SENDING (worker died mid-send)")
            stuck = (
                session.query(InvitationInvitee.id, InvitationInvitee.email, InvitationInvitee.updated_at)
                .filter(
                    InvitationInvitee.invitation_id == invitation_id,
                    InvitationInvitee.send_status == InviteeSendStatus.sending,
                )
                .limit(10)
                .all()
            )
            for iid, email, upd in stuck:
                print(f"  id={iid} email={email} updated_at={upd}")
            print()

        log_rows = (
            session.query(InvitationEmailLog.status, func.count())
            .filter(InvitationEmailLog.invitation_id == invitation_id)
            .group_by(InvitationEmailLog.status)
            .all()
        )
        if log_rows:
            print("invitation_email_logs by status:")
            for status, count in log_rows:
                label = status.value if status else str(status)
                print(f"  {label}: {count}")
            print()

        failed_sample = (
            session.query(InvitationInvitee.email, InvitationInvitee.error_message)
            .filter(
                InvitationInvitee.invitation_id == invitation_id,
                InvitationInvitee.send_status == InviteeSendStatus.failed,
            )
            .limit(5)
            .all()
        )
        if failed_sample:
            print("Sample FAILED invitees:")
            for email, err in failed_sample:
                print(f"  {email}: {err}")
            print()

        print("INTERPRETATION (orchestration):")
        print("  - Mail delivery uses send_batch_email() (SES/SendGrid/SMTP), not Redis.")
        print("  - Celery vs Gunicorn thread is NOT saved in DB.")
        print("  - If last_sent is old and status=PROCESSING, background job stopped.")
        print("  - Check logs around started_at for 'Celery unavailable' (thread fallback).")
        print("  - Resume: POST /api/invitations/{id}/send/start with JWT")
        print("=" * 60)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

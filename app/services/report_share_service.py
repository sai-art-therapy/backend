from datetime import datetime, timedelta
import hashlib
import secrets

from sqlalchemy.orm import Session

from app.core.config import REPORT_SHARE_TOKEN_EXPIRE_HOURS
from app.models.report_share import ReportShare


SHARE_TOKEN_BYTES = 32


def hash_share_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_share_token() -> str:
    return secrets.token_urlsafe(SHARE_TOKEN_BYTES)


def issue_report_share(
    db: Session,
    report_id: int,
) -> tuple[str, ReportShare]:
    """Revoke older links and issue one opaque, time-limited report token."""
    now = datetime.utcnow()
    (
        db.query(ReportShare)
        .filter(
            ReportShare.report_id == report_id,
            ReportShare.revoked_at.is_(None),
        )
        .update({ReportShare.revoked_at: now}, synchronize_session=False)
    )

    token = generate_share_token()
    share = ReportShare(
        report_id=report_id,
        token_hash=hash_share_token(token),
        expires_at=now + timedelta(hours=REPORT_SHARE_TOKEN_EXPIRE_HOURS),
    )
    db.add(share)
    db.flush()
    return token, share


def revoke_report_shares(db: Session, report_id: int) -> int:
    return (
        db.query(ReportShare)
        .filter(
            ReportShare.report_id == report_id,
            ReportShare.revoked_at.is_(None),
        )
        .update(
            {ReportShare.revoked_at: datetime.utcnow()},
            synchronize_session=False,
        )
    )


def find_active_report_share(db: Session, token: str) -> ReportShare | None:
    if not token or len(token) > 256:
        return None

    now = datetime.utcnow()
    return (
        db.query(ReportShare)
        .filter(
            ReportShare.token_hash == hash_share_token(token),
            ReportShare.revoked_at.is_(None),
            ReportShare.expires_at > now,
        )
        .first()
    )

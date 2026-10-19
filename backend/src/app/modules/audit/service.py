"""Écriture d'audit dans la transaction de l'opération consultée."""

from uuid import uuid4
from sqlalchemy.orm import Session
from app.db.models import AuditEvent


def record_event(
    db: Session, *, actor_user_id: str | None, action: str,
    resource_type: str, resource_id: str | None, outcome: str,
    correlation_id: str,
) -> None:
    db.add(AuditEvent(
        id=str(uuid4()), actor_user_id=actor_user_id, action=action,
        resource_type=resource_type, resource_id=resource_id,
        outcome=outcome, correlation_id=correlation_id,
    ))

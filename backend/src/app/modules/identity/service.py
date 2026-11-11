"""Résolution exacte et accès explicite à la rencontre."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Encounter, Patient, UserEncounterAccess


def resolve_patient(db: Session, identifier_domain: str, external_id: str) -> Patient | None:
    return db.scalar(select(Patient).where(
        Patient.identifier_domain == identifier_domain,
        Patient.external_id == external_id,
    ))


def accessible_patients(db: Session, user_id: str, limit: int, offset: int) -> list[Patient]:
    access = select(Encounter.id).join(
        UserEncounterAccess, UserEncounterAccess.encounter_id == Encounter.id,
    ).where(Encounter.patient_id == Patient.id, UserEncounterAccess.user_id == user_id)
    return list(db.scalars(select(Patient).where(Patient.is_synthetic.is_(True), access.exists())
                           .order_by(Patient.external_id, Patient.id).offset(offset).limit(limit)))


def accessible_encounters(db: Session, user_id: str, patient_id: str) -> list[Encounter]:
    return list(db.scalars(select(Encounter).join(
        UserEncounterAccess, UserEncounterAccess.encounter_id == Encounter.id,
    ).where(
        Encounter.patient_id == patient_id,
        UserEncounterAccess.user_id == user_id,
    ).order_by(Encounter.started_at)))

"""RIS workflow for encounter-linked orders, exams and the current report."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AppUser, Encounter, Patient, RadiologyExam, RadiologyOrder, RadiologyReport,
    UserEncounterAccess, UserRole,
)
from app.modules.audit.service import record_event


class RadiologyError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RadiologyError("INVALID_TIME")
    return value.astimezone(timezone.utc)


def _stored_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _stored_utc(value).isoformat().replace("+00:00", "Z")


def _authorize(db: Session, actor_user_id: str, encounter_id: str, allowed: set[str]) -> Encounter:
    encounter = db.get(Encounter, encounter_id)
    if encounter is None:
        raise RadiologyError("ENCOUNTER_UNKNOWN")
    patient = db.get(Patient, encounter.patient_id)
    if patient is None or not patient.is_synthetic:
        raise RadiologyError("PATIENT_UNKNOWN")
    roles = set(db.scalars(select(UserRole.role_name).where(UserRole.user_id == actor_user_id)))
    access = db.get(UserEncounterAccess, (actor_user_id, encounter_id))
    user = db.get(AppUser, actor_user_id)
    if user is None or not user.is_active or access is None or not roles.intersection(allowed):
        raise RadiologyError("ACCESS_DENIED")
    return encounter


def _exam_context(db: Session, exam_id: str, actor_user_id: str) -> tuple[RadiologyExam, RadiologyOrder, Encounter]:
    exam = db.scalar(select(RadiologyExam).where(RadiologyExam.id == exam_id).with_for_update())
    if exam is None:
        raise RadiologyError("EXAM_UNKNOWN")
    order = db.get(RadiologyOrder, exam.order_id)
    if order is None:
        raise RadiologyError("ORDER_UNKNOWN")
    encounter = _authorize(db, actor_user_id, order.encounter_id, {"radiologist"})
    return exam, order, encounter


def create_order(factory: sessionmaker[Session], *, actor_user_id: str, encounter_id: str,
                 accession_number: str, requested_procedure: str, modality: str,
                 priority: str = "routine", correlation_id: str | None = None) -> dict:
    """Create one scheduled exam for an authorized synthetic encounter."""
    if (not accession_number or len(accession_number) > 100 or accession_number != accession_number.strip()
            or not requested_procedure.strip() or len(requested_procedure) > 200
            or not modality.strip() or len(modality) > 20 or priority not in {"routine", "urgent"}):
        raise RadiologyError("INVALID_INPUT")
    try:
        with factory.begin() as db:
            _authorize(db, actor_user_id, encounter_id, {"physician", "radiologist"})
            if db.scalar(select(RadiologyOrder.id).where(RadiologyOrder.accession_number == accession_number)):
                raise RadiologyError("ACCESSION_CONFLICT")
            order = RadiologyOrder(id=str(uuid4()), encounter_id=encounter_id,
                                   accession_number=accession_number,
                                   requested_procedure=requested_procedure.strip(),
                                   priority=priority, status="ordered")
            exam = RadiologyExam(id=str(uuid4()), order_id=order.id,
                                 modality=modality.strip(), status="scheduled")
            db.add(order)
            db.flush()
            db.add(exam)
            record_event(db, actor_user_id=actor_user_id, action="radiology.order.create",
                         resource_type="radiology_order", resource_id=order.id, outcome="allowed",
                         correlation_id=correlation_id or str(uuid4()))
            return {"order_id": order.id, "exam_id": exam.id}
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if (constraint == "radiology_order_accession_number_key"
                or "radiology_order.accession_number" in str(exc.orig)):
            raise RadiologyError("ACCESSION_CONFLICT") from exc
        raise


def mark_performed(factory: sessionmaker[Session], *, actor_user_id: str, exam_id: str,
                   performed_at: datetime, correlation_id: str | None = None) -> None:
    performed_at = _utc(performed_at)
    with factory.begin() as db:
        exam, order, encounter = _exam_context(db, exam_id, actor_user_id)
        if exam.status != "scheduled" or order.status != "ordered":
            raise RadiologyError("INVALID_TRANSITION")
        if performed_at < _stored_utc(encounter.started_at) or (encounter.ended_at and performed_at > _stored_utc(encounter.ended_at)):
            raise RadiologyError("INVALID_TIME")
        exam.status = "performed"
        exam.performed_at = performed_at
        record_event(db, actor_user_id=actor_user_id, action="radiology.exam.perform",
                     resource_type="radiology_exam", resource_id=exam.id, outcome="allowed",
                     correlation_id=correlation_id or str(uuid4()))


def save_report_draft(factory: sessionmaker[Session], *, actor_user_id: str, exam_id: str,
                      content: str, correlation_id: str | None = None) -> str:
    content = content.strip()
    if not content or len(content) > 10000:
        raise RadiologyError("INVALID_INPUT")
    with factory.begin() as db:
        exam, order, _ = _exam_context(db, exam_id, actor_user_id)
        if exam.status != "performed" or order.status != "ordered" or exam.performed_at is None:
            raise RadiologyError("INVALID_TRANSITION")
        report = db.scalar(select(RadiologyReport).where(RadiologyReport.exam_id == exam_id).with_for_update())
        if report is None:
            report = RadiologyReport(id=str(uuid4()), exam_id=exam_id, author_user_id=actor_user_id,
                                     content=content, status="draft")
            db.add(report)
        elif report.status == "draft":
            report.content = content
            report.author_user_id = actor_user_id
        else:
            raise RadiologyError("INVALID_TRANSITION")
        record_event(db, actor_user_id=actor_user_id, action="radiology.report.draft",
                     resource_type="radiology_report", resource_id=report.id, outcome="allowed",
                     correlation_id=correlation_id or str(uuid4()))
        return report.id


def validate_report(factory: sessionmaker[Session], *, actor_user_id: str, exam_id: str,
                    validated_at: datetime, correlation_id: str | None = None) -> str:
    validated_at = _utc(validated_at)
    with factory.begin() as db:
        exam, order, _ = _exam_context(db, exam_id, actor_user_id)
        report = db.scalar(select(RadiologyReport).where(RadiologyReport.exam_id == exam_id).with_for_update())
        if (exam.status != "performed" or exam.performed_at is None or order.status != "ordered"
                or report is None or report.status != "draft" or not report.content.strip()):
            raise RadiologyError("INVALID_TRANSITION")
        if validated_at < _stored_utc(exam.performed_at):
            raise RadiologyError("INVALID_TIME")
        report.status = "final"
        report.validated_at = validated_at
        order.status = "completed"
        record_event(db, actor_user_id=actor_user_id, action="radiology.report.validate",
                     resource_type="radiology_report", resource_id=report.id, outcome="allowed",
                     correlation_id=correlation_id or str(uuid4()))
        return report.id


def get_encounter_exams(db: Session, encounter_id: str) -> dict:
    """Return the RIS projection for an already authorized encounter."""
    rows = db.execute(select(RadiologyExam, RadiologyOrder, RadiologyReport)
                      .join(RadiologyOrder, RadiologyExam.order_id == RadiologyOrder.id)
                      .outerjoin(RadiologyReport, RadiologyReport.exam_id == RadiologyExam.id)
                      .where(RadiologyOrder.encounter_id == encounter_id)
                      .order_by(RadiologyOrder.accession_number)).all()
    return {"exams": [{"id": exam.id, "order_id": order.id,
                       "accession_number": order.accession_number, "modality": exam.modality,
                       "status": exam.status, "performed_at": _iso(exam.performed_at),
                       "report": ({"id": report.id, "status": report.status,
                                   "content": report.content, "validated_at": _iso(report.validated_at)}
                                  if report else None)} for exam, order, report in rows]}

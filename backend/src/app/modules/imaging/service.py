"""Match an Orthanc study to one RIS exam and refresh its dated availability."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Encounter, ImagingStudy, Patient, RadiologyExam, RadiologyOrder
from app.integrations.orthanc.client import OrthancClient, OrthancError, OrthancStudy
from app.modules.audit.service import record_event


ROOT = Path(__file__).resolve().parents[5]


class ImagingError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _scenario() -> dict:
    manifest = json.loads((ROOT / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
    metadata = json.loads((ROOT / "data/dicom/study-metadata.json").read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True or metadata.get("synthetic") is not True:
        raise ValueError("Only synthetic imaging fixtures are supported")
    if (metadata["study_instance_uid"] != manifest["imaging"]["study_instance_uid"]
            or metadata["patient_id"] != manifest["identity"]["dicom_patient_id"]
            or metadata["identifier_domain"] != manifest["identity"]["dicom_identifier_domain"]
            or metadata["accession_number"] != manifest["imaging"]["accession_number"]
            or metadata["modality"] != manifest["imaging"]["modality"]
            or metadata["expected_series_count"] != manifest["imaging"]["expected_series_count"]
            or metadata["expected_instance_count"] != manifest["imaging"]["expected_instance_count"]):
        raise ValueError("Imaging fixture conflicts with the common manifest")
    return metadata


def _status(study: OrthancStudy, fixture: dict) -> str:
    if study.study_instance_uid != fixture["study_instance_uid"]:
        return "incomplete"  # No documented expectation for another study.
    if (study.series_count == fixture["expected_series_count"]
            and study.instance_count == fixture["expected_instance_count"]):
        return "available"
    return "incomplete"


def _identity(db: Session, order: RadiologyOrder) -> Patient:
    encounter = db.get(Encounter, order.encounter_id)
    if encounter is None:
        raise ImagingError("ENCOUNTER_UNKNOWN")
    patient = db.get(Patient, encounter.patient_id)
    if patient is None or not patient.is_synthetic:
        raise ImagingError("PATIENT_UNKNOWN")
    return patient


def _verify(study: OrthancStudy, patient: Patient, order: RadiologyOrder,
            exam: RadiologyExam, fixture: dict) -> None:
    if study.patient_id != patient.external_id:
        raise ImagingError("PATIENT_MISMATCH")
    domain = study.issuer_of_patient_id
    if domain is None and study.study_instance_uid == fixture["study_instance_uid"]:
        domain = fixture["identifier_domain"]
    if domain != patient.identifier_domain:
        raise ImagingError("IDENTIFIER_DOMAIN_MISMATCH")
    if study.accession_number != order.accession_number:
        raise ImagingError("ACCESSION_MISMATCH")
    if study.modality != exam.modality:
        raise ImagingError("MODALITY_MISMATCH")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite readback drops timezone information.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _public_study(study: ImagingStudy) -> dict:
    return {"id": study.id, "exam_id": study.exam_id,
            "study_instance_uid": study.study_instance_uid,
            "series_count": study.series_count, "instance_count": study.instance_count,
            "availability_status": study.availability_status,
            "last_synced_at": _iso(study.last_synced_at)}


def match_study(factory: sessionmaker[Session], client: OrthancClient, *, patient_id: str,
                accession_number: str, study_instance_uid: str, modality: str,
                timeout_ms: int = 500, correlation_id: str | None = None) -> dict:
    """Match an imported study using all four keys; never guess by patient name."""
    fixture = _scenario()
    if not all((patient_id, accession_number, study_instance_uid, modality)):
        raise ImagingError("INVALID_INPUT")
    # Reject an unknown local request before consulting the PACS. The locked
    # lookup below repeats these checks before any association is committed.
    with factory() as db:
        order = db.scalar(select(RadiologyOrder).where(
            RadiologyOrder.accession_number == accession_number))
        if order is None:
            raise ImagingError("UNKNOWN_ACCESSION")
        patient = _identity(db, order)
        if patient.id != patient_id:
            raise ImagingError("PATIENT_MISMATCH")
        exam = db.scalar(select(RadiologyExam).where(RadiologyExam.order_id == order.id))
        if exam is None:
            raise ImagingError("EXAM_UNKNOWN")
        if exam.modality != modality:
            raise ImagingError("MODALITY_MISMATCH")
    remote = client.find_study(study_instance_uid, timeout_ms)
    if remote is None:
        raise ImagingError("STUDY_NOT_FOUND")
    if remote.study_instance_uid != study_instance_uid:
        raise ImagingError("STUDY_UID_MISMATCH")
    checked_at = datetime.now(timezone.utc)
    try:
        with factory.begin() as db:
            order = db.scalar(select(RadiologyOrder).where(
                RadiologyOrder.accession_number == accession_number).with_for_update())
            if order is None:
                raise ImagingError("UNKNOWN_ACCESSION")
            patient = _identity(db, order)
            if patient.id != patient_id:
                raise ImagingError("PATIENT_MISMATCH")
            exam = db.scalar(select(RadiologyExam).where(RadiologyExam.order_id == order.id))
            if exam is None:
                raise ImagingError("EXAM_UNKNOWN")
            if exam.modality != modality:
                raise ImagingError("MODALITY_MISMATCH")
            _verify(remote, patient, order, exam, fixture)
            by_uid = db.scalar(select(ImagingStudy).where(ImagingStudy.study_instance_uid == study_instance_uid))
            by_exam = db.scalar(select(ImagingStudy).where(ImagingStudy.exam_id == exam.id))
            if (by_uid is not None and by_uid.exam_id != exam.id
                    or by_exam is not None and by_exam.study_instance_uid != study_instance_uid
                    or by_exam is not None and by_exam.orthanc_study_id != remote.orthanc_id):
                raise ImagingError("STUDY_CONFLICT")
            study = by_exam
            replayed = study is not None
            if study is None:
                study = ImagingStudy(id=str(uuid4()), exam_id=exam.id,
                                     study_instance_uid=study_instance_uid,
                                     orthanc_study_id=remote.orthanc_id, modality=remote.modality,
                                     series_count=0, instance_count=0,
                                     availability_status="incomplete")
                db.add(study)
            study.series_count = remote.series_count
            study.instance_count = remote.instance_count
            study.availability_status = _status(remote, fixture)
            study.last_synced_at = checked_at
            record_event(db, actor_user_id=None, action="imaging.match", resource_type="imaging_study",
                         resource_id=study.id, outcome="replayed" if replayed else "allowed",
                         correlation_id=correlation_id or str(uuid4()))
            return {"exam_id": exam.id, "imaging_study_id": study.id,
                    "availability_status": study.availability_status, "replayed": replayed}
    except IntegrityError as exc:
        # A competing request may have inserted this UID or exam association.
        raise ImagingError("STUDY_CONFLICT") from exc


def get_availability(factory: sessionmaker[Session], client: OrthancClient, *, exam_id: str,
                     timeout_ms: int = 500, correlation_id: str | None = None) -> dict:
    """Refresh a known study; retain its reference and last good sync on PACS failure."""
    fixture = _scenario()
    with factory.begin() as db:
        study = db.scalar(select(ImagingStudy).where(ImagingStudy.exam_id == exam_id))
        if study is None:
            if db.get(RadiologyExam, exam_id) is None:
                raise ImagingError("EXAM_UNKNOWN")
            record_event(db, actor_user_id=None, action="imaging.availability",
                         resource_type="radiology_exam", resource_id=exam_id,
                         outcome="allowed", correlation_id=correlation_id or str(uuid4()))
            return {"availability_status": "incomplete", "checked_at": _iso(datetime.now(timezone.utc)),
                    "studies": []}
        orthanc_id = study.orthanc_study_id
    remote = None
    warning_code = None
    try:
        if not orthanc_id:
            raise ImagingError("ORTHANC_REFERENCE_MISSING")
        remote = client.get_study(orthanc_id, timeout_ms)
    except (OrthancError, ImagingError) as exc:
        warning_code = exc.code
    checked_at = datetime.now(timezone.utc)
    with factory.begin() as db:
        study = db.scalar(select(ImagingStudy).where(ImagingStudy.exam_id == exam_id).with_for_update())
        if study is None or study.orthanc_study_id != orthanc_id:
            raise ImagingError("STUDY_CONFLICT")
        exam = db.get(RadiologyExam, exam_id)
        order = db.get(RadiologyOrder, exam.order_id)
        patient = _identity(db, order)
        if remote is not None:
            try:
                if remote.study_instance_uid != study.study_instance_uid:
                    raise ImagingError("STUDY_UID_MISMATCH")
                _verify(remote, patient, order, exam, fixture)
            except ImagingError as exc:
                warning_code = exc.code
        if warning_code:
            study.availability_status = "unavailable"
        else:
            study.series_count = remote.series_count
            study.instance_count = remote.instance_count
            study.availability_status = _status(remote, fixture)
            study.last_synced_at = checked_at
        record_event(db, actor_user_id=None, action="imaging.availability", resource_type="imaging_study",
                     resource_id=study.id, outcome="degraded" if warning_code else "allowed",
                     correlation_id=correlation_id or str(uuid4()))
        result = {"availability_status": study.availability_status,
                  "checked_at": _iso(checked_at), "studies": [_public_study(study)]}
        if warning_code:
            result["warning_code"] = warning_code
        return result

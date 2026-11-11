"""Compose an authorized synthetic encounter from the domain read services."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ACCESS_DENIED, NOT_FOUND, ApiError
from app.db.models import Encounter, Patient, UserEncounterAccess, UserRole
from app.integrations.orthanc.client import OrthancClient
from app.modules.audit.service import record_event
from app.modules.imaging.service import get_availability
from app.modules.laboratory.service import get_encounter_reports
from app.modules.radiology.service import get_encounter_exams


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_summary(factory: sessionmaker[Session], client: OrthancClient, *, actor_user_id: str,
                  encounter_id: str, correlation_id: str, timeout_ms: int = 500) -> dict:
    """Require a clinical role, explicit grant and successful audit before returning data."""
    with factory.begin() as db:
        encounter = db.get(Encounter, encounter_id)
        if encounter is None:
            record_event(db, actor_user_id=actor_user_id, action="encounter.summary",
                         resource_type="encounter", resource_id=None, outcome="not_found",
                         correlation_id=correlation_id)
            error = ApiError(*NOT_FOUND)
        else:
            roles = set(db.scalars(select(UserRole.role_name).where(UserRole.user_id == actor_user_id)))
            access = db.get(UserEncounterAccess, (actor_user_id, encounter_id))
            if access is None or not roles.intersection({"physician", "radiologist", "lab_technician", "imaging_technician"}):
                record_event(db, actor_user_id=actor_user_id, action="encounter.summary",
                             resource_type="encounter", resource_id=encounter_id, outcome="denied",
                             correlation_id=correlation_id)
                error = ApiError(*ACCESS_DENIED)
            else:
                patient = db.get(Patient, encounter.patient_id)
                if patient is None or not patient.is_synthetic:
                    raise ApiError(*NOT_FOUND)
                laboratory = get_encounter_reports(db, encounter_id)
                radiology = get_encounter_exams(db, encounter_id)
                record_event(db, actor_user_id=actor_user_id, action="encounter.summary",
                             resource_type="encounter", resource_id=encounter_id, outcome="allowed",
                             correlation_id=correlation_id)
                error = None
                identity = {"id": patient.id, "external_id": patient.external_id,
                            "identifier_domain": patient.identifier_domain,
                            "display_name": patient.display_name, "is_synthetic": patient.is_synthetic}
                encounter_data = {"id": encounter.id, "external_id": encounter.external_id,
                                  "status": encounter.status, "started_at": _iso(encounter.started_at)}
    if error is not None:
        raise error

    checks = [get_availability(factory, client, exam_id=item["id"], timeout_ms=timeout_ms,
                               correlation_id=correlation_id)
              for item in radiology["exams"]]
    studies = [study for check in checks for study in check["studies"]]
    statuses = [check["availability_status"] for check in checks]
    availability = ("unavailable" if "unavailable" in statuses else
                    "incomplete" if not statuses or "incomplete" in statuses else "available")
    checked_at = max((check["checked_at"] for check in checks), default=_iso(datetime.now(timezone.utc)))
    warnings = list(laboratory["warnings"])
    for check in checks:
        if check["availability_status"] == "unavailable":
            warnings.append({"code": "IMAGING_UNAVAILABLE",
                             "resource_id": check["studies"][0]["id"] if check["studies"] else None,
                             "field": None,
                             "message": "Imagerie temporairement indisponible. Les données métier restent consultables."})
    laboratory = {key: value for key, value in laboratory.items() if key != "warnings"}
    return {"patient": identity, "encounter": encounter_data, "laboratory": laboratory,
            "radiology": radiology, "imaging": {"availability_status": availability,
                                              "checked_at": checked_at, "studies": studies},
            "warnings": warnings}

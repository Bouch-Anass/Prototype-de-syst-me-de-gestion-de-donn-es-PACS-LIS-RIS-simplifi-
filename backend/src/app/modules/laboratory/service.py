"""Laboratory writes and read projection for the synthetic HL7 profile.

Each ingestion owns its transaction. A successful return therefore means the
inbound marker and the business rows have committed together.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Encounter, InboundMessage, LabObservation, LabOrder, LabReport, Patient, UserEncounterAccess, UserRole
from app.modules.audit.service import record_event


MANIFEST = Path(__file__).resolve().parents[5] / "data/fixtures/scenario.json"


class LaboratoryError(ValueError):
    """A domain rejection whose code can be mapped by the HL7 adapter."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ObservationValue:
    coding_system: str
    code: str
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    display: str | None = None


@dataclass(frozen=True)
class OrderCommand:
    source: str
    control_id: str
    content_hash: str
    patient_id: str
    encounter_id: str
    placer_number: str
    filler_number: str
    panel_code: str
    ordered_at: datetime


@dataclass(frozen=True)
class ResultCommand:
    source: str
    control_id: str
    content_hash: str
    patient_id: str
    encounter_id: str
    placer_number: str
    filler_number: str
    panel_code: str
    reported_at: datetime
    observations: tuple[ObservationValue, ...]
    correction: bool = False
    allow_additional: bool = False


@dataclass(frozen=True)
class OrderReceipt:
    lab_order_id: str
    replayed: bool


@dataclass(frozen=True)
class ResultReceipt:
    lab_report_id: str
    version: int
    replayed: bool


def _catalog(panel_code: str) -> tuple[dict, ...]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True or panel_code != manifest["hl7"]["panel_code"]:
        raise LaboratoryError("UNKNOWN_PANEL")
    return tuple(manifest["laboratory"]["expected_observations"])


def _validate_common(command: OrderCommand | ResultCommand) -> None:
    for field in ("source", "control_id", "patient_id", "encounter_id", "placer_number", "filler_number"):
        if not isinstance(getattr(command, field), str) or not getattr(command, field).strip():
            raise LaboratoryError("INVALID_INPUT")
    if (not isinstance(command.content_hash, str) or len(command.content_hash) != 64
            or any(char not in "0123456789abcdef" for char in command.content_hash)):
        raise LaboratoryError("INVALID_INPUT")
    instant = command.ordered_at if isinstance(command, OrderCommand) else command.reported_at
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise LaboratoryError("INVALID_TIME")


def _check_encounter(db: Session, patient_id: str, encounter_id: str) -> None:
    # Serialize writes for this encounter, including two new control IDs that
    # reference the same order number. SQLite ignores FOR UPDATE in unit tests.
    encounter = db.get(Encounter, encounter_id, with_for_update=True)
    if encounter is None or encounter.patient_id != patient_id:
        raise LaboratoryError("ENCOUNTER_UNKNOWN")


def _start_sqlite_transaction(db: Session) -> None:
    # Python's sqlite3 legacy mode does not BEGIN on SELECT. Without an explicit
    # BEGIN, a released SAVEPOINT can survive a later outer rollback in tests.
    if db.bind.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN")


def _claim(db: Session, source: str, control_id: str, content_hash: str, message_type: str) -> tuple[InboundMessage, bool]:
    key = (source, control_id)
    existing = db.scalar(select(InboundMessage).where(
        InboundMessage.source_system == source,
        InboundMessage.external_message_id == control_id,
    ))
    if existing is None:
        candidate = InboundMessage(id=str(uuid4()), source_system=source, external_message_id=control_id,
                                   message_type=message_type, processing_status="processed", payload_hash=content_hash)
        try:
            # The unique key arbitrates concurrent receptions on PostgreSQL.
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            return candidate, False
        except IntegrityError:
            existing = db.scalar(select(InboundMessage).where(
                InboundMessage.source_system == source,
                InboundMessage.external_message_id == control_id,
            ))
            if existing is None:
                raise
    if (existing.payload_hash != content_hash or existing.message_type != message_type
            or existing.processing_status != "processed"):
        raise LaboratoryError("MESSAGE_CONFLICT")
    return existing, True


def ingest_order(factory: sessionmaker[Session], command: OrderCommand,
                 correlation_id: str | None = None) -> OrderReceipt:
    """Persist one OML order; a byte-identical replay returns its existing ID."""
    _validate_common(command)
    _catalog(command.panel_code)
    with factory.begin() as db:
        _start_sqlite_transaction(db)
        _check_encounter(db, command.patient_id, command.encounter_id)
        _, replayed = _claim(db, command.source, command.control_id, command.content_hash, "OML_O21")
        order = db.scalar(select(LabOrder).where(
            LabOrder.source_system == command.source,
            LabOrder.placer_number == command.placer_number,
        ))
        if replayed:
            if order is None or order.encounter_id != command.encounter_id or order.filler_number != command.filler_number:
                raise LaboratoryError("MESSAGE_CONFLICT")
            if correlation_id:
                record_event(db, actor_user_id=None, action="lab.order.ingest", resource_type="lab_order",
                             resource_id=order.id, outcome="replayed", correlation_id=correlation_id)
            return OrderReceipt(order.id, True)
        if order is not None:
            raise LaboratoryError("ORDER_CONFLICT")
        order = LabOrder(id=str(uuid4()), encounter_id=command.encounter_id, source_system=command.source,
                         placer_number=command.placer_number, filler_number=command.filler_number,
                         panel_code=command.panel_code, ordered_at=command.ordered_at.astimezone(timezone.utc),
                         status="ordered")
        db.add(order)
        if correlation_id:
            record_event(db, actor_user_id=None, action="lab.order.ingest", resource_type="lab_order",
                         resource_id=order.id, outcome="allowed", correlation_id=correlation_id)
        return OrderReceipt(order.id, False)


def _validated_observations(command: ResultCommand, catalog: tuple[dict, ...]) -> list[tuple[dict, ObservationValue | None]]:
    expected = {(item["coding_system"], item["code"]): item for item in catalog}
    supplied: dict[tuple[str, str], ObservationValue] = {}
    if not command.observations:
        raise LaboratoryError("INVALID_OBSERVATION")
    additions = []
    for item in command.observations:
        key = (item.coding_system, item.code)
        if key in supplied:
            raise LaboratoryError("INVALID_OBSERVATION")
        if key in expected:
            if item.unit != expected[key]["unit"]:
                raise LaboratoryError("INVALID_OBSERVATION")
        elif (not command.allow_additional or item.coding_system != "DEMO"
              or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}", item.code)
              or not item.display or not item.display.strip() or len(item.display) > 120
              or not item.unit or not item.unit.strip() or len(item.unit) > 40):
            raise LaboratoryError("INVALID_OBSERVATION")
        else:
            additions.append({"coding_system": item.coding_system, "code": item.code,
                              "display": item.display.strip(), "unit": item.unit.strip()})
        numeric, textual = item.value_numeric, item.value_text
        if (numeric is None) == (textual is None):
            raise LaboratoryError("INVALID_OBSERVATION")
        if numeric is not None and (type(numeric) not in (int, float) or not math.isfinite(numeric)):
            raise LaboratoryError("INVALID_OBSERVATION")
        if textual is not None and (not isinstance(textual, str) or not textual.strip()):
            raise LaboratoryError("INVALID_OBSERVATION")
        supplied[key] = item
    return [(entry, supplied.get((entry["coding_system"], entry["code"])))
            for entry in (*catalog, *additions)]


def ingest_result(factory: sessionmaker[Session], command: ResultCommand,
                  correlation_id: str | None = None, actor_user_id: str | None = None) -> ResultReceipt:
    """Persist one complete report version, deriving missing expected observations."""
    _validate_common(command)
    catalog = _catalog(command.panel_code)
    observations = _validated_observations(command, catalog)
    with factory.begin() as db:
        _start_sqlite_transaction(db)
        _check_encounter(db, command.patient_id, command.encounter_id)
        if actor_user_id is not None:
            grant = db.get(UserEncounterAccess, (actor_user_id, command.encounter_id))
            roles = set(db.scalars(select(UserRole.role_name).where(UserRole.user_id == actor_user_id)))
            patient = db.get(Patient, command.patient_id)
            if grant is None or "lab_technician" not in roles or patient is None or not patient.is_synthetic:
                raise LaboratoryError("ACCESS_DENIED")
        marker, replayed = _claim(db, command.source, command.control_id, command.content_hash, "ORU_R01")
        if replayed:
            report = db.scalar(select(LabReport).where(LabReport.inbound_message_id == marker.id))
            if report is None:
                raise LaboratoryError("MESSAGE_CONFLICT")
            if correlation_id:
                record_event(db, actor_user_id=actor_user_id, action="lab.result.ingest", resource_type="lab_report",
                             resource_id=report.id, outcome="replayed", correlation_id=correlation_id)
            return ResultReceipt(report.id, report.version, True)
        order = db.scalar(select(LabOrder).where(
            LabOrder.source_system == command.source,
            LabOrder.placer_number == command.placer_number,
        ).with_for_update())
        if (order is None or order.encounter_id != command.encounter_id
                or order.filler_number != command.filler_number or order.panel_code != command.panel_code):
            raise LaboratoryError("ORDER_UNKNOWN")
        previous = db.scalar(select(LabReport).where(LabReport.lab_order_id == order.id)
                             .order_by(LabReport.version.desc()).limit(1))
        if command.correction != (previous is not None):
            raise LaboratoryError("INVALID_REPORT_SEQUENCE")
        version = 1 if previous is None else previous.version + 1
        report = LabReport(id=str(uuid4()), lab_order_id=order.id, inbound_message_id=marker.id,
                           reported_at=command.reported_at.astimezone(timezone.utc),
                           status="corrected" if command.correction else "final", version=version)
        db.add(report)
        db.flush()
        for expected, supplied in observations:
            db.add(LabObservation(id=str(uuid4()), lab_report_id=report.id,
                                  coding_system=expected["coding_system"], code=expected["code"],
                                  display=expected["display"], unit=expected["unit"],
                                  data_status="available" if supplied else "missing",
                                  value_numeric=supplied.value_numeric if supplied else None,
                                  value_text=supplied.value_text if supplied else None))
        order.status = "reported"
        if correlation_id:
            record_event(db, actor_user_id=actor_user_id, action="lab.result.ingest", resource_type="lab_report",
                         resource_id=report.id, outcome="allowed", correlation_id=correlation_id)
        return ResultReceipt(report.id, version, False)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:  # SQLite drops the timezone marker on readback.
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def get_encounter_reports(db: Session, encounter_id: str) -> dict:
    """Return only current versions, with warnings for unavailable values."""
    orders = list(db.scalars(select(LabOrder).where(LabOrder.encounter_id == encounter_id)
                             .order_by(LabOrder.ordered_at, LabOrder.id)))
    reports = []
    warnings = []
    pending = False
    for order in orders:
        report = db.scalar(select(LabReport).where(LabReport.lab_order_id == order.id)
                           .order_by(LabReport.version.desc()).limit(1))
        if report is None:
            pending = True
            continue
        values = list(db.scalars(select(LabObservation).where(LabObservation.lab_report_id == report.id)
                                 .order_by(LabObservation.code)))
        for item in values:
            if item.data_status == "missing":
                warnings.append({"code": "LAB_RESULT_MISSING", "resource_id": report.id, "field": item.code,
                                 "message": f"Résultat {item.display} attendu mais non reçu."})
        reports.append({"id": report.id, "lab_order_id": order.id, "version": report.version,
                        "status": report.status, "reported_at": _timestamp(report.reported_at),
                        "observations": [{"code": item.code, "coding_system": item.coding_system,
                                          "display": item.display, "value_numeric": item.value_numeric,
                                          "value_text": item.value_text, "unit": item.unit,
                                          "data_status": item.data_status} for item in values]})
    status = "unavailable" if not reports else "partial" if pending or warnings else "available"
    return {"status": status, "reports": reports, "warnings": warnings}

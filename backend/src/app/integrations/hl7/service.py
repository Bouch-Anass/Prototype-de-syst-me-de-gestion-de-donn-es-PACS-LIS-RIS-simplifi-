"""Strict DEMO-001 HL7 v2.5.1 adapter; no general HL7 parser is claimed."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Encounter, InboundMessage, Patient
from app.modules.audit.service import record_event
from app.modules.laboratory.service import (
    LaboratoryError, ObservationValue, OrderCommand, ResultCommand, ingest_order, ingest_result,
)


MANIFEST = Path(__file__).resolve().parents[5] / "data/fixtures/scenario.json"
MAX_MESSAGE_BYTES = 64 * 1024


class ProfileError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ParsedMessage:
    message_type: str
    source: str
    control_id: str
    sent_at: datetime
    patient_domain: str
    patient_external_id: str
    encounter_external_id: str
    placer_number: str
    filler_number: str
    panel_code: str
    observations: tuple[ObservationValue, ...]
    correction: bool


def _field(parts: list[str], number: int, *, msh: bool = False) -> str:
    index = number - 1 if msh else number
    return parts[index] if index < len(parts) else ""


def _only_fields(parts: list[str], allowed: set[int], *, msh: bool = False) -> None:
    for index, value in enumerate(parts[1:], 1):
        number = index + 1 if msh else index
        if number not in allowed and value:
            raise ProfileError("INVALID_PROFILE")


def _components(value: str, count: int) -> tuple[str, ...]:
    parts = tuple(value.split("^"))
    if len(parts) != count or any(not part for part in (parts[0], parts[-1])):
        raise ProfileError("INVALID_PROFILE")
    return parts


def parse_message(raw: bytes) -> ParsedMessage:
    if not raw or len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\r"):
        raise ProfileError("INVALID_PROFILE")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileError("INVALID_ENCODING") from exc
    if "\n" in content or "\x00" in content or "\r\r" in content:
        raise ProfileError("INVALID_PROFILE")
    lines = content[:-1].split("\r")
    if len(lines) < 5 or not lines[0].startswith("MSH|"):
        raise ProfileError("INVALID_PROFILE")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    profile = manifest["hl7"]
    identity = manifest["identity"]
    lab = manifest["laboratory"]
    msh = lines[0].split("|")
    _only_fields(msh, {2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 18}, msh=True)
    if (_field(msh, 2, msh=True) != r"^~\&" or _field(msh, 3, msh=True) != profile["sending_application"]
            or _field(msh, 4, msh=True) != profile["sending_facility"]
            or _field(msh, 5, msh=True) != profile["receiving_application"]
            or _field(msh, 6, msh=True) != profile["receiving_facility"]
            or _field(msh, 11, msh=True) != "P" or _field(msh, 12, msh=True) != "2.5.1"
            or _field(msh, 18, msh=True) != "UNICODE UTF-8"):
        raise ProfileError("INVALID_PROFILE")
    control_id = _field(msh, 10, msh=True)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", control_id):
        raise ProfileError("INVALID_PROFILE")
    message_type = _field(msh, 9, msh=True)
    if message_type not in {"OML^O21^OML_O21", "ORU^R01^ORU_R01"}:
        raise ProfileError("INVALID_PROFILE")
    try:
        sent_at = datetime.strptime(_field(msh, 7, msh=True), "%Y%m%d%H%M%S%z")
    except ValueError as exc:
        raise ProfileError("INVALID_PROFILE") from exc
    names = [line.split("|", 1)[0] for line in lines]
    is_order = message_type.startswith("OML")
    if (is_order and names != ["MSH", "PID", "PV1", "ORC", "OBR"]
            or not is_order and (names[:4] != ["MSH", "PID", "PV1", "OBR"]
                                 or len(names) not in {5, 6} or any(name != "OBX" for name in names[4:]))):
        raise ProfileError("INVALID_PROFILE")
    pid, pv1 = (lines[index].split("|") for index in (1, 2))
    _only_fields(pid, {1, 3})
    _only_fields(pv1, {1, 2, 19})
    if _field(pid, 1) != "1" or _field(pv1, 1) != "1" or _field(pv1, 2) != "O":
        raise ProfileError("INVALID_PROFILE")
    patient_ref = _components(_field(pid, 3), 5)
    encounter_ref = _components(_field(pv1, 19), 4)
    if (patient_ref[1:3] != ("", "") or patient_ref[4] != "MR"
            or encounter_ref[1:3] != ("", "") or patient_ref[3] != encounter_ref[3]
            or patient_ref[3] != identity["identifier_domain"]):
        raise ProfileError("INVALID_PROFILE")
    if is_order:
        orc = lines[3].split("|")
        _only_fields(orc, {1, 2, 3})
        if _field(orc, 1) != "NW":
            raise ProfileError("INVALID_PROFILE")
        obr = lines[4].split("|")
        if _field(orc, 2) != _field(obr, 2) or _field(orc, 3) != _field(obr, 3):
            raise ProfileError("INVALID_PROFILE")
    else:
        obr = lines[3].split("|")
    _only_fields(obr, {1, 2, 3, 4} | ({25} if not is_order else set()))
    if _field(obr, 1) != "1":
        raise ProfileError("INVALID_PROFILE")
    placer = _components(_field(obr, 2), 2)
    filler = _components(_field(obr, 3), 2)
    panel = _components(_field(obr, 4), 3)
    if (placer[1] != identity["identifier_domain"] or filler[1] != lab["source_system"]
            or panel != (profile["panel_code"], profile["panel_display"], identity["identifier_domain"])):
        raise ProfileError("INVALID_PROFILE")
    status = _field(obr, 25)
    if is_order and status or not is_order and status not in {"F", "C"}:
        raise ProfileError("INVALID_PROFILE")
    observations = []
    for number, line in enumerate(lines[4:] if not is_order else (), 1):
        obx = line.split("|")
        _only_fields(obx, {1, 2, 3, 5, 6, 11})
        code, display, coding_system = _components(_field(obx, 3), 3)
        if (_field(obx, 1) != str(number) or _field(obx, 2) != "NM"
                or _field(obx, 11) != status or not _field(obx, 5)):
            raise ProfileError("INVALID_PROFILE")
        try:
            value = float(_field(obx, 5))
        except ValueError as exc:
            raise ProfileError("INVALID_OBSERVATION") from exc
        if not math.isfinite(value):
            raise ProfileError("INVALID_OBSERVATION")
        observations.append(ObservationValue(coding_system, code, value, unit=_field(obx, 6)))
        expected = next((item for item in lab["expected_observations"]
                         if (item["coding_system"], item["code"]) == (coding_system, code)), None)
        if expected is None or display != expected["display"] or _field(obx, 6) != expected["unit"]:
            raise ProfileError("INVALID_OBSERVATION")
    if len({(item.coding_system, item.code) for item in observations}) != len(observations):
        raise ProfileError("INVALID_OBSERVATION")
    return ParsedMessage("OML_O21" if is_order else "ORU_R01", profile["sending_application"], control_id,
                         sent_at, patient_ref[3], patient_ref[0], encounter_ref[0], placer[0], filler[0],
                         panel[0], tuple(observations), status == "C")


def _existing_message(db: Session, parsed: ParsedMessage, content_hash: str) -> InboundMessage | None:
    marker = db.scalar(select(InboundMessage).where(
        InboundMessage.source_system == parsed.source,
        InboundMessage.external_message_id == parsed.control_id,
    ))
    if marker is None:
        return None
    if marker.payload_hash != content_hash or marker.message_type != parsed.message_type:
        raise ProfileError("MESSAGE_CONFLICT")
    if marker.processing_status == "processed":
        return marker
    raise ProfileError(marker.error_code or "MESSAGE_REJECTED")


def process_message(factory: sessionmaker[Session], raw: bytes, correlation_id: str) -> tuple[ParsedMessage, bool]:
    parsed = parse_message(raw)
    content_hash = hashlib.sha256(raw).hexdigest()
    with factory.begin() as db:
        existing = _existing_message(db, parsed, content_hash)
        if existing:
            record_event(db, actor_user_id=None, action="hl7.receive", resource_type="inbound_message",
                         resource_id=existing.id, outcome="replayed", correlation_id=correlation_id)
            return parsed, True
        patient = db.scalar(select(Patient).where(
            Patient.identifier_domain == parsed.patient_domain,
            Patient.external_id == parsed.patient_external_id,
        ))
        if patient is None:
            raise ProfileError("IDENTITY_UNKNOWN")
        encounter = db.scalar(select(Encounter).where(
            Encounter.patient_id == patient.id,
            Encounter.external_id == parsed.encounter_external_id,
        ))
        if encounter is None:
            raise ProfileError("ENCOUNTER_UNKNOWN")
        patient_id, encounter_id = patient.id, encounter.id
    try:
        if parsed.message_type == "OML_O21":
            receipt = ingest_order(factory, OrderCommand(
                parsed.source, parsed.control_id, content_hash, patient_id, encounter_id,
                parsed.placer_number, parsed.filler_number, parsed.panel_code, parsed.sent_at), correlation_id)
        else:
            receipt = ingest_result(factory, ResultCommand(
                parsed.source, parsed.control_id, content_hash, patient_id, encounter_id,
                parsed.placer_number, parsed.filler_number, parsed.panel_code, parsed.sent_at,
                parsed.observations, parsed.correction), correlation_id)
    except LaboratoryError as exc:
        raise ProfileError(exc.code) from exc
    return parsed, receipt.replayed


def message_header(raw: bytes) -> tuple[str, str, str]:
    """Extract safe technical keys for an ACK and a rejection trace."""
    try:
        first = raw.split(b"\r", 1)[0].decode("utf-8").split("|")
    except UnicodeDecodeError:
        return "", "", ""
    if not first or first[0] != "MSH":
        return "", "", ""
    source, control, kind = (_field(first, number, msh=True) for number in (3, 10, 9))
    source = source if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", source) else ""
    control = control if re.fullmatch(r"[A-Za-z0-9._-]{1,100}", control) else ""
    kind = kind if kind in {"OML^O21^OML_O21", "ORU^R01^ORU_R01"} else ""
    return source, control, kind


def record_rejection(factory: sessionmaker[Session], raw: bytes, code: str, correlation_id: str) -> None:
    source, control, kind = message_header(raw)
    message_type = "OML_O21" if kind.startswith("OML^") else "ORU_R01" if kind.startswith("ORU^") else "INVALID"
    content_hash = hashlib.sha256(raw).hexdigest()
    with factory.begin() as db:
        marker = None
        if source and control:
            marker = db.scalar(select(InboundMessage).where(
                InboundMessage.source_system == source,
                InboundMessage.external_message_id == control,
            ))
            if marker is None:
                marker = InboundMessage(id=str(uuid4()), source_system=source, external_message_id=control,
                                        message_type=message_type, processing_status="rejected",
                                        payload_hash=content_hash, error_code=code)
                db.add(marker)
        record_event(db, actor_user_id=None, action="hl7.receive", resource_type="inbound_message",
                     resource_id=marker.id if marker else None, outcome="rejected", correlation_id=correlation_id)


def build_ack(control_id: str, kind: str, acknowledgement: str, code: str = "") -> bytes:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["hl7"]
    trigger = "O21" if kind.startswith("OML^") else "R01"
    fields = ["MSH"] + [""] * 17
    values = {2: r"^~\&", 3: manifest["receiving_application"], 4: manifest["receiving_facility"],
              5: manifest["sending_application"], 6: manifest["sending_facility"],
              7: datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%z"),
              9: f"ACK^{trigger}^ACK", 10: str(uuid4()), 11: "P", 12: "2.5.1", 18: "UNICODE UTF-8"}
    for number, value in values.items():
        fields[number - 1] = value
    msa = f"MSA|{acknowledgement}|{control_id}|{code}" if code else f"MSA|{acknowledgement}|{control_id}"
    return ("|".join(fields) + "\r" + msa + "\r").encode("utf-8")

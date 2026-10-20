"""T04 laboratory invariants on an ephemeral relational database."""

import hashlib
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.cli import seed_demo  # noqa: E402
from app.db.models import Base, Encounter, InboundMessage, LabObservation, LabOrder, LabReport, Patient  # noqa: E402
from app.modules.laboratory.service import (  # noqa: E402
    LaboratoryError, ObservationValue, OrderCommand, ResultCommand,
    get_encounter_reports, ingest_order, ingest_result,
)


PATIENT = "10000000-0000-4000-8000-000000000001"
ENCOUNTER = "20000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class LaboratoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        seed_demo(self.factory)

    def tearDown(self):
        self.engine.dispose()

    def order(self, **changes):
        values = dict(source="DEMO-LIS", control_id="DEMO-OML-001", content_hash=digest("order"),
                      patient_id=PATIENT, encounter_id=ENCOUNTER, placer_number="DEMO-LAB001",
                      filler_number="DEMO-LIS001", panel_code="LAB-PANEL", ordered_at=NOW)
        values.update(changes)
        return OrderCommand(**values)

    def result(self, **changes):
        values = dict(source="DEMO-LIS", control_id="DEMO-ORU-001", content_hash=digest("result"),
                      patient_id=PATIENT, encounter_id=ENCOUNTER, placer_number="DEMO-LAB001",
                      filler_number="DEMO-LIS001", panel_code="LAB-PANEL", reported_at=NOW,
                      observations=(ObservationValue("DEMO", "CRP", 3.2, unit="mg/L"),
                                    ObservationValue("DEMO", "GLU", 4.8, unit="mmol/L")))
        values.update(changes)
        return ResultCommand(**values)

    def test_nominal_report_and_exact_replay(self):
        first_order = ingest_order(self.factory, self.order())
        self.assertFalse(first_order.replayed)
        self.assertEqual(ingest_order(self.factory, self.order()).lab_order_id, first_order.lab_order_id)
        first_report = ingest_result(self.factory, self.result())
        self.assertEqual((first_report.version, first_report.replayed), (1, False))
        replay = ingest_result(self.factory, self.result())
        self.assertEqual((replay.lab_report_id, replay.version, replay.replayed),
                         (first_report.lab_report_id, 1, True))
        with self.factory() as db:
            projection = get_encounter_reports(db, ENCOUNTER)
            self.assertEqual(projection["status"], "available")
            self.assertEqual(projection["reports"][0]["version"], 1)
            self.assertEqual(projection["warnings"], [])
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 2)
            self.assertEqual(db.scalar(select(func.count()).select_from(LabReport)), 1)

    def test_missing_crp_is_null_and_zero_remains_a_value(self):
        ingest_order(self.factory, self.order())
        ingest_result(self.factory, self.result(observations=(ObservationValue("DEMO", "GLU", 0.0, unit="mmol/L"),)))
        with self.factory() as db:
            result = get_encounter_reports(db, ENCOUNTER)
            values = {item["code"]: item for item in result["reports"][0]["observations"]}
            self.assertEqual(result["status"], "partial")
            self.assertEqual((values["CRP"]["data_status"], values["CRP"]["value_numeric"],
                              values["CRP"]["value_text"]), ("missing", None, None))
            self.assertEqual((values["GLU"]["data_status"], values["GLU"]["value_numeric"]), ("available", 0.0))
            self.assertEqual(result["warnings"][0]["field"], "CRP")

    def test_correction_creates_new_version_and_preserves_original(self):
        ingest_order(self.factory, self.order())
        original = ingest_result(self.factory, self.result())
        corrected = ingest_result(self.factory, self.result(
            control_id="DEMO-ORU-CORRECTION-001", content_hash=digest("correction"), correction=True,
            observations=(ObservationValue("DEMO", "CRP", 3.4, unit="mg/L"),
                          ObservationValue("DEMO", "GLU", 4.8, unit="mmol/L"))))
        self.assertEqual(corrected.version, 2)
        self.assertNotEqual(corrected.lab_report_id, original.lab_report_id)
        with self.factory() as db:
            reports = list(db.scalars(select(LabReport).order_by(LabReport.version)))
            old_crp = db.scalar(select(LabObservation).where(
                LabObservation.lab_report_id == original.lab_report_id, LabObservation.code == "CRP"))
            self.assertEqual([item.version for item in reports], [1, 2])
            self.assertEqual(old_crp.value_numeric, 3.2)
            self.assertEqual(get_encounter_reports(db, ENCOUNTER)["reports"][0]["id"], corrected.lab_report_id)

    def test_conflict_and_bad_values_leave_no_partial_writes(self):
        ingest_order(self.factory, self.order())
        for command in (
            self.result(observations=(ObservationValue("DEMO", "CRP", float("nan"), unit="mg/L"),)),
            self.result(observations=(ObservationValue("DEMO", "UNKNOWN", 1.0, unit="mg/L"),)),
            self.result(observations=(ObservationValue("DEMO", "CRP", 1.0, unit="wrong"),)),
            self.result(correction=True),
        ):
            with self.assertRaises(LaboratoryError):
                ingest_result(self.factory, command)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(LabReport)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 1)
        ingest_result(self.factory, self.result())
        with self.assertRaisesRegex(LaboratoryError, "MESSAGE_CONFLICT"):
            ingest_result(self.factory, self.result(content_hash=digest("different")))
        with self.assertRaisesRegex(LaboratoryError, "ORDER_CONFLICT"):
            ingest_order(self.factory, self.order(control_id="another", content_hash=digest("another")))
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 2)

    def test_identity_mismatch_is_rejected_without_identity_writes(self):
        with self.assertRaisesRegex(LaboratoryError, "ENCOUNTER_UNKNOWN"):
            ingest_order(self.factory, self.order(patient_id="10000000-0000-4000-8000-000000000002"))
        ingest_order(self.factory, self.order())
        with self.assertRaisesRegex(LaboratoryError, "ORDER_UNKNOWN"):
            ingest_result(self.factory, self.result(filler_number="wrong"))
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Patient)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Encounter)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(LabOrder)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 1)


if __name__ == "__main__":
    unittest.main()

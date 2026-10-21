"""HTTP HL7 profile, ingestion, ACK and rejection behavior."""

import os
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.cli import seed_demo  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.db.models import AuditEvent, Base, InboundMessage, LabObservation, LabOrder, LabReport  # noqa: E402
from app.main import create_app  # noqa: E402


HL7 = ROOT / "data/hl7"
HEADERS = {"Authorization": "Bearer test-service-secret",
           "Content-Type": "application/hl7-v2; charset=utf-8"}


class HL7Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        seed_demo(self.factory)
        self.client = TestClient(create_app(Settings("sqlite+pysqlite:///:memory:",
                                                  "http://127.0.0.1:8000", False, "test-service-secret"), self.factory))

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def send(self, filename: str, *, headers=None, body=None):
        return self.client.post("/internal/hl7/messages", content=body if body is not None else (HL7 / filename).read_bytes(),
                                headers=HEADERS if headers is None else headers)

    def test_order_result_replay_and_correction(self):
        order = self.send("order.oml.hl7")
        result = self.send("result.nominal.oru.hl7")
        replay = self.send("result.nominal.oru.hl7")
        correction = self.send("result.correction.oru.hl7")
        for response in (order, result, replay, correction):
            self.assertEqual(response.status_code, 200)
            self.assertIn("MSA|AA|", response.text)
        self.assertIn("MSA|AA|DEMO-ORU-001", replay.text)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(LabOrder)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(LabReport)), 2)
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 3)
            self.assertEqual([item.version for item in db.scalars(select(LabReport).order_by(LabReport.version))], [1, 2])

    def test_missing_crp_is_stored_as_null(self):
        self.send("order.oml.hl7")
        response = self.send("result.missing-crp.oru.hl7")
        self.assertEqual(response.status_code, 200)
        with self.factory() as db:
            crp = db.scalar(select(LabObservation).where(LabObservation.code == "CRP"))
            self.assertEqual(crp.data_status, "missing")
            self.assertIsNone(crp.value_numeric)

    def test_auth_and_size_fail_before_parsing(self):
        bad_auth = self.send("order.oml.hl7", headers={"Content-Type": HEADERS["Content-Type"]})
        self.assertEqual(bad_auth.status_code, 401)
        self.assertNotIn("MSA|", bad_auth.text)
        large = self.send("order.oml.hl7", body=b"X" * (64 * 1024 + 1))
        self.assertEqual(large.status_code, 413)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 0)

    def test_conflicting_replay_and_malformed_value_are_rejected_and_traced(self):
        self.send("order.oml.hl7")
        original = (HL7 / "result.nominal.oru.hl7").read_bytes()
        self.assertEqual(self.send("result.nominal.oru.hl7").status_code, 200)
        conflicting = self.send("result.nominal.oru.hl7", body=original.replace(b"3.2", b"3.3"))
        self.assertEqual(conflicting.status_code, 409)
        self.assertIn("MSA|AR|DEMO-ORU-001|MESSAGE_CONFLICT", conflicting.text)
        malformed = original.replace(b"DEMO-ORU-001", b"DEMO-ORU-BAD").replace(b"3.2", b"NaN")
        invalid = self.send("result.nominal.oru.hl7", body=malformed)
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("MSA|AR|DEMO-ORU-BAD|INVALID_OBSERVATION", invalid.text)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(LabReport)), 1)
            marker = db.scalar(select(InboundMessage).where(InboundMessage.external_message_id == "DEMO-ORU-BAD"))
            self.assertEqual(marker.processing_status, "rejected")
            self.assertEqual(marker.error_code, "INVALID_OBSERVATION")
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent)
                                       .where(AuditEvent.action == "hl7.receive")), 2)

    def test_unknown_patient_rejected_without_identity_creation(self):
        order = (HL7 / "order.oml.hl7").read_bytes()
        unknown = order.replace(b"DEMO-P001", b"DEMO-P999").replace(b"DEMO-OML-001", b"DEMO-OML-UNKNOWN")
        response = self.send("order.oml.hl7", body=unknown)
        self.assertEqual(response.status_code, 422)
        self.assertIn("IDENTITY_UNKNOWN", response.text)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(LabOrder)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 1)

    def test_failed_audit_blocks_success_ack_and_business_write(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_event "
                                    "BEGIN SELECT RAISE(FAIL, 'audit down'); END"))
        response = self.send("order.oml.hl7")
        self.assertEqual(response.status_code, 503)
        self.assertIn("MSA|AE|DEMO-OML-001|SERVICE_UNAVAILABLE", response.text)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(LabOrder)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 0)


if __name__ == "__main__":
    unittest.main()

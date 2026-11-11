"""Real PostgreSQL races; run only against a fresh, dedicated loopback *_test database."""

import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.cli import complete_demo_radiology, seed_demo, seed_radiology_demo  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.db.models import (  # noqa: E402
    AppUser, ImagingStudy, InboundMessage, LabOrder, LabReport, RadiologyOrder,
    Role, UserEncounterAccess, UserRole,
)
from app.integrations.hl7.service import process_message  # noqa: E402
from app.integrations.orthanc.client import OrthancStudy  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.auth.service import hash_password  # noqa: E402
from app.modules.imaging.service import match_study  # noqa: E402
from app.modules.radiology.service import (  # noqa: E402
    RadiologyError, create_order, mark_performed, save_report_draft, validate_report,
)

ENCOUNTER = "20000000-0000-4000-8000-000000000001"
PATIENT = "10000000-0000-4000-8000-000000000001"


class FakeOrthanc:
    study = OrthancStudy(
        orthanc_id="aaaaaaaa-bbbbbbbb-cccccccc-dddddddd-eeeeeeee",
        study_instance_uid="2.25.10101", patient_id="DEMO-P001", issuer_of_patient_id="DEMO",
        accession_number="DEMO-ACC001", modality="CT", series_count=1, instance_count=1)

    def find_study(self, uid, timeout_ms):
        return self.study

    def get_study(self, orthanc_id, timeout_ms):
        return self.study

    def get_preview(self, orthanc_id, timeout_ms):
        return b"\x89PNG\r\n\x1a\nsynthetic-preview"


class PostgresConcurrencyTests(unittest.TestCase):
    def test_replays_and_transitions_are_serialized(self):
        url = os.getenv("PG_TEST_DATABASE_URL", "")
        if not url:
            self.skipTest("PG_TEST_DATABASE_URL not set")
        parsed = urlsplit(url)
        if (parsed.scheme != "postgresql+psycopg" or parsed.hostname not in {"127.0.0.1", "localhost"}
                or not parsed.path.endswith("_test")):
            self.fail("Use a dedicated loopback PostgreSQL database named *_test")
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one(),
                                 "0003_imaging_role")
                self.assertEqual(conn.execute(text("SELECT count(*) FROM patient")).scalar_one(), 0,
                                 "The PostgreSQL test database must be fresh")
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            seed_demo(factory)
            seed_radiology_demo(factory)
            with factory.begin() as db:
                for name in ("physician", "radiologist"):
                    if db.get(Role, name) is None:
                        db.add(Role(name=name))
                db.flush()
                doctor_id = str(uuid4())
                radiologist_id = str(uuid4())
                db.add_all([AppUser(id=doctor_id, username="pg-doctor",
                                    password_hash=hash_password("temporary-test-password"),
                                    is_active=True, failed_attempts=0),
                            AppUser(id=radiologist_id, username="pg-radiologist", password_hash="test-only",
                                    is_active=True, failed_attempts=0)])
                db.flush()
                db.add_all([UserRole(user_id=doctor_id, role_name="physician"),
                            UserRole(user_id=radiologist_id, role_name="radiologist"),
                            UserEncounterAccess(user_id=doctor_id, encounter_id=ENCOUNTER),
                            UserEncounterAccess(user_id=radiologist_id, encounter_id=ENCOUNTER)])

            def concurrent(fn, count=4):
                with ThreadPoolExecutor(max_workers=count) as executor:
                    return list(executor.map(lambda _: fn(), range(count)))

            for filename, table in (("order.oml.hl7", LabOrder), ("result.nominal.oru.hl7", LabReport)):
                payload = (ROOT / "data/hl7" / filename).read_bytes()
                responses = concurrent(lambda: process_message(factory, payload, str(uuid4())))
                self.assertEqual(sum(not replayed for _, replayed in responses), 1)
                with factory() as db:
                    self.assertEqual(db.scalar(select(func.count()).select_from(table)), 1)
            with factory() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(InboundMessage)), 2)

            accession = "PG-RIS-" + uuid4().hex[:12]

            def new_order():
                try:
                    return create_order(factory, actor_user_id=radiologist_id, encounter_id=ENCOUNTER,
                                        accession_number=accession, requested_procedure="CT fictif", modality="CT")
                except RadiologyError as exc:
                    return exc.code

            created = concurrent(new_order, 2)
            self.assertEqual(sum(isinstance(item, dict) for item in created), 1)
            self.assertEqual(sum(item == "ACCESSION_CONFLICT" for item in created), 1)
            exam_id = next(item["exam_id"] for item in created if isinstance(item, dict))

            from datetime import datetime, timezone
            performed_at = datetime(2026, 1, 15, 9, 40, tzinfo=timezone.utc)

            def perform():
                try:
                    mark_performed(factory, actor_user_id=radiologist_id, exam_id=exam_id,
                                   performed_at=performed_at)
                    return "performed"
                except RadiologyError as exc:
                    return exc.code

            self.assertEqual(sorted(concurrent(perform, 2)), ["INVALID_TRANSITION", "performed"])
            save_report_draft(factory, actor_user_id=radiologist_id, exam_id=exam_id,
                              content="Compte rendu fictif PostgreSQL")

            def finalize():
                try:
                    validate_report(factory, actor_user_id=radiologist_id, exam_id=exam_id,
                                    validated_at=performed_at)
                    return "final"
                except RadiologyError as exc:
                    return exc.code

            self.assertEqual(sorted(concurrent(finalize, 2)), ["INVALID_TRANSITION", "final"])
            matched = concurrent(lambda: match_study(
                factory, FakeOrthanc(), patient_id=PATIENT, accession_number="DEMO-ACC001",
                study_instance_uid="2.25.10101", modality="CT"), 2)
            self.assertEqual(sorted(item["replayed"] for item in matched), [False, True])
            with factory() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(RadiologyOrder)
                                           .where(RadiologyOrder.accession_number == accession)), 1)
                self.assertEqual(db.scalar(select(func.count()).select_from(ImagingStudy)), 1)

            complete_demo_radiology(factory, "pg-radiologist")
            origin = "http://127.0.0.1:8000"
            with TestClient(create_app(Settings(url, origin, False), factory, FakeOrthanc())) as client:
                login = client.post("/api/v1/auth/login",
                                    json={"username": "pg-doctor", "password": "temporary-test-password"},
                                    headers={"Origin": origin})
                self.assertEqual(login.status_code, 200)
                summary = client.get(f"/api/v1/encounters/{ENCOUNTER}/summary")
                self.assertEqual(summary.status_code, 200)
                self.assertEqual(summary.json()["laboratory"]["status"], "available")
                self.assertEqual(summary.json()["radiology"]["exams"][0]["report"]["status"], "final")
                self.assertEqual(summary.json()["imaging"]["availability_status"], "incomplete")
                self.assertEqual(summary.json()["imaging"]["studies"][0]["availability_status"], "available")
                study_id = summary.json()["imaging"]["studies"][0]["id"]
                self.assertEqual(client.get(f"/api/v1/imaging-studies/{study_id}/preview").status_code, 200)
                durations = []
                for _ in range(30):
                    start = time.perf_counter()
                    response = client.get(f"/api/v1/encounters/{ENCOUNTER}/summary")
                    durations.append(time.perf_counter() - start)
                    self.assertEqual(response.status_code, 200)
                p95 = sorted(durations)[28]
                print(f"PostgreSQL summary p95 over 30 warm reads: {p95:.3f}s")
                self.assertLess(p95, 1.0)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

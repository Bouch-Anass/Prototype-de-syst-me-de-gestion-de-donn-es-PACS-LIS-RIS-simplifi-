"""T08 authenticated composition over the real domain projections."""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
sys.path.insert(0, str(ROOT))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.cli import seed_demo, seed_radiology_demo  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.db.models import (  # noqa: E402
    AppUser, AuditEvent, Base, RadiologyExam, RadiologyOrder, RadiologyReport,
    Role, UserEncounterAccess, UserRole,
)
from app.integrations.orthanc.client import OrthancStudy, OrthancUnavailable  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.auth.service import hash_password  # noqa: E402
from app.modules.imaging.service import match_study  # noqa: E402
from simulators.modality.generate_and_send import generate  # noqa: E402

ORIGIN = "http://127.0.0.1:8000"
ENCOUNTER_ID = "20000000-0000-4000-8000-000000000001"
EXAM_ID = "60000000-0000-4000-8000-000000000001"
HL7_HEADERS = {"Authorization": "Bearer test-service-secret",
               "Content-Type": "application/hl7-v2; charset=utf-8"}


class FakeOrthanc:
    def __init__(self):
        self.down = False
        self.study = OrthancStudy(
            orthanc_id="aaaaaaaa-bbbbbbbb-cccccccc-dddddddd-eeeeeeee",
            study_instance_uid="2.25.10101", patient_id="DEMO-P001",
            issuer_of_patient_id="DEMO", accession_number="DEMO-ACC001",
            modality="CT", series_count=1, instance_count=1)

    def find_study(self, uid, timeout_ms):
        return self.study

    def get_study(self, orthanc_id, timeout_ms):
        if self.down:
            raise OrthancUnavailable("ORTHANC_UNAVAILABLE")
        return self.study

    def get_preview(self, orthanc_id, timeout_ms):
        if self.down:
            raise OrthancUnavailable("ORTHANC_UNAVAILABLE")
        return b"\x89PNG\r\n\x1a\nsynthetic-preview"

    def store_instance(self, payload, timeout_ms=5000):
        return "aaaaaaaa-bbbbbbbb-cccccccc-dddddddd-eeeeeeee"


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        seed_demo(self.factory)
        seed_radiology_demo(self.factory)
        with self.factory.begin() as db:
            db.add_all([Role(name=name) for name in ("physician", "radiologist", "lab_technician", "imaging_technician", "admin")])
            db.flush()
            for name, role, grant in (("doctor", "physician", True), ("radiologist", "radiologist", True),
                                      ("technician", "lab_technician", True),
                                      ("imaging", "imaging_technician", True),
                                      ("outsider", "physician", False)):
                user_id = str(uuid4())
                db.add(AppUser(id=user_id, username=name, password_hash=hash_password("correct-password"),
                               is_active=True, failed_attempts=0))
                db.flush()
                db.add(UserRole(user_id=user_id, role_name=role))
                if grant:
                    db.add(UserEncounterAccess(user_id=user_id, encounter_id=ENCOUNTER_ID))
            exam = db.get(RadiologyExam, EXAM_ID)
            exam.status = "performed"
            exam.performed_at = datetime(2026, 1, 15, 9, 40, tzinfo=timezone.utc)
            db.get(RadiologyOrder, exam.order_id).status = "completed"
            db.add(RadiologyReport(id="70000000-0000-4000-8000-000000000001", exam_id=EXAM_ID,
                                   content="Compte rendu fictif.", status="final",
                                   validated_at=datetime(2026, 1, 15, 9, 55, tzinfo=timezone.utc)))
        self.orthanc = FakeOrthanc()
        settings = Settings("sqlite+pysqlite:///:memory:", ORIGIN, False, "test-service-secret")
        self.client = TestClient(create_app(settings, self.factory, self.orthanc))

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def login(self, name="doctor"):
        return self.client.post("/api/v1/auth/login", json={"username": name, "password": "correct-password"},
                                headers={"Origin": ORIGIN})

    def send(self, filename):
        return self.client.post("/internal/hl7/messages", headers=HL7_HEADERS,
                                content=(ROOT / "data/hl7" / filename).read_bytes())

    def summary(self):
        return self.client.get(f"/api/v1/encounters/{ENCOUNTER_ID}/summary")

    def csrf_headers(self):
        return {"Origin": ORIGIN, "X-CSRF-Token": self.client.cookies.get("csrf_token")}

    def test_nominal_summary_from_hl7_ris_and_orthanc(self):
        self.assertEqual(self.send("order.oml.hl7").status_code, 200)
        self.assertEqual(self.send("result.nominal.oru.hl7").status_code, 200)
        match_study(self.factory, self.orthanc, patient_id="10000000-0000-4000-8000-000000000001",
                    accession_number="DEMO-ACC001", study_instance_uid="2.25.10101", modality="CT")
        self.login()
        response = self.summary()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["patient"]["external_id"], "DEMO-P001")
        self.assertEqual(body["laboratory"]["status"], "available")
        self.assertEqual(body["radiology"]["exams"][0]["report"]["status"], "final")
        self.assertEqual(body["radiology"]["exams"][0]["requested_procedure"], "CT synthétique DEMO-001")
        self.assertEqual(body["radiology"]["exams"][0]["priority"], "routine")
        self.assertEqual(body["imaging"]["availability_status"], "available")
        self.assertEqual(body["warnings"], [])

    def test_frontend_requires_login_and_session_can_be_restored(self):
        self.assertEqual(self.client.get("/frontend/").status_code, 200)
        page = self.client.get("/frontend/").text
        self.assertIn('id="login-form"', page)
        self.assertNotIn('data-mode="mock"', page)
        self.assertNotIn('data-scenario="nominal"', page)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.login("technician")
        self.assertIn("lab_technician", self.client.get("/api/v1/auth/me").json()["roles"])
        self.assertEqual(self.client.get("/frontend/app.js").status_code, 200)

    def test_missing_result_and_pacs_outage_are_visible_without_losing_business_data(self):
        self.send("order.oml.hl7")
        self.send("result.missing-crp.oru.hl7")
        match_study(self.factory, self.orthanc, patient_id="10000000-0000-4000-8000-000000000001",
                    accession_number="DEMO-ACC001", study_instance_uid="2.25.10101", modality="CT")
        self.orthanc.down = True
        self.login()
        response = self.summary()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["laboratory"]["status"], "partial")
        values = {item["code"]: item for item in body["laboratory"]["reports"][0]["observations"]}
        self.assertIsNone(values["CRP"]["value_numeric"])
        self.assertEqual(values["GLU"]["value_numeric"], 4.8)
        self.assertEqual(body["imaging"]["availability_status"], "unavailable")
        self.assertEqual({warning["code"] for warning in body["warnings"]},
                         {"LAB_RESULT_MISSING", "IMAGING_UNAVAILABLE"})

    def test_access_and_audit_failure(self):
        self.assertEqual(self.summary().status_code, 401)
        self.login("technician")
        self.assertEqual(self.summary().status_code, 200)
        self.login("imaging")
        self.assertEqual(self.summary().status_code, 200)
        self.login("outsider")
        self.assertEqual(self.summary().status_code, 403)
        with self.factory() as db:
            self.assertEqual(len(list(db.scalars(select(AuditEvent).where(
                AuditEvent.action == "encounter.summary", AuditEvent.outcome == "denied")))), 1)
        self.login()
        with self.engine.begin() as conn:
            conn.execute(text("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_event "
                              "BEGIN SELECT RAISE(FAIL, 'audit down'); END"))
        result = self.summary()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("DEMO-P001", result.text)

    def test_ris_http_requires_csrf_and_radiologist_validation(self):
        self.login()
        body = {"encounter_id": ENCOUNTER_ID, "accession_number": "DEMO-ACC002",
                "requested_procedure": "CT synthétique", "modality": "CT"}
        self.assertEqual(self.client.post("/api/v1/radiology-orders", json=body).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/radiology-orders", json=body,
                                          headers=self.csrf_headers()).status_code, 403)
        self.login("radiologist")
        created = self.client.post("/api/v1/radiology-orders", json=body, headers=self.csrf_headers())
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.post("/api/v1/radiology-orders", json=body,
                                          headers=self.csrf_headers()).status_code, 409)
        exam_id = created.json()["exam_id"]
        path = f"/api/v1/radiology-exams/{exam_id}"
        performed = {"status": "performed", "performed_at": "2026-01-15T09:40:00Z"}
        self.login()
        self.assertEqual(self.client.patch(path, json=performed, headers=self.csrf_headers()).status_code, 403)
        self.login("radiologist")
        self.assertEqual(self.client.patch(path, json=performed, headers=self.csrf_headers()).status_code, 200)
        draft = self.client.put(path + "/report", json={"content": "Compte rendu fictif"},
                                headers=self.csrf_headers())
        self.assertEqual(draft.status_code, 200)
        final = self.client.post(path + "/report/validate",
                                 json={"validated_at": "2026-01-15T09:55:00Z"}, headers=self.csrf_headers())
        self.assertEqual(final.status_code, 200)
        self.assertEqual(final.json()["report_id"], draft.json()["report_id"])
        self.assertEqual(self.client.put(path + "/report", json={"content": "changed"},
                                         headers=self.csrf_headers()).status_code, 409)

    def test_viewer_is_authorized_and_pacs_outage_is_contained(self):
        linked = match_study(self.factory, self.orthanc, patient_id="10000000-0000-4000-8000-000000000001",
                             accession_number="DEMO-ACC001", study_instance_uid="2.25.10101", modality="CT")
        path = f"/api/v1/imaging-studies/{linked['imaging_study_id']}"
        self.assertEqual(self.client.get(path + "/preview").status_code, 401)
        self.login("technician")
        self.assertEqual(self.client.get(path + "/preview").status_code, 200)
        self.login("imaging")
        self.assertEqual(self.client.get(path + "/preview").status_code, 200)
        self.login()
        self.assertEqual(self.client.get(path).status_code, 200)
        link = self.client.get(path + "/viewer-link")
        self.assertEqual(link.status_code, 200)
        self.assertEqual(link.json()["url"], path + "/preview")
        preview = self.client.get(link.json()["url"])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/png")
        self.assertEqual(preview.headers["cache-control"], "no-store")
        self.assertNotIn("orthanc", preview.text.lower())
        self.orthanc.down = True
        self.assertEqual(self.client.get(path + "/preview").status_code, 503)

    def test_lab_role_can_add_version_but_other_roles_cannot(self):
        self.send("order.oml.hl7")
        self.send("result.nominal.oru.hl7")
        self.login("doctor")
        order_id = self.summary().json()["laboratory"]["reports"][0]["lab_order_id"]
        path = f"/api/v1/lab-orders/{order_id}/reports"
        body = {"observations": [{"code": "CRP", "value_numeric": 5.1, "unit": "mg/L"},
                                 {"code": "GLU", "value_numeric": 4.6, "unit": "mmol/L"}]}
        self.assertEqual(self.client.post(path, json=body, headers=self.csrf_headers()).status_code, 403)
        self.login("radiologist")
        self.assertEqual(self.client.post(path, json=body, headers=self.csrf_headers()).status_code, 403)
        self.login("imaging")
        self.assertEqual(self.client.post(path, json=body, headers=self.csrf_headers()).status_code, 403)
        self.login("technician")
        self.assertEqual(self.client.post(path, json=body).status_code, 403)
        response = self.client.post(path, json=body, headers=self.csrf_headers())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["version"], 2)
        self.assertEqual(self.summary().json()["laboratory"]["reports"][0]["observations"][0]["value_numeric"], 5.1)

    def test_lab_role_can_record_multiple_named_observations(self):
        self.send("order.oml.hl7")
        self.send("result.nominal.oru.hl7")
        self.login("technician")
        order_id = self.summary().json()["laboratory"]["reports"][0]["lab_order_id"]
        path = f"/api/v1/lab-orders/{order_id}/reports"
        body = {"observations": [
            {"code": "CRP", "value_numeric": 5.1, "unit": "mg/L"},
            {"code": "GLU", "value_numeric": 4.6, "unit": "mmol/L"},
            {"code": "HB", "display": "Hémoglobine", "value_numeric": 13.8, "unit": "g/dL"},
            {"code": "WBC", "display": "Leucocytes", "value_numeric": 7.2, "unit": "10^9/L"},
        ]}
        response = self.client.post(path, json=body, headers=self.csrf_headers())
        self.assertEqual(response.status_code, 201)
        observations = self.summary().json()["laboratory"]["reports"][0]["observations"]
        self.assertEqual({item["code"]: item["value_numeric"] for item in observations},
                         {"CRP": 5.1, "GLU": 4.6, "HB": 13.8, "WBC": 7.2})
        self.assertEqual(next(item["display"] for item in observations if item["code"] == "HB"), "Hémoglobine")
        body["observations"].append({"code": "HB", "display": "Duplicate", "value_numeric": 1, "unit": "g/dL"})
        self.assertEqual(self.client.post(path, json=body, headers=self.csrf_headers()).status_code, 422)

    def test_imaging_role_can_upload_only_matching_synthetic_dicom(self):
        self.send("order.oml.hl7")
        self.send("result.nominal.oru.hl7")
        with tempfile.TemporaryDirectory() as directory:
            payload = generate(Path(directory) / "demo.dcm").read_bytes()
        path = f"/api/v1/encounters/{ENCOUNTER_ID}/imaging-studies"
        headers = {"Content-Type": "application/dicom"}
        self.login("doctor")
        self.assertEqual(self.client.post(path, content=payload,
                                          headers={**headers, **self.csrf_headers()}).status_code, 403)
        self.login("technician")
        self.assertEqual(self.client.post(path, content=payload,
                                          headers={**headers, **self.csrf_headers()}).status_code, 403)
        self.login("imaging")
        self.assertEqual(self.client.post(path, content=b"bad",
                                          headers={**headers, **self.csrf_headers()}).status_code, 422)
        response = self.client.post(path, content=payload, headers={**headers, **self.csrf_headers()})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["availability_status"], "available")


if __name__ == "__main__":
    unittest.main()

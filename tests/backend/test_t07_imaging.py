"""T07 matching and availability with synthetic RIS rows and a fake PACS."""

import io
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.error import HTTPError
from uuid import uuid4

from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.cli import seed_demo, seed_radiology_demo  # noqa: E402
from app.db.models import AuditEvent, Base, ImagingStudy, RadiologyExam, RadiologyOrder  # noqa: E402
from app.integrations.orthanc.client import OrthancClient, OrthancStudy, OrthancUnavailable  # noqa: E402
from app.modules.imaging.service import ImagingError, get_availability, match_study  # noqa: E402


PATIENT_ID = "10000000-0000-4000-8000-000000000001"
EXAM_ID = "60000000-0000-4000-8000-000000000001"
UID = "2.25.10101"
ORTHANC_ID = "aaaaaaaa-bbbbbbbb-cccccccc-dddddddd-eeeeeeee"
SERIES_ID = "11111111-22222222-33333333-44444444-55555555"
INSTANCE_ID = "66666666-77777777-88888888-99999999-aaaaaaaa"


def remote(**changes):
    values = dict(orthanc_id=ORTHANC_ID, study_instance_uid=UID, patient_id="DEMO-P001",
                  issuer_of_patient_id="DEMO", accession_number="DEMO-ACC001",
                  modality="CT", series_count=1, instance_count=1)
    values.update(changes)
    return OrthancStudy(**values)


class FakeOrthanc:
    def __init__(self, study=None):
        self.study = study or remote()
        self.error = None

    def find_study(self, uid, timeout_ms):
        if self.error:
            raise self.error
        return self.study

    def get_study(self, orthanc_id, timeout_ms):
        if self.error:
            raise self.error
        return self.study


class ImagingTests(unittest.TestCase):
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
        seed_radiology_demo(self.factory)
        self.client = FakeOrthanc()

    def tearDown(self):
        self.engine.dispose()

    def match(self, **changes):
        values = dict(patient_id=PATIENT_ID, accession_number="DEMO-ACC001",
                      study_instance_uid=UID, modality="CT", timeout_ms=500)
        values.update(changes)
        return match_study(self.factory, self.client, **values)

    def test_match_and_exact_replay(self):
        first = self.match()
        second = self.match()
        self.assertEqual(first["imaging_study_id"], second["imaging_study_id"])
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(first["availability_status"], "available")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ImagingStudy)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent)
                                       .where(AuditEvent.action == "imaging.match")), 2)

    def test_bad_patient_unknown_accession_and_modality_are_rejected(self):
        for study, arguments, code in (
            (remote(patient_id="DEMO-P999"), {}, "PATIENT_MISMATCH"),
            (remote(accession_number="UNKNOWN"), {}, "ACCESSION_MISMATCH"),
            (remote(), {"accession_number": "UNKNOWN"}, "UNKNOWN_ACCESSION"),
            (remote(modality="MR"), {}, "MODALITY_MISMATCH"),
        ):
            self.client.study = study
            with self.assertRaisesRegex(ImagingError, code):
                self.match(**arguments)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ImagingStudy)), 0)

    def test_unknown_accession_is_rejected_even_when_pacs_is_down(self):
        self.client.error = OrthancUnavailable("ORTHANC_UNAVAILABLE")
        with self.assertRaisesRegex(ImagingError, "UNKNOWN_ACCESSION"):
            self.match(accession_number="UNKNOWN")

    def test_missing_study_and_conflicting_domain_are_rejected(self):
        self.client.study = None
        with self.assertRaisesRegex(ImagingError, "STUDY_NOT_FOUND"):
            self.match()
        self.client.study = remote(issuer_of_patient_id="OTHER")
        with self.assertRaisesRegex(ImagingError, "IDENTIFIER_DOMAIN_MISMATCH"):
            self.match()
        self.client.study = remote(issuer_of_patient_id=None)
        self.assertEqual(self.match()["availability_status"], "available")

    def test_exam_without_study_is_incomplete_and_audited(self):
        result = get_availability(self.factory, self.client, exam_id=EXAM_ID)
        self.assertEqual(result["availability_status"], "incomplete")
        self.assertEqual(result["studies"], [])
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent)
                                       .where(AuditEvent.action == "imaging.availability")), 1)

    def test_uid_conflict_cannot_relink_to_another_exam(self):
        self.match()
        other_order = str(uuid4())
        other_exam = str(uuid4())
        with self.factory.begin() as db:
            db.add(RadiologyOrder(id=other_order, encounter_id="20000000-0000-4000-8000-000000000001",
                                  accession_number="DEMO-ACC002", requested_procedure="CT synthetic",
                                  priority="routine", status="ordered"))
            db.flush()
            db.add(RadiologyExam(id=other_exam, order_id=other_order, modality="CT", status="scheduled"))
        self.client.study = remote(accession_number="DEMO-ACC002")
        with self.assertRaisesRegex(ImagingError, "STUDY_CONFLICT"):
            self.match(accession_number="DEMO-ACC002")

    def test_partial_then_complete_then_pacs_outage_preserves_reference(self):
        self.client.study = remote(instance_count=0)
        first = self.match()
        self.assertEqual(first["availability_status"], "incomplete")
        self.client.study = remote()
        refreshed = get_availability(self.factory, self.client, exam_id=EXAM_ID)
        self.assertEqual(refreshed["availability_status"], "available")
        good_sync = refreshed["studies"][0]["last_synced_at"]
        self.client.error = OrthancUnavailable("ORTHANC_UNAVAILABLE")
        degraded = get_availability(self.factory, self.client, exam_id=EXAM_ID)
        self.assertEqual(degraded["availability_status"], "unavailable")
        self.assertEqual(degraded["warning_code"], "ORTHANC_UNAVAILABLE")
        self.assertEqual(degraded["studies"][0]["id"], first["imaging_study_id"])
        self.assertEqual(degraded["studies"][0]["last_synced_at"], good_sync)
        self.assertTrue(degraded["checked_at"].endswith("Z"))

    def test_remote_mismatch_on_refresh_is_unavailable_without_relink(self):
        first = self.match()
        self.client.study = remote(patient_id="DEMO-P999")
        refreshed = get_availability(self.factory, self.client, exam_id=EXAM_ID)
        self.assertEqual(refreshed["availability_status"], "unavailable")
        self.assertEqual(refreshed["warning_code"], "PATIENT_MISMATCH")
        self.assertEqual(refreshed["studies"][0]["id"], first["imaging_study_id"])

    def test_audit_failure_rolls_back_match(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_event "
                                    "BEGIN SELECT RAISE(FAIL, 'audit down'); END"))
        with self.assertRaises(Exception):
            self.match()
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ImagingStudy)), 0)


class OrthancClientTests(unittest.TestCase):
    def test_query_metadata_counts_and_private_authentication(self):
        calls = []

        def opener(request, timeout):
            calls.append((request, timeout))
            path = request.full_url.removeprefix("http://127.0.0.1:8042")
            if path == "/tools/find":
                result = [ORTHANC_ID]
            elif path == f"/studies/{ORTHANC_ID}":
                result = {"ID": ORTHANC_ID, "MainDicomTags": {"StudyInstanceUID": UID,
                          "AccessionNumber": "DEMO-ACC001"},
                          "PatientMainDicomTags": {"PatientID": "DEMO-P001", "IssuerOfPatientID": "DEMO"},
                          "Series": [SERIES_ID]}
            elif path == f"/series/{SERIES_ID}":
                result = {"ID": SERIES_ID, "MainDicomTags": {"Modality": "CT"},
                          "Instances": [INSTANCE_ID]}
            else:
                self.fail(f"Unexpected Orthanc path: {path}")
            return io.BytesIO(json.dumps(result).encode("utf-8"))

        client = OrthancClient("http://127.0.0.1:8042", "demo", "private-password", opener=opener)
        study = client.find_study(UID, 500)
        self.assertEqual((study.patient_id, study.accession_number, study.modality,
                          study.series_count, study.instance_count),
                         ("DEMO-P001", "DEMO-ACC001", "CT", 1, 1))
        self.assertEqual(len(calls), 3)
        self.assertEqual(json.loads(calls[0][0].data)["Query"], {"StudyInstanceUID": UID})
        self.assertTrue(all(0 < timeout <= 0.5 for _, timeout in calls))
        self.assertTrue(all(request.get_header("Authorization").startswith("Basic ") for request, _ in calls))
        self.assertNotIn("private-password", str(study))

    def test_timeout_and_transport_error_are_normalized(self):
        def offline(request, timeout):
            raise URLError("connection refused")

        client = OrthancClient("http://127.0.0.1:8042", "demo", "secret", opener=offline)
        with self.assertRaisesRegex(OrthancUnavailable, "ORTHANC_UNAVAILABLE"):
            client.find_study(UID, 500)

        def timed_out(request, timeout):
            raise TimeoutError("timed out")

        client = OrthancClient("http://127.0.0.1:8042", "demo", "secret", opener=timed_out)
        with self.assertRaisesRegex(OrthancUnavailable, "ORTHANC_UNAVAILABLE"):
            client.find_study(UID, 500)

    def test_forbidden_orthanc_credentials_are_normalized(self):
        def forbidden(request, timeout):
            raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

        client = OrthancClient("http://127.0.0.1:8042", "demo", "bad-secret", opener=forbidden)
        with self.assertRaisesRegex(OrthancUnavailable, "ORTHANC_AUTH_FAILED"):
            client.find_study(UID, 500)


if __name__ == "__main__":
    unittest.main()

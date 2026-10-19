"""Comportements T03 vérifiés sur une base SQL éphémère."""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.cli import seed_demo  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.db.models import AppSession, AppUser, AuditEvent, Base, Patient, Role, UserEncounterAccess, UserRole  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.auth.service import hash_password  # noqa: E402


ORIGIN = "http://127.0.0.1:8000"
PATIENT_ID = "10000000-0000-4000-8000-000000000001"
ENCOUNTER_ID = "20000000-0000-4000-8000-000000000001"


class T03ApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(text("INSERT INTO alembic_version VALUES ('0001_t03')"))
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        seed_demo(self.factory)
        with self.factory.begin() as db:
            for role in ("physician", "radiologist", "lab_technician", "admin"):
                db.add(Role(name=role))
            self.physician_id = str(uuid4())
            self.admin_id = str(uuid4())
            db.add_all([
                AppUser(id=self.physician_id, username="doctor", password_hash=hash_password("correct-password"),
                        is_active=True, failed_attempts=0),
                AppUser(id=self.admin_id, username="admin", password_hash=hash_password("correct-password"),
                        is_active=True, failed_attempts=0),
            ])
            db.add_all([UserRole(user_id=self.physician_id, role_name="physician"),
                        UserRole(user_id=self.admin_id, role_name="admin"),
                        UserEncounterAccess(user_id=self.physician_id, encounter_id=ENCOUNTER_ID)])
        self.client = TestClient(create_app(Settings("sqlite+pysqlite:///:memory:", ORIGIN, False), self.factory))

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def login(self, username="doctor", password="correct-password"):
        return self.client.post("/api/v1/auth/login", json={"username": username, "password": password},
                                headers={"Origin": ORIGIN})

    def test_readiness_lookup_encounters_and_audit(self):
        self.assertEqual(self.client.get("/health/ready").status_code, 200)
        self.assertEqual(self.login().status_code, 200)
        result = self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["patients"][0]["id"], PATIENT_ID)
        encounters = self.client.get(f"/api/v1/patients/{PATIENT_ID}/encounters")
        self.assertEqual(encounters.status_code, 200)
        self.assertEqual(encounters.json()["encounters"][0]["id"], ENCOUNTER_ID)
        with self.factory() as db:
            actions = list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.occurred_at)))
        self.assertIn("patient.search", actions)
        self.assertIn("encounter.list", actions)

    def test_seed_is_idempotent_and_readiness_requires_audit_table(self):
        seed_demo(self.factory)
        with self.factory() as db:
            self.assertEqual(db.execute(text("SELECT count(*) FROM patient")).scalar_one(), 1)
            self.assertEqual(db.execute(text("SELECT count(*) FROM encounter")).scalar_one(), 1)
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE audit_event"))
        self.assertEqual(self.client.get("/health/ready").status_code, 503)

    def test_seed_rejects_existing_identity_conflict(self):
        with self.factory.begin() as db:
            db.get(Patient, PATIENT_ID).is_synthetic = False
        with self.assertRaisesRegex(ValueError, "conflicts"):
            seed_demo(self.factory)

    def test_existing_resource_outside_context_is_denied_and_audited(self):
        self.assertEqual(self.login("admin").status_code, 200)
        result = self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(set(result.json()), {"code", "message", "correlation_id"})
        self.assertNotIn("DEMO-P001", result.text)
        with self.factory() as db:
            audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "patient.search"))
            self.assertEqual(audit.outcome, "denied")
            self.assertEqual(audit.resource_id, PATIENT_ID)

    def test_role_without_encounter_grant_is_denied(self):
        self.login()
        with self.factory.begin() as db:
            db.delete(db.get(UserEncounterAccess, (self.physician_id, ENCOUNTER_ID)))
        result = self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        self.assertEqual(result.status_code, 403)

    def test_unknown_patient_is_404_and_identifier_is_exact(self):
        self.login()
        for domain, identifier in (("DEMO", "DEMO-P00"), ("OTHER", "DEMO-P001")):
            result = self.client.get("/api/v1/patients", params={"identifier_domain": domain, "identifier": identifier})
            self.assertEqual(result.status_code, 404)

    def test_unauthenticated_and_expired_session(self):
        result = self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        self.assertEqual(result.status_code, 401)
        self.login()
        with self.factory.begin() as db:
            session = db.scalar(select(AppSession).order_by(AppSession.created_at.desc()))
            session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        result = self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        self.assertEqual(result.status_code, 401)
        self.login()
        with self.factory.begin() as db:
            session = db.scalar(select(AppSession).order_by(AppSession.created_at.desc()))
            session.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        result = self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        self.assertEqual(result.status_code, 401)

    def test_login_lockout_and_csrf_logout(self):
        for _ in range(5):
            self.assertEqual(self.login(password="incorrect").status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        with self.factory.begin() as db:
            user = db.scalar(select(AppUser).where(AppUser.username == "doctor"))
            user.locked_until = None
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 403)
        csrf = self.client.cookies.get("csrf_token")
        result = self.client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"}).status_code, 401)

    def test_failed_audit_prevents_clinical_read(self):
        self.login()
        with self.engine.begin() as conn:
            conn.execute(text("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_event BEGIN SELECT RAISE(FAIL, 'audit down'); END"))
        self.assertEqual(self.client.get("/health/ready").status_code, 503)
        result = self.client.get("/api/v1/patients", params={"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("DEMO-P001", result.text)


if __name__ == "__main__":
    unittest.main()

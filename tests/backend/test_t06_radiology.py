"""T06 RIS workflow and report validation on an ephemeral relational database."""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from app.cli import complete_demo_radiology, seed_demo, seed_radiology_demo  # noqa: E402
from app.db.models import (  # noqa: E402
    AppUser, AuditEvent, Base, RadiologyExam, RadiologyOrder, RadiologyReport, Role,
    UserEncounterAccess, UserRole,
)
from app.modules.radiology.service import (  # noqa: E402
    RadiologyError, create_order, get_encounter_exams, mark_performed,
    save_report_draft, validate_report,
)


ENCOUNTER = "20000000-0000-4000-8000-000000000001"
PERFORMED = datetime(2026, 1, 15, 9, 40, tzinfo=timezone.utc)
VALIDATED = datetime(2026, 1, 15, 9, 55, tzinfo=timezone.utc)


class RadiologyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        seed_demo(self.factory)
        with self.factory.begin() as db:
            db.add_all(Role(name=name) for name in ("physician", "radiologist", "admin"))
            db.flush()
            for user_id, role, access in (
                ("doctor", "physician", True), ("radiologist", "radiologist", True),
                ("outsider", "radiologist", False), ("admin", "admin", True),
            ):
                db.add(AppUser(id=user_id, username=user_id, password_hash="test-only",
                               is_active=True, failed_attempts=0))
                db.flush()
                db.add(UserRole(user_id=user_id, role_name=role))
                if access:
                    db.add(UserEncounterAccess(user_id=user_id, encounter_id=ENCOUNTER))

    def tearDown(self):
        self.engine.dispose()

    def order(self, **changes):
        values = dict(actor_user_id="radiologist", encounter_id=ENCOUNTER,
                      accession_number="RIS-001", requested_procedure="CT synthétique",
                      modality="CT")
        values.update(changes)
        return create_order(self.factory, **values)

    def test_nominal_workflow_and_projection(self):
        ids = self.order()
        mark_performed(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                       performed_at=PERFORMED)
        report_id = save_report_draft(self.factory, actor_user_id="radiologist",
                                      exam_id=ids["exam_id"], content="  Compte rendu fictif.  ")
        self.assertEqual(report_id, save_report_draft(self.factory, actor_user_id="radiologist",
                         exam_id=ids["exam_id"], content="Version finale fictive."))
        self.assertEqual(validate_report(self.factory, actor_user_id="radiologist",
                         exam_id=ids["exam_id"], validated_at=VALIDATED), report_id)
        with self.factory() as db:
            result = get_encounter_exams(db, ENCOUNTER)["exams"][0]
            self.assertEqual(result["order_id"], ids["order_id"])
            self.assertEqual(result["status"], "performed")
            self.assertEqual(result["performed_at"], "2026-01-15T09:40:00Z")
            self.assertEqual(result["report"], {"id": report_id, "status": "final",
                             "content": "Version finale fictive.", "validated_at": "2026-01-15T09:55:00Z"})
            self.assertEqual(db.get(RadiologyOrder, ids["order_id"]).status, "completed")
            self.assertEqual(db.scalar(select(func.count()).select_from(RadiologyReport)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(AuditEvent)
                                       .where(AuditEvent.resource_type == "radiology_report")), 3)

    def test_invalid_transitions_and_final_report_is_immutable(self):
        ids = self.order()
        with self.assertRaisesRegex(RadiologyError, "INVALID_TRANSITION"):
            save_report_draft(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"], content="draft")
        with self.assertRaisesRegex(RadiologyError, "INVALID_TRANSITION"):
            validate_report(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                            validated_at=VALIDATED)
        mark_performed(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"], performed_at=PERFORMED)
        with self.assertRaisesRegex(RadiologyError, "INVALID_TRANSITION"):
            mark_performed(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"], performed_at=PERFORMED)
        save_report_draft(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"], content="draft")
        validate_report(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"], validated_at=VALIDATED)
        for operation in (
            lambda: save_report_draft(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                                      content="changed"),
            lambda: validate_report(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                                    validated_at=VALIDATED),
        ):
            with self.assertRaisesRegex(RadiologyError, "INVALID_TRANSITION"):
                operation()

    def test_role_and_encounter_access_are_required(self):
        for actor in ("doctor", "outsider", "admin"):
            with self.assertRaisesRegex(RadiologyError, "ACCESS_DENIED"):
                self.order(actor_user_id=actor)
        ids = self.order()
        for actor in ("doctor", "outsider", "admin"):
            with self.assertRaisesRegex(RadiologyError, "ACCESS_DENIED"):
                mark_performed(self.factory, actor_user_id=actor, exam_id=ids["exam_id"],
                               performed_at=PERFORMED)
        with self.factory() as db:
            self.assertEqual(db.get(RadiologyExam, ids["exam_id"]).status, "scheduled")
        with self.factory.begin() as db:
            db.get(AppUser, "radiologist").is_active = False
        with self.assertRaisesRegex(RadiologyError, "ACCESS_DENIED"):
            mark_performed(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                           performed_at=PERFORMED)

    def test_accession_and_dates_must_be_consistent(self):
        ids = self.order()
        with self.assertRaisesRegex(RadiologyError, "ACCESSION_CONFLICT"):
            self.order()
        with self.assertRaisesRegex(RadiologyError, "INVALID_TIME"):
            mark_performed(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                           performed_at=datetime(2026, 1, 15, 8, 59, tzinfo=timezone.utc))
        with self.assertRaisesRegex(RadiologyError, "INVALID_TIME"):
            mark_performed(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                           performed_at=datetime(2026, 1, 15, 9, 40))
        mark_performed(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"], performed_at=PERFORMED)
        save_report_draft(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"], content="draft")
        with self.assertRaisesRegex(RadiologyError, "INVALID_TIME"):
            validate_report(self.factory, actor_user_id="radiologist", exam_id=ids["exam_id"],
                            validated_at=datetime(2026, 1, 15, 9, 39, tzinfo=timezone.utc))
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(RadiologyOrder)), 1)
            self.assertEqual(db.scalar(select(RadiologyReport.status)), "draft")

    def test_audit_failure_rolls_back_clinical_change(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_event "
                                    "BEGIN SELECT RAISE(FAIL, 'audit down'); END"))
        with self.assertRaises(Exception):
            self.order()
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(RadiologyOrder)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(RadiologyExam)), 0)

    def test_demo_completion_uses_workflow_and_can_be_replayed(self):
        seed_radiology_demo(self.factory)
        complete_demo_radiology(self.factory, "radiologist")
        complete_demo_radiology(self.factory, "radiologist")
        with self.factory() as db:
            report = db.scalar(select(RadiologyReport))
            self.assertEqual(report.status, "final")
            self.assertEqual(db.scalar(select(func.count()).select_from(RadiologyReport)), 1)


if __name__ == "__main__":
    unittest.main()

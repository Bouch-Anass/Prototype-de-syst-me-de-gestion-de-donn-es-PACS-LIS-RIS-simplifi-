"""Initialisation locale sans mot de passe ni donnée réelle dans Git."""

import argparse
import getpass
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import AppUser, Encounter, Patient, RadiologyExam, RadiologyOrder, RadiologyReport, UserEncounterAccess, UserRole
from app.db.session import make_session_factory
from app.integrations.orthanc.client import OrthancClient
from app.modules.auth.service import hash_password
from app.modules.imaging.service import get_availability, match_study
from app.modules.radiology.service import mark_performed, save_report_draft, validate_report


ROOT = Path(__file__).resolve().parents[3]
ROLES = ("physician", "radiologist", "lab_technician", "imaging_technician", "admin")
DEMO_ROLES = {"demo-doctor": "physician", "demo-lab": "lab_technician",
              "demo-imaging": "imaging_technician", "demo-radiologist": "radiologist"}


def seed_demo_accounts(factory) -> None:
    """Create local fictional users once; keep cleartext passwords outside Git."""
    secret_path = Path("/run/secrets/demo_accounts")
    if not secret_path.exists():
        secret_path = ROOT / "infra/.secrets/demo_accounts.json"
    credentials = json.loads(secret_path.read_text(encoding="utf-8"))
    if set(credentials) != set(DEMO_ROLES) or any(len(value) < 12 for value in credentials.values()):
        raise ValueError("Invalid local demo account secret")
    encounter_id = "20000000-0000-4000-8000-000000000001"
    with factory.begin() as db:
        if db.get(Encounter, encounter_id) is None:
            raise ValueError("Seed the synthetic encounter first")
        for username, role in DEMO_ROLES.items():
            user = db.scalar(select(AppUser).where(AppUser.username == username))
            if user is None:
                user = AppUser(id=str(uuid4()), username=username,
                               password_hash=hash_password(credentials[username]),
                               is_active=True, failed_attempts=0)
                db.add(user)
                db.flush()
                db.add(UserRole(user_id=user.id, role_name=role))
            else:
                roles = set(db.scalars(select(UserRole.role_name).where(UserRole.user_id == user.id)))
                if roles != {role}:
                    raise ValueError(f"Existing demo account has unexpected role: {username}")
            if db.get(UserEncounterAccess, (user.id, encounter_id)) is None:
                db.add(UserEncounterAccess(user_id=user.id, encounter_id=encounter_id))
    print("Four fictional accounts ready. Passwords are in infra/.secrets/demo_accounts.json on the host.")


def seed_demo(factory) -> None:
    manifest = json.loads((ROOT / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "contracts/examples/summary.nominal.json").read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True or summary["patient"].get("is_synthetic") is not True:
        raise ValueError("Only synthetic fixtures may be seeded")
    with factory.begin() as db:
        patient_id = manifest["ids"]["patient"]
        encounter_id = manifest["ids"]["encounter"]
        patient = db.get(Patient, patient_id)
        if patient is None:
            db.add(Patient(id=patient_id, external_id=manifest["identity"]["patient_external_id"],
                           identifier_domain=manifest["identity"]["identifier_domain"],
                           display_name=summary["patient"]["display_name"], is_synthetic=True))
        elif (not patient.is_synthetic or patient.external_id != manifest["identity"]["patient_external_id"]
              or patient.identifier_domain != manifest["identity"]["identifier_domain"]):
            raise ValueError("Existing patient conflicts with synthetic manifest")
        encounter = db.get(Encounter, encounter_id)
        if encounter is None:
            db.add(Encounter(id=encounter_id, patient_id=patient_id,
                             external_id=manifest["identity"]["encounter_external_id"],
                             status=summary["encounter"]["status"],
                             started_at=datetime.fromisoformat(summary["encounter"]["started_at"].replace("Z", "+00:00"))))
        elif encounter.patient_id != patient_id or encounter.external_id != manifest["identity"]["encounter_external_id"]:
            raise ValueError("Existing encounter conflicts with synthetic manifest")
    print("Synthetic patient and encounter ready.")


def create_user(factory, username: str, role: str) -> None:
    password = getpass.getpass("New password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12 or password != confirmation:
        raise ValueError("Password confirmation failed or password is too short")
    with factory.begin() as db:
        if db.scalar(select(AppUser).where(AppUser.username == username)):
            raise ValueError("Username already exists")
        user = AppUser(id=str(uuid4()), username=username, password_hash=hash_password(password),
                       is_active=True, failed_attempts=0)
        db.add(user)
        db.add(UserRole(user_id=user.id, role_name=role))
    print("User created.")


def grant_encounter(factory, username: str, encounter_id: str) -> None:
    with factory.begin() as db:
        user = db.scalar(select(AppUser).where(AppUser.username == username))
        encounter = db.get(Encounter, encounter_id)
        if user is None or encounter is None:
            raise ValueError("User or encounter not found")
        if db.get(UserEncounterAccess, (user.id, encounter.id)) is None:
            db.add(UserEncounterAccess(user_id=user.id, encounter_id=encounter.id))
    print("Encounter access granted.")


def seed_radiology_demo(factory) -> None:
    manifest = json.loads((ROOT / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True:
        raise ValueError("Only synthetic fixtures may be seeded")
    with factory.begin() as db:
        if db.get(Encounter, manifest["ids"]["encounter"]) is None:
            raise ValueError("Seed the synthetic patient and encounter first")
        order_id = manifest["ids"]["radiology_order"]
        order = db.get(RadiologyOrder, order_id)
        if order is None:
            db.add(RadiologyOrder(id=order_id, encounter_id=manifest["ids"]["encounter"],
                                  accession_number=manifest["imaging"]["accession_number"],
                                  requested_procedure="CT synthétique DEMO-001",
                                  priority="routine", status="ordered"))
            db.flush()
        elif (order.encounter_id != manifest["ids"]["encounter"]
              or order.accession_number != manifest["imaging"]["accession_number"]):
            raise ValueError("Existing radiology order conflicts with synthetic manifest")
        exam_id = manifest["ids"]["radiology_exam"]
        exam = db.get(RadiologyExam, exam_id)
        if exam is None:
            db.add(RadiologyExam(id=exam_id, order_id=order_id,
                                 modality=manifest["imaging"]["modality"], status="scheduled"))
        elif exam.order_id != order_id or exam.modality != manifest["imaging"]["modality"]:
            raise ValueError("Existing radiology exam conflicts with synthetic manifest")
    print("Synthetic radiology order and exam ready.")


def complete_demo_radiology(factory, username: str) -> None:
    """Finish the seeded RIS exam through T06 using an authorized radiologist."""
    manifest = json.loads((ROOT / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
    sample = json.loads((ROOT / "contracts/examples/summary.nominal.json").read_text(encoding="utf-8"))
    exam_id = manifest["ids"]["radiology_exam"]
    fixture = sample["radiology"]["exams"][0]
    with factory() as db:
        actor = db.scalar(select(AppUser).where(AppUser.username == username))
        exam = db.get(RadiologyExam, exam_id)
        if actor is None or exam is None:
            raise ValueError("Radiologist or synthetic exam not found")
        actor_id = actor.id
        exam_status = exam.status
    if exam_status == "scheduled":
        mark_performed(factory, actor_user_id=actor_id, exam_id=exam_id,
                       performed_at=datetime.fromisoformat(fixture["performed_at"].replace("Z", "+00:00")))
    with factory() as db:
        report = db.scalar(select(RadiologyReport).where(RadiologyReport.exam_id == exam_id))
        report_status = report.status if report else None
    if report_status is None:
        save_report_draft(factory, actor_user_id=actor_id, exam_id=exam_id,
                          content=fixture["report"]["content"])
    if report_status != "final":
        validate_report(factory, actor_user_id=actor_id, exam_id=exam_id,
                        validated_at=datetime.fromisoformat(fixture["report"]["validated_at"].replace("Z", "+00:00")))
    print("Synthetic RIS exam and report ready.")


def _orthanc_client() -> tuple[OrthancClient, int]:
    base_url = os.getenv("ORTHANC_BASE_URL", "")
    username = os.getenv("ORTHANC_USERNAME", "")
    password = os.getenv("ORTHANC_PASSWORD", "")
    if not all((base_url, username, password)):
        raise ValueError("ORTHANC_BASE_URL, ORTHANC_USERNAME and ORTHANC_PASSWORD are required")
    timeout_ms = int(os.getenv("ORTHANC_TIMEOUT_MS", "500"))
    return OrthancClient(base_url, username, password), timeout_ms


def main() -> None:
    parser = argparse.ArgumentParser(description="Local synthetic backend setup")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed-demo")
    commands.add_parser("seed-demo-accounts")
    user_cmd = commands.add_parser("create-user")
    user_cmd.add_argument("--username", required=True)
    user_cmd.add_argument("--role", required=True, choices=ROLES)
    grant_cmd = commands.add_parser("grant-encounter")
    grant_cmd.add_argument("--username", required=True)
    grant_cmd.add_argument("--encounter-id", required=True)
    commands.add_parser("seed-radiology-demo")
    ris_cmd = commands.add_parser("complete-radiology-demo")
    ris_cmd.add_argument("--username", required=True)
    commands.add_parser("match-demo-study")
    commands.add_parser("refresh-demo-study")
    args = parser.parse_args()
    factory = make_session_factory(Settings.from_env().database_url)
    if args.command == "seed-demo":
        seed_demo(factory)
    elif args.command == "seed-demo-accounts":
        seed_demo_accounts(factory)
    elif args.command == "create-user":
        create_user(factory, args.username, args.role)
    elif args.command == "grant-encounter":
        grant_encounter(factory, args.username, args.encounter_id)
    elif args.command == "seed-radiology-demo":
        seed_radiology_demo(factory)
    elif args.command == "complete-radiology-demo":
        complete_demo_radiology(factory, args.username)
    else:
        manifest = json.loads((ROOT / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
        client, timeout_ms = _orthanc_client()
        if args.command == "match-demo-study":
            result = match_study(factory, client, patient_id=manifest["ids"]["patient"],
                                 accession_number=manifest["imaging"]["accession_number"],
                                 study_instance_uid=manifest["imaging"]["study_instance_uid"],
                                 modality=manifest["imaging"]["modality"], timeout_ms=timeout_ms)
        else:
            result = get_availability(factory, client, exam_id=manifest["ids"]["radiology_exam"],
                                      timeout_ms=timeout_ms)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

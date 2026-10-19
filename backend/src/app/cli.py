"""Initialisation locale sans mot de passe ni donnée réelle dans Git."""

import argparse
import getpass
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import AppUser, Encounter, Patient, UserEncounterAccess, UserRole
from app.db.session import make_session_factory
from app.modules.auth.service import hash_password


ROOT = Path(__file__).resolve().parents[3]
ROLES = ("physician", "radiologist", "lab_technician", "admin")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Local synthetic backend setup")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed-demo")
    user_cmd = commands.add_parser("create-user")
    user_cmd.add_argument("--username", required=True)
    user_cmd.add_argument("--role", required=True, choices=ROLES)
    grant_cmd = commands.add_parser("grant-encounter")
    grant_cmd.add_argument("--username", required=True)
    grant_cmd.add_argument("--encounter-id", required=True)
    args = parser.parse_args()
    factory = make_session_factory(Settings.from_env().database_url)
    if args.command == "seed-demo":
        seed_demo(factory)
    elif args.command == "create-user":
        create_user(factory, args.username, args.role)
    else:
        grant_encounter(factory, args.username, args.encounter_id)


if __name__ == "__main__":
    main()

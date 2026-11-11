"""Populate the local patient list with fictional records."""

from datetime import datetime, timedelta
from uuid import UUID, uuid5

from sqlalchemy import select

from app.db.models import (
    AppUser, Encounter, LabObservation, LabOrder, LabReport, Patient,
    RadiologyExam, RadiologyOrder, RadiologyReport, UserEncounterAccess, UserRole,
)


def seed_demo_patients(factory, manifest: dict, demo_roles: dict[str, str]) -> int:
    if manifest.get("synthetic") is not True:
        raise ValueError("Only synthetic fixtures may be seeded")
    original_id = manifest["ids"]["encounter"]
    domain = manifest["identity"]["identifier_domain"]
    names = {**demo_roles, **{f"{name}-local": role for name, role in demo_roles.items()}}
    with factory.begin() as db:
        original = db.get(Encounter, original_id, with_for_update=True)
        if original is None or not original.patient.is_synthetic or original.patient_id != manifest["ids"]["patient"]:
            raise ValueError("Seed the original synthetic encounter first")
        accounts = db.execute(select(AppUser.id, AppUser.username, UserRole.role_name)
                              .join(UserRole, UserRole.user_id == AppUser.id)
                              .join(UserEncounterAccess, UserEncounterAccess.user_id == AppUser.id)
                              .where(AppUser.username.in_(names), AppUser.is_active.is_(True),
                                     UserEncounterAccess.encounter_id == original_id))
        users = {user_id for user_id, username, role in accounts if names[username] == role}
        if not users:
            raise ValueError("Create the demo accounts and grant access to DEMO-E001 first")

        base_time = datetime.fromisoformat(manifest["fixture_timestamp"])
        for number in range(2, 26):
            patient_id = str(uuid5(UUID(original.patient_id), f"patient-{number}"))
            encounter_id = str(uuid5(UUID(original_id), f"encounter-{number}"))
            external_id = f"DEMO-P{number:03d}"
            encounter_reference = f"DEMO-E{number:03d}"
            started_at = base_time + timedelta(days=number - 1)
            patient = db.get(Patient, patient_id)
            if patient is None:
                db.add(Patient(id=patient_id, identifier_domain=domain, external_id=external_id,
                               display_name=f"Patient synthétique {number:03d}", is_synthetic=True))
                db.flush()
            elif not patient.is_synthetic or patient.external_id != external_id or patient.identifier_domain != domain:
                raise ValueError(f"Existing patient conflicts with {external_id}")
            encounter = db.get(Encounter, encounter_id)
            if encounter is None:
                db.add(Encounter(id=encounter_id, patient_id=patient_id, external_id=encounter_reference,
                                 status="active", started_at=started_at))
                db.flush()
                _seed_clinical_data(db, manifest, number, encounter_id, started_at)
            elif encounter.patient_id != patient_id or encounter.external_id != encounter_reference:
                raise ValueError(f"Existing encounter conflicts with {encounter_reference}")
            for user_id in users:
                if db.get(UserEncounterAccess, (user_id, encounter_id)) is None:
                    db.add(UserEncounterAccess(user_id=user_id, encounter_id=encounter_id))
    return 24


def _seed_clinical_data(db, manifest, number, encounter_id, started_at):
    def identifier(kind: str) -> str:
        return str(uuid5(UUID(encounter_id), kind))

    order_id, report_id = identifier("lab-order"), identifier("lab-report")
    db.add(LabOrder(id=order_id, encounter_id=encounter_id, source_system=manifest["laboratory"]["source_system"],
                    placer_number=f"DEMO-LIST-LAB{number:03d}", filler_number=f"DEMO-LIST-LIS{number:03d}",
                    panel_code=manifest["hl7"]["panel_code"], ordered_at=started_at, status="ordered"))
    db.flush()
    db.add(LabReport(id=report_id, lab_order_id=order_id, version=1, status="final",
                     reported_at=started_at + timedelta(minutes=30)))
    db.flush()
    values = {"CRP": None if number % 5 == 0 else round(1.1 + number * 0.7, 1),
              "GLU": round(4.1 + (number % 9) * 0.3, 1)}
    for analysis in manifest["laboratory"]["expected_observations"]:
        code = analysis["code"]
        value = values.get(code, analysis["nominal_value_numeric"])
        db.add(LabObservation(id=identifier(f"observation-{code}"), lab_report_id=report_id, code=code,
                              coding_system=analysis["coding_system"], display=analysis["display"],
                              unit=analysis["unit"], value_numeric=value,
                              data_status="missing" if value is None else "available"))

    modality, procedure = (("CT", "Scanner thoracique"), ("MR", "IRM du genou"),
                           ("US", "Échographie abdominale"), ("DX", "Radiographie thoracique"))[number % 4]
    radiology_order_id, exam_id = identifier("radiology-order"), identifier("exam")
    scheduled = number % 4 == 0
    final = not scheduled and number % 3 != 0
    db.add(RadiologyOrder(id=radiology_order_id, encounter_id=encounter_id,
                          accession_number=f"DEMO-LIST-{number:03d}", requested_procedure=procedure,
                          priority="routine", status="completed" if final else "ordered"))
    db.flush()
    db.add(RadiologyExam(id=exam_id, order_id=radiology_order_id, modality=modality,
                         status="scheduled" if scheduled else "performed",
                         performed_at=None if scheduled else started_at + timedelta(minutes=45)))
    if not scheduled:
        db.flush()
        db.add(RadiologyReport(id=identifier("radiology-report"), exam_id=exam_id,
                               content=f"{procedure}. Compte rendu fictif de démonstration.",
                               status="final" if final else "draft",
                               validated_at=started_at + timedelta(hours=1) if final else None))

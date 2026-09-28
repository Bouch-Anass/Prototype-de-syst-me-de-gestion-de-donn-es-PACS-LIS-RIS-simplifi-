"""Invariants ciblés des fixtures DEMO-001, sans prétention de schéma universel."""
from datetime import datetime
import math
from uuid import UUID


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Instant sans fuseau")
    return parsed


def no_private_fields(value):
    forbidden = {"password", "token", "secret", "orthanc_password", "orthanc_study_id", "raw_hl7"}
    if isinstance(value, dict):
        require(not (forbidden & set(value)), "Champ privé exposé")
        for item in value.values():
            no_private_fields(item)
    elif isinstance(value, list):
        for item in value:
            no_private_fields(item)


def validate_summary(summary, fixture):
    require(set(summary) == {"patient", "encounter", "laboratory", "radiology", "imaging", "warnings"},
            "Champs racine incohérents")
    require(fixture["synthetic"] is True, "Manifeste non synthétique")
    for value in fixture["ids"].values():
        UUID(value)
    require(len(set(fixture["ids"].values())) == len(fixture["ids"]), "UUID de fixture dupliqué")
    no_private_fields(summary)
    patient = summary["patient"]
    identity = fixture["identity"]
    ids = fixture["ids"]
    require(patient["is_synthetic"] is True, "Patient non synthétique")
    require(patient["id"] == ids["patient"], "Mauvais patient")
    require(patient["external_id"] == identity["patient_external_id"], "Identifiant externe incohérent")
    require(patient["identifier_domain"] == identity["identifier_domain"], "Domaine incohérent")
    require(identity["dicom_patient_id"] == patient["external_id"], "PatientID DICOM incohérent")
    encounter = summary["encounter"]
    require(encounter["id"] == ids["encounter"], "Mauvaise rencontre")
    require(encounter["external_id"] == identity["encounter_external_id"], "Rencontre externe incohérente")
    timestamp(encounter["started_at"])

    laboratory = summary["laboratory"]
    require(laboratory["status"] in {"available", "partial", "unavailable"}, "État laboratoire invalide")
    require(len(laboratory["reports"]) == 1, "Le scénario attend un rapport courant")
    report = laboratory["reports"][0]
    require(report["id"] == ids["lab_report"] and report["lab_order_id"] == ids["lab_order"],
            "Rapport ou demande biologique incohérent")
    require(type(report["version"]) is int and report["version"] >= 1, "Version invalide")
    require(report["status"] in {"preliminary", "final", "corrected"}, "État rapport invalide")
    timestamp(report["reported_at"])
    expected = {(item["coding_system"], item["code"]): item for item in fixture["laboratory"]["expected_observations"]}
    observations = report["observations"]
    keys = [(item["coding_system"], item["code"]) for item in observations]
    require(len(keys) == len(set(keys)) and set(keys) == set(expected), "Analyses attendues incohérentes")
    missing_codes = []
    for observation in observations:
        key = (observation["coding_system"], observation["code"])
        require(observation["unit"] == expected[key]["unit"], "Unité incohérente")
        state = observation["data_status"]
        require(state in {"available", "missing", "invalid"}, "État observation invalide")
        numeric, textual = observation["value_numeric"], observation["value_text"]
        if state == "available":
            require((numeric is not None) != (textual is not None), "Une seule valeur est requise")
            if numeric is not None:
                require(type(numeric) in (int, float) and math.isfinite(numeric), "Valeur numérique invalide")
            else:
                require(isinstance(textual, str) and bool(textual.strip()), "Valeur textuelle invalide")
        else:
            require(numeric is None and textual is None, "Valeur présente pour donnée manquante ou invalide")
            if state == "missing":
                missing_codes.append(observation["code"])
    all_available = all(item["data_status"] == "available" for item in observations)
    require(laboratory["status"] == ("available" if all_available else "partial"),
            "État global biologique incohérent pour cette fixture")

    exams = summary["radiology"]["exams"]
    require(len(exams) == 1, "Le scénario attend un examen")
    exam = exams[0]
    require(exam["id"] == ids["radiology_exam"] and exam["order_id"] == ids["radiology_order"],
            "Examen ou demande radiologique incohérent")
    require(exam["accession_number"] == fixture["imaging"]["accession_number"], "Accession incohérente")
    require(exam["modality"] == fixture["imaging"]["modality"], "Modalité incohérente")
    performed_at = timestamp(exam["performed_at"])
    require(exam["report"]["id"] == ids["radiology_report"], "Compte rendu incohérent")
    require(timestamp(exam["report"]["validated_at"]) >= performed_at, "Validation antérieure à l'examen")

    imaging = summary["imaging"]
    require(imaging["availability_status"] in {"available", "incomplete", "unavailable"}, "État imagerie invalide")
    require(len(imaging["studies"]) == 1, "Le scénario attend une référence d'étude")
    study = imaging["studies"][0]
    require(study["id"] == ids["imaging_study"], "Mauvaise étude")
    require(study["exam_id"] == exam["id"], "Étude liée au mauvais examen")
    require(study["study_instance_uid"] == fixture["imaging"]["study_instance_uid"], "Study Instance UID incohérent")
    require(study["availability_status"] == imaging["availability_status"], "États d'imagerie contradictoires")
    for key in ("series_count", "instance_count"):
        require(type(study[key]) is int and study[key] >= 0, "Compteur DICOM invalide")
        if study["availability_status"] == "available":
            require(study[key] == fixture["imaging"]["expected_" + key], "Étude incomplète dans cette fixture")
    require(timestamp(study["last_synced_at"]) <= timestamp(imaging["checked_at"]), "Dates d'imagerie incohérentes")
    warnings = summary["warnings"]
    for code in missing_codes:
        require(any(item["code"] == "LAB_RESULT_MISSING" and item["field"] == code for item in warnings),
                "Avertissement de résultat manquant absent")
    if imaging["availability_status"] == "unavailable":
        require(any(item["code"] == "IMAGING_UNAVAILABLE" for item in warnings), "Avertissement imagerie absent")


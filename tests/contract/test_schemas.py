"""Vérifier la structure publique indépendamment des valeurs de DEMO-001."""
import copy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

RACINE = Path(__file__).resolve().parents[2]


def lire_json(chemin):
    return json.loads((RACINE / chemin).read_text(encoding="utf-8"))


class TestsSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {}
        for nom in ("synthese", "erreur"):
            schema = lire_json(f"contracts/schemas/{nom}.schema.json")
            Draft202012Validator.check_schema(schema)
            cls.schemas[nom] = Draft202012Validator(schema, format_checker=FormatChecker())
        cls.nominal = lire_json("contracts/examples/summary.nominal.json")

    def verifier(self, donnees):
        self.schemas["synthese"].validate(donnees)

    def test_tous_les_exemples(self):
        for chemin in (RACINE / "contracts/examples").glob("summary.*.json"):
            with self.subTest(exemple=chemin.name):
                self.verifier(json.loads(chemin.read_text(encoding="utf-8")))

    def test_identifiant_invalide(self):
        donnees = copy.deepcopy(self.nominal)
        donnees["patient"]["id"] = "patient-1"
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_champ_prive_imbrique_refuse(self):
        donnees = copy.deepcopy(self.nominal)
        donnees["radiology"]["exams"][0]["report"]["mot_de_passe"] = "EXEMPLE"
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_etat_examen_inconnu(self):
        donnees = copy.deepcopy(self.nominal)
        donnees["radiology"]["exams"][0]["status"] = "termine_peut_etre"
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_champ_requis_manquant(self):
        donnees = copy.deepcopy(self.nominal)
        del donnees["imaging"]["checked_at"]
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_date_sans_fuseau(self):
        donnees = copy.deepcopy(self.nominal)
        donnees["encounter"]["started_at"] = "2026-01-15T09:00:00"
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_examen_planifie_sans_rapport(self):
        donnees = copy.deepcopy(self.nominal)
        examen = donnees["radiology"]["exams"][0]
        examen.update(status="planned", performed_at=None, report=None)
        donnees["imaging"].update(availability_status="incomplete", studies=[])
        self.verifier(donnees)

    def test_rapport_final_exige_date(self):
        donnees = copy.deepcopy(self.nominal)
        donnees["radiology"]["exams"][0]["report"]["validated_at"] = None
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_valeur_absente_ne_vaut_pas_zero(self):
        donnees = copy.deepcopy(self.nominal)
        observation = donnees["laboratory"]["reports"][0]["observations"][0]
        observation.update(data_status="missing", value_numeric=0)
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_deux_valeurs_refusees(self):
        donnees = copy.deepcopy(self.nominal)
        donnees["laboratory"]["reports"][0]["observations"][0]["value_text"] = "3.2"
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_uid_dicom_invalide(self):
        donnees = copy.deepcopy(self.nominal)
        donnees["imaging"]["studies"][0]["study_instance_uid"] = "2.025.123"
        with self.assertRaises(ValidationError):
            self.verifier(donnees)

    def test_erreur_publique(self):
        erreur = {
            "code": "ACCESS_DENIED", "message": "Accès non autorisé.",
            "correlation_id": "b0000000-0000-4000-8000-000000000001",
        }
        self.schemas["erreur"].validate(erreur)
        erreur["traceback"] = "détail interne"
        with self.assertRaises(ValidationError):
            self.schemas["erreur"].validate(erreur)


if __name__ == "__main__":
    unittest.main()

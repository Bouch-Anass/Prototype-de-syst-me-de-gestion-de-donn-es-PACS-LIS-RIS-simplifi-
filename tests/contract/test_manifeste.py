"""Cohérence des références partagées ; aucun serveur DICOM ou parseur HL7."""
import json
from pathlib import Path
import re
import unittest

RACINE = Path(__file__).resolve().parents[2]


class TestsManifeste(unittest.TestCase):
    def test_metadonnees_dicom_correspondent_au_manifeste(self):
        manifeste = json.loads((RACINE / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
        metadonnees = json.loads((RACINE / "data/fixtures/rapprochement-dicom.json").read_text(encoding="utf-8"))
        attendus = {
            "PatientID": manifeste["identity"]["dicom_patient_id"],
            "IssuerOfPatientID": manifeste["identity"]["identifier_domain"],
            "AccessionNumber": manifeste["imaging"]["accession_number"],
            "StudyInstanceUID": manifeste["imaging"]["study_instance_uid"],
            "Modality": manifeste["imaging"]["modality"],
        }
        for cle, valeur in attendus.items():
            with self.subTest(champ=cle):
                self.assertEqual(metadonnees[cle], valeur)
        self.assertEqual(manifeste["imaging"]["issuer_of_patient_id"], attendus["IssuerOfPatientID"])
        identifiants = [metadonnees[cle] for cle in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID")]
        self.assertEqual(len(set(identifiants)), 3)
        for valeur in identifiants:
            self.assertLessEqual(len(valeur), 64)
            self.assertIsNotNone(re.fullmatch(r"(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))+", valeur))


if __name__ == "__main__":
    unittest.main()

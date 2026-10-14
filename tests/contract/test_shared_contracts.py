"""Cross-domain invariants for the first synthetic journey."""

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_hl7_fixtures import messages  # noqa: E402


class SharedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
        cls.nominal = json.loads((ROOT / "contracts/examples/summary.nominal.json").read_text(encoding="utf-8"))
        cls.missing = json.loads((ROOT / "contracts/examples/summary.missing-crp.json").read_text(encoding="utf-8"))

    def test_dicom_keys_match_patient_order_and_study(self):
        metadata = json.loads((ROOT / "data/dicom/study-metadata.json").read_text(encoding="utf-8"))
        identity = self.manifest["identity"]
        imaging = self.manifest["imaging"]
        self.assertTrue(metadata["synthetic"])
        self.assertEqual(metadata["scenario_id"], self.manifest["scenario_id"])
        self.assertEqual(metadata["patient_id"], identity["dicom_patient_id"])
        self.assertEqual(metadata["identifier_domain"], identity["dicom_identifier_domain"])
        self.assertEqual(metadata["identifier_domain"], identity["identifier_domain"])
        for key in ("accession_number", "study_instance_uid", "modality", "expected_series_count", "expected_instance_count"):
            self.assertEqual(metadata[key], imaging[key])
        self.assertEqual(self.nominal["radiology"]["exams"][0]["accession_number"], metadata["accession_number"])
        self.assertEqual(self.nominal["imaging"]["studies"][0]["study_instance_uid"], metadata["study_instance_uid"])

    def test_nominal_and_missing_results_follow_manifest(self):
        expected = {item["code"]: item for item in self.manifest["laboratory"]["expected_observations"]}
        nominal = {item["code"]: item for item in self.nominal["laboratory"]["reports"][0]["observations"]}
        missing = {item["code"]: item for item in self.missing["laboratory"]["reports"][0]["observations"]}
        self.assertEqual(set(expected), set(nominal))
        for code, item in expected.items():
            self.assertEqual(nominal[code]["value_numeric"], item["nominal_value_numeric"])
            self.assertEqual(nominal[code]["unit"], item["unit"])
        self.assertIsNone(missing["CRP"]["value_numeric"])
        self.assertEqual(missing["CRP"]["data_status"], "missing")
        self.assertEqual(missing["GLU"]["value_numeric"], expected["GLU"]["nominal_value_numeric"])

    def test_hl7_fixtures_are_current_cr_terminated_and_correlated(self):
        generated = messages(self.manifest)
        for filename, expected_bytes in generated.items():
            with self.subTest(filename=filename):
                content = (ROOT / "data/hl7" / filename).read_bytes()
                self.assertEqual(content, expected_bytes, "Regenerate HL7 fixtures from the manifest")
                self.assertTrue(content.endswith(b"\r"))
                self.assertNotIn(b"\n", content)
                lines = content.decode("utf-8").rstrip("\r").split("\r")
                self.assertEqual(lines[0].split("|")[11], self.manifest["hl7"]["version"])
                self.assertEqual(lines[1].split("|")[3].split("^")[0], self.manifest["identity"]["patient_external_id"])
                self.assertEqual(lines[2].split("|")[19].split("^")[0], self.manifest["identity"]["encounter_external_id"])
                if filename.startswith("order"):
                    self.assertEqual([line[:3] for line in lines], ["MSH", "PID", "PV1", "ORC", "OBR"])
                else:
                    self.assertEqual([line[:3] for line in lines[:4]], ["MSH", "PID", "PV1", "OBR"])
                    codes = {line.split("|")[3].split("^")[0] for line in lines[4:]}
                    self.assertEqual(codes, {"GLU"} if "missing-crp" in filename else {"CRP", "GLU"})
                    if "correction" in filename:
                        self.assertEqual(lines[3].split("|")[25], "C")
                        corrected_crp = next(line for line in lines[4:] if line.split("|")[3].startswith("CRP^"))
                        self.assertEqual(float(corrected_crp.split("|")[5]), self.manifest["laboratory"]["expected_observations"][0]["corrected_value_numeric"])
                        self.assertTrue(all(line.split("|")[11] == "C" for line in lines[4:]))


if __name__ == "__main__":
    unittest.main()

import copy
import json
from pathlib import Path
import unittest

from example_checks import validate_summary

ROOT = Path(__file__).resolve().parents[2]


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ExampleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = read_json("data/fixtures/scenario.json")
        cls.nominal = read_json("contracts/examples/summary.nominal.json")
        cls.missing = read_json("contracts/examples/summary.missing-crp.json")
        cls.offline = read_json("contracts/examples/summary.orthanc-unavailable.json")

    def reject(self, data):
        with self.assertRaises(ValueError):
            validate_summary(data, self.fixture)

    def test_three_reference_examples(self):
        for example in (self.nominal, self.missing, self.offline):
            with self.subTest(status=example["laboratory"]["status"], imaging=example["imaging"]["availability_status"]):
                validate_summary(example, self.fixture)

    def test_shared_identity(self):
        self.assertEqual(self.nominal["patient"], self.missing["patient"])
        self.assertEqual(self.nominal["patient"], self.offline["patient"])

    def test_missing_result_is_not_zero(self):
        changed = copy.deepcopy(self.missing)
        changed["laboratory"]["reports"][0]["observations"][0]["value_numeric"] = 0
        self.reject(changed)

    def test_double_value_is_rejected(self):
        changed = copy.deepcopy(self.nominal)
        changed["laboratory"]["reports"][0]["observations"][0]["value_text"] = "3.2"
        self.reject(changed)

    def test_wrong_identity_is_rejected(self):
        changed = copy.deepcopy(self.nominal)
        changed["patient"]["identifier_domain"] = "OTHER"
        self.reject(changed)

    def test_wrong_accession_is_rejected(self):
        changed = copy.deepcopy(self.nominal)
        changed["radiology"]["exams"][0]["accession_number"] = "OTHER"
        self.reject(changed)

    def test_wrong_study_relation_is_rejected(self):
        changed = copy.deepcopy(self.nominal)
        changed["imaging"]["studies"][0]["exam_id"] = self.fixture["ids"]["encounter"]
        self.reject(changed)

    def test_incomplete_fixture_not_available(self):
        changed = copy.deepcopy(self.nominal)
        changed["imaging"]["studies"][0]["instance_count"] = 0
        self.reject(changed)

    def test_private_field_is_rejected(self):
        changed = copy.deepcopy(self.nominal)
        changed["imaging"]["studies"][0]["orthanc_password"] = "TEST_ONLY"
        self.reject(changed)

    def test_timestamp_requires_timezone(self):
        changed = copy.deepcopy(self.nominal)
        changed["imaging"]["checked_at"] = "2026-01-15T10:00:00"
        self.reject(changed)

    def test_missing_warning_is_rejected(self):
        changed = copy.deepcopy(self.missing)
        changed["warnings"] = []
        self.reject(changed)

    def test_offline_preserves_business_data(self):
        self.assertEqual(self.nominal["laboratory"], self.offline["laboratory"])
        self.assertEqual(self.nominal["radiology"], self.offline["radiology"])

    def test_missing_crp_preserves_glucose(self):
        nominal_glucose = self.nominal["laboratory"]["reports"][0]["observations"][1]
        missing_glucose = self.missing["laboratory"]["reports"][0]["observations"][1]
        self.assertEqual(nominal_glucose, missing_glucose)


if __name__ == "__main__":
    unittest.main()


"""Public test image preparation preserves pixels and replaces source metadata."""

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydicom import dcmread
from pydicom.data import get_testdata_file


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("seed_public_dicom", ROOT / "scripts/seed_public_dicom.py")
loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loader)
SAMPLE = json.loads((ROOT / "data/dicom/public-samples.json").read_text())["samples"][0]


class PublicSampleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.sources = Path(self.directory.name) / "sources"
        self.output = Path(self.directory.name) / "output"
        self.sources.mkdir()
        self.source = self.sources / SAMPLE["filename"]
        self.source.write_bytes(Path(get_testdata_file("CT_small.dcm")).read_bytes())
        self.sample = deepcopy(SAMPLE)
        self.source_patch = patch.object(loader, "SOURCES", self.sources)
        self.output_patch = patch.object(loader, "OUTPUT", self.output)
        self.source_patch.start()
        self.output_patch.start()
        self.addCleanup(self.source_patch.stop)
        self.addCleanup(self.output_patch.stop)

    def change_source(self, **changes):
        source = dcmread(self.source)
        for name, value in changes.items():
            setattr(source, name, value)
        source.add_new((0x0011, 0x1010), "LO", "private fixture value")
        source.save_as(self.source, enforce_file_format=True)
        self.sample["sha256"] = sha256(self.source.read_bytes()).hexdigest()

    def test_source_metadata_is_removed_and_pixels_are_unchanged(self):
        self.change_source(PatientName="Source^Identity", InstitutionName="Source institution")
        original = self.source.read_bytes()
        prepared = dcmread(loader.prepare_sample(self.sample))
        self.assertEqual(prepared.PatientID, "DEMO-P001")
        self.assertEqual(str(prepared.PatientName), "Synthetic^Demo001")
        self.assertNotIn("InstitutionName", prepared)
        self.assertFalse(any(element.tag.is_private for element in prepared.iterall()))
        self.assertEqual(prepared.PixelData, dcmread(self.source).PixelData)
        self.assertEqual(prepared.SOPClassUID, dcmread(self.source).SOPClassUID)
        self.assertEqual(self.source.read_bytes(), original)

    def test_preparing_again_preserves_stable_instance_and_study_identifiers(self):
        first = loader.prepare_sample(self.sample).read_bytes()
        second = loader.prepare_sample(self.sample).read_bytes()
        self.assertEqual(first, second)

    def test_changed_source_is_rejected_before_import(self):
        self.sample["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checksum"):
            loader.prepare_sample(self.sample)

    def test_declared_burned_in_annotation_is_rejected(self):
        self.change_source(BurnedInAnnotation="YES")
        with self.assertRaisesRegex(ValueError, "burned-in"):
            loader.prepare_sample(self.sample)


if __name__ == "__main__":
    unittest.main()

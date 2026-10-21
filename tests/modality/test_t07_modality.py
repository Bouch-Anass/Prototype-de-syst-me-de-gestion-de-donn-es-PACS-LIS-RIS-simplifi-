"""Synthetic DICOM generation and loopback C-STORE, without a live Orthanc."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

from pydicom import dcmread
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian
from pynetdicom import AE, evt


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "simulators/modality"))

from generate_and_send import generate, send  # noqa: E402


class ModalityTests(unittest.TestCase):
    def test_generate_and_send_synthetic_study(self):
        manifest = json.loads((ROOT / "data/fixtures/scenario.json").read_text(encoding="utf-8"))
        received = []

        def on_store(event):
            dataset = event.dataset
            received.append((str(dataset.PatientID), str(dataset.AccessionNumber),
                             str(dataset.StudyInstanceUID), str(dataset.Modality)))
            return 0x0000

        with tempfile.TemporaryDirectory() as directory:
            path = generate(Path(directory) / "synthetic.dcm")
            dataset = dcmread(path)
            self.assertEqual(dataset.file_meta.MediaStorageSOPClassUID, CTImageStorage)
            self.assertEqual(dataset.file_meta.TransferSyntaxUID, ExplicitVRLittleEndian)
            self.assertEqual(str(dataset.IssuerOfPatientID), "DEMO")
            self.assertEqual(len(dataset.PixelData), 8)

            ae = AE(ae_title="DEMOPACS")
            ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
            server = ae.start_server(("127.0.0.1", 0), block=False,
                                     evt_handlers=[(evt.EVT_C_STORE, on_store)])
            try:
                send(path, server.server_address[1])
            finally:
                server.shutdown()

        self.assertEqual(received, [
            (manifest["identity"]["dicom_patient_id"], manifest["imaging"]["accession_number"],
             manifest["imaging"]["study_instance_uid"], "CT")])


if __name__ == "__main__":
    unittest.main()

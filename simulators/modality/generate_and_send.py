"""Create one tiny synthetic CT DICOM instance and optionally C-STORE it locally."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import struct

from pydicom import dcmread
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian
from pynetdicom import AE


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data/fixtures/scenario.json"
OUTPUT = ROOT / "data/generated/demo-001-ct.dcm"


def generate(path: Path = OUTPUT) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("synthetic") is not True:
        raise ValueError("Only the synthetic DEMO-001 manifest may be generated")
    identity = manifest["identity"]
    imaging = manifest["imaging"]
    if imaging["modality"] != "CT":
        raise ValueError("This tiny generator supports CT only")
    study_uid = imaging["study_instance_uid"]
    series_uid = f"{study_uid}.1"
    sop_uid = f"{study_uid}.1.1"
    created_at = datetime.fromisoformat(manifest["fixture_timestamp"].replace("Z", "+00:00"))
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = "2.25.10101.999"
    dataset = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    dataset.SOPClassUID = CTImageStorage
    dataset.SOPInstanceUID = sop_uid
    dataset.StudyInstanceUID = study_uid
    dataset.SeriesInstanceUID = series_uid
    dataset.PatientName = "Synthetic^Demo001"
    dataset.PatientID = identity["dicom_patient_id"]
    dataset.IssuerOfPatientID = identity["dicom_identifier_domain"]
    dataset.AccessionNumber = imaging["accession_number"]
    dataset.Modality = "CT"
    dataset.StudyDate = created_at.strftime("%Y%m%d")
    dataset.StudyTime = created_at.strftime("%H%M%S")
    dataset.SeriesDate = dataset.StudyDate
    dataset.SeriesTime = dataset.StudyTime
    dataset.ContentDate = dataset.StudyDate
    dataset.ContentTime = dataset.StudyTime
    dataset.StudyID = "DEMO-001"
    dataset.SeriesNumber = 1
    dataset.InstanceNumber = 1
    dataset.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
    dataset.PatientPosition = "HFS"
    dataset.Rows = 2
    dataset.Columns = 2
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 16
    dataset.BitsStored = 16
    dataset.HighBit = 15
    dataset.PixelRepresentation = 1
    dataset.PixelSpacing = ["1", "1"]
    dataset.SliceThickness = "1"
    dataset.ImagePositionPatient = ["0", "0", "0"]
    dataset.ImageOrientationPatient = ["1", "0", "0", "0", "1", "0"]
    dataset.RescaleIntercept = "0"
    dataset.RescaleSlope = "1"
    dataset.KVP = "120"
    dataset.PixelData = struct.pack("<4h", 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    dcmwrite(path, dataset, enforce_file_format=True)
    saved = dcmread(path)
    for key, value in (("PatientID", identity["dicom_patient_id"]),
                       ("AccessionNumber", imaging["accession_number"]),
                       ("StudyInstanceUID", study_uid), ("Modality", "CT")):
        if str(getattr(saved, key)) != value:
            raise ValueError(f"Generated DICOM does not match synthetic {key}")
    return path


def send(path: Path, port: int) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("DICOM port must be between 1 and 65535")
    ae = AE(ae_title="DEMOMOD")
    ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
    association = ae.associate("127.0.0.1", port, ae_title="DEMOPACS")
    if not association.is_established:
        raise RuntimeError("Could not establish a local DICOM association")
    try:
        status = association.send_c_store(path)
        if status is None or status.Status != 0x0000:
            raise RuntimeError("Orthanc rejected the synthetic C-STORE request")
    finally:
        association.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and optionally send one synthetic CT DICOM instance")
    parser.add_argument("--send", action="store_true", help="C-STORE to local DEMOPACS after generation")
    parser.add_argument("--port", type=int, default=4242, help="local Orthanc DICOM port")
    args = parser.parse_args()
    path = generate()
    print(f"Synthetic DICOM ready: {path.relative_to(ROOT)}")
    if args.send:
        send(path, args.port)
        print("Synthetic C-STORE accepted by local Orthanc.")


if __name__ == "__main__":
    main()

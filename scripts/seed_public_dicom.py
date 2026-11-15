#!/usr/bin/env python3
"""Prepare public DICOM test slices and optionally import them through the API.

Use --import with role credentials as JSON on stdin. Originals, derived DICOM,
review PNGs and manifests stay in ignored local directories.
"""

import argparse
from datetime import datetime, timedelta
from hashlib import sha256
from http.cookiejar import CookieJar
import json
from pathlib import Path
import struct
import sys
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from uuid import NAMESPACE_URL, uuid5
import zlib

from pydicom import dcmread
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.uid import ExplicitVRLittleEndian


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data/local/dicom-sources"
OUTPUT = ROOT / "data/generated/public-dicom"
ENCOUNTER = "20000000-0000-4000-8000-000000000001"
PATIENT = "DEMO-P001"
LIMIT = 8 * 1024 * 1024


def cache_notices():
    notices = {
        "PYDICOM-LICENSE.txt": "https://raw.githubusercontent.com/pydicom/pydicom/v3.0.2/LICENSE",
        "PYDICOM-PROVENANCE.txt": "https://raw.githubusercontent.com/pydicom/pydicom/v3.0.2/src/pydicom/data/test_files/README.txt",
        "PYDICOM-DATA-LICENSE.txt": "https://raw.githubusercontent.com/pydicom/pydicom-data/39a2eb31815eec435dc26c322c27aec5cfcbddb6/LICENSE",
    }
    SOURCES.mkdir(parents=True, exist_ok=True)
    for filename, url in notices.items():
        path = SOURCES / filename
        if not path.exists():
            with urlopen(url, timeout=30) as response:
                content = response.read(64_001)
            if len(content) > 64_000:
                raise ValueError("Upstream notice exceeds the expected size")
            path.write_bytes(content)


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def review_png(dataset, path):
    rows, columns = int(dataset.Rows), int(dataset.Columns)
    if int(dataset.SamplesPerPixel) == 3 and dataset.PhotometricInterpretation == "RGB":
        pixels = dataset.PixelData
        if int(dataset.get("PlanarConfiguration", 0)) != 0:
            raise ValueError("Only interleaved RGB test samples are supported")
        channels, colour = 3, 2
    else:
        form = "<h" if int(dataset.PixelRepresentation) else "<H"
        values = [item[0] for item in struct.iter_unpack(form, dataset.PixelData)]
        low, high = min(values), max(values)
        pixels = bytes(round((value - low) * 255 / max(1, high - low)) for value in values)
        channels, colour = 1, 0
    stride = columns * channels
    if len(pixels) != rows * stride:
        raise ValueError("Unexpected pixel length")
    scanlines = b"".join(b"\0" + pixels[index:index + stride] for index in range(0, len(pixels), stride))
    header = struct.pack(">IIBBBBB", columns, rows, 8, colour, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
                     + png_chunk(b"IDAT", zlib.compress(scanlines)) + png_chunk(b"IEND", b""))


def prepare_sample(sample):
    SOURCES.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_path = SOURCES / sample["filename"]
    if not source_path.exists():
        with urlopen(sample["url"], timeout=30) as response:
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("Public sample exceeds the upload limit")
        source_path.write_bytes(raw)
    if sha256(source_path.read_bytes()).hexdigest() != sample["sha256"]:
        raise ValueError(f"Source checksum mismatch: {sample['filename']}")
    source = dcmread(source_path)
    if (str(source.file_meta.TransferSyntaxUID) != str(ExplicitVRLittleEndian)
            or str(source.Modality) != sample["modality"]
            or source.get("NumberOfFrames") not in (None, 1, "1")
            or source.get("BurnedInAnnotation") == "YES"):
        raise ValueError("Unexpected test image encoding or declared burned-in annotation")
    review_png(source, OUTPUT / f"{sample['accession'].lower()}-review.png")
    path = OUTPUT / f"{sample['accession'].lower()}.dcm"
    uid = sample["study_uid"]
    sop_uid = f"2.25.{uuid5(NAMESPACE_URL, uid + '/instance/1').int}"
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = source.SOPClassUID
    meta.MediaStorageSOPInstanceUID = sop_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = "2.25.10101.999"
    copy = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    copy.SOPClassUID, copy.SOPInstanceUID = source.SOPClassUID, sop_uid
    copy.StudyInstanceUID = uid
    copy.SeriesInstanceUID = f"2.25.{uuid5(NAMESPACE_URL, uid + '/series/1').int}"
    copy.PatientID, copy.IssuerOfPatientID = PATIENT, "DEMO"
    copy.PatientName = f"Synthetic^Demo{sample['variant']:03d}"
    copy.StudyID = f"DEMO-{sample['variant']:03d}"
    copy.AccessionNumber, copy.Modality = sample["accession"], sample["modality"]
    copy.StudyDate, copy.StudyTime = "20260115", "104000"
    copy.SeriesNumber = copy.InstanceNumber = 1
    copy.SeriesDescription = "Public test image, fictional patient, non-diagnostic"
    copy.ImageType = ["DERIVED", "SECONDARY"]
    copy.PatientIdentityRemoved = "YES"
    copy.DeidentificationMethod = "Public test; metadata allowlist; fictional IDs; review pixels"
    for key in ("Rows", "Columns", "SamplesPerPixel", "PhotometricInterpretation", "PlanarConfiguration",
                "BitsAllocated", "BitsStored", "HighBit", "PixelRepresentation", "PixelSpacing",
                "SliceThickness", "ImagePositionPatient", "ImageOrientationPatient", "RescaleIntercept",
                "RescaleSlope", "WindowCenter", "WindowWidth", "PixelPaddingValue", "VOILUTFunction"):
        if key in source:
            copy[key] = source[key]
    copy.PixelData = source.PixelData
    dcmwrite(path, copy, enforce_file_format=True)
    saved = dcmread(path)
    if (saved.PixelData != source.PixelData or saved.PatientID != PATIENT
            or any(element.tag.is_private for element in saved.iterall())):
        raise RuntimeError("Prepared sample failed validation")
    return path


class Client:
    def __init__(self, origin, credential):
        self.origin = origin.rstrip("/")
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))
        self.call("/api/v1/auth/login", "POST", credential)

    def call(self, path, method="GET", body=None):
        headers = {"Origin": self.origin, "Accept": "application/json"}
        if method != "GET":
            csrf = next((cookie.value for cookie in self.cookies if cookie.name == "csrf_token"), None)
            if csrf:
                headers["X-CSRF-Token"] = csrf
        if isinstance(body, bytes):
            headers["Content-Type"] = "application/dicom"
        elif body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body).encode("utf-8")
        request = Request(self.origin + path, data=body, method=method, headers=headers)
        with self.opener.open(request, timeout=30) as response:
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError("Response exceeds the preview limit")
            return raw if response.headers.get_content_type() == "image/png" else json.loads(raw)


def import_samples(samples, paths, origin, credentials):
    radiologist = Client(origin, credentials["radiologist"])
    imaging = Client(origin, credentials["imaging_technician"])
    doctor = Client(origin, credentials["physician"])
    summary_path = f"/api/v1/encounters/{ENCOUNTER}/summary"
    summary = doctor.call(summary_path)
    if summary["patient"]["external_id"] != PATIENT or not summary["patient"]["is_synthetic"]:
        raise ValueError("The target must be the fictional DEMO-P001 record")
    for sample, path in zip(samples, paths):
        exam = next((item for item in summary["radiology"]["exams"] if item["accession_number"] == sample["accession"]), None)
        if exam is None:
            created = radiologist.call("/api/v1/radiology-orders", "POST", {
                "encounter_id": ENCOUNTER, "accession_number": sample["accession"],
                "requested_procedure": sample["procedure"], "modality": sample["modality"],
            })
            performed = datetime.fromisoformat(summary["encounter"]["started_at"].replace("Z", "+00:00")) + timedelta(hours=1)
            radiologist.call(f"/api/v1/radiology-exams/{created['exam_id']}", "PATCH", {
                "status": "performed", "performed_at": performed.isoformat(),
            })
        elif exam["modality"] != sample["modality"]:
            raise ValueError("The existing examination has a different modality")
        imaging.call(f"/api/v1/encounters/{ENCOUNTER}/imaging-studies", "POST", path.read_bytes())
        print(f"Imported {sample['modality']}: {sample['accession']}")
    summary = doctor.call(summary_path)
    for sample in samples:
        study = next(item for item in summary["imaging"]["studies"] if item["study_instance_uid"] == sample["study_uid"])
        preview = doctor.call(f"/api/v1/imaging-studies/{study['id']}/preview")
        if not preview.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("The authenticated image preview is not a PNG")
        (OUTPUT / f"{sample['accession'].lower()}-api-preview.png").write_bytes(preview)
        size = struct.unpack(">II", preview[16:24])
        print(f"Verified {sample['modality']} preview: {size[0]} x {size[1]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import", dest="import_images", action="store_true")
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if args.origin != "http://127.0.0.1:8000":
        raise ValueError("This demonstration loader targets only the local application")
    manifest = json.loads((ROOT / "data/dicom/public-samples.json").read_text(encoding="utf-8"))
    cache_notices()
    samples = manifest["samples"]
    paths = [prepare_sample(sample) for sample in samples]
    (OUTPUT / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(paths)} public test images in data/generated/public-dicom.")
    if args.import_images:
        import_samples(samples, paths, args.origin, json.load(sys.stdin))


if __name__ == "__main__":
    main()

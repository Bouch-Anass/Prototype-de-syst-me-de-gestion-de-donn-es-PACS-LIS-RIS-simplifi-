#!/usr/bin/env python3
"""Make a metadata-minimized CT copy for the fictional DEMO-ACC002 exam.

The source stays untouched. Review the generated PNG for burned-in identifiers
before importing the DICOM; metadata removal cannot sanitize image pixels.
"""

import argparse
from pathlib import Path
import struct
import zlib

from pydicom import dcmread
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/generated/demo-002-nlst-ct.dcm"
PREVIEW = ROOT / "data/generated/demo-002-nlst-review.png"
STUDY_UID = "2.25.10102"
SERIES_UID = "2.25.10102.2"
SOP_UID = "2.25.10102.2.1"


def _png_chunk(name: bytes, payload: bytes) -> bytes:
    content = name + payload
    return struct.pack(">I", len(payload)) + content + struct.pack(">I", zlib.crc32(content))


def _pixel_review(source, path: Path) -> None:
    rows, columns = int(source.Rows), int(source.Columns)
    pixels = source.PixelData
    if len(pixels) != rows * columns * 2:
        raise ValueError("Expected one uncompressed 16-bit CT frame")
    intercept = float(source.get("RescaleIntercept", 0))
    slope = float(source.get("RescaleSlope", 1))
    scanlines = bytearray()
    for row in range(rows):
        scanlines.append(0)
        for (stored,) in struct.iter_unpack("<H", pixels[row * columns * 2:(row + 1) * columns * 2]):
            hu = stored * slope + intercept
            scanlines.append(max(0, min(255, round((hu + 1350) * 255 / 1500))))
    header = struct.pack(">IIBBBBB", columns, rows, 8, 0, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
           + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines)))
           + _png_chunk(b"IEND", b""))
    path.write_bytes(png)


def prepare(source_path: Path, output: Path = OUTPUT, preview: Path = PREVIEW) -> None:
    source = dcmread(source_path)
    if (str(source.SOPClassUID) != str(CTImageStorage)
            or str(source.file_meta.TransferSyntaxUID) != str(ExplicitVRLittleEndian)
            or str(source.Modality) != "CT"
            or int(source.SamplesPerPixel) != 1
            or int(source.BitsAllocated) != 16
            or int(source.PixelRepresentation) != 0
            or source.get("NumberOfFrames") not in (None, 1, "1")):
        raise ValueError("This helper accepts only single-frame, uncompressed 16-bit CT")
    if str(source.get("BurnedInAnnotation", "")).upper() == "YES":
        raise ValueError("Source declares burned-in annotation; manual de-identification required")

    output.parent.mkdir(parents=True, exist_ok=True)
    preview.parent.mkdir(parents=True, exist_ok=True)
    _pixel_review(source, preview)

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = SOP_UID
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = "2.25.10101.999"
    copy = FileDataset(str(output), {}, file_meta=meta, preamble=b"\0" * 128)
    copy.SOPClassUID = CTImageStorage
    copy.SOPInstanceUID = SOP_UID
    copy.StudyInstanceUID = STUDY_UID
    copy.SeriesInstanceUID = SERIES_UID
    copy.PatientName = "Synthetic^Demo002"
    copy.PatientID = "DEMO-P001"
    copy.IssuerOfPatientID = "DEMO"
    copy.AccessionNumber = "DEMO-ACC002"
    copy.StudyID = "DEMO-002"
    copy.Modality = "CT"
    copy.StudyDate = "20260115"
    copy.StudyTime = "104000"
    copy.SeriesDate = copy.StudyDate
    copy.SeriesTime = copy.StudyTime
    copy.ContentDate = copy.StudyDate
    copy.ContentTime = copy.StudyTime
    copy.SeriesNumber = 2
    copy.InstanceNumber = 1
    copy.ImageType = ["DERIVED", "PRIMARY", "AXIAL"]
    copy.PatientIdentityRemoved = "YES"
    copy.DeidentificationMethod = "Metadata allowlist; pixel review required before use"
    for key in ("Rows", "Columns", "SamplesPerPixel", "PhotometricInterpretation",
                "BitsAllocated", "BitsStored", "HighBit", "PixelRepresentation",
                "PixelSpacing", "SliceThickness", "ImagePositionPatient",
                "ImageOrientationPatient", "RescaleIntercept", "RescaleSlope",
                "WindowCenter", "WindowWidth"):
        if key in source:
            copy[key] = source[key]
    copy.PixelData = source.PixelData
    dcmwrite(output, copy, enforce_file_format=True)

    saved = dcmread(output)
    if (any(element.tag.is_private for element in saved.iterall())
            or saved.PixelData != source.PixelData
            or str(saved.PatientID) != "DEMO-P001"):
        raise RuntimeError("Demo copy failed post-write verification")
    print(f"Demo copy: {output}")
    print(f"Pixel review: {preview}")
    print("Review the PNG before uploading; the original source was not changed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Source CT DICOM, mounted read-only if using Docker")
    args = parser.parse_args()
    prepare(args.source)

"""Private REST client for the small Orthanc study surface used by T07."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


ORTHANC_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{8}){4}\Z")
MAX_PREVIEW_BYTES = 8 * 1024 * 1024


class OrthancError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class OrthancUnavailable(OrthancError):
    pass


class OrthancNotFound(OrthancError):
    pass


class OrthancProtocolError(OrthancError):
    pass


@dataclass(frozen=True)
class OrthancStudy:
    orthanc_id: str
    study_instance_uid: str
    patient_id: str
    issuer_of_patient_id: str | None
    accession_number: str
    modality: str
    series_count: int
    instance_count: int


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrthancProtocolError("ORTHANC_BAD_METADATA")
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None  # Never forward Orthanc credentials to a redirect target.


def _remaining_ms(deadline: float) -> int:
    remaining = int((deadline - monotonic()) * 1000)
    if remaining < 50:
        raise OrthancUnavailable("ORTHANC_TIMEOUT")
    return remaining


class OrthancClient:
    def __init__(self, base_url: str, username: str, password: str, opener=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or not username or not password):
            raise ValueError("Invalid private Orthanc connection settings")
        self.base_url = base_url.rstrip("/")
        credentials = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        self._authorization = f"Basic {credentials}"
        self._open = opener or build_opener(_NoRedirect()).open

    def _json(self, method: str, path: str, timeout_ms: int, payload: dict | None = None) -> object:
        if not 50 <= timeout_ms <= 30_000:
            raise ValueError("timeout_ms must be between 50 and 30000")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base_url + path, data=body, method=method,
                          headers={"Authorization": self._authorization,
                                   "Accept": "application/json",
                                   **({"Content-Type": "application/json"} if body is not None else {})})
        try:
            with self._open(request, timeout=timeout_ms / 1000) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code == 404:
                raise OrthancNotFound("ORTHANC_STUDY_NOT_FOUND") from exc
            if exc.code in {401, 403}:
                raise OrthancUnavailable("ORTHANC_AUTH_FAILED") from exc
            if exc.code >= 500:
                raise OrthancUnavailable("ORTHANC_UNAVAILABLE") from exc
            raise OrthancProtocolError("ORTHANC_REQUEST_REJECTED") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OrthancUnavailable("ORTHANC_UNAVAILABLE") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OrthancProtocolError("ORTHANC_BAD_RESPONSE") from exc

    def find_study(self, study_instance_uid: str, timeout_ms: int) -> OrthancStudy | None:
        _required_text(study_instance_uid)
        deadline = monotonic() + timeout_ms / 1000
        matches = self._json("POST", "/tools/find", _remaining_ms(deadline),
                             {"Level": "Study", "Query": {"StudyInstanceUID": study_instance_uid}})
        if not isinstance(matches, list) or any(not isinstance(item, str) for item in matches):
            raise OrthancProtocolError("ORTHANC_BAD_RESPONSE")
        if not matches:
            return None
        if len(matches) != 1:
            raise OrthancProtocolError("ORTHANC_AMBIGUOUS_STUDY")
        study = self._get_study(matches[0], deadline)
        if study.study_instance_uid != study_instance_uid:
            raise OrthancProtocolError("ORTHANC_UID_MISMATCH")
        return study

    def get_study(self, orthanc_id: str, timeout_ms: int) -> OrthancStudy:
        return self._get_study(orthanc_id, monotonic() + timeout_ms / 1000)

    def get_preview(self, orthanc_id: str, timeout_ms: int) -> bytes:
        """Read one bounded PNG preview from a validated study reference."""
        if not ORTHANC_ID.fullmatch(orthanc_id):
            raise OrthancProtocolError("ORTHANC_BAD_ID")
        deadline = monotonic() + timeout_ms / 1000
        study = self._json("GET", f"/studies/{orthanc_id}", _remaining_ms(deadline))
        series_ids = study.get("Series") if isinstance(study, dict) and study.get("ID") == orthanc_id else None
        if (not isinstance(series_ids, list) or not series_ids or not isinstance(series_ids[0], str)
                or not ORTHANC_ID.fullmatch(series_ids[0])):
            raise OrthancProtocolError("ORTHANC_BAD_METADATA")
        series = self._json("GET", f"/series/{series_ids[0]}", _remaining_ms(deadline))
        instances = series.get("Instances") if isinstance(series, dict) and series.get("ID") == series_ids[0] else None
        if (not isinstance(instances, list) or not instances or not isinstance(instances[0], str)
                or not ORTHANC_ID.fullmatch(instances[0])):
            raise OrthancProtocolError("ORTHANC_BAD_METADATA")
        request = Request(self.base_url + f"/instances/{instances[0]}/preview", method="GET",
                          headers={"Authorization": self._authorization, "Accept": "image/png"})
        try:
            with self._open(request, timeout=_remaining_ms(deadline) / 1000) as response:
                image = response.read(MAX_PREVIEW_BYTES + 1)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise OrthancUnavailable("ORTHANC_AUTH_FAILED") from exc
            if exc.code == 404:
                raise OrthancNotFound("ORTHANC_STUDY_NOT_FOUND") from exc
            raise OrthancUnavailable("ORTHANC_UNAVAILABLE") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OrthancUnavailable("ORTHANC_UNAVAILABLE") from exc
        if len(image) > MAX_PREVIEW_BYTES or not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise OrthancProtocolError("ORTHANC_BAD_PREVIEW")
        return image

    def _get_study(self, orthanc_id: str, deadline: float) -> OrthancStudy:
        if not ORTHANC_ID.fullmatch(orthanc_id):
            raise OrthancProtocolError("ORTHANC_BAD_ID")
        study = self._json("GET", f"/studies/{orthanc_id}", _remaining_ms(deadline))
        if not isinstance(study, dict):
            raise OrthancProtocolError("ORTHANC_BAD_METADATA")
        tags = study.get("MainDicomTags")
        patient_tags = study.get("PatientMainDicomTags")
        series_ids = study.get("Series")
        if (study.get("ID") != orthanc_id or not isinstance(tags, dict)
                or not isinstance(patient_tags, dict) or not isinstance(series_ids, list)
                or any(not isinstance(item, str) for item in series_ids)
                or len(series_ids) != len(set(series_ids)) or not series_ids):
            raise OrthancProtocolError("ORTHANC_BAD_METADATA")
        modalities: set[str] = set()
        instance_ids: set[str] = set()
        for series_id in series_ids:
            if not isinstance(series_id, str) or not ORTHANC_ID.fullmatch(series_id):
                raise OrthancProtocolError("ORTHANC_BAD_METADATA")
            series = self._json("GET", f"/series/{series_id}", _remaining_ms(deadline))
            if not isinstance(series, dict) or series.get("ID") != series_id:
                raise OrthancProtocolError("ORTHANC_BAD_METADATA")
            series_tags = series.get("MainDicomTags")
            instances = series.get("Instances")
            if not isinstance(series_tags, dict) or not isinstance(instances, list):
                raise OrthancProtocolError("ORTHANC_BAD_METADATA")
            modalities.add(_required_text(series_tags.get("Modality")))
            for instance_id in instances:
                if not isinstance(instance_id, str) or not ORTHANC_ID.fullmatch(instance_id) or instance_id in instance_ids:
                    raise OrthancProtocolError("ORTHANC_BAD_METADATA")
                instance_ids.add(instance_id)
        if len(modalities) != 1:
            raise OrthancProtocolError("ORTHANC_MIXED_MODALITY")
        issuer = patient_tags.get("IssuerOfPatientID")
        if issuer is not None and not isinstance(issuer, str):
            raise OrthancProtocolError("ORTHANC_BAD_METADATA")
        return OrthancStudy(
            orthanc_id=orthanc_id,
            study_instance_uid=_required_text(tags.get("StudyInstanceUID")),
            patient_id=_required_text(patient_tags.get("PatientID")),
            issuer_of_patient_id=issuer or None,
            accession_number=_required_text(tags.get("AccessionNumber")),
            modality=modalities.pop(),
            series_count=len(series_ids), instance_count=len(instance_ids),
        )

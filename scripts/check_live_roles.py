#!/usr/bin/env python3
"""Exercise the four fictional roles against the loopback Docker app."""

import json
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://127.0.0.1:8000"
ENCOUNTER = "20000000-0000-4000-8000-000000000001"
LAB_BODY = {"observations": [
    {"code": "CRP", "value_numeric": 5.1, "unit": "mg/L"},
    {"code": "GLU", "value_numeric": 4.6, "unit": "mmol/L"},
]}


class Client:
    def __init__(self):
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def call(self, path, method="GET", body=None, content_type="application/json"):
        headers = {"Accept": "application/json"}
        if method != "GET":
            headers["Origin"] = ORIGIN
            csrf = next((cookie.value for cookie in self.cookies if cookie.name == "csrf_token"), None)
            if csrf:
                headers["X-CSRF-Token"] = csrf
        if body is not None:
            headers["Content-Type"] = content_type
            if content_type == "application/json":
                body = json.dumps(body).encode("utf-8")
        request = Request(ORIGIN + path, data=body, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None

    def login(self, username, password):
        status, _ = self.call("/api/v1/auth/login", "POST",
                              {"username": username, "password": password})
        check(status == 200, f"{username} login")


def check(condition, label):
    if not condition:
        raise RuntimeError(f"FAIL: {label}")
    print(f"PASS: {label}")


def summary(client):
    status, data = client.call(f"/api/v1/encounters/{ENCOUNTER}/summary")
    check(status == 200 and data["patient"]["external_id"] == "DEMO-P001", "authorized read")
    return data


def main():
    credentials = json.loads((ROOT / "infra/.secrets/demo_accounts.json").read_text(encoding="utf-8"))
    image = (ROOT / "data/generated/demo-002-ct.dcm").read_bytes()
    clients = {}
    for username, password in credentials.items():
        client = Client()
        client.login(username, password)
        clients[username] = client
    doctor, lab, imaging, radiologist = (clients[name] for name in
        ("demo-doctor", "demo-lab", "demo-imaging", "demo-radiologist"))
    initial = summary(doctor)
    lab_order = initial["laboratory"]["reports"][0]["lab_order_id"]
    lab_path = f"/api/v1/lab-orders/{lab_order}/reports"
    dicom_path = f"/api/v1/encounters/{ENCOUNTER}/imaging-studies"
    ris_body = {"encounter_id": ENCOUNTER, "accession_number": "DEMO-ACC002",
                "requested_procedure": "CT synthétique", "modality": "CT"}
    for username, client in clients.items():
        summary(client)
        if username != "demo-lab":
            check(client.call(lab_path, "POST", LAB_BODY)[0] == 403, f"{username} cannot edit LIS")
        if username != "demo-radiologist":
            check(client.call("/api/v1/radiology-orders", "POST", ris_body)[0] == 403,
                  f"{username} cannot edit RIS")
        if username != "demo-imaging":
            check(client.call(dicom_path, "POST", image, "application/dicom")[0] == 403,
                  f"{username} cannot edit PACS")
    status, result = lab.call(lab_path, "POST", LAB_BODY)
    check(status == 201 and result["version"] >= 2, "lab creates a versioned report")
    check(summary(doctor)["laboratory"]["reports"][0]["version"] == result["version"],
          "doctor sees updated lab report")
    exam = next((item for item in summary(radiologist)["radiology"]["exams"]
                 if item["accession_number"] == "DEMO-ACC002"), None)
    if exam is None:
        status, created = radiologist.call("/api/v1/radiology-orders", "POST", ris_body)
        check(status == 201, "radiologist creates RIS order")
        exam_id = created["exam_id"]
        now = datetime.now(timezone.utc).isoformat()
        check(radiologist.call(f"/api/v1/radiology-exams/{exam_id}", "PATCH",
                               {"status": "performed", "performed_at": now})[0] == 200,
              "radiologist marks examination performed")
        check(radiologist.call(f"/api/v1/radiology-exams/{exam_id}/report", "PUT",
                               {"content": "Compte rendu entièrement fictif pour DEMO-ACC002."})[0] == 200,
              "radiologist drafts report")
        check(radiologist.call(f"/api/v1/radiology-exams/{exam_id}/report/validate", "POST",
                               {"validated_at": datetime.now(timezone.utc).isoformat()})[0] == 200,
              "radiologist validates report")
    status, result = imaging.call(dicom_path, "POST", image, "application/dicom")
    check(status == 201 and result["imaging_study_id"], "imaging technician imports synthetic CT")
    check(any(item["study_instance_uid"] == "2.25.10102" for item in summary(doctor)["imaging"]["studies"]),
          "doctor sees imported study")


if __name__ == "__main__":
    main()

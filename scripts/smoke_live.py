"""Check the loopback demo API with a real session and synthetic encounter."""

import argparse
import getpass
import json
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a running local PACS/LIS/RIS demo")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.rstrip("/")):
        parser.error("The smoke test accepts only a loopback HTTP origin")
    origin = args.base_url.rstrip("/")
    cookies = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))

    def request(path: str, *, method: str = "GET", body: dict | None = None,
                csrf: str | None = None):
        headers = {"Accept": "application/json"}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if method != "GET":
            headers["Origin"] = origin
        if csrf:
            headers["X-CSRF-Token"] = csrf
        req = Request(origin + path, data=payload, headers=headers, method=method)
        try:
            with opener.open(req, timeout=5) as response:
                data = response.read(8 * 1024 * 1024 + 1)
                if len(data) > 8 * 1024 * 1024:
                    raise RuntimeError("Response exceeded the smoke-test limit")
                return (data if response.headers.get_content_type() == "image/png" else json.loads(data))
        except HTTPError as exc:
            raise RuntimeError(f"{path}: HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"{path}: service unreachable") from exc

    password = getpass.getpass("Demo account password: ")
    if request("/health/ready")["status"] != "ready":
        raise RuntimeError("Business service is not ready")
    request("/api/v1/auth/login", method="POST",
            body={"username": args.username, "password": password})
    password = ""
    csrf = next((cookie.value for cookie in cookies if cookie.name == "csrf_token"), None)
    if not csrf:
        raise RuntimeError("CSRF cookie missing")
    try:
        query = urlencode({"identifier_domain": "DEMO", "identifier": "DEMO-P001"})
        patients = request("/api/v1/patients?" + query)["patients"]
        if len(patients) != 1 or not patients[0]["is_synthetic"]:
            raise RuntimeError("Synthetic patient lookup failed")
        encounters = request(f"/api/v1/patients/{patients[0]['id']}/encounters")["encounters"]
        if not encounters:
            raise RuntimeError("No authorized encounter")
        summary = request(f"/api/v1/encounters/{encounters[0]['id']}/summary")
        if (summary["patient"]["id"] != patients[0]["id"]
                or summary["encounter"]["id"] != encounters[0]["id"]):
            raise RuntimeError("Summary identity mismatch")
        print("Patient, encounter and summary: OK")
        print("Laboratory:", summary["laboratory"]["status"])
        print("RIS exams:", len(summary["radiology"]["exams"]))
        print("Imaging:", summary["imaging"]["availability_status"])
        if summary["imaging"]["availability_status"] == "available" and summary["imaging"]["studies"]:
            study_id = summary["imaging"]["studies"][0]["id"]
            link = request(f"/api/v1/imaging-studies/{study_id}/viewer-link")["url"]
            if link != f"/api/v1/imaging-studies/{study_id}/preview":
                raise RuntimeError("Unexpected viewer route")
            if not request(link).startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Invalid imaging preview")
            print("Controlled preview: OK")
    finally:
        request("/api/v1/auth/logout", method="POST", csrf=csrf)


if __name__ == "__main__":
    main()

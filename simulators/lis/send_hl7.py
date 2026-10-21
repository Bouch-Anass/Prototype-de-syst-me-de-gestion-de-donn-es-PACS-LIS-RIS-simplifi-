"""Send one checked-in synthetic HL7 fixture to the local internal endpoint."""

import argparse
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data/hl7"
MESSAGES = ("order.oml.hl7", "result.nominal.oru.hl7", "result.missing-crp.oru.hl7",
            "result.correction.oru.hl7")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a synthetic DEMO-001 HL7 fixture")
    parser.add_argument("message", choices=MESSAGES)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    secret = os.getenv("HL7_SERVICE_SECRET")
    if not secret:
        parser.error("HL7_SERVICE_SECRET must be set in the environment")
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    url = f"http://127.0.0.1:{args.port}/internal/hl7/messages"
    request = Request(url, data=(FIXTURES / args.message).read_bytes(), method="POST",
                      headers={"Authorization": f"Bearer {secret}",
                               "Content-Type": "application/hl7-v2; charset=utf-8"})
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        print(f"HTTP {response.status}")
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()

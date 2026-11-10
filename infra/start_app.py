"""Load mounted local secrets, migrate the database, and serve the application."""

import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote


def main() -> None:
    secrets = Path("/run/secrets")
    password = (secrets / "postgres_password").read_text().strip()
    orthanc = json.loads((secrets / "orthanc.secret.json").read_text())
    os.environ["DATABASE_URL"] = (
        f"postgresql+psycopg://app:{quote(password, safe='')}@postgres:5432/pacs_lis_ris"
    )
    os.environ["ORTHANC_BASE_URL"] = "http://orthanc:8042"
    os.environ["ORTHANC_USERNAME"] = "demo"
    os.environ["ORTHANC_PASSWORD"] = orthanc["RegisteredUsers"]["demo"]
    os.environ["HL7_SERVICE_SECRET"] = (secrets / "hl7_service_secret").read_text().strip()
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", "8000", "--no-access-log",
    ])


if __name__ == "__main__":
    main()

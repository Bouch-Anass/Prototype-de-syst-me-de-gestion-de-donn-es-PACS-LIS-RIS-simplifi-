#!/usr/bin/env python3
"""Create local-only Compose secrets without replacing existing credentials."""

import json
import os
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / "infra" / ".secrets"


def create_once(path: Path, content: str) -> bool:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError:
        return False
    if os.name != "nt":
        path.chmod(0o600)
    return True


def main() -> None:
    SECRETS.mkdir(mode=0o700, parents=True, exist_ok=True)
    postgres_created = create_once(
        SECRETS / "postgres_password.txt", secrets.token_urlsafe(36) + "\n"
    )
    orthanc_config = {
        "AuthenticationEnabled": True,
        "RegisteredUsers": {"demo": secrets.token_urlsafe(36)},
    }
    orthanc_created = create_once(
        SECRETS / "orthanc.secret.json",
        json.dumps(orthanc_config, indent=2) + "\n",
    )
    print("Local secrets ready in infra/.secrets (ignored by Git).")
    if not (postgres_created and orthanc_created):
        print("Existing secret files were preserved.")
    print("Do not share or commit these files. See infra/README.md for startup.")


if __name__ == "__main__":
    main()

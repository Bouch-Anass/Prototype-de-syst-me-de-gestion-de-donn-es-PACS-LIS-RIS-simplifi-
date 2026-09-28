#!/usr/bin/env python3
"""Contrôles documentaires locaux, sans réseau ni dépendance tierce."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "ARCHITECTURE.md", "CONTRIBUTING.md", "SECURITY.md",
    ".env.example", ".gitignore", ".gitattributes",
    "docs/REPARTITION_TRAVAIL.md", "docs/BACKLOG.md", "docs/MODELE_DONNEES.md",
    "docs/DEMARRAGE.md", "docs/DECISIONS.md", "docs/REFERENCES.md",
    "backend/README.md", "frontend/README.md", "infra/README.md",
    "contracts/api.md", "contracts/hl7.md", "contracts/imaging.md",
    "data/fixtures/scenario.json",
    "contracts/examples/summary.nominal.json",
    "contracts/examples/summary.missing-crp.json",
    "contracts/examples/summary.orthanc-unavailable.json",
    ".github/workflows/check-architecture.yml",
)
IGNORED = {".git", ".venv", "node_modules", "__pycache__", "generated", "pacs-lis-ris-starter"}
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = chr(96) * 3


def main():
    errors = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"Fichier requis absent : {relative}")
    documents = []
    json_files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix == ".json":
            json_files.append(path)
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                errors.append(f"JSON invalide {path.relative_to(ROOT)} : {exc}")
        if path.suffix != ".md":
            continue
        documents.append(path)
        content = path.read_text(encoding="utf-8")
        if sum(line.startswith(FENCE) for line in content.splitlines()) % 2:
            errors.append(f"Bloc de code non fermé : {path.relative_to(ROOT)}")
        outside_code = re.sub(re.escape(FENCE) + r".*?" + re.escape(FENCE), "", content, flags=re.S)
        for match in LINK.finditer(outside_code):
            url = urlsplit(match.group(1))
            if url.scheme or url.netloc or not url.path:
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(ROOT):
                errors.append(f"Lien hors dépôt : {path.relative_to(ROOT)} -> {url.path}")
            elif not target.exists():
                errors.append(f"Lien local absent : {path.relative_to(ROOT)} -> {url.path}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK : {len(documents)} documents Markdown, {len(json_files)} fichiers JSON.")
    print("Liens locaux et fichiers requis vérifiés ; ancres et sites externes non vérifiés.")
    print("Ces contrôles ne valident pas une application HL7/DICOM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Software kit: preparation phase

> **Architecture update (2026-09-28):** the repository baseline now proposes **FastAPI + PostgreSQL + Orthanc**. This earlier preparation note remains useful for individual workstation setup, but its SQLite/Streamlit proposal is not the current architecture. See the root [README](../README.md), [ARCHITECTURE.md](../ARCHITECTURE.md), and [decisions](DECISIONS.md).

Prepared 2026-09-21 for a group of six who know Python. This is a proposal. The deadline and any teacher-imposed tools or development method remain to be confirmed.

## Recommended direction

Use **Python + Streamlit + SQLite + Orthanc** for a small local classroom prototype. Confirm this choice after the kickoff and a small technical trial.

- Python handles application logic and laboratory message processing.
- Streamlit provides the consultation interface.
- SQLite holds relational patient, order, and result records.
- Orthanc holds DICOM imaging, linked to the shared patient record.

The assignment requires HL7 v2 laboratory exchange. Plan a real message import; manually entered laboratory results alone will not demonstrate that requirement. Keep application logic separate from the interface when coding begins.

## Prepare now

| Tool | Purpose | Who needs it | Verification |
| --- | --- | --- | --- |
| [Git](https://git-scm.com/downloads) | Preserve the history of work | All six | `git --version` |
| GitHub account | Later repository collaboration | All six | Record each username; verify access when collaboration starts |
| [VS Code](https://code.visualstudio.com/download) | Common editor recommendation | All six | Open the folder and preview Markdown |
| [Python 3.13, standard 64-bit build](https://www.python.org/downloads/windows/) | Common Python minor version | All six | `py -3.13 --version` on Windows |
| [Microsoft Python extension](https://code.visualstudio.com/docs/python/python-tutorial) | Select and run the project interpreter | VS Code users | Select `.venv` after creating it |
| [diagrams.net](https://app.diagrams.net/) | Workflow, database, and architecture diagrams | Browser access for all six | Save an editable `.drawio` file locally |

Use the current maintenance release of Python 3.13 from the official site and record the exact installed version. Match the minor version across the group. Existing editors are acceptable if they can use the same environment. The diagrams.net [desktop version](https://www.drawio.com/docs/manual/editor/offline/) is optional.

## Add at the first technical trial

| Component | Purpose | Timing |
| --- | --- | --- |
| [Streamlit](https://docs.streamlit.io/get-started/installation/command-line) | Python consultation interface | Install in `.venv` after accepting the proposal |
| [SQLite via Python's `sqlite3`](https://docs.python.org/3.13/library/sqlite3.html) | Relational database | Included in standard Windows Python; no database server needed |
| [Orthanc](https://orthanc.uclouvain.be/book/users/quick-start-windows.html) | DICOM storage and retrieval | Trial on one computer, then document and repeat |
| DICOM, HL7 v2, and testing libraries | Synthetic samples, message parsing, validation | Choose versions after agreeing on formats and required fields |

Streamlit currently documents support for Python 3.10-3.14. Python 3.13 is our proposed common baseline, not a teacher requirement. Orthanc has an official Windows installation route, so Docker is optional for this starting setup.

## Windows setup checklist

These are instructions for the setup session; software has not been installed by preparing this kit.

1. Install or verify Git, VS Code, and standard Python 3.13 from the official links.
2. Open the project folder in VS Code and its PowerShell terminal.
3. Verify the base tools:

   ```powershell
   git --version
   py -3.13 --version
   ```

4. Create and check the environment:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\python.exe -m pip --version
   .\.venv\Scripts\python.exe -c "import sqlite3; print(sqlite3.sqlite_version)"
   ```

5. Run **Python: Select Interpreter** in VS Code and choose `.venv\Scripts\python.exe`. The commands use the executable directly; PowerShell activation is unnecessary.
6. Record actual results below. Stop here for basic preparation.

During the later Streamlit trial, after agreeing on the stack:

```powershell
.\.venv\Scripts\python.exe -m pip install streamlit
.\.venv\Scripts\python.exe -m streamlit hello
```

Stop the example with Ctrl+C. Record successful versions and establish a shared dependency file before implementation. This trial command is not yet a reproducible project installation specification.

For the Orthanc trial, follow its official Windows guide, keep the instance local, and record the version and configuration. Success means uploading and retrieving the same documented synthetic DICOM instance. Use generated storage outside Git or in the ignored `orthanc-storage/` directory. The assignment prohibits real patient data.

## Checks on this computer

Read-only checks on 2026-09-21 found:

- Git installed: `2.54.0.windows.1`.
- VS Code installed: `1.137.0`.
- Python launcher present, but `py -0p` reports **No installed Pythons found**. Install or locate a normal development interpreter before setup. The assistant's bundled interpreter used to read the PDF is not the team's project environment.
- Docker not found on PATH; optional for the proposed initial setup.
- Streamlit and Orthanc installation and operation have not been verified.
- Existing `main` branch and GitHub origin detected. Preparation did not create commits, push, or change GitHub settings.

## Team readiness

Replace placeholders with names and real results.

| Member | OS | Git version | Python version | Editor ready | Environment + SQLite checked | Blocker |
| --- | --- | --- | --- | --- | --- | --- |
| 1: TBD | TBD | TBD | TBD | No | No | TBD |
| 2: TBD | TBD | TBD | TBD | No | No | TBD |
| 3: TBD | TBD | TBD | TBD | No | No | TBD |
| 4: TBD | TBD | TBD | TBD | No | No | TBD |
| 5: TBD | TBD | TBD | TBD | No | No | TBD |
| 6: TBD | TBD | TBD | TBD | No | No | TBD |

## Assignment references

Project 5 is on PDF page 10. General requirements are on pages 3-4 and 14; assessment is on page 15.

Bookmark [Orthanc documentation](https://www.orthanc-server.com/static.php?page=documentation), the [DICOM standard](https://www.dicomstandard.org/), and [HL7 standards](https://www.hl7.org/implement/standards/). During design, record the DICOM edition/parts and the HL7 v2 version and message profile actually used. Detailed standard mappings and legal-source review belong in that phase; this kit does not establish compliance.

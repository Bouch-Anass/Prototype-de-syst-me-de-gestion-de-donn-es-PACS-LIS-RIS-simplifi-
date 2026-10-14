#!/usr/bin/env python3
"""Generate deterministic CR-terminated HL7 demo fixtures from the manifest."""

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "fixtures" / "scenario.json"
OUTPUT = ROOT / "data" / "hl7"


def segment(name: str, **numbered_fields: str) -> str:
    maximum = max((int(key[1:]) for key in numbered_fields), default=0)
    fields = [name] + [""] * maximum
    for key, value in numbered_fields.items():
        fields[int(key[1:])] = str(value)
    return "|".join(fields)


def msh(manifest: dict, message_type: str, control_id: str) -> str:
    h = manifest["hl7"]
    instant = datetime.fromisoformat(manifest["fixture_timestamp"].replace("Z", "+00:00"))
    timestamp = instant.strftime("%Y%m%d%H%M%S%z")
    # MSH-1 is the delimiter itself, so MSH-n occupies array position n-1.
    fields = ["MSH"] + [""] * 17
    values = {
        2: r"^~\&", 3: h["sending_application"], 4: h["sending_facility"],
        5: h["receiving_application"], 6: h["receiving_facility"],
        7: timestamp, 9: message_type, 10: control_id, 11: "P",
        12: h["version"], 18: "UNICODE UTF-8",
    }
    for number, value in values.items():
        fields[number - 1] = value
    return "|".join(fields)


def common(manifest: dict) -> tuple[str, str, str, str, str]:
    identity = manifest["identity"]
    lab = manifest["laboratory"]
    h = manifest["hl7"]
    domain = identity["identifier_domain"]
    pid = segment("PID", f1="1", f3=f"{identity['patient_external_id']}^^^{domain}^MR")
    pv1 = segment("PV1", f1="1", f2="O", f19=f"{identity['encounter_external_id']}^^^{domain}")
    placer = f"{lab['placer_number']}^{domain}"
    filler = f"{lab['filler_number']}^{lab['source_system']}"
    panel = f"{h['panel_code']}^{h['panel_display']}^{domain}"
    return pid, pv1, placer, filler, panel


def messages(manifest: dict) -> dict[str, bytes]:
    h = manifest["hl7"]
    pid, pv1, placer, filler, panel = common(manifest)
    order = [
        msh(manifest, "OML^O21^OML_O21", h["order_message_control_id"]),
        pid, pv1,
        segment("ORC", f1="NW", f2=placer, f3=filler),
        segment("OBR", f1="1", f2=placer, f3=filler, f4=panel),
    ]

    def result(control_id: str, missing_crp: bool = False, corrected: bool = False) -> bytes:
        status = "C" if corrected else "F"
        lines = [
            msh(manifest, "ORU^R01^ORU_R01", control_id), pid, pv1,
            segment("OBR", f1="1", f2=placer, f3=filler, f4=panel, f25=status),
        ]
        for observation in manifest["laboratory"]["expected_observations"]:
            if missing_crp and observation["code"] == "CRP":
                continue
            code = f"{observation['code']}^{observation['display']}^{observation['coding_system']}"
            value = observation.get("corrected_value_numeric", observation["nominal_value_numeric"]) if corrected else observation["nominal_value_numeric"]
            lines.append(segment(
                "OBX", f1=str(len(lines) - 3), f2="NM", f3=code,
                f5=str(value), f6=observation["unit"], f11=status,
            ))
        return ("\r".join(lines) + "\r").encode("utf-8")

    return {
        "order.oml.hl7": ("\r".join(order) + "\r").encode("utf-8"),
        "result.nominal.oru.hl7": result(h["result_message_control_id"]),
        "result.missing-crp.oru.hl7": result(h["missing_crp_message_control_id"], missing_crp=True),
        "result.correction.oru.hl7": result(h["correction_message_control_id"], corrected=True),
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUTPUT.mkdir(exist_ok=True)
    for filename, content in messages(manifest).items():
        (OUTPUT / filename).write_bytes(content)
        print(f"Wrote data/hl7/{filename}")


if __name__ == "__main__":
    main()

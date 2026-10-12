"""Export the stimulation results: one row per stimulation, or a report.

TWO SHAPES, FOR TWO USES

A table (CSV, TSV) carries one row per stimulated pair, with the responses
joined into one cell. That is what a spreadsheet, a statistics package or
a colleague's script expects: one line, one stimulation.

A report (TXT) prints the cards one after another, the way the window
shows them, for the patient file and for reading.

JSON keeps the records exactly as the project holds them, nested
responses included. It is the only lossless one, and the one to use to
carry the work to another tool without deciding in advance what matters.

WHAT IS NOT IN THE TABLE

Nothing is recomputed on the way out. A field that was never filled in
leaves its cell empty rather than guessing a value, and a protocol that
was not noted reads NA, as it does on screen.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from . import stimulation as st

#: The columns of the table, in the order a reader expects them.
COLUMNS: tuple[str, ...] = (
    "id",
    "pair",
    "polarity",
    "electrode_a",
    "contact_a",
    "label_a",
    "x_a",
    "y_a",
    "z_a",
    "anatomy_a",
    "electrode_b",
    "contact_b",
    "label_b",
    "x_b",
    "y_b",
    "z_b",
    "anatomy_b",
    "reference",
    "frequency_hz",
    "intensity_ma",
    "pulse_width_us",
    "train_duration_s",
    "threshold_ma",
    "at_ad_threshold",
    "behavioural_state",
    "medication",
    "since_last_seizure",
    "task",
    "silent",
    "events",
    "habitual",
    "reproducibility",
    "discharge_location",
    "discharge_remote",
    "discharge_evolution",
    "interrupted",
    "n_responses",
    "response_categories",
    "responses",
    "notes",
    "operator",
    "recorded",
)

#: What separates two responses inside one cell.
JOIN = " | "


def _yes_no(value) -> str:
    return "yes" if value else "no"


def _number(value) -> str:
    """A number, or NA when it was never noted. Never a silent zero."""
    if value is None:
        return st.NOT_AVAILABLE

    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return st.NOT_AVAILABLE


def _ras_of(name: str, index, electrodes: list[dict]):
    """The contact in the coordinates the application displays."""
    lps = st._contact_lps(name, index, electrodes)

    if lps is None:
        return "", "", ""

    return (
        f"{-float(lps[0]):.2f}",
        f"{-float(lps[1]):.2f}",
        f"{float(lps[2]):.2f}",
    )


def _anatomy_of(record: dict, label: str) -> str:
    """The region stored beside that contact, or empty.

    The two are stored as one list of "LABEL region" strings, which is
    what the window showed when the card was written.
    """
    for entry in record.get("anatomy", []) or []:
        text = str(entry).strip()

        if text.startswith(f"{label} "):
            return text[len(label) + 1 :]

    return ""


def row_of(record: dict, electrodes: list[dict]) -> dict[str, Any]:
    """One stimulation as one flat row."""
    record = record or {}

    name_a = str(record.get("electrode", ""))
    index_a = record.get("contact")
    label_a = st.contact_name(name_a, index_a or 0) if name_a else ""

    name_b = str(record.get("electrode_b", ""))
    index_b = record.get("contact_b")
    label_b = st.contact_name(name_b, index_b) if (name_b and index_b is not None) else ""

    x_a, y_a, z_a = _ras_of(name_a, index_a, electrodes)
    x_b, y_b, z_b = _ras_of(name_b, index_b, electrodes) if label_b else ("", "", "")

    responses = record.get("responses", []) or []

    return {
        "id": str(record.get("id", "")),
        "pair": st.pair_label(record),
        "polarity": str(record.get("polarity", "")),
        "electrode_a": name_a,
        "contact_a": "" if index_a is None else int(index_a) + 1,
        "label_a": label_a,
        "x_a": x_a,
        "y_a": y_a,
        "z_a": z_a,
        "anatomy_a": _anatomy_of(record, label_a),
        "electrode_b": name_b,
        "contact_b": "" if index_b is None else int(index_b) + 1,
        "label_b": label_b,
        "x_b": x_b,
        "y_b": y_b,
        "z_b": z_b,
        "anatomy_b": _anatomy_of(record, label_b) if label_b else "",
        "reference": str(record.get("reference", "")),
        "frequency_hz": _number(record.get("frequency_hz")),
        "intensity_ma": _number(record.get("intensity_ma")),
        "pulse_width_us": _number(record.get("pulse_width_us")),
        "train_duration_s": _number(record.get("train_duration_s")),
        "threshold_ma": _number(record.get("threshold_ma"))
        if record.get("threshold_ma") is not None
        else "",
        "at_ad_threshold": _yes_no(record.get("at_ad_threshold")),
        "behavioural_state": str(record.get("behavioural_state", "")),
        "medication": str(record.get("asm", "")),
        "since_last_seizure": str(record.get("time_since_last_seizure", "")),
        "task": str(record.get("task", "")),
        "silent": _yes_no(st.is_silent(record)),
        "events": JOIN.join(str(e) for e in record.get("events", []) or []),
        "habitual": str(record.get("habitual", "")),
        "reproducibility": str(record.get("reproducibility", "")),
        "discharge_location": str(record.get("ad_location", "")),
        "discharge_remote": _yes_no(record.get("ad_remote")),
        "discharge_evolution": str(record.get("ad_evolution", "")),
        "interrupted": _yes_no(record.get("aborted")),
        "n_responses": len(responses),
        "response_categories": JOIN.join(
            str(r.get("category", "")) for r in responses
        ),
        "responses": JOIN.join(st.response_label(r) for r in responses),
        "notes": str(record.get("notes", "")),
        "operator": str(record.get("operator", "")),
        "recorded": str(record.get("created", "")),
    }


def rows_of(records: list[dict], electrodes: list[dict]) -> list[dict[str, Any]]:
    return [row_of(record, electrodes) for record in records or []]


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def _write_table(path: Path, rows: list[dict], delimiter: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # newline="" is what csv asks for: without it every row gains a blank
    # line on Windows.
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(COLUMNS), delimiter=delimiter, extrasaction="ignore"
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(row)

    return path


def write_csv(path, records: list[dict], electrodes: list[dict]) -> Path:
    return _write_table(Path(path), rows_of(records, electrodes), ",")


def write_tsv(path, records: list[dict], electrodes: list[dict]) -> Path:
    return _write_table(Path(path), rows_of(records, electrodes), "\t")


def write_json(path, records: list[dict], electrodes: list[dict]) -> Path:
    """The records as the project holds them: the only lossless export."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(list(records or []), handle, indent=2, ensure_ascii=False)

    return path


def report_text(records: list[dict], patient: str = "") -> str:
    """The cards one after another, the way the window shows them."""
    lines: list[str] = ["NeuXelec stimulation results"]

    if patient:
        lines.append(f"Patient: {patient}")

    lines.append(f"{len(records or [])} stimulation(s)")
    lines.append("")

    for record in records or []:
        lines.append(st.pair_label(record))
        lines.append("-" * len(st.pair_label(record)))

        for label, value in st.card_fields(record):
            lines.append(f"{label}: {value}")

        lines.append("")

    return "\n".join(lines)


def write_report(path, records: list[dict], patient: str = "") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text(records, patient), encoding="utf-8")
    return path


#: Extension to writer, for a save dialog that decides by the name typed.
WRITERS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".txt": "txt",
}


def write_any(path, records: list[dict], electrodes: list[dict], patient: str = "") -> Path:
    """Write in the format the file name asks for, CSV by default."""
    path = Path(path)
    kind = WRITERS.get(path.suffix.lower(), "csv")

    if kind == "tsv":
        return write_tsv(path, records, electrodes)

    if kind == "json":
        return write_json(path, records, electrodes)

    if kind == "txt":
        return write_report(path, records, patient)

    return write_csv(path, records, electrodes)

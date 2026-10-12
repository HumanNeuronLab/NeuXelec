"""Tie the channels of a TRC recording to the reconstructed electrodes.

This is where a reader of SEEG goes wrong in the way that matters. Everything
else fails loudly: a missing file, an unreadable header, a window out of range.
Binding HAG3 to the wrong contact fails quietly, and the trace shown for an
electrode in the hippocampus is the one from somewhere else entirely. So the
mapping is proposed here and reviewed by a human before it counts, never
guessed and applied.

WHAT THE NAMES LOOK LIKE

Micromed names a channel after the electrode and the contact: HAG1 to HAG9,
IAG1 to IAG18. The trailing letter is the side, G for gauche and D for droite,
and it belongs to the electrode name rather than being a separate field. On
one recorded session the 198 channels resolve into 16 electrodes with no hole
in the numbering, which is what makes an automatic proposal worth making:
people tend to name their reconstruction after the recording.

WHAT IS NOT A CONTACT

Every TRC carries channels that were never in a brain: MKR1+ to MKR4+, X1 to
X8, ECG+ and ECG-. Fourteen of the 198 on that session. Reported as unmatched
they would be fourteen false alarms per patient, and a window that cries wolf
stops being read, so they are set aside as ignored instead.

WHY PAIRS AND NOT CONTACTS

SEEG is read bipolar, contact N against N+1, because a common reference
contaminates everything. So what a user needs out of this window is not how
many contacts matched but how many PAIRS they will be able to open. One contact
missing in the middle of a shaft costs two pairs, and that is the number worth
putting in front of someone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

#: electrode name then contact number, the whole of the Micromed convention
_CHANNEL = re.compile(r"^([A-Za-z][A-Za-z'_.-]*?)\s*(\d+)\s*$")

#: Channels that were never in a brain. Matched on the whole name, case
#: insensitively, so a contact called "XING2" is not caught by the X rule.
_NOT_A_CONTACT = (
    re.compile(r"^MKR\d*[+-]?$", re.I),      # markers written by the headbox
    re.compile(r"^X\d+$", re.I),             # unused amplifier inputs
    re.compile(r"^ECG[+-]?$", re.I),
    re.compile(r"^EKG[+-]?$", re.I),
    re.compile(r"^EMG\d*[+-]?$", re.I),
    re.compile(r"^EOG\d*[+-]?$", re.I),
    re.compile(r"^(RESP|SPO2|SAT|PULS|PNI|TEMP|MIC|PHO|TRIG)\w*$", re.I),
    re.compile(r"^(REF|GND|GRD)\w*$", re.I),
)


def is_contact_channel(name: str) -> bool:
    """Whether a channel name could name an electrode contact."""
    text = str(name).strip()
    if not text:
        return False
    if any(rule.match(text) for rule in _NOT_A_CONTACT):
        return False
    return _CHANNEL.match(text) is not None


def split_channel(name: str) -> tuple[str, int] | None:
    """``"HAG12"`` into ``("HAG", 12)``, or None when it names no contact."""
    if not is_contact_channel(name):
        return None
    match = _CHANNEL.match(str(name).strip())
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def normalise(name: str) -> str:
    """Compare electrode names without punctuation or case.

    ``HAG``, ``hag``, ``H_A_G`` and ``HA-G`` are one electrode written four
    ways, and a mapping that refuses them makes the user redo by hand what the
    computer should have seen.
    """
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())


@dataclass
class ElectrodeMatch:
    """One reconstructed electrode and the TRC channels standing for it."""

    recon_name: str
    trc_prefix: str | None
    recon_contacts: int
    trc_contacts: tuple[int, ...] = ()
    manual: bool = False

    @property
    def matched(self) -> bool:
        return self.trc_prefix is not None and bool(self.trc_contacts)

    @property
    def missing_in_trc(self) -> list[int]:
        """Contacts localised but not recorded: disconnected, or off the headbox."""
        if not self.matched:
            return list(range(1, self.recon_contacts + 1))
        present = set(self.trc_contacts)
        return [n for n in range(1, self.recon_contacts + 1) if n not in present]

    @property
    def extra_in_trc(self) -> list[int]:
        """Contacts recorded but not localised, numbering past the reconstruction."""
        return [n for n in self.trc_contacts if n > self.recon_contacts]

    def bipolar_pairs(self) -> list[tuple[int, int]]:
        """Consecutive contacts present on both sides, as (N, N+1)."""
        if not self.matched:
            return []
        usable = sorted(n for n in self.trc_contacts if n <= self.recon_contacts)
        return [(a, b) for a, b in zip(usable, usable[1:]) if b == a + 1]

    def channel_names(self, contact: int) -> str | None:
        if not self.matched or contact not in self.trc_contacts:
            return None
        return f"{self.trc_prefix}{contact}"


@dataclass
class MatchReport:
    """What the review window shows, and what the project stores."""

    electrodes: list[ElectrodeMatch] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    unused_trc_prefixes: list[str] = field(default_factory=list)

    @property
    def matched(self) -> list[ElectrodeMatch]:
        return [e for e in self.electrodes if e.matched]

    @property
    def unmatched(self) -> list[ElectrodeMatch]:
        return [e for e in self.electrodes if not e.matched]

    @property
    def total_pairs(self) -> int:
        return sum(len(e.bipolar_pairs()) for e in self.electrodes)

    def warnings(self) -> list[str]:
        """One line per thing a human should look at before validating."""
        out: list[str] = []
        for e in self.electrodes:
            if not e.matched:
                out.append(f"{e.recon_name}: no channel found in the recording.")
                continue
            missing = e.missing_in_trc
            extra = e.extra_in_trc
            if missing:
                out.append(
                    f"{e.recon_name}: {len(missing)} contact(s) localised but not "
                    f"recorded ({', '.join(str(n) for n in missing)}). "
                    f"{len(e.bipolar_pairs())} pair(s) instead of {max(e.recon_contacts - 1, 0)}."
                )
            if extra:
                out.append(
                    f"{e.recon_name}: {len(extra)} channel(s) recorded beyond the "
                    f"reconstruction ({e.trc_prefix}{extra[0]} and up), not localised."
                )
        for prefix in self.unused_trc_prefixes:
            out.append(f"{prefix}: recorded, but no electrode of that name was reconstructed.")
        return out

    def to_dict(self) -> dict:
        return {
            "electrodes": [
                {
                    "recon_name": e.recon_name,
                    "trc_prefix": e.trc_prefix,
                    "recon_contacts": e.recon_contacts,
                    "trc_contacts": list(e.trc_contacts),
                    "manual": e.manual,
                }
                for e in self.electrodes
            ],
            "ignored": list(self.ignored),
            "unused_trc_prefixes": list(self.unused_trc_prefixes),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MatchReport":
        return cls(
            electrodes=[
                ElectrodeMatch(
                    recon_name=e["recon_name"],
                    trc_prefix=e.get("trc_prefix"),
                    recon_contacts=int(e.get("recon_contacts", 0)),
                    trc_contacts=tuple(e.get("trc_contacts") or ()),
                    manual=bool(e.get("manual", False)),
                )
                for e in data.get("electrodes") or []
            ],
            ignored=list(data.get("ignored") or []),
            unused_trc_prefixes=list(data.get("unused_trc_prefixes") or []),
        )


def group_trc_channels(channels: Iterable[str]) -> tuple[dict[str, list[int]], list[str]]:
    """Channel names into ``{electrode: [contact numbers]}`` plus the ignored ones."""
    electrodes: dict[str, list[int]] = {}
    ignored: list[str] = []
    for name in channels:
        split = split_channel(name)
        if split is None:
            ignored.append(str(name))
            continue
        prefix, number = split
        electrodes.setdefault(prefix, []).append(number)
    for numbers in electrodes.values():
        numbers.sort()
    return electrodes, ignored


def propose(
    trc_channels: Sequence[str],
    reconstructed: Sequence[dict],
) -> MatchReport:
    """Pair reconstructed electrodes with TRC channels, on names alone.

    ``reconstructed`` holds the project's electrodes, each with a ``name`` and
    its ``contacts_lps``. Nothing is decided here: the result is a proposal to
    be shown, corrected and validated.
    """
    groups, ignored = group_trc_channels(trc_channels)
    by_key = {normalise(prefix): prefix for prefix in groups}

    report = MatchReport(ignored=sorted(ignored))
    taken: set[str] = set()
    for electrode in reconstructed:
        name = str(electrode.get("name") or "").strip()
        count = len(electrode.get("contacts_lps") or [])
        prefix = by_key.get(normalise(name))
        if prefix is not None and prefix not in taken:
            taken.add(prefix)
            report.electrodes.append(
                ElectrodeMatch(
                    recon_name=name,
                    trc_prefix=prefix,
                    recon_contacts=count,
                    trc_contacts=tuple(groups[prefix]),
                )
            )
        else:
            report.electrodes.append(
                ElectrodeMatch(recon_name=name, trc_prefix=None, recon_contacts=count)
            )

    report.unused_trc_prefixes = sorted(p for p in groups if p not in taken)
    return report


def bind(report: MatchReport, recon_name: str, trc_prefix: str | None,
         trc_channels: Sequence[str]) -> None:
    """Attach a TRC electrode to a reconstructed one by hand, or detach it.

    Used by the review window. A prefix can only serve one electrode, so taking
    it releases it from wherever it was.
    """
    groups, _ = group_trc_channels(trc_channels)
    for electrode in report.electrodes:
        if electrode.trc_prefix == trc_prefix and electrode.recon_name != recon_name:
            electrode.trc_prefix = None
            electrode.trc_contacts = ()
            electrode.manual = True
    for electrode in report.electrodes:
        if electrode.recon_name != recon_name:
            continue
        electrode.trc_prefix = trc_prefix
        electrode.trc_contacts = tuple(groups.get(trc_prefix or "", ()))
        electrode.manual = True
    taken = {e.trc_prefix for e in report.electrodes if e.trc_prefix}
    report.unused_trc_prefixes = sorted(p for p in groups if p not in taken)

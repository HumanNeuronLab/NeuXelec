"""Read a folder of Micromed TRC files as one continuous recording.

A monitoring session is not a file, it is a folder: one recorded session holds
439 of them, 811 GB, twelve days end to end, because Micromed closes a file
around two gigabytes. Nothing here ever loads a file. ``neo`` memory-maps the
signal, so reading a window is a seek: measured on that session, ten seconds of
all 198 channels comes back in under a millisecond whatever the file weighs.

What costs time is the scan, 0.12 s per file to read a header, 52 s for 439 on
a network share. It runs once and :meth:`TrcRecording.to_dict` is meant to be
stored in the project so the next right-click opens straight away.

TWO THINGS THE DATA ITSELF TAUGHT US

``Trigger`` is not an annotation channel. That session holds 565,221 of them,
the code 255 alone appearing 176,257 times: they are sync pulses. The 346
``Note`` events are the ones a human typed, and they are what anyone wants to
see: "crise" ten times in twelve days, the stimulation parameters, "Reveil par
infirmiere". Triggers are therefore left out unless asked for.

A folder is not guaranteed to hold one montage. Three files of that same
session carry 256 channels named Z1L, L1Z and so on, nothing to do with the
patient's electrodes. They are kept out of the timeline and reported in
:attr:`TrcRecording.rejected`, rather than quietly breaking a channel mapping
built from the other 436.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

#: Event channel holding what a human typed. The other one, "Trigger", is
#: machine sync.
NOTE_CHANNEL = "Note"
TRIGGER_CHANNEL = "Trigger"


@dataclass(frozen=True)
class Segment:
    """One TRC file, placed on the wall clock."""

    path: Path
    start: datetime
    duration_s: float
    n_samples: int
    sampling_rate: float
    channels: tuple[str, ...]

    @property
    def stop(self) -> datetime:
        return self.start + timedelta(seconds=self.duration_s)

    def contains(self, when: datetime) -> bool:
        return self.start <= when < self.stop


@dataclass(frozen=True)
class Marker:
    """An event, placed on the wall clock rather than inside its file."""

    when: datetime
    text: str
    channel: str
    path: Path
    offset_s: float


def _read_header(path: Path):
    from neo.rawio import MicromedRawIO

    reader = MicromedRawIO(filename=str(path))
    reader.parse_header()
    return reader


def _segment_of(reader, path: Path) -> Segment:
    signal = reader.header["signal_channels"]
    rates = {float(c["sampling_rate"]) for c in signal}
    if len(rates) != 1:
        raise ValueError(f"{path.name}: several sampling rates, {sorted(rates)}")
    n = int(reader.get_signal_size(0, 0, stream_index=0))
    rate = rates.pop()
    return Segment(
        path=path,
        start=reader.raw_annotations["blocks"][0]["rec_datetime"],
        duration_s=n / rate,
        n_samples=n,
        sampling_rate=rate,
        channels=tuple(str(c["name"]) for c in signal),
    )


def _markers_of(reader, segment: Segment, include_triggers: bool) -> list[Marker]:
    out: list[Marker] = []
    for index, channel in enumerate(reader.header["event_channels"]):
        name = str(channel["name"])
        if name == TRIGGER_CHANNEL and not include_triggers:
            continue
        if reader.event_count(0, 0, index) == 0:
            continue
        stamps, _durations, labels = reader.get_event_timestamps(0, 0, index)
        seconds = reader.rescale_event_timestamp(stamps, dtype="float64")
        for k in range(len(stamps)):
            text = str(labels[k]) if labels is not None else ""
            out.append(
                Marker(
                    when=segment.start + timedelta(seconds=float(seconds[k])),
                    text=text,
                    channel=name,
                    path=segment.path,
                    offset_s=float(seconds[k]),
                )
            )
    return out


class TrcRecording:
    """Every TRC of a folder, ordered on the wall clock.

    ``segments`` share one montage, the one most files agree on. Anything else
    lands in ``rejected``: it is reported, never silently dropped.
    """

    def __init__(
        self,
        folder: Path | str,
        segments: Sequence[Segment],
        markers: Sequence[Marker],
        rejected: Sequence[tuple[Path, str]] = (),
    ):
        self.folder = Path(folder)
        self.segments = sorted(segments, key=lambda s: s.start)
        self.markers = sorted(markers, key=lambda m: m.when)
        self.rejected = list(rejected)

    # ------------------------------------------------------------------ scan
    @classmethod
    def scan(cls, folder: Path | str, *, include_triggers: bool = False) -> "TrcRecording":
        folder = Path(folder)
        # Windows matches case-insensitively, so both patterns return the same
        # files; the set is what stops every one of them being read twice.
        paths = sorted({p.resolve() for p in folder.glob("*.TRC")} | {p.resolve() for p in folder.glob("*.trc")})
        if not paths:
            raise FileNotFoundError(f"No TRC file in {folder}")

        read: list[tuple[Segment, object]] = []
        rejected: list[tuple[Path, str]] = []
        for path in paths:
            try:
                reader = _read_header(path)
                read.append((_segment_of(reader, path), reader))
            except Exception as error:
                rejected.append((path, str(error)))

        if not read:
            raise ValueError(f"No readable TRC in {folder}")

        # The montage most files agree on wins. A session can hold a handful of
        # files recorded with another headbox, and those must not be allowed to
        # define the channel list the mapping is built from.
        counts: dict[tuple[str, ...], int] = {}
        for segment, _ in read:
            counts[segment.channels] = counts.get(segment.channels, 0) + 1
        montage = max(counts, key=lambda key: (counts[key], len(key)))

        segments: list[Segment] = []
        markers: list[Marker] = []
        for segment, reader in read:
            if segment.channels != montage:
                rejected.append(
                    (
                        segment.path,
                        f"another montage, {len(segment.channels)} channels instead of {len(montage)}",
                    )
                )
                continue
            segments.append(segment)
            markers.extend(_markers_of(reader, segment, include_triggers))

        return cls(folder, segments, markers, rejected)

    # ------------------------------------------------------------- the basics
    @property
    def channels(self) -> tuple[str, ...]:
        return self.segments[0].channels if self.segments else ()

    @property
    def sampling_rate(self) -> float:
        return self.segments[0].sampling_rate if self.segments else 0.0

    @property
    def start(self) -> datetime | None:
        return self.segments[0].start if self.segments else None

    @property
    def stop(self) -> datetime | None:
        return self.segments[-1].stop if self.segments else None

    def gaps(self, minimum_s: float = 2.0) -> list[tuple[datetime, datetime, float]]:
        """Interruptions between consecutive files.

        Sixty-seven of them on that session, the longest 42 minutes. A timeline
        that ignores them sends the user looking for an instant that was never
        recorded.
        """
        out = []
        for before, after in zip(self.segments, self.segments[1:]):
            seconds = (after.start - before.stop).total_seconds()
            if seconds > minimum_s:
                out.append((before.stop, after.start, seconds))
        return out

    def notes(self) -> list[Marker]:
        return [m for m in self.markers if m.channel == NOTE_CHANNEL]

    def segment_at(self, when: datetime) -> Segment | None:
        for segment in self.segments:
            if segment.contains(when):
                return segment
        return None

    # ------------------------------------------------------------- the signal
    def read(
        self,
        when: datetime,
        duration_s: float,
        channels: Sequence[str] | None = None,
    ) -> tuple[np.ndarray, float]:
        """Signal for ``duration_s`` from ``when``, as (samples, channels) in uV.

        A window is not confined to one file. Asking for ten seconds forty
        minutes into a session lands near a file boundary often enough that
        truncating there would be noticed every time; the window is therefore
        assembled across files, and the stretch covered by a gap comes back as
        NaN rather than as silence that looks like flat signal.
        """
        if not self.segments:
            raise ValueError("Nothing to read: the recording holds no segment.")

        names = list(channels) if channels is not None else list(self.channels)
        unknown = [n for n in names if n not in self.channels]
        if unknown:
            raise KeyError(f"Unknown channel(s): {unknown}")
        indexes = [self.channels.index(n) for n in names]

        rate = self.sampling_rate
        total = int(round(duration_s * rate))
        out = np.full((total, len(names)), np.nan, dtype=np.float32)
        stop = when + timedelta(seconds=duration_s)

        for segment in self.segments:
            if segment.stop <= when or segment.start >= stop:
                continue
            first = max(when, segment.start)
            last = min(stop, segment.stop)

            i_start = int(round((first - segment.start).total_seconds() * rate))
            i_stop = int(round((last - segment.start).total_seconds() * rate))
            i_start = max(0, min(i_start, segment.n_samples))
            i_stop = max(i_start, min(i_stop, segment.n_samples))
            if i_stop == i_start:
                continue

            reader = _read_header(segment.path)
            block = reader.get_analogsignal_chunk(
                block_index=0,
                seg_index=0,
                i_start=i_start,
                i_stop=i_stop,
                stream_index=0,
                channel_indexes=indexes,
            )
            block = reader.rescale_signal_raw_to_float(
                block, dtype="float32", stream_index=0, channel_indexes=indexes
            )

            at = int(round((first - when).total_seconds() * rate))
            at = max(0, min(at, total))
            take = min(block.shape[0], total - at)
            if take > 0:
                out[at : at + take, :] = block[:take, :]

        return out, rate

    # ------------------------------------------------------- project storage
    def to_dict(self) -> dict:
        """What the project stores so the next scan is not needed.

        The channel list is kept with it: that is what tells us later whether
        the folder still holds the recording the mapping was built against.
        """
        return {
            "folder": str(self.folder),
            "channels": list(self.channels),
            "sampling_rate": self.sampling_rate,
            "segments": [
                {
                    "path": str(s.path),
                    "start": s.start.isoformat(),
                    "duration_s": s.duration_s,
                    "n_samples": s.n_samples,
                    "sampling_rate": s.sampling_rate,
                }
                for s in self.segments
            ],
            "markers": [
                {
                    "when": m.when.isoformat(),
                    "text": m.text,
                    "channel": m.channel,
                    "path": str(m.path),
                    "offset_s": m.offset_s,
                }
                for m in self.markers
            ],
            "rejected": [[str(p), why] for p, why in self.rejected],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrcRecording":
        channels = tuple(data.get("channels") or ())
        segments = [
            Segment(
                path=Path(s["path"]),
                start=datetime.fromisoformat(s["start"]),
                duration_s=float(s["duration_s"]),
                n_samples=int(s["n_samples"]),
                sampling_rate=float(s["sampling_rate"]),
                channels=channels,
            )
            for s in data.get("segments") or []
        ]
        markers = [
            Marker(
                when=datetime.fromisoformat(m["when"]),
                text=m["text"],
                channel=m["channel"],
                path=Path(m["path"]),
                offset_s=float(m["offset_s"]),
            )
            for m in data.get("markers") or []
        ]
        rejected = [(Path(p), why) for p, why in data.get("rejected") or []]
        return cls(data.get("folder", ""), segments, markers, rejected)

    def still_matches_disk(self) -> bool:
        """Whether the folder still holds what was scanned.

        Guards the stale mapping: a file added or removed, or a montage change,
        and the stored channel mapping may no longer describe what is there.
        """
        try:
            on_disk = {p.resolve() for p in self.folder.glob("*.TRC")} | {
                p.resolve() for p in self.folder.glob("*.trc")
            }
        except OSError:
            return False
        known = {s.path.resolve() for s in self.segments} | {p.resolve() for p, _ in self.rejected}
        return on_disk == known

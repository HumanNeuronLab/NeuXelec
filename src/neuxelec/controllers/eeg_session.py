"""Open the EEG window for a contact, asking only what is not already known.

The whole point is that the second right-click costs nothing. The first one
asks for the folder, scans it and shows the mapping for review; everything it
learns is stored in the project, so afterwards the window opens straight away.

The mapping is revisited only for a reason: the folder moved, its files
changed, or the user asked. Silent staleness is the failure to avoid, because a
mapping that no longer describes the recording still draws a trace, just not
the right one.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog

from ..utils.eeg_channel_match import MatchReport, propose
from ..utils.trc_reader import TrcRecording

logger = logging.getLogger(__name__)


def _message(parent, title: str, text: str, kind: str = "warning") -> None:
    from ..ui.neuxelec_message_dialog import NeuXelecMessageDialog

    getattr(NeuXelecMessageDialog, kind)(parent, title, text)


def _stored_recording(state) -> TrcRecording | None:
    data = getattr(state, "eeg_recording", None)
    if not data:
        return None
    try:
        return TrcRecording.from_dict(data)
    except Exception:
        logger.exception("Stored EEG recording could not be read back")
        return None


def _stored_match(state) -> MatchReport | None:
    data = getattr(state, "eeg_match", None)
    if not data:
        return None
    try:
        return MatchReport.from_dict(data)
    except Exception:
        logger.exception("Stored EEG channel mapping could not be read back")
        return None


def _scan(parent, folder: Path) -> TrcRecording | None:
    QApplication.setOverrideCursor(Qt.WaitCursor)
    QApplication.processEvents()
    try:
        return TrcRecording.scan(folder)
    except Exception as error:
        _message(parent, "No recording here", f"{folder}\n\n{error}", "critical")
        return None
    finally:
        QApplication.restoreOverrideCursor()


def _review(parent, state, recording: TrcRecording) -> MatchReport | None:
    from ..ui.eeg_match_dialog import EegMatchDialog

    electrodes = list(getattr(state, "electrodes", None) or [])
    if not electrodes:
        _message(parent, "No electrode", "Reconstruct the electrodes before opening the EEG.")
        return None

    report = propose(recording.channels, electrodes)
    dialog = EegMatchDialog(report, list(recording.channels), str(recording.folder), parent)
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.report()


def open_eeg_viewer(
    parent,
    state,
    electrode_name: str | None = None,
    contact: int | None = None,
    *,
    force_rematch: bool = False,
) -> None:
    """Entry point of the context menu, for an electrode or a single contact."""
    recording = None if force_rematch else _stored_recording(state)
    report = None if force_rematch else _stored_match(state)

    if recording is not None and not recording.still_matches_disk():
        logger.info("The TRC folder changed on disk, asking for the mapping again")
        _message(
            parent,
            "The recording changed",
            "The folder no longer holds the files this project was mapped against. "
            "The channel mapping has to be reviewed again.",
            "information",
        )
        recording, report = None, None

    if recording is None:
        start = str(getattr(state, "eeg_folder", "") or getattr(state, "last_browse_dir", "") or "")
        folder = QFileDialog.getExistingDirectory(parent, "Folder holding the TRC files", start)
        if not folder:
            return
        recording = _scan(parent, Path(folder))
        if recording is None:
            return
        report = None

    if report is None:
        report = _review(parent, state, recording)
        if report is None:
            return

    state.eeg_folder = str(recording.folder)
    state.eeg_recording = recording.to_dict()
    state.eeg_match = report.to_dict()

    if not report.matched:
        _message(
            parent,
            "Nothing to show",
            "No reconstructed electrode could be bound to a channel of this recording.",
        )
        return

    from ..ui.eeg_viewer_dialog import EegViewerDialog

    viewer = EegViewerDialog(
        recording=recording,
        report=report,
        # Passed whole, for the colours: a trace keeps the colour its shaft has
        # in the 3D view, which is what lets six electrodes share one screen.
        electrodes=list(getattr(state, "electrodes", None) or []),
        electrode_name=electrode_name,
        contact=contact,
        parent=parent,
    )
    # Modeless on purpose: reading the trace while turning the 3D view is the
    # whole reason for putting the two in the same application.
    viewer.setModal(False)
    viewer.show()
    # Kept referenced, or Python collects it and the window vanishes.
    existing = getattr(state, "_eeg_windows", None)
    if existing is None:
        existing = []
        state._eeg_windows = existing
    existing.append(viewer)

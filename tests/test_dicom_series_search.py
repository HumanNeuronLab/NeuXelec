# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Picking a DICOM folder.

A clinical export arrives as ``PAT_xxx/DICOM/SERIE_1/*.dcm``, and pointing at
``PAT_xxx`` is what anyone does first. SimpleITK's ``GetGDCMSeriesIDs`` has no
recursive mode, so it used to report nothing there: ITK printed "No Series were
found" from C++ and NeuXelec refused a folder that did hold the images.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import SimpleITK as sitk

from neuxelec.utils.format_convert import (
    convert_dicom_folder_to_nifti,
    find_dicom_series,
)

_UID = "1.2.826.0.1.3680043.2.1125.1.99999"


def _write_series(directory: Path, index: int, slices: int = 3, name: str = "") -> Path:
    """A small but genuine DICOM series, readable by GDCM."""
    directory.mkdir(parents=True, exist_ok=True)
    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()
    for k in range(slices):
        img = sitk.GetImageFromArray(np.full((8, 8), 100 + k, dtype=np.int16))
        tags = {
            "0008|0016": "1.2.840.10008.5.1.4.1.1.4",  # MR Image Storage
            "0008|0060": "MR",
            "0020|000d": f"{_UID}.{index}.1",  # StudyInstanceUID
            "0020|000e": f"{_UID}.{index}.2",  # SeriesInstanceUID
            "0008|0018": f"{_UID}.{index}.3.{k}",  # SOPInstanceUID
            "0020|0013": str(k),
            "0020|0032": f"0\\0\\{k}",
            "0028|0030": "1\\1",
            "0018|0050": "1",
        }
        if name:
            tags["0008|103e"] = name  # SeriesDescription
        for key, value in tags.items():
            img.SetMetaData(key, value)
        writer.SetFileName(str(directory / f"sl{k:02d}.dcm"))
        writer.Execute(img)
    return directory


def test_a_series_sitting_directly_in_the_folder_is_found(tmp_path: Path) -> None:
    _write_series(tmp_path, 1)
    found = find_dicom_series(str(tmp_path))
    assert [d for d, _ in found] == [str(tmp_path)]


def test_a_series_one_level_down_is_found(tmp_path: Path) -> None:
    """The case that used to fail: the export folder, not the series folder."""
    serie = _write_series(tmp_path / "DICOM" / "SERIE_1", 1)
    found = find_dicom_series(str(tmp_path))
    assert [d for d, _ in found] == [str(serie)]


def test_that_folder_now_converts(tmp_path: Path) -> None:
    _write_series(tmp_path / "DICOM" / "SERIE_1", 1)
    out = tmp_path / "out.nii.gz"
    convert_dicom_folder_to_nifti(str(tmp_path), str(out))
    assert sitk.ReadImage(str(out)).GetSize() == (8, 8, 3)


def test_an_empty_folder_still_refuses(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("nothing to see")
    with pytest.raises(RuntimeError, match="No DICOM series found"):
        convert_dicom_folder_to_nifti(str(tmp_path), str(tmp_path / "out.nii.gz"))


def test_several_series_in_the_folder_itself_keep_taking_the_first(tmp_path: Path) -> None:
    """Folders that already worked must not start refusing."""
    _write_series(tmp_path, 1, slices=3)
    _write_series(tmp_path, 2, slices=5)
    out = tmp_path / "out.nii.gz"
    convert_dicom_folder_to_nifti(str(tmp_path), str(out))
    assert sitk.ReadImage(str(out)).GetSize()[2] in (3, 5)


def test_several_series_below_are_named_instead_of_guessed(tmp_path: Path) -> None:
    """Silently taking the first would load the localizer instead of the T1."""
    _write_series(tmp_path / "S1", 1, name="localizer")
    _write_series(tmp_path / "S2", 2, name="T1 MPRAGE")

    assert len(find_dicom_series(str(tmp_path))) == 2
    with pytest.raises(RuntimeError) as err:
        convert_dicom_folder_to_nifti(str(tmp_path), str(tmp_path / "out.nii.gz"))

    message = str(err.value)
    assert "localizer" in message and "T1 MPRAGE" in message
    assert "3 slices" in message


def test_the_search_leaves_itk_warnings_switched_back_on(tmp_path: Path) -> None:
    """The scan silences ITK; it must not leave the whole app muted."""
    before = sitk.ProcessObject.GetGlobalWarningDisplay()
    find_dicom_series(str(tmp_path))
    assert sitk.ProcessObject.GetGlobalWarningDisplay() is before


def test_the_search_stays_quiet(tmp_path: Path, capfd: pytest.CaptureFixture) -> None:
    """No "No Series were found" per folder walked."""
    _write_series(tmp_path / "a" / "b" / "SERIE", 1)
    for extra in ("x", "y", "z"):
        (tmp_path / extra).mkdir()
    find_dicom_series(str(tmp_path))
    assert "No Series" not in capfd.readouterr().err


def test_the_search_stops_at_three_levels(tmp_path: Path) -> None:
    """A mis-click on a whole drive must not walk it."""
    _write_series(tmp_path / "a" / "b" / "c" / "d" / "SERIE", 1)
    assert find_dicom_series(str(tmp_path)) == []

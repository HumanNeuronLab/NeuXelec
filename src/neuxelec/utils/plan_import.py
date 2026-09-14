# -*- coding: utf-8 -*-
"""
Bring a NeuroInspire implantation plan into NeuXelec's MRI-1 (T1) space.

Plan coordinates are DICOM LPS of the *planning* MRI series. Two cases:

* the loaded MRI 1 **is** the planning series (same SeriesInstanceUID, or the
  user says so): coordinates are used as they are (``mode="identity"``);
* otherwise the planning MRI is rigidly registered to MRI 1 with the existing
  ANTs engine (``coregistration.rigid_coreg_to_fixed``) and the entry/target
  points are mapped through the resulting affine (``mode="affine"``).

ANTs convention reminder: the ``0GenericAffine.mat`` produced by registering
``moving`` onto ``fixed`` maps FIXED-space points into MOVING space (that is what
image resampling needs). To map POINTS from the moving (planning) space into the
fixed (MRI 1) space we therefore apply the *inverse*: ``-t [affine.mat,1]``.
"""
from __future__ import annotations

import csv
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Sequence

Point = tuple[float, float, float]


# ----------------------------------------------------------------------------- DICOM UIDs
def series_uid_from_source(path: str | os.PathLike | None) -> str | None:
    """SeriesInstanceUID (0020,000E) of a DICOM folder / file, or ``None`` if the
    source is not DICOM (NIfTI, MGZ, ...) or cannot be read."""
    if not path:
        return None
    try:
        import SimpleITK as sitk  # local import: keep this module importable without ITK
    except Exception:
        return None
    p = Path(path)
    try:
        if p.is_dir():
            files = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(str(p))
            if not files:
                return None
            first = files[0]
        elif p.is_file():
            first = str(p)
        else:
            return None
        r = sitk.ImageFileReader()
        r.SetFileName(first)
        r.LoadPrivateTagsOff()
        r.ReadImageInformation()
        if not r.HasMetaDataKey("0020|000e"):
            return None
        return r.GetMetaData("0020|000e").strip() or None
    except Exception:
        return None


# ----------------------------------------------------------------------------- geometry
def hemisphere_from_lps_x(x: float, midline_x: float = 0.0, margin_mm: float = 5.0) -> str | None:
    """Hemisphere from an LPS x coordinate (+x = patient Left). ``None`` near the midline."""
    if x > midline_x + margin_mm:
        return "L"
    if x < midline_x - margin_mm:
        return "R"
    return None


def theoretical_contacts(
    entry: Sequence[float], target: Sequence[float], spacings_mm: Sequence[float]
) -> list[Point]:
    """Planned contact centres: the deepest contact at ``target`` and the others
    back towards ``entry`` separated by ``spacings_mm`` (deepest -> next ...)."""
    e = [float(v) for v in entry]
    t = [float(v) for v in target]
    v = [a - b for a, b in zip(t, e)]
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-9:
        return [tuple(t)]
    u = [c / n for c in v]
    out: list[Point] = [tuple(t)]
    d = 0.0
    for s in spacings_mm:
        d += float(s)
        out.append(tuple(t[i] - u[i] * d for i in range(3)))
    return out


# ----------------------------------------------------------------------------- ANTs points
def transform_points_moving_to_fixed(
    points_lps: Iterable[Point], affine_mat_path: str | os.PathLike
) -> list[Point]:
    """Map LPS points from the MOVING image space into the FIXED image space using
    an ANTs ``0GenericAffine.mat`` (inverse applied, see module docstring)."""
    from ..coregistration import _ants_exe  # reuse the bundled ANTs binaries

    affine_mat_path = str(affine_mat_path)
    if not Path(affine_mat_path).exists():
        raise FileNotFoundError(f"Affine transform not found:\n{affine_mat_path}")
    pts = [tuple(float(v) for v in p) for p in points_lps]
    if not pts:
        return []
    exe = str(_ants_exe("antsApplyTransformsToPoints.exe"))
    with tempfile.TemporaryDirectory(prefix="neuxelec_plan_points_") as tmp:
        tmp = Path(tmp)
        in_csv, out_csv = tmp / "in.csv", tmp / "out.csv"
        with open(in_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["x", "y", "z", "t"])
            w.writeheader()
            for x, y, z in pts:
                w.writerow({"x": x, "y": y, "z": z, "t": 0.0})
        cmd = [exe, "-d", "3", "-i", str(in_csv), "-o", str(out_csv), "-t", f"[{affine_mat_path},1]"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not out_csv.exists():
            raise RuntimeError(
                "antsApplyTransformsToPoints failed:\n" + (res.stderr or res.stdout or "")
            )
        out: list[Point] = []
        with open(out_csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out.append((float(row["x"]), float(row["y"]), float(row["z"])))
    if len(out) != len(pts):
        raise RuntimeError("antsApplyTransformsToPoints returned an unexpected number of points")
    return out


# ----------------------------------------------------------------------------- plan -> T1
def build_trajectories_t1(
    plan: dict,
    mode: str,
    affine_mat_path: str | os.PathLike | None = None,
) -> list[dict]:
    """Return the plan trajectories with ``entry_t1_lps`` / ``target_t1_lps`` added.

    ``mode``: ``"identity"`` (MRI 1 is the planning series) or ``"affine"``
    (planning MRI registered onto MRI 1; ``affine_mat_path`` required).
    """
    trajs = plan.get("trajectories", []) or []
    if mode == "identity":
        mapped_e = [tuple(float(v) for v in t["entry_mm"]) for t in trajs]
        mapped_t = [tuple(float(v) for v in t["target_mm"]) for t in trajs]
    elif mode == "affine":
        if not affine_mat_path:
            raise ValueError("affine mode requires affine_mat_path")
        pts = [tuple(float(v) for v in t["entry_mm"]) for t in trajs] + [
            tuple(float(v) for v in t["target_mm"]) for t in trajs
        ]
        out = transform_points_moving_to_fixed(pts, affine_mat_path)
        mapped_e, mapped_t = out[: len(trajs)], out[len(trajs) :]
    else:
        raise ValueError(f"unknown mode {mode!r}")

    result = []
    for t, e, g in zip(trajs, mapped_e, mapped_t):
        d = dict(t)
        d["entry_t1_lps"] = [round(v, 3) for v in e]
        d["target_t1_lps"] = [round(v, 3) for v in g]
        d["hemisphere_guess"] = hemisphere_from_lps_x(e[0])
        result.append(d)
    return result


def summarize_plan(plan: dict) -> str:
    """One-line human summary used by the cockpit tooltip / status."""
    info = plan.get("plan_info", {}) or {}
    cs = plan.get("coordinate_system", {}) or {}
    n = plan.get("n_trajectories", len(plan.get("trajectories", []) or []))
    return (
        f"{plan.get('source', 'plan')} {info.get('software_version') or ''} · "
        f"{n} trajectories · reference MRI: {cs.get('reference_series_name') or '?'}"
    ).strip()

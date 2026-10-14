# -*- coding: utf-8 -*-
# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
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


def is_identity_transform(transform, tol_mm: float = 1e-4, tol_deg: float = 1e-3) -> bool:
    """True when a rigid refinement leaves everything where it was."""
    import math

    try:
        translation = [abs(float(v)) for v in transform.GetTranslation()]
        angles = [
            abs(math.degrees(float(a)))
            for a in (
                transform.GetAngleX(),
                transform.GetAngleY(),
                transform.GetAngleZ(),
            )
        ]
    except Exception:
        return False
    return max(translation) <= tol_mm and max(angles) <= tol_deg


def describe_rigid_transform(transform) -> dict:
    """JSON-friendly record of a rigid refinement, kept in the project file."""
    import math

    return {
        "translation_mm": [round(float(v), 4) for v in transform.GetTranslation()],
        "angles_deg": [
            round(math.degrees(float(a)), 4)
            for a in (
                transform.GetAngleX(),
                transform.GetAngleY(),
                transform.GetAngleZ(),
            )
        ],
        "center_lps": [round(float(v), 4) for v in transform.GetCenter()],
    }


def apply_manual_refinement(trajectories: list[dict], transform) -> list[dict]:
    """Move the plan points through the manual refinement of the review window.

    The review hands the transform back the way SimpleITK resamples an image:
    it maps a point of the corrected image onto the uncorrected one. A point
    therefore travels the other way, through the inverse, otherwise the
    trajectories would move away from the anatomy the user just aligned.

    ``trajectories`` are the dicts returned by :func:`build_trajectories_t1`.
    The result carries the corrected ``entry_t1_lps`` / ``target_t1_lps`` and
    the hemisphere recomputed from the corrected entry point.
    """
    inverse = transform.GetInverse()
    result = []
    for traj in trajectories:
        moved = dict(traj)
        for key in ("entry_t1_lps", "target_t1_lps"):
            point = moved.get(key)
            if point is None:
                continue
            new_point = inverse.TransformPoint(tuple(float(v) for v in point))
            moved[key] = [round(float(v), 3) for v in new_point]
        entry = moved.get("entry_t1_lps")
        if entry:
            moved["hemisphere_guess"] = hemisphere_from_lps_x(entry[0])
        result.append(moved)
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


# ======================================================================
# Relire un fichier de trajectoires ecrit par NeuXelec
# ======================================================================
#
# Save plan MRI / electrodes ecrit les trajectoires en LPS, deja dans
# l'espace de MRI 1. Les relire evite de refaire tout le chemin
# d'import : pas de .nip a retrouver, pas d'IRM de planification a
# recaler, pas d'alignement a revoir. Les coordonnees sont celles que
# NeuXelec a lui-meme calculees.
#
# C'est aussi pourquoi la verification porte sur l'espace et non sur la
# forme : un fichier bien ecrit mais calcule contre une autre IRM se
# lirait sans erreur et placerait les electrodes a cote.

#: La premiere ligne du fichier, qui le distingue de tout autre texte.
TRAJECTORY_FILE_HEADER = "SEEG_planned_trajectories"


def is_planned_trajectories_file(path: str | os.PathLike) -> bool:
    """Ce fichier est-il un export de trajectoires de NeuXelec ?

    On lit la premiere ligne plutot que de se fier a l'extension : un
    .txt ne dit rien, et l'utilisateur renomme ses fichiers.
    """
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            return handle.readline().strip() == TRAJECTORY_FILE_HEADER
    except Exception:
        return False


def _parse_lps_fields(reste: str):
    """``x=.. | y=.. | z=..`` vers un triplet, ou ``None``."""
    valeurs = {}
    for morceau in reste.split("|"):
        if "=" not in morceau:
            continue
        cle, _, valeur = morceau.partition("=")
        cle = cle.strip().lower()
        if cle in ("x", "y", "z"):
            try:
                valeurs[cle] = float(valeur.strip())
            except ValueError:
                return None
    if len(valeurs) != 3:
        return None
    return [valeurs["x"], valeurs["y"], valeurs["z"]]


def read_planned_trajectories(path: str | os.PathLike) -> dict:
    """Relire un export de trajectoires en un plan deja exprime en MRI 1.

    Rend un dictionnaire de la meme forme que celui d'un .nip importe,
    avec ``trajectories_t1`` rempli : les coordonnees du fichier sont
    deja celles de MRI 1, donc rien n'est a transformer.

    Leve ``ValueError`` si le fichier n'est pas un export de NeuXelec,
    ou s'il ne contient aucune trajectoire : mieux vaut le dire que
    poser un plan vide dont rien n'expliquerait le silence.
    """
    chemin = Path(path)
    entete: dict[str, str] = {}
    trajectoires: list[dict] = []
    courante: dict | None = None

    with open(chemin, encoding="utf-8", errors="ignore") as handle:
        premiere = handle.readline().strip()
        if premiere != TRAJECTORY_FILE_HEADER:
            raise ValueError(
                "This is not a NeuXelec trajectories file "
                f"(its first line reads {premiere!r})."
            )

        for ligne in handle:
            nu = ligne.strip()
            if not nu or set(nu) == {"="}:
                continue

            if nu.startswith("["):
                nom, _, reste = nu[1:].partition("]")
                courante = {
                    "name": nom.strip(),
                    "contacts_t1_lps": [],
                }
                for morceau in reste.split("|"):
                    cle, _, valeur = morceau.partition("=")
                    cle, valeur = cle.strip().lower(), valeur.strip()
                    if cle == "reference":
                        courante["reference_key"] = valeur
                        courante["reference"] = valeur
                    elif cle == "hemisphere":
                        courante["hemisphere"] = valeur
                trajectoires.append(courante)
                continue

            if courante is None:
                cle, _, valeur = nu.partition(":")
                if valeur:
                    entete[cle.strip().lower()] = valeur.strip()
                continue

            mot, _, reste = nu.partition("|")
            mot = mot.strip().lower()
            point = _parse_lps_fields(reste)
            if point is None:
                continue
            if mot == "entry":
                courante["entry_t1_lps"] = point
                courante["entry_mm"] = point
            elif mot == "target":
                courante["target_t1_lps"] = point
                courante["target_mm"] = point
            elif mot.startswith("contact"):
                courante["contacts_t1_lps"].append(point)

    if not trajectoires:
        raise ValueError("This trajectories file holds no electrode.")

    for traj in trajectoires:
        traj["contact_count"] = len(traj["contacts_t1_lps"])
        if not traj.get("hemisphere"):
            cible = traj.get("target_t1_lps")
            if cible:
                traj["hemisphere"] = hemisphere_from_lps_x(cible[0]) or ""

    # "LPS (nom_de_l_IRM)" : on garde le nom entre parentheses, qui dit
    # contre quelle IRM ces coordonnees ont ete calculees.
    repere = entete.get("coordinate system", "")
    etiquette = ""
    if "(" in repere and ")" in repere:
        etiquette = repere[repere.index("(") + 1 : repere.rindex(")")].strip()

    return {
        "source": entete.get("plan source", "NeuXelec trajectories"),
        "patient": entete.get("patient", ""),
        "export_date": entete.get("export date", ""),
        "coordinate_label": etiquette,
        "n_trajectories": len(trajectoires),
        "trajectories": trajectoires,
        "trajectories_t1": trajectoires,
        "transform": {"mode": "identity", "from_trajectories_file": str(chemin)},
    }


def trajectories_inside_fraction(trajectories, image) -> float:
    """Quelle part des points tombe dans le volume de l'image.

    La question posee est : ces coordonnees decrivent-elles bien cette
    IRM. Un plan calcule contre une autre serie se lit sans erreur et
    se poserait a cote du cerveau ; seul un comptage le montre.
    """
    if image is None:
        return 1.0

    points = []
    for traj in trajectories or []:
        for cle in ("entry_t1_lps", "target_t1_lps"):
            point = traj.get(cle)
            if point:
                points.append(point)
        points.extend(traj.get("contacts_t1_lps") or [])
    if not points:
        return 0.0

    taille = image.GetSize()
    dedans = 0
    for point in points:
        try:
            index = image.TransformPhysicalPointToIndex(
                tuple(float(v) for v in point)
            )
        except Exception:
            continue
        if all(0 <= i < n for i, n in zip(index, taille, strict=True)):
            dedans += 1
    return dedans / len(points)

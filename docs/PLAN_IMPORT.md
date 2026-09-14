# Implantation plan import (NeuroInspire `.nip`) and automatic detection

## What it does
1. **Files / Coregistration → Load Planning** reads a Renishaw NeuroInspire `.nip`
   plan *without SQL Server* (`neuxelec.utils.nip_reader`): electrode names,
   DIXI references (→ NeuXelec keys such as `DIXI-D08-12AM`), number of contacts,
   contact spacing, entry / target coordinates (DICOM LPS of the planning MRI) and
   the planning MRI series (name + SeriesInstanceUID).
2. A dialog lists the trajectories and asks how to express them in MRI 1 space:
   * MRI 1 **is** the planning MRI (detected automatically when MRI 1 was loaded
     from DICOM and the SeriesInstanceUID matches, or ticked by the user) → the
     coordinates are used directly;
   * otherwise choose the planning MRI (NIfTI or DICOM folder): it is rigidly
     registered onto MRI 1 with the usual ANTs engine and the points are mapped
     with `antsApplyTransformsToPoints -t [affine,1]` (moving → fixed).
3. The plan is stored in the project (`plan` key of the project JSON) and shown
   in the cockpit (**PLANNING** row: Missing / Loaded / Ready).
4. **Reconstruction → Automatic detection** (button above *Electrode parameters*)
   reconstructs every planned electrode not already in the list:
   * reference and hemisphere filled from the plan (unknown DIXI references are
     registered like user references);
   * deepest and second contacts detected on the CT (`neuxelec.utils.auto_detect`);
   * the standard two-point estimation is then run (LocalMax on), so electrodes
     appear in the electrode list exactly like a manual reconstruction and stay
     fully editable (rename, move contacts, delete...).
   A summary reports the electrodes reconstructed, those to review (weak metal
   contrast, metal beyond the search window, incomplete span) and those skipped.

## How the deepest contact is found
The planned axis is first re-centred laterally (±3 mm grid) on the metal, a thin
intensity profile is sampled along it, and the **distal end of the metal** is
located within ±15 mm of the planned target (threshold halfway between metal and
background). The deepest contact centre is 1 mm proximal to that end, the second
contact one spacing further back; both are refined by the intensity-weighted
centroid of the bright voxels. On a 1-mm CT the 1.5-mm gaps between 2-mm
contacts are not resolved, which is why the end of the metal, not the gap
pattern, anchors the phase.

## Developer notes
* Reader validation: `python scripts/nip_reader.py plan.nip --oracle plan_from_sql.json`
  (the SQL-Server converter on branch `feature/nip-autodetection` is the oracle).
* Tests: `tests/test_nip_reader_records.py`, `tests/test_plan_import.py`,
  `tests/test_auto_detect.py`.
* Still to validate on real data: the registration path and the detector on a
  post-implantation CT (compare with a manual reconstruction), and whether
  NeuroInspire's *target* is the electrode tip or the centre of contact 1.

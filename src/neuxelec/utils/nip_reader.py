# -*- coding: utf-8 -*-
"""
Read a Renishaw NeuroInspire ``.nip`` implantation plan WITHOUT SQL Server.

A ``.nip`` is a ZIP holding ``PlanInformation.xml`` and a Microsoft SQL Server
backup (``<guid>.sql-backup``, MTF-wrapped). The backup contains the database's
8-KB data pages verbatim, so the rows of the tables we need are decoded directly
from the page / record format (page header + slot array -> records; record =
status, fixed-length columns, null bitmap, variable-length columns).

Reading records THROUGH THE SLOT ARRAY is what makes this reliable: deleted or
superseded rows (ghosts) are not referenced by any slot, whereas raw pattern
matching happily picks them up.

Tables decoded (NeuroInspire 6.3.1 schema, self-validated by column counts):

* ``Trajectories`` : Id, TargetX/Y/Z, EntryX/Y/Z, ImplantableId, Name
* ``Implantables`` : Id, Description (catalogue reference), Manufacturer,
  ContactCount, ContactSeparation, ContactLength, Diameter
* ``Series``       : Id, SeriesInstanceUID, DisplayName, Protocol, patient fields
* ``Matrices``     : Id, 4x4 (row-major). The reference series is the one whose
  registration matrix is the identity: coordinates are in that series' DICOM LPS
  space.

Pure standard library; ~3 s for an 800-MB backup.
"""
from __future__ import annotations

import csv
import json
import mmap
import os
import re
import struct
import tempfile
import zipfile
from pathlib import Path

PAGE = 8192
HDR = 96


# ----------------------------------------------------------------------------- pages
def iter_data_pages(buf):
    """Yield ``(offset, slots)`` of plausible 8-KB DATA pages (type 1).

    Pages are 8-KB blocks inside the MTF stream; every 4096-byte offset is tested
    so both possible alignments are covered.
    """
    n = len(buf)
    for p in range(0, n - PAGE + 1, 4096):
        if buf[p] != 1 or buf[p + 1] != 1 or buf[p + 3] != 0:
            continue
        (slot_cnt,) = struct.unpack_from("<H", buf, p + 22)
        (free_cnt,) = struct.unpack_from("<H", buf, p + 28)
        if not (1 <= slot_cnt <= 700) or free_cnt > PAGE - HDR:
            continue
        slots = [struct.unpack_from("<H", buf, p + PAGE - 2 * (i + 1))[0] for i in range(slot_cnt)]
        if all(HDR <= s < PAGE - 2 * slot_cnt for s in slots):
            yield p, slots


def record_shape(buf, o):
    """Return ``(status, fixed_end, ncols, nvar, var_ends, var_start)`` of the
    record at offset ``o``, or ``None`` if it is not a primary data record."""
    try:
        status, fixed_end = struct.unpack_from("<HH", buf, o)
    except struct.error:
        return None
    rtype = (status >> 1) & 0x7  # 0 = primary record
    if rtype != 0 or fixed_end < 4 or fixed_end > PAGE:
        return None
    has_null = bool(status & 0x10)
    has_var = bool(status & 0x20)
    try:
        (ncols,) = struct.unpack_from("<H", buf, o + fixed_end)
    except struct.error:
        return None
    if not (1 <= ncols <= 200):
        return None
    p = o + fixed_end + 2 + ((ncols + 7) // 8 if has_null else 0)
    nvar, var_ends = 0, []
    if has_var:
        try:
            (nvar,) = struct.unpack_from("<H", buf, p)
            var_ends = list(struct.unpack_from("<%dH" % nvar, buf, p + 2))
        except struct.error:
            return None
        p += 2 + 2 * nvar
        if nvar > 40 or any(e < p - o or e > PAGE for e in var_ends):
            return None
    return status, fixed_end, ncols, nvar, var_ends, p - o


def var_strings(buf, o, var_ends, var_start):
    out, prev = [], var_start
    for e in var_ends:
        out.append(buf[o + prev : o + e].decode("utf-16-le", "replace") if e >= prev else "")
        prev = e
    return out


# ----------------------------------------------------------------------------- tables
_NAME_RE = re.compile(r"[A-Za-z0-9_\-' ]{1,40}")


def decode_trajectory(buf, o, shp):
    _status, fixed_end, ncols, nvar, var_ends, vs = shp
    if fixed_end != 60 or ncols != 9 or nvar != 1:
        return None
    (tid,) = struct.unpack_from("<i", buf, o + 4)
    c = struct.unpack_from("<6d", buf, o + 8)
    (imp,) = struct.unpack_from("<i", buf, o + 56)
    name = var_strings(buf, o, var_ends, vs)[0]
    if not _NAME_RE.fullmatch(name):
        return None
    return dict(
        id=tid,
        name=name,
        implantable_id=imp,
        target_mm=[round(v, 4) for v in c[:3]],
        entry_mm=[round(v, 4) for v in c[3:]],
    )


def decode_implantable(buf, o, shp):
    _status, fixed_end, ncols, nvar, var_ends, vs = shp
    if fixed_end != 90 or ncols != 18 or nvar != 2:
        return None
    (iid,) = struct.unpack_from("<i", buf, o + 4)
    fx = o + 8
    (diameter,) = struct.unpack_from("<d", buf, fx + 10)
    (total_len,) = struct.unpack_from("<d", buf, fx + 18)
    (contact_len,) = struct.unpack_from("<d", buf, fx + 50)
    (contact_count,) = struct.unpack_from("<i", buf, fx + 58)
    (contact_sep,) = struct.unpack_from("<d", buf, fx + 62)
    desc, manu = var_strings(buf, o, var_ends, vs)[:2]
    if not (1 <= contact_count <= 64) or not (0.1 < diameter < 5):
        return None
    return dict(
        id=iid,
        description=desc,
        manufacturer=manu,
        contact_count=contact_count,
        contact_separation_mm=round(contact_sep, 4),
        contact_length_mm=round(contact_len, 4),
        diameter_mm=round(diameter, 4),
        total_length_mm=round(total_len, 2),
        reference_key=f"{manu}-{desc}" if manu else desc,
    )


def decode_matrix(buf, o, shp):
    _status, fixed_end, ncols, nvar, _var_ends, _vs = shp
    if fixed_end != 136 or ncols != 17 or nvar != 0:
        return None
    (mid,) = struct.unpack_from("<i", buf, o + 4)
    m = struct.unpack_from("<16d", buf, o + 8)
    if any(v != v for v in m):
        return None
    return dict(id=mid, matrix=[list(m[i : i + 4]) for i in range(0, 16, 4)])


_UID_RE = re.compile(r"[0-9.]{10,64}")
_MOD_RE = re.compile(rb"\b(MR|CT|PT|NM|XA|MG|US)\b")


def decode_series(buf, o, shp):
    _status, fixed_end, ncols, nvar, var_ends, vs = shp
    if ncols != 36 or nvar != 8:
        return None
    (sid,) = struct.unpack_from("<i", buf, o + 4)
    strs = var_strings(buf, o, var_ends, vs)
    uid = strs[0]
    if not _UID_RE.fullmatch(uid):
        return None
    fixed = buf[o + 8 : o + fixed_end]
    ints = [struct.unpack_from("<i", fixed, k)[0] for k in range(0, len(fixed) - 3, 4)]
    mod = _MOD_RE.search(fixed)
    return dict(
        id=sid,
        series_instance_uid=uid,
        display_name=strs[1],
        protocol=strs[2],
        patient_id=strs[3],
        patient_name=strs[4],
        patient_birthdate=strs[5],
        study_instance_uid=strs[6],
        modality=mod.group(1).decode() if mod else None,
        _ints=ints,
    )


# ----------------------------------------------------------------------------- driver
def read_backup(buf):
    """Decode the four tables from a memory-mapped (or bytes) SQL backup."""
    T, I, M, S = {}, {}, {}, {}
    for p, slots in iter_data_pages(buf):
        for s in slots:
            o = p + s
            shp = record_shape(buf, o)
            if not shp:
                continue
            for dec, store in (
                (decode_trajectory, T),
                (decode_implantable, I),
                (decode_matrix, M),
                (decode_series, S),
            ):
                r = dec(buf, o, shp)
                if r:
                    store.setdefault(r["id"], r)  # first slot-referenced copy wins
                    break
    return T, I, M, S


def is_identity(m, tol=1e-9):
    return all(abs(m[i][j] - (1.0 if i == j else 0.0)) < tol for i in range(4) for j in range(4))


def pick_reference_series(S, M):
    """The reference series is the one whose registration matrix is the identity.

    The column holding ``RegistrationMatrix`` is not hard-coded: any int field of
    a series that names an identity matrix makes it a candidate.
    """
    ident_ids = {mid for mid, m in M.items() if is_identity(m["matrix"])}
    cands = [s for s in S.values() if any(v in ident_ids for v in s["_ints"])]
    if len(cands) == 1:
        return cands[0]
    mr = [s for s in S.values() if s.get("modality") == "MR"]
    return (mr or list(S.values()) or [None])[0]


def _plan_information(z: zipfile.ZipFile) -> dict:
    xml = [i for i in z.infolist() if i.filename.lower().endswith(".xml")]
    if not xml:
        return {}
    x = z.read(xml[0]).decode("utf-8", "replace")

    def tag(t):
        m = re.search(r"<%s>(.*?)</%s>" % (t, t), x, re.S)
        return m.group(1) if m else None

    return dict(
        software_version=tag("SoftwareVersionNumber"),
        product=tag("ProductLine"),
        created=tag("CreatedOn"),
        modified=tag("LastModifiedOn"),
        description=tag("Description"),
        patient_id=tag("Id"),
        patient_name=tag("Name"),
        patient_birthdate=tag("DateOfBirth"),
    )


def read_nip(nip_path: str | os.PathLike) -> dict:
    """Parse a ``.nip`` file and return the plan as a JSON-serialisable dict."""
    nip_path = str(nip_path)
    z = zipfile.ZipFile(nip_path)
    info = _plan_information(z)
    bak = [i for i in z.infolist() if i.filename.lower().endswith((".sql-backup", ".bak"))]
    if not bak:
        raise RuntimeError("No SQL backup member found inside the .nip file.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bak")
    tmp.close()
    try:
        with z.open(bak[0]) as src, open(tmp.name, "wb") as dst:
            while True:
                b = src.read(16 << 20)
                if not b:
                    break
                dst.write(b)
        with open(tmp.name, "rb") as f:
            buf = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                T, I, M, S = read_backup(buf)
            finally:
                buf.close()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if not T:
        raise RuntimeError(
            "No trajectory could be decoded from this .nip (unsupported NeuroInspire "
            "version or schema?)."
        )
    ref = pick_reference_series(S, M)
    trajectories = []
    for t in sorted(T.values(), key=lambda r: r["name"]):
        imp = I.get(t["implantable_id"], {})
        e, g = t["entry_mm"], t["target_mm"]
        length = sum((a - b) ** 2 for a, b in zip(e, g)) ** 0.5
        trajectories.append(
            dict(
                name=t["name"],
                reference_key=imp.get("reference_key"),
                reference=imp.get("description"),
                manufacturer=imp.get("manufacturer"),
                contact_count=imp.get("contact_count"),
                contact_separation_mm=imp.get("contact_separation_mm"),
                contact_length_mm=imp.get("contact_length_mm"),
                diameter_mm=imp.get("diameter_mm"),
                entry_mm=e,
                target_mm=g,
                length_mm=round(length, 2),
                nip_trajectory_id=t["id"],
                nip_implantable_id=t["implantable_id"],
            )
        )
    return dict(
        source="NeuroInspire",
        source_path=nip_path,
        reader="neuxelec.utils.nip_reader (pure Python, page/slot decoding)",
        plan_info=info,
        coordinate_system=dict(
            description=(
                "DICOM LPS (Left-Posterior-Superior) scanner space of the reference MRI series"
            ),
            reference_series_uid=ref["series_instance_uid"] if ref else None,
            reference_series_name=ref["display_name"] if ref else None,
            reference_series_protocol=ref["protocol"] if ref else None,
            reference_series_modality=ref.get("modality") if ref else None,
            note=(
                "To use these coordinates on another image, register the reference MRI "
                "to it and apply the transform."
            ),
        ),
        series=[{k: v for k, v in s.items() if not k.startswith("_")} for s in S.values()],
        matrices=[M[k] for k in sorted(M)],
        implantables=[I[k] for k in sorted(I)],
        trajectories=trajectories,
        n_trajectories=len(trajectories),
    )


def write_tsv(plan: dict, path: str | os.PathLike) -> None:
    cols = [
        "name", "reference_key", "contact_count", "contact_separation_mm", "contact_length_mm",
        "diameter_mm", "entry_x", "entry_y", "entry_z", "target_x", "target_y", "target_z",
        "length_mm", "coordinate_space", "reference_series_uid", "reference_series_name",
    ]
    cs = plan["coordinate_system"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(cols)
        for t in plan["trajectories"]:
            w.writerow(
                [t["name"], t["reference_key"], t["contact_count"], t["contact_separation_mm"],
                 t["contact_length_mm"], t["diameter_mm"], *t["entry_mm"], *t["target_mm"],
                 t["length_mm"], "LPS", cs["reference_series_uid"], cs["reference_series_name"]]
            )


def validate_against_oracle(plan: dict, oracle_path: str | os.PathLike) -> bool:
    """Compare with the JSON produced by the SQL-Server converter (dev check)."""
    o = json.load(open(oracle_path, encoding="utf-8"))
    ot = {t["name"]: t for t in o["trajectories"]}
    ok = miss = 0
    for t in plan["trajectories"]:
        r = ot.get(t["name"])
        if (
            r
            and all(abs(a - b) < 1e-3 for a, b in zip(t["target_mm"], r["target_mm"]))
            and all(abs(a - b) < 1e-3 for a, b in zip(t["entry_mm"], r["entry_mm"]))
        ):
            ok += 1
        else:
            miss += 1
            print(f"  MISMATCH/extra: {t['name']}")
    absent = [n for n in ot if n not in {t["name"] for t in plan["trajectories"]}]
    print(f"VALIDATION: {ok}/{len(ot)} oracle trajectories reproduced; extra={miss}; missing={absent}")
    ref_ok = (
        plan["coordinate_system"]["reference_series_uid"]
        == o["coordinate_system"]["reference_series_uid"]
    )
    print(f"VALIDATION: reference series UID {'matches' if ref_ok else 'DIFFERS from'} the oracle")
    return ok == len(ot) and not miss and not absent and ref_ok


def main(argv=None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Read a NeuroInspire .nip plan without SQL Server")
    ap.add_argument("nip")
    ap.add_argument("--out", help="output basename (default: next to the .nip)")
    ap.add_argument("--oracle", help="oracle JSON (from nip_to_plan.py) to validate against")
    a = ap.parse_args(argv)
    plan = read_nip(a.nip)
    base = Path(a.out) if a.out else Path(a.nip).with_suffix("")
    json.dump(plan, open(str(base) + ".plan.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    write_tsv(plan, str(base) + ".plan.tsv")
    cs = plan["coordinate_system"]
    print(
        f"{plan['n_trajectories']} trajectories, {len(plan['implantables'])} implantables, "
        f"{len(plan['series'])} series, {len(plan['matrices'])} matrices"
    )
    print(f"reference MRI: {cs['reference_series_name']}  [{cs['reference_series_uid']}]")
    for t in plan["trajectories"]:
        print(
            f"  {t['name']:6s} {str(t['reference_key']):18s} n={t['contact_count']}  "
            f"entry={t['entry_mm']}  target={t['target_mm']}  L={t['length_mm']} mm"
        )
    print(f"written: {base}.plan.json / .plan.tsv")
    if a.oracle:
        return 0 if validate_against_oracle(plan, a.oracle) else 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

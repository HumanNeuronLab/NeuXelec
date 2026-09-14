"""Synthetic SQL Server page: one live Trajectories record referenced by the slot
array and one ghost record that is NOT referenced -> only the live one is read."""
import struct

from neuxelec.utils.nip_reader import PAGE, read_backup


def _trajectory_record(tid, target, entry, imp, name):
    name_b = name.encode("utf-16-le")
    fixed = struct.pack("<HH", 0x0030, 60) + struct.pack("<i", tid) + struct.pack("<6d", *target, *entry) + struct.pack("<i", imp)
    var_end = 60 + 2 + 2 + 2 + 2 + len(name_b)   # ncols, nullbmp, nvar, varEnd, data
    tail = struct.pack("<HHHH", 9, 0, 1, var_end) + name_b
    return fixed + tail


def _page(records_live, records_ghost):
    page = bytearray(PAGE)
    page[0] = 1          # headerVersion
    page[1] = 1          # data page
    page[3] = 0          # level
    offs, cur = [], 96
    for r in records_live:
        page[cur:cur + len(r)] = r
        offs.append(cur)
        cur += len(r)
    for r in records_ghost:            # present in the page, not in the slot array
        page[cur:cur + len(r)] = r
        cur += len(r)
    struct.pack_into("<H", page, 22, len(offs))
    struct.pack_into("<H", page, 28, PAGE - cur - 2 * len(offs))
    for i, o in enumerate(offs):
        struct.pack_into("<H", page, PAGE - 2 * (i + 1), o)
    return bytes(page)


def test_slot_referenced_records_only():
    live = _trajectory_record(5, (31.6679, 2.6843, 47.7084), (58.8274, -3.9551, 48.0257), 5, "TSG")
    ghost = _trajectory_record(6, (1.0, 2.0, 3.0), (4.0, 5.0, 6.0), 6, "FOD")
    buf = b"\x00" * 4096 + _page([live], [ghost]) + b"\x00" * 4096   # page at offset 4096
    T, I, M, S = read_backup(buf)
    assert list(T) == [5]
    assert T[5]["name"] == "TSG"
    assert T[5]["target_mm"] == [31.6679, 2.6843, 47.7084]
    assert T[5]["entry_mm"] == [58.8274, -3.9551, 48.0257]
    assert T[5]["implantable_id"] == 5

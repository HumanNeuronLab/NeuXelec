#!/usr/bin/env python
"""CLI wrapper: read a NeuroInspire .nip plan without SQL Server.

The implementation lives in neuxelec.utils.nip_reader (used by the app).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from neuxelec.utils.nip_reader import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

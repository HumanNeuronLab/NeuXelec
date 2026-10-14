#!/usr/bin/env python
# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""CLI wrapper: read a NeuroInspire .nip plan without SQL Server.

The implementation lives in neuxelec.utils.nip_reader (used by the app).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from neuxelec.utils.nip_reader import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

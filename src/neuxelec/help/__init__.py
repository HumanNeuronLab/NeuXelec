# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""In-app documentation: the user guide window, the guided tour and the PDF.

Everything the user reads comes from :mod:`neuxelec.help.content`, so the
window (F1 / User guide), the guided tour shown on first launch and the PDF
manual published on the website can never drift apart.
"""

from .content import MANUAL_SECTIONS, SHORTCUTS, TOUR_STEPS

__all__ = ["MANUAL_SECTIONS", "SHORTCUTS", "TOUR_STEPS"]

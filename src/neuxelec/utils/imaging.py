# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
from PySide6.QtGui import QImage, QPixmap


def to_qpixmap(arr: np.ndarray) -> QPixmap:
    a = np.asarray(arr)

    # normalisation simple vers uint8 (si tu as déjà ta normalisation, garde-la)
    a = a.astype(np.float32, copy=False)
    lo = np.percentile(a, 1)
    hi = np.percentile(a, 99)
    if hi <= lo:
        hi = lo + 1.0
    u8 = np.clip((a - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)

    # ✅ IMPORTANT: rendre le buffer C-contiguous (transpose/rot90 cassent ça)
    u8 = np.ascontiguousarray(u8)

    h, w = u8.shape
    qimg = QImage(u8.data, w, h, w, QImage.Format_Grayscale8)
    return QPixmap.fromImage(qimg)

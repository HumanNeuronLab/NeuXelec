# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""One window to see what is saved and what is not.

The page used to carry ten Save buttons side by side, which is how a
page stops being readable. They live here now, one per line, each with a
light that says what state the output is in.

WHERE THE STATE COMES FROM

Not from a copy. Each line is backed by the real button of the page,
which the page already enables when an output is reviewed and marks as
written once the file exists. This window reads those two facts and
clicks that button: the rules about what can be saved stay in one place,
where they were, and no second truth is invented here.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .neuxelec_dialog import FIELD, FAINT, LINE, MUTED, NeuXelecDialog, TEXT

VERT = "#4ED07A"
ROSE = "#FF487D"
ORANGE = "#FFA23A"

#: (libelle, nom de l'attribut du bouton reel de la page), dans l'ordre
#: ou l'on travaille.
ROWS: tuple[tuple[str, str], ...] = (
    ("MRI 2", "btn_save_t2"),
    ("CT post-implant", "btn_save_ct"),
    ("PET", "btn_save_pet"),
    ("Ictal SPECT", "btn_save_ictal"),
    ("Interictal SPECT", "btn_save_interictal"),
    ("fMRI", "btn_save_fmri"),
    ("SISCOM", "btn_save_siscom"),
    ("Brain mask", "btn_save_brainmask"),
    ("Implantation plan", "btn_save_plan"),
)

SUPPLEMENT = f"""
QPushButton#rowSave {{
    background: {FIELD}; border: 1px solid {LINE}; border-radius: 8px;
    padding: 6px 14px; color: {TEXT}; min-width: 84px;
}}
QPushButton#rowSave:enabled {{ border: 1px solid #FF487D; }}
QPushButton#rowSave:disabled {{ color: {FAINT}; border: 1px solid {LINE}; }}
QFrame#rowsBox {{ background: {FIELD}; border: 1px solid {LINE}; border-radius: 8px; }}
"""


class SaveOutputsDialog(NeuXelecDialog):
    """Ce qui est enregistre, ce qui ne l'est pas, et un bouton par ligne."""

    def __init__(self, page, parent=None):
        super().__init__(
            "Save reviewed outputs",
            "Green: on disk. Orange: reviewed, not written yet.",
            parent=parent,
        )
        self.page = page
        self.setStyleSheet(self.styleSheet() + SUPPLEMENT)

        boite = QFrame()
        boite.setObjectName("rowsBox")
        self.grille = QGridLayout(boite)
        self.grille.setContentsMargins(14, 12, 14, 12)
        self.grille.setHorizontalSpacing(14)
        self.grille.setVerticalSpacing(9)
        self.body.addWidget(boite)

        self._lignes: list[dict] = []
        self._construire()

        pied = QHBoxLayout()
        self.btn_all = QPushButton("Save all that is not saved")
        self.btn_all.setObjectName("secondaryButton")
        self.btn_all.clicked.connect(self._save_all)
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("primaryButton")
        self.btn_close.clicked.connect(self.accept)
        pied.addWidget(self.btn_all)
        pied.addStretch(1)
        pied.addWidget(self.btn_close)
        self.body.addLayout(pied)

        self._rafraichir()
        self.setMinimumSize(460, 300)
        self.adjustSize()
        self.resize(560, self.height())

    # ------------------------------------------------------------ le contenu
    def _construire(self) -> None:
        for i, (libelle, attribut) in enumerate(ROWS):
            vrai = getattr(self.page, attribut, None)

            pastille = QLabel("●")
            pastille.setFixedWidth(16)
            nom = QLabel(libelle)
            etat = QLabel("")
            etat.setStyleSheet(f"color: {MUTED};")
            bouton = QPushButton("Save")
            bouton.setObjectName("rowSave")
            bouton.setCursor(Qt.PointingHandCursor)
            bouton.clicked.connect(lambda _c=False, b=vrai: self._cliquer(b))

            self.grille.addWidget(pastille, i, 0)
            self.grille.addWidget(nom, i, 1)
            self.grille.addWidget(etat, i, 2)
            self.grille.addWidget(bouton, i, 3)

            self._lignes.append(
                {
                    "vrai": vrai,
                    "pastille": pastille,
                    "nom": nom,
                    "etat": etat,
                    "bouton": bouton,
                }
            )

        self.grille.setColumnStretch(2, 1)

    def _etat_de(self, vrai) -> tuple[str, str, bool]:
        """(couleur, mot, bouton actif) pour une ligne."""
        if vrai is None:
            return FAINT, "nothing to save", False
        if bool(vrai.property("saved")):
            return VERT, "saved", bool(vrai.isEnabled())
        if vrai.isEnabled():
            return ORANGE, "not saved", True
        return FAINT, "nothing to save", False

    def _rafraichir(self) -> None:
        reste = 0
        for ligne in self._lignes:
            couleur, mot, actif = self._etat_de(ligne["vrai"])
            ligne["pastille"].setStyleSheet(f"color: {couleur}; font-size: 14px;")
            ligne["etat"].setText(mot)
            ligne["bouton"].setEnabled(actif)
            # Le contour rose est pose sur le bouton lui-meme: une regle
            # de la feuille du dialogue se ferait battre par celle qui
            # habille tous les QPushButton.
            # Le contour dit l'etat du fichier et non ce que le bouton
            # peut faire: rose une fois ecrit, gris tant qu'il ne l'est
            # pas. C'est ce que le contour disait deja sur la page.
            # Une feuille posee sur un widget remplace ce qu'il heritait:
            # elle doit donc redire tout l'habillage, pas seulement le bord.
            bord = ROSE if mot == "saved" else LINE
            encre = TEXT if actif else FAINT
            ligne["bouton"].setStyleSheet(
                f"background: {FIELD}; color: {encre}; border: 1px solid {bord};"
                " border-radius: 8px; padding: 6px 14px; min-width: 84px;"
            )
            ligne["nom"].setStyleSheet("" if actif or mot == "saved" else f"color: {MUTED};")
            if mot == "not saved":
                reste += 1

        self.btn_all.setEnabled(reste > 0)
        self.btn_all.setText(
            "Nothing left to save" if reste == 0 else f"Save the {reste} that are not saved"
        )

    # ---------------------------------------------------------- l'execution
    def _cliquer(self, vrai) -> None:
        """Click the page's own button, then read the new state from it."""
        if vrai is None:
            return
        try:
            vrai.click()
        finally:
            self._rafraichir()

    def _save_all(self) -> None:
        for ligne in self._lignes:
            vrai = ligne["vrai"]
            if vrai is None or not vrai.isEnabled() or bool(vrai.property("saved")):
                continue
            try:
                vrai.click()
            except Exception:
                continue
        self._rafraichir()

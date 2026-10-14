# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""La seule description des ascenseurs de NeuXelec.

POURQUOI UN SEUL ENDROIT

Il y en avait seize: dix blocs dans la feuille de style de la fenetre,
qui se recouvraient l'un l'autre, et autant de variantes recopiees dans
les fenetres filles. Trois dessins differents cohabitaient, un capsule
grise a bord rose, un degrade orange, un filet sans fleches, et le meme
projet montrait les trois selon l'endroit ou la fenetre etait trop
petite.

Le dessin retenu est celui des coupes de la page Reconstruction, que
l'on regarde du coin de l'oeil en lisant une image: une piste sombre,
une poignee capsule bordee de rose, et les deux bouts qui portent la
fleche qui agit sur eux. Il sert maintenant partout, du defilement d'une
page a la liste d'une fenetre.

COMMENT C'EST APPLIQUE

``apply_scrollbars(app)`` pose la feuille sur l'application entiere, au
demarrage. Une fenetre fille n'a donc rien a dire des ascenseurs: celle
qui en redecrirait un le ferait gagner sur celui-ci, puisque la feuille
la plus proche du widget l'emporte. Un test tient cette regle.
"""

from __future__ import annotations

SCROLLBARS_QSS = """
/* L'ascenseur: une piste sombre, et deux bouts de 18 px pour les
   fleches. La poignee est une capsule bordee de rose. */
QScrollBar:vertical {
    background-color: #11131B;
    border: 1px solid #232630;
    border-radius: 8px;
    width: 16px;
    margin: 0px;
    padding: 18px 0px 18px 0px;
}
QScrollBar:horizontal {
    background-color: #11131B;
    border: 1px solid #232630;
    border-radius: 8px;
    height: 16px;
    margin: 0px;
    padding: 0px 18px 0px 18px;
}

QScrollBar::handle:vertical {
    min-height: 30px;
    margin: 0px 1px;
    background-color: #3B3E48;
    border: 1px solid #FF487D;
    border-radius: 7px;
}
QScrollBar::handle:horizontal {
    min-width: 30px;
    margin: 1px 0px;
    background-color: #3B3E48;
    border: 1px solid #FF487D;
    border-radius: 7px;
}
QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {
    background-color: #4A4D58;
    border: 1px solid #FF6B98;
}

/* Les deux bouts. Ils portent la fleche, s'eclairent au survol et
   passent au rose quand on appuie. */
QScrollBar::sub-line:vertical {
    subcontrol-origin: margin;
    subcontrol-position: top;
    width: 16px;
    height: 18px;
    background-color: #181A22;
    border: 1px solid #232630;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border-bottom: none;
}
QScrollBar::add-line:vertical {
    subcontrol-origin: margin;
    subcontrol-position: bottom;
    width: 16px;
    height: 18px;
    background-color: #181A22;
    border: 1px solid #232630;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
    border-top: none;
}
QScrollBar::sub-line:horizontal {
    subcontrol-origin: margin;
    subcontrol-position: left;
    width: 18px;
    height: 16px;
    background-color: #181A22;
    border: 1px solid #232630;
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
    border-right: none;
}
QScrollBar::add-line:horizontal {
    subcontrol-origin: margin;
    subcontrol-position: right;
    width: 18px;
    height: 16px;
    background-color: #181A22;
    border: 1px solid #232630;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-left: none;
}
QScrollBar::sub-line:vertical:hover,
QScrollBar::add-line:vertical:hover,
QScrollBar::sub-line:horizontal:hover,
QScrollBar::add-line:horizontal:hover {
    background-color: #24262F;
    border: 1px solid #FF487D;
}
QScrollBar::sub-line:vertical:pressed,
QScrollBar::add-line:vertical:pressed,
QScrollBar::sub-line:horizontal:pressed,
QScrollBar::add-line:horizontal:pressed {
    background-color: #FF487D;
}

QScrollBar::up-arrow:vertical {
    image: url(resources/images/spin_up.svg);
    width: 10px;
    height: 7px;
}
QScrollBar::down-arrow:vertical {
    image: url(resources/images/spin_down.svg);
    width: 10px;
    height: 7px;
}
QScrollBar::left-arrow:horizontal {
    image: url(resources/images/spin_left.svg);
    width: 7px;
    height: 10px;
}
QScrollBar::right-arrow:horizontal {
    image: url(resources/images/spin_right.svg);
    width: 7px;
    height: 10px;
}

QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
    border: none;
}

/* Le carre entre les deux ascenseurs, qui restait gris clair. */
QAbstractScrollArea::corner {
    background: transparent;
    border: none;
}
"""


def apply_scrollbars(app) -> None:
    """Poser le dessin des ascenseurs sur toute l'application.

    La feuille de l'application est la plus eloignee des widgets: tout
    ce que la fenetre ou une fenetre fille declare la recouvre. C'est
    voulu, et c'est pourquoi plus personne d'autre ne declare
    d'ascenseur.
    """
    feuille = app.styleSheet() or ""
    if SCROLLBARS_QSS.strip() in feuille:
        return
    app.setStyleSheet((feuille + "\n" + SCROLLBARS_QSS) if feuille else SCROLLBARS_QSS)

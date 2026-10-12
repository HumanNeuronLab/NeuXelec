"""Emprunter une carte a un onglet, puis la rendre exactement a sa place.

POURQUOI EMPRUNTER PLUTOT QUE COPIER

Les cases des coupes et les curseurs d'opacite pilotent deja le mode MNI
quand il est actif : ce sont les bons controles, au mauvais endroit. En
poser des copies dans l'onglet MNI creerait deux objets pour un seul etat,
et plusieurs endroits du code cochent ces cases signaux bloques : la copie
ne l'apprendrait jamais et finirait par afficher le contraire de la
verite. Un widget Qt ne pouvant etre qu'a un seul endroit, on le deplace.

CE QU'IL FAUT RETENIR POUR LE RENDRE

Pas seulement sa disposition d'origine : sa place dedans. Une carte rendue
a la fin d'une grille au lieu de sa case changerait silencieusement la
mise en page de l'onglet d'ou elle vient. On retient donc l'index pour une
disposition lineaire, et la ligne, la colonne et les etalements pour une
grille.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtWidgets import QGridLayout, QLayout, QWidget

logger = logging.getLogger(__name__)


@dataclass
class _Place:
    """D'ou vient une carte, assez precisement pour l'y remettre."""

    layout: QLayout
    index: int
    grid: tuple[int, int, int, int] | None = None


class CardBorrower:
    """Deplacer des cartes vers un hote, et savoir toutes les rendre."""

    def __init__(self):
        self._places: dict[int, _Place] = {}
        self._order: list[QWidget] = []
        self._hosts: list[QLayout] = []

    # ------------------------------------------------------------------
    # Emprunt
    # ------------------------------------------------------------------

    @staticmethod
    def _locate(widget: QWidget) -> _Place | None:
        """La disposition qui tient ce widget, et sa place dedans."""
        parent = widget.parentWidget()
        while parent is not None:
            layout = parent.layout()
            place = CardBorrower._locate_in(layout, widget)
            if place is not None:
                return place
            parent = parent.parentWidget()
        return None

    @staticmethod
    def _locate_in(layout: QLayout | None, widget: QWidget) -> _Place | None:
        if layout is None:
            return None
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is None:
                continue
            if item.widget() is widget:
                if isinstance(layout, QGridLayout):
                    return _Place(layout, i, tuple(layout.getItemPosition(i)))
                return _Place(layout, i)
            trouve = CardBorrower._locate_in(item.layout(), widget)
            if trouve is not None:
                return trouve
        return None

    def borrow(self, widget: QWidget, host: QLayout) -> bool:
        """Deplacer ``widget`` dans ``host``, en retenant d'ou il vient.

        Rend ``False`` sans rien changer quand la carte est introuvable :
        un onglet incomplet reste utilisable, une exception non.
        """
        if widget is None or host is None:
            return False
        if id(widget) in self._places:
            return True

        place = self._locate(widget)
        if place is None:
            logger.warning("Could not locate %s to borrow it", widget.objectName())
            return False

        self._places[id(widget)] = place
        self._order.append(widget)
        place.layout.removeWidget(widget)
        host.addWidget(widget)
        widget.setVisible(True)
        if host not in self._hosts:
            self._hosts.append(host)
        return True

    # ------------------------------------------------------------------
    # Restitution
    # ------------------------------------------------------------------

    def return_all(self) -> None:
        """Tout rendre, dans l'ordre inverse de l'emprunt.

        L'ordre inverse parce qu'une disposition lineaire se renumerote :
        rendre d'abord la derniere prise laisse les index des precedentes
        valables.
        """
        for widget in reversed(self._order):
            place = self._places.pop(id(widget), None)
            if place is None:
                continue
            try:
                hote = widget.parentWidget()
                if hote is not None and hote.layout() is not None:
                    hote.layout().removeWidget(widget)
                if place.grid is not None and isinstance(place.layout, QGridLayout):
                    ligne, colonne, etal_l, etal_c = place.grid
                    place.layout.addWidget(widget, ligne, colonne, etal_l, etal_c)
                else:
                    place.layout.insertWidget(
                        min(place.index, place.layout.count()), widget
                    )
                widget.setVisible(True)
            except Exception:
                logger.exception("Could not return %s", widget.objectName())
        self._order = []
        self._places = {}

        # Rendre aussi sa taille a l'hote vide : sans cela il continue de
        # reclamer celle qu'il avait plein, et le panneau de commande
        # garde la hauteur de l'onglet qu'on vient de quitter.
        for host in self._hosts:
            self._invalidate(host)
        self._hosts = []

    #: Niveaux remontes au plus. La page 3D en compte sept entre une carte
    #: et la fenetre ; le reste est de la marge, et la borne evite de
    #: tourner si l'arbre se referme sur lui-meme.
    _MAX_LEVELS = 20

    @staticmethod
    def _invalidate(layout: QLayout | None) -> None:
        """Oublier la taille mise en cache, jusqu'a la racine.

        Une disposition seule ne suffit pas : ses parentes gardent la
        leur, et c'est la plus haute qui decide.

        La remontee s'arrete en silence sur une enveloppe Qt que Python ne
        detient plus. Ce n'est pas une panne : PySide en fabrique a la
        volee, et en croiser une signifie seulement qu'on est arrive en
        haut de ce qu'on peut atteindre.
        """
        for _ in range(CardBorrower._MAX_LEVELS):
            if layout is None:
                return
            try:
                layout.invalidate()
                widget = layout.parentWidget()
                if widget is None:
                    return
                widget.updateGeometry()
                parent = widget.parentWidget()
                layout = parent.layout() if parent is not None else None
            except RuntimeError:
                return

    @property
    def borrowed(self) -> list[QWidget]:
        return list(self._order)

    def is_borrowing(self) -> bool:
        return bool(self._order)

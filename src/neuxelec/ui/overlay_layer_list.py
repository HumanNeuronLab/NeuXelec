"""La colonne des calques de l'onglet Overlay.

La vue 3D et la coupe oblique ont le meme probleme et la meme solution :
une ligne par calque, et la carte du seul calque choisi. Les deux pages
partagent donc cette classe, chacune lui passant ses noms de widgets.
Dupliquer la colonne aurait laisse deux comportements a corriger
separement la prochaine fois.

POURQUOI UNE COLONNE PLUTOT QU'UNE PILE DE CARTES

Les sept cartes de calques demandent 1239 px de hauteur pour 279 px
disponibles. Empilées, on en voit un cinquième, et changer un paramètre
oblige à faire défiler jusqu'à lui. Une ligne par calque tient en 200 px,
et la carte du seul calque choisi occupe le reste.

POURQUOI DEPLACER LES CASES AU LIEU D'EN CREER

La case qui montre un calque existe déjà, dans sa carte. En poser une
copie dans la ligne ferait deux objets pour un seul état, et plusieurs
endroits du code cochent ces cases **signaux bloqués** pour éviter des
rendus en cascade : la copie ne l'apprendrait jamais et finirait par
afficher le contraire de la vérité. La ligne reçoit donc la case
elle-même, reparentée. Il n'y a jamais qu'un objet, donc rien à
synchroniser.

POURQUOI LE NOM EST UN BOUTON A PART

Cliquer le texte d'une case Qt la coche. Si le nom était le texte de la
case, on ne pourrait pas consulter les réglages d'un calque sans
l'allumer. La case garde donc son seul indicateur, et le nom devient un
bouton qui, lui, ne fait que choisir.

POURQUOI GRISER D'APRES LA CASE ET NON D'APRES L'ETAT

NeuXelec sait déjà activer ou désactiver ces cases selon que la
coregistration est validée, le mode MNI actif, le volume chargé. Relire
ces conditions ici en ferait une seconde version, qui dériverait. La
ligne suit donc ``isEnabled()`` de sa propre case, et se rafraîchit sur
l'évènement que Qt émet quand il change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayerRow:
    """Un calque, tel que la colonne le présente.

    ``checkbox`` et ``card`` sont des noms d'objet du .ui. ``card_label``
    est le texte à laisser dans la carte à la place de la case partie,
    pour les cartes qui n'ont pas d'autre titre pour ce bloc.
    """

    key: str
    label: str
    checkbox: str
    card: str
    card_label: str | None = None


#: L'ordre des anciennes cartes, de l'anatomie vers le fonctionnel.
#: La vue 3D.
LAYERS = (
    LayerRow("mri1", "MRI 1", "checkBox_3dView_T1", "card3DMRI"),
    LayerRow("mri2", "MRI 2", "checkBox_3dView_T2", "card3DMRI"),
    LayerRow("ct", "CT", "chk_3d_showCT", "card3DCT"),
    LayerRow("pet", "PET", "chk_3d_showPET", "card3DPET"),
    LayerRow("siscom", "SISCOM", "chk_3d_showSISCOM", "card3DSISCOM"),
    LayerRow("fmri", "fMRI", "chk_3d_showfMRI", "card3DfMRI"),
    # La carte SPECT porte deux blocs que seules leurs cases nommaient :
    # elles laissent une etiquette derriere elles.
    LayerRow("ictal", "Ictal SPECT", "chk_3d_showPET_ictal", "card3DSPECT", "Ictal SPECT"),
    LayerRow(
        "interictal",
        "Inter-ictal SPECT",
        "chk_3d_showPET_interictal",
        "card3DSPECT",
        "Inter-ictal SPECT",
    ),
)


#: La coupe oblique, dans le meme ordre pour qu'on ne cherche pas deux
#: fois au meme endroit. Ses cartes CT et MRI viennent d'une seule carte
#: ANATOMICAL IMAGE, scindee pour qu'un calque montre ses reglages seuls.
LAYERS_OBLIQUE = (
    LayerRow("mri1", "MRI 1", "checkBox_ObliqueSlice_T1", "cardObliqueMRI"),
    LayerRow("mri2", "MRI 2", "checkBox_ObliqueSlice_T2", "cardObliqueMRI"),
    LayerRow("ct", "CT", "chk_obliqueSlice_CT", "cardObliqueCT"),
    LayerRow("pet", "PET", "chk_obliqueSlice_PET", "cardObliquePET"),
    LayerRow("siscom", "SISCOM", "chk_obliqueSlice_SISCOM", "cardObliqueSISCOM"),
    LayerRow("fmri", "fMRI", "chk_obliqueSlice_fMRI", "cardObliquefMRI"),
    LayerRow(
        "ictal",
        "Ictal SPECT",
        "chk_obliqueSlice_PET_ictal",
        "cardObliqueSPECT",
        "Ictal SPECT",
    ),
    LayerRow(
        "interictal",
        "Inter-ictal SPECT",
        "chk_obliqueSlice_PET_interictal",
        "cardObliqueSPECT",
        "Inter-ictal SPECT",
    ),
)


@dataclass(frozen=True)
class ToggleRow:
    """Une case posée sous les calques, qui n'ouvre aucune carte.

    Les micro-tétrodes ne sont pas un calque : il n'y a rien à régler,
    seulement à montrer ou non. La ligne garde donc le texte de la case
    au lieu du bouton des calques, et cliquer le nom coche, ce qui est
    ici le geste voulu. Un bouton qui ne ferait apparaître aucune carte
    laisserait croire qu'une carte manque.

    ``empty_card`` est la carte que la case laisse vide en partant, à
    cacher : un cadre vide garderait ses marges et une ligne de vide.
    """

    key: str
    label: str
    checkbox: str
    empty_card: str | None = None


#: La coupe oblique : la case des micro-tetrodes tenait seule la carte
#: DISPLAY, dont le reglage de taille des contacts a ete retire.
TOGGLES_OBLIQUE = (
    ToggleRow(
        "micro_tetrodes",
        "Micro tetrodes",
        "checkBox_obliqueSlice_microTetrodes",
        "cardObliqueDisplay",
    ),
)

_STYLE = """
QFrame#%(frame)s {
    background-color: #11131B;
    border: 1px solid #252834;
    border-radius: 11px;
}
QPushButton#layerNameButton {
    /* Lisible au repos. A #9599AA, une colonne de noms pourtant
       disponibles avait l'air eteinte, et ne se distinguait plus des
       lignes reellement grisees. */
    color: #D8DAE4;
    background-color: transparent;
    border: none;
    border-radius: 7px;
    min-height: 20px;
    padding: 1px 6px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
}
QPushButton#layerNameButton:hover:enabled {
    color: #F2F2F5;
    background-color: #181A24;
}
QPushButton#layerNameButton:checked {
    color: white;
    background-color: #41434A;
}
QPushButton#layerNameButton:disabled {
    color: #4B4E5A;
}
QCheckBox#layerToggle {
    color: #D8DAE4;
    font-size: 12px;
    font-weight: 600;
    /* 4 px d'ecart dans la ligne d'un calque, plus 6 px de marge du
       bouton : le nom d'une bascule tombe ainsi sur ceux du dessus. */
    spacing: 10px;
}
QCheckBox#layerToggle:disabled {
    color: #4B4E5A;
}
QFrame#layerListSeparator {
    background-color: #252834;
    max-height: 1px;
    border: none;
}
QLabel#layerListTitle {
    color: #7E8294;
    font-size: 11px;
    font-weight: 600;
}
"""


class _EnabledWatcher(QObject):
    """Prévenir quand une case devient activable, ou cesse de l'être."""

    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.EnabledChange:
            try:
                self._on_change()
            except Exception:
                logger.exception("Could not refresh the overlay layer list")
        return False


class OverlayLayerList:
    """Bâtir la colonne et n'afficher que la carte du calque choisi."""

    def __init__(
        self,
        ui,
        on_selected=None,
        layers=LAYERS,
        frame_name="card3DLayerList",
        toggles=(),
    ):
        self.ui = ui
        self._on_selected = on_selected
        self._layers = tuple(layers)
        self._frame_name = str(frame_name)
        self._toggle_rows = tuple(toggles)
        self._toggles: dict[str, QCheckBox] = {}
        self._buttons: dict[str, QPushButton] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        self._cards: dict[str, QFrame] = {}
        self._group: QButtonGroup | None = None
        self._watcher: _EnabledWatcher | None = None
        self._current: str | None = None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build(self) -> bool:
        """Rendre ``False`` si le cadre n'est pas là, sans rien casser."""
        frame = self.ui.findChild(QFrame, self._frame_name)
        if frame is None:
            return False

        layout = frame.layout()
        if layout is None:
            layout = QVBoxLayout(frame)
        frame.setStyleSheet(_STYLE % {"frame": self._frame_name})

        titre = QLabel("CALQUES")
        titre.setObjectName("layerListTitle")
        layout.addWidget(titre)
        layout.setSpacing(1)
        layout.setContentsMargins(8, 6, 8, 6)

        self._group = QButtonGroup(frame)
        self._group.setExclusive(True)
        self._watcher = _EnabledWatcher(self.refresh, frame)

        for layer in self._layers:
            case = self.ui.findChild(QCheckBox, layer.checkbox)
            carte = self.ui.findChild(QFrame, layer.card)
            if case is None or carte is None:
                logger.warning("Overlay layer %s has no widget, skipped", layer.key)
                continue

            self._cards.setdefault(layer.card, carte)
            self._checkboxes[layer.key] = case
            layout.addWidget(self._make_row(frame, layer, case, carte))

        self._build_toggles(frame, layout)
        layout.addStretch(1)

        if self._buttons:
            premier = next(iter(self._buttons))
            self.select(premier)
        self.refresh()
        return True

    def _build_toggles(self, frame: QWidget, layout) -> None:
        """Poser les bascules sous les calques, derrière un filet.

        Sous, et non parmi : elles n'ouvrent pas de carte, et les mêler
        aux calques ferait attendre des réglages qui ne viendraient pas.
        """
        posees = 0
        for bascule in self._toggle_rows:
            case = self.ui.findChild(QCheckBox, bascule.checkbox)
            if case is None:
                logger.warning("Toggle %s has no checkbox, skipped", bascule.key)
                continue

            if posees == 0:
                filet = QFrame(frame)
                filet.setObjectName("layerListSeparator")
                filet.setFrameShape(QFrame.HLine)
                layout.addSpacing(6)
                layout.addWidget(filet)
                layout.addSpacing(2)

            case.setParent(frame)
            case.setObjectName("layerToggle")
            case.setText(bascule.label)
            case.setVisible(True)
            layout.addWidget(case)
            self._toggles[bascule.key] = case
            posees += 1

            # La carte que la case laisse vide garderait ses marges.
            if bascule.empty_card:
                carte = self.ui.findChild(QFrame, bascule.empty_card)
                if carte is not None:
                    carte.setVisible(False)

    def toggles(self) -> dict:
        """Les bascules posées, par clé. Pour les tests et l'appelant."""
        return dict(self._toggles)

    def _make_row(
        self, parent: QWidget, layer: LayerRow, case: QCheckBox, card: QFrame
    ) -> QWidget:
        self._leave_label_behind(layer, case, card)

        case.setText("")
        case.setToolTip(layer.label)

        bouton = QPushButton(layer.label)
        bouton.setObjectName("layerNameButton")
        bouton.setCheckable(True)
        bouton.setCursor(Qt.PointingHandCursor)
        bouton.clicked.connect(lambda _=False, k=layer.key: self.select(k))
        self._buttons[layer.key] = bouton
        if self._group is not None:
            self._group.addButton(bouton)
        if self._watcher is not None:
            case.installEventFilter(self._watcher)

        ligne = QWidget(parent)
        boite = QHBoxLayout(ligne)
        boite.setContentsMargins(0, 0, 0, 0)
        boite.setSpacing(4)
        boite.addWidget(case)
        boite.addWidget(bouton, 1)
        return ligne

    @staticmethod
    def _owning_layout(root, widget):
        """La disposition qui contient vraiment ce widget, et son rang.

        ``parentWidget().layout()`` ne suffit pas : une disposition
        imbriquée ne reparente rien, donc la case a pour parent le cadre
        de la carte alors qu'elle est posée trois niveaux plus bas.
        """
        if root is None:
            return None, -1
        for i in range(root.count()):
            item = root.itemAt(i)
            if item is None:
                continue
            if item.widget() is widget:
                return root, i
            trouve, rang = OverlayLayerList._owning_layout(item.layout(), widget)
            if trouve is not None:
                return trouve, rang
        return None, -1

    @staticmethod
    def _leave_label_behind(layer: LayerRow, case: QCheckBox, card) -> None:
        """Poser une étiquette là où la case s'en va, quand elle nommait seule.

        La carte SPECT tient deux blocs que rien d'autre ne distinguait.
        Sans cela, on y verrait deux séries de réglages identiques.
        """
        if not layer.card_label:
            return
        layout, index = OverlayLayerList._owning_layout(
            card.layout() if card is not None else None, case
        )
        if layout is None or index < 0:
            logger.warning("Could not label the %s block left behind", layer.key)
            return
        etiquette = QLabel(layer.card_label)
        etiquette.setObjectName(f"layerCardLabel_{layer.key}")
        layout.insertWidget(index, etiquette)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select(self, key: str) -> None:
        """Montrer la carte de ce calque, et elle seule."""
        if key not in self._buttons:
            return
        self._current = key

        bouton = self._buttons[key]
        if not bouton.isChecked():
            bouton.setChecked(True)

        voulue = next((layer.card for layer in self._layers if layer.key == key), None)
        for nom, carte in self._cards.items():
            carte.setVisible(nom == voulue)

        if self._on_selected is not None:
            try:
                self._on_selected(key)
            except Exception:
                logger.exception("Could not announce the overlay layer change")

    def current(self) -> str | None:
        return self._current

    # ------------------------------------------------------------------
    # Etat
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Griser les calques dont la case n'est pas activable.

        Grisé plutôt que caché : une ligne qui disparaît ne dit pas
        pourquoi, alors qu'une ligne grise montre que le calque existe et
        qu'il attend sa coregistration.
        """
        for key, bouton in self._buttons.items():
            case = self._checkboxes.get(key)
            if case is None:
                continue
            activable = bool(case.isEnabled())
            bouton.setEnabled(activable)
            bouton.setToolTip(
                "" if activable else "Not available yet: coregister and validate it first."
            )

"""La colonne des calques de l'onglet Overlay, en vue 3D.

Ce qui doit tenir, et que seule une interface reellement chargee peut
dire :

  - chaque calque declare pointe sur des widgets qui existent vraiment ;
  - une seule carte est visible a la fois, c'est tout l'interet ;
  - la case d'un calque est **celle de sa carte**, deplacee, et non une
    copie. Plusieurs endroits du code cochent ces cases signaux bloques :
    une copie finirait par afficher le contraire de la verite ;
  - le grise suit isEnabled de la case, et non une relecture de l'etat ;
  - la carte SPECT garde de quoi distinguer ses deux blocs, que seules
    leurs cases nommaient.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QFile  # noqa: E402
from PySide6.QtUiTools import QUiLoader  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QFrame,
    QLabel,
    QPushButton,
)

from neuxelec.ui.overlay_layer_list import LAYERS, OverlayLayerList  # noqa: E402
from neuxelec.utils.resources import resource_path  # noqa: E402

CARTES = (
    "card3DMRI",
    "card3DCT",
    "card3DPET",
    "card3DSISCOM",
    "card3DfMRI",
    "card3DSPECT",
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _charger(app):
    f = QFile(str(resource_path("resources/ui/MainWindow.ui")))
    assert f.open(QFile.ReadOnly), "MainWindow.ui illisible"
    try:
        w = QUiLoader().load(f)
    finally:
        f.close()
    assert w is not None, "MainWindow.ui ne se charge pas"
    return w


@pytest.fixture
def brut(app):
    """L'interface telle qu'elle sort du fichier, colonne non montee."""
    return _charger(app)


@pytest.fixture
def monte(app):
    """L'interface avec la colonne batie, comme la page 3D la monte.

    Le panneau des regions est monte lui aussi : c'est lui qui fixe la
    hauteur du panneau de commande, et sans lui on mesurerait une
    configuration qui n'existe nulle part.
    """
    from neuxelec.ui.parcellation_region_panel import ParcellationRegionPanel

    w = _charger(app)
    liste = OverlayLayerList(w)
    assert liste.build(), "la colonne ne s'est pas construite"
    assert ParcellationRegionPanel(w).build()
    return w, liste


def test_chaque_calque_declare_pointe_sur_des_widgets_reels(brut):
    """Une faute de frappe dans un nom ferait disparaitre la ligne en silence."""
    for layer in LAYERS:
        assert brut.findChild(QCheckBox, layer.checkbox) is not None, layer.checkbox
        assert brut.findChild(QFrame, layer.card) is not None, layer.card


def test_les_huit_calques_ont_leur_ligne(monte):
    _, liste = monte
    assert sorted(liste._buttons) == sorted(layer.key for layer in LAYERS)


@pytest.mark.parametrize("cle,carte", [(layer.key, layer.card) for layer in LAYERS])
def test_une_seule_carte_visible_a_la_fois(monte, cle, carte):
    w, liste = monte
    liste.select(cle)
    visibles = [n for n in CARTES if not w.findChild(QFrame, n).isHidden()]
    assert visibles == [carte]


def test_la_case_est_celle_de_la_carte_et_non_une_copie(monte, brut):
    """Le piege : deux objets pour un seul etat, et la copie qui ment."""
    w, _ = monte
    for layer in LAYERS:
        cases = [c for c in w.findChildren(QCheckBox) if c.objectName() == layer.checkbox]
        assert len(cases) == 1, f"{layer.checkbox} existe en {len(cases)} exemplaires"


def test_la_case_a_quitte_sa_carte_pour_la_ligne(monte, brut):
    """Avant, elle est dans la carte ; apres, elle n'y est plus."""
    carte_avant = brut.findChild(QFrame, "card3DPET")
    assert any(
        c.objectName() == "chk_3d_showPET" for c in carte_avant.findChildren(QCheckBox)
    )

    w, _ = monte
    carte_apres = w.findChild(QFrame, "card3DPET")
    assert not any(
        c.objectName() == "chk_3d_showPET" for c in carte_apres.findChildren(QCheckBox)
    )
    colonne = w.findChild(QFrame, "card3DLayerList")
    assert any(c.objectName() == "chk_3d_showPET" for c in colonne.findChildren(QCheckBox))


def test_le_nom_est_un_bouton_a_part_et_la_case_n_a_plus_de_texte(monte):
    """Sinon cliquer le nom cocherait la case, et on ne pourrait pas
    consulter les reglages d'un calque sans l'allumer."""
    w, liste = monte
    for layer in LAYERS:
        case = w.findChild(QCheckBox, layer.checkbox)
        assert case.text() == "", layer.key
        assert case.toolTip() == layer.label
        assert liste._buttons[layer.key].text() == layer.label


def test_le_grise_suit_la_case_et_rien_d_autre(monte):
    w, liste = monte
    case = w.findChild(QCheckBox, "chk_3d_showSISCOM")
    bouton = liste._buttons["siscom"]

    case.setEnabled(False)
    assert not bouton.isEnabled()
    assert "coregister" in bouton.toolTip().lower()

    case.setEnabled(True)
    assert bouton.isEnabled()
    assert bouton.toolTip() == ""


def test_cocher_une_case_n_est_pas_perturbe_par_la_colonne(monte):
    """Le cas qui a mordu ailleurs : du code qui coche signaux bloques."""
    w, _ = monte
    case = w.findChild(QCheckBox, "chk_3d_showPET")
    case.blockSignals(True)
    case.setChecked(True)
    case.blockSignals(False)
    assert case.isChecked()
    # Une seule case existe, donc rien ne peut diverger.
    assert len([c for c in w.findChildren(QCheckBox) if c.objectName() == "chk_3d_showPET"]) == 1


def test_la_carte_spect_distingue_toujours_ses_deux_blocs(monte):
    """Ses deux cases la nommaient : parties, il reste des etiquettes."""
    w, _ = monte
    carte = w.findChild(QFrame, "card3DSPECT")
    textes = [lbl.text() for lbl in carte.findChildren(QLabel)]
    assert "Ictal SPECT" in textes
    assert "Inter-ictal SPECT" in textes


def test_un_seul_nom_selectionne_a_la_fois(monte):
    w, liste = monte
    liste.select("pet")
    liste.select("fmri")
    coches = [k for k, b in liste._buttons.items() if b.isChecked()]
    assert coches == ["fmri"]


def test_sans_le_cadre_la_colonne_renonce_sans_lever(app):
    """Une interface sans ce cadre doit rester utilisable."""

    class _Vide:
        def findChild(self, *_a, **_k):
            return None

    assert OverlayLayerList(_Vide()).build() is False


def test_les_boutons_de_nom_portent_le_meme_nom_d_objet(monte):
    """La feuille de style les vise par la, donc ils doivent tous l'avoir."""
    _, liste = monte
    for bouton in liste._buttons.values():
        assert bouton.objectName() == "layerNameButton"
        assert isinstance(bouton, QPushButton)


def test_le_calque_choisi_tient_sans_defilement(app, monte):
    """Tout l'interet de la colonne : plus rien a faire defiler.

    Mesure sur une fenetre de 1920 x 1080, la taille ou NeuXelec est
    utilise. En dessous il reste quelques pixels sur la carte SPECT, qui
    porte deux calques cote a cote.
    """
    from PySide6.QtWidgets import QScrollArea, QStackedWidget, QTabWidget

    w, liste = monte
    pile = w.findChild(QStackedWidget, "stackedWidget")
    for i in range(pile.count()):
        if pile.widget(i).objectName() == "page3DView":
            pile.setCurrentIndex(i)
    w.resize(1920, 1080)
    w.show()
    onglets = w.findChild(QTabWidget, "tabWidget3D")
    onglets.setCurrentIndex(1)
    for _ in range(6):
        QApplication.processEvents()

    zone = w.findChild(QScrollArea, "scrollArea_5")
    debordements = {}
    for layer in LAYERS:
        liste.select(layer.key)
        for _ in range(4):
            QApplication.processEvents()
        reste = (zone.verticalScrollBar().maximum(), zone.horizontalScrollBar().maximum())
        if reste != (0, 0):
            debordements[layer.key] = reste
    w.hide()
    assert debordements == {}, debordements


def test_les_quatre_onglets_sont_la(monte):
    from PySide6.QtWidgets import QTabWidget

    w, _ = monte
    onglets = w.findChild(QTabWidget, "tabWidget3D")
    assert [onglets.tabText(i) for i in range(onglets.count())] == [
        "Brain",
        "Overlay",
        "Parcellation",
        "MNI",
    ]


def test_la_parcellation_a_quitte_la_pile_des_calques(monte):
    """Elle a son onglet, ou se greffera le trace de regions choisies."""
    from PySide6.QtWidgets import QTabWidget

    w, _ = monte
    onglets = w.findChild(QTabWidget, "tabWidget3D")
    page = onglets.widget(2)
    assert page.findChild(QFrame, "card3DParcellation") is not None
    assert onglets.widget(1).findChild(QFrame, "card3DParcellation") is None


def test_un_calque_disponible_ne_ressemble_pas_a_un_calque_grise(monte):
    """Le defaut signale : au repos les noms etaient si ternes qu'une
    colonne entiere de calques disponibles passait pour eteinte."""
    w, liste = monte
    colonne = w.findChild(QFrame, "card3DLayerList")
    colonne.show()

    def couleurs(cle, activable):
        w.findChild(QCheckBox, next(x.checkbox for x in LAYERS if x.key == cle)).setEnabled(
            activable
        )
        for _ in range(3):
            QApplication.processEvents()
        bouton = liste._buttons[cle]
        bouton.ensurePolished()
        image = bouton.grab().toImage()
        return {
            tuple(image.pixelColor(x, y).getRgb()[:3])
            for y in range(image.height())
            for x in range(image.width())
        }

    # Comparer sur un calque jamais selectionne, pour ne pas mesurer le
    # fond de la ligne choisie.
    liste.select("mri1")
    disponible = couleurs("siscom", True)
    grise = couleurs("siscom", False)
    w.hide()

    assert disponible != grise, "disponible et grise se ressemblent trop"
    # Le texte disponible doit etre franchement plus clair.
    plus_clair = max(sum(c) for c in disponible)
    assert plus_clair > 3 * 180, "les noms disponibles restent trop ternes"

"""Le panneau des regions de l'onglet Parcellation.

Ce qui doit tenir :

  - toutes les regions cochees au depart, puisqu'on part du cerveau
    entier et qu'on en retire ;
  - le bouton unique dit lequel des deux gestes il fera, et ne touche
    qu'aux lignes visibles : filtrer puis tout decocher doit decocher ce
    qu'on regarde, pas les quatre cents autres ;
  - le filtre cache sans decocher, sinon filtrer changerait le dessin ;
  - changer de parcellation refait la table, les numeros d'etiquette du 1
    ne designant pas les memes regions que ceux du 2.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget  # noqa: E402

from neuxelec.ui.parcellation_region_panel import (  # noqa: E402
    COL_CONTACTS,
    COL_REGION,
    ParcellationRegionPanel,
)
from neuxelec.utils.parcellation_regions import Region  # noqa: E402

REGIONS = [
    Region(3, "ctx-lh-superiortemporal", (140, 20, 20), ("TB1", "TB2")),
    Region(4, "ctx-lh-middletemporal", (60, 20, 220), ("TB3",)),
    Region(5, "ctx-rh-precentral", (60, 220, 60), ()),
    Region(6, "Left-Hippocampus", (220, 20, 100), ("HP1",)),
]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Hote(QWidget):
    """Un hote minimal qui porte le cadre attendu."""

    def __init__(self):
        super().__init__()
        cadre = QFrame(self)
        cadre.setObjectName("card3DRegions")
        QVBoxLayout(cadre)


@pytest.fixture
def panneau(app):
    hote = _Hote()
    traces = {"plot": [], "regions": []}
    p = ParcellationRegionPanel(
        hote,
        on_plot_toggled=traces["plot"].append,
        on_regions_changed=lambda s: traces["regions"].append(set(s)),
    )
    assert p.build(), "le panneau ne s'est pas construit"
    p.set_regions(REGIONS)
    return p, traces, hote


def _visibles(p):
    return [
        p.table.item(i, COL_REGION).text()
        for i in range(p.table.rowCount())
        if not p.table.isRowHidden(i)
    ]


def _coches(p):
    return {
        p.table.item(i, COL_REGION).text()
        for i in range(p.table.rowCount())
        if p.table.item(i, COL_REGION).checkState() == Qt.Checked
    }


# ------------------------------------------------------------- le tableau


def test_tout_est_coche_au_depart(panneau):
    p, _, _ = panneau
    assert p.checked_labels() == {3, 4, 5, 6}
    assert len(_coches(p)) == 4


def test_chaque_region_montre_ses_contacts(panneau):
    p, _, _ = panneau
    par_nom = {
        p.table.item(i, COL_REGION).text(): p.table.item(i, COL_CONTACTS).text()
        for i in range(p.table.rowCount())
    }
    assert par_nom["ctx-lh-superiortemporal"] == "TB1 TB2"
    assert par_nom["Left-Hippocampus"] == "HP1"
    assert par_nom["ctx-rh-precentral"] == "-"


def test_decocher_une_region_la_retire_de_la_selection(panneau):
    p, traces, _ = panneau
    ligne = next(
        i
        for i in range(p.table.rowCount())
        if p.table.item(i, COL_REGION).text() == "ctx-rh-precentral"
    )
    p.table.item(ligne, COL_REGION).setCheckState(Qt.Unchecked)
    assert p.checked_labels() == {3, 4, 6}
    assert traces["regions"][-1] == {3, 4, 6}


def test_changer_de_parcellation_refait_la_table(panneau):
    """Les etiquettes du 1 ne designent pas les regions du 2."""
    p, _, _ = panneau
    p.table.item(0, COL_REGION).setCheckState(Qt.Unchecked)
    p.set_regions([Region(77, "autre-atlas", (1, 2, 3), ())])
    assert p.table.rowCount() == 1
    assert p.checked_labels() == {77}


# ------------------------------------------------------------- le bouton


def test_le_bouton_dit_ce_qu_il_va_faire(panneau):
    p, _, _ = panneau
    assert p.btn_toggle_all.text() == "Uncheck all"
    p.btn_toggle_all.click()
    assert p.checked_labels() == set()
    assert p.btn_toggle_all.text() == "Check all"
    p.btn_toggle_all.click()
    assert p.checked_labels() == {3, 4, 5, 6}
    assert p.btn_toggle_all.text() == "Uncheck all"


def test_le_bouton_agit_sur_toutes_les_regions(panneau):
    """Tout cocher veut dire tout. Le filtre se charge de restreindre
    ensuite ce qui est trace, sans avoir a decocher le reste."""
    p, _, _ = panneau
    p.edit_filter.setText("middletemporal")
    assert _visibles(p) == ["ctx-lh-middletemporal"]

    p.btn_toggle_all.click()
    assert p.checked_labels() == set(), "les lignes cachees n'ont pas suivi"

    p.btn_toggle_all.click()
    assert p.checked_labels() == {3, 4, 5, 6}


# -------------------------------------------------------------- le filtre


def test_le_filtre_cache_sans_decocher(panneau):
    """Il restreint le trace, mais ne touche pas aux cases : retirer le
    filtre doit retrouver la selection telle qu'on l'avait laissee."""
    p, _, _ = panneau
    avant = p.checked_labels()
    p.edit_filter.setText("hippo")
    assert _visibles(p) == ["Left-Hippocampus"]
    assert p.checked_labels() == avant
    p.edit_filter.setText("")
    assert p.checked_labels() == avant


def test_le_filtre_ignore_la_casse(panneau):
    p, _, _ = panneau
    p.edit_filter.setText("HIPPO")
    assert _visibles(p) == ["Left-Hippocampus"]


def test_les_regions_sans_contact_peuvent_etre_masquees(panneau):
    p, _, _ = panneau
    p.chk_with_contacts.setChecked(True)
    assert "ctx-rh-precentral" not in _visibles(p)
    assert len(_visibles(p)) == 3


def test_le_filtre_et_le_tri_par_contacts_se_combinent(panneau):
    p, _, _ = panneau
    p.chk_with_contacts.setChecked(True)
    p.edit_filter.setText("ctx-lh")
    assert sorted(_visibles(p)) == ["ctx-lh-middletemporal", "ctx-lh-superiortemporal"]


def test_un_filtre_sans_resultat_ne_change_rien_au_dessin(panneau):
    """Un filtre masque des lignes, il ne decoche pas et n'efface pas.

    Taper trois lettres pour retrouver une region ne doit pas faire
    disparaitre le cerveau le temps de la recherche.
    """
    p, traces, _ = panneau
    avant = len(traces["regions"])
    p.edit_filter.setText("zzzz")

    assert _visibles(p) == []
    assert p.checked_labels() == {3, 4, 5, 6}
    assert p.plotted_labels() == {3, 4, 5, 6}
    assert len(traces["regions"]) == avant, "le filtre a redessine"
    assert p.btn_toggle_all.text() == "Uncheck all"


# --------------------------------------------------------------- le trace


def test_la_case_de_trace_previent_l_appelant(panneau):
    p, traces, _ = panneau
    assert not p.is_plotting()
    p.chk_plot.setChecked(True)
    assert traces["plot"] == [True]
    assert p.is_plotting()
    p.chk_plot.setChecked(False)
    assert traces["plot"] == [True, False]


def test_forcer_l_etat_ne_rejoue_pas_la_bascule(panneau):
    """Pour que la vue 3D puisse remettre la case sans se rappeler elle-meme."""
    p, traces, _ = panneau
    p.set_plotting(True)
    assert p.is_plotting()
    assert traces["plot"] == []


def test_sans_cadre_le_panneau_renonce_sans_lever(app):
    class _Vide:
        def findChild(self, *_a, **_k):
            return None

    assert ParcellationRegionPanel(_Vide()).build() is False


def test_un_rappel_qui_leve_ne_casse_pas_le_panneau(app):
    """Une exception dans la vue 3D ne doit pas figer la table."""
    hote = _Hote()

    def casse(_):
        raise RuntimeError("la vue 3D a echoue")

    p = ParcellationRegionPanel(hote, on_plot_toggled=casse, on_regions_changed=casse)
    assert p.build()
    p.set_regions(REGIONS)
    p.chk_plot.setChecked(True)
    p.btn_toggle_all.click()
    assert p.checked_labels() == set()


def test_la_recherche_trouve_une_region_par_son_contact(panneau):
    """Devant une electrode, la question est : ou tombe TB3 ?"""
    p, _, _ = panneau
    p.edit_filter.setText("TB3")
    assert _visibles(p) == ["ctx-lh-middletemporal"]

    p.edit_filter.setText("hp1")
    assert _visibles(p) == ["Left-Hippocampus"]


def test_la_recherche_par_contact_ignore_la_casse(panneau):
    p, _, _ = panneau
    p.edit_filter.setText("tb1")
    assert _visibles(p) == ["ctx-lh-superiortemporal"]


def test_le_nom_de_region_marche_toujours(panneau):
    """L'ajout ne doit pas avoir casse la recherche d'origine."""
    p, _, _ = panneau
    p.edit_filter.setText("precentral")
    assert _visibles(p) == ["ctx-rh-precentral"]


def test_le_tableau_montre_exactement_quatre_lignes(panneau):
    """Fixe, et non plafonne : un plafond seul laissait le panneau de
    commande se regler sur d'autres contenus et le tableau tomber a deux
    lignes. Fixe, il compte dans le minimum du panneau."""
    from neuxelec.ui.parcellation_region_panel import VISIBLE_ROWS

    p, _, hote = panneau
    hote.resize(600, 900)
    hote.show()
    for _ in range(4):
        QApplication.processEvents()

    ligne = p.table.verticalHeader().defaultSectionSize()
    attendue = (
        p.table.horizontalHeader().sizeHint().height()
        + VISIBLE_ROWS * ligne
        + 2 * p.table.frameWidth()
    )
    assert p.table.height() == attendue
    assert p.table.minimumHeight() == p.table.maximumHeight()
    hote.hide()


# ------------------------------------------- ce qui est trace


def test_est_trace_ce_qui_est_coche(panneau):
    """La regle, en une ligne : les cases, et rien d'autre."""
    p, _, _ = panneau
    assert p.plotted_labels() == {3, 4, 5, 6}

    p.edit_filter.setText("ctx-lh")
    assert p.plotted_labels() == {3, 4, 5, 6}, "la recherche a change le dessin"

    p.table.item(0, COL_REGION).setCheckState(Qt.Unchecked)
    assert p.plotted_labels() == p.checked_labels()


def test_with_contacts_only_raccourcit_la_liste_sans_toucher_au_dessin(panneau):
    """Elle range le tableau, comme la recherche.

    Pour ne tracer que les regions qui portent des contacts, on decoche
    tout puis on coche celles que cette case laisse voir : le dessin
    reste commande par les cases seules, d'ou qu'on les coche.
    """
    p, traces, _ = panneau
    avant = len(traces["regions"])

    p.chk_with_contacts.setChecked(True)
    assert "ctx-rh-precentral" not in _visibles(p), "la ligne devait etre masquee"
    assert p.plotted_labels() == {3, 4, 5, 6}
    assert len(traces["regions"]) == avant, "la case a redessine"


def test_cocher_une_seule_region_ne_trace_qu_elle(panneau):
    p, traces, _ = panneau
    p.btn_toggle_all.click()
    assert traces["regions"][-1] == set()

    ligne = next(
        i
        for i in range(p.table.rowCount())
        if p.table.item(i, COL_REGION).text() == "Left-Hippocampus"
    )
    p.table.item(ligne, COL_REGION).setCheckState(Qt.Checked)
    assert traces["regions"][-1] == {6}


def test_filtrer_ne_touche_jamais_au_dessin(panneau):
    p, _, _ = panneau
    avant = p.plotted_labels()
    p.edit_filter.setText("hippo")
    assert p.plotted_labels() == avant
    p.edit_filter.setText("")
    assert p.plotted_labels() == avant


@pytest.mark.parametrize("recherche", ["", "hippo", "ctx-lh", "zzzz"])
def test_le_bouton_trace_tout_ou_rien_quelle_que_soit_la_recherche(panneau, recherche):
    """Le defaut signale : avec du texte dans la barre, Check all ne
    tracait que les lignes trouvees."""
    p, traces, _ = panneau
    p.edit_filter.setText(recherche)

    p.btn_toggle_all.click()
    assert traces["regions"][-1] == set(), "Uncheck all a laisse quelque chose"

    p.btn_toggle_all.click()
    assert traces["regions"][-1] == {3, 4, 5, 6}, "Check all n'a pas tout trace"


@pytest.mark.parametrize("recherche", ["", "hippo", "zzzz"])
def test_cocher_une_region_masquee_la_trace_quand_meme(panneau, recherche):
    """La case decide, pas la ligne qui l'affiche."""
    p, traces, _ = panneau
    p.btn_toggle_all.click()
    assert traces["regions"][-1] == set()

    ligne = next(
        i
        for i in range(p.table.rowCount())
        if p.table.item(i, COL_REGION).text() == "ctx-lh-middletemporal"
    )
    p.edit_filter.setText(recherche)
    p.table.item(ligne, COL_REGION).setCheckState(Qt.Checked)

    assert traces["regions"][-1] == {4}

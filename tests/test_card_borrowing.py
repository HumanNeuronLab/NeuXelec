"""Emprunter une carte, puis la rendre exactement a sa place.

Ce qui doit tenir : rendre une carte ailleurs que la ou elle etait
changerait silencieusement la mise en page de l'onglet d'ou elle vient.
Une grille est le cas qui mord : une carte rendue a la fin plutot qu'a sa
case se retrouve dans une rangee qui n'est pas la sienne.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from neuxelec.ui.card_borrowing import CardBorrower  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def scene(app):
    """Une grille de trois cartes, et un hote vide."""
    source = QWidget()
    grille = QGridLayout(source)
    cartes = {}
    for nom, (ligne, colonne, el, ec) in {
        "a": (0, 0, 1, 1),
        "b": (0, 1, 1, 1),
        "c": (1, 0, 1, 2),
    }.items():
        carte = QFrame()
        carte.setObjectName(nom)
        QVBoxLayout(carte).addWidget(QLabel(nom))
        grille.addWidget(carte, ligne, colonne, el, ec)
        cartes[nom] = carte

    hote = QWidget()
    hote_layout = QVBoxLayout(hote)
    # La scene garde une reference sur source et hote : sans cela Python
    # les libere et Qt detruit leurs dispositions avec eux.
    return source, grille, cartes, hote_layout, hote


def _position(grille, carte):
    for i in range(grille.count()):
        if grille.itemAt(i).widget() is carte:
            return tuple(grille.getItemPosition(i))
    return None


def test_emprunter_deplace_la_carte(scene):
    _source, grille, cartes, hote, _h = scene
    emprunteur = CardBorrower()
    assert emprunteur.borrow(cartes["b"], hote)

    assert hote.count() == 1
    assert hote.itemAt(0).widget() is cartes["b"]
    assert _position(grille, cartes["b"]) is None


def test_rendre_remet_la_carte_dans_sa_case(scene):
    """Le piege : rendue a la fin de la grille, elle changerait de rangee."""
    _source, grille, cartes, hote, _h = scene
    avant = {n: _position(grille, c) for n, c in cartes.items()}

    emprunteur = CardBorrower()
    emprunteur.borrow(cartes["b"], hote)
    emprunteur.borrow(cartes["c"], hote)
    emprunteur.return_all()

    apres = {n: _position(grille, c) for n, c in cartes.items()}
    assert apres == avant


def test_rendre_respecte_les_etalements(scene):
    """La carte c s'etale sur deux colonnes : elle doit le retrouver."""
    _source, grille, cartes, hote, _h = scene
    emprunteur = CardBorrower()
    emprunteur.borrow(cartes["c"], hote)
    emprunteur.return_all()
    assert _position(grille, cartes["c"]) == (1, 0, 1, 2)


def test_une_disposition_lineaire_retrouve_son_ordre(app):
    source = QWidget()
    colonne = QVBoxLayout(source)
    cartes = []
    for nom in ("un", "deux", "trois"):
        carte = QFrame()
        carte.setObjectName(nom)
        colonne.addWidget(carte)
        cartes.append(carte)

    porteur = QWidget()
    hote = QVBoxLayout(porteur)
    emprunteur = CardBorrower()
    emprunteur.borrow(cartes[1], hote)
    emprunteur.return_all()

    ordre = [colonne.itemAt(i).widget().objectName() for i in range(colonne.count())]
    assert ordre == ["un", "deux", "trois"]


def test_emprunter_deux_fois_ne_fait_rien_de_plus(scene):
    _source, _grille, cartes, hote, _h = scene
    emprunteur = CardBorrower()
    assert emprunteur.borrow(cartes["a"], hote)
    assert emprunteur.borrow(cartes["a"], hote)
    assert hote.count() == 1
    assert emprunteur.borrowed == [cartes["a"]]


def test_une_carte_absente_est_refusee_sans_lever(app):
    """Un onglet incomplet reste utilisable, une exception non."""
    orpheline = QFrame()
    porteur = QWidget()
    hote = QVBoxLayout(porteur)
    emprunteur = CardBorrower()
    assert emprunteur.borrow(orpheline, hote) is False
    assert emprunteur.borrow(None, hote) is False
    assert not emprunteur.is_borrowing()


def test_rendre_sans_avoir_emprunte_ne_fait_rien(app):
    emprunteur = CardBorrower()
    emprunteur.return_all()
    assert emprunteur.borrowed == []


def test_une_carte_dans_une_disposition_imbriquee_est_trouvee(app):
    """Les cartes de NeuXelec sont souvent a trois niveaux de profondeur."""
    source = QWidget()
    dehors = QVBoxLayout(source)
    dedans = QGridLayout()
    dehors.addLayout(dedans)
    carte = QFrame()
    carte.setObjectName("profonde")
    dedans.addWidget(carte, 2, 3, 1, 2)

    porteur = QWidget()
    hote = QVBoxLayout(porteur)
    emprunteur = CardBorrower()
    assert emprunteur.borrow(carte, hote)
    emprunteur.return_all()
    assert _position(dedans, carte) == (2, 3, 1, 2)


def test_tout_est_rendu_en_un_seul_appel(scene):
    _source, grille, cartes, hote, _h = scene
    emprunteur = CardBorrower()
    for carte in cartes.values():
        emprunteur.borrow(carte, hote)
    assert hote.count() == 3
    assert emprunteur.is_borrowing()

    emprunteur.return_all()
    assert hote.count() == 0
    assert not emprunteur.is_borrowing()
    assert all(_position(grille, c) is not None for c in cartes.values())


def test_rendre_fait_oublier_la_taille_a_l_hote(scene):
    """Le defaut signale : revenir d'un onglet gardait sa hauteur.

    Qt garde en cache la taille minimale d'une disposition. Un hote rempli
    puis vide continue de la reclamer, et c'est la plus haute des
    dispositions qui decide de celle du panneau.
    """
    _source, _grille, cartes, hote, porteur = scene
    porteur.show()
    QApplication.processEvents()
    avant = porteur.minimumSizeHint().height()

    emprunteur = CardBorrower()
    for carte in cartes.values():
        carte.setMinimumHeight(120)
        emprunteur.borrow(carte, hote)
    QApplication.processEvents()
    plein = porteur.minimumSizeHint().height()
    assert plein > avant, "l'hote n'a pas grandi, le test ne prouve rien"

    emprunteur.return_all()
    QApplication.processEvents()
    assert porteur.minimumSizeHint().height() == avant, "l'hote reclame encore sa taille"
    porteur.hide()


def test_l_invalidation_s_arrete_sur_une_enveloppe_morte(app):
    """PySide fabrique des enveloppes a la volee : en croiser une veut
    dire qu'on est en haut, pas qu'il y a une panne."""
    CardBorrower._invalidate(None)

    class _Morte:
        def invalidate(self):
            raise RuntimeError("Internal C++ object already deleted.")

    CardBorrower._invalidate(_Morte())


def test_l_invalidation_ne_tourne_pas_en_rond(app):
    """Un arbre qui se referme sur lui-meme doit s'arreter."""
    appels = []

    class _Boucle:
        def invalidate(self):
            appels.append(1)

        def parentWidget(self):  # noqa: N802
            return self

        def updateGeometry(self):  # noqa: N802
            pass

        def layout(self):
            return self

    CardBorrower._invalidate(_Boucle())
    assert len(appels) == CardBorrower._MAX_LEVELS

"""Le trace d'une region par region, du cote de la vue 3D.

Ce qui doit tenir, et qu'aucun test du panneau seul ne peut dire :

  - cocher le trace eteint le cerveau, et le decocher **remet ce qui
    etait la**, pas le brainmask par defaut ;
  - un maillage par region, pose a sa vraie place dans le volume. Une
    erreur d'un voxel sur le coin de la decoupe deplacerait toutes les
    regions sans que rien ne le signale ;
  - decocher une region la cache sans reconstruire : c'est un geste que
    l'on fait vingt fois de suite ;
  - changer de parcellation jette les anciens maillages, dont les
    etiquettes ne designent plus les memes regions.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import SimpleITK as sitk

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QFrame,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from neuxelec.pages.view3d import View3DPage  # noqa: E402

LUT = {
    3: ("ctx-lh-superiortemporal", (140, 20, 20)),
    4: ("Left-Hippocampus", (220, 20, 100)),
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _volume():
    """Deux blocs bien separes, assez gros pour marching cubes."""
    vol = np.zeros((20, 20, 20), dtype=np.int32)
    vol[2:8, 2:8, 2:8] = 3
    vol[12:18, 12:18, 12:18] = 4
    return vol


def _image(vol, origine=(0.0, 0.0, 0.0), espacement=(1.0, 1.0, 1.0)):
    img = sitk.GetImageFromArray(vol)
    img.SetSpacing(espacement)
    img.SetOrigin(origine)
    return img


class _Etat:
    def __init__(self):
        self.electrodes = []
        self.parcel1_path = "C:/essai/aparc+aseg.nii.gz"
        self.parcel2_path = None


class _Plotter:
    def __init__(self):
        self.meshes = []
        self.removed = []

    def add_mesh(self, mesh, **kwargs):
        acteur = _Acteur(mesh, kwargs)
        self.meshes.append(acteur)
        return acteur

    def remove_actor(self, actor, **_k):
        self.removed.append(actor)


class _Mapper:
    def __init__(self):
        self.planes = []

    def RemoveAllClippingPlanes(self):  # noqa: N802
        self.planes = []

    def AddClippingPlane(self, plan):  # noqa: N802
        self.planes.append(plan)


class _Propriete:
    def __init__(self):
        self.opacite = 1.0

    def SetOpacity(self, v):  # noqa: N802
        self.opacite = float(v)


class _Acteur:
    def __init__(self, mesh, kwargs):
        self.mesh = mesh
        self.kwargs = kwargs
        self.visible = True
        self._propriete = _Propriete()
        self._mapper = _Mapper()

    def GetProperty(self):  # noqa: N802
        return self._propriete

    def GetMapper(self):  # noqa: N802
        return self._mapper

    def SetVisibility(self, v):  # noqa: N802
        self.visible = bool(v)

    def PickableOff(self):  # noqa: N802
        pass


class _Overlay:
    def __init__(self):
        self.messages = []
        self.fini = 0
        self.annule = 0

    def begin(self, message=None):
        self.messages.append(("begin", message))

    def set_progress(self, value, message=None):
        self.messages.append(("progress", round(float(value), 2)))

    def complete(self):
        self.fini += 1

    def cancel(self):
        self.annule += 1


class _Hote(QWidget):
    def __init__(self):
        super().__init__()
        cadre = QFrame(self)
        cadre.setObjectName("card3DRegions")
        QVBoxLayout(cadre)
        self.chk_brainmask = QCheckBox("brainmask", self)
        self.chk_brainmask.setObjectName("chk_3d_showBrainmask")
        self.chk_pial = QCheckBox("pial", self)
        self.chk_pial.setObjectName("chk_3d_showPialsurface")


class _Page:
    """Juste assez de la vue 3D pour exercer le trace des regions."""

    def __init__(self, vol=None, img=None):
        self.ui = _Hote()
        self.state = _Etat()
        self.plotter = _Plotter()
        self._loading_overlay = _Overlay()
        self._parcel1_img = img if img is not None else _image(vol if vol is not None else _volume())
        self._parcel2_img = None
        self._parcel1_lut = dict(LUT)
        self._parcel2_lut = {}
        self.chk_parcel1 = QCheckBox()
        self.chk_parcel1.setChecked(True)
        self.chk_parcel2 = QCheckBox()
        self.spn_parcel1_opacity = QSpinBox()
        self.spn_parcel1_opacity.setRange(0, 100)
        self.spn_parcel1_opacity.setValue(100)
        self.spn_parcel2_opacity = QSpinBox()
        self.spn_parcel2_opacity.setRange(0, 100)
        self.spn_parcel2_opacity.setValue(30)
        # Les plans de coupe, decoches : _add_region_actor decoupe
        # chaque maillage des sa naissance et les consulte.
        for nom in ("coronal", "axial", "sagittal"):
            case = QCheckBox()
            setattr(self, f"chk_{nom}_plane", case)
            setattr(self, f"_build_vtk_{nom}_clip_plane", lambda n=nom: f"plan-{n}")
        self.chk_brainmask = self.ui.chk_brainmask
        self.chk_pial = self.ui.chk_pial
        self.brain_sources = []
        self.mni_visible = False
        self.renders = 0

    def _set_checked(self, case, valeur):
        case.blockSignals(True)
        case.setChecked(bool(valeur))
        case.blockSignals(False)

    def _on_brain_source(self, which, checked):
        self.brain_sources.append((which, bool(checked)))

    def _render(self):
        self.renders += 1

    def _dialog_parent(self):
        return None

    def _mni_t1_slices_are_visible(self):
        return bool(self.mni_visible)

    def _get_active_parcellation_img_and_lut(self):
        """Le vrai choix tient compte du mode MNI ; ce double s'en tient
        au patient, les tests du mode MNI etant ailleurs."""
        if self.chk_parcel1.isChecked() and self._parcel1_img is not None:
            return self._parcel1_img, self._parcel1_lut
        if self.chk_parcel2.isChecked() and self._parcel2_img is not None:
            return self._parcel2_img, self._parcel2_lut
        return None, {}

    # Les vraies methodes, prises telles quelles.
    _binarymask_to_polydata = View3DPage._binarymask_to_polydata
    _verts_faces_to_polydata = View3DPage._verts_faces_to_polydata
    _build_parcellation_region_panel = View3DPage._build_parcellation_region_panel
    _active_parcellation_for_regions = View3DPage._active_parcellation_for_regions
    _contact_points_for_regions = View3DPage._contact_points_for_regions
    _region_table_signature = View3DPage._region_table_signature
    _parcellation_label_volume = View3DPage._parcellation_label_volume
    _refresh_parcellation_regions = View3DPage._refresh_parcellation_regions
    _on_parcellation_plot_toggled = View3DPage._on_parcellation_plot_toggled
    _on_parcellation_regions_changed = View3DPage._on_parcellation_regions_changed
    _hide_brain_for_regions = View3DPage._hide_brain_for_regions
    _restore_brain_before_regions = View3DPage._restore_brain_before_regions
    _start_region_plot = View3DPage._start_region_plot
    _start_region_plot_work = View3DPage._start_region_plot_work
    _region_plot_step = View3DPage._region_plot_step
    _add_region_actor = View3DPage._add_region_actor
    _apply_clipping_to_region_actor = View3DPage._apply_clipping_to_region_actor
    _parcellation_region_opacity = View3DPage._parcellation_region_opacity
    # staticmethod : sans l'enveloppe, self prendrait la place de l'acteur.
    _set_region_actor_opacity = staticmethod(View3DPage._set_region_actor_opacity)
    _apply_region_opacity = View3DPage._apply_region_opacity
    _clear_region_actors = View3DPage._clear_region_actors


def _page_prete(**kw):
    page = _Page(**kw)
    page._build_parcellation_region_panel()
    assert page._region_panel is not None
    return page


def _tout_tracer(page):
    """Derouler le vrai chemin, sans attendre les minuteries de Qt.

    Passe par _start_region_plot pour que rien ne soit court-circuite :
    c'est lui qui eteint le cerveau, remplit la file et pose le drapeau
    qui rend les etapes legitimes.
    """
    # Sans regions, _start_region_plot ouvre un dialogue modal qui, faute
    # de boucle d'evenements, bloquerait la suite pendant des minutes au
    # lieu d'echouer. On verifie donc avant d'appeler.
    assert page._region_panel is not None and page._region_panel.regions()
    page._region_panel.set_plotting(True)
    page._start_region_plot()
    # La minuterie que _start_region_plot pose, jouee a la main : elle
    # existe pour que le voile de chargement ait le temps d'apparaitre.
    page._start_region_plot_work()
    gardefou = 0
    while page._region_queue and gardefou < 500:
        page._region_plot_step()
        gardefou += 1


# ------------------------------------------------------------- le tableau


def test_le_tableau_se_remplit_depuis_la_parcellation_cochee(app):
    page = _page_prete()
    noms = [r.name for r in page._region_panel._regions]
    assert noms == ["ctx-lh-superiortemporal", "Left-Hippocampus"]


def test_sans_parcellation_cochee_le_tableau_est_vide(app):
    page = _page_prete()
    page.chk_parcel1.setChecked(False)
    page._refresh_parcellation_regions()
    assert page._region_panel._regions == []


# --------------------------------------------------------------- le trace


def test_une_region_donne_un_maillage(app):
    page = _page_prete()
    _tout_tracer(page)
    assert sorted(page._region_actors) == [3, 4]
    assert len(page.plotter.meshes) == 2


def test_chaque_maillage_tombe_ou_est_sa_region(app):
    """Le piege : un coin de decoupe faux deplace tout sans rien casser."""
    page = _page_prete()
    _tout_tracer(page)

    # La vue 3D dessine en RAS : x et y changent de signe depuis le LPS.
    attendus = {3: (2, 8), 4: (12, 18)}
    for label, (lo, hi) in attendus.items():
        bornes = page._region_actors[label].mesh.bounds
        z0, z1 = bornes[4], bornes[5]
        assert lo - 1.5 <= z0 <= lo + 1.5, f"region {label} mal placee en z"
        assert hi - 1.5 <= z1 <= hi + 1.5, f"region {label} mal placee en z"


def test_le_maillage_suit_l_origine_de_l_image(app):
    """Une parcellation qui ne commence pas a zero doit decaler d'autant."""
    decalage = 40.0
    page = _page_prete(img=_image(_volume(), origine=(0.0, 0.0, decalage)))
    _tout_tracer(page)
    z0 = page._region_actors[3].mesh.bounds[4]
    assert decalage + 0.5 <= z0 <= decalage + 3.5


def test_chaque_region_porte_sa_couleur_d_atlas(app):
    page = _page_prete()
    _tout_tracer(page)
    couleur = page._region_actors[4].kwargs["color"]
    assert couleur == pytest.approx((220 / 255.0, 20 / 255.0, 100 / 255.0))


# ------------------------------------------------------- montrer et cacher


def test_decocher_une_region_la_cache_sans_reconstruire(app):
    page = _page_prete()
    _tout_tracer(page)
    construits = len(page.plotter.meshes)

    page._on_parcellation_regions_changed({3})
    assert page._region_actors[3].visible
    assert not page._region_actors[4].visible
    assert len(page.plotter.meshes) == construits, "des maillages ont ete refaits"

    page._on_parcellation_regions_changed({3, 4})
    assert page._region_actors[4].visible


# ------------------------------------------------------- le cerveau d avant


def test_tracer_eteint_le_cerveau_et_decocher_remet_ce_qui_etait_la(app):
    """Remettre, et non rallumer le brainmask par defaut."""
    page = _page_prete()
    page.chk_pial.setChecked(True)
    page.chk_brainmask.setChecked(False)

    _tout_tracer(page)
    assert not page.chk_pial.isChecked()
    assert ("pial", False) in page.brain_sources

    page._region_panel.set_plotting(False)
    page._on_parcellation_plot_toggled(False)
    assert page.chk_pial.isChecked()
    assert not page.chk_brainmask.isChecked(), "le brainmask n'etait pas allume"
    assert ("pial", True) in page.brain_sources


def test_decocher_le_trace_retire_les_maillages(app):
    page = _page_prete()
    _tout_tracer(page)
    page._region_panel.set_plotting(False)
    page._on_parcellation_plot_toggled(False)
    assert page._region_actors == {}
    assert len(page.plotter.removed) == 2


# ------------------------------------------------------- changer d'atlas


def test_changer_de_parcellation_jette_les_anciens_maillages(app):
    """Les etiquettes de l'une ne designent pas les regions de l'autre."""
    page = _page_prete()
    _tout_tracer(page)
    assert page._region_actors

    autre = _volume()
    autre[autre == 4] = 0
    page._parcel1_img = _image(autre)
    page._region_vol_cache = {}
    page._refresh_parcellation_regions()

    assert page._region_actors == {}, "les maillages de l'atlas precedent sont restes"
    assert [r.label for r in page._region_panel._regions] == [3]


# ------------------------------------------------------------- robustesse


def test_l_ecran_de_chargement_est_pose_puis_retire(app):
    page = _page_prete()
    page._region_panel.set_plotting(True)
    page._start_region_plot()
    assert page._loading_overlay.messages[0][0] == "begin"
    page._start_region_plot_work()
    gardefou = 0
    while page._region_queue and gardefou < 500:
        page._region_plot_step()
        gardefou += 1
    assert page._loading_overlay.fini == 1

    # Une minuterie tardive ne doit pas rejouer la fin.
    page._region_plot_step()
    assert page._loading_overlay.fini == 1


def test_une_region_impossible_a_mailler_ne_casse_pas_le_reste(app):
    """Un voxel isole ne donne pas de surface fermee : on passe au suivant."""
    vol = _volume()
    vol[19, 19, 19] = 9
    page = _page_prete(img=_image(vol))
    _tout_tracer(page)
    assert 3 in page._region_actors
    assert 4 in page._region_actors


# ------------------------------------- les onglets ne changent pas la scene


def test_revenir_sur_l_onglet_ne_recoche_pas_les_regions(app):
    """Le defaut signale : une selection d'une seule region redevenait le
    cerveau entier des qu'on quittait l'onglet et qu'on y revenait."""
    page = _page_prete()
    _tout_tracer(page)

    # L'utilisateur ne garde qu'une region.
    page._on_parcellation_regions_changed({3})
    page._region_panel._checked = {3}
    assert page._region_actors[3].visible
    assert not page._region_actors[4].visible

    # Aller voir ailleurs, puis revenir : rien ne doit bouger.
    page._refresh_parcellation_regions()

    assert page._region_panel.checked_labels() == {3}
    assert page._region_actors[3].visible
    assert not page._region_actors[4].visible


def test_revenir_sur_l_onglet_ne_refait_aucun_maillage(app):
    """Reconstruire serait inutile, lent, et ferait clignoter la scene."""
    page = _page_prete()
    _tout_tracer(page)
    construits = len(page.plotter.meshes)

    for _ in range(5):
        page._refresh_parcellation_regions()

    assert len(page.plotter.meshes) == construits
    assert page.plotter.removed == []


def test_un_vrai_changement_de_parcellation_refait_bien_le_tableau(app):
    """La prudence ne doit pas aller jusqu'a ignorer un vrai changement."""
    page = _page_prete()
    _tout_tracer(page)

    autre = _volume()
    autre[autre == 4] = 0
    page._parcel1_img = _image(autre)
    page._region_vol_cache = {}
    page._refresh_parcellation_regions()

    assert [r.label for r in page._region_panel.regions()] == [3]


def test_un_contact_reconstruit_refait_le_tableau(app):
    """La colonne des contacts serait perimee sinon."""
    page = _page_prete()
    assert page._region_panel.regions()[0].contacts == ()

    page.state.electrodes = [{"name": "TB", "contacts_lps": [(5.0, 5.0, 5.0)]}]
    page._refresh_parcellation_regions()

    avec = [r for r in page._region_panel.regions() if r.contacts]
    assert [r.contacts for r in avec] == [("TB1",)]


def test_relancer_le_trace_ne_perd_pas_le_cerveau_d_avant(app):
    """Le second defaut : _hide_brain_for_regions rappelee ecrasait l'etat
    retenu par l'etat deja eteint, et decocher ne remettait plus rien."""
    page = _page_prete()
    page.chk_pial.setChecked(True)
    _tout_tracer(page)
    assert not page.chk_pial.isChecked()

    # Un vrai changement de parcellation, qui relance le trace.
    page._hide_brain_for_regions()
    page._hide_brain_for_regions()

    page._region_panel.set_plotting(False)
    page._on_parcellation_plot_toggled(False)
    assert page.chk_pial.isChecked(), "la pial surface d'avant a ete perdue"


# -------------------------------------------- la decoupe sur les coupes


def _page_avec_coupes(cochees=True):
    """La page standard, avec ses trois plans cochés ou non."""
    page = _page_prete()
    for nom in ("coronal", "axial", "sagittal"):
        getattr(page, f"chk_{nom}_plane").setChecked(bool(cochees))
    return page


def test_une_region_neuve_nait_deja_decoupee(app):
    """Elles arrivent par paquets, bien apres le reglage des coupes : sans
    cela les premieres traverseraient les plans jusqu'au prochain reglage."""
    page = _page_avec_coupes()
    acteur = _Acteur(None, {})

    page._apply_clipping_to_region_actor(acteur)
    assert sorted(acteur._mapper.planes) == ["plan-axial", "plan-coronal", "plan-sagittal"]


def test_garder_la_parcellation_entiere_n_ajoute_aucun_plan(app):
    page = _page_avec_coupes()
    page._keep_parcellation_in_volume = True
    acteur = _Acteur(None, {})

    page._apply_clipping_to_region_actor(acteur)
    assert acteur._mapper.planes == []


def test_sans_coupe_cochee_rien_n_est_decoupe(app):
    page = _page_avec_coupes(cochees=False)
    acteur = _Acteur(None, {})

    page._apply_clipping_to_region_actor(acteur)
    assert acteur._mapper.planes == []


def _page_decoupe_complete(garder=False):
    """Une page capable d'exercer _apply_actor_clipping en entier."""
    page = _page_avec_coupes()
    _tout_tracer(page)
    page._keep_parcellation_in_volume = bool(garder)
    for nom in ("_brain_actor", "_ct_actor", "_pet_actor", "_mni_atlas_actor",
                "_siscom_actor", "_fmri_actor"):
        setattr(page, nom, None)
    page._elec_actors = {}
    page._mni_electrode_actors = {}
    page._apply_electrode_actor_depth_mode = lambda _a: None
    page._apply_actor_clipping = View3DPage._apply_actor_clipping.__get__(page)
    return page


def test_bouger_une_coupe_decoupe_la_parcellation(app):
    """Le chemin reel : celui qui tourne quand on deplace un plan."""
    page = _page_decoupe_complete()
    page._apply_actor_clipping()
    for acteur in page._region_actors.values():
        assert sorted(acteur._mapper.planes) == [
            "plan-axial",
            "plan-coronal",
            "plan-sagittal",
        ]


def test_keep_parcellation_in_volume_laisse_les_regions_entieres(app):
    page = _page_decoupe_complete(garder=True)
    page._apply_actor_clipping()
    for acteur in page._region_actors.values():
        assert acteur._mapper.planes == [], "la region a ete coupee malgre l'option"


def test_la_bascule_reprend_la_decoupe(app):
    """Decocher l'option doit redecouper, pas attendre le prochain reglage."""
    page = _page_decoupe_complete(garder=True)
    page._apply_actor_clipping()
    assert all(a._mapper.planes == [] for a in page._region_actors.values())

    page._keep_parcellation_in_volume = False
    page._apply_actor_clipping()
    assert all(len(a._mapper.planes) == 3 for a in page._region_actors.values())


# ------------------------------------------------------------- opacite


def test_un_maillage_neuf_nait_a_l_opacite_du_curseur(app):
    """Sinon il faudrait toucher le curseur une fois pour que ca prenne."""
    page = _page_prete()
    page.spn_parcel1_opacity.setValue(40)
    _tout_tracer(page)
    for acteur in page._region_actors.values():
        assert acteur.GetProperty().opacite == pytest.approx(0.40)


def test_bouger_le_curseur_change_toutes_les_regions(app):
    page = _page_prete()
    _tout_tracer(page)
    page.spn_parcel1_opacity.setValue(25)
    page._apply_region_opacity()
    assert all(
        a.GetProperty().opacite == pytest.approx(0.25)
        for a in page._region_actors.values()
    )


def test_chaque_parcellation_garde_son_propre_curseur(app):
    """Les deux cases sont exclusives, et chacune a son reglage."""
    page = _page_prete()
    assert page._parcellation_region_opacity() == pytest.approx(1.0)

    page.chk_parcel1.setChecked(False)
    page.chk_parcel2.setChecked(True)
    assert page._parcellation_region_opacity() == pytest.approx(0.30)


def test_l_opacite_reste_entre_zero_et_un(app):
    page = _page_prete()
    page.spn_parcel1_opacity.setRange(-500, 500)
    page.spn_parcel1_opacity.setValue(-200)
    assert page._parcellation_region_opacity() == 0.0
    page.spn_parcel1_opacity.setValue(400)
    assert page._parcellation_region_opacity() == 1.0


def test_sans_region_tracee_le_curseur_ne_fait_rien(app):
    page = _page_prete()
    avant = page.renders
    page._apply_region_opacity()
    assert page.renders == avant, "un rendu pour rien"


# ------------------------------------------------- la parcellation MNI


def test_en_mode_mni_ce_sont_les_contacts_mni_qui_sont_lus(app):
    """Les contacts du patient ne sont pas dans le repere du gabarit :
    les y confronter les placerait tous a cote."""
    page = _page_prete()
    page.state.electrodes = [{"name": "TB", "contacts_lps": [(5.0, 5.0, 5.0)]}]
    page.state.mni_electrode_sets = [
        {"contacts": [{"name": "MNI-A1", "mni_ras": [-5.0, -5.0, 5.0]}]}
    ]

    assert [n for n, _ in page._contact_points_for_regions()] == ["TB1"]

    page.mni_visible = True
    assert page._contact_points_for_regions() == [("MNI-A1", (5.0, 5.0, 5.0))]


def test_le_wmparc_n_est_pas_cherche_a_cote_d_un_atlas_mni(app):
    """Il irait prendre celui du patient, dans un autre repere."""
    import neuxelec.utils.wmparc as wmparc

    vus = []
    vrai = wmparc.find_sibling_wmparc

    def espion(chemin, img):
        vus.append(chemin)
        return None

    try:
        page = _page_prete()
        wmparc.find_sibling_wmparc = espion
        # En natif, le chemin du patient est bien transmis.
        page._region_vol_cache = {}
        page._parcellation_label_volume(page._parcel1_img)
        assert vus == ["C:/essai/aparc+aseg.nii.gz"]

        vus.clear()
        page.mni_visible = True
        page._region_vol_cache = {}
        page._parcellation_label_volume(page._parcel1_img)
    finally:
        wmparc.find_sibling_wmparc = vrai

    assert vus == [None], "le wmparc du patient a ete cherche en mode MNI"


def test_entrer_en_mode_mni_retire_les_surfaces_natives(app):
    """Le defaut signale : le cerveau de la parcellation restait affiche
    sur le gabarit MNI, ou il n'a rien a faire. Ces maillages sont tailles
    dans l'espace du patient."""
    page = _page_prete()
    _tout_tracer(page)
    assert page._region_actors

    # Ce que fait _clear_native_scene_for_mni_mode en entrant dans le MNI.
    page._clear_region_actors()

    assert page._region_actors == {}
    assert len(page.plotter.removed) == 2


def test_le_nettoyage_natif_du_mode_mni_appelle_bien_ce_nettoyage(app):
    """Sans cet appel, les maillages survivraient au changement de repere."""
    import inspect

    from neuxelec.pages.view3d_mni import View3DMniMixin

    source = inspect.getsource(View3DMniMixin._clear_native_scene_for_mni_mode)
    assert "_clear_region_actors()" in source


def test_le_voile_est_pose_avant_que_rien_ne_bouge(app):
    """Le defaut signale : la vue se defaisait, puis le voile arrivait."""
    page = _page_prete()
    _tout_tracer(page)
    page._region_panel.set_plotting(False)
    page._on_parcellation_plot_toggled(False)

    page.plotter.removed.clear()
    page.brain_sources.clear()
    page._loading_overlay.messages.clear()

    page._region_panel.set_plotting(True)
    page._start_region_plot()

    assert page._loading_overlay.messages[0][0] == "begin"
    assert page.plotter.removed == [], "des acteurs ont ete retires avant le voile"
    assert page.brain_sources == [], "le cerveau a ete eteint avant le voile"


# --------------------------------- le filtre et les boutons, cote 3D


def test_filtrer_ne_touche_pas_a_la_scene(app):
    """Chercher une region dans le tableau ne doit rien effacer.

    Le filtre range la liste, il ne commande pas la scene : ni les
    acteurs visibles, ni les maillages deja construits ne bougent.
    """
    page = _page_prete()
    _tout_tracer(page)
    construits = len(page.plotter.meshes)
    avant = {k for k, a in page._region_actors.items() if a.visible}

    for recherche in ("hippo", "zzzz", ""):
        page._region_panel.edit_filter.setText(recherche)
        visibles = {k for k, a in page._region_actors.items() if a.visible}
        assert visibles == avant, "la recherche %r a change la scene" % recherche
        assert len(page.plotter.meshes) == construits


def test_les_boutons_tracent_tout_ou_rien_malgre_la_recherche(app):
    """Le defaut signale : avec du texte dans la barre, Check all ne
    rallumait que les regions trouvees."""
    page = _page_prete()
    _tout_tracer(page)
    toutes = set(page._region_actors)

    page._region_panel.edit_filter.setText("hippo")

    page._region_panel.btn_toggle_all.click()
    assert not any(a.visible for a in page._region_actors.values())

    page._region_panel.btn_toggle_all.click()
    allumees = {k for k, a in page._region_actors.items() if a.visible}
    assert allumees == toutes, allumees


def test_tout_decocher_retire_tout_le_dessin(app):
    page = _page_prete()
    _tout_tracer(page)
    page._region_panel.btn_toggle_all.click()
    assert not any(a.visible for a in page._region_actors.values())

    page._region_panel.btn_toggle_all.click()
    assert all(a.visible for a in page._region_actors.values())


def test_sans_la_case_de_trace_rien_n_est_dessine(app):
    """Toutes ces commandes ne font effet que le trace allume."""
    page = _page_prete()
    assert not page._region_panel.is_plotting()

    page._region_panel.btn_toggle_all.click()
    page._region_panel.edit_filter.setText("hippo")
    page._region_panel.chk_with_contacts.setChecked(True)

    assert page._region_actors == {}
    assert page.plotter.meshes == []

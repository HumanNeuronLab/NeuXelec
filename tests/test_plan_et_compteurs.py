"""Le plan enregistre, relu, et les trois compteurs d'electrodes.

QUATRE DEMANDES QUI SE TIENNENT

Enregistrer le plan laisse un fichier de trajectoires. Ce fichier est
desormais retenu, ce qui permet trois choses : le bouton Save peut
dire qu'il a enregistre, Load Planning peut le relire, et la page
Reconstruction peut dire combien d'electrodes restent a faire.

CE QUE LE FICHIER RELU EVITE

Ses coordonnees sont celles que NeuXelec a calculees, deja dans
l'espace de MRI 1 : pas de .nip a retrouver, pas d'IRM de
planification a recaler, pas d'alignement a revoir.

Il faut en revanche verifier qu'elles decrivent bien **cette** IRM. Un
fichier calcule contre une autre serie se lit sans la moindre erreur
et poserait les electrodes a cote du cerveau : seul un comptage des
points tombant dans le volume le montre.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
import SimpleITK as sitk

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from neuxelec.controllers.electrodes import ElectrodesController  # noqa: E402
from neuxelec.state import AppState  # noqa: E402
from neuxelec.utils.plan_import import (  # noqa: E402
    TRAJECTORY_FILE_HEADER,
    is_planned_trajectories_file,
    read_planned_trajectories,
    trajectories_inside_fraction,
)

FICHIER = """SEEG_planned_trajectories
========================================
Patient: Patient6
Export date: 2026-10-12
Export time: 10:00:00
Coordinate system: LPS (MRI1)
Plan source: NeuroInspire
Alignment on MRI1: affine, reviewed
========================================

[HAG] | reference=MM08 | hemisphere=left
  entry  | x=60.00 | y=10.00 | z=-5.00
  target | x=30.00 | y=12.00 | z=-6.00
  contact=1   | x=30.00 | y=12.00 | z=-6.00
  contact=2   | x=34.00 | y=12.00 | z=-6.00

[HAD] | reference=MM08 | hemisphere=right
  entry  | x=-60.00 | y=10.00 | z=-5.00
  target | x=-30.00 | y=12.00 | z=-6.00
  contact=1   | x=-30.00 | y=12.00 | z=-6.00
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fichier(tmp_path):
    chemin = tmp_path / "plan_trajectories_LPS.txt"
    chemin.write_text(FICHIER, encoding="utf-8")
    return chemin


def _irm(taille=(200, 200, 200), origine=(100.0, 100.0, -100.0)):
    img = sitk.GetImageFromArray(np.zeros(tuple(reversed(taille)), dtype=np.int16))
    img.SetOrigin(origine)
    img.SetDirection((-1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0))
    return img


# ------------------------------------------- reconnaitre le fichier


def test_le_fichier_est_reconnu_a_sa_premiere_ligne(fichier):
    """Pas a son extension : un .txt ne dit rien."""
    assert is_planned_trajectories_file(fichier)


def test_un_autre_texte_n_est_pas_pris_pour_un_plan(tmp_path):
    autre = tmp_path / "notes.txt"
    autre.write_text("des notes", encoding="utf-8")
    assert not is_planned_trajectories_file(autre)


def test_un_fichier_absent_ne_fait_rien_lever(tmp_path):
    assert not is_planned_trajectories_file(tmp_path / "rien.txt")


def test_l_entete_est_celui_qu_ecrit_la_sauvegarde():
    """Les deux cotes doivent nommer la meme chaine."""
    assert FICHIER.splitlines()[0] == TRAJECTORY_FILE_HEADER


# ------------------------------------------------- le relire


def test_les_deux_electrodes_sont_relues(fichier):
    plan = read_planned_trajectories(fichier)
    assert len(plan["trajectories_t1"]) == 2
    assert [t["name"] for t in plan["trajectories_t1"]] == ["HAG", "HAD"]


def test_chaque_electrode_garde_sa_reference_et_son_cote(fichier):
    plan = read_planned_trajectories(fichier)
    hag, had = plan["trajectories_t1"]
    assert hag["reference_key"] == "MM08"
    assert hag["hemisphere"] == "left"
    assert had["hemisphere"] == "right"


def test_les_points_sont_relus_exactement(fichier):
    plan = read_planned_trajectories(fichier)
    hag = plan["trajectories_t1"][0]
    assert hag["entry_t1_lps"] == [60.0, 10.0, -5.0]
    assert hag["target_t1_lps"] == [30.0, 12.0, -6.0]
    assert hag["contacts_t1_lps"] == [[30.0, 12.0, -6.0], [34.0, 12.0, -6.0]]


def test_le_nombre_de_contacts_est_compte(fichier):
    plan = read_planned_trajectories(fichier)
    assert [t["contact_count"] for t in plan["trajectories_t1"]] == [2, 1]


def test_l_entete_dit_contre_quelle_irm(fichier):
    """C'est ce qui permet de prevenir d'une IRM differente."""
    plan = read_planned_trajectories(fichier)
    assert plan["coordinate_label"] == "MRI1"
    assert plan["patient"] == "Patient6"


def test_le_plan_relu_n_a_rien_a_transformer(fichier):
    """Ses coordonnees sont deja celles de MRI 1."""
    plan = read_planned_trajectories(fichier)
    assert plan["transform"]["mode"] == "identity"
    assert plan["trajectories_t1"] is plan["trajectories"]


def test_un_fichier_sans_electrode_est_refuse(tmp_path):
    """Un plan vide se chargerait sans rien expliquer de son silence."""
    chemin = tmp_path / "vide.txt"
    chemin.write_text(TRAJECTORY_FILE_HEADER + "\n====\nPatient: X\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_planned_trajectories(chemin)


def test_un_fichier_etranger_est_refuse(tmp_path):
    chemin = tmp_path / "autre.txt"
    chemin.write_text("autre chose\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_planned_trajectories(chemin)


# --------------------------------------- le controle d'espace


def test_des_coordonnees_dans_l_irm_sont_reconnues(fichier):
    plan = read_planned_trajectories(fichier)
    part = trajectories_inside_fraction(plan["trajectories_t1"], _irm())
    assert part == pytest.approx(1.0)


def test_des_coordonnees_d_une_autre_serie_sont_vues(fichier):
    """Le cas qui se lit sans erreur et se pose a cote du cerveau."""
    plan = read_planned_trajectories(fichier)
    ailleurs = _irm(taille=(50, 50, 50), origine=(500.0, 500.0, 500.0))
    assert trajectories_inside_fraction(plan["trajectories_t1"], ailleurs) == 0.0


def test_sans_irm_le_controle_ne_bloque_rien(fichier):
    plan = read_planned_trajectories(fichier)
    assert trajectories_inside_fraction(plan["trajectories_t1"], None) == 1.0


def test_un_plan_sans_point_ne_passe_pas_pour_bon():
    assert trajectories_inside_fraction([{"name": "X"}], _irm()) == 0.0


# ------------------------------------------- les trois compteurs


class _Controleur:
    _planned_electrode_count = ElectrodesController._planned_electrode_count
    _loaded_patient_count = ElectrodesController._loaded_patient_count
    _update_electrodes_count_labels = (
        ElectrodesController._update_electrodes_count_labels
    )

    def __init__(self, state, mni=False):
        self.state = state
        self._mni = mni
        self._count_labels_by_name = {
            nom: QLabel()
            for nom in (
                "lbl_ElectrodesCount",
                "lbl_ElectrodesCount_2",
                "lbl_ElectrodesCount_3",
            )
        }

    def _mni_mode_active(self):
        return self._mni

    def textes(self):
        self._update_electrodes_count_labels()
        return {n: l.text() for n, l in self._count_labels_by_name.items()}


def _etat(n_electrodes=0, n_plan=0, n_patients=0):
    etat = AppState()
    etat.electrodes = [{"name": "E%d" % i} for i in range(n_electrodes)]
    if n_plan:
        etat.plan = {"trajectories_t1": [{"name": "T%d" % i} for i in range(n_plan)]}
    etat.mni_electrode_sets = [{"contacts": []} for _ in range(n_patients)]
    return etat


def test_sans_plan_le_compte_reste_ordinaire(app):
    textes = _Controleur(_etat(n_electrodes=3)).textes()
    assert textes["lbl_ElectrodesCount"] == "3 electrodes"


def test_avec_un_plan_la_reconstruction_dit_ce_qui_reste(app):
    """La demande : 3 electrodes / 17."""
    textes = _Controleur(_etat(n_electrodes=3, n_plan=17)).textes()
    assert textes["lbl_ElectrodesCount"] == "3 electrodes / 17"


def test_une_seule_electrode_se_dit_au_singulier(app):
    textes = _Controleur(_etat(n_electrodes=1, n_plan=17)).textes()
    assert textes["lbl_ElectrodesCount"] == "1 electrode / 17"


def test_le_plan_ne_change_que_la_reconstruction(app):
    """Les deux autres pages ne savent rien de ce qui reste a faire."""
    textes = _Controleur(_etat(n_electrodes=3, n_plan=17)).textes()
    assert textes["lbl_ElectrodesCount_2"] == "3 electrodes"
    assert textes["lbl_ElectrodesCount_3"] == "3 electrodes"


def test_en_mode_mni_la_vue_3d_compte_les_patients(app):
    textes = _Controleur(_etat(n_electrodes=3, n_patients=4), mni=True).textes()
    assert textes["lbl_ElectrodesCount_3"] == "4 patients"


def test_un_seul_patient_se_dit_au_singulier(app):
    textes = _Controleur(_etat(n_patients=1), mni=True).textes()
    assert textes["lbl_ElectrodesCount_3"] == "1 patient"


def test_le_compte_de_patients_ne_parait_qu_en_mode_mni(app):
    """La demande le precise : visible seulement dans ce mode."""
    textes = _Controleur(_etat(n_electrodes=3, n_patients=4), mni=False).textes()
    assert textes["lbl_ElectrodesCount_3"] == "3 electrodes"


def test_le_mode_mni_ne_touche_pas_aux_deux_autres_pages(app):
    textes = _Controleur(_etat(n_electrodes=3, n_patients=4), mni=True).textes()
    assert textes["lbl_ElectrodesCount"] == "3 electrodes"
    assert textes["lbl_ElectrodesCount_2"] == "3 electrodes"


def test_les_deux_regles_se_combinent(app):
    """Un plan charge et le mode MNI actif en meme temps."""
    textes = _Controleur(
        _etat(n_electrodes=3, n_plan=17, n_patients=2), mni=True
    ).textes()
    assert textes["lbl_ElectrodesCount"] == "3 electrodes / 17"
    assert textes["lbl_ElectrodesCount_3"] == "2 patients"


def test_un_plan_vide_ne_fait_pas_apparaitre_de_barre(app):
    etat = _etat(n_electrodes=2)
    etat.plan = {"trajectories_t1": []}
    assert _Controleur(etat).textes()["lbl_ElectrodesCount"] == "2 electrodes"


# ------------------------------- le contour rose du bouton Save


class _Page:
    SAVED_PATHS = None
    SAVED_ALL_PATHS = None

    def __init__(self, state):
        self.state = state


def _drapeaux(**chemins):
    from neuxelec.pages.files_page import FilesPage

    etat = AppState()
    for nom, valeur in chemins.items():
        setattr(etat, nom, valeur)

    page = _Page(etat)
    page.SAVED_PATHS = FilesPage.SAVED_PATHS
    page.SAVED_ALL_PATHS = FilesPage.SAVED_ALL_PATHS
    return FilesPage._saved_flags(page)


def test_aucun_bouton_n_est_marque_au_depart():
    assert not any(_drapeaux().values())


def test_enregistrer_le_plan_marque_son_bouton():
    """La demande : le contour rose comme les autres apres un Save."""
    assert _drapeaux(plan_trajectories_path="C:/x/plan.txt")["btn_save_plan"]


def test_l_irm_de_planification_seule_suffit():
    """Un plan deja dans l'espace de MRI 1 n'ecrit pas d'image."""
    assert _drapeaux(plan_mri_in_t1_path="C:/x/planningMRI.nii.gz")["btn_save_plan"]


def test_le_plan_ne_marque_pas_save_all():
    """Save all parle des sorties de coregistration, pas du plan."""
    drapeaux = _drapeaux(plan_trajectories_path="C:/x/plan.txt")
    assert drapeaux["btn_save_plan"]
    assert not drapeaux["btn_save_all"]


def test_une_coregistration_marque_son_bouton_et_save_all():
    drapeaux = _drapeaux(ct_coreg_path="C:/x/ct.nii.gz")
    assert drapeaux["btn_save_ct"]
    assert drapeaux["btn_save_all"]
    assert not drapeaux["btn_save_plan"]


def test_chaque_bouton_connu_a_sa_condition():
    """Un bouton oublie dans la table ne s'allumerait jamais."""
    from neuxelec.pages.files_page import FilesPage

    attendus = {
        "btn_save_t2", "btn_save_fmri", "btn_save_ct", "btn_save_pet",
        "btn_save_ictal", "btn_save_interictal", "btn_save_siscom",
        "btn_save_brainmask", "btn_save_plan",
    }
    assert set(FilesPage.SAVED_PATHS) == attendus

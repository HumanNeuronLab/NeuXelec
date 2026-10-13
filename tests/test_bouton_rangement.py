"""Le rangement est atteignable, et il sait de quel dossier il parle.

La logique et la fenetre sont testees a cote. Reste ce qui les relie : un
bouton sous les enregistrements, et la facon dont NeuXelec devine le
dossier du patient. S'il se trompait de dossier, il listerait les
fichiers de quelqu'un d'autre.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from neuxelec.pages.files_page import FilesPage  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class _Ui(QWidget):
    """Le minimum que le bouton cherche : la carte des enregistrements."""

    def __init__(self):
        super().__init__()
        self.card = QFrame(self)
        self.card.setObjectName("cardFilesToSave")
        self.layout_card = QVBoxLayout(self.card)
        self.layout_card.addWidget(QPushButton("Save all"))


def _page(qt_app, **champs):
    page = FilesPage.__new__(FilesPage)
    page.ui = _Ui()

    class _State:
        pass

    page.state = _State()
    for nom in ("project_path", "t1_path", "t1_source_path", "last_browse_dir"):
        setattr(page.state, nom, champs.get(nom))
    return page


# ----------------------------------------------------- le bouton existe


def test_le_bouton_se_pose_sous_les_enregistrements(qt_app):
    page = _page(qt_app)

    page._install_tidy_button()

    assert page.btn_tidy_folder.text() == "Tidy up this folder..."
    assert page.ui.layout_card.indexOf(page.btn_tidy_folder) >= 0


def test_sans_la_carte_le_bouton_ne_fait_pas_tomber_la_page(qt_app):
    """Le .ui n'est pas modifie par cette fonction : si la carte changeait
    de nom, la page doit s'ouvrir quand meme, sans le bouton."""
    page = _page(qt_app)
    page.ui.card.setObjectName("autre_chose")

    page._install_tidy_button()

    assert not hasattr(page, "btn_tidy_folder")


# ----------------------------------------------------- quel dossier


def test_le_projet_designe_le_dossier(qt_app, tmp_path):
    projet = tmp_path / "patient" / "projet.json"
    projet.parent.mkdir()
    projet.write_text("{}", encoding="utf-8")
    page = _page(qt_app, project_path=str(projet), t1_path=r"D:\ailleurs\T1.nii")

    assert page._patient_folder() == str(projet.parent)


def test_sans_projet_l_image_sert_de_reference(qt_app, tmp_path):
    t1 = tmp_path / "images" / "T1.nii.gz"
    t1.parent.mkdir()
    t1.write_bytes(b"x")
    page = _page(qt_app, t1_path=str(t1))

    assert page._patient_folder() == str(t1.parent)


def test_un_dossier_donne_tel_quel_est_garde(qt_app, tmp_path):
    page = _page(qt_app, last_browse_dir=str(tmp_path))

    assert page._patient_folder() == str(tmp_path)


def test_sans_rien_il_n_y_a_pas_de_dossier(qt_app):
    assert _page(qt_app)._patient_folder() is None


def test_sans_dossier_le_rangement_le_dit_au_lieu_d_ouvrir(qt_app, monkeypatch):
    page = _page(qt_app)
    page._dialog_parent = lambda: None
    dits = []
    monkeypatch.setattr(
        "neuxelec.ui.neuxelec_message_dialog.NeuXelecMessageDialog.information",
        classmethod(lambda cls, parent, titre, message: dits.append(message)),
    )

    page.open_folder_tidy()

    assert dits and "No patient folder" in dits[0]

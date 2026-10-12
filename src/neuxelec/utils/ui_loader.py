"""Charger le .ui, et rendre absolus les chemins d'images de sa feuille.

POURQUOI TOUCHER A LA FEUILLE DE STYLE

Qt resout un ``url()`` relatif contre le **repertoire courant**, et non
contre le .ui qui le porte. La feuille de NeuXelec en compte treize :
la croix de ses cases a cocher et les fleches de ses boites a compteur.
Lance depuis un autre dossier que la racine du projet, l'application
perdait donc ces images, sans rien signaler : une case cochee et une
case vide se ressemblaient.

Le paquet PyInstaller s'en tirait par un ``os.chdir(_MEIPASS)`` au
demarrage, qui ne dit pas son nom et ne protege pas le mode developpe.
Resoudre les chemins une fois au chargement vaut mieux : la feuille
devient independante du repertoire d'ou l'on lance.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader

from .resources import resource_path

#: ``url(x)``, ``url('x')`` et ``url("x")``.
_URL = re.compile(r"""url\(\s*(['"]?)([^)'"]+)\1\s*\)""")

def _est_absolu(chemin: str) -> bool:
    """Racine POSIX, lettre de lecteur Windows, ou ressource Qt compilee."""
    if not chemin:
        return True
    if chemin[0] in ("/", "\\", ":"):
        return True
    return len(chemin) > 1 and chemin[1] == ":" and chemin[0].isalpha()


def absolutise_stylesheet_urls(feuille: str) -> str:
    """Rendre absolus les ``url()`` relatifs d'une feuille de style."""
    if not feuille or "url(" not in feuille:
        return feuille

    def remplacer(m: re.Match) -> str:
        chemin = m.group(2).strip()
        if _est_absolu(chemin):
            return m.group(0)
        return "url(%s)" % Path(resource_path(chemin)).as_posix()

    return _URL.sub(remplacer, feuille)


def load_ui(ui_path: str | Path, parent=None):
    """Load a Qt Designer `.ui` file using QUiLoader."""
    path = Path(ui_path)
    qfile = QFile(str(path))

    if not qfile.open(QFile.ReadOnly):
        raise RuntimeError(f"Cannot open UI file: {path}")

    loader = QUiLoader()
    widget = loader.load(qfile, parent)
    qfile.close()

    if widget is None:
        raise RuntimeError(f"Failed to load UI: {path}")

    try:
        feuille = widget.styleSheet()
        if feuille:
            widget.setStyleSheet(absolutise_stylesheet_urls(feuille))
    except Exception:
        # Une feuille non reecrite reste la feuille d'origine : les
        # images manqueront peut-etre, mais la fenetre s'ouvre.
        pass

    return widget

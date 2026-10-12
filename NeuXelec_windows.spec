# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

project_root = Path(SPEC).resolve().parent
src_dir = project_root / "src"
entry_script = project_root / "scripts" / "run_neuxelec.py"
icon_file = project_root / "resources" / "images" / "brain_logo.ico"

# Application data required at runtime.
datas = [
    (str(project_root / "resources"), "resources"),
    (str(project_root / "templates"), "templates"),
    (str(src_dir / "neuxelec" / "utils" / "FreeSurferColorLUT.txt"), "neuxelec/utils"),
    (str(src_dir / "neuxelec" / "utils" / "electrodes_ref.json"), "neuxelec/utils"),
    (str(src_dir / "neuxelec" / "utils" / "electrodes_ref.txt"), "neuxelec/utils"),
]

# ANTs executables and MNI/template files.
#
# What is shipped is chosen file by file, not by copying tools/ wholesale.
# tools/ants holds 99 executables for 914 MB and NeuXelec starts three of them,
# 45 MB in total: every installer and every update carried 869 MB that no code
# path can reach. The three below are the complete list, taken from every call
# site of _ants_exe, which is the only way a binary is ever started here and is
# always given a literal name. Nothing is built at run time, so this list cannot
# silently fall out of date: a name that is not here is a name nothing calls.
#
# Same for the templates. They are opened by their exact name from
# tools/templates, so the archived copies kept alongside in old_one/, to_keep/
# and parcel1/ are unreachable, and that is another 64 MB.
#
# Nothing is deleted from the working tree, only left out of the bundle.
tools_dir = project_root / "tools"
if not tools_dir.exists():
    raise FileNotFoundError(
        "Missing tools directory. Restore tools/ before building NeuXelec."
    )

ANTS_EXECUTABLES = (
    "antsRegistration.exe",
    "antsApplyTransforms.exe",
    "antsApplyTransformsToPoints.exe",
)
for _name in ANTS_EXECUTABLES:
    _binary = tools_dir / "ants" / _name
    if not _binary.is_file():
        raise FileNotFoundError(
            f"Missing {_binary}. NeuXelec cannot coregister without it."
        )
    datas.append((str(_binary), "tools/ants"))

# Everything sitting directly in tools/templates, and only that: the loader
# never descends into a subfolder.
#
# With one exception, and it is a licensing one rather than a technical one.
# template_parcellation2 is the Brainnetome Atlas, granted to academic and
# not-for-profit users "for use for non-commercial purposes", with share alike,
# and a commercial licence has to be asked for separately. GPL-3.0 section 7
# forbids adding a restriction of that kind to a covered work, so shipping it
# would quietly narrow what someone may do with NeuXelec, which is the opposite
# of what its licence promises. It stays in the working tree and is left out of
# the installer; whoever wants it fetches it from atlas.brainnetome.org and
# accepts those terms in their own name.
EXCLUDED_TEMPLATES = (
    "template_parcellation2.nii.gz",
    "template_parcellation2.nii",
    "template_parcellation2_lut.tsv",
)
_templates_dir = tools_dir / "templates"
_templates = sorted(
    p for p in _templates_dir.iterdir()
    if p.is_file() and p.name not in EXCLUDED_TEMPLATES
)
if not _templates:
    raise FileNotFoundError(f"No template file in {_templates_dir}.")
for _template in _templates:
    datas.append((str(_template), "tools/templates"))

# Third-party licences travel with the binaries they cover. ANTs is Apache-2.0,
# whose section 4 requires the licence to accompany any redistribution, and the
# templates carry their own attribution terms.
_licences = project_root / "licenses"
if _licences.is_dir():
    datas.append((str(_licences), "licenses"))

# Explicitly collect scientific/3D packages with dynamic modules and data files.
# neuxelec.help is only imported from inside methods (User guide, guided tour),
# so it is listed here to be certain it reaches the bundle.
hiddenimports = [
    "neuxelec.help",
    "neuxelec.help.content",
    "neuxelec.help.tour",
    "neuxelec.help.user_guide_dialog",
    # Same reason: the relocation dialog is imported inside the project-opening
    # function, only when a file is missing.
    "neuxelec.project_paths",
    "neuxelec.ui.relocate_files_dialog",
]
binaries = []
for package_name in (
    "pyvista",
    "pyvistaqt",
    "vtk",
    "skimage",
    "scipy",
    "matplotlib",
    "nibabel",
    "SimpleITK",
    "openpyxl",
    "imageio",
):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package_name)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [str(entry_script)],
    pathex=[str(src_dir), str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pytest",
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NeuXelec",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_file),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="NeuXelec",
)

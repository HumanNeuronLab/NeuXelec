"""Single source of the NeuXelec documentation.

Three renderings share this module:

* the **User guide** window (``User guide`` button in the left menu, or F1),
* the **guided tour** shown on first launch (spotlight over the interface),
* the **PDF manual** published on the website and on GitHub.

Writing rules, so the three stay readable:

* English only, short sentences, no marketing;
* a section explains *what it is for*, then *how to do it*, then *what to watch
  out for*;
* a tour step is at most three lines: it points at something, it does not
  replace the manual.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Keyboard shortcuts and mouse gestures (also rendered as a table below)
# ---------------------------------------------------------------------------
#: (context, keys, action)
SHORTCUTS: list[tuple[str, str, str]] = [
    ("Anywhere", "F1", "Open this user guide"),
    ("Anywhere", "Right click", "Open the options of the view under the cursor"),
    ("Reconstruction, review", "Wheel", "Zoom the three views together"),
    ("Reconstruction, review", "Ctrl + wheel", "Move one slice at a time"),
    ("Reconstruction, review", "Left click or drag", "Move the crosshair"),
    ("Reconstruction, review", "Shift + left drag", "Pan, once zoomed in"),
    ("Reconstruction, review", "Double click", "Reset that view"),
    ("Reconstruction", "Ctrl+D", "Send the crosshair to the 3D view as a marker"),
    ("Reconstruction", "Ctrl+Z", "Hide that 3D marker"),
    ("Oblique slice", "Wheel", "Zoom the slice"),
    ("Oblique slice", "Shift + wheel", "Move the plane 1 mm along its normal"),
    ("Oblique slice", "Left drag", "Pan the slice"),
    ("Oblique slice", "Ctrl + left drag", "Rotate the plane around the electrode axis"),
    ("Oblique slice", "Double click", "Back to the plane of the electrode"),
    ("3D view", "Left drag", "Rotate the scene"),
    ("3D view", "Wheel", "Zoom"),
    ("3D view", "Middle drag, or Shift + left drag", "Pan"),
    ("3D view", "Double click", "Reset the camera on the visible plane"),
    ("3D view", "Ctrl+F", "Back to Reconstruction, at the 3D marker"),
    ("3D view", "Esc", "Leave full screen"),
    ("Parcellation table (MNI)", "Ctrl+F", "Search a region"),
    ("Electrode list", "Right click", "Rename, colour, labels, projection, delete"),
]


def _shortcut_table_html() -> str:
    # The alternating class is ignored by the dark window; it shades one row out
    # of two in the printed manual.
    rows = "\n".join(
        "<tr{}><td>{}</td><td><b>{}</b></td><td>{}</td></tr>".format(
            " class='alt'" if index % 2 else "", ctx, keys, action
        )
        for index, (ctx, keys, action) in enumerate(SHORTCUTS)
    )
    return (
        "<table width='100%' cellspacing='0' cellpadding='6'>"
        "<tr><th align='left'>Where</th><th align='left'>Keys</th>"
        "<th align='left'>Action</th></tr>"
        f"{rows}</table>"
    )


# ---------------------------------------------------------------------------
# Manual
# ---------------------------------------------------------------------------
@dataclass
class Section:
    """One chapter of the manual, rendered as HTML in all three outputs."""

    id: str
    title: str
    body: str
    figure: str | None = None          # file name under resources/docs/figures
    caption: str = ""


MANUAL_SECTIONS: list[Section] = [
    Section(
        id="overview",
        title="Overview",
        body="""
<p>NeuXelec brings every image of a SEEG patient into one space, reconstructs
the implanted electrodes and exports coordinates that other tools can read.
The work always follows the same order.</p>
<ol>
<li><b>Files &amp; coregistration</b> - import the images, align them on MRI 1,
review each alignment and save the results.</li>
<li><b>Reconstruction</b> - place the electrodes on the post-implantation CT.</li>
<li><b>Oblique slice</b> - inspect the contacts along the axis of an electrode.</li>
<li><b>3D view</b> - see the electrodes, the brain surface and the functional
maps together.</li>
</ol>
<p>The left menu carries the patient identifier, <b>Save project</b>, this
<b>User guide</b>, and the four pages. A project file (<code>.json</code>)
remembers the paths of the images, the electrodes and the display settings; it
does <b>not</b> contain the images themselves.</p>
<p><b>Watch out.</b> Validating a coregistration keeps it for the session only.
It is written to disk when you click the matching <i>Save</i> button, or
<i>Save all validated</i>. NeuXelec warns you when you save the project with
work that is not on disk yet.</p>
""",
    ),
    Section(
        id="files",
        title="Files and coregistration",
        body="""
<p>Everything starts here. MRI 1 is the reference: every other image is aligned
on it, and all coordinates are expressed in its space.</p>

<h3>1. Import the data</h3>
<p><b>Load Imaging</b> takes several files at once (NIfTI, DICOM folder,
FreeSurfer <code>.mgz</code>) and asks you to assign each one to a modality:
MRI 1, MRI 2, CT, PET, ictal and inter-ictal SPECT, SISCOM, fMRI. <b>Load
Parcellation</b>, <b>Load Surfaces</b> and <b>Load Planning</b> take the atlas
volumes, the pial surfaces and brain mask, and a NeuroInspire
<code>.nip</code> plan.</p>
<p>Images are cleaned on import (intensity sanitising, 1 mm isotropic for MRI 1)
and the cleaned copy becomes the file NeuXelec uses.</p>

<h3>2. The cockpit</h3>
<p>The cockpit is the state of the patient at a glance. <b>Imaging</b> is split
into <b>Structural</b> (MRI 1, MRI 2, CT) and <b>Functional</b> (PET, SPECT,
SISCOM, fMRI), followed by parcellations, surfaces and the plan. A grey dot
means missing, blue means loaded and waiting for coregistration, green means
coregistered or available. Hovering a row shows the full path of the file.</p>

<h3>3. Align a modality</h3>
<p>Tick exactly one modality and press <b>Perform coregistration</b>. NeuXelec
uses ANTs: rigid then affine for the other modalities, and <b>rigid only for the
CT</b>, so the geometry of the electrodes is never scaled. Then press <b>Review
coregistration</b>: the reference is green, the moving image is red, the wheel
zooms, Ctrl+wheel moves through the slices, and a manual console lets you
correct the alignment by hand before accepting it.</p>

<h3>4. Brain mask and SISCOM</h3>
<p><b>Generate brain mask</b> produces the mask used for 3D rendering and for
cropping the functional overlays. <b>Generate SISCOM</b> computes the
ictal minus inter-ictal map once both SPECT are validated.</p>

<h3>5. Save</h3>
<p>Each validated output has its own <i>Save</i> button, and <b>Save all
validated</b> writes everything in one folder. The button keeps a rose outline
once the file exists on disk.</p>

<h3>Export</h3>
<p>The export dialog writes the contact coordinates as TXT, CSV, TSV, JSON,
Cartool ELS or iELVIS, in LPS or RAS, and can produce a valid <b>BIDS</b> folder
with <code>electrodes.tsv</code>, the anatomical labels of every contact and,
optionally, the other coregistered images. BIDS is written either in the native
T1 space or in MNI152 space. The <b>Deface</b> option, available for the native
BIDS export, removes the face, eyes, nose, mouth and ears from the exported
images; the brain is never touched.</p>
""",
    ),
    Section(
        id="reconstruction",
        title="Reconstruction",
        body="""
<p>This page turns the post-implantation CT into a list of contacts. An
electrode is reconstructed from two picks.</p>
<ol>
<li>Choose the <b>electrode reference</b> (the DIXI model, or <i>Other</i> for a
custom one), give the electrode a name and a hemisphere.</li>
<li>Click the <b>deepest contact</b>, then a <b>second contact</b> further out
along the same shaft. NeuXelec places every remaining contact from the geometry
of the reference.</li>
</ol>
<p>The contacts appear in the shared electrode list, and stay editable: right
click an electrode to rename it, change its colour, show or hide its labels,
project it on the surface, or delete it. A right click on a contact shows it in
the coronal, axial or sagittal slice, edits its coordinates, or deletes it.</p>

<h3>Moving around the three views</h3>
<p>A left click, or a left drag, moves the crosshair. The wheel zooms the three
views together, Ctrl+wheel moves one slice at a time, Shift+left drag pans once
you are zoomed in, and a double click resets that view. <b>Ctrl+D</b> sends the
current crosshair to the 3D view as a marker and switches to that page;
<b>Ctrl+Z</b> hides the marker again, and <b>Ctrl+F</b> in the 3D view brings you
back here at the marker.</p>

<h3>Custom electrodes</h3>
<p><i>Other</i> opens a small editor: number of contacts visible on the shaft,
contacts that are not connected (using a print-range syntax, contact 1 being the
deepest), and variable spacing such as <code>7x2, 10x3.5</code>. A live diagram
shows the result, unconnected contacts in grey. The reference is remembered for
the next patients, and a right click on the list deletes one you added.</p>

<h3>Using an implantation plan</h3>
<p>When a NeuroInspire <code>.nip</code> plan is loaded, the labelling is
proposed for you. As soon as you click the <b>deepest contact</b>, NeuXelec
ranks the planned trajectories of that hemisphere by distance to your click and,
if the closest one is <b>within 12 mm</b>, asks: <i>Closest planned electrode to
this deep contact ... Use this label and reference?</i></p>
<ul>
<li><b>Use it</b> fills the electrode name, the hemisphere and the DIXI
reference of the plan.</li>
<li><b>Choose another</b> lists the other planned trajectories, sorted by
distance, when the nearest one is not the right one.</li>
<li><b>No</b> keeps your manual labelling.</li>
</ul>
<p>A left-hemisphere click can only match a left-hemisphere plan electrode, and
the proposal never appears once you have typed a name yourself. After the second
pick, if the axis you drew differs from the planned direction by more than 25
degrees, or if another trajectory fits it better, NeuXelec says so and offers to
relabel the electrode.</p>
<p>The plan never moves your picks: it only proposes the labelling. The contacts
always come from the CT.</p>
""",
    ),
    Section(
        id="oblique",
        title="Oblique slice",
        body="""
<p>Two slices cut along the axis of the electrodes you tick in the list, which
is the only way to see every contact of a shaft at once.</p>

<h3>Moving the plane</h3>
<p>The wheel zooms and a left drag pans. <b>Ctrl+left drag</b> turns the plane
around the axis of the electrode, and <b>Shift+wheel</b> translates it along its
own normal, one millimetre per notch, to look at what lies beside the shaft. A
double click returns to the plane of the electrode.</p>

<h3>Overlays</h3>
<p>Each card switches one layer on: MRI, CT, PET, SPECT, SISCOM, fMRI,
parcellations. A parcellation and a functional overlay are mutually exclusive,
so the colours stay readable. Every card carries its own opacity and threshold;
an fMRI threshold left at <i>auto</i> is derived from the map itself.</p>

<h3>Quick tools</h3>
<p>The small arrow in the corner of each slice opens the quick tools: save a
screenshot (also copied to the clipboard), export a GIF that turns the plane
around the electrode, save and restore a slice position, remove the black
background, and rotate the image by 45, 90, 135 or 180 degrees.</p>

<h3>Contacts table</h3>
<p>For the electrodes on screen, the table gives, per contact, the anatomical
region and how much of its neighbourhood belongs to it. The number is the
<b>SEEG2parc</b> measure: the share of the 3x3x3 voxel cube centred on the
contact, each of the 27 neighbours weighted by one over its distance to the
centre. The regions are sorted, and the table shows the dominant one. Hovering a
row lists every region the contact straddles with its own share; hovering a
column header explains the column. These are the values exported to BIDS.</p>

<h3>White matter and wmparc</h3>
<p>An <code>aparc+aseg</code> parcellation labels the cortex gyrus by gyrus but
puts every cerebral white-matter voxel under one generic label, so a contact in
white matter would only ever be reported as <i>white matter</i>. FreeSurfer and
FastSurfer also write <code>wmparc</code>, which splits that white matter per
gyrus (<code>wm-lh-superiortemporal</code>, and so on) plus
<i>Unsegmented white matter</i> for the deep white matter.</p>
<p>NeuXelec looks for a <code>wmparc</code> file <b>next to the parcellation you
loaded</b>, from the same FreeSurfer run, and substitutes it for the generic
white-matter label, exactly as SEEG2parc and Voxeloc do. Nothing to load by
hand: put the parcellation where FreeSurfer wrote it and the white-matter
contacts become informative, in the table and in the BIDS export alike. Without
that file, everything still works, and a white-matter contact simply reads
<i>Left</i> or <i>Right-Cerebral-White-Matter</i>.</p>
""",
    ),
    Section(
        id="view3d",
        title="3D view",
        body="""
<p>The scene shows the brain surface, the electrodes and the slice planes. A
left drag rotates, the wheel zooms, a middle drag pans, and a double click
resets the camera on the visible plane. The button in the corner of the scene
switches to full screen, and Esc leaves it. <b>Ctrl+F</b> goes back to the
Reconstruction page at the position of the 3D marker.</p>

<h3>Panels</h3>
<p>The panels under the scene control the brain (mask, pial surfaces,
isosurface), the electrodes, the three slice planes, and each functional
overlay: PET, SPECT, SISCOM and fMRI, with threshold, opacity and minimum
cluster size.</p>

<h3>Quick tools</h3>
<p>The arrow in the corner of the scene opens the quick tools: screenshot,
rotating GIF around X, Y or Z, the standard camera views (anterior, posterior,
left, right and two obliques), a camera position saved in the project, and a
transparent background for figures.</p>

<h3>Functional maps</h3>
<p>An fMRI activation can be shown as a blob, projected on the pial surface, or
painted on the slice planes. <b>Min cluster (mm&sup3;)</b> hides clusters smaller
than the given volume, which removes isolated noise; the value is shared with
the oblique page, and <i>Off</i> keeps every voxel above the threshold.
<b>Functional overlays: cortex only</b>, in the right-click menu, restricts PET,
SPECT, SISCOM and fMRI to the cortical ribbon; it needs parcellation 1 and
applies to the oblique page as well.</p>

<h3>Markers</h3>
<p>A right click on a slice adds an anatomical marker, which can be renamed,
hidden or exported.</p>
""",
    ),
    Section(
        id="rightclick",
        title="Right-click menus",
        body="""
<p>Each view carries its options behind a right click, grouped in labelled
sections. An entry only appears when it applies: no <i>fMRI</i> section without
an fMRI, no <i>cortex only</i> without a parcellation, no <i>Planning</i>
without a plan. Everything the menus can offer is listed below.</p>

<h3>3D view, right click in the scene</h3>
<p><b>MARKERS</b>: <i>Marker list</i>; <i>Add marker</i> when the click lands on
a slice plane; on an existing marker <i>Edit marker</i>, <i>Hide marker</i>,
<i>Export marker</i>, <i>Delete marker</i>; <i>Show hidden markers</i>.</p>
<p><b>OVERLAY COLORS</b>: <i>Color PET</i>, <i>Color SISCOM</i>, <i>Color
fMRI</i>, <i>Color CT</i>, <i>Color Ictal SPECT</i>, <i>Color Inter-ictal
SPECT</i>.</p>
<p><b>fMRI</b>: <i>Plot</i> or <i>Hide fMRI blob</i>; <i>Keep</i> or <i>Crop
fMRI blob through slices</i>; <i>Project</i> or <i>Hide fMRI on surface</i>.</p>
<p><b>DISPLAY</b>: <i>Add</i> or <i>Remove color scale</i>; <i>Add</i> or
<i>Remove frame</i> around the slice planes; <i>Functional overlays: cortex
only</i> or <i>whole brain</i>; <i>Keep electrodes visible through slices</i>;
<i>Don't crop SISCOM blob through slices</i>; <i>Render Brain</i>, which opens
the lighting and material settings of the surface.</p>
<p><b>PLANNING</b>: <i>Plot</i> or <i>Hide planning electrodes</i>.</p>
<p><b>MNI ATLAS</b>: <i>Load MNI electrodes.tsv</i>, <i>Add</i> or <i>Remove MNI
T1 slices</i>, <i>Parcellation table</i>. In MNI mode the overlay colours and
<i>Render Brain</i> step aside, since the scene is the template, not the
patient.</p>
<p><b>PIAL SURFACES</b>: <i>Add</i> or <i>Remove LH</i>, <i>Add</i> or
<i>Remove RH</i>.</p>

<h3>Oblique slice, right click on a slice</h3>
<p><b>OVERLAY COLORS</b>: <i>Color PET</i>, <i>Color SISCOM</i>, <i>Color
fMRI</i>, <i>Color Ictal SPECT</i>, <i>Color Inter-ictal SPECT</i>.</p>
<p><b>DISPLAY</b>: <i>Add</i> or <i>Remove color scale</i>; <i>Functional
overlays: cortex only</i> or <i>whole brain</i>, which is the same setting as in
the 3D view.</p>

<h3>Electrode list</h3>
<p>On an <b>electrode</b>: <i>Add</i> or <i>Remove contact labels</i> and
<i>Add</i> or <i>Remove electrode label</i> (Oblique slice and 3D view);
<i>Add</i> or <i>Remove surface projection</i> (3D view only); <i>Rename
electrode</i>; <i>Color</i>; <i>Delete electrode</i>. With several electrodes
selected, renaming steps aside and the deletion becomes <i>Delete N
electrodes</i>.</p>
<p>On a <b>contact</b>: <i>Add</i> or <i>Remove label</i> (Oblique slice and 3D
view); <i>Show coronal slice</i>, <i>Show axial slice</i>, <i>Show sagittal
slice</i> (3D view only); <i>Edit coordinates</i> (Reconstruction only);
<i>Delete contact</i>, or <i>Delete N contacts</i>.</p>
<p>In View Only mode, renaming and deleting are hidden; the colour, the labels
and the projection stay available.</p>

<h3>Electrode reference, on the Reconstruction page</h3>
<p>A right click on the reference selector deletes a reference you created
yourself. The DIXI references that ship with NeuXelec cannot be deleted, and
when you have not added any the menu simply says <i>No custom reference to
delete</i>.</p>

<h3>Marker list</h3>
<p><i>Show on axial slice</i>, <i>Show on coronal slice</i>, <i>Show on sagittal
slice</i>; <i>Edit marker</i>; <i>Hide marker</i> or <i>Show marker</i>;
<i>Export marker</i>; <i>Delete marker</i>.</p>

<h3>MNI electrodes, in the MNI list</h3>
<p>On an imported patient: <i>Color</i>, <i>Add</i> or <i>Remove electrode
names</i>, <i>Add</i> or <i>Remove patient name</i>, <i>Delete patient</i>. On
one electrode: <i>Color</i>, <i>Add</i> or <i>Remove labels</i>. On a contact:
<i>Add</i> or <i>Remove label</i>, <i>Show coronal</i>, <i>axial</i> or
<i>sagittal slice</i>.</p>
""",
    ),
    Section(
        id="formats",
        title="File formats",
        body="""
<p><b>Images</b>: NIfTI (<code>.nii</code>, <code>.nii.gz</code>), DICOM folders,
FreeSurfer <code>.mgz</code> and <code>.mgh</code>.</p>
<p><b>fMRI</b>: a statistical map (t, z, contrast), or a colour fusion exported
by the scanner, from which NeuXelec recovers the activation. A raw 4D BOLD
series cannot be displayed: it needs a first-level analysis first.</p>
<p><b>Parcellations</b>: any integer label volume. FreeSurfer atlases
(<code>aparc+aseg</code>, DKT, Destrieux) are named automatically; another atlas
is used as is, and you may load its own lookup table. A <code>wmparc</code> file
sitting next to an <code>aparc+aseg</code> is picked up on its own and refines
the white-matter labels.</p>
<p><b>Plan</b>: NeuroInspire <code>.nip</code>.</p>
<p><b>Export</b>: CSV, TSV, BIDS (<code>electrodes.tsv</code> plus derivatives).</p>
""",
    ),
    Section(
        id="shortcuts",
        title="Keyboard shortcuts",
        body="<p>The slice views and the 3D scene do not answer to the same "
        "gestures, so the table gives them page by page.</p>"
        + _shortcut_table_html(),
    ),
]


# ---------------------------------------------------------------------------
# Guided tour
# ---------------------------------------------------------------------------
@dataclass
class TourStep:
    """One spotlight step.

    ``target`` is the objectName of the widget to highlight, or a list of them
    (they are then framed together). A step whose target does not exist or is
    hidden is skipped, so the tour also works on an empty session.
    """

    title: str
    body: str
    target: str | list[str] | None = None
    page: str | None = None           # objectName of the page to show first
    delay_ms: int = 0                 # extra wait after switching page
    extra: dict = field(default_factory=dict)


TOUR_STEPS: list[TourStep] = [
    TourStep(
        title="Welcome to NeuXelec",
        body="A short tour of the interface: the pages, the cockpit and where "
             "the options live. You can leave it at any time and replay it later.",
        target=None,
        page="pageFiles",
    ),
    TourStep(
        title="The four pages",
        body="Files and coregistration, Reconstruction, Oblique slice, 3D view. "
             "The work follows that order, from importing the images to the "
             "reconstructed electrodes.",
        target=["btn_menu_fileCoreg", "btn_menu_reconstruction",
                "btn_menu_obliqueSlice", "btn_menu_3Dview"],
        page="pageFiles",
    ),
    TourStep(
        title="Import the patient data",
        body="Select several files at once, then assign each one to its modality. "
             "NIfTI, DICOM folders and FreeSurfer volumes are all accepted.",
        target="btn_FilesCoreg_loadImaging",
        page="pageFiles",
    ),
    TourStep(
        title="The cockpit",
        body="The state of the patient at a glance: structural images, functional "
             "images, parcellations, surfaces and plan. Hover a row to see the "
             "full path of the file.",
        target="cardFilesStatusOverview",
        page="pageFiles",
    ),
    TourStep(
        title="Align on MRI 1",
        body="Tick one modality, run the coregistration, then review it. MRI 1 is "
             "the reference for every image and every coordinate.",
        target="cardCoregistration",
        page="pageFiles",
    ),
    TourStep(
        title="Save what you validated",
        body="A validated coregistration lives in the session only. It reaches the "
             "disk when you save it here, and the button then keeps a rose outline.",
        target="cardFilesToSave",
        page="pageFiles",
    ),
    TourStep(
        title="Reconstruct an electrode",
        body="Choose the electrode reference, name it, then click the deepest "
             "contact and a second one along the shaft. The other contacts follow "
             "from the geometry of the reference.",
        target=["comboReco_electrodeRef", "btnReco_pickDeepest",
                "btnReco_pickSecond", "btnReco_estimate"],
        page="pageReconstruction",
        delay_ms=400,
    ),
    TourStep(
        title="Slices along the electrode",
        body="Tick an electrode to cut along its axis and see every contact at "
             "once. The overlay panel switches CT, MRI, PET, SISCOM and fMRI on, "
             "one layer at a time.",
        target=["cardObliqueDisplay", "cardObliqueAnatomical", "cardObliquePET",
                "cardObliqueSISCOM", "cardObliquefMRI"],
        page="pageObliqueSlices",
        delay_ms=900,
    ),
    TourStep(
        title="The 3D scene",
        body="Brain surface, electrodes, slice planes and functional maps are "
             "switched on from these panels. In the scene above, left drag "
             "rotates, the wheel zooms, Ctrl+F goes full screen.",
        target=["card3DSurfaces", "card3DElectrodes", "card3DSlices",
                "card3DPET", "card3DSISCOM", "card3DfMRI"],
        page="page3DView",
        delay_ms=1200,
    ),
    TourStep(
        title="Right click carries the options",
        body="Every view hides its options behind a right click, grouped in "
             "labelled sections: overlay colours, display, fMRI, planning, "
             "surfaces.",
        target=None,
        page="page3DView",
        extra={"image": "menu_3d_sections.png"},
    ),
    TourStep(
        title="Everything is written down here",
        body="The user guide explains every page, every right-click menu and every "
             "shortcut. Press F1 at any time, or click this button.",
        target="btn_menu_userGuide",
        page="pageFiles",
    ),
]

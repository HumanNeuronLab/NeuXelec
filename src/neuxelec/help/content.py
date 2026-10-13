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
    (
        "3D view",
        "Ctrl + arrow + wheel",
        "Move a slice: up for axial, down for coronal, left for sagittal",
    ),
    ("3D view", "Ctrl+C + left drag", "Move the red crosshair marker"),
    (
        "3D view",
        "Left click, while placing a marker",
        "Leave the marker on the slice under the cursor; Esc or right click gives up",
    ),
    ("3D view", "Ctrl+F", "Back to Reconstruction, at the 3D marker"),
    ("3D view", "Esc", "Leave full screen"),
    ("Parcellation table (MNI)", "Ctrl+F", "Search a region"),
    ("Electrode list", "Right click", "Rename, colour, labels, projection, delete"),
    (
        "Electrode list",
        "Right click a contact",
        "Add a stimulation result, labels, slices, coordinates",
    ),
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
    figure: str | None = None  # file name under resources/docs/figures
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
<p>On top of that, electrical stimulation results are recorded by hand, one
card per stimulated pair, and read back on the brain in a mode of their own:
see <i>Stimulation results</i>.</p>
<p>The left menu carries the patient identifier, <b>Save project</b>, this
<b>User guide</b>, and the four pages. A project file (<code>.json</code>)
remembers the paths of the images, the electrodes and the display settings; it
does <b>not</b> contain the images themselves. It travels between computers:
see <i>Moving a project</i>.</p>
<p>The two stimulation windows speak <b>English and French</b>, chosen in
their title bar. The language changes what is shown, never what is stored: a
descriptor picked in French is saved in English, so two cards of the same
patient stay comparable.</p>
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

<h3>4. The implantation plan</h3>
<p><b>Load Planning</b> reads a NeuroInspire <code>.nip</code> file. When the
plan was made on another MRI, that image is registered on MRI 1 first, which
takes about three minutes and shows the usual progress. The alignment is then
presented for review, reference in green and planning MRI in red, exactly like
any other modality: <b>every trajectory of the plan rests on this one
registration</b>. A correction made by hand there is applied to the coordinates
of the trajectories, not only to the image. A right click on <b>Load
Planning</b> reopens that review later in the session.</p>

<h3>5. Brain mask and SISCOM</h3>
<p><b>Generate brain mask</b> produces the mask used for 3D rendering and for
cropping the functional overlays. It works by registering MRI 1 onto the
reference template and bringing the template's own mask back, which takes a few
minutes. That registration is the same one the MNI coordinates and the defacing
need, so it is computed once per patient and kept in the transforms folder: the
second feature to ask for it gets it in seconds. NeuXelec recomputes it if you
change MRI 1 or the template.</p>
<p><b>Generate SISCOM</b> computes the ictal minus inter-ictal map once both
SPECT are validated.</p>

<h3>6. Save</h3>
<p>Each validated output has its own <i>Save</i> button, and <b>Save all
validated</b> writes everything in one folder. The button keeps a rose outline
once the file exists on disk.</p>

<h3>7. What the modality leaves behind</h3>
<p>A CT arrives as a DICOM folder, becomes a NIfTI, then a cleaned copy, and
only then the volume resampled into MRI 1 that you save. Once that last file
exists the first three are usually of no further use, and after seven
modalities they are what makes a patient folder unreadable.</p>
<p>So the save itself asks. <b>Clean up CT</b> opens on the volume
you have just saved, which heads the list and has no tick box, and lists under
it everything else of that modality that is still on disk: the DICOM folder
with its size and its number of slices, the NIfTI of its conversion, the copy
NeuXelec reads, and an earlier aligned volume if you had saved one.</p>
<p><b>Nothing is ticked for you.</b> These are your files, the DICOM first of
all. Tick what you want gone, and the window says in one line how many items
that is and how much space. <i>Keep all</i> closes it and changes
nothing.</p>
<p>What is deleted goes to the recycle bin when Windows allows it. The project
is then pointed at the volume you saved, which is a perfectly good image of
that modality, already in the space of MRI 1: without that, the next opening
would ask for files that are gone. Save the project to record it.</p>
<p>The same question follows MRI 2, fMRI, PET, both SPECT, SISCOM and the
brain mask. A modality that has nothing left to offer simply confirms the
save.</p>

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
screenshot, export a GIF that turns the plane around the electrode, save and
restore a slice position, remove the black background, and rotate the image by
45, 90, 135 or 180 degrees.</p>
<p>A screenshot is written as a <b>PNG</b> or a <b>JPEG</b>, which are copied to
the clipboard as well, or as a <b>PDF</b> or an <b>SVG</b>. Those two keep the
contacts, their names and the colour bars as objects rather than pixels: they
stay sharp at any magnification, and a drawing program can move a label or
recolour a contact. The anatomy itself stays an image whatever the format,
since it is made of voxels, but it is written at its own resolution rather than
at the size of the window.</p>
<p><b>Remove background</b> applies on screen and to PNG, PDF and SVG
screenshots, where the transparency is real. A GIF cannot carry it: the format has no alpha channel,
and the skin fades gradually into the air, which one transparent colour cannot
reproduce. Asking for a GIF without a background therefore stops with an
explanation rather than quietly returning a black one. For an animation meant
for a slide, set a <i>Background color</i> instead: the air fades into the
colour of the slide and the picture reads as having no background at all.</p>

<h3>Contacts table</h3>
<p>For the electrodes on screen, the table gives, per contact, the anatomical
region and how much of its neighbourhood belongs to it. The number is the
<b>SEEG2parc</b> measure: the share of the 3x3x3 voxel cube centred on the
contact, each of the 27 neighbours weighted by one over its distance to the
centre. The regions are sorted, and the table shows the dominant one. Hovering a
row lists every region the contact straddles with its own share; hovering a
column header explains the column. These are the values exported to BIDS.</p>

<h3>Contacts in grey matter</h3>
<p>A depth electrode crosses grey and white matter alternately, and the contacts
that record what you are looking for sit in grey matter. <b>Contacts: grey
matter only</b>, in the right-click menu of either view, hides the others. The
test is the same SEEG2parc region the contacts table displays, so the filter can
never disagree with what you read in the table, and it keeps <b>every</b> grey
structure, not just the cortical ribbon: the hippocampus and the amygdala stay
visible, which would not be the case with a cortex restriction. A contact whose
label is unknown stays visible, because a hidden contact is one nobody looks at.
The entry appears only when a parcellation names grey regions, the filter is
shared between the oblique slice and the 3D view, and it never alters the
contacts you showed or hid by hand.</p>

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
<p>The 3D scene is written as an image, and not as a PDF or an SVG the way the
oblique slices are. The exporter that would do it renders the scene into a
picture and wraps that picture in the file: the result claims to be vector
without being one. A PNG at least says what it is.</p>

<h3>Functional maps</h3>
<p>An fMRI activation can be shown as a blob, projected on the pial surface, or
painted on the slice planes. <b>Min cluster (mm&sup3;)</b> hides clusters smaller
than the given volume, which removes isolated noise; the value is shared with
the oblique page, and <i>Off</i> keeps every voxel above the threshold.
<b>Functional overlays: cortex only</b>, in the right-click menu, restricts PET,
SPECT, SISCOM and fMRI to the cortical ribbon; it needs parcellation 1 and
applies to the oblique page as well.</p>

<h3>Markers</h3>
<p><b>Add marker</b> in the right-click menu arms the placement rather than
placing anything: the cursor becomes a cross, and the left click leaves the
marker on the slice under it. The window asking for its name, colour
and size opens afterwards, on a position you have already looked at. A right
click or Esc gives up. The marker remembers which slice it was dropped on.</p>
<p><b>Move marker</b>, on a marker, picks it back up: the same cross follows
the slice, and the click puts it down, on the same slice or another one. It
keeps its name, colour and size, so moving one is not filling it in again.</p>
<p>A marker can then be renamed or hidden from the marker list.
<b>Export all</b>, beside <i>Close</i> in that list, writes every marker of the
list into one text file, with the coordinates and the slice each was dropped
on.</p>

<h3>Stimulation results</h3>
<p>A right click in the scene opens <b>Stimulation results</b>: one tab to
filter what the scene shows, one tab holding a card per stimulation. See the
<i>Stimulation results</i> chapter.</p>
""",
    ),
    Section(
        id="stimulation",
        title="Stimulation results",
        body="""
<p>Electrical stimulation results are entered by hand, one card per stimulated
pair, and read back on the brain. Nothing is computed from the signal: what is
written down is what the examination found.</p>

<h3>Writing one down</h3>
<p>Two ways in, and they open the same window. A right click on a
<b>contact</b> in the electrode list, on any page, offers <b>Add stimulation
result</b>. Or, from the mode described below, the <b>+ Add a stimulation</b>
button in the <i>Stimulation cards</i> tab.</p>
<p>Both contacts of the pair are chosen in the window itself, so nothing has to
be aimed at beforehand. Bipolar stimulation between two adjacent contacts is
the standard, so the adjacent contact is already proposed; any other contact
can be typed, and is checked against the implantation. A pair that is not
adjacent, or that spans two electrodes, warns and is recorded all the same:
both are practised and neither has an established recommendation. Monopolar
stimulation is recorded with its reference. Only a contact stimulated against
itself is refused.</p>
<p>When a parcellation is loaded, both contacts are named automatically, with
the same construction as the oblique table and the BIDS export.</p>

<h3>The protocol</h3>
<p>Choosing the frequency fills the pulse width, the train duration and the
current with the values proposed for that protocol, and leaves alone any field
already typed into. The two modes are low frequency, 1 Hz, with long trains at
a constant current, and high frequency, 50 or 60 Hz, with short trains and the
current raised until after-discharges appear.</p>
<p>The frequency and the pulse width are recorded because milliamps alone do
not describe a stimulation: the same current at 1 Hz and at 50 Hz is two
different examinations, and the charge delivered is the current times the pulse
duration. Above the usual maximum the window says so rather than refusing, the
real limit depending on the surface area of the contact implanted.</p>
<p>Any of these four can be left unknown: the bottom of each field reads
<b>NA</b>, and the frequency offers it in its list. NA is not zero, and a card
says NA rather than inventing a number. A filter on current or frequency sets
such a card aside, since it can be neither above nor below a bound.</p>

<h3>What happened</h3>
<p>Discharges and seizures are separate questions, and several can be ticked
at once. A seizure is recorded at one of four levels: habitual and
electro-clinical, habitual aura alone without an EEG change, subclinical with
an EEG change and no symptom, or not habitual. Whether the patient's own event
was reproduced is asked separately, and so is the reproducibility of the
response on repeat stimulation.</p>
<p>The details of a discharge appear once there is one to describe: where it
was seen, whether it was remote from the stimulated contacts, how it evolved,
and whether the stimulation had to be interrupted.</p>

<h3>The responses</h3>
<p>A response is added as a block, so that several responses to one
stimulation each keep their own localisation. The eleven categories are motor,
language, somatosensory, visual, auditory, olfactory or gustatory, vestibular,
autonomic, affective, cognitive, and other. Each one offers its own
descriptors, and the question asked for the localisation follows the category:
where on the body for motor and somatosensory, which part of the visual field
for visual, which ear for auditory, and nothing at all for the others. A motor
response is asked first whether it was positive, a movement appearing, or
negative, an ongoing movement stopping.</p>
<p>Every list ends in <i>Other</i>, with a free text box: there is no standard
classification of evoked responses, so the vocabulary here is incomplete by
nature.</p>
<p>A pair tested without any response is recorded as such, with the current it
was pushed to. That is a result, not a missing one.</p>

<h3>The Stimulation Result mode</h3>
<p>A right click in the 3D scene offers <b>Mode: Stimulation Result</b>.
Entering it changes one thing and one thing only: the electrodes turn light
grey and their shaft disappears. Slice planes, overlays, the parcellation, the
brain surface and the camera all stay exactly as they were, and the contact
labels that were switched on stay switched on, in grey. A contact or an
electrode hidden by hand stays hidden.</p>
<p>The view takes a rose border, with a white <b>STIMULATION RESULTS</b> badge
and an <b>Esc</b> button in its top right corner. Leaving by that button, by
closing the window, or by leaving the 3D page puts the view back exactly as it
was: the state is remembered on the way in rather than recomputed.</p>
<p>With no filter set, every contact of the implantation is drawn in grey: that
grey is the map the results are read on. As soon as a filter is set, only the
contacts of the stimulations it keeps remain, so the view narrows down to what
was asked. A bipolar pair is drawn as a tube from one contact to the other,
where the current density peaks.</p>
<p>The MNI view is never affected.</p>

<h3>The three tabs</h3>
<p><b>Visualisation filters</b> decides what the scene draws: current,
frequency, kind of event, kind of response, and whether the patient's own event
was reproduced. Ticking two boxes inside one filter means either of them;
between filters, every active filter must be satisfied. Nothing ticked means
everything.</p>
<p><b>Appearance</b> decides what it looks like. The colour can follow what the
finding is worth, the kind of clinical response, one colour for all, or rules
of your own. A rule is a condition and a colour, and the first rule that
matches a stimulation wins, so their order counts; a rule is made from the
filters currently set, so a condition is written in one place only. Three sets
of rules come with the application and load in one click. The tube thickness,
the contact size, the opacity and the grey of the contacts are set here too,
and the legend below the colour choice always says what the current setting
means.</p>
<p><b>Stimulation cards</b> holds one card per stimulation, with the detail on
the right. A card prints only the fields that were filled in. It can be
corrected, deleted, or a new one added.</p>
<p>Both stimulation windows can be made full screen, reduced out of the way
without being closed, resized by their edges and corners, and switched between
English and French in their title bar.</p>
<h3>Taking them out</h3>
<p><b>Export all</b>, beside <i>Close</i> in the window bar, writes every
stimulation of the patient into one file, in the format the file name asks
for. A <b>.csv</b> or <b>.tsv</b> carries one row per stimulated
pair, with the responses joined into one cell, which is what a spreadsheet or
a colleague's script expects. A <b>.txt</b> prints the cards one after another,
for the patient file. A <b>.json</b> keeps the records exactly as the project
holds them, nested responses included, and is the only lossless one.</p>
<p>Nothing is recomputed on the way out: a field never filled in leaves its
cell empty, and a protocol that was not noted reads NA.</p>
<p>Cards and appearance settings are saved with the project.</p>
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
<p><b>MARKERS</b>: <i>Marker list</i>; <i>Add marker</i> as soon as a slice is
displayed, which arms the placement rather than placing anything; on an
existing marker <i>Edit marker</i>, <i>Move marker</i>, <i>Hide marker</i>,
<i>Export marker</i>, <i>Delete marker</i>; <i>Show hidden markers</i>.</p>
<p><b>MODE</b>: <i>Mode: Stimulation Result</i>, and once inside it,
<i>Leave mode: Stimulation Result</i>.</p>
<p><b>OVERLAY COLORS</b>: <i>Color PET</i>, <i>Color SISCOM</i>, <i>Color
fMRI</i>, <i>Color CT</i>, <i>Color Ictal SPECT</i>, <i>Color Inter-ictal
SPECT</i>.</p>
<p><b>fMRI</b>: <i>Plot</i> or <i>Hide fMRI blob</i>; <i>Keep</i> or <i>Crop
fMRI blob through slices</i>; <i>Project</i> or <i>Hide fMRI on surface</i>.</p>
<p><b>DISPLAY</b>: <i>Background color</i> and, once one is chosen,
<i>Reset background</i>; <i>Add</i> or <i>Remove color scale</i>; <i>Add</i> or
<i>Remove frame</i> around the slice planes; <i>Functional overlays: cortex
only</i> or <i>whole brain</i>; <i>Contacts: grey matter only</i> or <i>Contacts:
all</i>; <i>Keep electrodes visible through slices</i>;
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
<p><b>DISPLAY</b>: <i>Background color</i> and, once one is chosen,
<i>Reset background</i>; <i>Add</i> or <i>Remove color scale</i>; <i>Functional
overlays: cortex only</i> or <i>whole brain</i>; <i>Contacts: grey matter only</i>
or <i>Contacts: all</i>. The last two are shared with the 3D view; the background
is set per view.</p>

<h3>Choosing a background</h3>
<p>Both views are drawn on black by default. <i>Background color</i> replaces
that black with a colour of your choosing, which matters when a screenshot or an
animation has to sit on a slide: painted in the colour of the slide, the picture
reads as having no background at all, and a GIF cannot achieve that with
transparency because the format carries none.</p>
<p>In the <b>3D view</b> the colour is simply the ground behind the scene. In
the <b>Oblique slice</b> it does something less obvious, because there the black
around the head is not a canvas, it is the air of the scan. NeuXelec makes that
air transparent and lets the skin fade into the colour progressively, so no dark
outline is left around the head. Only the air that reaches the edge of the
picture is treated this way: air trapped inside the skull, in the sinuses or the
orbits, stays black, because it is anatomy.</p>
<p>The choice lives with the session, not with the project: reopening a patient
gives you black again. <i>Reset background</i> returns to it at any time.</p>

<h3>Electrode list</h3>
<p>On an <b>electrode</b>: <i>Add</i> or <i>Remove contact labels</i> and
<i>Add</i> or <i>Remove electrode label</i> (Oblique slice and 3D view);
<i>Add</i> or <i>Remove surface projection</i> (3D view only); <i>Rename
electrode</i>; <i>Color</i>; <i>Delete electrode</i>. With several electrodes
selected, renaming steps aside and the deletion becomes <i>Delete N
electrodes</i>.</p>
<p>On a <b>contact</b>: <i>Add</i> or <i>Remove label</i> (Oblique slice and 3D
view); <i>Show coronal slice</i>, <i>Show axial slice</i>, <i>Show sagittal
slice</i> (3D view only); <i>Add stimulation result</i>, on every page;
<i>Edit coordinates</i> (Reconstruction only);
<i>Delete contact</i>, or <i>Delete N contacts</i>.</p>
<p>In View Only mode, renaming, deleting and <i>Add stimulation result</i>
are hidden; the colour, the labels and the projection stay available. See
<i>View Only mode</i> for the whole of it.</p>

<h3>Load Planning, on the Files page</h3>
<p><i>Review plan alignment</i> reopens the comparison of the planning MRI with
MRI 1, so the registration every trajectory rests on can be checked again, and
corrected by hand if needed. The entry is greyed out until a plan is loaded, and
after a project is reopened, since the registered planning MRI only lives in the
session.</p>

<h3>Electrode reference, on the Reconstruction page</h3>
<p>A right click on the reference selector deletes a reference you created
yourself. The DIXI references that ship with NeuXelec cannot be deleted, and
when you have not added any the menu simply says <i>No custom reference to
delete</i>.</p>

<h3>Marker list</h3>
<p><i>Show on axial slice</i>, <i>Show on coronal slice</i>, <i>Show on sagittal
slice</i>; <i>Edit marker</i>; <i>Hide marker</i> or <i>Show marker</i>;
<i>Delete marker</i>. Exporting is the <i>Export all</i> button of the window,
not an entry of this menu.</p>

<h3>MNI electrodes, in the MNI list</h3>
<p>On an imported patient: <i>Color</i>, <i>Add</i> or <i>Remove electrode
names</i>, <i>Add</i> or <i>Remove patient name</i>, <i>Delete patient</i>. On
one electrode: <i>Color</i>, <i>Add</i> or <i>Remove labels</i>. On a contact:
<i>Add</i> or <i>Remove label</i>, <i>Show coronal</i>, <i>axial</i> or
<i>sagittal slice</i>.</p>
""",
    ),
    Section(
        id="viewonly",
        title="View Only mode",
        body="""
<p>A project can be opened to be read rather than worked on, to hand a case
over without any risk of changing it.</p>

<h3>What stays yours to play with</h3>
<p>Everything that only changes what you see: colours and opacities, the
filters and the appearance of the stimulation results, the camera, which slice
is shown, labels, surface projections, the parcellation, full screen. You can
explore a case exactly as in Edit mode.</p>
<p>Every export stays available too, since none of them writes anything back:
contact coordinates, BIDS, the stimulation results, the markers, screenshots in
PNG, PDF or SVG, and the rotating GIFs.</p>

<h3>What is not offered</h3>
<p>Anything that changes the patient's data. The Files and Reconstruction pages
are closed, so no image is imported, coregistered, deleted or renamed. In the
electrode list, renaming and deleting are hidden, and so is <i>Add stimulation
result</i>. In the 3D scene, <i>Add marker</i>, <i>Move marker</i>, <i>Edit
marker</i> and <i>Delete marker</i> are hidden, while <i>Marker list</i>,
<i>Hide marker</i> and the exports remain. The stimulation window shows its
cards and its filters, without the buttons that add, correct or delete one.
<i>Load MNI electrodes.tsv</i> and <i>Delete patient</i> are hidden from the
MNI list.</p>

<h3>The project file is never written</h3>
<p>And that is enforced where the writing happens, not on the Save button.
NeuXelec saves a project from six places, three of them on their own after a
renamed electrode, a saved camera or a stored slice position; a guard on the
button would have left those three writing. So the function that writes
refuses, the button is switched off to say so, and leaving a project no longer
asks whether you want to save it.</p>
<p>A consequence worth knowing: a colour or a camera you change in View Only
lasts as long as the session, and no longer.</p>
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
<p><b>Written next to your images</b>: a cleaned copy
<code>&lt;name&gt;_neuxelec.nii.gz</code> for every modality, the NIfTI of a
DICOM conversion, the coregistered volumes you save, the ANTs transforms, and
the by-products of the brain mask and the defacing. Saving a modality offers to
remove the ones that led to it.</p>
<p><b>Pictures</b>: PNG and JPEG everywhere, GIF for the rotating animations,
and PDF or SVG for an oblique slice, where the contacts and their names stay
objects. The 3D scene has no vector export: see the quick tools of the 3D
view.</p>
""",
    ),
    Section(
        id="portability",
        title="Moving a project",
        body="""
<p>The project file holds the location of every image, not the images. Copy it
to another computer, move the patient folder, change a drive letter, and those
locations no longer point anywhere.</p>
<p>NeuXelec checks them all when the project opens, before reading a single
image, and finds them again on its own whenever it can. It looks, in order: at
the stored location; at the same place relative to the project file; at the move
it has just learned from another file, so relocating one image relocates every
image that shared its folder; and finally by file name, around the project
folder and around the files already found. Your images do not have to sit in one
folder: each one is resolved on its own.</p>
<p>A file is only rebound when it really is the right file. Saving records the
size and the geometry of each image, and a candidate whose fingerprint does not
match is refused. Two patients whose MRI is called <code>T1.nii</code> is not
rare in a shared folder, and binding the wrong one would be far worse than
asking.</p>
<p><b>The window appears only when a file the project needs is still missing.</b>
It lists those files, where they used to be, and what was found instead. Point
NeuXelec at one of them with <i>Locate</i>, or let it search a folder you choose,
and everything that moved with it follows. <i>Save the new locations in the
project file</i> makes the repair permanent. Files that are only stored for
convenience, such as the original DICOM folder you deleted after conversion,
never open this window.</p>
<p><b>In practice.</b> Keep the <code>.json</code> inside the patient folder.
The whole folder then travels as one piece, between computers or between
colleagues, and reopens without a single question. Sending the project file
alone is also safe: no patient image leaves with it, and the person who receives
it points NeuXelec at their own copy of the images.</p>
""",
    ),
    Section(
        id="shortcuts",
        title="Keyboard shortcuts",
        body="<p>The slice views and the 3D scene do not answer to the same "
        "gestures, so the table gives them page by page.</p>" + _shortcut_table_html(),
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
    page: str | None = None  # objectName of the page to show first
    delay_ms: int = 0  # extra wait after switching page
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
        target=[
            "btn_menu_fileCoreg",
            "btn_menu_reconstruction",
            "btn_menu_obliqueSlice",
            "btn_menu_3Dview",
        ],
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
        target=[
            "comboReco_electrodeRef",
            "btnReco_pickDeepest",
            "btnReco_pickSecond",
            "btnReco_estimate",
        ],
        page="pageReconstruction",
        delay_ms=400,
    ),
    TourStep(
        title="Slices along the electrode",
        body="Tick an electrode to cut along its axis and see every contact at "
        "once. The overlay panel switches CT, MRI, PET, SISCOM and fMRI on, "
        "one layer at a time.",
        target=[
            "cardObliqueLayerList",
            "cardObliqueDisplay",
        ],
        page="pageObliqueSlices",
        delay_ms=900,
    ),
    TourStep(
        title="The 3D scene",
        body="Brain surface, electrodes, slice planes and functional maps are "
        "switched on from these panels. In the scene above, left drag "
        "rotates, the wheel zooms, Ctrl+F goes full screen.",
        target=[
            "card3DSurfaces",
            "card3DElectrodes",
            "card3DSlices",
            "card3DPET",
            "card3DSISCOM",
            "card3DfMRI",
        ],
        page="page3DView",
        delay_ms=1200,
    ),
    TourStep(
        title="Electrical stimulation",
        body="A right click on a contact in the electrode list records what a "
        "stimulation did: the pair, the protocol, what the trace showed and "
        "what the patient felt. One card per stimulated pair.",
        # Chaque page a sa propre liste: celle de la vue 3D est la
        # troisieme. Une etape dont la cible n'existe pas est sautee.
        target="tv_Electrodes_3",
        page="page3DView",
        delay_ms=400,
    ),
    TourStep(
        title="Reading the stimulations back",
        body="A right click in the scene opens Mode: Stimulation Result. The "
        "electrodes turn grey, and a coloured tube joins the two contacts of "
        "each pair the filters keep. Nothing else in the view changes.",
        target=None,
        page="page3DView",
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
        body="The user guide explains every page, every right-click menu, every "
        "shortcut and the stimulation results. Press F1 at any time, or click "
        "this button.",
        target="btn_menu_userGuide",
        page="pageFiles",
    ),
]

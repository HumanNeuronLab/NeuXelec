"""Build the NeuXelec brochure as a PDF.

A two-page leaflet for the website and for print: what NeuXelec does and the
path it follows, from the raw images to the figures. Text only, white
background, the logo on top.

    python scripts/build_brochure.py [output.pdf]

Default output: ``docs/NeuXelec_Brochure_<version>.pdf``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# No window is shown, but the native platform plugin is needed for the fonts.
os.environ.pop("QT_QPA_PLATFORM", None)

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QTextDocument,
)

from neuxelec import __version__  # noqa: E402

FIGURES = ROOT / "resources" / "docs" / "figures"

ACCENT = QColor("#FF487D")
MUTED = QColor("#6B6F7E")

DPI = 300
MM = DPI / 25.4

WEBSITE = "neuxelec.com"
REPOSITORY = "github.com/HumanNeuronLab/NeuXelec"
CONTACT = "contact@neuxelec.com"

HEADER_MM = 40.0   # logo band on the first page
FOOTER_MM = 18.0   # links and institutional logos

CSS = """
body { color: #23252F; }
p, li { color: #23252F; font-size: 10pt; line-height: 133%; }
p.lead { color: #12131A; font-size: 12pt; line-height: 140%; }
p.kicker {
    color: #B01E4E; font-size: 10pt; font-weight: 600;
}
h2 {
    color: #12131A; font-size: 14pt; font-weight: 600;
    margin-top: 16px; margin-bottom: 7px;
}
h3 { color: #B01E4E; font-size: 11pt; font-weight: 600;
     margin-top: 14px; margin-bottom: 2px; }
b { color: #12131A; font-weight: 600; }
i { color: #23252F; }
td { color: #23252F; font-size: 10pt; line-height: 133%; }
td.step { color: #FF487D; font-size: 12pt; font-weight: 600; }
table { margin-top: 11px; }
p.quote {
    color: #B01E4E; font-size: 12pt; line-height: 138%; font-weight: 600;
    margin-top: 22px;
}
"""


def step(number: str, title: str, text: str) -> str:
    """One numbered step of the workflow, laid out as a two-column row."""
    return (
        "<table width='100%' cellspacing='0' cellpadding='0'>"
        "<tr>"
        f"<td class='step' width='9%' valign='top'>{number}</td>"
        f"<td width='91%'><b>{title}</b><br>{text}</td>"
        "</tr></table>"
    )


PAGE_ONE = f"""
<p class="lead">NeuXelec brings every image of a SEEG patient into one space,
reconstructs the implanted electrodes, names every contact against the
patient's own anatomy, and exports coordinates the rest of your tools can read.
One application, from the raw DICOM to the figure in the report.</p>

<h2>From raw images to a labelled implantation</h2>

{step("1", "Import what you have",
      "Pre and post-implantation MRI, CT, PET, ictal and inter-ictal SPECT, "
      "fMRI, FreeSurfer parcellations and pial surfaces, and the NeuroInspire "
      "plan. NIfTI, DICOM folders and FreeSurfer volumes, several files at a "
      "time.")}

{step("2", "Align on one reference",
      "Coregistration is run with ANTs on MRI 1, rigid only for the CT so the "
      "geometry of the electrodes is never scaled. Every alignment is reviewed "
      "before it counts: the reference in green, the moving image in red, and "
      "a manual console to correct it by hand.")}

{step("3", "Reconstruct in two clicks",
      "One electrode is two picks on the post-implantation CT: the deepest "
      "contact and a second point along the shaft. The DIXI reference places "
      "the rest. Custom electrodes are supported too, with unconnected "
      "contacts and variable spacing.")}

{step("4", "Let the plan do the labelling",
      "With a NeuroInspire plan loaded, NeuXelec proposes the name, the "
      "hemisphere and the reference of the nearest planned trajectory, and "
      "tells you when the axis you drew does not match the planned one. The "
      "plan never moves your picks.")}

{step("5", "Read the anatomy of every contact",
      "Each contact is labelled with the dominant region of the 3x3x3 voxel "
      "cube around it, every neighbour weighted by its distance, the way "
      "SEEG2parc does it. White matter is refined gyrus by gyrus with wmparc, "
      "and the regions a contact straddles are one hover away.")}

<p class="quote">Two picks per electrode, every contact named in the patient's
own anatomy.</p>
"""

PAGE_TWO = f"""
{step("6", "Look at it properly",
      "Oblique slices cut along the axis of an electrode show every contact of "
      "a shaft at once, turn around it and travel millimetre by millimetre "
      "beside it. The 3D scene puts electrodes, brain surface, slice planes and "
      "functional maps in one picture.")}

{step("7", "Export to whatever comes next",
      "Contact coordinates as TXT, CSV, TSV, JSON, Cartool ELS or iELVIS, in "
      "LPS or RAS, and a valid BIDS folder with the anatomical labels, in the "
      "patient space or in MNI152. Exported images can be defaced on the way "
      "out, and the brain is never touched.")}

<h2>Functional imaging where you need it</h2>
<p>PET, ictal and inter-ictal SPECT, and the SISCOM computed inside the
application once both SPECT are aligned. fMRI is read either as a statistical
map or recovered from the colour fusion the scanner exports, so what the
neurologist sends is what you display. Threshold, opacity, colour map,
minimum cluster size in mm&sup3;, restriction to the cortical ribbon: as a blob
in 3D, on the pial surface, or painted on the slice planes, next to the contacts
that matter.</p>

<h2>Made to be used in the clinic</h2>
<p><b>Everything in the patient's own space.</b> MNI is there when you ask for
it, never behind your back.</p>
<p><b>Nothing is written without you.</b> A validated coregistration lives in
the session until you save it, and NeuXelec says so if you leave it behind.</p>
<p><b>A project reopens as you left it.</b> Images, electrodes, colours and
display settings come back in one click, and a read-only mode lets you hand the
case over without any risk of changing it.</p>
<p><b>Nothing to configure, nothing to learn by heart.</b> A Windows installer
with the registration tools included, an update notice when a new version is
out, a guided tour on the first launch and the whole user guide behind F1.</p>
<p><b>Free and open source.</b> Released under the GNU General Public License
v3: read it, cite it, improve it.</p>

<h2>Where it comes from</h2>
<p>NeuXelec is developed at the Human Neuron Lab, Hôpitaux Universitaires de
Genève and Université de Genève, with the neurologists and neurosurgeons who
use it on real implantations. It is a research tool and does not replace the
judgement of the clinician in charge.</p>
"""


def make_document(html: str, width: float, height: float, device) -> QTextDocument:
    doc = QTextDocument()
    # Point sizes are resolved against the paint device: without it the text
    # would be laid out for a 96 dpi screen on a 300 dpi page.
    doc.documentLayout().setPaintDevice(device)
    doc.setDefaultFont(QFont("Segoe UI", 10))
    doc.setDefaultStyleSheet(CSS)
    doc.setPageSize(QSizeF(width, height))
    doc.setHtml(f"<body>{html}</body>")
    return doc


def draw_image(painter: QPainter, path: Path, x: float, top: float,
               width: float) -> float:
    image = QImage(str(path))
    if image.isNull():
        return top
    height = image.height() * width / image.width()
    painter.drawImage(QRectF(x, top, width, height), image)
    return top + height


def draw_header(painter: QPainter, width: float) -> None:
    """Logo, tagline and accent rule at the top of the first page."""
    bottom = draw_image(painter, FIGURES / "logo_neuxelec.png", 0, 0, 68 * MM)

    painter.setPen(MUTED)
    font = QFont("Segoe UI", 11)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)
    painter.setFont(font)
    painter.drawText(
        QRectF(0, bottom + 3 * MM, width, 8 * MM),
        Qt.AlignLeft | Qt.AlignTop,
        "MULTIMODAL ELECTRODE HUB FOR SEEG",
    )

    pen = painter.pen()
    pen.setColor(ACCENT)
    pen.setWidth(max(2, int(0.8 * MM)))
    painter.setPen(pen)
    y = bottom + 12 * MM
    painter.drawLine(0, int(y), int(width), int(y))


def draw_small_header(painter: QPainter, width: float) -> None:
    """Compact logo and rule at the top of the following pages."""
    bottom = draw_image(painter, FIGURES / "logo_neuxelec.png", 0, 0, 26 * MM)
    pen = painter.pen()
    pen.setColor(QColor("#D7D9E0"))
    pen.setWidth(max(1, int(0.3 * MM)))
    painter.setPen(pen)
    y = bottom + 4 * MM
    painter.drawLine(0, int(y), int(width), int(y))


def draw_footer(painter: QPainter, width: float, height: float,
                with_logos: bool) -> None:
    painter.save()
    pen = painter.pen()
    pen.setColor(QColor("#D7D9E0"))
    pen.setWidth(max(1, int(0.3 * MM)))
    painter.setPen(pen)
    y = height - FOOTER_MM * MM
    painter.drawLine(0, int(y), int(width), int(y))

    painter.setFont(QFont("Segoe UI", 9))
    painter.setPen(MUTED)
    painter.drawText(
        QRectF(0, y + 3 * MM, width, 6 * MM),
        Qt.AlignLeft | Qt.AlignTop,
        f"{WEBSITE}   ·   {REPOSITORY}   ·   {CONTACT}",
    )
    painter.drawText(
        QRectF(0, y + 3 * MM, width, 6 * MM),
        Qt.AlignRight | Qt.AlignTop,
        f"Version {__version__}",
    )

    if with_logos:
        logos = ["logo_hug.png", "logo_unige.png", "logo_hnl.png"]
        available = [FIGURES / n for n in logos if (FIGURES / n).exists()]
        logo_height = 9 * MM
        gap = 10 * MM
        widths = []
        for path in available:
            image = QImage(str(path))
            widths.append(image.width() * logo_height / image.height())
        x = width - sum(widths) - gap * (len(widths) - 1)
        for path, w in zip(available, widths):
            painter.drawImage(
                QRectF(x, y + 9 * MM, w, logo_height), QImage(str(path))
            )
            x += w + gap
    painter.restore()


def build(output: Path) -> Path:
    QGuiApplication.instance() or QGuiApplication(sys.argv)

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(output))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setPageMargins(QMarginsF(20, 16, 20, 14), QPageLayout.Millimeter)
    writer.setResolution(DPI)
    writer.setTitle(f"NeuXelec {__version__}")
    writer.setCreator("NeuXelec")

    width = float(writer.width())
    height = float(writer.height())

    first_height = height - HEADER_MM * MM - FOOTER_MM * MM
    second_header = 14.0 * MM
    second_height = height - second_header - FOOTER_MM * MM

    first = make_document(PAGE_ONE, width, first_height, writer)
    second = make_document(PAGE_TWO, width, second_height, writer)

    painter = QPainter(writer)
    try:
        draw_header(painter, width)
        painter.save()
        painter.translate(0, HEADER_MM * MM)
        first.drawContents(painter, QRectF(0, 0, width, first_height))
        painter.restore()
        draw_footer(painter, width, height, with_logos=False)

        writer.newPage()
        draw_small_header(painter, width)
        painter.save()
        painter.translate(0, second_header)
        second.drawContents(painter, QRectF(0, 0, width, second_height))
        painter.restore()
        draw_footer(painter, width, height, with_logos=True)
    finally:
        painter.end()

    print(f"{output}")
    print(f"   page 1 needs {first.pageCount()} page(s), "
          f"page 2 needs {second.pageCount()} page(s)")
    return output


if __name__ == "__main__":
    target = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "docs" / f"NeuXelec_Brochure_{__version__}.pdf"
    )
    build(target)

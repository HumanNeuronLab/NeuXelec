"""Build the printed NeuXelec manual as a PDF.

Same source as the in-application User guide (``neuxelec.help.content``), so the
two can never drift apart, rendered for paper: white background, black text, the
NeuXelec logo on the cover, a table of contents, figures and page numbers.

    python scripts/build_manual.py [output.pdf]

Default output: ``installer/NeuXelec_User_Guide_<version>.pdf``,
beside the setup executables rather than in docs/, which is for text.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# No window is ever shown, but the native platform plugin is required: the
# offscreen one has no font database, and every glyph would come out as a box.
os.environ.pop("QT_QPA_PLATFORM", None)

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt, QUrl  # noqa: E402
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
from neuxelec.help.content import MANUAL_SECTIONS  # noqa: E402

FIGURES = ROOT / "resources" / "docs" / "figures"

ACCENT = QColor("#FF487D")
INK = QColor("#12131A")
MUTED = QColor("#6B6F7E")
RULE = QColor("#D7D9E0")

DPI = 300
MM = DPI / 25.4
FOOTER_MM = 12.0

WEBSITE = "neuxelec.com"
REPOSITORY = "github.com/HumanNeuronLab/NeuXelec"
CONTACT = "contact@neuxelec.com"

#: Figure printed at the end of each section, when the file exists.
SECTION_FIGURES = {
    "files": (
        "coreg_review.png",
        "Reviewing a coregistration: the reference in green, the moving image "
        "in red. Here a post-implantation CT on MRI 1.",
    ),
    "reconstruction": (
        "reconstruction.png",
        "Reconstructed electrodes on the post-implantation CT, seen in the "
        "3D view.",
    ),
    "oblique": (
        "oblique_parcellation.png",
        "An oblique slice cut along an electrode, with the parcellation "
        "overlaid and the contacts in yellow.",
    ),
    "view3d": (
        "view3d_pial.png",
        "Contacts projected on the pial surface, each labelled with its "
        "electrode name.",
    ),
    "rightclick": (
        "menu_3d.png",
        "The 3D view menu. Every menu is grouped in labelled sections.",
    ),
}

PRINT_CSS = """
body { color: #12131A; }
h1 {
    color: #12131A; font-size: 19pt; font-weight: 600;
    margin-top: 0px; margin-bottom: 22px; page-break-before: always;
}
h2 { color: #12131A; font-size: 19pt; font-weight: 600; margin-bottom: 22px; }
h3 {
    color: #B01E4E; font-size: 11.5pt; font-weight: 600;
    margin-top: 16px; margin-bottom: 2px;
}
p, li { color: #23252F; font-size: 10.5pt; line-height: 148%; }
b { color: #12131A; font-weight: 600; }
i { color: #23252F; }
code { color: #A8184A; font-family: "Consolas", "Courier New"; font-size: 10pt; }
p.lead { color: #4A4D5A; font-size: 11pt; }
p.figure { line-height: 100%; margin-top: 22px; margin-bottom: 0px; }
p.caption { color: #6B6F7E; font-size: 9pt; line-height: 130%; margin-top: 6px; }
th {
    color: #6B6F7E; font-size: 9pt; font-weight: 600;
    border-bottom: 1px solid #B9BCC6;
}
td { color: #23252F; font-size: 9.5pt; border-bottom: 1px solid #E7E8EE; }
tr.alt td { background-color: #F5F6F9; }
table { margin-top: 8px; }
"""


#: Images referenced by the body, registered on the document before layout.
FIGURE_RESOURCES: dict[str, QImage] = {}

MAX_FIGURE_W_MM = 118.0   # width of a figure on the page
MAX_FIGURE_H_MM = 88.0    # so that the caption still fits under it
CSS_PX_PER_MM = 96.0 / 25.4  # <img width> is read in CSS pixels, not device px


def figure_html(name: str, caption: str, force_break: bool) -> str:
    """One figure and its caption.

    The image is registered as a document resource: a bare QTextDocument does
    not fetch ``file://`` URLs by itself. Its size is given in CSS pixels, which
    the layout scales to the 300 dpi page.
    """
    path = FIGURES / name
    if not path.exists():
        return ""
    image = QImage(str(path))
    if image.isNull():
        return ""
    FIGURE_RESOURCES[name] = image

    # Natural size on paper at 300 dpi, enlarged a little but never past the
    # limits above.
    width_mm = min(image.width() / DPI * 25.4 * 1.4, MAX_FIGURE_W_MM)
    height_mm = width_mm * image.height() / image.width()
    if height_mm > MAX_FIGURE_H_MM:
        width_mm *= MAX_FIGURE_H_MM / height_mm
        height_mm = MAX_FIGURE_H_MM

    # The paragraph keeps a 100% line height: with the body's 148%, a 70 mm
    # image would reserve a 104 mm line box and push its caption away.
    style = ' style="page-break-before: always"' if force_break else ""
    return (
        f'<p class="figure"{style}><img src="{name}" '
        f'width="{int(width_mm * CSS_PX_PER_MM)}" '
        f'height="{int(height_mm * CSS_PX_PER_MM)}"></p>'
        f'<p class="caption">{caption}</p>'
    )


def body_html(breaks: set[str] | None = None) -> str:
    breaks = breaks or set()
    parts = []
    for index, section in enumerate(MANUAL_SECTIONS):
        style = ' style="page-break-before: auto"' if index == 0 else ""
        parts.append(f"<h1{style}>{section.title}</h1>")
        figure = SECTION_FIGURES.get(section.id)
        html = figure_html(figure[0], figure[1], figure[0] in breaks) if figure else ""
        # The figure goes right after the opening paragraph: at the end of a
        # section it would often be pushed alone onto the next page.
        body = section.body
        cut = body.find("</p>")
        if html and cut != -1:
            parts.append(body[: cut + 4] + html + body[cut + 4 :])
        else:
            parts.append(body)
            parts.append(html)

    parts.append("<h1>About this guide</h1>")
    parts.append(
        f"<p>This manual describes NeuXelec {__version__}. The same text is "
        "available inside the application: press <b>F1</b> or click <b>User "
        "guide</b> in the left menu. The guided tour shown on the first launch "
        "can be replayed from that window at any time.</p>"
        f"<p><b>Website</b> {WEBSITE}<br>"
        f"<b>Source code</b> {REPOSITORY}<br>"
        f"<b>Contact</b> {CONTACT}</p>"
        "<p>NeuXelec is developed at the Human Neuron Lab, Hopitaux "
        "Universitaires de Geneve and Universite de Geneve, and released under "
        "the GNU General Public License v3 or later.</p>"
        "<p>NeuXelec is a research tool. It is not a certified medical device "
        "and every result must be reviewed by the clinician in charge.</p>"
    )
    return "".join(parts)


def contents_html(entries, content_px: int) -> str:
    rows = "".join(
        f"<tr><td width='88%'>{title}</td>"
        f"<td width='12%' align='right'>{page}</td></tr>"
        for title, page in entries
    )
    return (
        "<h2>Contents</h2>"
        f"<table width='100%' cellspacing='0' cellpadding='7'>{rows}</table>"
    )


def make_document(html: str, width: float, height: float, device) -> QTextDocument:
    doc = QTextDocument()
    # Without the paint device, point sizes are resolved against the screen
    # (96 dpi) while the page is measured at 300 dpi: the text would come out
    # three times too small.
    doc.documentLayout().setPaintDevice(device)
    for name, image in FIGURE_RESOURCES.items():
        doc.addResource(QTextDocument.ImageResource, QUrl(name), image)
    doc.setDefaultFont(QFont("Segoe UI", 10))
    doc.setDefaultStyleSheet(PRINT_CSS)
    doc.setPageSize(QSizeF(width, height))
    doc.setHtml(f"<body>{html}</body>")
    return doc


def section_pages(doc: QTextDocument, body_height: float, offset: int):
    """(title, printed page) for every level-1 heading of the document."""
    layout = doc.documentLayout()
    entries = []
    block = doc.begin()
    while block.isValid():
        if block.blockFormat().headingLevel() == 1:
            top = layout.blockBoundingRect(block).top()
            entries.append(
                (block.text(), int(top // body_height) + 1 + offset)
            )
        block = block.next()
    return entries


def image_name_of(block) -> str | None:
    """The resource name of the image this block holds, if it holds one."""
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid() and fragment.charFormat().isImageFormat():
            return fragment.charFormat().toImageFormat().name()
        iterator += 1
    return None


def split_figures(doc: QTextDocument, body_height: float) -> set[str]:
    """Figures that do not sit on one page with their caption.

    Qt has no ``page-break-inside: avoid``, so the document is laid out, the
    offenders are collected here, and the caller rebuilds it asking for a page
    break in front of them.
    """
    layout = doc.documentLayout()
    offenders = set()
    block = doc.begin()
    while block.isValid():
        name = image_name_of(block)
        if name:
            rect = layout.blockBoundingRect(block)
            caption = block.next()
            caption_rect = (
                layout.blockBoundingRect(caption) if caption.isValid() else rect
            )
            first = int(rect.top() // body_height)
            last = int(max(rect.bottom() - 1, caption_rect.bottom() - 1) // body_height)
            if first != last:
                offenders.add(name)
        block = block.next()
    return offenders


def heading_rules(doc: QTextDocument, body_height: float):
    """(page index, y inside that page) of the accent rule under each title.

    Qt paints borders on table cells and frames, not on ordinary blocks, so the
    rule under a section title is drawn with the painter.
    """
    layout = doc.documentLayout()
    marks = []
    block = doc.begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        if level in (1, 2):
            rect = layout.blockBoundingRect(block)
            page = int(rect.top() // body_height)
            bottom = rect.bottom() - page * body_height
            marks.append((page, bottom + 2.6 * MM))
        block = block.next()
    return marks


def draw_rules(painter: QPainter, marks, page: int, width: float) -> None:
    painter.save()
    pen = painter.pen()
    pen.setColor(ACCENT)
    pen.setWidth(max(2, int(0.7 * MM)))
    painter.setPen(pen)
    for mark_page, y in marks:
        if mark_page == page:
            painter.drawLine(0, int(y), int(width), int(y))
    painter.restore()


def draw_footer(painter: QPainter, width: float, height: float, page: int) -> None:
    painter.save()
    pen = painter.pen()
    pen.setColor(RULE)
    pen.setWidth(max(1, int(0.3 * MM)))
    painter.setPen(pen)
    y = height - FOOTER_MM * MM + 2 * MM
    painter.drawLine(0, int(y), int(width), int(y))

    font = QFont("Segoe UI", 8)
    painter.setFont(font)
    painter.setPen(MUTED)
    text_rect = QRectF(0, y + 1.5 * MM, width, 6 * MM)
    painter.drawText(
        text_rect, Qt.AlignLeft | Qt.AlignTop, f"NeuXelec {__version__} user guide"
    )
    painter.drawText(text_rect, Qt.AlignRight | Qt.AlignTop, str(page))
    painter.restore()


def draw_image(painter: QPainter, path: Path, center_x: float, top: float,
               width: float) -> float:
    """Draw an image centred on ``center_x``; returns its bottom edge."""
    image = QImage(str(path))
    if image.isNull():
        return top
    height = image.height() * width / image.width()
    target = QRectF(center_x - width / 2.0, top, width, height)
    painter.drawImage(target, image)
    return top + height


def draw_cover(painter: QPainter, width: float, height: float) -> None:
    center = width / 2.0

    bottom = draw_image(
        painter, FIGURES / "logo_neuxelec.png", center, 26 * MM, 96 * MM
    )

    painter.setPen(INK)
    font = QFont("Segoe UI", 27)
    font.setWeight(QFont.DemiBold)
    font.setLetterSpacing(QFont.AbsoluteSpacing, 3.0 * MM / 4)
    painter.setFont(font)
    title_rect = QRectF(0, bottom + 12 * MM, width, 18 * MM)
    painter.drawText(title_rect, Qt.AlignHCenter | Qt.AlignTop, "USER GUIDE")

    painter.setPen(MUTED)
    font = QFont("Segoe UI", 11)
    painter.setFont(font)
    painter.drawText(
        QRectF(0, bottom + 30 * MM, width, 10 * MM),
        Qt.AlignHCenter | Qt.AlignTop,
        "Multimodal electrode hub for SEEG",
    )

    pen = painter.pen()
    pen.setColor(ACCENT)
    pen.setWidth(max(1, int(0.6 * MM)))
    painter.setPen(pen)
    rule_y = bottom + 42 * MM
    painter.drawLine(
        int(center - 22 * MM), int(rule_y), int(center + 22 * MM), int(rule_y)
    )

    hero_bottom = draw_image(
        painter, FIGURES / "view3d_electrodes.png", center, rule_y + 14 * MM,
        130 * MM,
    )

    painter.setPen(MUTED)
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(
        QRectF(0, hero_bottom + 6 * MM, width, 8 * MM),
        Qt.AlignHCenter | Qt.AlignTop,
        f"Version {__version__}  ·  {date.today().strftime('%B %Y')}  ·  {WEBSITE}",
    )

    # Institutional logos, aligned on a common height at the foot of the page.
    logos = ["logo_hug.png", "logo_unige.png", "logo_hnl.png"]
    available = [FIGURES / name for name in logos if (FIGURES / name).exists()]
    if not available:
        return
    logo_height = 13 * MM
    gap = 14 * MM
    widths = []
    for path in available:
        image = QImage(str(path))
        widths.append(image.width() * logo_height / image.height())
    total = sum(widths) + gap * (len(widths) - 1)
    x = center - total / 2.0
    y = height - 24 * MM
    for path, w in zip(available, widths):
        image = QImage(str(path))
        painter.drawImage(QRectF(x, y, w, logo_height), image)
        x += w + gap


def build(output: Path) -> Path:
    QGuiApplication.instance() or QGuiApplication(sys.argv)

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(output))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setPageMargins(QMarginsF(18, 16, 18, 16), QPageLayout.Millimeter)
    writer.setResolution(DPI)
    writer.setTitle(f"NeuXelec {__version__} user guide")
    writer.setCreator("NeuXelec")

    width = float(writer.width())
    height = float(writer.height())
    body_height = height - FOOTER_MM * MM

    # Lay the body out, move the figures that straddle two pages, and settle.
    breaks: set[str] = set()
    body = make_document(body_html(breaks), width, body_height, writer)
    for _ in range(3):
        offenders = split_figures(body, body_height) - breaks
        if not offenders:
            break
        breaks |= offenders
        body = make_document(body_html(breaks), width, body_height, writer)

    entries = section_pages(body, body_height, offset=2)
    contents = make_document(
        contents_html(entries, int(width)), width, body_height, writer
    )

    painter = QPainter(writer)
    try:
        draw_cover(painter, width, height)

        writer.newPage()
        contents.drawContents(painter, QRectF(0, 0, width, body_height))
        draw_rules(painter, heading_rules(contents, body_height), 0, width)
        draw_footer(painter, width, height, 2)

        marks = heading_rules(body, body_height)
        pages = body.pageCount()
        for index in range(pages):
            writer.newPage()
            painter.save()
            painter.translate(0, -index * body_height)
            body.drawContents(
                painter,
                QRectF(0, index * body_height, width, body_height),
            )
            painter.restore()
            draw_rules(painter, marks, index, width)
            draw_footer(painter, width, height, index + 3)
    finally:
        painter.end()

    print(f"{output}  ({2 + body.pageCount()} pages)")
    for title, page in entries:
        print(f"   p.{page:<3d} {title}")
    return output


if __name__ == "__main__":
    target = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "installer" / f"NeuXelec_User_Guide_{__version__}.pdf"
    )
    build(target)

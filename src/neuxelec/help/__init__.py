"""In-app documentation: the user guide window, the guided tour and the PDF.

Everything the user reads comes from :mod:`neuxelec.help.content`, so the
window (F1 / User guide), the guided tour shown on first launch and the PDF
manual published on the website can never drift apart.
"""

from .content import MANUAL_SECTIONS, SHORTCUTS, TOUR_STEPS

__all__ = ["MANUAL_SECTIONS", "SHORTCUTS", "TOUR_STEPS"]

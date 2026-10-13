"""Edit mode, or View Only, in one place.

The mode used to be read as a string in whichever file needed it, which
is how an action ends up protected on one page and open on another. It
is read here now, and the question is asked the same way everywhere.

WHAT VIEW ONLY MEANS

Display settings stay free: colours, opacities, filters, the camera,
which slice is shown. What the viewer cannot do is change the patient's
data, and the project file cannot be written at all.

That second half is the one that matters. Six places in the application
write the project, three of them on their own, after a renamed
electrode, a saved camera or a stored slice position. Disabling a button
would have left those three open, so the refusal lives in the function
that writes, and the button is only the visible half of it.
"""

from __future__ import annotations

EDIT = "edit"
VIEW_ONLY = "visualization"


class ProjectIsViewOnly(RuntimeError):
    """Raised instead of writing a project opened in View Only mode."""


def mode_of(state) -> str:
    return str(getattr(state, "app_mode", EDIT) or EDIT).lower().strip()


def is_edit_mode(state) -> bool:
    return mode_of(state) == EDIT


def is_view_only(state) -> bool:
    return not is_edit_mode(state)

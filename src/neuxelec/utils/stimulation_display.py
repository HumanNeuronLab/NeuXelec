# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""How a stimulation is drawn in the 3D view, and the rules that decide it.

WHY RULES RATHER THAN ONE SETTING

A map is read by looking, not by reading a legend twice. What makes it
readable is that the thing you came to find stands out: the pairs that
reproduced the patient's own aura thick and red, the silent ones thin and
grey. One global colour cannot do that, so the settings are a list of
RULES: a condition, borrowed from the filter vocabulary, and the style to
draw what matches it. The first enabled rule that matches wins.

Three named sets of rules come with the application, so that the first use
needs no setting up, and anything can be added or changed on top.

WHERE IT IS DRAWN

Between the two contacts by default. For a bipolar pair the current
density peaks there, so a tube from one contact to the other says what the
examination did; a mark on the contacts alone would suggest each contact
was stimulated by itself.
"""

from __future__ import annotations

from typing import Any

from . import stimulation as st

# --------------------------------------------------------------------------
# Where a result is drawn.
# --------------------------------------------------------------------------

WHERE_LINE = "line"
WHERE_CONTACTS = "contacts"
WHERE_BOTH = "both"

WHERE_CHOICES: tuple[tuple[str, str], ...] = (
    (WHERE_LINE, "A tube between the two contacts"),
    (WHERE_CONTACTS, "A mark on each contact"),
    (WHERE_BOTH, "Both"),
)

# --------------------------------------------------------------------------
# What decides the colour.
# --------------------------------------------------------------------------

BY_FINDING = "finding"
BY_CATEGORY = "category"
BY_RULES = "rules"
FIXED = "fixed"

COLOUR_MODES: tuple[tuple[str, str], ...] = (
    (BY_FINDING, "What the finding is worth"),
    (BY_CATEGORY, "The kind of clinical response"),
    (BY_RULES, "My own rules"),
    (FIXED, "One colour for all"),
)

#: One colour per response category, far enough apart to tell on a brain.
CATEGORY_COLOURS: dict[str, str] = {
    "motor": "#FF6B3D",
    "language": "#4DA3FF",
    "somatosensory": "#36C5F0",
    "visual": "#B86BFF",
    "auditory": "#2ED9A0",
    "olfactory_gustatory": "#C8D11A",
    "vestibular": "#FF8FD0",
    "autonomic": "#FFC400",
    "affective": "#FF4D6D",
    "cognitive": "#7A8CFF",
    "other": "#9AA0B0",
}

#: Every contact of the implantation is drawn in this light grey, so that
#: the coloured results are the only thing that reads on top of it.
DEFAULT_GREY = "#B9BFCC"

DEFAULT_STYLE: dict[str, Any] = {
    "where": WHERE_LINE,
    "colour": st.COLOUR_RESPONSE,
    "line_width_mm": 1.4,
    "contact_radius_mm": 1.2,
    "opacity": 1.0,
}


def default_settings() -> dict[str, Any]:
    """What a patient file carries before anyone changes anything."""
    return {
        "colour_mode": BY_FINDING,
        "where": WHERE_LINE,
        "line_width_mm": 1.4,
        "contact_radius_mm": 1.2,
        "opacity": 1.0,
        "fixed_colour": st.COLOUR_RESPONSE,
        "grey_colour": DEFAULT_GREY,
        # Shown only when colour_mode is BY_RULES, but kept whatever the
        # mode: switching to another mode and back must not lose them.
        "rules": [],
    }


# --------------------------------------------------------------------------
# One rule.
# --------------------------------------------------------------------------


def new_rule(
    name: str = "",
    *,
    when: dict | None = None,
    colour: str = st.COLOUR_RESPONSE,
    where: str = "",
    line_width_mm: float | None = None,
    contact_radius_mm: float | None = None,
    opacity: float | None = None,
    enabled: bool = True,
    rule_id: str = "",
) -> dict[str, Any]:
    """A condition and the style to draw what matches it.

    A style value left empty falls back to the global setting, so a rule
    that only changes the colour does not have to repeat the rest.
    """
    condition = st.empty_filters()
    condition.update(when or {})

    return {
        "id": str(rule_id),
        "name": str(name),
        "enabled": bool(enabled),
        "when": _serialisable_condition(condition),
        "colour": str(colour),
        "where": str(where),
        "line_width_mm": line_width_mm,
        "contact_radius_mm": contact_radius_mm,
        "opacity": opacity,
    }


def _serialisable_condition(condition: dict) -> dict:
    """Sets do not survive JSON, so they are stored as sorted lists."""
    out: dict[str, Any] = {}

    for key, value in (condition or {}).items():
        out[key] = sorted(value) if isinstance(value, (set, frozenset)) else value

    return out


def _condition_as_filters(condition: dict) -> dict:
    """Back to the shape the filter matcher expects."""
    out = st.empty_filters()

    for key, value in (condition or {}).items():
        if isinstance(out.get(key), set) and isinstance(value, (list, tuple, set)):
            out[key] = set(value)
        else:
            out[key] = value

    return out


def next_rule_id(rules: list[dict]) -> str:
    highest = 0

    for rule in rules or []:
        raw = str((rule or {}).get("id", ""))

        if raw.startswith("rule-") and raw[5:].isdigit():
            highest = max(highest, int(raw[5:]))

    return f"rule-{highest + 1}"


def rule_matches(rule: dict, record: dict) -> bool:
    if not (rule or {}).get("enabled", True):
        return False

    return st.matches_filters(record, _condition_as_filters(rule.get("when")))


# --------------------------------------------------------------------------
# The sets of rules that come with the application.
# --------------------------------------------------------------------------


def _preset_clinical() -> list[dict]:
    """What a surgical discussion looks for, ranked."""
    return [
        new_rule(
            "Habitual event reproduced",
            when={"habitual": ["identical"]},
            colour=st.COLOUR_HABITUAL,
            line_width_mm=2.4,
            rule_id="rule-1",
        ),
        new_rule(
            "Some elements of it",
            when={"habitual": ["partial"]},
            colour=st.COLOUR_PARTIAL,
            line_width_mm=1.8,
            rule_id="rule-2",
        ),
        new_rule(
            "Seizure, not habitual",
            when={"events": sorted(st.SEIZURE_EVENTS)},
            colour=st.COLOUR_SEIZURE,
            line_width_mm=1.4,
            rule_id="rule-3",
        ),
        new_rule(
            "Tested, no response",
            when={"include_silent": True, "events": [], "categories": []},
            colour=DEFAULT_GREY,
            line_width_mm=0.6,
            opacity=0.5,
            rule_id="rule-4",
        ),
    ]


def _preset_eloquent() -> list[dict]:
    """Where it would be dangerous to cut."""
    return [
        new_rule(
            "Language",
            when={"categories": ["language"]},
            colour=CATEGORY_COLOURS["language"],
            line_width_mm=2.4,
            rule_id="rule-1",
        ),
        new_rule(
            "Motor",
            when={"categories": ["motor"]},
            colour=CATEGORY_COLOURS["motor"],
            line_width_mm=2.0,
            rule_id="rule-2",
        ),
        new_rule(
            "Somatosensory",
            when={"categories": ["somatosensory"]},
            colour=CATEGORY_COLOURS["somatosensory"],
            line_width_mm=1.6,
            rule_id="rule-3",
        ),
        new_rule(
            "Visual",
            when={"categories": ["visual"]},
            colour=CATEGORY_COLOURS["visual"],
            line_width_mm=1.6,
            rule_id="rule-4",
        ),
    ]


def _preset_thresholds() -> list[dict]:
    """What answered at a low current, and what needed to be pushed."""
    return [
        new_rule(
            "Responded under 1.5 mA",
            when={"max_intensity_ma": 1.5, "include_silent": False},
            colour=st.COLOUR_HABITUAL,
            line_width_mm=2.4,
            rule_id="rule-1",
        ),
        new_rule(
            "Responded under 3 mA",
            when={"max_intensity_ma": 3.0, "include_silent": False},
            colour=st.COLOUR_PARTIAL,
            line_width_mm=1.8,
            rule_id="rule-2",
        ),
        new_rule(
            "Responded above 3 mA",
            when={"min_intensity_ma": 3.0, "include_silent": False},
            colour=st.COLOUR_RESPONSE,
            line_width_mm=1.2,
            rule_id="rule-3",
        ),
    ]


PRESETS: tuple[tuple[str, str], ...] = (
    ("clinical", "What the finding is worth"),
    ("eloquent", "Eloquent cortex"),
    ("thresholds", "Response thresholds"),
)

_PRESET_BUILDERS = {
    "clinical": _preset_clinical,
    "eloquent": _preset_eloquent,
    "thresholds": _preset_thresholds,
}


def preset_rules(name: str) -> list[dict]:
    """A fresh copy of one of the sets that come with the application."""
    builder = _PRESET_BUILDERS.get(str(name))
    return builder() if builder is not None else []


# --------------------------------------------------------------------------
# Resolving one record to one style.
# --------------------------------------------------------------------------


def _number(value, fallback: float) -> float:
    try:
        return float(fallback if value is None else value)
    except (TypeError, ValueError):
        return float(fallback)


def category_colour(record: dict) -> str:
    """The colour of the first response, or grey for a record with none."""
    for response in (record or {}).get("responses", []):
        colour = CATEGORY_COLOURS.get(str(response.get("category", "")))

        if colour:
            return colour

    return DEFAULT_GREY


def style_for(record: dict, settings: dict | None = None) -> dict[str, Any]:
    """How this stimulation should be drawn, settings and rules applied."""
    settings = {**default_settings(), **(settings or {})}

    style = {
        "where": str(settings.get("where") or WHERE_LINE),
        "colour": str(settings.get("fixed_colour") or st.COLOUR_RESPONSE),
        "line_width_mm": _number(settings.get("line_width_mm"), 1.4),
        "contact_radius_mm": _number(settings.get("contact_radius_mm"), 1.2),
        "opacity": _number(settings.get("opacity"), 1.0),
        "rule": "",
    }

    mode = str(settings.get("colour_mode") or BY_FINDING)

    if mode == BY_FINDING:
        style["colour"] = st.marker_colour(record)
    elif mode == BY_CATEGORY:
        style["colour"] = category_colour(record)
    elif mode == BY_RULES:
        matched = first_matching_rule(record, settings.get("rules"))

        if matched is None:
            # Nothing claims it: draw it faintly rather than not at all, so
            # a rule that is too narrow shows up as grey instead of as a
            # pair that seems never to have been tested.
            style["colour"] = str(settings.get("grey_colour") or DEFAULT_GREY)
            style["opacity"] = min(style["opacity"], 0.45)
        else:
            style["rule"] = str(matched.get("name", ""))
            style["colour"] = str(matched.get("colour") or style["colour"])

            if matched.get("where"):
                style["where"] = str(matched["where"])

            for key in ("line_width_mm", "contact_radius_mm", "opacity"):
                if matched.get(key) is not None:
                    style[key] = _number(matched[key], style[key])

    return style


def first_matching_rule(record: dict, rules: list[dict] | None) -> dict | None:
    for rule in rules or []:
        if rule_matches(rule, record):
            return rule

    return None


def grey_colour(settings: dict | None = None) -> str:
    settings = settings or {}
    return str(settings.get("grey_colour") or DEFAULT_GREY)


def legend_entries(settings: dict | None = None) -> list[tuple[str, str]]:
    """What the colours mean right now, in the order they are decided."""
    settings = {**default_settings(), **(settings or {})}
    mode = str(settings.get("colour_mode") or BY_FINDING)

    if mode == BY_FINDING:
        return [(colour, text) for colour, text in st.COLOUR_LEGEND]

    if mode == BY_CATEGORY:
        return [
            (CATEGORY_COLOURS[cat.key], cat.label)
            for cat in st.CATEGORIES
            if cat.key in CATEGORY_COLOURS
        ]

    if mode == BY_RULES:
        entries = [
            (str(rule.get("colour") or DEFAULT_GREY), str(rule.get("name") or "rule"))
            for rule in settings.get("rules") or []
            if rule.get("enabled", True)
        ]
        entries.append((grey_colour(settings), "matched by no rule"))
        return entries

    return [(str(settings.get("fixed_colour") or st.COLOUR_RESPONSE), "every stimulation")]

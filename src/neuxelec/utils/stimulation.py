"""Electrical stimulation results: the vocabulary, the record, the filters.

WHY A MODULE OF ITS OWN

There is no standard classification of responses evoked by intracerebral
stimulation. The EStiMapp authors say so in as many words, and the 2023
international survey of SEEG stimulation practice found centres diverging
widely. So the vocabulary below is a synthesis, and the one thing it must
do is let someone record what they saw even when no term fits: every list
ends in OTHER, and OTHER carries its own free text.

WHERE THE TERMS COME FROM

- The eleven response categories are the EStiMapp consensus list.
- The descriptors inside each category, and the positive/negative motor
  distinction, follow the ACNS draft technical standards, section 7.1
  (Response Documentation).
- The subjective terms follow the ILAE glossary of descriptive ictal
  terminology: an ILLUSION alters a real percept, a HALLUCINATION has no
  external stimulus, and familiarity/unfamiliarity are mnemonic phenomena.
- The protocol defaults follow ACNS Table 2 for SEEG, and the recorded
  fields follow its Table 4 datasheet.

WHAT THE RECORD INSISTS ON

Four fields exist because a card without them cannot be read later:

- the FREQUENCY, because 1 Hz and 50 Hz are different examinations at the
  same current, and induced seizures run 7-18% at 1 Hz against 40-55% at
  50 Hz;
- the PULSE WIDTH, because charge is current times duration, so milliamps
  alone say nothing;
- whether the HABITUAL aura or seizure was reproduced, which is what
  decides the localising value of the whole card;
- the REPRODUCIBILITY, which the ACNS requires and which separates a
  response seen once from one seen twice.

A response is stored as a BLOCK, not as a flat list of words: category,
descriptor, localisation, laterality. Two responses to one stimulation
would otherwise lose track of which localisation belongs to which.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .i18n import FRENCH, language, tr

# --------------------------------------------------------------------------
# How a category is localised. This is what lets the entry window show one
# localisation widget and hide the others instead of asking for everything.
# --------------------------------------------------------------------------

LOC_NONE = "none"
LOC_BODY = "body"
LOC_VISUAL_FIELD = "visual_field"
LOC_EAR = "ear"

OTHER = "other"


class Category:
    """One response category, its descriptors and how it is localised."""

    __slots__ = ("key", "label", "descriptors", "localisation", "signed")

    def __init__(self, key, label, descriptors, localisation=LOC_NONE, signed=False):
        self.key = key
        self.label = label
        self.descriptors = tuple(descriptors)
        self.localisation = localisation
        #: True for motor only: the ACNS asks first whether the response was
        #: positive (a new movement) or negative (an ongoing movement stopped).
        self.signed = bool(signed)


#: The eleven EStiMapp categories, in the order the entry window shows them.
CATEGORIES: tuple[Category, ...] = (
    Category(
        "motor",
        "Motor",
        (
            "Tonic posturing",
            "Clonic jerks",
            "Dystonic posturing",
            "Versive movement or eye deviation",
            "Head turning",
            "Automatism",
            "Myoclonus",
            "Movement arrest",
            "Loss of muscle tone",
            OTHER,
        ),
        localisation=LOC_BODY,
        signed=True,
    ),
    Category(
        "language",
        "Language",
        (
            "Speech arrest",
            "Anomia",
            "Semantic paraphasia",
            "Phonemic paraphasia",
            "Circumlocution",
            "Neologism",
            "Dysarthria",
            "Apraxia of speech",
            "Comprehension impairment",
            "Reading impairment",
            "Writing impairment",
            "Counting arrest",
            "Perseveration",
            OTHER,
        ),
    ),
    Category(
        "somatosensory",
        "Somatosensory",
        (
            "Tingling or paresthesia",
            "Numbness",
            "Buzzing",
            "Burning",
            "Pain",
            "Thermal sensation",
            "Electric sensation",
            "Illusion of movement",
            "Cephalic sensation",
            OTHER,
        ),
        localisation=LOC_BODY,
    ),
    Category(
        "visual",
        "Visual",
        (
            "Phosphenes",
            "Colours",
            "Simple geometric shapes",
            "Blurring",
            "Scotoma",
            "Visual field loss",
            "Complex visual hallucination",
            "Visual illusion (micropsia, macropsia, metamorphopsia)",
            "Palinopsia",
            OTHER,
        ),
        localisation=LOC_VISUAL_FIELD,
    ),
    Category(
        "auditory",
        "Auditory",
        (
            "Tinnitus",
            "Buzzing",
            "Humming",
            "Pure tone",
            "Change in loudness",
            "Complex sound",
            "Voices",
            "Music",
            "Auditory illusion",
            OTHER,
        ),
        localisation=LOC_EAR,
    ),
    Category(
        "olfactory_gustatory",
        "Olfactory or gustatory",
        (
            "Unpleasant odour",
            "Pleasant odour",
            "Indefinable odour",
            "Metallic taste",
            "Bitter taste",
            "Sweet taste",
            "Salty taste",
            "Acid taste",
            OTHER,
        ),
    ),
    Category(
        "vestibular",
        "Vestibular",
        (
            "Vertigo or rotation",
            "Sensation of body displacement",
            "Floating",
            "Falling",
            "Tilting",
            OTHER,
        ),
    ),
    Category(
        "autonomic",
        "Autonomic",
        (
            "Epigastric rising sensation",
            "Abdominal sensation",
            "Nausea",
            "Palpitations",
            "Tachycardia",
            "Bradycardia",
            "Respiratory change",
            "Hypersalivation",
            "Flushing",
            "Pallor",
            "Sweating",
            "Piloerection",
            "Pupillary change",
            "Urge to urinate",
            OTHER,
        ),
    ),
    Category(
        "affective",
        "Affective",
        (
            "Fear or anxiety",
            "Sadness",
            "Joy or pleasure",
            "Mirth or laughter",
            "Anger",
            "Erotic sensation",
            OTHER,
        ),
    ),
    Category(
        "cognitive",
        "Cognitive",
        (
            "Deja-vu (familiarity)",
            "Jamais-vu (unfamiliarity)",
            "Dreamy state",
            "Reminiscence",
            "Forced thinking",
            "Depersonalisation",
            "Derealisation",
            "Out-of-body experience",
            "Ictal amnesia",
            "Acalculia",
            "Neglect",
            "Apraxia",
            "Confusion",
            OTHER,
        ),
    ),
    Category(
        "other",
        "Other",
        ("Indescribable aura", OTHER),
    ),
)

CATEGORY_BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}


def category(key: str) -> Category | None:
    return CATEGORY_BY_KEY.get(str(key))


# --------------------------------------------------------------------------
# The vocabularies the localisation widgets offer.
# --------------------------------------------------------------------------

#: Somatotopy, ordered head to foot so the list reads like a body.
BODY_PARTS: tuple[str, ...] = (
    "Face",
    "Lips",
    "Tongue",
    "Mouth",
    "Pharynx or larynx",
    "Head",
    "Neck",
    "Shoulder",
    "Arm",
    "Elbow",
    "Forearm",
    "Wrist",
    "Hand",
    "Thumb",
    "Fingers",
    "Trunk",
    "Abdomen",
    "Back",
    "Hip",
    "Leg",
    "Knee",
    "Foot",
    "Toes",
    "Genital",
    "Whole hemibody",
    OTHER,
)

VISUAL_FIELDS: tuple[str, ...] = (
    "Left hemifield",
    "Right hemifield",
    "Upper left quadrant",
    "Upper right quadrant",
    "Lower left quadrant",
    "Lower right quadrant",
    "Central",
    "Whole field",
    OTHER,
)

EARS: tuple[str, ...] = ("Left ear", "Right ear", "Both ears", "Inside the head", OTHER)

#: Which side the response appeared on, relative to the stimulated side.
LATERALITIES: tuple[tuple[str, str], ...] = (
    ("contralateral", "Contralateral"),
    ("ipsilateral", "Ipsilateral"),
    ("bilateral", "Bilateral"),
    ("axial", "Axial or midline"),
    ("unspecified", "Not specified"),
)

MOTOR_SIGNS: tuple[tuple[str, str], ...] = (
    ("positive", "Positive (a movement appeared)"),
    ("negative", "Negative (an ongoing movement stopped)"),
)


def localisation_values(category_key: str) -> tuple[str, ...]:
    """The list the localisation widget should offer, empty when none applies."""
    cat = category(category_key)

    if cat is None:
        return ()

    return {
        LOC_BODY: BODY_PARTS,
        LOC_VISUAL_FIELD: VISUAL_FIELDS,
        LOC_EAR: EARS,
    }.get(cat.localisation, ())


# --------------------------------------------------------------------------
# What happened electrically. Two axes, not one: discharges and seizures.
# The four seizure levels are the scheme used in the literature, and they
# are the reason a card can be ranked for localising value at all.
# --------------------------------------------------------------------------

EVENT_DISCHARGES: tuple[tuple[str, str], ...] = (
    ("after_discharges", "After-discharges"),
    ("spikes", "Spikes or polyspikes"),
)

EVENT_SEIZURES: tuple[tuple[str, str], ...] = (
    ("seizure_electroclinical", "Habitual seizure, electro-clinical"),
    ("seizure_aura", "Habitual aura only, no EEG change"),
    ("seizure_subclinical", "Subclinical, EEG change without symptom"),
    ("seizure_atypical", "Non-habitual or atypical seizure"),
)

EVENT_OTHER: tuple[tuple[str, str], ...] = ((OTHER, "Other"),)

EVENTS: tuple[tuple[str, str], ...] = EVENT_DISCHARGES + EVENT_SEIZURES + EVENT_OTHER

EVENT_LABELS: dict[str, str] = dict(EVENTS)

SEIZURE_EVENTS: frozenset[str] = frozenset(k for k, _ in EVENT_SEIZURES)

#: Was the patient's own aura or seizure reproduced. The ACNS Table 4 flags
#: this on two separate columns, which is how much it matters.
HABITUAL: tuple[tuple[str, str], ...] = (
    ("identical", "Identical to the habitual event"),
    ("partial", "Some elements of the habitual event"),
    ("no", "Not habitual"),
    ("unspecified", "Not specified"),
)

#: The ACNS asks for the consistency of the semiology on repeat stimulation.
REPRODUCIBILITY: tuple[tuple[str, str], ...] = (
    ("reproduced", "Reproduced on repeat stimulation"),
    ("not_reproduced", "Not reproduced"),
    ("single_trial", "Tested once"),
)

BEHAVIOURAL_STATES: tuple[tuple[str, str], ...] = (
    ("awake", "Awake"),
    ("drowsy", "Drowsy"),
    ("asleep", "Asleep"),
    ("unspecified", "Not specified"),
)

#: Antiseizure medication, named by the ACNS as a determinant of the chosen
#: intensity: a stimulation off medication does not compare with one on it.
ASM_STATES: tuple[tuple[str, str], ...] = (
    ("unchanged", "Unchanged"),
    ("reduced", "Reduced"),
    ("withdrawn", "Withdrawn"),
    ("unspecified", "Not specified"),
)

POLARITIES: tuple[tuple[str, str], ...] = (
    ("bipolar", "Bipolar"),
    ("monopolar", "Monopolar"),
)


def label_of(pairs: tuple[tuple[str, str], ...], key: str) -> str:
    """The human text of a key, or the key itself when it is unknown."""
    for k, text in pairs:
        if k == key:
            return text

    return str(key)


# --------------------------------------------------------------------------
# The protocol. Defaults come from ACNS Table 2 for SEEG, so that choosing
# a frequency fills the rest and only what differs has to be typed.
# --------------------------------------------------------------------------

LOW_FREQUENCY_HZ = 1.0
HIGH_FREQUENCY_HZ = 50.0

FREQUENCY_PRESETS: tuple[float, ...] = (1.0, 50.0, 60.0)

#: pulse width in us, train duration in s, intensity in mA.
PROTOCOL_LOW = {"pulse_width_us": 500, "train_duration_s": 30.0, "intensity_ma": 3.0}
PROTOCOL_HIGH = {"pulse_width_us": 300, "train_duration_s": 4.0, "intensity_ma": 2.0}

#: Above this, at a pulse width of 250 us or more, the ACNS asks for the
#: charge density to be computed for the contact actually used.
HIGH_CURRENT_WARN_MA = 6.0
WIDE_PULSE_US = 250

#: The table's own upper bound for SEEG stimulation.
MAX_REASONABLE_MA = 10.0


def default_protocol(frequency_hz: float) -> dict[str, Any]:
    """The ACNS Table 2 defaults for a frequency.

    Low frequency is the 1 Hz "shock" protocol, run at a constant 3-5 mA
    with long trains. High frequency is the 50 or 60 Hz "train" protocol,
    with short trains and the current raised until after-discharges appear.
    """
    try:
        hz = float(frequency_hz)
    except (TypeError, ValueError):
        hz = LOW_FREQUENCY_HZ

    return dict(PROTOCOL_LOW if hz <= 5.0 else PROTOCOL_HIGH)


def charge_warning(intensity_ma: float, pulse_width_us: float) -> str | None:
    """A sentence to show beside the current, or None when it is unremarkable.

    This warns, it never blocks: the limit depends on the surface area of
    the contact actually implanted, which this record does not know.
    """
    if intensity_ma is None or pulse_width_us is None:
        return None

    try:
        ma = float(intensity_ma)
        us = float(pulse_width_us)
    except (TypeError, ValueError):
        return None

    if ma > MAX_REASONABLE_MA:
        return (
            f"{ma:g} mA is above the 0.5-10 mA range proposed for SEEG "
            "stimulation. Check the setting."
        )

    if ma > HIGH_CURRENT_WARN_MA and us >= WIDE_PULSE_US:
        return (
            f"{ma:g} mA at {us:g} us is above the usual 6-7 mA maximum. "
            "Compute the charge density for this contact."
        )

    return None


# --------------------------------------------------------------------------
# The pair. Bipolar between two adjacent contacts is the standard, but the
# ACNS lists non-adjacent pairs, pairs across two electrodes and monopolar
# stimulation among its unresolved questions, which means they are done.
# So these are warnings, never refusals. Only a contact paired with itself
# is impossible.
# --------------------------------------------------------------------------


def contact_name(electrode_name: str, contact_index: int) -> str:
    """The label the rest of the app shows: contacts count from 1."""
    return f"{electrode_name}{int(contact_index) + 1}"


def parse_contact_name(text: str, electrodes: list[dict]) -> tuple[int, int] | None:
    """Read "A2" into (electrode id, 0-based contact index).

    Returns None when no electrode bears that name or the contact is out of
    range. Case and surrounding spaces are forgiven; an electrode whose own
    name ends in a digit is matched on the longest name first, so that "A12"
    is read as contact 12 of A rather than contact 2 of A1.
    """
    raw = str(text or "").strip()

    if not raw:
        return None

    names = sorted(
        ((str(e.get("name", "")).strip(), i) for i, e in enumerate(electrodes or [])),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )

    for name, elec_id in names:
        if not name:
            continue

        if raw.lower().startswith(name.lower()):
            digits = raw[len(name) :].strip()

            if not digits.isdigit():
                continue

            number = int(digits)

            if number < 1:
                return None

            contacts = (electrodes[elec_id].get("contacts_lps") or [])

            if number > len(contacts):
                return None

            return elec_id, number - 1

    return None


def pair_warning(
    electrodes: list[dict],
    elec_a: int,
    idx_a: int,
    elec_b: int | None,
    idx_b: int | None,
) -> str | None:
    """What is unusual about this pair, in one sentence, or None.

    A pair this returns a sentence for is still recordable.
    """
    if elec_b is None or idx_b is None:
        return None

    if elec_a != elec_b:
        return (
            "This pair spans two electrodes. Bipolar stimulation of contacts "
            "on different electrodes has no established recommendation."
        )

    if abs(int(idx_a) - int(idx_b)) != 1:
        return "These contacts are not adjacent."

    return None


def pair_error(elec_a: int, idx_a: int, elec_b: int | None, idx_b: int | None) -> str | None:
    """What makes this pair impossible, or None."""
    if elec_b is None or idx_b is None:
        return None

    if int(elec_a) == int(elec_b) and int(idx_a) == int(idx_b):
        return "A contact cannot be stimulated against itself."

    return None


# --------------------------------------------------------------------------
# The record.
# --------------------------------------------------------------------------

ID_PREFIX = "stim-"


def next_id(existing: list[dict]) -> str:
    """A stable id, one past the highest already used."""
    highest = 0

    for record in existing or []:
        raw = str((record or {}).get("id", ""))

        if raw.startswith(ID_PREFIX):
            tail = raw[len(ID_PREFIX) :]

            if tail.isdigit():
                highest = max(highest, int(tail))

    return f"{ID_PREFIX}{highest + 1}"


def new_response(
    category_key: str = "",
    descriptor: str = "",
    *,
    sign: str = "",
    location: str = "",
    laterality: str = "unspecified",
    other: str = "",
    note: str = "",
) -> dict[str, Any]:
    """One response block. A stimulation can carry several."""
    return {
        "category": str(category_key),
        "descriptor": str(descriptor),
        # Motor only: a movement appeared, or an ongoing one stopped.
        "sign": str(sign),
        "location": str(location),
        "laterality": str(laterality),
        # What OTHER means, whenever OTHER was chosen.
        "other": str(other),
        "note": str(note),
    }


#: Passe a la place d'une valeur pour dire "non renseigne". None, lui,
#: veut dire "prends le defaut du protocole".
NOT_SET = object()


def _or_default(value, default, cast):
    """None prend le defaut, NOT_SET reste vide, le reste est converti."""
    if value is NOT_SET:
        return None

    return cast(default if value is None else value)


def new_record(
    *,
    electrode: str,
    contact: int,
    electrode_b: str = "",
    contact_b: int | None = None,
    polarity: str = "bipolar",
    reference: str = "",
    frequency_hz=LOW_FREQUENCY_HZ,
    intensity_ma: float | None = None,
    pulse_width_us: int | None = None,
    train_duration_s: float | None = None,
    threshold_ma: float | None = None,
    at_ad_threshold: bool = False,
    behavioural_state: str = "unspecified",
    asm: str = "unspecified",
    time_since_last_seizure: str = "",
    task: str = "",
    events: list[str] | None = None,
    habitual: str = "unspecified",
    reproducibility: str = "single_trial",
    ad_location: str = "",
    ad_remote: bool = False,
    ad_evolution: str = "",
    aborted: bool = False,
    responses: list[dict] | None = None,
    anatomy: list[str] | None = None,
    eeg_time_s: float | None = None,
    operator: str = "",
    notes: str = "",
    record_id: str = "",
    created: str = "",
) -> dict[str, Any]:
    """Build one stimulation record, filling the protocol from the frequency.

    Contact indices are 0-based here, as everywhere in the state; only the
    labels count from 1.
    """
    defaults = default_protocol(frequency_hz)

    return {
        "id": str(record_id),
        "created": str(created or datetime.now().isoformat(timespec="seconds")),
        "operator": str(operator),
        # ---- the pair
        "polarity": str(polarity),
        "electrode": str(electrode),
        "contact": int(contact),
        "electrode_b": str(electrode_b),
        "contact_b": None if contact_b is None else int(contact_b),
        "reference": str(reference),
        # Filled from the parcellation when one is loaded: a bipolar pair
        # often straddles two regions, and grey and white matter.
        "anatomy": list(anatomy or []),
        # ---- the protocol
        "frequency_hz": _or_default(frequency_hz, LOW_FREQUENCY_HZ, float),
        # Laisse a None par NOT_SET: ces quatre la peuvent ne pas avoir
        # ete notes, et un zero mentirait.
        "intensity_ma": _or_default(intensity_ma, defaults["intensity_ma"], float),
        "pulse_width_us": _or_default(
            pulse_width_us, defaults["pulse_width_us"], int
        ),
        "train_duration_s": _or_default(
            train_duration_s, defaults["train_duration_s"], float
        ),
        "threshold_ma": None if threshold_ma is None else float(threshold_ma),
        "at_ad_threshold": bool(at_ad_threshold),
        # ---- the context
        "behavioural_state": str(behavioural_state),
        "asm": str(asm),
        "time_since_last_seizure": str(time_since_last_seizure),
        "task": str(task),
        # ---- what happened
        "events": [str(e) for e in (events or [])],
        "habitual": str(habitual),
        "reproducibility": str(reproducibility),
        "ad_location": str(ad_location),
        "ad_remote": bool(ad_remote),
        "ad_evolution": str(ad_evolution),
        "aborted": bool(aborted),
        "responses": [dict(r) for r in (responses or [])],
        # ---- back to the trace
        "eeg_time_s": None if eeg_time_s is None else float(eeg_time_s),
        "notes": str(notes),
    }


#: Ce qu'une fiche affiche quand le parametre n'a pas ete note. Un
#: protocole inconnu n'est pas un protocole a zero: inventer un chiffre
#: ferait croire a une mesure.
NOT_AVAILABLE = "NA"


def amount(value, unit: str = "") -> str:
    """Un nombre avec son unite, ou NA quand il n'a pas ete note."""
    if value is None:
        return NOT_AVAILABLE

    try:
        texte = f"{float(value):g}"
    except (TypeError, ValueError):
        return NOT_AVAILABLE

    return f"{texte} {unit}".strip() if unit else texte


def has_seizure(record: dict) -> bool:
    return any(e in SEIZURE_EVENTS for e in (record or {}).get("events", []))


def is_silent(record: dict) -> bool:
    """Tested and nothing happened.

    A silent pair is a result, not a missing one: it is what gives meaning
    to the intensity that was reached.
    """
    record = record or {}
    return not record.get("events") and not record.get("responses")


def pair_label(record: dict) -> str:
    """"A1-A2", or "A1 vs ref" when the stimulation was monopolar."""
    record = record or {}
    a = contact_name(record.get("electrode", ""), record.get("contact", 0))

    if str(record.get("polarity", "")) == "monopolar" or record.get("contact_b") is None:
        reference = str(record.get("reference", "")).strip()
        return f"{a} vs {reference}" if reference else f"{a} (monopolar)"

    b = contact_name(record.get("electrode_b", ""), record.get("contact_b", 0))
    return f"{a}-{b}"


def response_label(response: dict) -> str:
    """One response block as a line of text."""
    response = response or {}
    cat = category(response.get("category", ""))
    bits: list[str] = [
        tr(cat.label) if cat is not None else str(response.get("category", ""))
    ]

    descriptor = str(response.get("descriptor", "")).strip()
    other = str(response.get("other", "")).strip()

    if descriptor == OTHER and other:
        bits.append(other)
    elif descriptor:
        bits.append(tr(descriptor))

    sign = str(response.get("sign", "")).strip()

    if sign:
        bits.append(tr(label_of(MOTOR_SIGNS, sign)).split(" (")[0].lower())

    location = str(response.get("location", "")).strip()
    laterality = str(response.get("laterality", "")).strip()

    side = (
        tr(label_of(LATERALITIES, laterality)).lower()
        if laterality and laterality != "unspecified"
        else ""
    )
    place = tr(location).lower() if location else ""

    if place and side:
        # English puts the side first, French puts it after and in
        # brackets, which also sidesteps the agreement of the adjective.
        bits.append(f"{place} ({side})" if language() == FRENCH else f"{side} {place}")
    elif place or side:
        bits.append(place or side)

    return ", ".join(b for b in bits if b)


def summary_line(record: dict) -> str:
    """The one line the list of cards shows per stimulation."""
    record = record or {}
    head = (
        f"{pair_label(record)}  "
        f"{amount(record.get('frequency_hz'), 'Hz')}  "
        f"{amount(record.get('intensity_ma'), 'mA')}"
    )

    if is_silent(record):
        return f"{head}  {tr('no response')}"

    pieces = [tr(EVENT_LABELS.get(e, e)) for e in record.get("events", [])]
    pieces += [response_label(r) for r in record.get("responses", [])]

    return f"{head}  {' / '.join(p for p in pieces if p)}"


# --------------------------------------------------------------------------
# The filters of the 3D view.
#
# A record passes when it satisfies every active filter. Inside one filter,
# any match counts: asking for motor and visual means either of them, which
# is what someone reaching for a filter means by it.
# --------------------------------------------------------------------------


def empty_filters() -> dict[str, Any]:
    return {
        "min_intensity_ma": None,
        "max_intensity_ma": None,
        "frequencies": set(),
        "events": set(),
        "categories": set(),
        "habitual": set(),
        "only_reproduced": False,
        "include_silent": True,
    }


def matches_filters(record: dict, filters: dict | None) -> bool:
    record = record or {}
    filters = filters or {}

    low = filters.get("min_intensity_ma")
    high = filters.get("max_intensity_ma")
    intensity = record.get("intensity_ma")

    # Un courant non note ne peut etre ni au-dessus ni au-dessous d'une
    # borne: demander une borne l'ecarte, plutot que de le compter pour
    # zero.
    if low is not None or high is not None:
        if intensity is None:
            return False

        if low is not None and float(intensity) < float(low):
            return False

        if high is not None and float(intensity) > float(high):
            return False

    frequencies = filters.get("frequencies") or set()

    if frequencies:
        frequency = record.get("frequency_hz")

        if frequency is None:
            return False

        if float(frequency) not in {float(f) for f in frequencies}:
            return False

    silent = is_silent(record)

    if silent and not filters.get("include_silent", True):
        return False

    events = filters.get("events") or set()

    if events and not (set(record.get("events", [])) & set(events)):
        return False

    categories = filters.get("categories") or set()

    if categories:
        present = {str(r.get("category", "")) for r in record.get("responses", [])}

        if not (present & set(categories)):
            return False

    habitual = filters.get("habitual") or set()

    if habitual and str(record.get("habitual", "")) not in set(habitual):
        return False

    if filters.get("only_reproduced") and str(record.get("reproducibility", "")) != "reproduced":
        return False

    return True


def filters_are_active(filters: dict | None) -> bool:
    """Is anything actually being asked for.

    With nothing asked, the 3D view shows every contact of the
    implantation; the moment a filter is set, it narrows down to what was
    asked. So the difference between "no filter" and "a filter that lets
    everything through" has to be told apart.
    """
    filters = filters or {}
    empty = empty_filters()

    for key, blank in empty.items():
        value = filters.get(key, blank)

        if isinstance(blank, set):
            if set(value or ()):
                return True
        elif value != blank:
            return True

    return False


def contacts_of(records: list[dict]) -> set[tuple[str, int]]:
    """Every contact these stimulations touch, as (electrode, index)."""
    out: set[tuple[str, int]] = set()

    for record in records or []:
        record = record or {}

        try:
            out.add((str(record.get("electrode", "")), int(record.get("contact", 0))))
        except (TypeError, ValueError):
            pass

        if record.get("contact_b") is None:
            continue

        try:
            out.add(
                (str(record.get("electrode_b", "")), int(record.get("contact_b", 0)))
            )
        except (TypeError, ValueError):
            pass

    return out


def filter_records(records: list[dict], filters: dict | None) -> list[dict]:
    return [r for r in (records or []) if matches_filters(r, filters)]


# --------------------------------------------------------------------------
# Where to draw it. For a bipolar pair the current density peaks between the
# two contacts, so that midpoint is the honest place for a marker, rather
# than either contact.
# --------------------------------------------------------------------------


def pair_midpoint_lps(record: dict, electrodes: list[dict]) -> list[float] | None:
    """The point to draw, in the LPS coordinates the state stores."""
    record = record or {}

    first = _contact_lps(record.get("electrode", ""), record.get("contact"), electrodes)

    if first is None:
        return None

    if str(record.get("polarity", "")) == "monopolar" or record.get("contact_b") is None:
        return first

    second = _contact_lps(record.get("electrode_b", ""), record.get("contact_b"), electrodes)

    if second is None:
        return first

    return [(a + b) / 2.0 for a, b in zip(first, second)]


def _contact_lps(name: str, index, electrodes: list[dict]) -> list[float] | None:
    if index is None:
        return None

    for electrode in electrodes or []:
        if str(electrode.get("name", "")).strip() != str(name).strip():
            continue

        contacts = electrode.get("contacts_lps") or []

        if 0 <= int(index) < len(contacts):
            return [float(v) for v in contacts[int(index)][:3]]

    return None


# --------------------------------------------------------------------------
# The identity card. Formatted here rather than in the window so that what a
# card says can be tested without building a window to read it.
# --------------------------------------------------------------------------


def _event_text(record: dict) -> str:
    return ", ".join(tr(EVENT_LABELS.get(e, e)) for e in record.get("events", []))


def _discharge_text(record: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    where = str(record.get("ad_location", "")).strip()

    if where or record.get("ad_remote"):
        remote = f" ({tr('remote')})" if record.get("ad_remote") else ""
        rows.append(("Discharge seen at", f"{where}{remote}".strip()))

    evolution = str(record.get("ad_evolution", "")).strip()

    if evolution:
        rows.append(("Evolution", evolution))

    if record.get("aborted"):
        rows.append(("Interrupted", tr("the stimulation had to be stopped")))

    return rows


def card_fields(record: dict) -> list[tuple[str, str]]:
    """One stimulation as label and value pairs, in reading order.

    Only what was filled in appears: an empty line on a clinical card is
    noise, and noise is what stops a card being read.
    """
    record = record or {}
    rows: list[tuple[str, str]] = [("Pair", pair_label(record))]

    anatomy = [str(a) for a in record.get("anatomy", []) if str(a).strip()]

    if anatomy:
        rows.append(("Anatomy", "   ".join(anatomy)))

    rows.append(
        (
            "Protocol",
            f"{amount(record.get('frequency_hz'), 'Hz')}, "
            f"{amount(record.get('intensity_ma'), 'mA')}, "
            f"{amount(record.get('pulse_width_us'), 'µs')}, "
            f"{tr('train')} {amount(record.get('train_duration_s'), 's')}",
        )
    )

    if record.get("threshold_ma") is not None:
        rows.append(("Response threshold", f"{float(record['threshold_ma']):g} mA"))

    if record.get("at_ad_threshold"):
        rows.append(("Current", tr("at the after-discharge threshold")))

    for label, pairs, key in (
        ("Patient", BEHAVIOURAL_STATES, "behavioural_state"),
        ("Medication", ASM_STATES, "asm"),
    ):
        value = str(record.get(key, ""))

        if value and value != "unspecified":
            rows.append((label, tr(label_of(pairs, value))))

    for label, key in (
        ("Since last seizure", "time_since_last_seizure"),
        ("Task", "task"),
    ):
        value = str(record.get(key, "")).strip()

        if value:
            rows.append((label, value))

    if is_silent(record):
        rows.append(
            (
                "Result",
                f"{tr('tested, no response at')} "
                f"{amount(record.get('intensity_ma'), 'mA')}",
            )
        )
    else:
        events = _event_text(record)

        if events:
            rows.append(("On the trace", events))

    habitual = str(record.get("habitual", ""))

    if habitual and habitual != "unspecified":
        rows.append(("Habitual event", tr(label_of(HABITUAL, habitual))))

    reproducibility = str(record.get("reproducibility", ""))

    if reproducibility:
        rows.append(
            ("Reproducibility", tr(label_of(REPRODUCIBILITY, reproducibility)))
        )

    rows.extend(_discharge_text(record))

    for index, response in enumerate(record.get("responses", []), start=1):
        label = tr("Response") if index == 1 else f"{tr('Response')} {index}"
        text = response_label(response)
        note = str(response.get("note", "")).strip()
        rows.append((label, f"{text} - {note}" if note else text))

    notes = str(record.get("notes", "")).strip()

    if notes:
        rows.append(("Notes", notes))

    operator = str(record.get("operator", "")).strip()

    if operator:
        rows.append(("Interpreted by", operator))

    created = str(record.get("created", "")).strip()

    if created:
        rows.append(("Recorded", created.replace("T", " ")))

    return rows


def card_text(record: dict) -> str:
    """The card as plain text, for reading and for copying out."""
    return "\n".join(
        f"{tr(label)}: {value}" for label, value in card_fields(record)
    )


# --------------------------------------------------------------------------
# The colour of a marker in the 3D view.
#
# Ranked by what the finding is worth for the epileptogenic zone, not by
# category, so that a glance at the map answers the question the map is
# there for. The international survey ranks a habitual seizure induced at
# 1 Hz as the most localising finding of all, and a habitual aura without
# an EEG correlate above a habitual seizure at 50 Hz.
# --------------------------------------------------------------------------

COLOUR_HABITUAL = "#FF2D55"
COLOUR_PARTIAL = "#FF8000"
COLOUR_SEIZURE = "#FFC400"
COLOUR_RESPONSE = "#36C5F0"
COLOUR_DISCHARGE = "#C8D11A"
COLOUR_SILENT = "#7A7F8C"

#: Read top to bottom beside the view, which is the order of the scale.
COLOUR_LEGEND: tuple[tuple[str, str], ...] = (
    (COLOUR_HABITUAL, "habitual event reproduced"),
    (COLOUR_PARTIAL, "some elements of the habitual event"),
    (COLOUR_SEIZURE, "seizure, not habitual"),
    (COLOUR_RESPONSE, "clinical response, no seizure"),
    (COLOUR_DISCHARGE, "discharges only"),
    (COLOUR_SILENT, "tested, no response"),
)


def marker_colour(record: dict) -> str:
    """The colour of this stimulation in the 3D view."""
    record = record or {}

    if is_silent(record):
        return COLOUR_SILENT

    habitual = str(record.get("habitual", ""))

    if has_seizure(record):
        if habitual == "identical":
            return COLOUR_HABITUAL

        if habitual == "partial":
            return COLOUR_PARTIAL

        return COLOUR_SEIZURE

    # A habitual aura can be recorded without any seizure event ticked.
    if habitual in ("identical", "partial"):
        return COLOUR_HABITUAL if habitual == "identical" else COLOUR_PARTIAL

    if record.get("responses"):
        return COLOUR_RESPONSE

    return COLOUR_DISCHARGE

# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""English and French for the stimulation windows.

WHY A DICTIONARY AND NOT QT LINGUIST

Qt has a translation system, and it is the right answer for a whole
application: compiled .qm files, a tool to extract the strings, context
per class. It is the wrong answer for two windows, because it adds a
build step and a binary file to ship for a hundred and fifty sentences.

So: one dictionary, keyed by the English text, read at display time. A key
that is missing falls back to the English rather than to an empty label,
because an untranslated word is readable and a blank one is not.

THE TERMS ARE CLINICAL, NOT LITERAL

"Habitual seizure" is a seizure habituelle, not a crise habituee.
"Speech arrest" is an arret du langage. "After-discharges" are
post-decharges. Where French epileptology has its own word, that word is
used rather than a translation of the English one.

WHAT IS NOT TRANSLATED

Contact names, electrode names, the anatomical labels that come from
FreeSurfer, and anything the user typed. Translating those would make a
card say something its author did not write.
"""

from __future__ import annotations

ENGLISH = "en"
FRENCH = "fr"

LANGUAGES: tuple[tuple[str, str], ...] = ((ENGLISH, "English"), (FRENCH, "Francais"))

_current = ENGLISH

#: English text to French. The keys are the exact strings used in the code.
FR: dict[str, str] = {
    # ------------------------------------------------ the windows
    "Stimulation result": "Resultat de stimulation",
    "Stimulation results": "Resultats de stimulation",
    "Cancel": "Annuler",
    "Save": "Enregistrer",
    "Close": "Fermer",
    "Edit": "Modifier",
    "Delete": "Supprimer",
    "+ Add a stimulation": "+ Ajouter une stimulation",
    "Export all": "Tout exporter",
    "Every stimulation of this patient, in one file": (
        "Toutes les stimulations de ce patient, dans un seul fichier"
    ),
    "Export every stimulation result": (
        "Exporter tous les resultats de stimulation"
    ),
    "Table, report or the records themselves": (
        "Tableau, rapport, ou les enregistrements eux-memes"
    ),
    "Export the stimulation results": "Exporter les resultats de stimulation",
    "There is nothing to export yet.": "Il n'y a encore rien a exporter.",
    "Could not write the file": "Impossible d'ecrire le fichier",
    "stimulation(s) written to": "stimulation(s) ecrites dans",
    "Table (*.csv);;Table, tab separated (*.tsv);;Report (*.txt);;Records (*.json)": (
        "Tableau (*.csv);;Tableau, separe par tabulations (*.tsv);;"
        "Rapport (*.txt);;Enregistrements (*.json)"
    ),
    "No electrode is reconstructed yet.": "Aucune electrode n'est reconstruite.",
    "stimulated from": "stimule depuis",
    "Name the contact the current was applied from.": (
        "Nommez le contact depuis lequel le courant a ete applique."
    ),
    "Visualisation filters": "Filtres d'affichage",
    "Appearance": "Apparence",
    "Stimulation cards": "Fiches de stimulation",
    "Language": "Langue",
    # ------------------------------------------------ the pair
    "the stimulated pair": "la paire stimulee",
    "polarity": "polarite",
    "Bipolar": "Bipolaire",
    "Monopolar": "Monopolaire",
    "stimulated against": "stimule contre",
    "type it or pick it": "a taper ou a choisir",
    "remote reference": "reference distante",
    "e.g. scalp Fz": "par exemple Fz au scalp",
    "Which two contacts carried the current. Bipolar between two "
    "adjacent contacts is the usual case, and is already filled in.": (
        "Quels deux contacts ont porte le courant. Le bipolaire entre deux "
        "contacts adjacents est le cas habituel, et il est deja rempli."
    ),
    "Name the second contact of the pair.": "Nommez le second contact de la paire.",
    "A contact cannot be stimulated against itself.": (
        "Un contact ne peut pas etre stimule contre lui-meme."
    ),
    "These contacts are not adjacent.": "Ces contacts ne sont pas adjacents.",
    "This pair spans two electrodes. Bipolar stimulation of contacts "
    "on different electrodes has no established recommendation.": (
        "Cette paire est a cheval sur deux electrodes. La stimulation "
        "bipolaire de contacts d'electrodes differentes n'a pas de "
        "recommandation etablie."
    ),
    # ------------------------------------------------ the protocol
    "stimulation protocol": "protocole de stimulation",
    "frequency (Hz)": "frequence (Hz)",
    "current": "courant",
    "pulse width": "largeur d'impulsion",
    "train duration": "duree du train",
    "tube thickness": "epaisseur du tube",
    "contact size": "taille des contacts",
    "Choosing the frequency fills the rest with the usual values.": (
        "Choisir la frequence remplit le reste avec les valeurs usuelles."
    ),
    "Leave it all empty for a pair tested that stayed silent.": (
        "Laissez tout vide pour une paire testee restee muette."
    ),
    "Tested and silent, unless you add one.": (
        "Testee et muette, sauf si vous en ajoutez une."
    ),
    "Nothing ticked means every pair.": "Rien de coche veut dire toutes les paires.",
    "The first rule that matches wins, so the order counts.": (
        "La premiere regle qui correspond gagne, donc l'ordre compte."
    ),
    "No rule yet.": "Aucune regle.",
    "current (mA)": "courant (mA)",
    "pulse width (us)": "largeur d'impulsion (us)",
    "train duration (s)": "duree du train (s)",
    "response threshold": "seuil de reponse",
    "the lowest current that produced it, if you looked for it": (
        "le courant le plus bas qui l'a produite, si vous l'avez cherche"
    ),
    "the current was at the after-discharge threshold": (
        "le courant etait au seuil de post-decharge"
    ),
    "1 Hz and 50 Hz are two different examinations at the same "
    "current, and the charge is the current times the pulse width. "
    "Choosing the frequency fills the rest.": (
        "1 Hz et 50 Hz sont deux examens differents au meme courant, et la "
        "charge est le produit du courant par la largeur d'impulsion. "
        "Choisir la frequence remplit le reste."
    ),
    # ------------------------------------------------ the conditions
    "conditions of the examination": "conditions de l'examen",
    "patient was": "le patient etait",
    "medication": "traitement",
    "since the last seizure": "depuis la derniere crise",
    "task performed during the stimulation": "tache pendant la stimulation",
    "e.g. 2 days": "par exemple 2 jours",
    "counting, naming, reading, holding a posture": (
        "comptage, denomination, lecture, maintien d'une posture"
    ),
    "These decide which intensity was reasonable. The task matters "
    "most for language: a response to a word cannot be read without "
    "knowing what was asked.": (
        "Elles decident de l'intensite raisonnable. La tache compte surtout "
        "pour le langage: une reponse a un mot ne se lit pas sans savoir ce "
        "qui etait demande."
    ),
    "Awake": "Eveille",
    "Drowsy": "Somnolent",
    "Asleep": "Endormi",
    "Not specified": "Non precise",
    "no response": "pas de reponse",
    "tested, no response at": "testee, pas de reponse a",
    "remote": "a distance",
    "response": "reponse",
    "Unchanged": "Inchange",
    "Reduced": "Diminue",
    "Withdrawn": "Arrete",
    # ------------------------------------------------ what happened
    "what happened on the trace": "ce qui s'est passe sur le trace",
    "discharges": "decharges",
    "seizure": "crise",
    "After-discharges": "Post-decharges",
    "Spikes or polyspikes": "Pointes ou polypointes",
    "Habitual seizure, electro-clinical": "Crise habituelle, electro-clinique",
    "Habitual aura only, no EEG change": "Aura habituelle seule, sans trace EEG",
    "Subclinical, EEG change without symptom": (
        "Infraclinique, trace EEG sans symptome"
    ),
    "Non-habitual or atypical seizure": "Crise non habituelle ou atypique",
    "Something else, described in the notes": "Autre chose, decrite dans les notes",
    "Tick everything that applies. Leave it all empty for a pair "
    "tested that stayed silent: the card will say so, with the "
    "current it was pushed to.": (
        "Cochez tout ce qui s'applique. Laissez tout vide pour une paire "
        "testee restee muette: la fiche le dira, avec le courant atteint."
    ),
    "was the patient's own event reproduced": (
        "l'evenement propre au patient a-t-il ete reproduit"
    ),
    "the single most localising thing a card can say": (
        "ce qu'une fiche peut dire de plus localisateur"
    ),
    "seen again on repeat stimulation": "revu a la stimulation repetee",
    "a response seen once does not weigh the same": (
        "une reponse vue une seule fois ne pese pas pareil"
    ),
    "Identical to the habitual event": "Identique a l'evenement habituel",
    "Some elements of the habitual event": "Certains elements de l'evenement habituel",
    "Not habitual": "Non habituel",
    "Reproduced on repeat stimulation": "Reproduite a la stimulation repetee",
    "Not reproduced": "Non reproduite",
    "Tested once": "Testee une seule fois",
    "about that discharge": "a propos de cette decharge",
    "where it was seen": "ou elle a ete vue",
    "the stimulated contacts, and any contact it spread to": (
        "les contacts stimules, et tout contact vers lequel elle s'est propagee"
    ),
    "away from the stimulated contacts": "a distance des contacts stimules",
    "how it evolved": "comment elle a evolue",
    "morphology, frequency, how far it spread": (
        "morphologie, frequence, jusqu'ou elle s'est propagee"
    ),
    "the stimulation had to be interrupted": "la stimulation a du etre interrompue",
    # ------------------------------------------------ the responses
    "clinical responses": "reponses cliniques",
    "+ add a response": "+ ajouter une reponse",
    "kind of response": "type de reponse",
    "what exactly": "quoi exactement",
    "movement": "mouvement",
    "positive: it appeared. negative: it stopped.": (
        "positif: il est apparu. negatif: il s'est arrete."
    ),
    "where": "ou",
    "where on the body": "ou sur le corps",
    "which part of the visual field": "dans quelle partie du champ visuel",
    "which ear": "quelle oreille",
    "which side": "quel cote",
    "relative to the stimulated side": "par rapport au cote stimule",
    "describe it": "decrivez-la",
    "in your own words": "avec vos mots",
    "note on this response": "note sur cette reponse",
    "latency, how long it lasted, what the patient said": (
        "latence, duree, ce que le patient a dit"
    ),
    "What the patient did, felt, or could no longer do. One block "
    "per response, each keeping its own localisation.": (
        "Ce que le patient a fait, ressenti, ou ne pouvait plus faire. Un "
        "bloc par reponse, chacun gardant sa propre localisation."
    ),
    "No response block yet. Left as it is, this pair is recorded as "
    "tested and silent.": (
        "Aucun bloc de reponse. En l'etat, cette paire est enregistree comme "
        "testee et muette."
    ),
    "Positive (a movement appeared)": "Positif (un mouvement est apparu)",
    "Negative (an ongoing movement stopped)": (
        "Negatif (un mouvement en cours s'est arrete)"
    ),
    "Contralateral": "Controlateral",
    "Ipsilateral": "Ipsilateral",
    "Bilateral": "Bilateral",
    "Axial or midline": "Axial ou median",
    # ------------------------------------------------ the categories
    "Motor": "Moteur",
    "Somatosensory": "Somatosensoriel",
    "Visual": "Visuel",
    "Auditory": "Auditif",
    "Olfactory or gustatory": "Olfactif ou gustatif",
    "Vestibular": "Vestibulaire",
    "Autonomic": "Vegetatif",
    "Affective": "Affectif",
    "Cognitive": "Cognitif",
    "Other": "Autre",
    "other": "autre",
    # ------------------------------------------------ the notes
    "notes and provenance": "notes et provenance",
    "free notes": "notes libres",
    "anything that bears on reading this card later: pain, distraction, "
    "what the patient said in their own words": (
        "tout ce qui compte pour relire cette fiche plus tard: douleur, "
        "distraction, ce que le patient a dit avec ses mots"
    ),
    "interpreted by": "interprete par",
    "initials": "initiales",
    "pair stimulated from": "paire stimulee depuis",
    # ------------------------------------------------ the filters
    "current and protocol": "courant et protocole",
    "from": "a partir de",
    "up to": "jusqu'a",
    "frequency": "frequence",
    "include pairs tested without a response": (
        "inclure les paires testees sans reponse"
    ),
    "only responses reproduced on repeat stimulation": (
        "seulement les reponses reproduites a la stimulation repetee"
    ),
    "Tick a bound to use it. Inside one filter, ticking two boxes "
    "means either of them; between filters, every tick must be "
    "satisfied.": (
        "Cochez une borne pour l'utiliser. Dans un meme filtre, cocher deux "
        "cases veut dire l'une ou l'autre; entre filtres, toutes les cases "
        "cochees doivent etre satisfaites."
    ),
    "show only the pairs where this happened": (
        "ne montrer que les paires ou cela s'est produit"
    ),
    "Nothing ticked means every pair, whatever happened.": (
        "Rien de coche veut dire toutes les paires, quoi qu'il se soit passe."
    ),
    "show only the pairs that gave this response": (
        "ne montrer que les paires ayant donne cette reponse"
    ),
    "show only the pairs that reproduced the habitual event": (
        "ne montrer que les paires ayant reproduit l'evenement habituel"
    ),
    "A habitual seizure induced at 1 Hz is the most localising "
    "finding of all, ahead of a habitual aura without an EEG "
    "change, itself ahead of a habitual seizure at 50 Hz.": (
        "Une crise habituelle induite a 1 Hz est la trouvaille la plus "
        "localisatrice de toutes, devant une aura habituelle sans trace EEG, "
        "elle-meme devant une crise habituelle a 50 Hz."
    ),
    "Show everything": "Tout remontrer",
    "stimulations shown in the 3D view": "stimulations montrees dans la vue 3D",
    "Delete this stimulation": "Supprimer cette stimulation",
    "Delete the stimulation": "Supprimer la stimulation",
    "It was entered by hand and cannot be recomputed.": (
        "Elle a ete saisie a la main et ne se recalcule pas."
    ),
    "No stimulation recorded yet.": "Aucune stimulation enregistree.",
    "Select a stimulation on the left.": "Choisissez une stimulation a gauche.",
    # ------------------------------------------------ the appearance
    "what the colour means": "ce que la couleur signifie",
    "colour decided by": "couleur decidee par",
    "that one colour": "cette couleur",
    "What the finding is worth": "Ce que vaut la trouvaille",
    "The kind of clinical response": "Le type de reponse clinique",
    "My own rules": "Mes propres regles",
    "One colour for all": "Une seule couleur pour tout",
    "where it is drawn, and how big": "ou c'est dessine, et de quelle taille",
    "draw the result as": "dessiner le resultat en",
    "A tube between the two contacts": "Un tube entre les deux contacts",
    "A mark on each contact": "Une marque sur chaque contact",
    "Both": "Les deux",
    "tube thickness (mm)": "epaisseur du tube (mm)",
    "contact size (mm)": "taille des contacts (mm)",
    "opacity": "opacite",
    "colour of every contact": "couleur de chaque contact",
    "the grey background of the mode": "le fond gris du mode",
    "Every contact of the implantation is drawn in grey, with no "
    "shaft. A bipolar pair is then drawn between its two contacts, "
    "where the current density peaks, unless you ask for the "
    "colour to sit on the contacts instead.": (
        "Chaque contact de l'implantation est dessine en gris, sans tige. "
        "Une paire bipolaire est ensuite dessinee entre ses deux contacts, "
        "la ou la densite de courant est maximale, sauf si vous demandez que "
        "la couleur soit portee par les contacts."
    ),
    "my rules": "mes regles",
    "Load this set": "Charger ce jeu",
    "+ make a rule from the current filters": (
        "+ faire une regle avec les filtres actuels"
    ),
    "A rule is a condition and a colour. The first rule that "
    "matches wins, so the order counts. Set the filters on the "
    "first tab, then turn them into a rule: a condition is then "
    "written in one place only.": (
        "Une regle est une condition et une couleur. La premiere regle qui "
        "correspond gagne, donc l'ordre compte. Posez les filtres dans le "
        "premier onglet, puis transformez-les en regle: une condition ne "
        "s'ecrit alors qu'a un seul endroit."
    ),
    "No rule yet. Rules are used only when the colour above is "
    "decided by them.": (
        "Aucune regle. Les regles ne servent que si la couleur ci-dessus est "
        "decidee par elles."
    ),
    "name of this rule": "nom de cette regle",
    "Colour of this rule": "Couleur de cette regle",
    "Eloquent cortex": "Cortex eloquent",
    "Response thresholds": "Seuils de reponse",
    "matched by no rule": "ne correspond a aucune regle",
    "every stimulation": "toutes les stimulations",
    "Every stimulation": "Toutes les stimulations",
    # ------------------------------------------------ the legend
    "habitual event reproduced": "evenement habituel reproduit",
    "some elements of the habitual event": (
        "certains elements de l'evenement habituel"
    ),
    "seizure, not habitual": "crise, non habituelle",
    "clinical response, no seizure": "reponse clinique, sans crise",
    "discharges only": "decharges seulement",
    "tested, no response": "testee, sans reponse",
    "colour of a marker in the 3D view": "couleur d'un marqueur dans la vue 3D",
    "A bipolar pair is drawn midway between its two contacts, "
    "where the current density peaks.": (
        "Une paire bipolaire est dessinee a mi-chemin entre ses deux "
        "contacts, la ou la densite de courant est maximale."
    ),
    # ------------------------------------------------ the card
    "Pair": "Paire",
    "Anatomy": "Anatomie",
    "Protocol": "Protocole",
    "Response threshold": "Seuil de reponse",
    "Current": "Courant",
    "Patient": "Patient",
    "Medication": "Traitement",
    "Since last seizure": "Depuis la derniere crise",
    "Task": "Tache",
    "Result": "Resultat",
    "On the trace": "Sur le trace",
    "Habitual event": "Evenement habituel",
    "Reproducibility": "Reproductibilite",
    "Discharge seen at": "Decharge vue en",
    "Evolution": "Evolution",
    "Interrupted": "Interrompue",
    "Response": "Reponse",
    "Notes": "Notes",
    "Interpreted by": "Interprete par",
    "Recorded": "Enregistree",
    "at the after-discharge threshold": "au seuil de post-decharge",
    "the stimulation had to be stopped": "la stimulation a du etre arretee",
}


from .i18n_terms import FR_TERMS  # noqa: E402

# The clinical terms live in their own module: they are checked against
# what a French-speaking epileptologist writes, not against the English.
FR.update(FR_TERMS)


def language() -> str:
    return _current


def set_language(code: str) -> None:
    """Pick the language the stimulation windows speak."""
    global _current
    _current = FRENCH if str(code) == FRENCH else ENGLISH


def tr(text: str) -> str:
    """The text in the current language, or the English when it is missing.

    A missing key gives back the English rather than an empty string: an
    untranslated word can still be read, a blank label cannot.
    """
    if _current != FRENCH:
        return str(text)

    return FR.get(str(text), str(text))


def tr_pairs(pairs) -> list[tuple[str, str]]:
    """Translate the labels of a (key, label) vocabulary, keys untouched."""
    return [(key, tr(label)) for key, label in pairs or ()]


def tr_all(values) -> list[str]:
    return [tr(v) for v in values or ()]

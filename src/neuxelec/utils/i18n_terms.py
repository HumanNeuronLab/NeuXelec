# NeuXelec, localisation d'electrodes SEEG et imagerie multimodale.
# Copyright (C) 2026 Hopitaux Universitaires de Geneve
#                    et Universite de Geneve.
# Auteur: Jules Veber, Human Neuron Lab.
#
# Ce programme est un logiciel libre, distribue sous licence GNU General
# Public License version 3 ou ulterieure. Voir le fichier LICENSE.
# SPDX-License-Identifier: GPL-3.0-or-later
"""The clinical vocabulary in French, kept apart from the window strings.

Separate because these are terms, not sentences: they are the words a
French-speaking epileptologist writes in a report, and they are checked
against that, not against the English they are placed beside. Where
French has its own word, that word wins: a seizure habituelle, an arret
du langage, des post-decharges, une sensation epigastrique ascendante.

Two notes on choices that are not obvious:

- the ILAE separates an ILLUSION, which distorts something really there,
  from a HALLUCINATION, which has no object. French keeps the same two
  words, so the distinction survives the translation.
- deja-vu and jamais-vu are French in the English list already, so they
  lose their parenthetical gloss here rather than gain one.
"""

from __future__ import annotations

FR_TERMS: dict[str, str] = {
    # --------------------------------------------------------- motor
    "Tonic posturing": "Posture tonique",
    "Clonic jerks": "Secousses cloniques",
    "Dystonic posturing": "Posture dystonique",
    "Versive movement or eye deviation": "Mouvement versif ou deviation oculaire",
    "Head turning": "Rotation de la tete",
    "Automatism": "Automatisme",
    "Myoclonus": "Myoclonie",
    "Movement arrest": "Arret du mouvement",
    "Loss of muscle tone": "Perte du tonus musculaire",
    # --------------------------------------------------------- language
    "Speech arrest": "Arret du langage",
    "Anomia": "Manque du mot",
    "Semantic paraphasia": "Paraphasie semantique",
    "Phonemic paraphasia": "Paraphasie phonemique",
    "Circumlocution": "Circonlocution",
    "Neologism": "Neologisme",
    "Dysarthria": "Dysarthrie",
    "Apraxia of speech": "Apraxie de la parole",
    "Comprehension impairment": "Trouble de la comprehension",
    "Reading impairment": "Trouble de la lecture",
    "Writing impairment": "Trouble de l'ecriture",
    "Counting arrest": "Arret du comptage",
    "Perseveration": "Perseveration",
    # --------------------------------------------------- somatosensory
    "Tingling or paresthesia": "Fourmillements ou paresthesies",
    "Numbness": "Engourdissement",
    "Buzzing": "Bourdonnement",
    "Burning": "Brulure",
    "Pain": "Douleur",
    "Thermal sensation": "Sensation thermique",
    "Electric sensation": "Sensation electrique",
    "Illusion of movement": "Illusion de mouvement",
    "Cephalic sensation": "Sensation cephalique",
    # --------------------------------------------------------- visual
    "Phosphenes": "Phosphenes",
    "Colours": "Couleurs",
    "Simple geometric shapes": "Formes geometriques simples",
    "Blurring": "Flou visuel",
    "Scotoma": "Scotome",
    "Visual field loss": "Amputation du champ visuel",
    "Complex visual hallucination": "Hallucination visuelle complexe",
    "Visual illusion (micropsia, macropsia, metamorphopsia)": (
        "Illusion visuelle (micropsie, macropsie, metamorphopsie)"
    ),
    "Palinopsia": "Palinopsie",
    # --------------------------------------------------------- auditory
    "Tinnitus": "Acouphene",
    "Humming": "Ronronnement",
    "Pure tone": "Son pur",
    "Change in loudness": "Changement d'intensite sonore",
    "Complex sound": "Son complexe",
    "Voices": "Voix",
    "Music": "Musique",
    "Auditory illusion": "Illusion auditive",
    # ---------------------------------------------- olfactory, gustatory
    "Unpleasant odour": "Odeur desagreable",
    "Pleasant odour": "Odeur agreable",
    "Indefinable odour": "Odeur indefinissable",
    "Metallic taste": "Gout metallique",
    "Bitter taste": "Gout amer",
    "Sweet taste": "Gout sucre",
    "Salty taste": "Gout sale",
    "Acid taste": "Gout acide",
    # ------------------------------------------------------ vestibular
    "Vertigo or rotation": "Vertige ou rotation",
    "Sensation of body displacement": "Sensation de deplacement du corps",
    "Floating": "Sensation de flottement",
    "Falling": "Sensation de chute",
    "Tilting": "Sensation de bascule",
    # ------------------------------------------------------- autonomic
    "Epigastric rising sensation": "Sensation epigastrique ascendante",
    "Abdominal sensation": "Sensation abdominale",
    "Nausea": "Nausee",
    "Palpitations": "Palpitations",
    "Tachycardia": "Tachycardie",
    "Bradycardia": "Bradycardie",
    "Respiratory change": "Modification respiratoire",
    "Hypersalivation": "Hypersalivation",
    "Flushing": "Bouffee vasomotrice",
    "Pallor": "Paleur",
    "Sweating": "Sudation",
    "Piloerection": "Piloerection",
    "Pupillary change": "Modification pupillaire",
    "Urge to urinate": "Envie d'uriner",
    # ------------------------------------------------------- affective
    "Fear or anxiety": "Peur ou anxiete",
    "Sadness": "Tristesse",
    "Joy or pleasure": "Joie ou plaisir",
    "Mirth or laughter": "Hilarite ou rire",
    "Anger": "Colere",
    "Erotic sensation": "Sensation erotique",
    # ------------------------------------------------------- cognitive
    "Deja-vu (familiarity)": "Deja-vu (familiarite)",
    "Jamais-vu (unfamiliarity)": "Jamais-vu (etrangete)",
    "Dreamy state": "Etat de reve",
    "Reminiscence": "Reminiscence",
    "Forced thinking": "Pensee forcee",
    "Depersonalisation": "Depersonnalisation",
    "Derealisation": "Derealisation",
    "Out-of-body experience": "Experience de sortie du corps",
    "Ictal amnesia": "Amnesie ictale",
    "Acalculia": "Acalculie",
    "Neglect": "Negligence",
    "Apraxia": "Apraxie",
    "Confusion": "Confusion",
    # ----------------------------------------------------------- other
    "Indescribable aura": "Aura indescriptible",
    # ------------------------------------------------------ body parts
    "Face": "Visage",
    "Lips": "Levres",
    "Tongue": "Langue",
    "Mouth": "Bouche",
    "Pharynx or larynx": "Pharynx ou larynx",
    "Head": "Tete",
    "Neck": "Cou",
    "Shoulder": "Epaule",
    "Arm": "Bras",
    "Elbow": "Coude",
    "Forearm": "Avant-bras",
    "Wrist": "Poignet",
    "Hand": "Main",
    "Thumb": "Pouce",
    "Fingers": "Doigts",
    "Trunk": "Tronc",
    "Abdomen": "Abdomen",
    "Back": "Dos",
    "Hip": "Hanche",
    "Leg": "Jambe",
    "Knee": "Genou",
    "Foot": "Pied",
    "Toes": "Orteils",
    "Genital": "Genital",
    "Whole hemibody": "Hemicorps entier",
    # --------------------------------------------------- visual fields
    "Left hemifield": "Hemichamp gauche",
    "Right hemifield": "Hemichamp droit",
    "Upper left quadrant": "Quadrant superieur gauche",
    "Upper right quadrant": "Quadrant superieur droit",
    "Lower left quadrant": "Quadrant inferieur gauche",
    "Lower right quadrant": "Quadrant inferieur droit",
    "Central": "Central",
    "Whole field": "Champ entier",
    # ------------------------------------------------------------ ears
    "Left ear": "Oreille gauche",
    "Right ear": "Oreille droite",
    "Both ears": "Les deux oreilles",
    "Inside the head": "Dans la tete",
}

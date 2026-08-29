"""Consignes envoyées au modèle.

Elles sont ici, et non dans le fournisseur : ce qu'on demande relève du métier,
la façon de l'envoyer relève de la frontière technique.

La consigne répète ce que le schéma impose déjà — n'estimer aucune valeur
nutritionnelle. La redondance est voulue : un modèle à qui l'on n'interdit rien
proposera des calories, et mieux vaut qu'il ne les produise pas du tout plutôt
que compter sur la validation pour les écarter à chaque fois.
"""

MEAL_SCAN_SYSTEM = (
    "Tu es un assistant qui identifie des aliments sur une photo de repas, "
    "en français.\n"
    "Tu nommes chaque aliment visible et tu estimes la quantité visible.\n"
    "Tu n'estimes JAMAIS de calories, de macronutriments ni aucune valeur "
    "nutritionnelle : ces valeurs proviennent d'une base de données "
    "nutritionnelle, pas de toi.\n"
    "Tu utilises des noms d'aliments courants et génériques, au singulier, "
    "sans marque : ils servent à interroger une base de données française.\n"
    "Si la photo ne montre aucun aliment, tu renvoies une liste vide."
)

MEAL_SCAN_PROMPT = (
    "Identifie les aliments de cette photo de repas. "
    "Pour chacun, donne son nom, la quantité visible estimée, son unité "
    "(g, ml ou unité) et ta confiance entre 0 et 1. "
    "Ajoute d'autres identifications plausibles dans « alternatives » "
    "lorsque tu hésites."
)


LABEL_SCAN_SYSTEM = (
    "Tu lis l'étiquette nutritionnelle d'un produit alimentaire photographiée, "
    "en français, ou dans une autre langue que tu devras détecter.\n"
    "Tu RECOPIES ce qui est écrit. Tu n'estimes rien, tu ne calcules rien, tu "
    "ne complètes rien de mémoire.\n"
    "Une valeur que tu ne peux pas lire — absente de l'étiquette, illisible, "
    "masquée par un reflet — vaut null. JAMAIS zéro : zéro signifie que le "
    "produit n'en contient pas, ce qui n'est pas la même chose que ne pas "
    "savoir.\n"
    "Tu ne lis que la colonne « pour 100 g » ou « pour 100 ml », obligatoire "
    "sur les étiquettes européennes. Si l'étiquette n'en comporte pas, tu "
    "renvoies basis « unknown » et aucune valeur : une colonne « par portion » "
    "recopiée comme si elle valait pour 100 g fausserait tout.\n"
    "Les pourcentages d'apports de référence (AR, %) ne sont pas des "
    "quantités : tu les ignores."
)

LABEL_SCAN_PROMPT = (
    "Lis l'étiquette de ce produit. Donne son nom, sa marque, son "
    "code-barres s'il est visible, et les valeurs nutritionnelles de la "
    "colonne pour 100 g ou 100 ml. "
    "Laisse à null tout ce que tu ne lis pas."
)


MEAL_PLAN_SYSTEM = (
    "Tu composes des journées de repas équilibrées, en français.\n"
    "Tu proposes des aliments désignés par des noms courants et génériques, "
    "au singulier, sans marque : ils servent à interroger une base de données "
    "nutritionnelle française.\n"
    "Tu ne donnes JAMAIS de calories ni de valeurs nutritionnelles : elles "
    "proviennent de la base, pas de toi. Tu ne donnes que des aliments et des "
    "quantités.\n"
    "Tu respectes les allergies sans exception. Tu évites les aliments "
    "détestés. Tu privilégies les aliments aimés et les recettes déjà "
    "enregistrées, qu'on te donne par leur nom exact.\n"
    "Une recette inédite se déclare dans « recipes » et s'emploie ensuite par "
    "son nom exact, avec le type « recipe » et l'unité « portion »."
)


def _listing(label: str, values: list[str]) -> str:
    return f"{label} : {', '.join(values)}.\n" if values else ""


def meal_plan_prompt(
    *,
    day: str,
    targets: dict,
    meal_names: list[str],
    allergies: list[str],
    liked: list[str],
    disliked: list[str],
    recipes: list[str],
    frequent: list[str],
    already_planned: list[str],
    feedback: str | None = None,
) -> str:
    """Compose la demande d'une journée.

    Une journée à la fois : mesuré contre l'API, une semaine entière dépasse
    16 000 jetons de réponse et revient tronquée, quand une journée en tient
    1 100. Découper rend aussi chaque correction locale — un jour hors
    tolérance se rejoue seul.
    """
    cible = (
        f"Objectifs de la journée : {targets['daily_calories']} kcal, "
        f"{targets['protein_g']} g de protéines, {targets['carbs_g']} g de glucides, "
        f"{targets['fat_g']} g de lipides.\n"
    )

    parties = [
        f"Compose la journée du {day}.\n",
        cible,
        f"Repas à remplir, exactement ceux-ci : {', '.join(meal_names)}.\n",
        _listing("Allergies, à ne jamais employer", allergies),
        _listing("Aliments détestés, à éviter", disliked),
        _listing("Aliments aimés, à privilégier", liked),
        _listing("Recettes déjà enregistrées, utilisables par leur nom exact", recipes),
        _listing("Aliments fréquemment consommés", frequent),
        # Sans cette liste, chaque journée étant composée seule, la semaine
        # répéterait le même déjeuner sept fois.
        _listing("Déjà prévu les jours précédents, à varier", already_planned),
    ]

    if feedback:
        parties.append(f"\n{feedback}\n")

    return "".join(parties)


def deviation_feedback(
    deviations: dict[str, float], targets: dict, measured: list[tuple[str, str, str]] | None = None
) -> str:
    """Dit au modèle de combien sa proposition précédente s'écartait.

    Les écarts sont ceux mesurés **sur les fiches de la base**, après
    résolution : lui renvoyer ses propres estimations ne corrigerait rien.

    `measured` lui donne en plus ce que ses quantités valaient réellement. Sans
    cela il corrige à l'aveugle — il ignore ce que pèse « 80 g de flocons »
    dans ce référentiel-ci, et une correction au jugé retombe à côté. Lui
    fournir ces valeurs ne le fait pas devenir source de vérité : elles
    viennent de la base, et c'est toujours la base qui tranchera.
    """
    lignes = [
        f"- {nom} : {ecart:+.0f} % par rapport à la cible" for nom, ecart in deviations.items()
    ]

    parties = [
        "Ta proposition précédente, une fois ses aliments retrouvés dans la base, "
        "s'écartait des objectifs :\n",
        "\n".join(lignes),
    ]

    if measured:
        parties.append(
            "\n\nVoici ce que valaient réellement tes quantités, d'après la base "
            "(calories, puis protéines / glucides / lipides en grammes) :\n"
            + "\n".join(
                f"- {libelle} {quantite} : {energie} kcal"
                for libelle, quantite, energie in measured
            )
        )

    parties.append(
        "\n\nCorrige les quantités et, si besoin, remplace des aliments. "
        f"Rappel des cibles : {targets['daily_calories']} kcal, "
        f"{targets['protein_g']} g de protéines, {targets['carbs_g']} g de glucides, "
        f"{targets['fat_g']} g de lipides."
    )

    return "".join(parties)

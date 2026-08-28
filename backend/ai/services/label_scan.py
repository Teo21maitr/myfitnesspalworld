"""Lecture d'étiquette : de la photo au brouillon d'aliment (spec 01 §11).

Ce module tient la règle qui gouverne l'étape :

> **Non lu n'est pas zéro.**

Un reflet sur la ligne des fibres, un nutriment que le produit ne déclare pas,
une étiquette photographiée de biais : chacun doit ressortir `null`. Un zéro
enregistré affirme que le produit n'en contient pas — et ce mensonge-là serait
recopié dans chaque snapshot de journal qui suivra (spec 01 §8).

Second garde-fou, la **base de déclaration**. Les étiquettes européennes
portent obligatoirement une colonne « pour 100 g » ou « pour 100 ml », mais
beaucoup en ajoutent une « par portion ». Recopier la mauvaise fausse tout d'un
facteur trois sans que rien ne le signale. Quand le modèle n'a pas trouvé de
colonne pour 100, on ne rend aucune valeur.

Rien n'est enregistré ici : le brouillon préremplit le formulaire, et c'est
l'utilisateur qui crée l'aliment (CLAUDE.md §2).
"""

import re

from ai.schemas import LABEL_NUTRIENTS

#: Un code-barres de produit alimentaire : des chiffres, 8 à 24 positions.
#: Un code mal lu vaut moins qu'un code absent — il ferait créer un doublon
#: sous une identité fausse.
BARCODE_PATTERN = re.compile(r"^\d{8,24}$")

#: Unité de référence déduite de la colonne lue.
REFERENCE_UNIT = {"100g": "g", "100ml": "ml"}

REFERENCE_AMOUNT = "100"


def _clean_barcode(raw: str | None) -> str:
    """Ne garde qu'un code plausible, et rien sinon."""
    digits = re.sub(r"\D", "", raw or "")
    return digits if BARCODE_PATTERN.match(digits) else ""


def build_draft(result: dict) -> dict:
    """Transforme une lecture validée en brouillon prêt à préremplir le formulaire."""
    basis = result["basis"]
    reference_unit = REFERENCE_UNIT.get(basis)

    # Sans colonne pour 100, aucune valeur n'est reprise : l'identité du produit
    # reste utile, ses chiffres non.
    values = result["nutrition"] if reference_unit else {}

    nutrition: dict[str, str | None] = {}
    unreadable: list[str] = []

    for name in LABEL_NUTRIENTS:
        value = values.get(name)
        if value is None:
            nutrition[name] = None
            unreadable.append(name)
        else:
            # Chaîne plutôt que Decimal, comme partout ailleurs dans l'API : ce
            # brouillon est stocké en JSON dans la tâche.
            nutrition[name] = str(value)

    return {
        "basis": basis,
        "draft": {
            "name": result["name"],
            "brand": (result.get("brand") or "").strip(),
            "barcode": _clean_barcode(result.get("barcode")),
            "reference_amount": REFERENCE_AMOUNT,
            "reference_unit": reference_unit or "g",
            "nutrition": nutrition,
        },
        # Nommé plutôt que déduit d'un champ nul : l'interface peut dire « la
        # photo n'a pas donné les fibres » au lieu de laisser croire à un zéro.
        "unreadable": unreadable,
    }

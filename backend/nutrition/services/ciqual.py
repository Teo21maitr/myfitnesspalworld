"""Import de la table de composition nutritionnelle Ciqual (spec 11 §2).

Attribution à conserver dans l'application et la documentation :

    Anses. <millésime>. Table de composition nutritionnelle des aliments Ciqual

Les données sont réutilisables selon les conditions de la Licence Ouverte, à
condition d'indiquer la source **et la version**. Le millésime est donc lu dans
le jeu lui-même plutôt que figé ici : l'Anses en publie un nouveau
régulièrement, et une constante oubliée ferait afficher une attribution fausse
sans que rien ne le signale — le cas exact rencontré au passage de 2020 à 2025.

Le jeu se compose de quatre fichiers XML encodés en `windows-1252`, dont un de
55 Mo : la lecture se fait en flux, jamais en mémoire.
"""

import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree.ElementTree import Element

# `defusedxml` protège des attaques par expansion d'entités : le fichier vient
# d'une source externe, même si elle est officielle.
from defusedxml.ElementTree import iterparse

#: Millésime lisible dans le nom des fichiers publiés — `alim_2025_11_03.xml`.
#: L'extrait de test, lui, ne porte que l'année : les deux formes sont admises.
_VERSION_PATTERN = re.compile(r"_(\d{4})(?:_(\d{2})_(\d{2}))?")

#: Employé lorsque le millésime est illisible. Nommer l'ignorance vaut mieux que
#: d'afficher une année inventée : c'est la règle des nutriments inconnus
#: (spec 01 §8) appliquée à l'attribution.
UNKNOWN_VERSION = "millésime inconnu"


def read_version(directory: Path) -> str:
    """Millésime du jeu, lu dans le nom de son fichier d'aliments."""
    match = _VERSION_PATTERN.search(_find_file(directory, "alim_").name)
    if match is None:
        return UNKNOWN_VERSION
    year, month, day = match.groups()
    return f"{year}-{month}-{day}" if month else year


def attribution(version: str) -> str:
    """Mention d'attribution exigée par la Licence Ouverte."""
    year = version.split("-")[0] if version != UNKNOWN_VERSION else "s.d."
    return f"Anses. {year}. Table de composition nutritionnelle des aliments Ciqual"


# Correspondance entre les codes de constituants Ciqual et les champs de
# `FoodNutrition`. Les unités sont celles de la table : elles coïncident avec
# celles du modèle, aucune conversion n'est nécessaire.
NUTRIENT_CODES: dict[str, str] = {
    "328": "energy_kcal",  # Énergie, Règlement UE 1169/2011
    "25000": "protein_g",  # Protéines, N x facteur de Jones
    "31000": "carbohydrates_g",
    "40000": "fat_g",
    "34100": "fiber_g",
    "32000": "sugars_g",
    "10110": "sodium_mg",
    "10004": "salt_g",
    "75100": "cholesterol_mg",
    "10190": "potassium_mg",
    "10200": "calcium_mg",
    "10260": "iron_mg",
    "10120": "magnesium_mg",
    "56500": "vitamin_b6_mg",
    "56600": "vitamin_b12_ug",
    "55100": "vitamin_c_mg",
    "52100": "vitamin_d_ug",
    "53100": "vitamin_e_mg",
    "54101": "vitamin_k_ug",
}

# Ciqual ne publie pas de « vitamine A » : elle se reconstitue à partir du
# rétinol et du bêta-carotène.
RETINOL_CODE = "51200"
BETA_CAROTENE_CODE = "51330"
# Convention européenne : 6 µg de bêta-carotène équivalent à 1 µg de rétinol.
BETA_CAROTENE_TO_RETINOL = Decimal("6")

# Valeurs textuelles signifiant « mesuré, mais négligeable ».
NEGLIGIBLE_VALUES = {"traces", "trace"}
LESS_THAN_PATTERN = re.compile(r"^<\s*[\d,.]+$")


def parse_teneur(raw: str | None) -> Decimal | None:
    """Convertit une teneur Ciqual en `Decimal`, ou `None` si inconnue.

    Quatre formes coexistent dans le fichier :

    - ``-`` : la donnée n'a pas été mesurée. Elle reste **inconnue**, donc
      `None` — jamais zéro (spec 01 §8) ;
    - ``traces`` : mesurée et négligeable, donc `0` ;
    - ``< 0,01`` : mesurée sous un seuil de détection, donc `0` ;
    - ``59,7`` : valeur décimale à la française.
    """
    if raw is None:
        return None

    value = raw.strip()
    if not value or value == "-":
        return None

    lowered = value.lower()
    if lowered in NEGLIGIBLE_VALUES or LESS_THAN_PATTERN.match(value):
        return Decimal("0")

    try:
        return Decimal(value.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        # Une forme inattendue est traitée comme inconnue plutôt que
        # d'interrompre l'import de 3 000 aliments.
        return None


@dataclass
class CiqualFood:
    """Aliment lu dans la table, avant écriture en base."""

    code: str
    name: str
    group_code: str = ""
    nutrients: dict[str, Decimal] = field(default_factory=dict)
    retinol_ug: Decimal | None = None
    beta_carotene_ug: Decimal | None = None

    def vitamin_a_ug(self) -> Decimal | None:
        """Vitamine A en équivalents rétinol.

        Reste inconnue si aucune des deux sources n'est mesurée ; sinon
        l'absence de l'une est traitée comme un apport nul, ce qui est le
        comportement usuel des tables de composition.
        """
        if self.retinol_ug is None and self.beta_carotene_ug is None:
            return None

        retinol = self.retinol_ug or Decimal("0")
        carotene = self.beta_carotene_ug or Decimal("0")
        return retinol + carotene / BETA_CAROTENE_TO_RETINOL


def _text(element: Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _find_file(directory: Path, prefix: str) -> Path:
    matches = sorted(directory.glob(f"{prefix}*.xml"))
    if not matches:
        raise FileNotFoundError(
            f"Aucun fichier « {prefix}*.xml » dans {directory}. "
            "Le jeu Ciqual complet est-il bien extrait à cet endroit ?"
        )
    return matches[0]


# Les fichiers publiés par l'Anses ne sont pas du XML bien formé : le texte
# contient des « < » bruts, dans les noms d'aliments comme
# « Panaché préemballé (<1° alc.) » et surtout dans les milliers de teneurs
# de la forme « < 0,01 ». Ils sont échappés à la volée avant analyse.
STRAY_LESS_THAN = re.compile(rb"<(?![A-Za-z/?!])")
STRAY_AMPERSAND = re.compile(rb"&(?![A-Za-z#][A-Za-z0-9]*;)")


def sanitize_xml_line(line: bytes) -> bytes:
    """Échappe les caractères qui rendent la ligne invalide.

    Une ligne ne coupe jamais une balise dans ces fichiers : le traitement
    ligne par ligne est donc sûr et permet de rester en flux sur les 55 Mo du
    fichier de composition.
    """
    return STRAY_LESS_THAN.sub(rb"&lt;", STRAY_AMPERSAND.sub(rb"&amp;", line))


class SanitizedXMLStream(io.RawIOBase):
    """Flux binaire assainissant le XML ligne par ligne."""

    def __init__(self, path: Path) -> None:
        self._file = path.open("rb")
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, target) -> int:
        while len(self._buffer) < len(target):
            line = self._file.readline()
            if not line:
                break
            self._buffer += sanitize_xml_line(line)

        chunk = self._buffer[: len(target)]
        self._buffer = self._buffer[len(chunk) :]
        target[: len(chunk)] = chunk
        return len(chunk)

    def close(self) -> None:
        self._file.close()
        super().close()


def _iter_records(path: Path, tag: str) -> Iterator[Element]:
    """Parcourt un fichier XML en flux, en libérant chaque élément lu."""
    # Les fichiers déclarent `windows-1252` dans leur prologue : le parseur
    # d'ElementTree le respecte lorsqu'on lui passe un flux binaire.
    with SanitizedXMLStream(path) as stream:
        for _, element in iterparse(stream, events=("end",)):
            if element.tag == tag:
                yield element
                element.clear()


def read_foods(directory: Path) -> dict[str, CiqualFood]:
    """Lit les aliments, puis leur composition."""
    foods: dict[str, CiqualFood] = {}

    for element in _iter_records(_find_file(directory, "alim_2"), "ALIM"):
        code = _text(element, "alim_code")
        name = _text(element, "alim_nom_fr")
        if code and name:
            foods[code] = CiqualFood(
                code=code, name=name, group_code=_text(element, "alim_grp_code")
            )

    for element in _iter_records(_find_file(directory, "compo"), "COMPO"):
        food = foods.get(_text(element, "alim_code"))
        if food is None:
            continue

        const_code = _text(element, "const_code")
        value = parse_teneur(_text(element, "teneur"))
        if value is None:
            continue

        if const_code == RETINOL_CODE:
            food.retinol_ug = value
        elif const_code == BETA_CAROTENE_CODE:
            food.beta_carotene_ug = value
        elif (attribute := NUTRIENT_CODES.get(const_code)) is not None:
            food.nutrients[attribute] = value

    return foods


def extract_archive(archive: Path, destination: Path) -> Path:
    """Décompresse une archive Ciqual et renvoie le dossier obtenu.

    L'Anses publie le jeu XML en **7z**, pas en ZIP. Les deux sont acceptés :
    refuser le format réellement publié obligerait à décompresser à la main
    avec un outil que l'image de production n'embarque pas.
    """
    destination.mkdir(parents=True, exist_ok=True)

    if archive.suffix.lower() == ".7z":
        import py7zr

        with py7zr.SevenZipFile(archive) as sevenzip:
            sevenzip.extractall(destination)
        return destination

    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(destination)
    return destination

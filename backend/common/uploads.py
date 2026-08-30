"""Validation des images reçues, partagée par toute l'application (spec 05 §14).

Quatre vérifications, dont deux comptent plus que les autres.

Le **type MIME** et l'**extension** sont déclarés par le client : ils
n'engagent personne, et ne servent qu'à écarter tôt ce qui n'a manifestement
rien à faire là. Les **premiers octets** du fichier, eux, sont vérifiables sans
dépendance : c'est la seule des quatre qu'un client ne peut pas contredire.

Ces règles vivaient dans le scan de repas. Les photos de progression en ont
besoin aussi, mais elles **persistent** leurs octets alors que le scan les
jette : les écrire deux fois les ferait diverger, et une règle de sécurité qui
diverge est une règle qu'on a perdue.
"""

from django.conf import settings
from rest_framework.exceptions import ValidationError

#: Signatures de fichier des formats acceptés.
SIGNATURES: dict[str, tuple[tuple[int, bytes], ...]] = {
    "image/jpeg": ((0, b"\xff\xd8\xff"),),
    "image/png": ((0, b"\x89PNG\r\n\x1a\n"),),
    # WebP : conteneur RIFF, puis le marqueur de format en huitième octet.
    "image/webp": ((0, b"RIFF"), (8, b"WEBP")),
}

#: Extensions admises pour chaque type. Une extension qui contredit le type
#: déclaré trahit un renommage, et rien de bon ne commence par là.
EXTENSIONS: dict[str, tuple[str, ...]] = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
}

ACCEPTED_LABEL = "Formats acceptés : JPEG, PNG et WebP."


def max_bytes() -> int:
    return settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def matches_signature(data: bytes, media_type: str) -> bool:
    return all(
        data[offset : offset + len(marker)] == marker for offset, marker in SIGNATURES[media_type]
    )


def read_image(upload, *, field: str) -> tuple[str, bytes]:
    """Valide un fichier et rend son type et ses octets.

    `field` nomme le champ du formulaire, pour que l'erreur se pose au bon
    endroit dans la réponse.
    """
    if upload.size > max_bytes():
        raise ValidationError(
            {field: [f"Chaque photo doit peser moins de {settings.MAX_UPLOAD_SIZE_MB} Mo."]}
        )

    media_type = (upload.content_type or "").split(";")[0].strip().lower()
    if media_type not in SIGNATURES:
        raise ValidationError({field: [ACCEPTED_LABEL]})

    name = (upload.name or "").lower()
    if not name.endswith(EXTENSIONS[media_type]):
        raise ValidationError({field: ["L'extension du fichier ne correspond pas à son format."]})

    data = upload.read()
    if not matches_signature(data, media_type):
        raise ValidationError({field: ["Ce fichier n'est pas une image valide."]})

    return media_type, data

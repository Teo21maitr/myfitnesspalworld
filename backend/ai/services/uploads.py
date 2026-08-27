"""Validation des images reçues par Meal Scan (spec 05 §14).

Trois vérifications, dont la troisième compte autant que les deux autres : un
type MIME est déclaré par le client, donc il n'engage personne. Les premiers
octets du fichier, eux, sont vérifiables sans dépendance.
"""

from django.conf import settings
from rest_framework.exceptions import ValidationError

from ai.providers import ImagePart

#: Une assiette photographiée sous trois angles suffit largement.
MAX_IMAGES = 3

#: Signatures de fichier des formats acceptés.
SIGNATURES: dict[str, tuple[tuple[int, bytes], ...]] = {
    "image/jpeg": ((0, b"\xff\xd8\xff"),),
    "image/png": ((0, b"\x89PNG\r\n\x1a\n"),),
    # WebP : conteneur RIFF, puis le marqueur de format en huitième octet.
    "image/webp": ((0, b"RIFF"), (8, b"WEBP")),
}

FIELD = "images"


def _max_bytes() -> int:
    return settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _matches_signature(data: bytes, media_type: str) -> bool:
    return all(
        data[offset : offset + len(marker)] == marker for offset, marker in SIGNATURES[media_type]
    )


def read_uploads(files: list) -> list[ImagePart]:
    """Valide les fichiers reçus et les charge en mémoire.

    Les octets ne sont jamais écrits sur disque : ils passent du corps de la
    requête au cache Redis, puis au fournisseur (spec 07 §5).
    """
    if not files:
        raise ValidationError({FIELD: ["Ajoutez au moins une photo."]})

    if len(files) > MAX_IMAGES:
        raise ValidationError({FIELD: [f"{MAX_IMAGES} photos au maximum."]})

    limit = _max_bytes()
    images = []

    for upload in files:
        if upload.size > limit:
            raise ValidationError(
                {FIELD: [f"Chaque photo doit peser moins de {settings.MAX_UPLOAD_SIZE_MB} Mo."]}
            )

        media_type = (upload.content_type or "").split(";")[0].strip().lower()
        if media_type not in SIGNATURES:
            raise ValidationError({FIELD: ["Formats acceptés : JPEG, PNG et WebP."]})

        data = upload.read()
        if not _matches_signature(data, media_type):
            raise ValidationError({FIELD: ["Ce fichier n'est pas une image valide."]})

        images.append(ImagePart(media_type=media_type, data=data))

    return images

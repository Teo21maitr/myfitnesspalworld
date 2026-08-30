"""Cycle de vie des photos de progression (spec 01 §20, spec 05 §10-§11).

Ce module n'existe que pour une raison : **ce qu'on supprime doit disparaître
du stockage**, et il y a trois façons de l'oublier — une photo, un groupe, un
compte. Les trois passent par ici, pour qu'aucune n'ait sa propre version de la
règle.

L'ordre compte, et il est contre-intuitif. On supprime **les lignes d'abord,
les objets ensuite**, hors de la transaction et seulement après son succès :
supprimer un objet est irréversible, et le faire depuis une transaction qui peut
encore échouer laisserait une ligne pointant vers un fichier disparu. C'est
l'erreur symétrique, tout aussi silencieuse.
"""

import io
import logging
from collections.abc import Iterable

from django.db import transaction

from accounts.models import User
from progress.models import ProgressPhoto, ProgressPhotoGroup
from progress.services import photo_storage

logger = logging.getLogger(__name__)

#: Plus long côté conservé. La photo est gardée durablement : plus généreux que
#: les 1280 px du scan de repas, qui ne sert qu'à une analyse.
MAX_SIDE = 1600

#: Qualité de réencodage. Au-delà, le poids grimpe sans gain visible.
JPEG_QUALITY = 85

#: Tout est réencodé en JPEG : un seul format à servir, et le réencodage est
#: précisément ce qui fait tomber les métadonnées.
STORED_TYPE = "image/jpeg"


def prepare(data: bytes) -> bytes:
    """Redimensionne, réencode, et **retire les métadonnées EXIF**.

    Le client compresse déjà de son côté, mais le frontend n'est jamais la
    source de vérité (CLAUDE.md §2) : un autre client, ou une future API,
    enverrait l'original.

    Le retrait de l'EXIF n'est pas cosmétique. Un cliché de téléphone porte les
    coordonnées GPS du lieu où il a été pris, et une photo de progression est
    prise chez soi. La recopier inscrirait une adresse dans un fichier.
    `frombytes` reconstruit l'image à partir de ses seuls pixels : ni EXIF, ni
    profil colorimétrique, ni commentaire ne traverse.
    """
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as source:
        # Redresse selon l'orientation EXIF **avant** de la jeter, sinon une
        # photo prise à l'horizontale ressortirait couchée.
        upright = ImageOps.exif_transpose(source)
        upright.thumbnail((MAX_SIDE, MAX_SIDE))
        rgb = upright.convert("RGB")

        clean = Image.frombytes("RGB", rgb.size, rgb.tobytes())

    buffer = io.BytesIO()
    clean.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def store_photo(group: ProgressPhotoGroup, *, data: bytes, photo_type: str) -> ProgressPhoto:
    """Traite l'image, la dépose, et enregistre de quoi la retrouver."""
    prepared = prepare(data)
    key = photo_storage.store(prepared, content_type=STORED_TYPE)

    # Ni la clé ni les octets : seulement de quoi diagnostiquer (spec 05 §15).
    logger.info("Photo de progression ajoutée au groupe %s", group.pk)

    return ProgressPhoto.objects.create(
        group=group,
        photo_type=photo_type,
        storage_key=key,
        mime_type=STORED_TYPE,
        size_bytes=len(prepared),
    )


def purge(keys: Iterable[str]) -> None:
    """Retire les objets, après que la base a confirmé.

    Un échec du stockage ne doit pas défaire une suppression déjà acquise : la
    ligne est partie, et la reconstituer serait pire. L'incident est journalisé
    pour qu'un objet orphelin puisse être retrouvé.
    """
    wanted = list(keys)
    if not wanted:
        return

    try:
        photo_storage.delete(wanted)
    except Exception:
        logger.exception("Suppression de %d objet(s) de progression en échec", len(wanted))


def delete_photo(photo: ProgressPhoto) -> None:
    """Une photo, et son objet."""
    key = photo.storage_key

    with transaction.atomic():
        photo.delete()

    purge([key])


def delete_group(group: ProgressPhotoGroup) -> None:
    """Une journée entière, et tous ses objets."""
    keys = list(group.photos.values_list("storage_key", flat=True))

    with transaction.atomic():
        group.delete()

    purge(keys)


def keys_of(user: User) -> list[str]:
    """Toutes les clés d'un compte, **avant** que la cascade ne les efface.

    C'est l'ordre qui compte à la suppression d'un compte : relever d'abord,
    laisser la base tomber, purger ensuite. Purger en premier ferait perdre les
    photos à qui verrait ensuite sa suppression échouer (spec 05 §11).
    """
    return list(
        ProgressPhoto.objects.filter(group__user=user).values_list("storage_key", flat=True)
    )

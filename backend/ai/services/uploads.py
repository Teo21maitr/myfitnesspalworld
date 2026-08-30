"""Images reçues par Meal Scan et la lecture d'étiquette (spec 05 §14).

La validation elle-même vit dans [`common.uploads`](common/uploads.py) : les
photos de progression appliquent les mêmes règles, et deux copies d'un contrôle
de sécurité finissent toujours par diverger. Ne reste ici que ce qui est propre
au scan — le nombre d'images et le nom du champ.
"""

from rest_framework.exceptions import ValidationError

from ai.providers import ImagePart
from common.uploads import read_image

#: Une assiette photographiée sous trois angles suffit largement.
MAX_IMAGES = 3

FIELD = "images"


def read_uploads(files: list) -> list[ImagePart]:
    """Valide les fichiers reçus et les charge en mémoire.

    Les octets ne sont jamais écrits sur disque : ils passent du corps de la
    requête au cache Redis, puis au fournisseur (spec 07 §5).
    """
    if not files:
        raise ValidationError({FIELD: ["Ajoutez au moins une photo."]})

    if len(files) > MAX_IMAGES:
        raise ValidationError({FIELD: [f"{MAX_IMAGES} photos au maximum."]})

    return [
        ImagePart(media_type=media_type, data=data)
        for media_type, data in (read_image(upload, field=FIELD) for upload in files)
    ]

"""Transport temporaire des images vers le worker (spec 07 §5).

Une image ne peut pas voyager par fichier temporaire : en production, l'API et
le worker sont deux conteneurs, donc deux systèmes de fichiers. Elle ne peut
pas non plus voyager dans le broker, dont le sérialiseur est JSON — dix
mégaoctets encodés en base64 en feraient treize dans la file.

Elle est donc déposée dans le cache Redis sous une clé non prédictible, avec
une durée de vie courte, et le worker ne reçoit que la clé.

**Rien ici n'est conservé.** Le worker supprime les images dès qu'il les a
lues, y compris quand l'appel échoue ; la durée de vie est le filet pour le cas
où le worker meurt avant. Aucun octet n'atteint le disque, aucun log, aucune
table (spec 05 §15, spec 07 §5).
"""

import uuid

from django.core.cache import cache

from ai.providers import ImagePart

#: Assez pour absorber une file d'attente, assez court pour qu'un incident ne
#: laisse pas traîner la photo du dîner de quelqu'un.
TTL_SECONDS = 600

KEY_PREFIX = "mealscan"


def _key() -> str:
    """Clé non devinable : rien ne relie deux images d'un même scan."""
    return f"{KEY_PREFIX}:{uuid.uuid4().hex}"


def stash(images: list[ImagePart]) -> list[str]:
    """Dépose les images et renvoie leurs clés."""
    keys = []
    for image in images:
        key = _key()
        cache.set(key, (image.media_type, image.data), timeout=TTL_SECONDS)
        keys.append(key)
    return keys


def read(keys: list[str]) -> list[ImagePart]:
    """Relit les images déposées.

    Une clé expirée est simplement absente : la tâche traitera ce qu'il reste,
    et une liste vide sera refusée plus haut plutôt qu'analysée à vide.
    """
    images = []
    for key in keys:
        stored = cache.get(key)
        if stored is None:
            continue
        media_type, data = stored
        images.append(ImagePart(media_type=media_type, data=data))
    return images


def discard(keys: list[str]) -> None:
    """Supprime les images. À appeler quoi qu'il arrive."""
    cache.delete_many(keys)

"""Budget d'appels partagé par toute l'application.

À distinguer du throttling de DRF, qui compte *par utilisateur* : certaines
sources externes limitent par adresse IP, et le backend n'en présente qu'une
pour l'ensemble des comptes. Sans compteur commun, dix utilisateurs modérés
dépasseraient ensemble un quota qu'aucun d'eux ne dépasse seul (spec 11 §3).

Le compteur vit dans le cache Redis partagé par tous les processus : un
compteur en mémoire serait remis à zéro à chaque worker.
"""

import time

from django.core.cache import cache

#: Fenêtre de comptage, alignée sur les quotas exprimés « par minute ».
WINDOW_SECONDS = 60


def consume_budget(bucket: str, limit: int, window_seconds: int = WINDOW_SECONDS) -> bool:
    """Réserve un appel dans `bucket`. Renvoie `False` si le budget est épuisé.

    Fenêtre fixe plutôt que fenêtre glissante : c'est exactement la façon dont
    les quotas « N par minute » sont annoncés, et cela tient en une clé de
    cache. Le pire cas — deux fenêtres consécutives consommées d'un coup — reste
    sans conséquence ici, la source se contentant de renvoyer un 429 que le
    client sait déjà traiter.
    """
    if limit <= 0:
        return False

    window = int(time.time()) // window_seconds
    key = f"ratelimit:{bucket}:{window}"

    # `add` ne réussit que si la clé n'existe pas encore : c'est ce qui pose la
    # fenêtre et son expiration de façon atomique.
    if cache.add(key, 1, timeout=window_seconds):
        return True

    try:
        used = cache.incr(key)
    except ValueError:
        # La clé a expiré entre le `add` et le `incr` : la fenêtre a tourné.
        cache.add(key, 1, timeout=window_seconds)
        return True

    return used <= limit


def reset_budget(bucket: str, window_seconds: int = WINDOW_SECONDS) -> None:
    """Libère le budget courant. Réservé aux tests et aux commandes d'admin."""
    window = int(time.time()) // window_seconds
    cache.delete(f"ratelimit:{bucket}:{window}")

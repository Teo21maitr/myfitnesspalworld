"""Disponibilité de l'IA (spec 07 §11).

Trois conditions, et il en faut trois :

* `AI_ENABLED` — l'IA est déployée ;
* une clé d'API — elle est configurable ;
* `AppSetting["ai_enabled"]` — un administrateur ne l'a pas coupée.

Les deux premières se changent en redéployant ; seule la troisième est un vrai
interrupteur, d'où son existence en base.
"""

from django.conf import settings

from common.models import AppSetting

#: Le fournisseur simulé n'appelle personne : il n'a pas besoin de clé.
KEYLESS_PROVIDERS = frozenset({"fake"})


def is_configured() -> bool:
    """L'IA est déployée et sait à qui parler."""
    if not settings.AI_ENABLED:
        return False
    if settings.AI_PROVIDER in KEYLESS_PROVIDERS:
        return True
    return bool(settings.ANTHROPIC_API_KEY)


def is_enabled() -> bool:
    """L'IA est configurée et l'administrateur ne l'a pas coupée.

    Le réglage est lu à chaque appel, sans mise en cache : un coupe-circuit
    doit agir à l'instant où on l'actionne.
    """
    return is_configured() and AppSetting.get_bool(AppSetting.AI_ENABLED, default=True)

"""Frontière avec un fournisseur d'IA (spec 07 §2).

Le protocole ne connaît ni aliment, ni calorie, ni repas : il sait envoyer un
prompt et rendre du JSON conforme à un schéma. Les schémas métier et leur
validation vivent au-dessus, dans les services.

C'est ce qui permet d'ajouter `OpenAIProvider` en un fichier, et d'ajouter la
saisie vocale en une méthode de service — jamais en réécrivant le fournisseur.
"""

from dataclasses import dataclass
from typing import Protocol


class AIProviderError(Exception):
    """Base des erreurs de la frontière IA."""


class AIProviderUnavailable(AIProviderError):
    """Le fournisseur n'a pas pu être interrogé.

    Couvre indifféremment l'absence de clé, la panne réseau, le délai dépassé,
    le 429 et la surcharge : côté appelant il n'y a qu'une conduite à tenir,
    le dire clairement et ne rien inventer (spec 07 §11).
    """


class AIResponseUnusable(AIProviderError):
    """Le fournisseur a répondu, mais pas quelque chose d'exploitable.

    Distinct d'une panne : réessayer à l'identique donnerait le même résultat.
    """


@dataclass(frozen=True)
class ImagePart:
    """Image transmise au modèle, en mémoire uniquement.

    Ces octets ne sont jamais écrits sur disque, jamais journalisés et jamais
    persistés (spec 05 §15, spec 07 §5).
    """

    media_type: str
    data: bytes


class AIProvider(Protocol):
    """Ce qu'un fournisseur doit savoir faire."""

    #: Identifiant court, journalisé dans `AITaskLog`.
    name: str

    def structured_completion(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict,
        images: tuple[ImagePart, ...] = (),
        max_tokens: int | None = None,
        effort: str | None = None,
    ) -> dict:
        """Renvoie un objet JSON conforme à `schema`.

        Contraindre la sortie est la responsabilité du fournisseur, qui seul
        connaît le mécanisme natif de son API. La validation *métier* reste au
        dessus : un schéma respecté ne garantit pas une valeur sensée.

        `max_tokens` borne la réponse. Le laisser à `None` prend la valeur par
        défaut du fournisseur — suffisante pour une liste d'aliments, pas pour
        une journée de plan, dont la réponse est plusieurs fois plus longue.
        Une réponse tronquée n'est pas du JSON valide : mieux vaut un budget
        mesuré qu'un échec de parsing inexplicable.

        `effort` règle la profondeur de réflexion. Une tâche dont la structure
        est déjà imposée par le schéma n'en demande pas beaucoup, et la
        réflexion se paie en jetons comme en secondes.

        Lève `AIProviderUnavailable` ou `AIResponseUnusable`, jamais une
        exception de bibliothèque tierce.
        """
        ...

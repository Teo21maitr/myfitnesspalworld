"""Fournisseur Anthropic (spec 07 §2).

Seul module du projet à connaître le SDK. Il ne laisse remonter aucune
exception de bibliothèque : au-dessus, il n'existe que `AIProviderUnavailable`
et `AIResponseUnusable`.

Le modèle n'est jamais codé en dur (spec 07 §3) : il arrive en paramètre,
depuis les variables d'environnement `AI_*_MODEL`.
"""

import base64
import json
import logging

from django.conf import settings

from .base import AIProviderUnavailable, AIResponseUnusable, ImagePart

logger = logging.getLogger(__name__)

#: Budget par défaut, taillé pour une liste d'aliments détectés.
#:
#: Une journée de plan en demande davantage : mesuré à ~1 100 jetons, contre
#: ~200 pour un scan de repas. Une réponse tronquée n'est pas du JSON valide et
#: échoue au parsing sans dire pourquoi — d'où un budget explicite par tâche.
MAX_TOKENS = 2048


class AnthropicProvider:
    """Appelle l'API Messages en sortie structurée."""

    name = "anthropic"

    def __init__(self, api_key: str | None = None, max_tokens: int = MAX_TOKENS) -> None:
        self._api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self._max_tokens = max_tokens

    def _client(self):
        """Instancie le client, en important le SDK au dernier moment.

        L'import tardif garde le socle démarrable sans le paquet installé, et
        évite de charger le SDK dans les processus qui n'appellent jamais l'IA.
        """
        if not self._api_key:
            raise AIProviderUnavailable("Aucune clé d'API n'est configurée.")

        try:
            import anthropic
        except ImportError as error:  # pragma: no cover - dépendance déclarée
            raise AIProviderUnavailable("Le client Anthropic n'est pas installé.") from error

        return anthropic, anthropic.Anthropic(api_key=self._api_key)

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
        sdk, client = self._client()

        if not model:
            raise AIProviderUnavailable("Aucun modèle n'est configuré pour cette tâche.")

        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.media_type,
                    "data": base64.b64encode(image.data).decode("ascii"),
                },
            }
            for image in images
        ]
        content.append({"type": "text", "text": prompt})

        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens or self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
                # Sortie structurée native : le modèle ne peut pas répondre
                # autre chose qu'un objet conforme au schéma.
                output_config={
                    "format": {"type": "json_schema", "schema": schema},
                    **({"effort": effort} if effort else {}),
                },
            )
        except (sdk.AuthenticationError, sdk.PermissionDeniedError) as error:
            # La clé est refusée. Le message d'erreur du fournisseur peut citer
            # la clé : il n'est pas journalisé (spec 05 §15).
            raise AIProviderUnavailable("La clé d'API Anthropic est refusée.") from error
        except (sdk.RateLimitError, sdk.OverloadedError) as error:
            raise AIProviderUnavailable("Le fournisseur d'IA est saturé.") from error
        except (sdk.APIConnectionError, sdk.APITimeoutError) as error:
            raise AIProviderUnavailable("Le fournisseur d'IA est injoignable.") from error
        except sdk.APIStatusError as error:
            _log_status_error(error)
            raise AIProviderUnavailable("Le fournisseur d'IA a refusé la requête.") from error
        except sdk.AnthropicError as error:
            raise AIProviderUnavailable("Appel au fournisseur d'IA impossible.") from error

        return self._read(message)

    @staticmethod
    def _read(message) -> dict:
        """Extrait l'objet JSON de la réponse."""
        # Une réponse coupée par le budget n'est pas du JSON valide, et le dire
        # explicitement évite un « n'a rien renvoyé » incompréhensible : les
        # jetons de réflexion s'imputent sur `max_tokens`, et un prompt riche
        # en consomme davantage.
        if getattr(message, "stop_reason", None) == "max_tokens":
            raise AIResponseUnusable(
                "La réponse du fournisseur d'IA a été coupée avant d'être complète."
            )

        text = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )
        if not text:
            raise AIResponseUnusable("Le fournisseur d'IA n'a rien renvoyé.")

        try:
            payload = json.loads(text)
        except ValueError as error:
            # Le texte reçu n'est pas journalisé : il décrit le repas de
            # quelqu'un.
            raise AIResponseUnusable("Le fournisseur d'IA n'a pas renvoyé de JSON.") from error

        if not isinstance(payload, dict):
            raise AIResponseUnusable("Le fournisseur d'IA n'a pas renvoyé un objet.")
        return payload


#: Seul type d'erreur dont le message est journalisé.
#:
#: `invalid_request_error` décrit la **forme** de la requête — « property
#: `maxItems` is not supported » — soit un défaut de configuration, jamais le
#: contenu de la photo de quelqu'un. Les autres types peuvent citer la charge
#: utile : seuls leur code et leur identifiant de requête sont conservés.
LOGGABLE_ERROR_TYPE = "invalid_request_error"


def _log_status_error(error) -> None:
    """Journalise de quoi diagnostiquer, sans jamais recopier de donnée privée.

    Le message générique rendu à l'utilisateur est juste, mais il ne dit pas
    *pourquoi* : sans cette trace, un schéma devenu invalide se présente comme
    une panne quelconque, et le diagnostic demande de rejouer l'appel à la main.
    """
    body = getattr(error, "body", None)
    detail = body.get("error") if isinstance(body, dict) else None
    kind = detail.get("type") if isinstance(detail, dict) else None
    request_id = getattr(error, "request_id", None)

    if kind == LOGGABLE_ERROR_TYPE and isinstance(detail, dict):
        logger.warning(
            "Requête refusée par le fournisseur d'IA (%s, requête %s) : %s",
            error.status_code,
            request_id or "inconnue",
            detail.get("message"),
        )
        return

    logger.info(
        "Réponse %s du fournisseur d'IA (%s, requête %s)",
        error.status_code,
        kind or "type inconnu",
        request_id or "inconnue",
    )

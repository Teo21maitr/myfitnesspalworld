"""Exceptions des endpoints adossés à une source externe (spec 10 §5).

Elles portent le `default_code` que le gestionnaire d'erreurs du projet
restitue au client, afin que le frontend distingue « produit inconnu » —
qui mène à la création manuelle — d'une véritable panne de la source.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidBarcode(APIException):
    """Code-barres syntaxiquement invalide.

    Rejeté avant tout appel réseau : le quota de la source est trop étroit pour
    le dépenser sur une saisie erronée.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Ce code-barres n’est pas valide."
    default_code = "invalid_barcode"


class ProductNotFound(APIException):
    """Code-barres inconnu de toutes les sources.

    Cas nominal : il conduit à proposer la création manuelle du produit
    (spec 01 §10).
    """

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Ce produit est introuvable. Vous pouvez le créer vous-même."
    default_code = "product_not_found"


class ExternalSourceUnavailable(APIException):
    """La source externe est injoignable, saturée ou désactivée.

    Le reste de l'application continue de fonctionner sur les données locales
    (spec 11 §3).
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "Open Food Facts est momentanément indisponible. "
        "La recherche dans vos aliments et dans Ciqual reste disponible."
    )
    default_code = "external_source_unavailable"

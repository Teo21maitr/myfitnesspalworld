"""Stockage objet des photos de progression (spec 05 §10, spec 09 §17).

Un service dédié plutôt que le stockage global de Django : les photos sont les
seuls fichiers privés du projet, et remplacer `STORAGES["default"]` toucherait
aussi les fichiers statiques que sert whitenoise. La surface reste petite, et
les trois règles vivent au même endroit.

Ces règles sont :

0. **l'URL signée pointe là où le navigateur peut aller** — le backend et le
   stockage peuvent se parler par un réseau privé ; le navigateur, non ;
1. **la clé ne se devine pas** — et ne dit pas à qui elle appartient. Un chemin
   qui contient l'identifiant de son propriétaire le trahit sans même qu'on
   ouvre le fichier ;
2. **l'URL signée est courte** — une fois émise, elle vaut jusqu'à son
   expiration, y compris si la photo est supprimée entre-temps ;
3. **ce qu'on supprime disparaît d'ici**, pas seulement de la base.

Le client est **injectable**. Les tests en passent un en mémoire : les trois
règles sont alors exercées à l'identique, sans seconde implémentation qui
finirait par diverger.
"""

import uuid
from collections.abc import Iterable

from django.conf import settings

#: Préfixe des clés. Sert à ranger, jamais à identifier.
KEY_PREFIX = "progress-photos"


class StorageUnavailable(RuntimeError):
    """Le stockage objet n'est pas configuré.

    Le reste de l'application n'en dépend pas : seule la photo est refusée.
    """


def is_configured() -> bool:
    return bool(settings.S3_BUCKET_NAME and settings.S3_ENDPOINT_URL)


def _client(endpoint: str | None = None):
    """Client S3, construit à la demande.

    Importé et instancié tardivement : le socle démarre sans `boto3` configuré,
    comme il démarre sans fournisseur d'IA.
    """
    if not is_configured():
        raise StorageUnavailable

    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION or None,
        # SigV4 explicitement : sans lui, boto3 retombe sur SigV2 selon le
        # point d'accès, dont la signature est dépréciée et plus faible. Une
        # URL signée est le seul chemin vers une photo : autant qu'elle soit
        # signée correctement.
        config=Config(signature_version="s3v4"),
    )


#: Client courant. Remplacé par les tests, jamais par le code applicatif.
_override = None


def set_client(client) -> None:
    """Impose un client. Réservé aux tests."""
    global _override
    _override = client


def client():
    return _override if _override is not None else _client()


def public_client():
    """Client visant l'adresse que le navigateur peut joindre.

    Un client distinct, et non une substitution de l'hôte après coup : SigV4
    signe l'en-tête `Host`, donc une URL signée pour `minio:9000` puis réécrite
    en `localhost:9002` serait refusée. C'est l'adresse publique qu'il faut
    signer, dès le départ.
    """
    if _override is not None:
        return _override

    return _client(settings.S3_PUBLIC_ENDPOINT_URL)


def new_key() -> str:
    """Clé non devinable, qui ne dit rien de son propriétaire ni de sa date."""
    return f"{KEY_PREFIX}/{uuid.uuid4().hex}"


def store(data: bytes, *, content_type: str) -> str:
    """Dépose les octets et rend leur clé."""
    key = new_key()
    client().put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def signed_url(key: str, *, seconds: int | None = None) -> str:
    """URL de lecture temporaire.

    Le seau étant privé, c'est le seul chemin vers l'objet — et il se referme
    tout seul. Elle est signée pour l'adresse **publique** : c'est le navigateur
    qui l'ouvrira, et il ne connaît pas le réseau privé du backend.
    """
    return public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
        ExpiresIn=seconds or settings.PROGRESS_PHOTO_URL_TTL,
    )


def delete(keys: Iterable[str]) -> None:
    """Supprime des objets. Appelée quoi qu'il arrive, jamais à moitié.

    Une clé absente n'est pas une erreur : le but est qu'elle ne soit plus là.
    """
    wanted = [key for key in keys if key]
    if not wanted:
        return

    bucket = settings.S3_BUCKET_NAME
    target = client()

    # `delete_objects` traite mille clés par appel ; au-delà, on découpe.
    for start in range(0, len(wanted), 1000):
        target.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": key} for key in wanted[start : start + 1000]]},
        )

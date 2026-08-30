"""Réglages de production (spec 05 §13, spec 09 §8)."""

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import AI_PROVIDER, CELERY_TASK_ALWAYS_EAGER, env

DEBUG = False

# Obligatoire : aucune valeur par défaut permissive en production.
SECRET_KEY = env.str("DJANGO_SECRET_KEY")

#: Hôte que la plateforme emploie pour sonder la santé du service.
#:
#: Railway n'interroge pas le domaine public : il tape le conteneur directement,
#: avec `Host: healthcheck.railway.app`. Absent d'`ALLOWED_HOSTS`, Django répond
#: 400 **avant toute vue** — et la plateforme, healthcheck échoué, conserve
#: l'ancien conteneur. L'application continue donc de répondre pendant que le
#: déploiement est mort : exactement le comportement plausible que cette étape
#: combat.
#:
#: Ajouté ici plutôt que laissé à la variable, parce qu'un `DJANGO_ALLOWED_HOSTS`
#: réécrit un jour rejouerait la panne, avec pour seul indice un « HTTP 400 » qui
#: ne nomme rien.
#:
#: Sans risque : les liens absolus de l'application viennent de `FRONTEND_URL` et
#: `BACKEND_URL`, jamais de l'en-tête `Host`.
HEALTHCHECK_HOST = "healthcheck.railway.app"

ALLOWED_HOSTS = [*env.list("DJANGO_ALLOWED_HOSTS"), HEALTHCHECK_HOST]

# Allowlist stricte, jamais "*".
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# HTTPS derrière le proxy Railway.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)

#: La sonde de la plateforme arrive par le réseau interne, sans
#: `X-Forwarded-Proto`. La redirection HTTPS lui répondrait 301 vers une adresse
#: qu'elle n'a pas demandée, et le healthcheck échouerait pour une raison qui
#: n'a rien à voir avec la santé du service. Une sonde interne n'a pas à être
#: redirigée ; le reste de l'application, si.
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
# Le préchargement HSTS est un engagement **irréversible en pratique** : la
# liste est embarquée dans les navigateurs, et en sortir prend des mois. Il se
# décide une fois le domaine stabilisé, pas au premier déploiement.
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)

#: `check --deploy` est exécuté en CI avec `--fail-level WARNING` : un
#: avertissement qu'on laisse passer est un avertissement qu'on ne lira plus
#: jamais. Celui-ci est donc tu **explicitement**, avec sa raison ci-dessus,
#: plutôt qu'ignoré en masse.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Si le frontend et l'API sont sur des sous-domaines distincts, SameSite=None
# est nécessaire — ce qui impose Secure=True.
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=True)
AUTH_COOKIE_SAMESITE = env.str("AUTH_COOKIE_SAMESITE", default="None")

#: Le cookie CSRF suit le cookie d'authentification, et n'a pas son propre
#: réglage : les deux voyagent sur la même requête, vers le même domaine.
#:
#: Les laisser diverger produit la pire des pannes — l'authentification passe,
#: l'écriture est refusée. L'utilisateur se connecte, navigue, puis reçoit un
#: « CSRF cookie not set » sur son premier enregistrement. Rien dans ce message
#: ne désigne le `SameSite` d'un cookie, et rien ne se voit en local, où
#: frontend et backend partagent le site `localhost`.
#:
#: C'est arrivé : `up.railway.app` est un suffixe public, donc deux
#: sous-domaines Railway sont deux **sites** pour le navigateur.
CSRF_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE

DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)

# -----------------------------------------------------------------------------
# Refus de démarrage
# -----------------------------------------------------------------------------
# Deux familles de fautes, et la seconde est la plus dangereuse.
#
# Les deux premiers refus couvrent ce qui serait **visiblement** faux. Ceux qui
# suivent couvrent ce qui laisserait l'application marcher de travers : un lien
# de réinitialisation vers `localhost` part et s'affiche comme envoyé, un
# backend email console écrit dans les journaux pendant qu'`EmailLog` annonce
# « SENT ». Aucune de ces fautes ne lève d'exception — c'est pourquoi le
# démarrage doit en lever une.

# Le fournisseur d'IA simulé renvoie des suggestions inventées. En production
# elles seraient servies sans le moindre signe extérieur.
if AI_PROVIDER == "fake":
    raise ImproperlyConfigured("AI_PROVIDER=fake est interdit en production.")

# Même raisonnement : en exécution synchrone, une requête d'analyse tiendrait
# la connexion HTTP pendant tout l'appel au modèle.
if CELERY_TASK_ALWAYS_EAGER:
    raise ImproperlyConfigured("CELERY_TASK_ALWAYS_EAGER est interdit en production.")

#: Réglages sans défaut acceptable : leur valeur de développement est une
#: adresse locale, qui ne mène nulle part depuis un téléphone.
REQUIRED_URLS = ("FRONTEND_URL", "BACKEND_URL", "DEFAULT_FROM_EMAIL")

for name in REQUIRED_URLS:
    if not env.str(name, default=""):
        raise ImproperlyConfigured(
            f"{name} est obligatoire en production : sans elle, les emails "
            f"renverraient vers une adresse locale sans que rien ne le signale."
        )

FRONTEND_URL = env.str("FRONTEND_URL")
BACKEND_URL = env.str("BACKEND_URL")
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL")

#: Backends qui acceptent un email sans jamais le remettre à personne.
#:
#: Les laisser passer serait la pire des configurations : l'envoi réussit,
#: `EmailLog` enregistre « SENT », et le compte reste inaccessible à qui a
#: perdu son mot de passe.
SILENT_EMAIL_BACKENDS = (
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
)

EMAIL_BACKEND = env.str("EMAIL_BACKEND", default="")

if not EMAIL_BACKEND:
    raise ImproperlyConfigured(
        "EMAIL_BACKEND est obligatoire en production : par défaut les emails "
        "partiraient dans la console, et personne ne les recevrait."
    )

if EMAIL_BACKEND in SILENT_EMAIL_BACKENDS:
    raise ImproperlyConfigured(
        f"EMAIL_BACKEND={EMAIL_BACKEND} ne remet aucun email à son destinataire. "
        f"Une réinitialisation de mot de passe y serait perdue en silence."
    )

# Sert les fichiers statiques de l'admin sans serveur web dédié.
MIDDLEWARE = [
    *MIDDLEWARE[:1],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

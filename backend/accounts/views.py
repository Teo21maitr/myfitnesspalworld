"""Vues d'authentification et de gestion de compte.

Les vues restent fines : la logique de session, d'inscription et d'email vit
dans `accounts.services` et `notifications.services` (spec 10 §2).
"""

import contextlib

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.exceptions import AuthenticationError, InvalidResetToken
from accounts.models import User, UserSettings, UserStatus, normalize_username
from accounts.serializers import (
    AccountDeletionSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    MeSerializer,
    ProfileSerializer,
    RegistrationRequestSerializer,
    ResetPasswordSerializer,
    UserSettingsSerializer,
)
from accounts.services.sessions import (
    TOKEN_VERSION_CLAIM,
    build_refresh_token,
    clear_auth_cookies,
    revoke_all_sessions,
    set_auth_cookies,
)
from common.permissions import IsActiveAccount
from notifications.services.email import send_password_reset_email
from progress.services import photos as progress_photos

INVALID_CREDENTIALS_MESSAGE = "Nom d’utilisateur ou mot de passe incorrect."
PENDING_ACCOUNT_MESSAGE = (
    "Votre demande d’inscription n’a pas encore été acceptée par un administrateur."
)
SUSPENDED_ACCOUNT_MESSAGE = "Votre compte est suspendu. Contactez l’administrateur."

# Réponse volontairement identique que le compte existe ou non, et qu'il ait
# une adresse email ou non : un anonyme ne doit pas pouvoir déduire
# l'existence d'un compte (spec 05 §12).
RESET_REQUEST_ACK_MESSAGE = (
    "Si un compte correspond à ce nom d’utilisateur et qu’une adresse email y est "
    "associée, un lien de réinitialisation vient d’être envoyé. Sinon, contactez "
    "l’administrateur."
)


class AuthThrottleMixin:
    """Limite les endpoints sensibles d'authentification (spec 05 §12)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class RegistrationRequestView(AuthThrottleMixin, APIView):
    """`POST /auth/register-request/` — dépose une demande de compte."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegistrationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "detail": (
                    "Votre demande d’inscription a bien été envoyée. Un administrateur "
                    "doit maintenant l’accepter avant que vous puissiez vous connecter."
                )
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(AuthThrottleMixin, APIView):
    """`POST /auth/login/` — pose les cookies d'authentification."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self._authenticate(
            serializer.validated_data["username"],
            serializer.validated_data["password"],
        )

        refresh = build_refresh_token(user)
        response = Response(MeSerializer(user).data, status=status.HTTP_200_OK)
        return set_auth_cookies(response, refresh)

    def _authenticate(self, username: str, password: str) -> User:
        """Vérifie les identifiants sans permettre l'énumération des comptes.

        Un compte inexistant et un mauvais mot de passe renvoient le même
        message. En revanche, une fois le mot de passe correct fourni, le
        demandeur a prouvé qu'il détient le compte : lui indiquer que celui-ci
        est en attente ou suspendu ne divulgue plus rien.
        """
        try:
            user = User.objects.get(normalized_username=normalize_username(username))
        except User.DoesNotExist as exc:
            # Hachage factice pour que la durée de réponse ne trahisse pas
            # l'absence de compte.
            check_password(password, User().password)
            raise AuthenticationError(
                INVALID_CREDENTIALS_MESSAGE, code="invalid_credentials"
            ) from exc

        if not user.check_password(password):
            raise AuthenticationError(INVALID_CREDENTIALS_MESSAGE, code="invalid_credentials")

        if user.status == UserStatus.PENDING:
            raise AuthenticationError(PENDING_ACCOUNT_MESSAGE, code="account_pending")
        if user.status == UserStatus.SUSPENDED:
            raise AuthenticationError(SUSPENDED_ACCOUNT_MESSAGE, code="account_suspended")

        return user


class RefreshView(AuthThrottleMixin, APIView):
    """`POST /auth/refresh/` — renouvelle l'access token depuis le cookie."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    # Quota distinct de celui de la connexion : l'application le déclenche
    # elle-même à chaque chargement de page.
    throttle_scope = "refresh"

    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        if not raw_refresh:
            raise AuthenticationError("Session absente.", code="no_refresh_cookie")

        try:
            refresh = RefreshToken(raw_refresh)
        except TokenError as exc:
            raise AuthenticationError("Session expirée.", code="invalid_refresh") from exc

        try:
            user = User.objects.get(pk=refresh["user_id"])
        except User.DoesNotExist as exc:
            raise AuthenticationError("Session invalide.", code="invalid_refresh") from exc

        if not user.is_active:
            raise AuthenticationError("Compte inactif.", code="account_inactive")

        if refresh.get(TOKEN_VERSION_CLAIM) != user.token_version:
            raise AuthenticationError("Session révoquée.", code="session_revoked")

        # La rotation est activée : l'ancien refresh est mis en liste noire et
        # un nouveau couple de tokens est émis.
        refresh.blacklist()
        new_refresh = build_refresh_token(user)

        response = Response(MeSerializer(user).data, status=status.HTTP_200_OK)
        return set_auth_cookies(response, new_refresh)


class LogoutView(APIView):
    """`POST /auth/logout/` — déconnecte l'appareil courant."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        # Un refresh déjà expiré ou révoqué n'empêche pas la déconnexion :
        # les cookies sont effacés dans tous les cas.
        if raw_refresh:
            with contextlib.suppress(TokenError):
                RefreshToken(raw_refresh).blacklist()

        response = Response(status=status.HTTP_204_NO_CONTENT)
        return clear_auth_cookies(response)


class LogoutAllView(APIView):
    """`POST /auth/logout-all/` — révoque toutes les sessions du compte."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        revoke_all_sessions(request.user)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        return clear_auth_cookies(response)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """`GET /auth/me/` — profil courant, et sème le cookie CSRF."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """`GET /auth/csrf/` — pose le cookie CSRF et **rend le jeton**.

    Le cookie ne suffit pas quand le frontend vit sur un autre domaine que
    l'API : `document.cookie` ne donne accès qu'aux cookies du domaine
    courant. Le navigateur envoie bien celui de l'API à chaque requête, mais le
    JavaScript ne peut pas le lire pour le recopier dans l'en-tête
    `X-CSRFToken` — d'où un « CSRF token missing » que rien ne laisse prévoir
    en local, où frontend et API partagent l'hôte `localhost`.

    Le jeton voyage donc aussi dans le corps de la réponse. Ce n'est pas un
    secret à protéger du client : c'est précisément **lui** qui doit le
    renvoyer. Ce qu'il protège, c'est qu'un autre site ne puisse pas
    l'obtenir — ce que la politique d'origine croisée garantit, cette réponse
    n'étant lisible que depuis les origines autorisées par CORS.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request)})


class ForgotPasswordView(AuthThrottleMixin, APIView):
    """`POST /auth/forgot-password/` — envoie un lien de réinitialisation."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        user = User.objects.filter(
            normalized_username=normalize_username(username),
            status=UserStatus.ACTIVE,
        ).first()

        if user and user.email:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = (
                f"{settings.FRONTEND_URL}/reinitialiser-mot-de-passe?uid={uid}&token={token}"
            )
            send_password_reset_email(user, reset_url)

        # Réponse identique dans tous les cas.
        return Response({"detail": RESET_REQUEST_ACK_MESSAGE})


class ResetPasswordView(AuthThrottleMixin, APIView):
    """`POST /auth/reset-password/` — applique un nouveau mot de passe."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = self._user_from_uid(data["uid"])
        if user is None or not default_token_generator.check_token(user, data["token"]):
            raise InvalidResetToken

        serializer.validate_password_pair(
            data,
            field="new_password",
            confirmation_field="new_password_confirmation",
            user=user,
        )

        user.set_password(data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        # Le changement de mot de passe invalide toutes les sessions
        # existantes ; le token de reset devient lui aussi inutilisable
        # puisqu'il dérive du hash du mot de passe.
        revoke_all_sessions(user)

        return Response({"detail": "Votre mot de passe a été modifié. Vous pouvez vous connecter."})

    @staticmethod
    def _user_from_uid(uid: str) -> User | None:
        try:
            pk = force_str(urlsafe_base64_decode(uid))
            return User.objects.get(pk=pk)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None


class ProfileView(APIView):
    """`GET|PATCH /profile/` — identité de l'utilisateur courant."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get(self, request: Request) -> Response:
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request: Request) -> Response:
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserSettingsView(APIView):
    """`GET|PATCH /profile/settings/` — préférences applicatives."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def get_object(self, request: Request) -> UserSettings:
        settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)
        return settings_obj

    def get(self, request: Request) -> Response:
        return Response(UserSettingsSerializer(self.get_object(request)).data)

    def patch(self, request: Request) -> Response:
        serializer = UserSettingsSerializer(
            self.get_object(request), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """`POST /account/change-password/`.

    Stratégie retenue : le changement révoque **toutes** les sessions, puis de
    nouveaux cookies sont immédiatement posés pour l'appareil courant.
    L'utilisateur reste donc connecté ici et est déconnecté partout ailleurs —
    la sémantique de `update_session_auth_hash` de Django.
    """

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        revoke_all_sessions(user)

        refresh = build_refresh_token(user)
        response = Response(
            {
                "detail": (
                    "Votre mot de passe a été modifié. Vos autres appareils ont été déconnectés."
                )
            }
        )
        return set_auth_cookies(response, refresh)


class AccountView(APIView):
    """`DELETE /account/` — suppression définitive du compte (spec 05 §11)."""

    permission_classes = [IsAuthenticated, IsActiveAccount]

    def delete(self, request: Request) -> Response:
        serializer = AccountDeletionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user

        # Les clés du stockage objet sont relevées **avant** la cascade :
        # après elle, plus rien ne dit quels fichiers appartenaient à ce
        # compte, et ils survivraient indéfiniment (spec 05 §11).
        photo_keys = progress_photos.keys_of(user)

        with transaction.atomic():
            # Les jetons pointent sur l'utilisateur en SET_NULL : ils sont
            # supprimés explicitement pour ne rien laisser derrière.
            OutstandingToken.objects.filter(user=user).delete()
            user.delete()

        # Hors transaction, et seulement une fois la suppression acquise :
        # retirer un objet est irréversible.
        progress_photos.purge(photo_keys)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        return clear_auth_cookies(response)

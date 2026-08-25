"""Serializers des comptes.

Aucun serializer n'expose `password`, `token_version` ni
`normalized_username` (spec 10 §5).
"""

from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import (
    MINIMUM_AGE,
    RegistrationRequest,
    ThemeMode,
    User,
    UserProfile,
    normalize_username,
)
from accounts.services.registration import username_is_available
from common.dates import age_on

USERNAME_TAKEN_MESSAGE = "Ce nom d’utilisateur est déjà utilisé."


def validate_adult(birth_date: date) -> date:
    """Refuse une date de naissance de moins de 18 ans (spec 01 §2)."""
    today = date.today()
    if birth_date > today:
        raise serializers.ValidationError("La date de naissance ne peut pas être dans le futur.")
    if age_on(birth_date, today) < MINIMUM_AGE:
        raise serializers.ValidationError(
            f"L’application est réservée aux personnes de {MINIMUM_AGE} ans et plus."
        )
    return birth_date


def _run_password_validators(password: str, user: User | None = None) -> None:
    """Applique les validateurs de mot de passe de Django."""
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc


class PasswordPairMixin:
    """Vérifie qu'un mot de passe et sa confirmation correspondent.

    Les noms de champs sont passés en argument plutôt que stockés en
    attributs de classe : chaque serializer nomme ses champs différemment.
    """

    def validate_password_pair(
        self,
        attrs: dict,
        *,
        field: str,
        confirmation_field: str,
        user: User | None = None,
    ) -> dict:
        secret = attrs.get(field)
        confirmation = attrs.get(confirmation_field)

        if secret != confirmation:
            raise serializers.ValidationError(
                {confirmation_field: ["Les deux mots de passe ne correspondent pas."]}
            )

        try:
            _run_password_validators(secret, user)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({field: exc.detail}) from exc

        return attrs


class RegistrationRequestSerializer(PasswordPairMixin, serializers.ModelSerializer):
    """Demande de création de compte (spec 01 §1)."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirmation = serializers.CharField(write_only=True, style={"input_type": "password"})
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = RegistrationRequest
        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
            "password_confirmation",
        )
        extra_kwargs = {
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
        }

    def validate_username(self, value: str) -> str:
        value = value.strip()
        if not username_is_available(value):
            raise serializers.ValidationError(USERNAME_TAKEN_MESSAGE)
        return value

    def validate(self, attrs: dict) -> dict:
        # Utilisateur fictif pour que le validateur de similarité dispose du
        # username et du nom sans qu'aucun compte n'existe encore.
        candidate = User(
            username=attrs.get("username", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
            email=attrs.get("email") or None,
        )
        return self.validate_password_pair(
            attrs,
            field="password",
            confirmation_field="password_confirmation",
            user=candidate,
        )

    def create(self, validated_data: dict) -> RegistrationRequest:
        validated_data.pop("password_confirmation")
        password = validated_data.pop("password")

        registration_request = RegistrationRequest(
            **{**validated_data, "email": validated_data.get("email") or None}
        )
        registration_request.set_password(password)
        registration_request.normalized_username = normalize_username(registration_request.username)
        registration_request.full_clean(exclude=["password"])
        registration_request.save()
        return registration_request


class LoginSerializer(serializers.Serializer):
    """Identifiants de connexion."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class MeSerializer(serializers.ModelSerializer):
    """Informations strictement nécessaires au frontend (spec 04 §1)."""

    onboarding_completed = serializers.BooleanField(
        source="profile.onboarding_completed", read_only=True
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "status",
            "is_staff",
            "onboarding_completed",
        )
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """Données de profil renseignées par l'onboarding (spec 03 §1)."""

    class Meta:
        model = UserProfile
        fields = (
            "birth_date",
            "sex_for_calculation",
            "height_cm",
            "activity_level",
            "goal_type",
            "goal_rate_kg_per_week",
            "target_weight_kg",
            "onboarding_completed",
        )
        # `onboarding_completed` ne bascule que par l'endpoint d'onboarding.
        read_only_fields = ("onboarding_completed",)

    def validate_birth_date(self, value: date) -> date:
        return validate_adult(value)


class ProfileSerializer(serializers.ModelSerializer):
    """Profil modifiable par l'utilisateur : identité et données personnelles."""

    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    onboarding_completed = serializers.BooleanField(
        source="profile.onboarding_completed", read_only=True
    )
    profile = UserProfileSerializer()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "status",
            "is_staff",
            "onboarding_completed",
            "profile",
            "created_at",
        )
        read_only_fields = ("id", "status", "is_staff", "onboarding_completed", "created_at")

    def validate_username(self, value: str) -> str:
        value = value.strip()
        # Le username reste modifiable tant qu'il conserve son unicité
        # insensible à la casse (spec 01 §1).
        if normalize_username(value) == self.instance.normalized_username:
            return value
        if not username_is_available(value):
            raise serializers.ValidationError(USERNAME_TAKEN_MESSAGE)
        return value

    def update(self, instance: User, validated_data: dict) -> User:
        profile_data = validated_data.pop("profile", None)
        if profile_data:
            profile = instance.profile
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.full_clean()
            profile.save()

        if "email" in validated_data:
            validated_data["email"] = validated_data["email"] or None

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.full_clean(exclude=["password"])
        instance.save()
        return instance


class UserSettingsSerializer(serializers.ModelSerializer):
    """Préférences applicatives (spec 03 §1)."""

    theme_mode = serializers.ChoiceField(choices=ThemeMode.choices)

    class Meta:
        from accounts.models import UserSettings

        model = UserSettings
        fields = ("language", "theme_mode", "date_format")
        # L'application est en français uniquement (spec 00 §8).
        read_only_fields = ("language",)


class ChangePasswordSerializer(PasswordPairMixin, serializers.Serializer):
    """Changement de mot de passe par un utilisateur authentifié."""

    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirmation = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Le mot de passe actuel est incorrect.")
        return value

    def validate(self, attrs: dict) -> dict:
        return self.validate_password_pair(
            attrs,
            field="new_password",
            confirmation_field="new_password_confirmation",
            user=self.context["request"].user,
        )


class ForgotPasswordSerializer(serializers.Serializer):
    """Demande de réinitialisation."""

    username = serializers.CharField()


class ResetPasswordSerializer(PasswordPairMixin, serializers.Serializer):
    """Application d'une réinitialisation à partir du lien reçu par email.

    La paire de mots de passe est validée par la vue, qui seule connaît
    l'utilisateur ciblé par le token.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirmation = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )


class AccountDeletionSerializer(serializers.Serializer):
    """Confirmation de suppression définitive du compte (spec 04 §20)."""

    username_confirmation = serializers.CharField()

    def validate_username_confirmation(self, value: str) -> str:
        # Comparaison exacte, sensible à la casse : la confirmation doit être
        # une action délibérée.
        if value != self.context["request"].user.username:
            raise serializers.ValidationError(
                "La confirmation ne correspond pas à votre nom d’utilisateur."
            )
        return value

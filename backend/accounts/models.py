"""Modèle utilisateur personnalisé (spec 03 §1, spec 05 §2).

Le username est unique de manière insensible à la casse et reste modifiable.
L'email est facultatif et ne sert jamais à la recherche sociale.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# L'application est réservée aux adultes (spec 01 §2).
MINIMUM_AGE = 18


class UserStatus(models.TextChoices):
    """États de compte.

    `REJECTED` n'existe pas : une demande refusée est supprimée et aucun
    utilisateur n'est créé (spec 05 §2).
    """

    PENDING = "PENDING", "En attente"
    ACTIVE = "ACTIVE", "Actif"
    SUSPENDED = "SUSPENDED", "Suspendu"


def normalize_username(username: str) -> str:
    """Forme canonique servant à garantir l'unicité insensible à la casse."""
    return username.strip().casefold()


class UserManager(BaseUserManager):
    """Manager du modèle utilisateur personnalisé."""

    use_in_migrations = True

    def _create_user(self, username: str, password: str | None, **extra_fields):
        if not username:
            raise ValueError("Le nom d’utilisateur est obligatoire.")

        email = extra_fields.pop("email", None)
        email = self.normalize_email(email) if email else None

        user = self.model(username=username.strip(), email=email, **extra_fields)
        # Renseigné avant la validation pour que l'unicité insensible à la
        # casse remonte comme une ValidationError et non comme une
        # IntegrityError.
        user.normalized_username = normalize_username(user.username)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, username: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("status", UserStatus.PENDING)
        return self._create_user(username, password, **extra_fields)

    def create_superuser(self, username: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", UserStatus.ACTIVE)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superutilisateur doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superutilisateur doit avoir is_superuser=True.")
        if extra_fields.get("status") != UserStatus.ACTIVE:
            raise ValueError("Un superutilisateur doit être ACTIVE.")

        return self._create_user(username, password, **extra_fields)

    def get_by_natural_key(self, username: str | None):
        """Permet la connexion sans tenir compte de la casse."""
        return self.get(normalized_username=normalize_username(username or ""))


username_validator = RegexValidator(
    regex=r"^[\w.@+-]+$",
    message=(
        "Le nom d’utilisateur ne peut contenir que des lettres, chiffres et "
        "les caractères . @ + - _"
    ),
)


class User(AbstractBaseUser, PermissionsMixin):
    """Utilisateur de l'application."""

    username = models.CharField(
        "nom d'utilisateur",
        max_length=30,
        unique=True,
        validators=[username_validator],
        help_text="Sert à la connexion et à la recherche sociale.",
    )
    normalized_username = models.CharField(
        "nom d'utilisateur normalisé",
        max_length=30,
        unique=True,
        editable=False,
        help_text="Forme minuscule garantissant l'unicité insensible à la casse.",
    )
    # `null=True` est volontaire malgré la convention Django de la chaîne vide
    # (DJ001) : la spec 03 §1 décrit l'email comme nullable, et NULL distingue
    # « pas d'email » d'une chaîne vide tout en restant compatible avec une
    # future contrainte d'unicité partielle.
    email = models.EmailField(  # noqa: DJ001
        "adresse email",
        null=True,
        blank=True,
        help_text="Facultatif. Jamais utilisé pour la recherche sociale.",
    )
    first_name = models.CharField("prénom", max_length=100, blank=True)
    last_name = models.CharField("nom", max_length=100, blank=True)
    status = models.CharField(
        "statut",
        max_length=16,
        choices=UserStatus.choices,
        default=UserStatus.PENDING,
        db_index=True,
    )
    is_staff = models.BooleanField(
        "membre de l'équipe",
        default=False,
        help_text="Autorise l'accès à l'administration Django.",
    )
    token_version = models.PositiveIntegerField(
        "version de session",
        default=1,
        editable=False,
        help_text=(
            "Incrémentée pour révoquer immédiatement tous les tokens émis "
            "précédemment (déconnexion globale, changement de mot de passe, "
            "suspension)."
        ),
    )
    created_at = models.DateTimeField("créé le", default=timezone.now, editable=False)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["username"]

    def __str__(self) -> str:
        return self.username

    def save(self, *args, **kwargs):
        self.normalized_username = normalize_username(self.username)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.normalized_username = normalize_username(self.username)

    @property
    def is_active(self) -> bool:
        """Seul un compte ACTIVE peut s'authentifier (spec 05 §2).

        Django s'appuie sur cet attribut dans `ModelBackend` et dans l'admin :
        un compte PENDING ou SUSPENDED est donc rejeté à la connexion sans
        code supplémentaire.
        """
        return self.status == UserStatus.ACTIVE

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.first_name or self.username


class RegistrationRequest(models.Model):
    """Demande de création de compte en attente de validation (spec 01 §1).

    Le mot de passe est stocké **haché** dès la demande, puis transféré tel
    quel au `User` lors de l'acceptation : l'utilisateur conserve ainsi le mot
    de passe qu'il a choisi, sans qu'il ait jamais transité ni été stocké en
    clair.

    Aucun champ de statut n'est nécessaire : accepter ou refuser supprime la
    demande, ce qui autorise naturellement une nouvelle demande ultérieure.
    """

    first_name = models.CharField("prénom", max_length=100)
    last_name = models.CharField("nom", max_length=100)
    username = models.CharField(
        "nom d'utilisateur",
        max_length=30,
        unique=True,
        validators=[username_validator],
    )
    normalized_username = models.CharField(
        "nom d'utilisateur normalisé",
        max_length=30,
        unique=True,
        editable=False,
    )
    email = models.EmailField(  # noqa: DJ001 - facultatif, cf. User.email
        "adresse email",
        null=True,
        blank=True,
    )
    password = models.CharField(
        "mot de passe haché",
        max_length=128,
        editable=False,
    )
    created_at = models.DateTimeField("demandé le", default=timezone.now, editable=False)

    class Meta:
        verbose_name = "demande d'inscription"
        verbose_name_plural = "demandes d'inscription"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.username

    def save(self, *args, **kwargs):
        self.normalized_username = normalize_username(self.username)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        self.normalized_username = normalize_username(self.username)

    def set_password(self, raw_password: str) -> None:
        """Hache le mot de passe fourni. Jamais de stockage en clair."""
        self.password = make_password(raw_password)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.username


class SexForCalculation(models.TextChoices):
    """Sexe utilisé par la formule métabolique (spec 01 §2)."""

    FEMALE = "FEMALE", "Femme"
    MALE = "MALE", "Homme"


class ActivityLevel(models.TextChoices):
    """Niveau d'activité servant au calcul initial (spec 01 §2)."""

    SEDENTARY = "SEDENTARY", "Sédentaire"
    LIGHTLY_ACTIVE = "LIGHTLY_ACTIVE", "Légèrement actif"
    MODERATELY_ACTIVE = "MODERATELY_ACTIVE", "Modérément actif"
    VERY_ACTIVE = "VERY_ACTIVE", "Très actif"
    EXTREMELY_ACTIVE = "EXTREMELY_ACTIVE", "Extrêmement actif"


class GoalType(models.TextChoices):
    """Objectif de poids (spec 01 §2)."""

    LOSS = "LOSS", "Perte"
    MAINTENANCE = "MAINTENANCE", "Maintien"
    GAIN = "GAIN", "Prise"


class UserProfile(models.Model):
    """Profil de l'utilisateur (spec 03 §1).

    Les champs nutritionnels existent dès maintenant pour que le modèle soit
    complet, mais ils restent nuls et ne sont pas exposés par l'API : ils
    seront renseignés par l'onboarding.
    """

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="utilisateur",
    )
    birth_date = models.DateField("date de naissance", null=True, blank=True)
    sex_for_calculation = models.CharField(  # noqa: DJ001 - nul tant que non renseigné
        "sexe utilisé pour le calcul",
        max_length=16,
        choices=SexForCalculation.choices,
        null=True,
        blank=True,
    )
    height_cm = models.DecimalField(
        "taille (cm)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    activity_level = models.CharField(  # noqa: DJ001 - nul tant que non renseigné
        "niveau d'activité",
        max_length=24,
        choices=ActivityLevel.choices,
        null=True,
        blank=True,
    )
    goal_type = models.CharField(  # noqa: DJ001 - nul tant que non renseigné
        "objectif",
        max_length=16,
        choices=GoalType.choices,
        null=True,
        blank=True,
    )
    goal_rate_kg_per_week = models.DecimalField(
        "rythme (kg/semaine)", max_digits=4, decimal_places=2, null=True, blank=True
    )
    target_weight_kg = models.DecimalField(
        "poids cible (kg)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    onboarding_completed = models.BooleanField("onboarding terminé", default=False)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "profil"
        verbose_name_plural = "profils"

    def __str__(self) -> str:
        return f"Profil de {self.user.username}"


class ThemeMode(models.TextChoices):
    """Thème de l'interface (spec 06 §8)."""

    LIGHT = "light", "Clair"
    DARK = "dark", "Sombre"
    SYSTEM = "system", "Système"


class UserSettings(models.Model):
    """Préférences applicatives de l'utilisateur (spec 03 §1)."""

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="settings",
        verbose_name="utilisateur",
    )
    # L'application est en français uniquement (spec 00 §8).
    language = models.CharField("langue", max_length=5, default="fr")
    theme_mode = models.CharField(
        "thème",
        max_length=8,
        choices=ThemeMode.choices,
        default=ThemeMode.SYSTEM,
    )
    date_format = models.CharField("format de date", max_length=20, default="DD/MM/YYYY")
    # Renseignés par les étapes ultérieures (dashboard, confidentialité).
    dashboard_config = models.JSONField("configuration du dashboard", default=dict, blank=True)
    privacy_config = models.JSONField("configuration de confidentialité", default=dict, blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "paramètres"
        verbose_name_plural = "paramètres"

    def __str__(self) -> str:
        return f"Paramètres de {self.user.username}"

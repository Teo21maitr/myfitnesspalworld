"""Administration des comptes.

L'administrateur peut accepter ou refuser une demande, suspendre ou
réactiver un compte, et forcer une réinitialisation de mot de passe. Il ne
peut jamais lire le mot de passe courant (spec 05 §4).
"""

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.services.registration import (
    accept_registration_request,
    reject_registration_request,
)
from accounts.services.sessions import revoke_all_sessions
from notifications.services.email import send_password_reset_email

from .models import RegistrationRequest, User, UserProfile, UserSettings, UserStatus


class MfpUserCreationForm(AdminUserCreationForm):
    """Formulaire de création côté admin.

    `AdminUserCreationForm` (et non `UserCreationForm`) est nécessaire pour
    disposer du champ `usable_password`, qui permet de créer un compte sans
    mot de passe utilisable.
    """

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "status")


class MfpUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profil"
    extra = 0


class UserSettingsInline(admin.StackedInline):
    model = UserSettings
    can_delete = False
    verbose_name_plural = "Paramètres"
    extra = 0


@admin.register(RegistrationRequest)
class RegistrationRequestAdmin(admin.ModelAdmin):
    """Demandes d'inscription en attente de validation (spec 01 §1)."""

    list_display = ("username", "full_name", "email", "created_at")
    search_fields = ("username", "normalized_username", "email", "first_name", "last_name")
    ordering = ("created_at",)
    # Le hash du mot de passe n'est jamais affiché ni modifiable.
    readonly_fields = ("normalized_username", "created_at")
    fields = ("username", "normalized_username", "first_name", "last_name", "email", "created_at")

    @admin.display(description="Nom complet")
    def full_name(self, obj: RegistrationRequest) -> str:
        return obj.full_name

    @admin.action(description="Accepter les demandes sélectionnées")
    def accept_requests(self, request, queryset) -> None:
        accepted, failed = 0, 0

        for registration_request in queryset:
            try:
                accept_registration_request(registration_request)
            except ValidationError as exc:
                failed += 1
                self.message_user(request, str(exc.messages[0]), level=messages.ERROR)
            else:
                accepted += 1

        if accepted:
            self.message_user(
                request,
                f"{accepted} compte(s) créé(s) et activé(s).",
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                f"{failed} demande(s) n'ont pas pu être acceptées.",
                level=messages.WARNING,
            )

    @admin.action(description="Refuser les demandes sélectionnées")
    def reject_requests(self, request, queryset) -> None:
        count = 0
        for registration_request in queryset:
            reject_registration_request(registration_request)
            count += 1

        self.message_user(request, f"{count} demande(s) refusée(s) et supprimée(s).")

    actions = ("accept_requests", "reject_requests")

    def has_add_permission(self, request) -> bool:
        # Une demande naît de l'API publique, pas de l'admin.
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = MfpUserChangeForm
    add_form = MfpUserCreationForm
    inlines = (UserProfileInline, UserSettingsInline)

    list_display = ("username", "email", "full_name", "status", "is_staff", "created_at")
    # `is_active` est une propriété dérivée de `status` : c'est `status` qui
    # est filtrable.
    list_filter = ("status", "is_staff", "is_superuser", "groups")
    search_fields = ("username", "normalized_username", "email", "first_name", "last_name")
    ordering = ("username",)
    readonly_fields = ("normalized_username", "created_at", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("username", "normalized_username", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "email")}),
        ("Statut", {"fields": ("status",)}),
        (
            "Permissions",
            {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "status",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def get_inline_instances(self, request, obj=None):
        # Profil et paramètres sont créés par signal juste après le compte :
        # ils n'ont pas d'existence sur la page de création.
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    @admin.display(description="Nom complet")
    def full_name(self, obj: User) -> str:
        return obj.full_name

    @admin.action(description="Activer les comptes sélectionnés")
    def activate_accounts(self, request, queryset) -> None:
        updated = queryset.update(status=UserStatus.ACTIVE)
        self.message_user(request, f"{updated} compte(s) activé(s).")

    @admin.action(description="Suspendre les comptes sélectionnés")
    def suspend_accounts(self, request, queryset) -> None:
        count = 0
        for user in queryset:
            user.status = UserStatus.SUSPENDED
            user.save(update_fields=["status", "updated_at"])
            # La suspension doit couper les sessions en cours, pas seulement
            # empêcher les connexions futures (spec 05 §2).
            revoke_all_sessions(user)
            count += 1

        self.message_user(request, f"{count} compte(s) suspendu(s) et déconnecté(s).")

    @admin.action(description="Forcer la réinitialisation du mot de passe")
    def force_password_reset(self, request, queryset) -> None:
        """Envoie un lien de réinitialisation, ou rend le mot de passe inutilisable.

        L'administrateur ne choisit jamais le mot de passe d'un utilisateur :
        soit celui-ci reçoit un lien, soit il doit contacter l'administrateur
        qui utilisera le formulaire de mot de passe de l'admin.
        """
        emailed, blocked = 0, 0

        for user in queryset:
            revoke_all_sessions(user)

            if user.email:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                send_password_reset_email(
                    user,
                    f"{settings.FRONTEND_URL}/reinitialiser-mot-de-passe?uid={uid}&token={token}",
                )
                emailed += 1
            else:
                user.set_unusable_password()
                user.save(update_fields=["password", "updated_at"])
                blocked += 1

        if emailed:
            self.message_user(request, f"{emailed} lien(s) de réinitialisation envoyé(s).")
        if blocked:
            self.message_user(
                request,
                f"{blocked} compte(s) sans email : mot de passe rendu inutilisable, "
                "définissez-en un nouveau depuis la fiche du compte.",
                level=messages.WARNING,
            )

    actions = ("activate_accounts", "suspend_accounts", "force_password_reset")

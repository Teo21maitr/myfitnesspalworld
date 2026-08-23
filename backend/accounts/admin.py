"""Administration des comptes.

L'administrateur peut accepter, suspendre ou réactiver un compte, mais ne
peut jamais lire le mot de passe courant (spec 05 §4).
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User, UserStatus


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


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = MfpUserChangeForm
    add_form = MfpUserCreationForm

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

    @admin.display(description="Nom complet")
    def full_name(self, obj: User) -> str:
        return obj.full_name

    @admin.action(description="Activer les comptes sélectionnés")
    def activate_accounts(self, request, queryset):
        updated = queryset.update(status=UserStatus.ACTIVE)
        self.message_user(request, f"{updated} compte(s) activé(s).")

    @admin.action(description="Suspendre les comptes sélectionnés")
    def suspend_accounts(self, request, queryset):
        updated = queryset.update(status=UserStatus.SUSPENDED)
        self.message_user(request, f"{updated} compte(s) suspendu(s).")

    actions = ("activate_accounts", "suspend_accounts")

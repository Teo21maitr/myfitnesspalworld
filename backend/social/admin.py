"""Administration des amitiés et des partages."""

from django.contrib import admin

from .models import FriendRequest, Friendship, SharePermission


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("from_user__username", "to_user__username")
    readonly_fields = ("from_user", "to_user", "status", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("user_1", "user_2", "created_at")
    search_fields = ("user_1__username", "user_2__username")
    readonly_fields = ("user_1", "user_2", "created_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(SharePermission)
class SharePermissionAdmin(admin.ModelAdmin):
    """Consultation. Retirer un partage depuis l'admin le révoque réellement.

    Modifier une permission à la main court-circuiterait les vérifications du
    service — notamment l'exigence d'amitié — d'où la lecture seule.
    """

    list_display = ("owner", "target_user", "resource_type", "resource_id", "visibility_type")
    list_filter = ("resource_type", "visibility_type")
    search_fields = ("owner__username", "target_user__username")
    readonly_fields = (
        "owner",
        "target_user",
        "resource_type",
        "resource_id",
        "visibility_type",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

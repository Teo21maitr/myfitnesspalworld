"""Administration des listes de courses."""

from django.contrib import admin

from .models import ShoppingList, ShoppingListItem


class ShoppingListItemInline(admin.TabularInline):
    model = ShoppingListItem
    extra = 0
    fields = ("name", "food", "quantity", "unit_label", "is_checked", "source_type")
    readonly_fields = fields


@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    """Consultation : les listes se composent depuis l'application."""

    list_display = ("name", "owner", "visibility", "created_at")
    list_filter = ("visibility",)
    search_fields = ("name", "owner__username")
    inlines = [ShoppingListItemInline]
    readonly_fields = ("owner", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

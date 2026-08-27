"""Routes de la liste de courses, montées sous `/api/v1/shopping-lists/`."""

from django.urls import path

from planning import views

shopping_list_patterns = [
    path("", views.ShoppingListListCreateView.as_view(), name="list"),
    path("generate/", views.ShoppingListGenerateView.as_view(), name="generate"),
    path("<int:pk>/", views.ShoppingListDetailView.as_view(), name="detail"),
    path("<int:pk>/items/", views.ShoppingListItemCreateView.as_view(), name="items"),
    path(
        "<int:pk>/items/<int:item_id>/",
        views.ShoppingListItemDetailView.as_view(),
        name="item-detail",
    ),
]

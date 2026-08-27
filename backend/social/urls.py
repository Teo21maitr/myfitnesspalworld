"""Routes sociales et de consultation partagée (spec 04 §12 et §13)."""

from django.urls import path

from social import views

user_patterns = [
    path("search/", views.UserSearchView.as_view(), name="search"),
]

friend_patterns = [
    path("", views.FriendListView.as_view(), name="list"),
    path("<int:user_id>/", views.FriendDetailView.as_view(), name="detail"),
]

friend_request_patterns = [
    path("", views.FriendRequestListCreateView.as_view(), name="list"),
    path(
        "<int:pk>/accept/",
        views.FriendRequestActionView.as_view(action="accept"),
        name="accept",
    ),
    path(
        "<int:pk>/reject/",
        views.FriendRequestActionView.as_view(action="reject"),
        name="reject",
    ),
]

share_patterns = [
    path("", views.ShareListCreateView.as_view(), name="list"),
    path("received/", views.ShareReceivedView.as_view(), name="received"),
    path("<int:pk>/", views.ShareDetailView.as_view(), name="detail"),
]

#: Consultation en lecture seule. Aucun verbe d'écriture n'existe ici : les
#: routes du propriétaire restent les seules à pouvoir modifier ses données.
shared_patterns = [
    path("diary/", views.SharedDiaryView.as_view(), name="diary"),
    path("progress/charts/", views.SharedProgressChartView.as_view(), name="progress-charts"),
    path("progress/weight/", views.SharedWeightView.as_view(), name="progress-weight"),
]

"""Routes des comptes, exposées sous `/api/v1/` (spec 04 §1, §2, §20)."""

from django.urls import path

from accounts import views

app_name = "accounts"

auth_patterns = [
    path("register-request/", views.RegistrationRequestView.as_view(), name="register-request"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", views.RefreshView.as_view(), name="refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("logout-all/", views.LogoutAllView.as_view(), name="logout-all"),
    path("me/", views.MeView.as_view(), name="me"),
    path("csrf/", views.CsrfView.as_view(), name="csrf"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset-password"),
]

profile_patterns = [
    path("", views.ProfileView.as_view(), name="profile"),
    path("settings/", views.UserSettingsView.as_view(), name="settings"),
]

account_patterns = [
    path("", views.AccountView.as_view(), name="account"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
]

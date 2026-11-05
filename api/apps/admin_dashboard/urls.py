from django.urls import path

from . import api

urlpatterns = [
    path("auth/login", api.AdminLoginView.as_view(), name="admin-login"),
    path("auth/logout", api.AdminLogoutView.as_view(), name="admin-logout"),
    path("auth/reauthenticate", api.AdminReauthenticateView.as_view(), name="admin-reauthenticate"),
    path("me", api.AdminMeView.as_view(), name="admin-me"),
    path("overview", api.AdminOverviewView.as_view(), name="admin-overview"),
    path("feature-flags", api.AdminFeatureFlagListView.as_view(), name="admin-feature-flags"),
    path("feature-flags/<str:key>/change", api.AdminFeatureFlagUpdateView.as_view(), name="admin-feature-flag-change"),
    path("feature-flags/<str:key>/history", api.AdminFeatureFlagHistoryView.as_view(), name="admin-feature-flag-history"),
    path("audit-logs", api.AdminAuditListView.as_view(), name="admin-audit-logs"),
    path("settings", api.AdminSettingsView.as_view(), name="admin-settings"),
    path("settings/<str:key>/change", api.AdminSettingUpdateView.as_view(), name="admin-setting-change"),
]

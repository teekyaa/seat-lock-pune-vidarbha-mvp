from django.urls import include, path

urlpatterns = [path("api/v1/admin/", include("apps.admin_dashboard.urls"))]

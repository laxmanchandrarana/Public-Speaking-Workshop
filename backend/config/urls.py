from django.contrib import admin
from django.urls import path, include
from .views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="health-check"),
    # Workshop endpoints will be mounted under /api/v1/
    path("api/v1/", include("apps.workshops.urls")),
    path("api/v1/", include("apps.registrations.urls")),
    path("api/v1/", include("apps.integrations.urls")),
]

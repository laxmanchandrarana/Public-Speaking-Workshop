from django.urls import path
from .views import NotificationClaimView, AutomationCallbackView

urlpatterns = [
    path(
        "integrations/notifications/claim/",
        NotificationClaimView.as_view(),
        name="notification-claim",
    ),
    path(
        "integrations/automation-callback/",
        AutomationCallbackView.as_view(),
        name="automation-callback",
    ),
]

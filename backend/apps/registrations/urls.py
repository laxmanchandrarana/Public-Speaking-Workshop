from django.urls import path
from .views import RegistrationCreateView

urlpatterns = [
    path("registrations/", RegistrationCreateView.as_view(), name="registration-create"),
]

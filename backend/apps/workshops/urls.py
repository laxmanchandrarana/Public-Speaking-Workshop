from django.urls import path
from .views import WorkshopDetailView

urlpatterns = [
    path("workshop/", WorkshopDetailView.as_view(), name="workshop-detail"),
]

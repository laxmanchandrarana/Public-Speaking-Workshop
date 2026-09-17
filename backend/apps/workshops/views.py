from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Workshop
from .serializers import WorkshopSerializer


class WorkshopDetailView(APIView):
    """
    Public endpoint providing current workshop details.
    """
    def get(self, request):
        # We fetch the primary Public Speaking Workshop record or first active workshop
        workshop = Workshop.objects.filter(is_active=True).first()
        if not workshop:
            return Response(
                {"error": "No active workshop found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = WorkshopSerializer(workshop)
        return Response(serializer.data, status=status.HTTP_200_OK)

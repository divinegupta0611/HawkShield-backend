from rest_framework import generics
from .models import Camera
from .serializers import CameraSerializer

class CameraListView(generics.ListCreateAPIView):
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer

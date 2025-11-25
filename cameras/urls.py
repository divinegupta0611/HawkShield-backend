from django.urls import path
from .views import CameraListView

urlpatterns = [
    path("cameras/", CameraListView.as_view(), name="camera-list"),
]

from django.urls import path
from . import views

urlpatterns = [
    path('add/', views.add_camera),
    path('all/', views.get_cameras),
    path('', views.get_cameras, name='get_cameras'),  # This was missing!
    path('delete/<str:cam_id>/', views.delete_camera),
]

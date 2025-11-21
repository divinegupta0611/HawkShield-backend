from django.urls import path
from . import views

urlpatterns = [
    path('all/', views.get_cameras),
    path('', views.get_cameras, name='get_cameras'),
    path('add/', views.add_camera, name='add_camera'),
    path('delete/<str:cam_id>/', views.delete_camera, name='delete_camera'),
    path('update/<str:cam_id>/', views.update_camera_status, name='update_camera_status'),
    path('cleanup/', views.cleanup_inactive_cameras, name='cleanup_cameras'),
    path('frame/<str:cam_id>/upload/', views.upload_frame, name='upload_frame'),
    path('frame/<str:cam_id>/', views.get_frame, name='get_frame'),
]

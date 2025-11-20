from django.urls import path
from .views import detect_mask_api, detect_threats, detect_emotion_api

urlpatterns = [
    path("detect-mask/", detect_mask_api),
    path("threats/", detect_threats),
    path("emotion/", detect_emotion_api),
]
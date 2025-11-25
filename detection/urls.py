from django.urls import path
from .views import detect_mask_api, detect_threats, detect_emotion_api, get_logs

urlpatterns = [
    path("detect-mask/", detect_mask_api),
    path("threats/", detect_threats),
    path("emotion/", detect_emotion_api),
    path("logs/", get_logs),
]
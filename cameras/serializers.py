# cameras/serializers.py
from rest_framework import serializers
from .models import Camera, Detection

class CameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Camera
        fields = ['id','name','owner','is_live','created_at','description']

class DetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Detection
        fields = ['id','camera','timestamp','label','confidence','bbox','raw']

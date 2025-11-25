from django.db import models

# Create your models here.
# cameras/models.py
from django.db import models
from django.conf import settings
import uuid

class Camera(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    is_live = models.BooleanField(default=False)
    # optional extra metadata
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.id})"

class Detection(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="detections")
    timestamp = models.DateTimeField(auto_now_add=True)
    label = models.CharField(max_length=100)   # e.g. "gun", "knife", "mask"
    confidence = models.FloatField()
    bbox = models.JSONField()  # {x,y,w,h} normalized or absolute
    raw = models.JSONField(blank=True, null=True)  # store extra info

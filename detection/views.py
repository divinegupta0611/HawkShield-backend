from django.shortcuts import render

# Create your views here.
from rest_framework.response import Response
from rest_framework.decorators import api_view
from detection.services.mask_detector import detect_mask
from detection.services.knife_detector import detect_knife
from detection.services.gun_detector import detect_gun
from detection.services.emotion_detector import detect_emotion
import tempfile

@api_view(["POST"])
def detect_mask_api(request):
    # Get uploaded file
    img = request.FILES.get("image")
    if not img:
        return Response({"error": "Image file not provided"}, status=400)

    # Save temp image
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in img.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    result = detect_mask(tmp_path)
    return Response(result)

@api_view(["POST"])
def detect_threats(request):
    image = request.FILES.get("image")
    if not image:
        return Response({"error": "Image not provided"}, status=400)

    # Save uploaded image to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in image.chunks():
            tmp.write(chunk)
        img_path = tmp.name

    # Run models
    knife_results = detect_knife(img_path)
    gun_results = detect_gun(img_path)

    # Combine results
    return Response({
        "knife": knife_results.get("predictions", []),
        "gun": gun_results.get("predictions", []),
        "total_detections": (
            knife_results.get("predictions", [])
            + gun_results.get("predictions", [])
        )
    })

@api_view(["POST"])
def detect_emotion_api(request):
    image = request.FILES.get("image")
    if not image:
        return Response({"error": "Image not provided"}, status=400)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in image.chunks():
            tmp.write(chunk)
        img_path = tmp.name

    result = detect_emotion(img_path)
    return Response(result)

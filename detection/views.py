from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view
from detection.services.mask_detector import detect_mask
from detection.services.knife_detector import detect_knife
from detection.services.gun_detector import detect_gun
from detection.services.emotion_detector import detect_emotion
from django.conf import settings
import tempfile
import os

@api_view(["POST"])
def detect_mask_api(request):
    """Detect masks in uploaded image"""
    img = request.FILES.get("image")
    if not img:
        return Response({"error": "Image file not provided"}, status=400)

    # Save temp image
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in img.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        result = detect_mask(tmp_path)
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@api_view(["POST"])
def detect_threats(request):
    """Detect weapons (knife, gun) in uploaded image"""
    image = request.FILES.get("image")
    camera_id = request.POST.get("cameraId")  # Optional: track which camera
    
    if not image:
        return Response({"error": "Image not provided"}, status=400)

    # Save uploaded image to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in image.chunks():
            tmp.write(chunk)
        img_path = tmp.name

    try:
        # Run detection models
        knife_results = detect_knife(img_path)
        gun_results = detect_gun(img_path)
        
        # Extract predictions safely
        knife_preds = knife_results.get("predictions", []) if isinstance(knife_results, dict) else []
        gun_preds = gun_results.get("predictions", []) if isinstance(gun_results, dict) else []
        
        # Combine results
        response_data = {
            "knife": knife_preds,
            "gun": gun_preds,
            "total_detections": len(knife_preds) + len(gun_preds),
            "has_threat": len(knife_preds) > 0 or len(gun_preds) > 0
        }
        
        if camera_id:
            response_data["cameraId"] = camera_id
            
            # Update threat count in database if camera_id provided
            try:
                collection = settings.CAMERA_COLLECTION
                if response_data["has_threat"]:
                    collection.update_one(
                        {"cameraId": camera_id},
                        {"$inc": {"threats": 1}}
                    )
            except Exception as db_error:
                print(f"Error updating threat count: {db_error}")
        
        return Response(response_data)
        
    except Exception as e:
        print(f"Error in threat detection: {e}")
        return Response({"error": str(e)}, status=500)
    finally:
        # Clean up temp file
        if os.path.exists(img_path):
            os.remove(img_path)


@api_view(["POST"])
def detect_emotion_api(request):
    """Detect emotions in uploaded image"""
    image = request.FILES.get("image")
    if not image:
        return Response({"error": "Image not provided"}, status=400)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in image.chunks():
            tmp.write(chunk)
        img_path = tmp.name

    try:
        result = detect_emotion(img_path)
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    finally:
        # Clean up temp file
        if os.path.exists(img_path):
            os.remove(img_path)


@api_view(["POST"])
def batch_detect_threats(request):
    """
    Detect threats in multiple images at once
    Useful for processing queued frames from multiple cameras
    """
    images = request.FILES.getlist("images")
    camera_ids = request.POST.getlist("cameraIds")
    
    if not images:
        return Response({"error": "No images provided"}, status=400)
    
    results = []
    
    for idx, image in enumerate(images):
        camera_id = camera_ids[idx] if idx < len(camera_ids) else None
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            for chunk in image.chunks():
                tmp.write(chunk)
            img_path = tmp.name
        
        try:
            knife_results = detect_knife(img_path)
            gun_results = detect_gun(img_path)
            
            knife_preds = knife_results.get("predictions", []) if isinstance(knife_results, dict) else []
            gun_preds = gun_results.get("predictions", []) if isinstance(gun_results, dict) else []
            
            result = {
                "cameraId": camera_id,
                "knife": knife_preds,
                "gun": gun_preds,
                "has_threat": len(knife_preds) > 0 or len(gun_preds) > 0
            }
            results.append(result)
            
        except Exception as e:
            results.append({
                "cameraId": camera_id,
                "error": str(e)
            })
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)
    
    return Response({
        "results": results,
        "total_processed": len(results)
    })
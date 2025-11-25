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
from datetime import datetime

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
        
        # Filter mask predictions to only include actual masks
        if isinstance(result, dict) and "predictions" in result:
            all_preds = result["predictions"]
            mask_preds = []
            mask_class_names = ["mask", "with_mask", "face_mask", "masked", "wearing_mask", "with-mask", "face-mask"]
            no_mask_class_names = ["no_mask", "without_mask", "no-mask", "without-mask", "no mask", "without mask"]
            
            print(f"Mask API returned {len(all_preds)} predictions")
            for pred in all_preds:
                if isinstance(pred, dict):
                    pred_class = pred.get("class", "").lower() or pred.get("predicted_class", "").lower() or ""
                    confidence = float(pred.get("confidence", 0) or pred.get("confidence_score", 0) or 0)
                    
                    # Exclude "no mask" detections
                    is_no_mask = any(no_mask in pred_class for no_mask in no_mask_class_names)
                    if is_no_mask:
                        continue
                    
                    # Check if it's a mask detection
                    is_mask = any(mask_name in pred_class for mask_name in mask_class_names)
                    if is_mask and confidence > 0.3:
                        mask_preds.append(pred)
                    elif confidence > 0.6 and pred_class:  # High confidence unknown class
                        mask_preds.append(pred)
            
            result["predictions"] = mask_preds
            result["filtered_count"] = len(mask_preds)
            result["original_count"] = len(all_preds)
            print(f"Filtered to {len(mask_preds)} mask detections")
        
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@api_view(["POST"])
def detect_threats(request):
    """Detect all threats: knives, guns, masks, and angry emotions"""
    image = request.FILES.get("image")
    camera_id = request.POST.get("cameraId")
    camera_name = request.POST.get("cameraName", "Unknown")
    
    if not image:
        return Response({"error": "Image not provided"}, status=400)

    # Save uploaded image to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in image.chunks():
            tmp.write(chunk)
        img_path = tmp.name

    try:
        # Run all detection models
        print("Starting detection for all threat types...")
        knife_results = detect_knife(img_path)
        gun_results = detect_gun(img_path)
        mask_results = detect_mask(img_path)
        emotion_results = detect_emotion(img_path)
        
        # Log mask detection results for debugging
        if isinstance(mask_results, dict):
            if "error" in mask_results:
                print(f"❌ Mask detection error: {mask_results['error']}")
            elif "predictions" in mask_results:
                print(f"✅ Mask detection raw results: {len(mask_results['predictions'])} predictions found")
                # Print all predictions for debugging
                for idx, pred in enumerate(mask_results.get("predictions", [])):
                    if isinstance(pred, dict):
                        pred_class = pred.get("class", "") or pred.get("predicted_class", "")
                        confidence = pred.get("confidence", 0) or pred.get("confidence_score", 0)
                        print(f"  Prediction {idx}: class='{pred_class}', confidence={confidence}")
            else:
                print(f"⚠️ Mask detection response structure: {list(mask_results.keys())}")
                print(f"Full mask response (first 500 chars): {str(mask_results)[:500]}")
        else:
            print(f"⚠️ Mask detection returned non-dict: {type(mask_results)}")
        
        # Extract predictions safely
        knife_preds = knife_results.get("predictions", []) if isinstance(knife_results, dict) else []
        gun_preds = gun_results.get("predictions", []) if isinstance(gun_results, dict) else []
        all_mask_preds = mask_results.get("predictions", []) if isinstance(mask_results, dict) else []
        emotion_preds = emotion_results.get("predictions", []) if isinstance(emotion_results, dict) else []
        
        # ACCEPT EVERYTHING - Any detection in front of face = mask
        mask_preds = []
        
        print(f"🔍 Processing {len(all_mask_preds)} mask predictions...")
        
        # ACCEPT ALL PREDICTIONS - anything detected in front of face is a mask
        if len(all_mask_preds) > 0:
            for pred in all_mask_preds:
                if isinstance(pred, dict):
                    pred_class = pred.get("class", "") or pred.get("predicted_class", "") or "unknown"
                    confidence = float(pred.get("confidence", 0) or pred.get("confidence_score", 0) or 0)
                    
                    # ACCEPT EVERYTHING - no filtering
                    mask_preds.append(pred)
                    print(f"  ✅ ACCEPTED: '{pred_class}' (confidence: {confidence:.2f}) - ANYTHING in front of face = MASK")
        else:
            print("  ⚠️ No mask predictions returned from API")
        
        print(f"🎯 Final mask count: {len(mask_preds)} masks detected (ALL predictions accepted)")
        
        # Check for angry emotions
        angry_emotions = []
        for pred in emotion_preds:
            if isinstance(pred, dict):
                pred_class = pred.get("class", "").lower() or pred.get("predicted_class", "").lower()
                if any(angry_word in pred_class for angry_word in ["angry", "anger", "furious", "rage"]):
                    angry_emotions.append(pred)
        
        # Debug logging
        print(f"Detection results - Knife: {len(knife_preds)}, Gun: {len(gun_preds)}, Mask: {len(mask_preds)}, Angry: {len(angry_emotions)}")
        
        # Determine if there's a threat - MASKS ARE ALWAYS THREATS
        has_threat = (
            len(knife_preds) > 0 or 
            len(gun_preds) > 0 or 
            len(mask_preds) > 0 or  # ANY mask detection = threat
            len(angry_emotions) > 0
        )
        
        # Force log if masks detected
        if len(mask_preds) > 0:
            print(f"🚨 THREAT DETECTED: {len(mask_preds)} mask(s) found! (ANYTHING in front of face = MASK = THREAT)")
        else:
            print(f"✅ No threats detected (knife: {len(knife_preds)}, gun: {len(gun_preds)}, mask: {len(mask_preds)}, angry: {len(angry_emotions)})")
        
        # Combine results
        response_data = {
            "knife": knife_preds,
            "gun": gun_preds,
            "mask": mask_preds,
            "emotion": emotion_preds,
            "angry_emotions": angry_emotions,
            "total_detections": len(knife_preds) + len(gun_preds) + len(mask_preds) + len(angry_emotions),
            "has_threat": has_threat
        }
        
        if camera_id:
            response_data["cameraId"] = camera_id
            response_data["cameraName"] = camera_name
            
            # Update threat count and create log entry
            try:
                camera_collection = settings.CAMERA_COLLECTION
                logs_collection = settings.LOGS_COLLECTION
                
                # Update camera threat count and lastSeen
                if has_threat:
                    camera_collection.update_one(
                        {"cameraId": camera_id},
                        {"$inc": {"threats": 1}, "$set": {"lastSeen": datetime.utcnow().isoformat()}}
                    )
                else:
                    camera_collection.update_one(
                        {"cameraId": camera_id},
                        {"$set": {"lastSeen": datetime.utcnow().isoformat()}}
                    )
                
                # Create log entry
                threat_types = []
                if len(knife_preds) > 0:
                    threat_types.append("Knife")
                if len(gun_preds) > 0:
                    threat_types.append("Gun")
                if len(mask_preds) > 0:
                    threat_types.append("Face Mask")
                if len(angry_emotions) > 0:
                    threat_types.append("Angry Person")
                
                if has_threat:
                    # Always log threats
                    log_entry = {
                        "cameraId": camera_id,
                        "cameraName": camera_name,
                        "type": "threat",
                        "threatTypes": threat_types,
                        "timestamp": datetime.utcnow().isoformat(),
                        "detections": {
                            "knife": len(knife_preds),
                            "gun": len(gun_preds),
                            "mask": len(mask_preds),
                            "angry_emotions": len(angry_emotions)
                        }
                    }
                    logs_collection.insert_one(log_entry)
                else:
                    # Log safe status only every 30 seconds to avoid spam
                    last_safe_log = logs_collection.find_one(
                        {"cameraId": camera_id, "type": "safe"},
                        sort=[("timestamp", -1)]
                    )
                    
                    should_log_safe = False
                    if not last_safe_log:
                        should_log_safe = True
                    else:
                        try:
                            last_time = datetime.fromisoformat(last_safe_log["timestamp"].replace('Z', '+00:00'))
                            time_diff = (datetime.utcnow() - last_time.replace(tzinfo=None)).total_seconds()
                            if time_diff >= 30:
                                should_log_safe = True
                        except:
                            should_log_safe = True
                    
                    if should_log_safe:
                        log_entry = {
                            "cameraId": camera_id,
                            "cameraName": camera_name,
                            "type": "safe",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        logs_collection.insert_one(log_entry)
                        
            except Exception as db_error:
                print(f"Error updating database: {db_error}")
        
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


@api_view(["GET"])
def get_logs(request):
    """Get threat and safe logs from database"""
    try:
        logs_collection = settings.LOGS_COLLECTION
        limit = int(request.GET.get("limit", 100))
        log_type = request.GET.get("type")  # "threat" or "safe" or None for all
        
        query = {}
        if log_type:
            query["type"] = log_type
        
        logs = list(logs_collection.find(query).sort("timestamp", -1).limit(limit))
        
        # Convert ObjectId to string
        for log in logs:
            if "_id" in log:
                log["_id"] = str(log["_id"])
        
        return Response({
            "logs": logs,
            "count": len(logs)
        })
    except Exception as e:
        return Response({"error": str(e)}, status=500)
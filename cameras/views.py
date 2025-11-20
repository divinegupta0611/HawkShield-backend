from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings
from bson import ObjectId
from datetime import datetime

collection = settings.CAMERA_COLLECTION

# Helper function to convert ObjectId to string
def serialize_camera(camera):
    if '_id' in camera:
        camera['_id'] = str(camera['_id'])
    return camera

@csrf_exempt
def add_camera(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))

            if 'cameraId' not in data or 'cameraName' not in data:
                return JsonResponse({"error": "cameraId and cameraName required"}, status=400)

            # Check if camera already exists
            existing = collection.find_one({"cameraId": data['cameraId']})
            if existing:
                return JsonResponse({
                    "error": "Camera with this ID already exists",
                    "camera": serialize_camera(existing)
                }, status=409)

            camera = {
                "cameraId": data['cameraId'],
                "cameraName": data['cameraName'],
                "people": data.get("people", 0),
                "threats": data.get("threats", 0),
                "sourceDeviceId": data.get("sourceDeviceId", None),  # Track which device owns this camera
                "hasRemoteStream": data.get("hasRemoteStream", False),
                "status": "active",
                "lastSeen": datetime.utcnow().isoformat(),
                "createdAt": datetime.utcnow().isoformat()
            }

            result = collection.insert_one(camera)
            camera['_id'] = str(result.inserted_id)

            return JsonResponse({"message": "Camera added", "camera": camera}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            print("Error adding camera:", e)
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


def get_cameras(request):
    """Get all cameras with their current status"""
    try:
        cams = list(collection.find({}))
        
        # Update lastSeen for active cameras
        current_time = datetime.utcnow().isoformat()
        
        # Convert all ObjectIds to string and add status info
        cams = [serialize_camera(cam) for cam in cams]
        
        return JsonResponse({
            "cameras": cams,
            "count": len(cams),
            "timestamp": current_time
        }, status=200)
    except Exception as e:
        print("Error fetching cameras:", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def update_camera_status(request, cam_id):
    """Update camera status (heartbeat from streaming devices)"""
    if request.method == "PUT":
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            update_data = {
                "lastSeen": datetime.utcnow().isoformat(),
                "status": data.get("status", "active")
            }
            
            # Update optional fields if provided
            if "people" in data:
                update_data["people"] = data["people"]
            if "threats" in data:
                update_data["threats"] = data["threats"]
            
            result = collection.update_one(
                {"cameraId": cam_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return JsonResponse({"error": "Camera not found"}, status=404)
            
            return JsonResponse({
                "message": "Camera status updated",
                "cameraId": cam_id
            }, status=200)
            
        except Exception as e:
            print("Error updating camera status:", e)
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request method"}, status=405)


@csrf_exempt
def delete_camera(request, cam_id):
    if request.method == "DELETE":
        try:
            result = collection.delete_one({"cameraId": cam_id})
            
            if result.deleted_count == 0:
                return JsonResponse({"error": "Camera not found"}, status=404)
            
            return JsonResponse({
                "message": "Camera removed successfully",
                "cameraId": cam_id
            }, status=200)
            
        except Exception as e:
            print("Error deleting camera:", e)
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@csrf_exempt
def cleanup_inactive_cameras(request):
    """Remove cameras that haven't sent heartbeat in 60 seconds"""
    if request.method == "POST":
        try:
            from datetime import datetime, timedelta
            
            cutoff_time = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
            
            result = collection.delete_many({
                "lastSeen": {"$lt": cutoff_time}
            })
            
            return JsonResponse({
                "message": f"Cleaned up {result.deleted_count} inactive cameras",
                "count": result.deleted_count
            }, status=200)
            
        except Exception as e:
            print("Error cleaning up cameras:", e)
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Invalid request method"}, status=405)
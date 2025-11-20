from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings
from bson import ObjectId

collection = settings.CAMERA_COLLECTION

# Helper function to convert ObjectId to string
def serialize_camera(camera):
    camera['_id'] = str(camera['_id'])
    return camera

@csrf_exempt
def add_camera(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))

            if 'cameraId' not in data or 'cameraName' not in data:
                return JsonResponse({"error": "cameraId and cameraName required"}, status=400)

            camera = {
                "cameraId": data['cameraId'],
                "cameraName": data['cameraName'],
                "people": data.get("people", 0),
                "threats": data.get("threats", 0)
            }

            result = collection.insert_one(camera)

            # Add _id to response
            camera['_id'] = str(result.inserted_id)

            return JsonResponse({"message": "Camera added", "camera": camera}, status=201)

        except Exception as e:
            print("Error adding camera:", e)
            return JsonResponse({"error": "Failed to add camera"}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)


def get_cameras(request):
    try:
        cams = list(collection.find({}))
        # Convert all ObjectIds to string
        cams = [serialize_camera(cam) for cam in cams]
        return JsonResponse({"cameras": cams}, status=200)
    except Exception as e:
        print("Error fetching cameras:", e)
        return JsonResponse({"error": "Failed to fetch cameras"}, status=500)


@csrf_exempt
def delete_camera(request, cam_id):
    if request.method == "DELETE":
        try:
            result = collection.delete_one({"cameraId": cam_id})
            if result.deleted_count == 0:
                return JsonResponse({"error": "Camera not found"}, status=404)
            return JsonResponse({"message": "Camera removed"}, status=200)
        except Exception as e:
            print("Error deleting camera:", e)
            return JsonResponse({"error": "Failed to delete camera"}, status=500)

    return JsonResponse({"error": "Invalid request"}, status=400)

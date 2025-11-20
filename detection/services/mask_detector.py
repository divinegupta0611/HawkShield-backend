import requests

ROBOFLOW_API_KEY = "nob2A5RQmN6iKyQFIsC5"
MODEL_ID = "face-mask-detection-2gpmy/1"
API_URL = f"https://detect.roboflow.com/{MODEL_ID}?api_key={ROBOFLOW_API_KEY}"


def detect_mask(image_path: str):
    """
    Sends an image to Roboflow API and returns mask detection result.
    Works with Python 3.13 (no inference-sdk needed).
    """

    with open(image_path, "rb") as img:
        response = requests.post(API_URL, files={"file": img})
    
    try:
        return response.json()
    except Exception:
        return {"error": "Invalid response received"}

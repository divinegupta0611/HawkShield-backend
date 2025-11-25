import requests

ROBOFLOW_API_KEY = "nob2A5RQmN6iKyQFIsC5"
MODEL_ID = "gun-detection-ghlzd/4"
API_URL = f"https://detect.roboflow.com/{MODEL_ID}?api_key={ROBOFLOW_API_KEY}"


def detect_gun(image_path: str):
    """
    Sends image to Roboflow Gun Detection model.
    Fully compatible with Python 3.13.
    """
    with open(image_path, "rb") as img:
        response = requests.post(API_URL, files={"file": img})

    try:
        return response.json()
    except Exception:
        return {"error": "Invalid Roboflow response"}

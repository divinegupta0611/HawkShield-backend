import requests

ROBOFLOW_API_KEY = "nob2A5RQmN6iKyQFIsC5"
MODEL_ID = "face-mask-detection-2gpmy/1"
API_URL = f"https://detect.roboflow.com/{MODEL_ID}?api_key={ROBOFLOW_API_KEY}"


def detect_mask(image_path: str):
    """
    Sends an image to Roboflow API and returns mask detection result.
    Works with Python 3.13 (no inference-sdk needed).
    """

    try:
        with open(image_path, "rb") as img:
            response = requests.post(API_URL, files={"file": img}, timeout=10)
        
        if response.status_code != 200:
            print(f"Mask detection API error: {response.status_code} - {response.text}")
            return {"error": f"API returned status {response.status_code}", "predictions": []}
        
        result = response.json()
        
        # Log the response for debugging
        if "predictions" in result:
            print(f"Mask detection found {len(result['predictions'])} predictions")
            for pred in result['predictions']:
                if isinstance(pred, dict):
                    print(f"  - Class: {pred.get('class', 'unknown')}, Confidence: {pred.get('confidence', 0)}")
        
        return result
    except requests.exceptions.Timeout:
        print("Mask detection API timeout")
        return {"error": "API timeout", "predictions": []}
    except requests.exceptions.RequestException as e:
        print(f"Mask detection API request error: {e}")
        return {"error": str(e), "predictions": []}
    except Exception as e:
        print(f"Mask detection error: {e}")
        return {"error": str(e), "predictions": []}

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
            response = requests.post(API_URL, files={"file": img}, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Mask detection API error: {response.status_code} - {response.text[:200]}")
            return {"error": f"API returned status {response.status_code}", "predictions": []}
        
        result = response.json()
        
        # Log the response for debugging
        print(f"📦 Mask API Response Keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        if "predictions" in result:
            print(f"✅ Mask detection found {len(result['predictions'])} predictions")
            for idx, pred in enumerate(result['predictions']):
                if isinstance(pred, dict):
                    print(f"  [{idx}] Class: '{pred.get('class', 'unknown')}', Confidence: {pred.get('confidence', 0):.2f}")
        else:
            print(f"⚠️ No 'predictions' key in response. Full response: {str(result)[:300]}")
        
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

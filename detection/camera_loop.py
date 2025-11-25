import cv2
import time
from detection.services.mask_detector import detect_mask
from detection.services.knife_detector import detect_knife

def start_camera_detection():
    cap = cv2.VideoCapture(0)  # your webcam

    if not cap.isOpened():
        print("Camera not detected")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Save current frame
        cv2.imwrite("current_frame.jpg", frame)

        # Call detection
        result = detect_mask("current_frame.jpg")
        print("Detection:", result)

        # Sleep so you don't spam API
        time.sleep(1)
        
def start_knife_detection():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Camera not available")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        cv2.imwrite("current_frame.jpg", frame)

        result = detect_knife("current_frame.jpg")
        print("Knife Detection:", result)

        time.sleep(1)
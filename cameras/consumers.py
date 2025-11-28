import json
import cv2
import numpy as np
import base64
import torch
from channels.generic.websocket import AsyncWebsocketConsumer
from pathlib import Path
import asyncio
from ultralytics import YOLO
from datetime import datetime


# Load YOLO models at startup
BASE_DIR = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = BASE_DIR / "cameras" / "weights"

# Load models
face_mask_model = YOLO(str(WEIGHTS_DIR / "face_mask_best.pt"))
weapon_model = YOLO(str(WEIGHTS_DIR / "knife_detector.pt"))

print("✅ YOLOv11 Models loaded successfully!")

# Set different confidence thresholds per detection type
CONFIDENCE_THRESHOLDS = {
    "face_mask": 0.5,
    "gun": 0.6,      # Higher threshold to reduce false positives
    "knife": 0.55,   # Slightly higher
    "blood": 0.7,    # Much higher to prevent false blood detections
}

# Default model confidence (will be overridden per class)
face_mask_model.conf = 0.5
weapon_model.conf = 0.5

# Print model class names for debugging
print(f"Face Mask Model Classes: {face_mask_model.names}")
print(f"Weapon Model Classes: {weapon_model.names}")


class CameraConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.camera_id = None
        self.role = None  # 'streamer' or 'viewer'
        self.detection_task = None
        print(f"WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        # Stop detection task if running
        if self.detection_task:
            self.detection_task.cancel()
            
        if self.camera_id:
            # Leave the camera group
            await self.channel_layer.group_discard(
                f"camera_{self.camera_id}",
                self.channel_name
            )
            
            # Notify others about disconnection
            if self.role == "streamer":
                await self.channel_layer.group_send(
                    f"camera_{self.camera_id}",
                    {
                        "type": "streamer_left",
                        "camera_id": self.camera_id
                    }
                )
        print(f"WebSocket disconnected: {self.channel_name}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get("action")
            
            print(f"Received action: {action} from {self.channel_name}")

            # ---------- Streamer joins ----------
            if action == "streamer_join":
                self.camera_id = data["camera_id"]
                self.role = "streamer"
                
                # Join camera group
                await self.channel_layer.group_add(
                    f"camera_{self.camera_id}",
                    self.channel_name
                )
                
                await self.send(text_data=json.dumps({
                    "action": "streamer_joined",
                    "camera_id": self.camera_id,
                    "channel": self.channel_name
                }))
                print(f"Streamer joined camera {self.camera_id}")

            # ---------- Video Frame for Detection ----------
            elif action == "video_frame":
                # Process frame for detection
                frame_data = data.get("frame")
                camera_name = data.get("camera_name", "Unknown Camera")
                if frame_data:
                    await self.process_frame(frame_data, camera_name)

            # ---------- Viewer joins ----------
            elif action == "viewer_join":
                self.camera_id = data["camera_id"]
                self.role = "viewer"
                
                # Join camera group
                await self.channel_layer.group_add(
                    f"camera_{self.camera_id}",
                    self.channel_name
                )
                
                # Notify streamer that viewer joined
                await self.channel_layer.group_send(
                    f"camera_{self.camera_id}",
                    {
                        "type": "viewer_joined",
                        "viewer_channel": self.channel_name,
                        "camera_id": self.camera_id
                    }
                )
                print(f"Viewer {self.channel_name} joined camera {self.camera_id}")

            # ---------- WebRTC Signaling ----------
            elif action == "offer":
                target = data["target"]
                await self.channel_layer.send(
                    target,
                    {
                        "type": "webrtc_message",
                        "message": {
                            "action": "offer",
                            "sdp": data["sdp"],
                            "sender": self.channel_name
                        }
                    }
                )
                print(f"Offer sent from {self.channel_name} to {target}")

            elif action == "answer":
                target = data["target"]
                await self.channel_layer.send(
                    target,
                    {
                        "type": "webrtc_message",
                        "message": {
                            "action": "answer",
                            "sdp": data["sdp"],
                            "sender": self.channel_name
                        }
                    }
                )
                print(f"Answer sent from {self.channel_name} to {target}")

            elif action == "ice-candidate":
                target = data["target"]
                await self.channel_layer.send(
                    target,
                    {
                        "type": "webrtc_message",
                        "message": {
                            "action": "ice-candidate",
                            "candidate": data["candidate"],
                            "sender": self.channel_name
                        }
                    }
                )
                print(f"ICE candidate sent from {self.channel_name} to {target}")

        except Exception as e:
            print(f"Error in receive: {e}")
            import traceback
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                "action": "error",
                "message": str(e)
            }))

    async def process_frame(self, frame_data, camera_name):
        """Process video frame for object detection"""
        try:
            # Decode base64 image
            img_data = base64.b64decode(frame_data.split(',')[1])
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
            
            # Run detection in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            detections = await loop.run_in_executor(None, self.detect_objects, frame)
            
            # Send detections back to streamer
            if detections:
                await self.send(text_data=json.dumps({
                    "action": "detections",
                    "detections": detections
                }))
                
                # Broadcast detections to all viewers in this camera group
                await self.channel_layer.group_send(
                    f"camera_{self.camera_id}",
                    {
                        "type": "broadcast_detections",
                        "detections": detections,
                        "camera_id": self.camera_id,
                        "camera_name": camera_name,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                )
                
        except Exception as e:
            print(f"Error processing frame: {e}")
            import traceback
            traceback.print_exc()

    def detect_objects(self, frame):
        """Run both models and collect all detections"""
        detections = []

        # ----- FACE MASK DETECTION -----
        try:
            mask_results = face_mask_model(frame, verbose=False)[0]
            for box in mask_results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = face_mask_model.names[cls]

                # Apply threshold
                if conf >= CONFIDENCE_THRESHOLDS["face_mask"]:
                    detections.append({
                        "type": "face_mask",
                        "class": class_name,
                        "confidence": round(conf, 3),
                        "bbox": [x1, y1, x2, y2],
                        "severity": self.get_severity("face_mask", class_name)
                    })
        except Exception as e:
            print(f"Error in face mask detection: {e}")

        # ----- WEAPON & BLOOD DETECTION -----
        try:
            # Run detection with lower base confidence to catch more objects
            weapon_results = weapon_model(frame, conf=0.4, verbose=False)[0]
            
            for box in weapon_results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = weapon_model.names[cls]

                # Determine detection type
                detection_type = self.classify_detection(class_name)
                
                # Apply class-specific threshold
                threshold = CONFIDENCE_THRESHOLDS.get(detection_type, 0.5)
                
                # Debug logging
                print(f"Detected: {class_name} ({detection_type}) - Confidence: {conf:.3f} - Threshold: {threshold}")
                
                # Only include if meets threshold
                if conf >= threshold:
                    detections.append({
                        "type": detection_type,
                        "class": class_name,
                        "confidence": round(conf, 3),
                        "bbox": [x1, y1, x2, y2],
                        "severity": self.get_severity(detection_type, class_name)
                    })
                else:
                    print(f"  ❌ Filtered out (below threshold)")
                    
        except Exception as e:
            print(f"Error in weapon/blood detection: {e}")
            import traceback
            traceback.print_exc()

        return detections

    def classify_detection(self, class_name):
        """Classify detection type based on class name"""
        class_name_lower = class_name.lower()
        
        # More comprehensive matching
        if any(keyword in class_name_lower for keyword in ['gun', 'pistol', 'firearm', 'rifle', 'weapon']):
            return "gun"
        elif any(keyword in class_name_lower for keyword in ['knife', 'blade', 'dagger', 'machete']):
            return "knife"
        elif 'blood' in class_name_lower:
            return "blood"
        else:
            # If no match, print for debugging
            print(f"⚠️ Unknown class name: {class_name}")
            return "weapon"

    def get_severity(self, detection_type, class_name):
        """Assign severity level to detections"""
        # Critical severity for weapons and blood
        if detection_type == "gun":
            return "critical"
        elif detection_type == "knife":
            return "high"
        elif detection_type == "blood":
            return "high"
        # Medium severity for no mask
        elif detection_type == "face_mask" and any(word in class_name.lower() for word in ["without", "no", "not"]):
            return "medium"
        # Low severity for with mask
        elif detection_type == "face_mask" and any(word in class_name.lower() for word in ["with", "mask"]):
            return "low"
        else:
            return "medium"

    # Handler for viewer joined notification
    async def viewer_joined(self, event):
        # Only send to streamer
        if self.role == "streamer":
            await self.send(text_data=json.dumps({
                "action": "viewer_joined",
                "viewer": event["viewer_channel"],
                "camera_id": event["camera_id"]
            }))

    # Handler for streamer left notification
    async def streamer_left(self, event):
        if self.role == "viewer":
            await self.send(text_data=json.dumps({
                "action": "streamer_left",
                "camera_id": event["camera_id"]
            }))

    # Handler for WebRTC messages
    async def webrtc_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    # Handler for broadcasting detections to viewers
    async def broadcast_detections(self, event):
        # Only send to viewers
        if self.role == "viewer":
            await self.send(text_data=json.dumps({
                "action": "detections",
                "detections": event["detections"],
                "camera_id": event["camera_id"],
                "camera_name": event["camera_name"],
                "timestamp": event["timestamp"]
            }))
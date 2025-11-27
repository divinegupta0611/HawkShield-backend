import json
import cv2
import numpy as np
import base64
import torch
from channels.generic.websocket import AsyncWebsocketConsumer
from pathlib import Path
import asyncio
from ultralytics import YOLO


# Load YOLO models at startup
BASE_DIR = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = BASE_DIR / "cameras" / "weights"
# Load models
face_mask_model = YOLO(str(WEIGHTS_DIR / "face_mask_best.pt"))
knife_model = YOLO(str(WEIGHTS_DIR / "knife_detector.pt"))

print("✅ YOLOv11 Models loaded successfully!")

face_mask_model.conf = 0.6  # confidence threshold

knife_model.conf = 0.6  # confidence threshold


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
                if frame_data:
                    await self.process_frame(frame_data)

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

    async def process_frame(self, frame_data):
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
            
            # Send detections back to client
            if detections:
                await self.send(text_data=json.dumps({
                    "action": "detections",
                    "detections": detections
                }))
                
        except Exception as e:
            print(f"Error processing frame: {e}")
            import traceback
            traceback.print_exc()

    def detect_objects(self, frame):
        detections = []

        # ----- FACE MASK DETECTION -----
        mask_results = face_mask_model(frame)[0]
        for box in mask_results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            class_name = face_mask_model.names[cls]

            detections.append({
                "type": "face_mask",
                "class": class_name,
                "confidence": conf,
                "bbox": [x1, y1, x2, y2]
            })

        # ----- KNIFE DETECTION -----
        knife_results = knife_model(frame)[0]
        for box in knife_results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            class_name = knife_model.names[cls]

            detections.append({
                "type": "knife",
                "class": class_name,
                "confidence": conf,
                "bbox": [x1, y1, x2, y2]
            })

        return detections


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
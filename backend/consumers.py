import json
from channels.generic.websocket import AsyncWebsocketConsumer

# Store active streamers and viewers
STREAMERS = {}  # camera_id -> channel_name
VIEWERS = {}    # viewer_channel -> camera_id

class CameraConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        print(f"WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        print(f"WebSocket disconnected: {self.channel_name}")
        
        # Remove viewer
        if self.channel_name in VIEWERS:
            camera_id = VIEWERS.pop(self.channel_name)
            print(f"Viewer {self.channel_name} left camera {camera_id}")

        # Remove streamer
        for cam_id, ch_name in list(STREAMERS.items()):
            if ch_name == self.channel_name:
                STREAMERS.pop(cam_id)
                print(f"Streamer for camera {cam_id} disconnected")
                break

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get("action")
            print(f"Received action: {action}")

            # ---------- Streamer joins ----------
            if action == "streamer_join":
                camera_id = data["camera_id"]
                STREAMERS[camera_id] = self.channel_name
                print(f"Streamer joined for camera {camera_id}")
                await self.send(text_data=json.dumps({
                    "action": "streamer_joined",
                    "camera_id": camera_id
                }))
                return

            # ---------- Viewer joins ----------
            if action == "viewer_join":
                camera_id = data["camera_id"]
                VIEWERS[self.channel_name] = camera_id
                streamer_channel = STREAMERS.get(camera_id)
                
                print(f"Viewer {self.channel_name} wants to watch camera {camera_id}")
                print(f"Streamer channel: {streamer_channel}")
                
                if streamer_channel:
                    # Tell streamer a viewer joined
                    await self.channel_layer.send(streamer_channel, {
                        "type": "viewer_joined",
                        "viewer": self.channel_name
                    })
                else:
                    # No streamer available
                    await self.send(text_data=json.dumps({
                        "action": "error",
                        "message": "Camera is not streaming"
                    }))
                return

            # ---------- Offer from streamer ----------
            if action == "offer":
                target = data["target"]
                await self.channel_layer.send(target, {
                    "type": "webrtc_relay",
                    "data": {
                        "action": "offer",
                        "sdp": data["sdp"],
                        "target": self.channel_name
                    }
                })
                return

            # ---------- Answer from viewer ----------
            if action == "answer":
                target = data["target"]
                await self.channel_layer.send(target, {
                    "type": "webrtc_relay",
                    "data": {
                        "action": "answer",
                        "sdp": data["sdp"],
                        "target": self.channel_name
                    }
                })
                return

            # ---------- ICE candidate ----------
            if action == "ice-candidate":
                target = data["target"]
                await self.channel_layer.send(target, {
                    "type": "webrtc_relay",
                    "data": {
                        "action": "ice-candidate",
                        "candidate": data["candidate"],
                        "target": self.channel_name
                    }
                })
                return

        except Exception as e:
            print(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                "action": "error",
                "message": str(e)
            }))

    # Handler to send viewer join notification to streamer
    async def viewer_joined(self, event):
        await self.send(text_data=json.dumps({
            "action": "viewer_joined",
            "viewer": event["viewer"]
        }))

    # Relay WebRTC messages
    async def webrtc_relay(self, event):
        await self.send(text_data=json.dumps(event["data"]))
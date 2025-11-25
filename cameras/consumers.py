import json
from channels.generic.websocket import AsyncWebsocketConsumer

class CameraConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.camera_id = None
        self.role = None  # 'streamer' or 'viewer'
        print(f"WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
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
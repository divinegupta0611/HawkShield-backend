from channels.generic.websocket import AsyncWebsocketConsumer
import json

class CameraStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.camera_id = self.scope['url_route']['kwargs']['camera_id']
        self.room_group_name = f"camera_{self.camera_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        # Forward the frame to all viewers
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_stream",
                "bytes": bytes_data
            }
        )

    async def broadcast_stream(self, event):
        await self.send(bytes_data=event["bytes"])

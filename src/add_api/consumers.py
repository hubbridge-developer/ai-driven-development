"""WebSocket consumer for real-time workflow status updates."""

import json
import structlog
from channels.generic.websocket import AsyncWebsocketConsumer

logger = structlog.get_logger()


class WorkflowConsumer(AsyncWebsocketConsumer):
    """WebSocket endpoint: /ws/workflow/{workflow_id}

    Broadcasts agent transitions, approval notifications, and status updates.
    """

    async def connect(self):
        self.workflow_id = self.scope["url_route"]["kwargs"]["workflow_id"]
        self.group_name = f"workflow_{self.workflow_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info("ws_connected", workflow_id=self.workflow_id)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info("ws_disconnected", workflow_id=self.workflow_id)

    async def receive(self, text_data=None, bytes_data=None):
        # Client messages not expected, but handle gracefully
        pass

    async def workflow_update(self, event):
        """Handle workflow.update messages from channel layer."""
        await self.send(text_data=json.dumps(event["data"]))

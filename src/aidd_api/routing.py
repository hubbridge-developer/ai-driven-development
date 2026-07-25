from django.urls import re_path
from src.aidd_api.consumers import WorkflowConsumer

websocket_urlpatterns = [
    re_path(r"ws/workflow/(?P<workflow_id>[\w-]+)$", WorkflowConsumer.as_asgi()),
]

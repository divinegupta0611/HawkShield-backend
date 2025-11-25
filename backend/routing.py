from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import cameras.routing   # ✔ FIXED: this file now exists

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(
        cameras.routing.websocket_urlpatterns
    ),
})

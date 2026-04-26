# main/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/barcode/$', consumers.BarcodeScannerConsumer.as_asgi()),
    re_path(r'ws/watch/$', consumers.WatchConsumer.as_asgi()),
    re_path(r'ws/chat/(?P<room_name>\w+)/$', consumers.ChatConsumer.as_asgi()),
]
# main/consumers.py
import cv2
from pyzbar.pyzbar import decode
import numpy as np
import base64
import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

# ==============================================================================
# 📷 Barcode Scanner Consumer
# ==============================================================================
class BarcodeScannerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.scanning = False
        await self.accept()
        print("✅ WebSocket connected for barcode scanning")

    async def disconnect(self, close_code):
        self.scanning = False
        print("🔌 WebSocket disconnected for barcode scanning")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'start_scan':
                self.scanning = True
                await self.start_scanning(data.get('image'))
            elif action == 'stop_scan':
                self.scanning = False
                await self.send(json.dumps({
                    'type': 'scan_stopped',
                    'message': 'تم إيقاف الماسح'
                }))
                
        except Exception as e:
            await self.send(json.dumps({
                'type': 'error',
                'error': str(e)
            }))

    async def start_scanning(self, image_data):
        try:
            # فك تشفير الصورة
            if 'base64,' in image_data:
                image_data = image_data.split('base64,')[1]
            
            image_bytes = base64.b64decode(image_data)
            import io
            from PIL import Image
            image = Image.open(io.BytesIO(image_bytes))
            
            # تحويل إلى numpy array
            frame = np.array(image)
            if len(frame.shape) == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # مسح الباركود
            results = []
            for code in decode(frame):
                data = code.data.decode('utf-8')
                code_type = code.type
                results.append({
                    'type': code_type,
                    'data': data
                })
            
            if results and self.scanning:
                await self.send(json.dumps({
                    'type': 'barcode_detected',
                    'results': results
                }))
                
        except Exception as e:
            await self.send(json.dumps({
                'type': 'error',
                'error': str(e)
            }))


# ==============================================================================
# ⌚ Watch Consumer (للساعة الذكية)
# ==============================================================================
class WatchConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'watch_group'
        
        # انضم إلى المجموعة
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        print("✅ Watch WebSocket connected")

    async def disconnect(self, close_code):
        # اخرج من المجموعة
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print("🔌 Watch WebSocket disconnected")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            print(f"📡 Watch data received: {data}")
            
            # إرسال البيانات لجميع العملاء في المجموعة
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'watch_data',
                    'data': data
                }
            )
        except Exception as e:
            print(f"Error: {e}")

    async def watch_data(self, event):
        # إرسال البيانات للعميل
        await self.send(text_data=json.dumps(event['data']))


# ==============================================================================
# 💬 Chat Consumer (للدردشة)
# ==============================================================================
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        # انضم إلى المجموعة
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"✅ Chat connected to room: {self.room_name}")

    async def disconnect(self, close_code):
        # اخرج من المجموعة
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"🔌 Chat disconnected from room: {self.room_name}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message', '')
            username = data.get('username', 'Anonymous')
            
            # إرسال الرسالة لجميع العملاء في المجموعة
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username,
                    'timestamp': data.get('timestamp')
                }
            )
        except Exception as e:
            print(f"Error: {e}")

    async def chat_message(self, event):
        # إرسال الرسالة للعميل
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'username': event['username'],
            'timestamp': event['timestamp']
        }))
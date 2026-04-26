# camera_server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
from pyzbar.pyzbar import decode
import numpy as np
import base64
from PIL import Image
import io
import requests
import json
import os

app = Flask(__name__)
CORS(app)

# ✅ استخدام PORT من متغيرات البيئة (Render يستخدم 10000)
PORT = int(os.environ.get('PORT', 10000))

# ✅ دالة للبحث عن المنتج في Open Food Facts
def get_product_info(barcode):
    """البحث عن معلومات المنتج باستخدام الباركود"""
    print(f"🔍 Searching for barcode: {barcode}")
    
    try:
        # البحث في Open Food Facts API
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=5, headers={'User-Agent': 'CameraService/1.0'})
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1:
                product = data['product']
                nutriments = product.get('nutriments', {})
                
                # استخراج البيانات المهمة
                product_name = product.get('product_name') or product.get('generic_name') or f"منتج {barcode[-8:]}"
                calories = nutriments.get('energy-kcal') or nutriments.get('energy') or 0
                protein = nutriments.get('proteins') or 0
                carbs = nutriments.get('carbohydrates') or 0
                fat = nutriments.get('fat') or 0
                
                # تحديد الوحدة
                quantity = product.get('quantity', '')
                unit = 'غرام'
                if 'ml' in quantity.lower():
                    unit = 'مل'
                elif 'g' in quantity.lower():
                    unit = 'غرام'
                
                print(f"✅ Product found: {product_name}")
                
                return {
                    'name': product_name,
                    'calories': round(float(calories), 1),
                    'protein': round(float(protein), 1),
                    'carbs': round(float(carbs), 1),
                    'fat': round(float(fat), 1),
                    'brand': product.get('brands', ''),
                    'unit': unit
                }
            else:
                print(f"⚠️ Product not found in Open Food Facts for barcode: {barcode}")
        else:
            print(f"⚠️ Open Food Facts API error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error fetching product info: {e}")
    
    # إذا لم يتم العثور على المنتج
    return {
        'name': f"منتج جديد ({barcode[-8:]})",
        'calories': 0,
        'protein': 0,
        'carbs': 0,
        'fat': 0,
        'brand': '',
        'unit': 'غرام'
    }

@app.route('/scan-barcode', methods=['POST'])
def scan_barcode():
    print("📸 Scan request received")
    
    try:
        data = request.json
        image_data = data.get('image', '')
        
        if not image_data:
            return jsonify({'success': False, 'message': 'No image data'}), 400
        
        # فك تشفير الصورة
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        frame = np.array(image)
        
        # تحويل الألوان إذا لزم الأمر
        if len(frame.shape) == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # مسح الباركود
        decoded_objects = decode(frame)
        
        if decoded_objects:
            results = []
            for obj in decoded_objects:
                barcode = obj.data.decode('utf-8')
                code_type = obj.type
                
                print(f"✅ Barcode detected: {barcode} ({code_type})")
                
                # ✅ البحث عن معلومات المنتج
                product_info = get_product_info(barcode)
                
                result = {
                    'type': code_type,
                    'data': barcode,
                    'name': product_info['name'],
                    'calories': product_info['calories'],
                    'protein': product_info['protein'],
                    'carbs': product_info['carbs'],
                    'fat': product_info['fat'],
                    'brand': product_info['brand'],
                    'unit': product_info['unit']
                }
                results.append(result)
                
                print(f"📦 Returning product: {result}")
            
            return jsonify({
                'success': True,
                'results': results
            })
        else:
            print("⚠️ No barcode found in image")
            return jsonify({
                'success': False,
                'message': 'No barcode found'
            })
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    print(f"🚀 Starting Camera Service on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
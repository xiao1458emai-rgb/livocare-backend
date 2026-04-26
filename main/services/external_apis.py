# main/services/external_apis.py
from django.conf import settings
import requests
import json


class APIConfig:
    """تكوين APIs الخارجية - جلب المفاتيح من settings.py"""
    
    # OpenWeather API
    WEATHER_API_KEY = getattr(settings, 'OPENWEATHER_API_KEY', '')
    WEATHER_BASE_URL = "http://api.openweathermap.org/data/2.5"
    
    # OpenFoodFacts - مجاني تماماً
    OPENFOODFACTS_ENABLED = getattr(settings, 'OPENFOODFACTS_ENABLED', True)
    OPENFOODFACTS_BASE_URL = "https://world.openfoodfacts.org"
    
    # RapidAPI
    RAPIDAPI_KEY = getattr(settings, 'RAPIDAPI_KEY', '')
    RAPIDAPI_HOST = "nutrition-tracker-api.p.rapidapi.com"
    
    # Google Maps
    GOOGLE_MAPS_KEY = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')

    @staticmethod
    def _get_language_text(ar_text, en_text, is_arabic=True):
        """اختيار النص حسب اللغة"""
        return ar_text if is_arabic else en_text

    @staticmethod
    def get_weather(city, language='ar'):
        """جلب بيانات الطقس من OpenWeather"""
        is_arabic = language == 'ar'
        
        try:
            if not APIConfig.WEATHER_API_KEY:
                return APIConfig._get_mock_weather(city, is_arabic)
            
            url = f"{APIConfig.WEATHER_BASE_URL}/weather"
            params = {
                'q': city,
                'appid': APIConfig.WEATHER_API_KEY,
                'units': 'metric',
                'lang': 'ar' if is_arabic else 'en'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # استخراج الإرشادات بناءً على الطقس
                temp = data['main']['temp']
                weather_main = data['weather'][0]['main']
                
                recommendation = ""
                if temp > 35:
                    recommendation = APIConfig._get_language_text(
                        "الجو حار جداً، اشرب الكثير من الماء وتجنب التعرض المباشر للشمس",
                        "Very hot weather, drink plenty of water and avoid direct sunlight",
                        is_arabic
                    )
                elif temp > 30:
                    recommendation = APIConfig._get_language_text(
                        "الجو حار، احرص على ترطيب جسمك",
                        "Hot weather, stay hydrated",
                        is_arabic
                    )
                elif temp < 10:
                    recommendation = APIConfig._get_language_text(
                        "الجو بارد، ارتد ملابس دافئة واحصل على قسط كاف من النوم",
                        "Cold weather, wear warm clothes and get enough sleep",
                        is_arabic
                    )
                elif 'rain' in weather_main.lower():
                    recommendation = APIConfig._get_language_text(
                        "الجو ممطر، احرص على أخذ مظلتك وارتداء ملابس مناسبة",
                        "Rainy weather, don't forget your umbrella and wear appropriate clothing",
                        is_arabic
                    )
                else:
                    recommendation = APIConfig._get_language_text(
                        "طقس معتدل، وقت مناسب للمشي والأنشطة الخارجية",
                        "Mild weather, good time for walking and outdoor activities",
                        is_arabic
                    )
                
                return {
                    'success': True,
                    'city': data['name'],
                    'temperature': round(temp),
                    'feels_like': round(data['main']['feels_like']),
                    'humidity': data['main']['humidity'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon'],
                    'wind_speed': data['wind']['speed'],
                    'recommendation': recommendation
                }
            else:
                return APIConfig._get_mock_weather(city, is_arabic)
                
        except Exception as e:
            print(f"Weather API error: {e}")
            return APIConfig._get_mock_weather(city, is_arabic)
    
    @staticmethod
    def _get_mock_weather(city, is_arabic=True):
        """بيانات تجريبية للطقس"""
        return {
            'success': True,
            'city': city,
            'temperature': 25,
            'feels_like': 24,
            'humidity': 60,
            'description': APIConfig._get_language_text('سماء صافية', 'Clear sky', is_arabic),
            'icon': '01d',
            'wind_speed': 3.5,
            'recommendation': APIConfig._get_language_text(
                'طقس معتدل، وقت مناسب للمشي والأنشطة الخارجية',
                'Mild weather, good time for walking and outdoor activities',
                is_arabic
            )
        }
    
    @staticmethod
    def search_food_openfoodfacts(query, language='ar'):
        """البحث عن الطعام باستخدام OpenFoodFacts API"""
        is_arabic = language == 'ar'
        
        try:
            url = f"{APIConfig.OPENFOODFACTS_BASE_URL}/cgi/search.pl"
            
            params = {
                'search_terms': query,
                'search_simple': 1,
                'action': 'process',
                'json': 1,
                'page_size': 8,
                'fields': 'product_name,nutriments,image_url,categories,code'
            }
            
            print(f"Searching OpenFoodFacts for: {query}")
            response = requests.get(url, params=params, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                products = data.get('products', [])
                
                results = []
                for product in products[:6]:
                    nutriments = product.get('nutriments', {})
                    
                    # استخراج القيم الغذائية
                    calories = nutriments.get('energy-kcal_100g') or nutriments.get('energy_100g', 0)
                    if calories and calories > 1000:
                        calories = calories / 4.184
                    
                    name = product.get('product_name', '')
                    if not name or name == '':
                        name = query
                    
                    image = product.get('image_url')
                    
                    results.append({
                        'name': name,
                        'calories': round(calories) if calories else 100,
                        'protein': round(nutriments.get('proteins_100g', 5), 1),
                        'carbs': round(nutriments.get('carbohydrates_100g', 10), 1),
                        'fat': round(nutriments.get('fat_100g', 3), 1),
                        'fiber': round(nutriments.get('fiber_100g', 1), 1),
                        'image': image
                    })
                
                print(f"Found {len(results)} results from OpenFoodFacts")
                return results
            
            print(f"OpenFoodFacts returned status code: {response.status_code}")
            return []
            
        except requests.exceptions.Timeout:
            print("OpenFoodFacts timeout after 25 seconds")
            return []
        except Exception as e:
            print(f"OpenFoodFacts error: {e}")
            return []
    
    @staticmethod
    def search_food_mock(query, language='ar'):
        """بيانات تجريبية - تستخدم كبديل إذا فشل API"""
        query_lower = query.lower()
        is_arabic = language == 'ar'
        
        # قائمة الأطعمة بالعربية
        mock_database_ar = {
            'رز': [
                {
                    'name': 'أرز أبيض مطبوخ',
                    'calories': 130,
                    'protein': 2.7,
                    'carbs': 28,
                    'fat': 0.3,
                    'fiber': 0.4,
                    'image': None
                },
                {
                    'name': 'أرز بسمتي',
                    'calories': 150,
                    'protein': 3.5,
                    'carbs': 32,
                    'fat': 0.5,
                    'fiber': 0.6,
                    'image': None
                }
            ],
            'تفاح': [
                {
                    'name': 'تفاح أحمر',
                    'calories': 52,
                    'protein': 0.3,
                    'carbs': 14,
                    'fat': 0.2,
                    'fiber': 2.4,
                    'image': None
                }
            ],
            'موز': [
                {
                    'name': 'موز',
                    'calories': 89,
                    'protein': 1.1,
                    'carbs': 23,
                    'fat': 0.3,
                    'fiber': 2.6,
                    'image': None
                }
            ],
            'دجاج': [
                {
                    'name': 'دجاج مشوي',
                    'calories': 165,
                    'protein': 31,
                    'carbs': 0,
                    'fat': 3.6,
                    'fiber': 0,
                    'image': None
                }
            ],
            'لحم': [
                {
                    'name': 'ستيك لحم',
                    'calories': 271,
                    'protein': 25,
                    'carbs': 0,
                    'fat': 19,
                    'fiber': 0,
                    'image': None
                }
            ],
            'خبز': [
                {
                    'name': 'خبز أبيض',
                    'calories': 265,
                    'protein': 9,
                    'carbs': 49,
                    'fat': 3.2,
                    'fiber': 2.7,
                    'image': None
                },
                {
                    'name': 'خبز أسمر',
                    'calories': 247,
                    'protein': 13,
                    'carbs': 41,
                    'fat': 4.2,
                    'fiber': 6.8,
                    'image': None
                }
            ],
            'بيض': [
                {
                    'name': 'بيض مسلوق',
                    'calories': 155,
                    'protein': 13,
                    'carbs': 1.1,
                    'fat': 11,
                    'fiber': 0,
                    'image': None
                }
            ],
            'لبن': [
                {
                    'name': 'لبن كامل الدسم',
                    'calories': 61,
                    'protein': 3.3,
                    'carbs': 4.8,
                    'fat': 3.3,
                    'fiber': 0,
                    'image': None
                }
            ],
            'زبادي': [
                {
                    'name': 'زبادي كامل الدسم',
                    'calories': 61,
                    'protein': 3.5,
                    'carbs': 4.7,
                    'fat': 3.3,
                    'fiber': 0,
                    'image': None
                }
            ]
        }
        
        # قائمة الأطعمة بالإنجليزية
        mock_database_en = {
            'rice': [
                {
                    'name': 'White Rice (cooked)',
                    'calories': 130,
                    'protein': 2.7,
                    'carbs': 28,
                    'fat': 0.3,
                    'fiber': 0.4,
                    'image': None
                },
                {
                    'name': 'Basmati Rice',
                    'calories': 150,
                    'protein': 3.5,
                    'carbs': 32,
                    'fat': 0.5,
                    'fiber': 0.6,
                    'image': None
                }
            ],
            'apple': [
                {
                    'name': 'Red Apple',
                    'calories': 52,
                    'protein': 0.3,
                    'carbs': 14,
                    'fat': 0.2,
                    'fiber': 2.4,
                    'image': None
                }
            ],
            'banana': [
                {
                    'name': 'Banana',
                    'calories': 89,
                    'protein': 1.1,
                    'carbs': 23,
                    'fat': 0.3,
                    'fiber': 2.6,
                    'image': None
                }
            ],
            'chicken': [
                {
                    'name': 'Grilled Chicken',
                    'calories': 165,
                    'protein': 31,
                    'carbs': 0,
                    'fat': 3.6,
                    'fiber': 0,
                    'image': None
                }
            ],
            'meat': [
                {
                    'name': 'Beef Steak',
                    'calories': 271,
                    'protein': 25,
                    'carbs': 0,
                    'fat': 19,
                    'fiber': 0,
                    'image': None
                }
            ],
            'bread': [
                {
                    'name': 'White Bread',
                    'calories': 265,
                    'protein': 9,
                    'carbs': 49,
                    'fat': 3.2,
                    'fiber': 2.7,
                    'image': None
                },
                {
                    'name': 'Whole Wheat Bread',
                    'calories': 247,
                    'protein': 13,
                    'carbs': 41,
                    'fat': 4.2,
                    'fiber': 6.8,
                    'image': None
                }
            ],
            'egg': [
                {
                    'name': 'Boiled Egg',
                    'calories': 155,
                    'protein': 13,
                    'carbs': 1.1,
                    'fat': 11,
                    'fiber': 0,
                    'image': None
                }
            ],
            'milk': [
                {
                    'name': 'Whole Milk',
                    'calories': 61,
                    'protein': 3.3,
                    'carbs': 4.8,
                    'fat': 3.3,
                    'fiber': 0,
                    'image': None
                }
            ],
            'yogurt': [
                {
                    'name': 'Whole Yogurt',
                    'calories': 61,
                    'protein': 3.5,
                    'carbs': 4.7,
                    'fat': 3.3,
                    'fiber': 0,
                    'image': None
                }
            ]
        }
        
        mock_database = mock_database_ar if is_arabic else mock_database_en
        
        for key in mock_database:
            if key in query_lower:
                return mock_database[key]
        
        # إذا لم يتم العثور على تطابق
        default_name = query if is_arabic else query
        return [
            {
                'name': default_name,
                'calories': 150,
                'protein': 8,
                'carbs': 20,
                'fat': 5,
                'fiber': 2,
                'image': None
            }
        ]


# ==============================================================================
# ✅ دالة مساعدة للاستخدام السريع
# ==============================================================================

def get_weather(city, language='ar'):
    """وظيفة مساعدة لجلب الطقس"""
    return APIConfig.get_weather(city, language)


def search_food(query, language='ar'):
    """وظيفة مساعدة للبحث عن الطعام"""
    # جرب API أولاً
    results = APIConfig.search_food_openfoodfacts(query, language)
    
    # إذا لم تكن هناك نتائج، استخدم البيانات التجريبية
    if not results:
        results = APIConfig.search_food_mock(query, language)
    
    return results
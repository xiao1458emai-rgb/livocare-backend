# main/services/nutrition_service.py
from .external_apis import APIConfig
import requests
import time

class NutritionService:
    """خدمة البحث عن المعلومات الغذائية"""
    
    def __init__(self):
        self.api_config = APIConfig()
    
    def search_food(self, query, language='ar'):
        """البحث عن الطعام مع دعم اللغة"""
        try:
            print(f"🔍 Searching for food: {query}")
            
            # ✅ حاول استخدام OpenFoodFacts أولاً
            if self.api_config.OPENFOODFACTS_ENABLED:
                print("⏳ Fetching from OpenFoodFacts...")
                
                start_time = time.time()
                results = self.api_config.search_food_openfoodfacts(query, language)
                elapsed = time.time() - start_time
                
                print(f"⏱️ OpenFoodFacts response time: {elapsed:.2f}s")
                
                if results and len(results) > 0:
                    print(f"✅ Found {len(results)} results from OpenFoodFacts")
                    return {
                        'success': True,
                        'source': 'openfoodfacts',
                        'data': results,
                        'count': len(results),
                        'query': query
                    }
                else:
                    print("⚠️ OpenFoodFacts returned no results, using mock data")
            
            # ✅ استخدم البيانات التجريبية (Mock Data)
            print("ℹ️ Using mock data")
            mock_results = self.api_config.search_food_mock(query, language)
            
            return {
                'success': True,
                'source': 'mock',
                'data': mock_results,
                'count': len(mock_results),
                'query': query
            }
            
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout searching for: {query}")
            return {
                'success': False,
                'error': 'Connection timeout',
                'data': self.api_config.search_food_mock(query, language),
                'count': 0
            }
            
        except requests.exceptions.ConnectionError:
            print(f"🔌 Connection error searching for: {query}")
            return {
                'success': False,
                'error': 'Connection error',
                'data': self.api_config.search_food_mock(query, language),
                'count': 0
            }
            
        except Exception as e:
            print(f"❌ NutritionService error: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': self.api_config.search_food_mock(query, language),
                'count': 0
            }
# main/services/nutrition_service.py
from .external_apis import APIConfig
import requests

class NutritionService:
    """خدمة البحث عن المعلومات الغذائية"""
    
    def __init__(self):
        self.api_config = APIConfig()
    
    def search_food(self, query):
        """البحث عن الطعام"""
        try:
            print(f"🔍 Searching for food: {query}")
            
            # حاول استخدام OpenFoodFacts
            if self.api_config.OPENFOODFACTS_ENABLED:
                print("⏳ Fetching from OpenFoodFacts...")
                results = self.api_config.search_food_openfoodfacts(query)
                
                if results and len(results) > 0:
                    print(f"✅ Found {len(results)} results from OpenFoodFacts")
                    return results
                else:
                    print("⚠️ OpenFoodFacts returned no results, using mock data")
            
            # استخدم البيانات التجريبية
            print("ℹ️ Using mock data")
            return self.api_config.search_food_mock(query)
            
        except Exception as e:
            print(f"❌ NutritionService error: {e}")
            return self.api_config.search_food_mock(query)
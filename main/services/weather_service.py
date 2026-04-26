# services/weather_service.py
import requests
from django.conf import settings

class WeatherService:
    def __init__(self):
        self.api_key = settings.OPENWEATHER_API_KEY
        self.base_url = "http://api.openweathermap.org/data/2.5"
    
    def get_weather(self, city="Cairo"):
        """جلب بيانات الطقس لمدينة معينة"""
        try:
            response = requests.get(
                f"{self.base_url}/weather",
                params={
                    'q': city,
                    'appid': self.api_key,
                    'units': 'metric',
                    'lang': 'ar'
                }
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'temperature': data['main']['temp'],
                    'feels_like': data['main']['feels_like'],
                    'humidity': data['main']['humidity'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon'],
                    'wind_speed': data['wind']['speed'],
                    'city': data['name']
                }
        except Exception as e:
            print(f"Error fetching weather: {e}")
        return None
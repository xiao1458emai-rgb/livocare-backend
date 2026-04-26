# main/services/ai_chat_service.py
from django.conf import settings
import requests
import json
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models

# ✅ استيراد النماذج من main.models (ليس من .models)
from main.models import (
    CustomUser,
    HealthStatus,
    MoodEntry,
    Sleep,
    PhysicalActivity,
    Meal,
    HabitLog,
    HabitDefinition
)

logger = logging.getLogger(__name__)


class LlamaService:
    def __init__(self):
        self.api_key = getattr(settings, 'GROQ_API_KEY', None)
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.api_model = "llama-3.1-8b-instant"
        self.local_url = "http://localhost:1234/v1/chat/completions"
        self.local_model = "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF"
        self.use_api = True
    
    def get_user_language(self, user, request=None):
        """استرجاع لغة المستخدم"""
        try:
            if hasattr(user, 'profile') and user.profile.language:
                return user.profile.language
        except:
            pass
        # افتراضياً العربية
        return 'ar'
    
    def get_chat_response(self, message, user, chat_history=[], request=None):
        """الحصول على رد من المساعد الذكي"""
        if not message or message.strip() == '':
            return self._get_empty_message_response(user)
        
        # تحديد لغة المستخدم
        user_lang = self.get_user_language(user, request)
        is_arabic = user_lang == 'ar'
        
        # جمع بيانات المستخدم
        user_data = self._collect_user_data(user)
        
        # بناء الـ prompt
        prompt = self._build_prompt(message, user, user_data, chat_history, is_arabic)
        
        # محاولة استخدام API
        if self.use_api and self.api_key:
            response = self._try_api(prompt)
            if response:
                return response
        
        # رد احتياطي
        return self._fallback_response(message, user_data, is_arabic)
    
    def _get_empty_message_response(self, user):
        """رد عندما تكون الرسالة فارغة"""
        is_arabic = self.get_user_language(user) == 'ar'
        if is_arabic:
            return "👋 مرحباً! كيف يمكنني مساعدتك اليوم؟ يمكنك سؤالي عن صحتك، وزنك، نومك، أو أي استفسار صحي."
        else:
            return "👋 Hello! How can I help you today? You can ask me about your health, weight, sleep, or any health inquiry."
    
    def _collect_user_data(self, user):
        """جمع بيانات المستخدم من قاعدة البيانات"""
        user_data = {
            'username': user.username,
            'weight': None,
            'blood_pressure': None,
            'glucose': None,
            'heart_rate': None,
            'spo2': None,
            'mood': None,
            'avg_sleep': None,
            'calories_today': 0,
            'activities_count': 0,
            'habits_completed': 0,
            'has_health_data': False,
            'has_sleep_data': False,
            'has_mood_data': False,
        }
        
        # آخر البيانات الصحية
        last_health = HealthStatus.objects.filter(user=user).order_by('-recorded_at').first()
        if last_health:
            user_data['weight'] = last_health.weight_kg
            if last_health.systolic_pressure and last_health.diastolic_pressure:
                user_data['blood_pressure'] = f"{last_health.systolic_pressure}/{last_health.diastolic_pressure}"
            user_data['glucose'] = last_health.blood_glucose
            user_data['heart_rate'] = last_health.heart_rate
            user_data['spo2'] = last_health.spo2
            user_data['has_health_data'] = True
        
        # آخر مزاج
        last_mood = MoodEntry.objects.filter(user=user).order_by('-entry_time').first()
        if last_mood:
            user_data['mood'] = last_mood.mood
            user_data['has_mood_data'] = True
        
        # متوسط النوم آخر 7 أيام
        week_ago = datetime.now() - timedelta(days=7)
        sleeps = Sleep.objects.filter(user=user, sleep_start__gte=week_ago)
        if sleeps.exists():
            total_sleep = 0
            count = 0
            for sleep in sleeps:
                if sleep.sleep_start and sleep.sleep_end:
                    duration = (sleep.sleep_end - sleep.sleep_start).seconds / 3600
                    if 0 < duration < 24:
                        total_sleep += duration
                        count += 1
            user_data['avg_sleep'] = round(total_sleep / count, 1) if count > 0 else None
            user_data['has_sleep_data'] = count > 0
        
        # سعرات اليوم
        today = datetime.now().date()
        today_meals = Meal.objects.filter(user=user, meal_time__date=today)
        user_data['calories_today'] = today_meals.aggregate(models.Sum('total_calories'))['total_calories__sum'] or 0
        
        # عدد الأنشطة هذا الأسبوع
        activities = PhysicalActivity.objects.filter(user=user, start_time__gte=week_ago)
        user_data['activities_count'] = activities.count()
        
        # عدد العادات المنجزة اليوم
        today_logs = HabitLog.objects.filter(habit__user=user, log_date=today, is_completed=True)
        user_data['habits_completed'] = today_logs.count()
        
        return user_data
    
    def _build_prompt(self, message, user, user_data, chat_history, is_arabic):
        """بناء الـ prompt"""
        if is_arabic:
            return f"""أنت مساعد صحي ذكي اسمك "LivoCare AI".

معلومات المستخدم {user.username}:
- الوزن: {user_data['weight'] or 'غير مسجل'} كجم
- ضغط الدم: {user_data['blood_pressure'] or 'غير مسجل'} mmHg
- السكر: {user_data['glucose'] or 'غير مسجل'} mg/dL
- نبضات القلب: {user_data['heart_rate'] or 'غير مسجل'} BPM
- الأكسجين: {user_data['spo2'] or 'غير مسجل'}%
- آخر مزاج: {user_data['mood'] or 'غير مسجل'}
- متوسط النوم: {user_data['avg_sleep'] or 'غير مسجل'} ساعات
- سعرات اليوم: {user_data['calories_today']} سعرة
- أنشطة هذا الأسبوع: {user_data['activities_count']}
- عادات منجزة اليوم: {user_data['habits_completed']}

المستخدم يقول: {message}

تعليمات:
1. استخدم معلومات المستخدم الحقيقية في ردودك
2. كن ودوداً ومشجعاً
3. قدم نصائح عملية
4. تحدث باللغة العربية الفصحى البسيطة

الرد:"""
        else:
            return f"""You are a smart health assistant named "LivoCare AI".

User {user.username} information:
- Weight: {user_data['weight'] or 'Not recorded'} kg
- Blood pressure: {user_data['blood_pressure'] or 'Not recorded'} mmHg
- Glucose: {user_data['glucose'] or 'Not recorded'} mg/dL
- Heart rate: {user_data['heart_rate'] or 'Not recorded'} BPM
- Oxygen level: {user_data['spo2'] or 'Not recorded'}%
- Last mood: {user_data['mood'] or 'Not recorded'}
- Average sleep: {user_data['avg_sleep'] or 'Not recorded'} hours
- Today's calories: {user_data['calories_today']}
- Activities this week: {user_data['activities_count']}
- Habits completed today: {user_data['habits_completed']}

User says: {message}

Instructions:
1. Use the user's real information in your responses
2. Be friendly and encouraging
3. Provide practical advice
4. Speak in simple, clear English

Response:"""
    
    def _try_api(self, prompt):
        """محاولة استخدام Groq API"""
        if not self.api_key:
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.api_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                print(f"API Error: {response.status_code}")
        except Exception as e:
            print(f"API error: {e}")
        
        return None
    
    def _fallback_response(self, message, user_data, is_arabic):
        """رد احتياطي عندما يفشل API"""
        message_lower = message.lower()
        
        if is_arabic:
            if 'وزن' in message_lower:
                if user_data.get('weight'):
                    return f"⚖️ وزنك الحالي هو {user_data['weight']} كجم. هل تريد نصائح للحفاظ عليه؟"
                return "⚖️ لم تسجل وزنك بعد. يمكنك إضافته في قسم الصحة الحيوية."
            
            if 'نوم' in message_lower or 'sleep' in message_lower:
                if user_data.get('avg_sleep'):
                    return f"🌙 متوسط نومك هو {user_data['avg_sleep']} ساعات. حاول النوم 7-8 ساعات يومياً لتحسين صحتك."
                return "🌙 لم تسجل أي نوم بعد. يمكنك تتبع نومك في قسم النوم."
            
            if 'مزاج' in message_lower or 'mood' in message_lower:
                if user_data.get('mood'):
                    return f"😊 آخر مزاج لك كان {user_data['mood']}. كيف تشعر اليوم؟"
                return "😊 لم تسجل أي مزاج بعد. كيف تشعر اليوم؟"
            
            return f"""👋 مرحباً {user_data['username']}! كيف يمكنني مساعدتك اليوم؟

💡 يمكنك سؤالي عن:
- وزنك الحالي
- نومك
- حالتك المزاجية
- نصائح صحية عامة

أنا هنا لمساعدتك في رحلتك الصحية! 😊"""
        
        else:
            if 'weight' in message_lower:
                if user_data.get('weight'):
                    return f"⚖️ Your current weight is {user_data['weight']} kg. Would you like tips to maintain it?"
                return "⚖️ You haven't recorded your weight yet. You can add it in the health section."
            
            if 'sleep' in message_lower:
                if user_data.get('avg_sleep'):
                    return f"🌙 Your average sleep is {user_data['avg_sleep']} hours. Try to sleep 7-8 hours daily for better health."
                return "🌙 You haven't recorded any sleep yet. You can track your sleep in the sleep section."
            
            if 'mood' in message_lower:
                if user_data.get('mood'):
                    return f"😊 Your last recorded mood was {user_data['mood']}. How are you feeling today?"
                return "😊 You haven't recorded any mood yet. How are you feeling today?"
            
            return f"""👋 Hello {user_data['username']}! How can I help you today?

💡 You can ask me about:
- Your current weight
- Your sleep
- Your mood
- General health tips

I'm here to help you on your health journey! 😊"""
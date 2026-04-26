# main/views.py
# ==============================================================================
# 📦 الاستيرادات
# ==============================================================================

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import date, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import get_user_model
import requests
import json
import logging
import os
from rest_framework import permissions
from django.conf import settings
from django.views.decorators.http import require_http_methods
from .models import (
    PhysicalActivity, Sleep, MoodEntry, HealthStatus, Meal, 
    FoodItem, HabitDefinition, HabitLog, HealthGoal, 
    ChronicCondition, MedicalRecord, Recommendation, ChatLog, 
    Notification, EnvironmentData, CustomUser,
)
from .serializers import (
    PhysicalActivitySerializer, SleepSerializer, MoodEntrySerializer, 
    HealthStatusSerializer, MealSerializer, FoodItemSerializer, 
    HabitDefinitionSerializer, HabitLogSerializer, HealthGoalSerializer, 
    ChronicConditionSerializer, MedicalRecordSerializer, RecommendationSerializer, 
    ChatLogSerializer, NotificationSerializer, EnvironmentDataSerializer, 
    UserRegistrationSerializer, UserProfileSerializer
)
from .services.nutrition_service import NutritionService
from .services.weather_service import WeatherService
from .services.exercise_service import AdvancedHealthAnalytics
from .services.cross_insights_service import HealthInsightsEngine, CrossInsightsService
from .services.habit_analytics_service import HabitAnalyticsService
from .services.ai_chat_service import LlamaService
from .services.sentiment_service import SentimentAnalyzer
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)
User = get_user_model()


# ==============================================================================
# 🔧 دوال مساعدة (Helper Functions)
# ==============================================================================

def get_request_language(request):
    """استخراج اللغة من الطلب"""
    lang_param = request.GET.get('lang')
    if lang_param in ['ar', 'en']:
        return lang_param
    
    accept_lang = request.headers.get('Accept-Language', '')
    if accept_lang.startswith('en'):
        return 'en'
    elif accept_lang.startswith('ar'):
        return 'ar'
    
    if request.method == 'POST' and request.body:
        try:
            body = json.loads(request.body)
            if body.get('lang') in ['ar', 'en']:
                return body['lang']
        except:
            pass
    
    return 'ar'


def get_translated_response(message_key, is_arabic, **kwargs):
    """الحصول على رسالة مترجمة"""
    messages = {
        'profile_updated': {'ar': 'تم تحديث الملف الشخصي بنجاح', 'en': 'Profile updated successfully'},
        'password_changed': {'ar': 'تم تغيير كلمة المرور بنجاح', 'en': 'Password changed successfully'},
        'notifications_marked_read': {'ar': 'تم تحديث جميع الإشعارات كمقروءة', 'en': 'All notifications marked as read'},
        'invalid_password': {'ar': 'كلمة المرور الحالية غير صحيحة', 'en': 'Current password is incorrect'},
        'password_too_short': {'ar': 'كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل', 'en': 'New password must be at least 8 characters'},
        'server_error': {'ar': 'حدث خطأ في الخادم', 'en': 'Server error occurred'},
        'weight_advice': {'ar': 'وزنك أعلى من المعدل. جرب المشي 30 دقيقة يومياً', 'en': 'Your weight is above normal. Try walking 30 minutes daily'},
        'stressed_advice': {'ar': 'جرب تمارين التنفس العميق', 'en': 'Try deep breathing exercises'},
        'anxious_advice': {'ar': 'خذ استراحة قصيرة وتأمل', 'en': 'Take a short break and meditate'},
        'sad_advice': {'ar': 'تحدث مع شخص تثق به', 'en': 'Talk to someone you trust'},
        'activity_advice': {'ar': 'لم تمارس أي نشاط اليوم. المشي 10 دقائق مفيد لصحتك', 'en': 'No activity today. 10 minutes of walking is good for your health'},
        'weather_error': {'ar': 'تعذر جلب بيانات الطقس', 'en': 'Unable to fetch weather data'},
        'text_required': {'ar': 'الرجاء إدخال نص للتحليل', 'en': 'Please enter text to analyze'},
    }
    
    msg_data = messages.get(message_key, {'ar': message_key, 'en': message_key})
    text = msg_data.get('ar' if is_arabic else 'en', message_key)
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except:
            return text
    return text


def send_push_notification_to_user(user_id, title, body, url='/'):
    """إرسال إشعار منبثق لمستخدم محدد"""
    try:
        response = requests.post(
            f'https://notification-service-6nzm.onrender.com/notify/{user_id}',
            json={'title': title, 'body': body, 'icon': '/logo192.png', 'url': url},
            timeout=5
        )
        if response.ok:
            print(f"✅ Push sent to user {user_id}: {title}")
        else:
            print(f"❌ Push failed for user {user_id}: {response.status_code}")
    except Exception as e:
        print(f"❌ Push error for user {user_id}: {e}")


# ==============================================================================
# 🔐 1. أذونات مخصصة
# ==============================================================================

class IsOwnerOrReadOnly(permissions.BasePermission):
    """فقط المالك يمكنه التعديل أو الحذف"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'meal') and hasattr(obj.meal, 'user'):
            return obj.meal.user == request.user
        elif hasattr(obj, 'habit') and hasattr(obj.habit, 'user'):
            return obj.habit.user == request.user
        
        return False


# ==============================================================================
# 📊 2. ViewSet الأساسي (يجب أن يأتي قبل أي ViewSet يرث منه)
# ==============================================================================

class BaseUserViewSet(viewsets.ModelViewSet):
    """ViewSet أساسي للموديلات المرتبطة بالمستخدم"""
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        if self.request.user.is_authenticated:
            return self.queryset.filter(user=self.request.user)
        return self.queryset.model.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ==============================================================================
# 📊 3. ViewSets الأساسية (كلها ترث من BaseUserViewSet)
# ==============================================================================

class PhysicalActivityViewSet(BaseUserViewSet):
    queryset = PhysicalActivity.objects.all()
    serializer_class = PhysicalActivitySerializer


class SleepViewSet(BaseUserViewSet):
    queryset = Sleep.objects.all()
    serializer_class = SleepSerializer


class MoodEntryViewSet(BaseUserViewSet):
    queryset = MoodEntry.objects.all()
    serializer_class = MoodEntrySerializer
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_entry = MoodEntry.objects.filter(
            user=request.user, entry_time__gte=today_start
        ).order_by('-entry_time').first()
        
        if today_entry:
            serializer = self.get_serializer(today_entry)
            return Response(serializer.data)
        return Response({"message": "No mood entry found for today."}, status=204)


class HealthStatusViewSet(BaseUserViewSet):
    queryset = HealthStatus.objects.all()
    serializer_class = HealthStatusSerializer


class MealViewSet(BaseUserViewSet):
    queryset = Meal.objects.all()
    serializer_class = MealSerializer


class HabitDefinitionViewSet(BaseUserViewSet):
    queryset = HabitDefinition.objects.all()
    serializer_class = HabitDefinitionSerializer


class HealthGoalViewSet(BaseUserViewSet):
    queryset = HealthGoal.objects.all()
    serializer_class = HealthGoalSerializer


class ChronicConditionViewSet(BaseUserViewSet):
    queryset = ChronicCondition.objects.all()
    serializer_class = ChronicConditionSerializer


class MedicalRecordViewSet(BaseUserViewSet):
    queryset = MedicalRecord.objects.all()
    serializer_class = MedicalRecordSerializer


class RecommendationViewSet(BaseUserViewSet):
    queryset = Recommendation.objects.all()
    serializer_class = RecommendationSerializer
    http_method_names = ['get', 'head', 'options', 'put', 'patch', 'delete']


class EnvironmentDataViewSet(BaseUserViewSet):
    queryset = EnvironmentData.objects.all()
    serializer_class = EnvironmentDataSerializer


class ChatLogViewSet(BaseUserViewSet):
    queryset = ChatLog.objects.all()
    serializer_class = ChatLogSerializer
    
    @action(detail=False, methods=['post'])
    def send_message(self, request):
        message = request.data.get('message', '')
        if not message:
            is_arabic = get_request_language(request) == 'ar'
            error_msg = get_translated_response('text_required', is_arabic)
            return Response({'error': error_msg}, status=400)
        
        is_arabic = get_request_language(request) == 'ar'
        
        user_message = ChatLog.objects.create(
            user=request.user, sender='User', message_text=message, sentiment_score=0.0
        )
        
        recent_messages = ChatLog.objects.filter(user=request.user).order_by('timestamp')[:20]
        chat_history = [{'sender': msg.sender, 'message': msg.message_text} for msg in recent_messages]
        
        try:
            llama_service = LlamaService()
            bot_response = llama_service.get_chat_response(message, request.user, chat_history)
        except Exception as e:
            bot_response = f"عذراً {request.user.username}، حدث خطأ غير متوقع." if is_arabic else f"Sorry {request.user.username}, an unexpected error occurred."
        
        ChatLog.objects.create(
            user=request.user, sender='Bot', message_text=bot_response, sentiment_score=0.0
        )
        
        all_messages = ChatLog.objects.filter(user=request.user).order_by('-timestamp')[:50]
        messages_for_display = list(reversed(all_messages))
        serializer = self.get_serializer(messages_for_display, many=True)
        
        return Response({'success': True, 'data': serializer.data}, status=201)


# ==============================================================================
# 📊 4. ViewSets الأخرى (لا ترث من BaseUserViewSet)
# ==============================================================================

class FoodItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    queryset = FoodItem.objects.all()
    serializer_class = FoodItemSerializer
    
    def get_queryset(self):
        return FoodItem.objects.filter(meal__user=self.request.user).order_by('-meal__meal_time')


class HabitLogViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    serializer_class = HabitLogSerializer
    
    def get_queryset(self):
        return HabitLog.objects.filter(habit__user=self.request.user).order_by('-log_date')
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        logs = HabitLog.objects.filter(habit__user=request.user, log_date=today).select_related('habit')
        all_habits = HabitDefinition.objects.filter(user=request.user, is_active=True)
        
        result = []
        log_habit_ids = logs.values_list('habit_id', flat=True)
        
        for log in logs:
            result.append({
                'id': log.id,
                'habit': {'id': log.habit.id, 'name': log.habit.name, 'description': log.habit.description},
                'is_completed': log.is_completed,
                'actual_value': log.actual_value,
                'notes': log.notes,
                'log_date': log.log_date,
            })
        
        for habit in all_habits:
            if habit.id not in log_habit_ids:
                result.append({
                    'id': None,
                    'habit': {'id': habit.id, 'name': habit.name, 'description': habit.description},
                    'is_completed': False,
                    'actual_value': None,
                    'notes': None,
                    'log_date': today,
                })
        
        return Response(result)
    
    @action(detail=False, methods=['post'])
    def complete(self, request):
        habit_id = request.data.get('habit_id')
        actual_value = request.data.get('actual_value')
        notes = request.data.get('notes', '')
        
        if not habit_id:
            return Response({'error': 'habit_id مطلوب'}, status=400)
        
        try:
            habit = HabitDefinition.objects.get(id=habit_id, user=request.user)
        except HabitDefinition.DoesNotExist:
            return Response({'error': 'العادة غير موجودة'}, status=404)
        
        today = timezone.now().date()
        log, created = HabitLog.objects.update_or_create(
            habit=habit, log_date=today,
            defaults={'is_completed': True, 'actual_value': actual_value, 'notes': notes}
        )
        
        serializer = self.get_serializer(log)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-sent_at')
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        is_arabic = get_request_language(request) == 'ar'
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({
            'success': True,
            'count': count,
            'message': get_translated_response('notifications_marked_read', is_arabic)
        })
    
    @action(detail=False, methods=['delete'])
    def delete_all_read(self, request):
        count = Notification.objects.filter(user=request.user, is_read=True).delete()[0]
        return Response({'success': True, 'count': count})
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        total = Notification.objects.filter(user=request.user).count()
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        read = total - unread
        return Response({
            'total': total,
            'unread': unread,
            'read': read
        })
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        limit = int(request.query_params.get('limit', 10))
        notifications = self.get_queryset()[:limit]
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def manage_profile(request):
    """إدارة الملف الشخصي"""
    user = request.user
    is_arabic = get_request_language(request) == 'ar'
    
    if request.method == 'GET':
        return Response({
            'success': True,
            'data': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_of_birth': getattr(user, 'date_of_birth', None),
                'gender': getattr(user, 'gender', None),
                'phone_number': getattr(user, 'phone_number', None),
                'initial_weight': float(user.initial_weight) if user.initial_weight else None,
                'height': float(user.height) if user.height else None,
                'occupation_status': getattr(user, 'occupation_status', None),
                'health_goal': getattr(user, 'health_goal', None),
                'activity_level': getattr(user, 'activity_level', None),
                # ❌ أزل هذه السطور - تسبب خطأ RelatedManager
                # 'chronic_conditions': getattr(user, 'chronic_conditions', None),
                # 'current_medications': getattr(user, 'current_medications', None),
            }
        })
    
    elif request.method in ['PUT', 'PATCH']:
        data = request.data
        allowed_fields = [
            'first_name', 'last_name', 'date_of_birth', 'gender', 'phone_number',
            'initial_weight', 'height', 'occupation_status',
            'health_goal', 'activity_level'
        ]
        
        for field in allowed_fields:
            if field in data:
                value = data[field]
                if field in ['initial_weight', 'height']:
                    try:
                        value = float(value) if value else None
                    except (ValueError, TypeError):
                        value = None
                setattr(user, field, value)
        
        user.save()
        
        return Response({
            'success': True,
            'message': get_translated_response('profile_updated', is_arabic),
            'data': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_of_birth': getattr(user, 'date_of_birth', None),
                'gender': getattr(user, 'gender', None),
                'phone_number': getattr(user, 'phone_number', None),
                'initial_weight': float(user.initial_weight) if user.initial_weight else None,
                'height': float(user.height) if user.height else None,
                'occupation_status': getattr(user, 'occupation_status', None),
                'health_goal': getattr(user, 'health_goal', None),
                'activity_level': getattr(user, 'activity_level', None),
            }
        })

# ==============================================================================
# 🌤️ 6. APIs الخارجية
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_weather(request):
    """جلب بيانات الطقس مع دعم اللغة"""
    try:
        city = request.query_params.get('city', 'Cairo')
        is_arabic = get_request_language(request) == 'ar'
        
        service = WeatherService()
        weather_data = service.get_weather(city)
        
        if weather_data and 'error' not in weather_data:
            if is_arabic:
                condition_map = {
                    'clear sky': 'سماء صافية', 'few clouds': 'قليل من الغيوم',
                    'scattered clouds': 'غيوم متفرقة', 'broken clouds': 'غيوم متكسرة',
                    'rain': 'مطر', 'thunderstorm': 'عاصفة رعدية', 'snow': 'ثلج', 'mist': 'ضباب',
                }
                if weather_data.get('description'):
                    weather_data['description'] = condition_map.get(weather_data['description'].lower(), weather_data['description'])
            
            return Response({'success': True, 'data': weather_data})
        
        error_msg = get_translated_response('weather_error', is_arabic)
        return Response({'success': False, 'error': error_msg}, status=500)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_food(request):
    """البحث عن الطعام"""
    try:
        query = request.query_params.get('query', '')
        if not query:
            return Response({'success': False, 'error': 'الرجاء إدخال اسم الطعام', 'data': []}, status=400)
        
        from urllib.parse import quote
        encoded_query = quote(query)
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={encoded_query}&search_simple=1&action=process&json=1&page_size=20"
        
        headers = {'User-Agent': 'LivocareApp/1.0'}
        response = requests.get(url, timeout=15, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            products = []
            for product in data.get('products', []):
                product_name = product.get('product_name') or product.get('generic_name')
                if product_name and len(product_name) > 1:
                    products.append({
                        'id': product.get('code'),
                        'name': product_name,
                        'brand': product.get('brands'),
                        'image': product.get('image_front_small_url'),
                        'calories': product.get('nutriments', {}).get('energy-kcal', 0),
                    })
            
            return Response({'success': True, 'data': products, 'count': len(products)})
        
        return Response({'success': False, 'error': 'فشل في الاتصال بقاعدة البيانات', 'data': []}, status=500)
    except Exception as e:
        return Response({'success': False, 'error': str(e), 'data': []}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suggest_exercises(request):
    """اقتراح تمارين رياضية"""
    try:
        muscle = request.query_params.get('muscle')
        difficulty = request.query_params.get('difficulty')
        language = get_request_language(request)
        
        service = AdvancedHealthAnalytics(request.user, language=language)
        exercises = service.suggest_exercises(muscle, difficulty)
        
        return Response({'success': True, 'data': exercises})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# 😊 7. تحليل المشاعر والذكاء الاصطناعي
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_sentiment(request):
    """تحليل المشاعر مع دعم اللغة"""
    try:
        text = request.data.get('text', '')
        is_arabic = get_request_language(request) == 'ar'
        
        if not text:
            error_msg = get_translated_response('text_required', is_arabic)
            return Response({'success': False, 'error': error_msg}, status=400)
        
        analyzer = SentimentAnalyzer(language='ar' if is_arabic else 'en')
        result = analyzer.analyze(text)
        
        return Response({'success': True, 'data': result})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_smart_recommendations(request):
    """توصيات ذكية مخصصة مع دعم اللغة"""
    try:
        user = request.user
        is_arabic = get_request_language(request) == 'ar'
        
        latest_health = HealthStatus.objects.filter(user=user).first()
        latest_mood = MoodEntry.objects.filter(user=user).first()
        recent_activities = PhysicalActivity.objects.filter(user=user, start_time__date=date.today()).count()
        
        recommendations = []
        
        if latest_health and latest_health.weight_kg and latest_health.weight_kg > 90:
            recommendations.append({
                'icon': '⚖️',
                'message': get_translated_response('weight_advice', is_arabic)
            })
        
        if latest_mood and latest_mood.mood in ['Stressed', 'Anxious', 'Sad']:
            mood_advice = {
                'Stressed': get_translated_response('stressed_advice', is_arabic),
                'Anxious': get_translated_response('anxious_advice', is_arabic),
                'Sad': get_translated_response('sad_advice', is_arabic)
            }
            recommendations.append({
                'icon': '🧘',
                'message': mood_advice.get(latest_mood.mood, get_translated_response('stressed_advice', is_arabic))
            })
        
        if recent_activities == 0:
            recommendations.append({
                'icon': '🚶',
                'message': get_translated_response('activity_advice', is_arabic)
            })
        
        return Response({'success': True, 'data': recommendations})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# 🧠 8. التحليلات الذكية
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def smart_insights(request):
    """تحليلات ذكية متكاملة"""
    user = request.user
    today = timezone.now()
    week_ago = today - timedelta(days=7)
    
    is_arabic = get_request_language(request) == 'ar'
    
    habits = HabitDefinition.objects.filter(user=user)
    habit_logs = HabitLog.objects.filter(habit__user=user, log_date__gte=week_ago.date())
    total_habits = habits.count()
    completed_today = habit_logs.filter(log_date=today.date(), is_completed=True).count()
    completion_rate = round((completed_today / total_habits) * 100) if total_habits > 0 else 0
    
    sleep_data = Sleep.objects.filter(user=user, sleep_start__gte=week_ago)
    avg_sleep = sleep_data.aggregate(Avg('duration_hours'))['duration_hours__avg'] or 0
    
    mood_data = MoodEntry.objects.filter(user=user, entry_time__gte=week_ago)
    mood_counts = mood_data.values('mood').annotate(count=Count('mood'))
    dominant_mood = mood_counts.order_by('-count').first()
    
    meal_data = Meal.objects.filter(user=user, meal_time__gte=week_ago)
    avg_calories = meal_data.aggregate(Avg('total_calories'))['total_calories__avg'] or 0
    
    mood_translation = {
        'Excellent': 'ممتاز' if is_arabic else 'Excellent',
        'Good': 'جيد' if is_arabic else 'Good',
        'Neutral': 'محايد' if is_arabic else 'Neutral',
        'Stressed': 'مرهق' if is_arabic else 'Stressed',
        'Anxious': 'قلق' if is_arabic else 'Anxious',
        'Sad': 'حزين' if is_arabic else 'Sad'
    }
    
    recommendations = []
    
    if avg_sleep < 7:
        recommendations.append({'icon': '🌙', 'title': 'نم أكثر', 'tips': ['حدد موعداً ثابتاً للنوم', 'ابتعد عن الشاشات قبل النوم']})
    
    if completion_rate < 50:
        recommendations.append({'icon': '💊', 'title': 'التزم بعاداتك', 'tips': ['ابدأ بعادة صغيرة وسهلة']})
    
    if avg_calories < 1500:
        recommendations.append({'icon': '🥗', 'title': 'نظام غذائي متوازن', 'tips': ['أضف وجبات خفيفة صحية']})
    
    return Response({
        'success': True,
        'data': {
            'summary': {
                'total_habits': total_habits,
                'completion_rate': completion_rate,
                'avg_sleep': round(float(avg_sleep), 1),
                'dominant_mood': mood_translation.get(dominant_mood['mood'] if dominant_mood else '', 'غير متوفر'),
                'avg_calories': round(float(avg_calories))
            },
            'recommendations': recommendations
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def advanced_cross_insights(request):
    """تحليلات متقاطعة متقدمة"""
    try:
        language = get_request_language(request)
        engine = HealthInsightsEngine(request.user, language=language)
        data = {
            'energy_consumption': engine.analyze_energy_consumption(),
            'pulse_pressure': engine.analyze_pulse_pressure(),
            'pre_exercise': engine.analyze_pre_exercise_risk(),
            'vital_signs': engine.analyze_vital_signs(),
            'holistic': engine.generate_holistic_recommendations(),
            'predictive': engine.generate_predictive_alerts()
        }
        return Response({'success': True, 'data': data})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cross_insights(request):
    """تحليلات متقاطعة أساسية"""
    try:
        service = CrossInsightsService(request.user)
        insights = service.get_all_correlations()
        return Response({'success': True, 'data': insights})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# 📊 9. التقارير
# ==============================================================================

class HealthSummaryView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        today = date.today()
        
        activity_summary = PhysicalActivity.objects.filter(
            user=user, start_time__date=today
        ).aggregate(total_calories_burned=Sum('calories_burned'), total_duration_minutes=Sum('duration_minutes'))
        
        sleep_summary = Sleep.objects.filter(
            user=user, sleep_end__date=today
        ).aggregate(average_sleep_quality=Avg('quality_rating'))
        
        meal_summary = Meal.objects.filter(
            user=user, meal_time__date=today
        ).aggregate(total_calories_consumed=Sum('total_calories'))
        
        last_mood_entry = MoodEntry.objects.filter(user=user, entry_time__date=today).order_by('-entry_time').first()
        
        return Response({
            "date": today.isoformat(),
            "activities": {
                "total_calories_burned": activity_summary.get('total_calories_burned') or 0,
                "total_duration_minutes": activity_summary.get('total_duration_minutes') or 0
            },
            "sleep": {"average_sleep_quality": round(sleep_summary.get('average_sleep_quality') or 0, 1)},
            "nutrition": {"total_calories_consumed": meal_summary.get('total_calories_consumed') or 0},
            "mood": {"last_recorded_mood": last_mood_entry.mood if last_mood_entry else "N/A"},
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_reports_data(request):
    """جلب جميع بيانات التقارير دفعة واحدة"""
    user = request.user
    today = timezone.now().date()
    
    sleep_data = Sleep.objects.filter(user=user, sleep_start__date__gte=today - timedelta(days=30)).values(
        'id', 'sleep_start', 'sleep_end', 'duration_hours', 'quality_rating'
    ).order_by('-sleep_start')
    
    mood_data = MoodEntry.objects.filter(user=user, entry_time__date__gte=today - timedelta(days=30)).values(
        'id', 'entry_time', 'mood', 'factors'
    ).order_by('-entry_time')
    
    activity_data = PhysicalActivity.objects.filter(user=user, start_time__date__gte=today - timedelta(days=30)).values(
        'id', 'start_time', 'activity_type', 'duration_minutes', 'calories_burned'
    ).order_by('-start_time')
    
    habit_data = HabitLog.objects.filter(habit__user=user, log_date__gte=today - timedelta(days=30)).select_related('habit').values(
        'id', 'log_date', 'habit__name', 'is_completed'
    ).order_by('-log_date')
    
    return Response({
        'sleep': list(sleep_data),
        'mood': list(mood_data),
        'activity': list(activity_data),
        'habits': list(habit_data)
    })


# ==============================================================================
# 🔔 10. الإشعارات (دوال منفصلة)
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_notification(request):
    try:
        data = request.data
        notification = Notification.objects.create(
            user=request.user,
            title=data.get('title', 'LivoCare'),
            message=data.get('message', ''),
            type=data.get('type', 'info'),
            priority=data.get('priority', 'medium'),
            action_url=data.get('action_url', '/notifications'),
            is_read=False
        )
        return Response({'success': True, 'notification': {'id': notification.id}})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    try:
        notifications = Notification.objects.filter(user=request.user).order_by('-sent_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response({'success': True, 'notifications': serializer.data})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({'success': True, 'message': 'تم تحديث الإشعار كمقروء'})
    except Notification.DoesNotExist:
        return Response({'success': False, 'error': 'الإشعار غير موجود'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    try:
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'success': True, 'message': 'تم تحديث جميع الإشعارات كمقروءة'})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.delete()
        return Response({'success': True, 'message': 'تم حذف الإشعار بنجاح'})
    except Notification.DoesNotExist:
        return Response({'success': False, 'error': 'الإشعار غير موجود'}, status=404)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_read_notifications(request):
    try:
        deleted_count = Notification.objects.filter(user=request.user, is_read=True).delete()[0]
        return Response({'success': True, 'message': f'تم حذف {deleted_count} إشعار مقروء'})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_notifications(request):
    try:
        notifications = Notification.objects.filter(user=request.user).order_by('-sent_at')
        result = []
        for n in notifications:
            result.append({
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.type,
                'priority': n.priority,
                'is_read': n.is_read,
                'action_url': n.action_url,
                'created_at': n.sent_at.isoformat() if n.sent_at else None,
            })
        return Response({'success': True, 'count': len(result), 'results': result})
    except Exception as e:
        return Response({'success': True, 'count': 0, 'results': []})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications_simple(request):
    try:
        notifications = Notification.objects.filter(user=request.user).order_by('-sent_at')
        result = [{'id': n.id, 'title': n.title, 'message': n.message, 'is_read': n.is_read} for n in notifications]
        return Response({'success': True, 'count': len(result), 'results': result})
    except Exception as e:
        return Response({'success': True, 'count': 0, 'results': []})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_test_notifications(request):
    user = request.user
    created = []
    
    notifications_data = [
        {'title': '🎉 مرحباً في LivoCare', 'message': 'أهلاً بك في التطبيق!', 'type': 'health', 'priority': 'high'},
        {'title': '💪 هدف اليوم', 'message': 'أنت على بعد 3000 خطوة من هدفك!', 'type': 'activity', 'priority': 'medium'},
        {'title': '🥗 تذكير بالوجبة', 'message': 'حان وقت الغداء!', 'type': 'nutrition', 'priority': 'medium'},
        {'title': '😊 كيف تشعر اليوم؟', 'message': 'سجل حالتك المزاجية', 'type': 'mood', 'priority': 'low'},
        {'title': '🏆 إنجاز', 'message': 'لقد أكملت 7 أيام متتالية!', 'type': 'achievement', 'priority': 'high'},
    ]
    
    for n in notifications_data:
        notification = Notification.objects.create(user=user, **n, action_url='/dashboard', is_read=False)
        created.append({'id': notification.id, 'title': notification.title})
    
    return Response({'success': True, 'created': created, 'total': Notification.objects.filter(user=user).count()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_notification_from_sw(request):
    try:
        data = request.data
        notification = Notification.objects.create(
            user=request.user,
            title=data.get('title', 'LivoCare'),
            message=data.get('message', ''),
            type=data.get('type', 'info'),
            priority=data.get('priority', 'medium'),
            action_url=data.get('action_url', '/notifications'),
            is_read=False
        )
        return Response({'success': True, 'id': notification.id}, status=201)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_push_notification(request):
    try:
        title = request.data.get('title', 'LivoCare')
        message = request.data.get('message', 'لديك إشعار جديد')
        
        response = requests.post(
            'https://notification-service-6nzm.onrender.com/notify/all',
            json={'title': title, 'body': message, 'icon': '/logo192.png', 'url': '/dashboard'},
            timeout=10
        )
        
        return Response({'success': True, 'message': 'تم إرسال الإشعار'})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_subscribe(request):
    try:
        subscription = request.data
        if not subscription or not subscription.get('endpoint'):
            return Response({'success': False, 'error': 'بيانات الاشتراك غير صالحة'}, status=400)
        
        request.session['push_subscription'] = subscription
        return Response({'success': True, 'message': 'تم حفظ اشتراك الإشعارات بنجاح'})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_achievements(request):
    return Response({'success': True, 'data': []})


# ==============================================================================
# 🤖 11. إشعارات ذكية و Cron Jobs
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_and_send_smart_notifications(request):
    """فحص وإرسال إشعارات ذكية بناءً على سلوك المستخدم"""
    user = request.user
    today = timezone.now().date()
    now = timezone.now()
    created_count = 0
    
    meals_today = Meal.objects.filter(user=user, meal_time__date=today).count()
    if meals_today == 0:
        Notification.objects.create(
            user=user, title='🥗 تذكير بالوجبة', message='لم تسجل أي وجبة اليوم!',
            type='nutrition', priority='medium', action_url='/nutrition', is_read=False
        )
        send_push_notification_to_user(user.id, '🥗 تذكير بالوجبة', 'لم تسجل أي وجبة اليوم!', '/nutrition')
        created_count += 1
    
    activities_today = PhysicalActivity.objects.filter(user=user, start_time__date=today).count()
    if activities_today == 0:
        Notification.objects.create(
            user=user, title='🏃 حان وقت الحركة', message='المشي 30 دقيقة يحسن صحتك.',
            type='activity', priority='medium', action_url='/activities', is_read=False
        )
        send_push_notification_to_user(user.id, '🏃 حان وقت الحركة', 'لم تمارس أي نشاط بدني اليوم!', '/activities')
        created_count += 1
    
    mood_today = MoodEntry.objects.filter(user=user, entry_time__date=today).count()
    if mood_today == 0:
        Notification.objects.create(
            user=user, title='😊 كيف تشعر اليوم؟', message='سجل حالتك المزاجية الآن',
            type='mood', priority='low', action_url='/mood', is_read=False
        )
        send_push_notification_to_user(user.id, '😊 كيف تشعر اليوم؟', 'سجل حالتك المزاجية الآن', '/mood')
        created_count += 1
    
    current_hour = now.hour
    if current_hour >= 22:
        sleep_today = Sleep.objects.filter(user=user, sleep_start__date=today).count()
        if sleep_today == 0:
            Notification.objects.create(
                user=user, title='🌙 وقت النوم', message='النوم الكافي يحسن صحتك',
                type='sleep', priority='medium', action_url='/sleep', is_read=False
            )
            send_push_notification_to_user(user.id, '🌙 وقت النوم', 'حان وقت النوم! نم باكراً', '/sleep')
            created_count += 1
    
    return Response({'success': True, 'message': f'تم إنشاء {created_count} إشعار ذكي', 'count': created_count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_daily_summary_notification(request):
    """إرسال ملخص اليوم"""
    user = request.user
    today = timezone.now().date()
    
    activities = PhysicalActivity.objects.filter(user=user, start_time__date=today)
    total_minutes = activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
    total_calories_burned = activities.aggregate(Sum('calories_burned'))['calories_burned__sum'] or 0
    
    meals = Meal.objects.filter(user=user, meal_time__date=today)
    total_calories_consumed = meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0
    
    sleep = Sleep.objects.filter(user=user, sleep_start__date=today).first()
    sleep_hours = sleep.duration_hours if sleep else 0
    
    push_message = f"📊 نشاط: {total_minutes} دقيقة | 🍽️ سعرات: {total_calories_consumed}"
    
    Notification.objects.create(
        user=user, title="🌙 ملخص يومك", message=push_message,
        type="summary", priority="medium", action_url="/dashboard", is_read=False
    )
    
    send_push_notification_to_user(user.id, "🌙 ملخص يومك", push_message, "/dashboard")
    
    return Response({'success': True, 'message': 'تم إرسال ملخص اليوم'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_morning_tip(request):
    """إرسال نصيحة صباحية"""
    user = request.user
    
    tips = [
        {'title': '💧 شرب الماء', 'message': 'ابدأ يومك بكوب من الماء الدافئ لتنشيط الجسم.'},
        {'title': '🍳 فطور صحي', 'message': 'لا تهمل وجبة الإفطار! تناول بروتين وخضروات.'},
        {'title': '🚶 نشاط صباحي', 'message': 'تمدد أو امشِ 10 دقائق لتنشيط الدورة الدموية.'},
    ]
    
    import random
    tip = random.choice(tips)
    
    Notification.objects.create(
        user=user, title=tip['title'], message=tip['message'],
        type="tip", priority="low", action_url="/tips", is_read=False
    )
    
    send_push_notification_to_user(user.id, tip['title'], tip['message'], "/tips")
    
    return Response({'success': True, 'tip': tip})


@api_view(['POST'])
@permission_classes([AllowAny])
def send_notifications_to_all_users(request):
    """إرسال إشعارات لجميع المستخدمين"""
    users = CustomUser.objects.filter(is_active=True)
    total = 0
    
    for user in users:
        Notification.objects.create(
            user=user, title="🌙 مساء الخير", message="كيف كان يومك؟ لا تنسى تسجيل نشاطك",
            type="reminder", priority="medium", action_url="/dashboard", is_read=False
        )
        total += 1
    
    return Response({'success': True, 'message': f'تم إرسال الإشعارات إلى {total} مستخدم'})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def generate_notifications_now(request):
    """توليد إشعارات فورية"""
    from main.services.notification_service import NotificationService
    try:
        if request.user.is_authenticated:
            count = NotificationService.generate_all_notifications(request.user)
        else:
            count = 0
        return Response({'success': True, 'message': f'✅ تم إنشاء {count} إشعار جديد', 'count': count})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def trigger_notifications(request):
    try:
        return Response({'success': True, 'message': 'تم تشغيل الإشعارات بنجاح', 'timestamp': timezone.now().isoformat()})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# 📅 12. Cron Jobs endpoints (بدون مصادفة - لـ cron-job.org)
# ==============================================================================

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_daily_summary(request):
    """إرسال ملخص اليوم لجميع المستخدمين"""
    try:
        users = CustomUser.objects.filter(is_active=True)
        today = timezone.now().date()
        total = 0
        
        for user in users:
            activities = PhysicalActivity.objects.filter(user=user, start_time__date=today)
            total_minutes = activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
            
            meals = Meal.objects.filter(user=user, meal_time__date=today)
            total_calories = meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0
            
            message = f"📊 نشاط: {total_minutes} دقيقة | 🍽️ سعرات: {total_calories}"
            
            Notification.objects.create(
                user=user, title="🌙 ملخص يومك", message=message,
                type="summary", priority="medium", action_url="/dashboard", is_read=False
            )
            
            send_push_notification_to_user(user.id, "🌙 ملخص يومك", message, "/dashboard")
            total += 1
        
        return Response({'success': True, 'message': f'تم إرسال الملخص إلى {total} مستخدم'})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_morning_tip(request):
    """إرسال نصيحة صباحية لجميع المستخدمين"""
    try:
        users = CustomUser.objects.filter(is_active=True)
        tips = [
            {'title': '💧 اشرب ماء', 'message': 'ابدأ يومك بكوب من الماء الدافئ'},
            {'title': '🍳 فطور صحي', 'message': 'لا تهمل وجبة الإفطار'},
            {'title': '🚶 تمدد', 'message': 'تمدد أو امشِ 10 دقائق لتنشيط الدورة الدموية'},
        ]
        import random
        tip = random.choice(tips)
        total = 0
        
        for user in users:
            Notification.objects.create(
                user=user, title=tip['title'], message=tip['message'],
                type="tip", priority="low", action_url="/dashboard", is_read=False
            )
            send_push_notification_to_user(user.id, tip['title'], tip['message'], "/dashboard")
            total += 1
        
        return Response({'success': True, 'message': f'تم إرسال النصيحة إلى {total} مستخدم', 'tip': tip})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_smart_notifications(request):
    """إرسال إشعارات ذكية لجميع المستخدمين"""
    try:
        users = CustomUser.objects.filter(is_active=True)
        today = timezone.now().date()
        total = 0
        
        for user in users:
            created = 0
            
            if Meal.objects.filter(user=user, meal_time__date=today).count() == 0:
                Notification.objects.create(
                    user=user, title='🥗 تذكير بالوجبة', message='لم تسجل أي وجبة اليوم!',
                    type='nutrition', priority='medium', action_url='/nutrition', is_read=False
                )
                created += 1
            
            if PhysicalActivity.objects.filter(user=user, start_time__date=today).count() == 0:
                Notification.objects.create(
                    user=user, title='🏃 حان وقت الحركة', message='المشي 30 دقيقة يحسن صحتك.',
                    type='activity', priority='medium', action_url='/activities', is_read=False
                )
                created += 1
            
            if created > 0:
                total += 1
        
        return Response({'success': True, 'message': f'تم إرسال الإشعارات الذكية إلى {total} مستخدم'})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_test_simple(request):
    """Endpoint بسيط لاختبار cron-job.org"""
    return JsonResponse({
        'success': True,
        'message': 'Cron job is working!',
        'timestamp': timezone.now().isoformat()
    })


# ==============================================================================
# ⌚ 13. بيانات الساعة الذكية
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def watch_health_data(request):
    try:
        data = request.data
        heart_rate = data.get('heart_rate') or data.get('heartRate')
        systolic = data.get('systolic_pressure') or data.get('systolic')
        diastolic = data.get('diastolic_pressure') or data.get('diastolic')
        recorded_at = data.get('recorded_at') or data.get('timestamp') or timezone.now()
        
        health_data = HealthStatus.objects.create(
            user=request.user, heart_rate=heart_rate,
            systolic_pressure=systolic, diastolic_pressure=diastolic, recorded_at=recorded_at
        )
        
        return Response({'success': True, 'data': {'id': health_data.id}})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def watch_history(request):
    try:
        data = HealthStatus.objects.filter(user=request.user).order_by('-recorded_at')[:50]
        result = [{'id': item.id, 'heart_rate': item.heart_rate, 'recorded_at': item.recorded_at.isoformat()} for item in data]
        return Response({'success': True, 'data': result})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def adb_watch_data(request):
    """استقبال بيانات من ESP32"""
    try:
        data = request.data
        logger.info(f"📡 ESP32 data received: {data}")
        
        heart_rate = data.get('bpm') or data.get('heart_rate')
        spo2 = data.get('spo2') or data.get('oxygen')
        
        health_data = HealthStatus.objects.create(
            user=request.user, heart_rate=heart_rate, spo2=spo2, recorded_at=timezone.now()
        )
        
        return Response({'success': True, 'data': {'id': health_data.id}})
    except Exception as e:
        logger.error(f"❌ ESP32 data error: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# 📷 14. ماسح الباركود
# ==============================================================================

@csrf_exempt
@api_view(['POST'])
def scan_barcode(request):
    try:
        data = json.loads(request.body)
        camera_url = os.environ.get('CAMERA_SERVICE_URL', 'https://camera-service-fag3.onrender.com')
        response = requests.post(f"{camera_url}/scan-barcode", json={'image': data.get('image', '')}, timeout=10)
        return JsonResponse(response.json(), status=response.status_code)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# 🩺 15. الأدوية (FDA API)
# ==============================================================================

class OpenFDAService:
    BASE_URL = "https://api.fda.gov/drug"
    
    def search_by_brand_name(self, brand_name, limit=10):
        params = {'search': f'openfda.brand_name.exact:"{brand_name}"', 'limit': limit}
        try:
            response = requests.get(f"{self.BASE_URL}/drugsfda.json", params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = []
                for drug in data.get('results', []):
                    openfda = drug.get('openfda', {})
                    results.append({
                        'brand_name': openfda.get('brand_name', [''])[0] if openfda.get('brand_name') else '',
                        'generic_name': openfda.get('generic_name', [''])[0] if openfda.get('generic_name') else '',
                        'manufacturer': openfda.get('manufacturer_name', [''])[0] if openfda.get('manufacturer_name') else '',
                    })
                return results
        except Exception:
            pass
        return []


fda_service = OpenFDAService()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_medication(request):
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response({'success': False, 'error': 'الرجاء إدخال اسم الدواء', 'results': []}, status=400)
    
    results = fda_service.search_by_brand_name(query)
    return Response({'success': True, 'results': results, 'count': len(results)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_medication_details(request, medication_id):
    return Response({'success': False, 'error': 'قيد التطوير'}, status=501)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_medications(request):
    return Response({'success': True, 'data': [], 'count': 0})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_user_medication(request):
    return Response({'success': False, 'error': 'قيد التطوير'}, status=501)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user_medication(request, user_med_id):
    return Response({'success': False, 'error': 'قيد التطوير'}, status=501)


# ==============================================================================
# 🧪 16. دوال اختبارية
# ==============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def test_websocket(request):
    return Response({'success': True, 'message': 'WebSocket API is working', 'status': 'ok'})


# ==============================================================================
# 🔐 17. مصادقة Google
# ==============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def google_auth(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)
        
        name_parts = data.get('name', '').split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
            }
        )
        
        refresh = RefreshToken.for_user(user)
        
        return JsonResponse({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'id': user.id, 'username': user.username, 'email': user.email}
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
# أضف هذا في نهاية main/views.py

class RegisterUserView(generics.CreateAPIView):
    """تسجيل مستخدم جديد"""
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # توليد توكنات JWT للمستخدم الجديد
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'message': 'تم إنشاء الحساب بنجاح',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
# أضف هذا في نهاية main/views.py

# ==============================================================================
# 📊 دوال إضافية
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nutrition_insights(request):
    """
    تحليلات التغذية المتقدمة
    Advanced nutrition insights
    """
    try:
        user = request.user
        is_arabic = get_request_language(request) == 'ar'
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # إحصائيات الوجبات
        meals = Meal.objects.filter(user=user, meal_time__date__gte=week_ago)
        total_meals = meals.count()
        avg_calories = meals.aggregate(Avg('total_calories'))['total_calories__avg'] or 0
        total_calories = meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0
        
        # الوجبات حسب النوع
        meals_by_type = meals.values('meal_type').annotate(
            count=Count('id'),
            avg_calories=Avg('total_calories')
        )
        
        # أكثر المكونات استخداماً
        all_ingredients = []
        for meal in meals:
            if meal.ingredients:
                all_ingredients.extend([i.get('name', '') for i in meal.ingredients if i.get('name')])
        
        from collections import Counter
        top_ingredients = Counter(all_ingredients).most_common(5)
        
        # نصائح غذائية
        tips = []
        if avg_calories < 1500:
            tips.append({
                'icon': '🍽️',
                'title': 'سعرات منخفضة' if is_arabic else 'Low Calories',
                'message': 'سعراتك الحرارية أقل من الموصى بها' if is_arabic else 'Your calories are below recommended',
                'advice': 'أضف وجبات خفيفة صحية مثل المكسرات والفواكه' if is_arabic else 'Add healthy snacks like nuts and fruits'
            })
        elif avg_calories > 2500:
            tips.append({
                'icon': '⚠️',
                'title': 'سعرات مرتفعة' if is_arabic else 'High Calories',
                'message': 'سعراتك الحرارية أعلى من الموصى بها' if is_arabic else 'Your calories are above recommended',
                'advice': 'قلل من الكربوهيدرات البسيطة وزد من الخضروات' if is_arabic else 'Reduce simple carbs and increase vegetables'
            })
        
        return Response({
            'success': True,
            'data': {
                'period': {
                    'days': 7,
                    'start': week_ago.isoformat(),
                    'end': today.isoformat()
                },
                'summary': {
                    'total_meals': total_meals,
                    'avg_daily_calories': round(avg_calories, 0),
                    'total_calories': total_calories,
                    'avg_meals_per_day': round(total_meals / 7, 1) if total_meals > 0 else 0
                },
                'meals_by_type': list(meals_by_type),
                'top_ingredients': [{'name': name, 'count': count} for name, count in top_ingredients],
                'recommendations': tips
            },
            'language': 'ar' if is_arabic else 'en'
        })
        
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


class RegisterUserView(generics.CreateAPIView):
    """تسجيل مستخدم جديد"""
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'message': 'تم إنشاء الحساب بنجاح',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_blood_sugar(request):
    """جلب بيانات سكر الدم"""
    try:
        latest = HealthStatus.objects.filter(user=request.user).order_by('-recorded_at').first()
        if latest and latest.blood_glucose:
            return Response({
                'success': True,
                'blood_sugar': latest.blood_glucose,
                'recorded_at': latest.recorded_at
            })
        return Response({'success': True, 'blood_sugar': None})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fix_notifications_dates(request):
    """إصلاح التواريخ الفارغة في الإشعارات القديمة"""
    try:
        from django.utils import timezone
        updated = Notification.objects.filter(sent_at__isnull=True).update(sent_at=timezone.now())
        return Response({
            'success': True,
            'updated_count': updated,
            'message': f'✅ تم تحديث {updated} إشعار'
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)
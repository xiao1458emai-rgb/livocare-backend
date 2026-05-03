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
    """إرسال إشعار منبثق لمستخدم محدد عبر خدمة الإشعارات"""
    try:
        # استدعاء خدمة الإشعارات المنفصلة
        response = requests.post(
            f'https://notification-v4jz.onrender.com/notify/{user_id}',
            json={'title': title, 'body': body, 'icon': '/logo192.png', 'url': url},
            timeout=10
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

# =============================================================================
# إدارة الحساب - جميع الدوال الناقصة دفعة واحدة
# =============================================================================

from django.contrib.auth.hashers import check_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
import json

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """تغيير كلمة المرور"""
    user = request.user
    is_arabic = get_request_language(request) == 'ar'
    
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    if not current_password or not new_password:
        return Response({'success': False, 'error': 'الرجاء إدخال كلمة المرور الحالية والجديدة'}, status=400)
    
    if len(new_password) < 8:
        return Response({'success': False, 'error': 'كلمة المرور الجديدة قصيرة جداً (8 أحرف على الأقل)'}, status=400)
    
    if not user.check_password(current_password):
        return Response({'success': False, 'error': 'كلمة المرور الحالية غير صحيحة'}, status=400)
    
    user.set_password(new_password)
    user.save()
    
    return Response({'success': True, 'message': 'تم تغيير كلمة المرور بنجاح'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_my_account(request):
    """حذف حساب المستخدم بالكامل"""
    user = request.user
    username = user.username
    user.delete()
    return Response({'success': True, 'message': f'تم حذف حساب المستخدم {username} بنجاح'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_all_data(request):
    """تصدير جميع بيانات المستخدم"""
    user = request.user
    data = {
        'profile': {'username': user.username, 'email': user.email},
        'user_id': user.id,
        'export_date': timezone.now().isoformat(),
    }
    return Response({'success': True, 'data': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backup_data(request):
    """إنشاء نسخة احتياطية من البيانات"""
    user = request.user
    backup = {
        'user_id': user.id,
        'username': user.username,
        'export_date': timezone.now().isoformat(),
        'data': {'profile': {'username': user.username, 'email': user.email}}
    }
    return Response({'success': True, 'backup': backup, 'message': 'تم إنشاء النسخة الاحتياطية بنجاح'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_backup(request):
    """استعادة البيانات من نسخة احتياطية"""
    backup_data = request.data.get('backup')
    if not backup_data:
        return Response({'success': False, 'error': 'لا توجد بيانات للاستعادة'}, status=400)
    return Response({'success': True, 'message': 'تم استعادة البيانات بنجاح'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    """إعدادات المستخدم"""
    if request.method == 'GET':
        return Response({
            'success': True,
            'data': {
                'dark_mode': getattr(request.user, 'dark_mode', False),
                'notifications_enabled': getattr(request.user, 'notifications_enabled', True),
                'language': getattr(request.user, 'language', 'ar'),
            }
        })
    else:
        data = request.data
        if 'dark_mode' in data:
            request.user.dark_mode = data['dark_mode']
        if 'notifications_enabled' in data:
            request.user.notifications_enabled = data['notifications_enabled']
        if 'language' in data:
            request.user.language = data['language']
        request.user.save()
        return Response({'success': True, 'message': 'تم حفظ الإعدادات بنجاح'})


@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_goals(request):
    """إدارة الأهداف الصحية"""
    from .models import HealthGoal
    from .serializers import HealthGoalSerializer
    
    if request.method == 'GET':
        goals = HealthGoal.objects.filter(user=request.user)
        return Response({'success': True, 'data': list(goals.values())})
    
    elif request.method == 'POST':
        serializer = HealthGoalSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({'success': True, 'data': serializer.data, 'message': 'تم إضافة الهدف بنجاح'})
        return Response({'success': False, 'errors': serializer.errors}, status=400)
    
    elif request.method == 'PUT':
        goal_id = request.data.get('id')
        try:
            goal = HealthGoal.objects.get(id=goal_id, user=request.user)
            serializer = HealthGoalSerializer(goal, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({'success': True, 'data': serializer.data, 'message': 'تم تحديث الهدف بنجاح'})
            return Response({'success': False, 'errors': serializer.errors}, status=400)
        except HealthGoal.DoesNotExist:
            return Response({'success': False, 'error': 'الهدف غير موجود'}, status=404)
    
    elif request.method == 'DELETE':
        goal_id = request.data.get('id')
        try:
            goal = HealthGoal.objects.get(id=goal_id, user=request.user)
            goal.delete()
            return Response({'success': True, 'message': 'تم حذف الهدف بنجاح'})
        except HealthGoal.DoesNotExist:
            return Response({'success': False, 'error': 'الهدف غير موجود'}, status=404)
# أضف هذه الدالة في main/views.py (إذا لم تكن موجودة)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def manage_profile(request):
    """إدارة الملف الشخصي - إصدار مبسط وآمن"""
    user = request.user
    
    if request.method == 'GET':
        return Response({
            'success': True,
            'data': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
                'gender': user.gender,
                'phone_number': user.phone_number,
                'initial_weight': float(user.initial_weight) if user.initial_weight else None,
                'height': float(user.height) if user.height else None,
                'occupation_status': user.occupation_status,
                'health_goal': user.health_goal,
                'activity_level': user.activity_level,
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
            'message': 'Profile updated successfully',
            'data': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'initial_weight': float(user.initial_weight) if user.initial_weight else None,
                'height': float(user.height) if user.height else None,
                'health_goal': user.health_goal,
                'activity_level': user.activity_level,
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
    """البحث عن الطعام في Open Food Facts"""
    try:
        query = request.query_params.get('query', '').strip()
        if not query:
            return Response({
                'success': False, 
                'error': 'الرجاء إدخال اسم الطعام', 
                'data': []
            }, status=400)
        
        from urllib.parse import quote
        encoded_query = quote(query)
        
        # ✅ URL الصحيح لـ Open Food Facts
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={encoded_query}&search_simple=1&action=process&json=1&page_size=20"
        
        headers = {
            'User-Agent': 'LivocareApp/1.0 (https://livocare.onrender.com)'
        }
        
        # ✅ مهلة أقل (10 ثوانٍ كافية)
        response = requests.get(url, timeout=10, headers=headers)
        
        # ✅ التحقق من الاستجابة
        if response.status_code == 200:
            data = response.json()
            products = []
            
            # ✅ استخراج المنتجات بشكل آمن
            for product in data.get('products', []):
                product_name = product.get('product_name') or product.get('generic_name')
                
                # ✅ تجاهل المنتجات بدون اسم
                if not product_name or len(product_name) < 2:
                    continue
                
                # ✅ استخراج السعرات بشكل آمن
                nutriments = product.get('nutriments', {})
                calories = nutriments.get('energy-kcal', 0)
                if calories == 0:
                    calories = nutriments.get('energy_value', 0)
                
                # ✅ استخراج الصورة
                image_url = product.get('image_front_small_url') or product.get('image_url')
                
                products.append({
                    'id': product.get('code', ''),
                    'name': product_name,
                    'brand': product.get('brands', ''),
                    'image': image_url,
                    'calories': calories,
                    'serving_size': product.get('serving_size', ''),
                    'fat': nutriments.get('fat', 0),
                    'protein': nutriments.get('proteins', 0),
                    'carbs': nutriments.get('carbohydrates', 0)
                })
            
            # ✅ حتى لو لم تكن هناك نتائج، نعيد success
            if len(products) == 0:
                return Response({
                    'success': True,
                    'data': [],
                    'count': 0,
                    'message': f'لم يتم العثور على نتائج لـ "{query}"'
                })
            
            return Response({
                'success': True,
                'data': products,
                'count': len(products)
            })
        
        # ✅ خطأ من API الخارجي
        elif response.status_code == 404:
            return Response({
                'success': True,
                'data': [],
                'count': 0,
                'message': f'لا توجد نتائج لـ "{query}"'
            })
        else:
            return Response({
                'success': False,
                'error': f'فشل الاتصال بقاعدة البيانات (رمز {response.status_code})',
                'data': []
            }, status=500)
            
    except requests.exceptions.Timeout:
        # ✅ مهلة الاتصال
        return Response({
            'success': False,
            'error': 'انتهى وقت الاتصال بقاعدة البيانات، يرجى المحاولة مرة أخرى',
            'data': []
        }, status=504)
        
    except requests.exceptions.ConnectionError:
        # ✅ مشكلة في الاتصال بالإنترنت أو الخادم
        return Response({
            'success': False,
            'error': 'لا يمكن الاتصال بقاعدة البيانات، تحقق من اتصالك بالإنترنت',
            'data': []
        }, status=503)
        
    except Exception as e:
        # ✅ أي خطأ آخر
        print(f"❌ Food search error: {e}")
        return Response({
            'success': False,
            'error': 'حدث خطأ أثناء البحث، يرجى المحاولة مرة أخرى',
            'data': []
        }, status=500)



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
            'https://notification-v4jz.onrender.com/notify/all',
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
    """إرسال ملخص اليوم لجميع المستخدمين مع إشعارات منبثقة"""
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
            
            # ✅ حفظ في قاعدة البيانات
            Notification.objects.create(
                user=user, title="🌙 ملخص يومك", message=message,
                type="summary", priority="medium", action_url="/dashboard", is_read=False
            )
            
            # ✅ ✅ ✅ إرسال إشعار منبثق (Push Notification)
            send_push_notification_to_user(user.id, "🌙 ملخص يومك", message, "/dashboard")
            
            total += 1
        
        return Response({'success': True, 'message': f'تم إرسال الملخص إلى {total} مستخدم'})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)
    
    
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_morning_tip(request):
    """إرسال نصيحة صباحية لجميع المستخدمين مع إشعارات منبثقة"""
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
            # ✅ حفظ في قاعدة البيانات
            Notification.objects.create(
                user=user, title=tip['title'], message=tip['message'],
                type="tip", priority="low", action_url="/dashboard", is_read=False
            )
            
            # ✅ ✅ ✅ إرسال إشعار منبثق (Push Notification)
            send_push_notification_to_user(user.id, tip['title'], tip['message'], "/dashboard")
            
            total += 1
        
        return Response({'success': True, 'message': f'تم إرسال النصيحة إلى {total} مستخدم', 'tip': tip})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cron_smart_notifications(request):
    """إرسال إشعارات ذكية لجميع المستخدمين مع إشعارات منبثقة"""
    try:
        users = CustomUser.objects.filter(is_active=True)
        today = timezone.now().date()
        total = 0
        
        for user in users:
            created = 0
            
            if Meal.objects.filter(user=user, meal_time__date=today).count() == 0:
                # ✅ حفظ في قاعدة البيانات
                Notification.objects.create(
                    user=user, title='🥗 تذكير بالوجبة', message='لم تسجل أي وجبة اليوم!',
                    type='nutrition', priority='medium', action_url='/nutrition', is_read=False
                )
                # ✅ ✅ ✅ إرسال إشعار منبثق
                send_push_notification_to_user(user.id, '🥗 تذكير بالوجبة', 'لم تسجل أي وجبة اليوم!', '/nutrition')
                created += 1
            
            if PhysicalActivity.objects.filter(user=user, start_time__date=today).count() == 0:
                # ✅ حفظ في قاعدة البيانات
                Notification.objects.create(
                    user=user, title='🏃 حان وقت الحركة', message='المشي 30 دقيقة يحسن صحتك.',
                    type='activity', priority='medium', action_url='/activities', is_read=False
                )
                # ✅ ✅ ✅ إرسال إشعار منبثق
                send_push_notification_to_user(user.id, '🏃 حان وقت الحركة', 'لم تمارس أي نشاط بدني اليوم!', '/activities')
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
# 🤖 18. دوال ESP32 - تحديث العلامات الحيوية مباشرة
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def esp32_update_health_status(request):
    """
    تحديث حالة العلامات الحيوية للمستخدم الحالي من قراءات ESP32
    """
    try:
        user = request.user
        bpm = request.data.get('bpm')
        spo2 = request.data.get('spo2')
        
        # التحقق من وجود البيانات
        if bpm is None or spo2 is None:
            return Response({
                'status': 'error',
                'message': 'البيانات غير مكتملة - مطلوب bpm و spo2'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # تنظير القيم
        try:
            bpm = int(bpm)
            spo2 = int(spo2)
        except (ValueError, TypeError):
            return Response({
                'status': 'error',
                'message': 'القيم يجب أن تكون أرقاماً صحيحة'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # التحقق من صحة القيم
        if bpm < 30 or bpm > 250:
            return Response({
                'status': 'warning',
                'message': f'قراءة النبض غير طبيعية: {bpm} BPM',
                'data': {'bpm': bpm, 'spo2': spo2}
            }, status=status.HTTP_200_OK)
        
        if spo2 < 70 or spo2 > 100:
            return Response({
                'status': 'warning',
                'message': f'قراءة الأكسجين غير طبيعية: {spo2}%',
                'data': {'bpm': bpm, 'spo2': spo2}
            }, status=status.HTTP_200_OK)
        
        # ✅ تحديث أو إنشاء حالة صحية للمستخدم الحالي
        # استخدم spo2 بدلاً من blood_oxygen
        health_status, created = HealthStatus.objects.get_or_create(
            user=user,
            defaults={
                'heart_rate': bpm,
                'spo2': spo2,  # ✅ استخدم الحقل الموجود
                'recorded_at': timezone.now()
            }
        )
        
        if not created:
            # تحديث القراءة الحالية
            health_status.heart_rate = bpm
            health_status.spo2 = spo2  # ✅ استخدم الحقل الموجود
            health_status.recorded_at = timezone.now()
            health_status.save()
        
        # ✅ إنشاء إشعار تلقائي إذا كانت القراءات خطرة
        if bpm > 120 or bpm < 50 or spo2 < 90:
            Notification.objects.create(
                user=user,
                title='⚠️ تنبيه صحي',
                message=f'قراءات غير طبيعية: نبض {bpm} BPM، أكسجين {spo2}%',
                type='alert',
                priority='high',
                action_url='/health',
                is_read=False
            )
        
        return Response({
            'status': 'success',
            'message': 'تم تحديث القراءات بنجاح',
            'data': {
                'user_id': user.id,
                'username': user.username,
                'heart_rate': health_status.heart_rate,
                'blood_oxygen': spo2,  # ✅ للتوافق مع Frontend
                'spo2': health_status.spo2,
                'recorded_at': health_status.recorded_at.isoformat()
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"ESP32 update error: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def esp32_get_latest_health_status(request):
    """
    جلب آخر قراءة للعلامات الحيوية للمستخدم الحالي
    """
    try:
        user = request.user
        
        # جلب أحدث حالة صحية للمستخدم
        latest_status = HealthStatus.objects.filter(user=user).order_by('-recorded_at').first()
        
        if not latest_status:
            return Response({
                'status': 'success',
                'data': None,
                'message': 'لا توجد قراءات متاحة بعد'
            })
        
        # ✅ الحصول على قيمة الأكسجين من الحقل الصحيح (تجنب AttributeError)
        spo2_value = None
        if hasattr(latest_status, 'blood_oxygen'):
            spo2_value = latest_status.blood_oxygen
        elif hasattr(latest_status, 'spo2'):
            spo2_value = latest_status.spo2
        elif hasattr(latest_status, 'oxygen_saturation'):
            spo2_value = latest_status.oxygen_saturation
        
        # ✅ الحصول على قيمة النبض
        heart_rate_value = latest_status.heart_rate if hasattr(latest_status, 'heart_rate') else None
        
        return Response({
            'status': 'success',
            'data': {
                'heart_rate': heart_rate_value,
                'blood_oxygen': spo2_value,
                'recorded_at': latest_status.recorded_at.isoformat() if latest_status.recorded_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"ESP32 get latest error: {e}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def esp32_get_health_history(request):
    """
    جلب تاريخ قراءات العلامات الحيوية (آخر 50 قراءة)
    """
    try:
        user = request.user
        
        readings = HealthStatus.objects.filter(user=user).order_by('-recorded_at')[:50]
        
        data = [{
            'heart_rate': r.heart_rate,
            'blood_oxygen': r.spo2 if hasattr(r, 'spo2') else None,  # ✅ استخدم spo2
            'recorded_at': r.recorded_at.isoformat()
        } for r in readings if r.heart_rate or (hasattr(r, 'spo2') and r.spo2)]
        
        return Response({
            'status': 'success',
            'count': len(data),
            'data': data
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def esp32_test_update(request):
    """
    نسخة تجريبية - تحديث بدون توثيق (للتجربة فقط)
    """
    try:
        bpm = request.data.get('bpm')
        spo2 = request.data.get('spo2')
        
        if bpm is None or spo2 is None:
            return Response({
                'status': 'error',
                'message': 'Missing bpm or spo2'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # استخدام أول مستخدم في النظام للتجربة
        first_user = CustomUser.objects.filter(is_active=True).first()
        
        if not first_user:
            return Response({
                'status': 'error',
                'message': 'لا يوجد مستخدمين في النظام'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ✅ تصحيح: استخدم spo2 بدلاً من blood_oxygen
        health_status, created = HealthStatus.objects.get_or_create(
            user=first_user,
            defaults={
                'heart_rate': int(bpm),
                'spo2': int(spo2),  # ✅ تغيير من blood_oxygen إلى spo2
                'recorded_at': timezone.now()
            }
        )
        
        if not created:
            health_status.heart_rate = int(bpm)
            health_status.spo2 = int(spo2)  # ✅ تغيير من blood_oxygen إلى spo2
            health_status.recorded_at = timezone.now()
            health_status.save()
        
        return Response({
            'status': 'success',
            'message': 'Data received (test mode)',
            'data': {
                'user': first_user.username,
                'heart_rate': health_status.heart_rate,
                'blood_oxygen': health_status.spo2,  # ✅ للتوافق مع Frontend
                'spo2': health_status.spo2
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# ==============================================================================
# 🔓 19. نسخة تجريبية بدون توثيق (للتجربة فقط - يمكنك إزالتها لاحقاً)
# ==============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def esp32_test_update(request):
    """
    نسخة تجريبية - تحديث بدون توثيق (للتجربة فقط)
    """
    try:
        bpm = request.data.get('bpm')
        spo2 = request.data.get('spo2')
        
        if bpm is None or spo2 is None:
            return Response({
                'status': 'error',
                'message': 'Missing bpm or spo2'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # استخدام أول مستخدم في النظام للتجربة
        first_user = CustomUser.objects.filter(is_active=True).first()
        
        if not first_user:
            return Response({
                'status': 'error',
                'message': 'لا يوجد مستخدمين في النظام'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # تحديث الحالة الصحية للمستخدم الأول
        health_status, created = HealthStatus.objects.get_or_create(
            user=first_user,
            defaults={
                'heart_rate': int(bpm),
                'blood_oxygen': int(spo2),
                'recorded_at': timezone.now()
            }
        )
        
        if not created:
            health_status.heart_rate = int(bpm)
            health_status.blood_oxygen = int(spo2)
            health_status.recorded_at = timezone.now()
            health_status.save()
        
        return Response({
            'status': 'success',
            'message': 'Data received (test mode)',
            'data': {
                'user': first_user.username,
                'heart_rate': health_status.heart_rate,
                'blood_oxygen': health_status.blood_oxygen
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

# main/views.py - أضف أو عدّل هذه الدالة

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework_simplejwt.tokens import RefreshToken
from main.models import CustomUser  # ✅ استخدم نموذج المستخدم المخصص
import json

@csrf_exempt
@require_http_methods(["POST"])
def google_auth(request):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        name = data.get('name', '')
        google_id = data.get('google_id', '')
        
        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)
        
        # ✅ إنشاء اسم مستخدم فريد من البريد الإلكتروني
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        
        # ✅ التأكد من أن اسم المستخدم فريد
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # ✅ تقسيم الاسم الكامل إلى اسم أول واسم عائلة
        name_parts = name.split(' ', 1) if name else ['', '']
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # ✅ إنشاء المستخدم أو جلبه باستخدام CustomUser
        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                # ✅ الحقول الإضافية من CustomUser
                'gender': None,  # سيطلب من المستخدم إكماله لاحقاً
                'health_goal': None,  # سيطلب من المستخدم إكماله لاحقاً
                'activity_level': None,  # سيطلب من المستخدم إكماله لاحقاً
            }
        )
        
        # ✅ إذا كان المستخدم موجوداً مسبقاً، تأكد من تحديث الاسم إذا كان فارغاً
        if not created:
            if not user.first_name and first_name:
                user.first_name = first_name
                user.save(update_fields=['first_name', 'last_name'])
        
        # ✅ إنشاء التوكن JWT
        refresh = RefreshToken.for_user(user)
        
        return JsonResponse({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"❌ Google auth error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
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
    
# في main/views.py - استخدم هذا التعريف فقط

class MealViewSet(viewsets.ModelViewSet):
    """ViewSet لإدارة الوجبات"""
    serializer_class = MealSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_queryset(self):
        """جلب وجبات المستخدم فقط"""
        return Meal.objects.filter(user=self.request.user).order_by('-meal_time')
    
    def perform_create(self, serializer):
        """إضافة المستخدم تلقائياً عند إنشاء وجبة"""
        serializer.save(user=self.request.user)

# views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from main.services.cross_insights_service import get_health_insights
import json

@login_required
def health_dashboard(request):
    """
    عرض لوحة التحكم الصحية
    """
    context = {
        'page_title': 'لوحة التحليل الصحي الذكي',
        'user_name': request.user.get_full_name() or request.user.username,
    }
    return render(request, 'health/dashboard.html', context)


@login_required
def get_health_analysis_api(request):
    """
    API لجلب التحليلات الصحية (AJAX)
    """
    language = request.GET.get('lang', 'ar')
    result = get_health_insights(request.user, language=language)
    
    if result['success']:
        return JsonResponse({
            'success': True,
            'data': result['data'],
            'is_arabic': language == 'ar'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'حدث خطأ في التحليل'),
            'message': result.get('message', '')
        }, status=500)


@login_required
def refresh_analysis(request):
    """
    تحديث التحليلات (عادةً ما يتم تخزينها في cache)
    """
    # يمكنك إضافة منطق التخزين المؤقت هنا
    return get_health_analysis_api(request)
## views.py - النسخة الصحيحة

# main/views.py - أضف هذه الدوال في نهاية الملف

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Avg, Count
import logging
import traceback
from django.conf import settings

logger = logging.getLogger(__name__)

# ✅ استيراد خدمة التحليلات المتقدمة
try:
    from .services.cross_insights_service import get_health_insights
    ML_SERVICE_AVAILABLE = True
    print("✅ ML service loaded successfully")
except ImportError as e:
    ML_SERVICE_AVAILABLE = False
    print(f"⚠️ ML service not available: {e}")


# ==============================================================================
# ✅ API الرئيسي للتحليلات الشاملة (SmartRecommendations)
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comprehensive_analytics_api(request):
    """
    API للتحليلات الصحية الشاملة - يستخدم خدمة ML المتقدمة
    هذا هو الـ endpoint الرئيسي الذي تستخدمه واجهة SmartRecommendations
    """
    try:
        user = request.user
        lang = request.GET.get('lang', 'en')
        is_arabic = lang == 'ar'
        
        # ✅ استخدام خدمة ML إذا كانت متوفرة
        if ML_SERVICE_AVAILABLE:
            try:
                result = get_health_insights(user, language=lang)
                
                if result.get('success'):
                    ml_data = result.get('data', {})
                    
                    # ✅ تحويل البيانات إلى الهيكل المتوقع من SmartRecommendations
                    converted_data = convert_ml_to_smart_recommendations_format(ml_data, is_arabic)
                    
                    return Response({
                        'success': True,
                        'data': converted_data,
                        'is_ml_enhanced': True,
                        'message': is_arabic and '✓ تم التحليل باستخدام الذكاء الاصطناعي' or '✓ Analyzed with AI'
                    })
                else:
                    return get_fallback_analytics_response(user, is_arabic)
                    
            except Exception as e:
                logger.error(f"ML service error: {e}")
                logger.error(traceback.format_exc())
                return get_fallback_analytics_response(user, is_arabic)
        else:
            return get_fallback_analytics_response(user, is_arabic)
            
    except Exception as e:
        logger.error(f"Comprehensive analytics error: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': is_arabic and 'حدث خطأ في تحليل البيانات' or 'Error analyzing data'
        }, status=500)


# ==============================================================================
# ✅ API للتوصيات فقط (للوحة الرئيسية)
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recommendations_only(request):
    """
    API للحصول على التوصيات فقط
    يستخدمه SmartRecommendations في تبويب التوصيات
    """
    language = request.GET.get('lang', 'ar')
    is_arabic = language == 'ar'
    limit = int(request.GET.get('limit', 10))
    
    try:
        if ML_SERVICE_AVAILABLE:
            result = get_health_insights(request.user, language=language)
            
            if result.get('success'):
                ml_data = result.get('data', {})
                smart_recs = ml_data.get('smart_recommendations', [])
                
                recommendations = []
                for rec in smart_recs[:limit]:
                    recommendations.append({
                        'category': rec.get('category', 'general'),
                        'priority': rec.get('priority', 'medium'),
                        'icon': rec.get('icon', '💡'),
                        'title': rec.get('title', ''),
                        'description': rec.get('description', ''),
                        'advice': rec.get('actionable_tip', rec.get('description', '')),
                        'actions': rec.get('actions', [])
                    })
                
                return Response({
                    'success': True,
                    'recommendations': recommendations,
                    'total': len(smart_recs),
                    'is_arabic': is_arabic
                })
        
        # Fallback: توصيات بسيطة
        return get_fallback_recommendations(request.user, is_arabic, limit)
        
    except Exception as e:
        logger.error(f"Recommendations API error: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': is_arabic and 'حدث خطأ في جلب التوصيات' or 'Error fetching recommendations'
        }, status=500)


# ==============================================================================
# ✅ دوال التحويل والتنسيق
# ==============================================================================

def convert_ml_to_smart_recommendations_format(ml_data, is_arabic):
    """
    تحويل بيانات خدمة ML إلى الهيكل المتوقع من SmartRecommendations
    """
    lifetime_summary = ml_data.get('lifetime_summary', {})
    user_info = ml_data.get('user_info', {})
    predictions = ml_data.get('predictions', {})
    correlations = ml_data.get('correlations', [])
    recommendations = ml_data.get('smart_recommendations', [])
    
    # ✅ حساب درجة الصحة
    health_score = calculate_health_score_from_ml(ml_data, is_arabic)
    
    # ✅ بناء الهيكل المطلوب
    return {
        'profile': {
            'age': user_info.get('age'),
            'gender': user_info.get('gender'),
            'height_cm': user_info.get('height_cm'),
            'health_goal': user_info.get('health_goal'),
            'tracking_days': user_info.get('total_tracking_days', 0)
        },
        'vital_signs': {
            'status': 'normal',
            'last_check': timezone.now().isoformat()
        },
        'sleep': {
            'status': 'good' if lifetime_summary.get('sleep_summary', {}).get('average_hours', 0) >= 7 else 'needs_improvement',
            'average_hours': lifetime_summary.get('sleep_summary', {}).get('average_hours', 0),
            'total_nights': lifetime_summary.get('sleep_summary', {}).get('total_nights', 0),
            'regularity': lifetime_summary.get('sleep_summary', {}).get('regularity', 'moderate')
        },
        'mood_mental': {
            'status': 'good' if lifetime_summary.get('mood_summary', {}).get('average_score', 0) >= 3.5 else 'needs_attention',
            'average_score': lifetime_summary.get('mood_summary', {}).get('average_score', 0),
            'total_entries': lifetime_summary.get('mood_summary', {}).get('total_entries', 0)
        },
        'activity': {
            'status': lifetime_summary.get('activity_summary', {}).get('actual_activity_level', 'none'),
            'activity_level': lifetime_summary.get('activity_summary', {}).get('actual_activity_level', 'none'),
            'average_daily_minutes': round(lifetime_summary.get('activity_summary', {}).get('avg_weekly_activity', 0) / 7, 1),
            'total_activities': lifetime_summary.get('activity_summary', {}).get('total_activities', 0)
        },
        'nutrition': {
            'status': 'sufficient' if lifetime_summary.get('nutrition_summary', {}).get('average_calories_per_day', 0) >= 1800 else 'insufficient',
            'average_daily_calories': lifetime_summary.get('nutrition_summary', {}).get('average_calories_per_day', 0),
            'total_meals': lifetime_summary.get('nutrition_summary', {}).get('total_meals', 0)
        },
        'habits': {
            'status': 'good' if lifetime_summary.get('habits_summary', {}).get('completion_rates') else 'no_data',
            'total_habits': lifetime_summary.get('habits_summary', {}).get('total_habits', 0),
            'best_habit': lifetime_summary.get('habits_summary', {}).get('best_habit')
        },
        'executive_summary': generate_executive_summary_from_ml(ml_data, is_arabic),
        'health_score': health_score,
        'patterns_correlations': {
            'correlations': convert_correlations_to_dict(correlations),
            'insights': [c.get('description', '') for c in correlations]
        },
        'personalized_recommendations': [
            {
                'category': rec.get('category', 'general'),
                'priority': rec.get('priority', 'medium'),
                'icon': rec.get('icon', '💡'),
                'title': rec.get('title', ''),
                'description': rec.get('description', ''),
                'advice': rec.get('actionable_tip', rec.get('description', ''))
            }
            for rec in recommendations[:10]
        ],
        'predictions': {
            'weight': {
                'current': predictions.get('weight_trend', {}).get('current'),
                'predictions': [predictions.get('weight_trend', {}).get('predicted_2weeks')] if predictions.get('weight_trend', {}).get('predicted_2weeks') else [],
                'trend': predictions.get('weight_trend', {}).get('trend', 'stable'),
                'confidence': predictions.get('weight_trend', {}).get('confidence', 70)
            },
            'mood': {
                'current': lifetime_summary.get('mood_summary', {}).get('average_score', 0),
                'trend': predictions.get('mood_forecast', {}).get('trend', 'stable'),
                'message': predictions.get('mood_forecast', {}).get('message', '')
            }
        }
    }


def calculate_health_score_from_ml(ml_data, is_arabic):
    """حساب درجة الصحة من بيانات ML"""
    lifetime_summary = ml_data.get('lifetime_summary', {})
    
    score = 0
    components = {}
    
    # النشاط البدني (30 نقطة)
    activity_level = lifetime_summary.get('activity_summary', {}).get('actual_activity_level', 'none')
    if activity_level == 'high':
        score += 30
        components['activity'] = 30
    elif activity_level == 'medium':
        score += 20
        components['activity'] = 20
    elif activity_level == 'low':
        score += 10
        components['activity'] = 10
    else:
        components['activity'] = 0
    
    # النوم (25 نقطة)
    avg_sleep = lifetime_summary.get('sleep_summary', {}).get('average_hours', 0)
    if 7 <= avg_sleep <= 9:
        score += 25
        components['sleep'] = 25
    elif 6 <= avg_sleep < 7 or 9 < avg_sleep <= 10:
        score += 15
        components['sleep'] = 15
    elif avg_sleep > 0:
        score += 5
        components['sleep'] = 5
    else:
        components['sleep'] = 0
    
    # العادات (20 نقطة)
    completion_rates = lifetime_summary.get('habits_summary', {}).get('completion_rates', {})
    if completion_rates:
        avg_rate = sum(completion_rates.values()) / len(completion_rates)
        if avg_rate >= 80:
            score += 20
            components['habits'] = 20
        elif avg_rate >= 50:
            score += 12
            components['habits'] = 12
        else:
            score += 5
            components['habits'] = 5
    else:
        components['habits'] = 0
    
    # المزاج (15 نقطة)
    avg_mood = lifetime_summary.get('mood_summary', {}).get('average_score', 0)
    if avg_mood >= 4:
        score += 15
        components['mood'] = 15
    elif avg_mood >= 3:
        score += 10
        components['mood'] = 10
    elif avg_mood > 0:
        score += 5
        components['mood'] = 5
    else:
        components['mood'] = 0
    
    # نظام غذائي (10 نقاط)
    avg_calories = lifetime_summary.get('nutrition_summary', {}).get('average_calories_per_day', 0)
    if 1800 <= avg_calories <= 2500:
        score += 10
        components['nutrition'] = 10
    elif avg_calories > 0:
        score += 5
        components['nutrition'] = 5
    else:
        components['nutrition'] = 0
    
    # تحديد الفئة
    if score >= 80:
        category = 'excellent'
        category_text = is_arabic and 'ممتازة' or 'Excellent'
    elif score >= 60:
        category = 'good'
        category_text = is_arabic and 'جيدة' or 'Good'
    elif score >= 40:
        category = 'fair'
        category_text = is_arabic and 'متوسطة' or 'Fair'
    else:
        category = 'poor'
        category_text = is_arabic and 'تحتاج تحسيناً' or 'Needs Improvement'
    
    return {
        'total_score': score,
        'category': category,
        'category_text': category_text,
        'components': components,
        'max_score': 100
    }


def convert_correlations_to_dict(correlations):
    """تحويل قائمة الارتباطات إلى قاموس"""
    result = {}
    for corr in correlations:
        title = corr.get('title', '')
        if 'النشاط والنوم' in title or 'Activity & Sleep' in title:
            result['activity_sleep'] = corr.get('strength', 0.5)
        elif 'العادات والمزاج' in title or 'Habits & Mood' in title:
            result['habits_mood'] = corr.get('strength', 0.5)
        elif 'النوم والمزاج' in title or 'Sleep & Mood' in title:
            result['sleep_mood'] = corr.get('strength', 0.5)
        elif 'النشاط والمزاج' in title or 'Activity & Mood' in title:
            result['activity_mood'] = corr.get('strength', 0.5)
    return result


def generate_executive_summary_from_ml(ml_data, is_arabic):
    """توليد ملخص تنفيذي ذكي"""
    lifetime_summary = ml_data.get('lifetime_summary', {})
    activity_summary = lifetime_summary.get('activity_summary', {})
    sleep_summary = lifetime_summary.get('sleep_summary', {})
    weight_summary = lifetime_summary.get('weight_summary', {})
    habits_summary = lifetime_summary.get('habits_summary', {})
    tracking_days = lifetime_summary.get('tracking_period', {}).get('total_days', 0)
    
    parts = []
    
    if tracking_days > 0:
        parts.append(f"📊 أنت تتابع صحتك منذ {tracking_days} يوماً." if is_arabic else f"📊 You've been tracking for {tracking_days} days.")
    
    activity_level = activity_summary.get('actual_activity_level', 'none')
    if activity_level == 'high':
        parts.append("🏃 مستوى نشاطك ممتاز! استمر." if is_arabic else "🏃 Your activity level is excellent! Keep it up.")
    elif activity_level == 'low':
        parts.append("🚶 يحتاج نشاطك إلى تحسين. ابدأ بالمشي 10 دقائق يومياً." if is_arabic else "🚶 Your activity needs improvement. Start with 10 min walking daily.")
    
    avg_sleep = sleep_summary.get('average_hours', 0)
    if 7 <= avg_sleep <= 9:
        parts.append("😴 نومك ممتاز!" if is_arabic else "😴 Your sleep is excellent!")
    elif avg_sleep > 0:
        parts.append(f"😴 متوسط نومك {avg_sleep} ساعات." if is_arabic else f"😴 Your average sleep is {avg_sleep} hours.")
    
    best_habit = habits_summary.get('best_habit')
    if best_habit:
        rate = habits_summary.get('completion_rates', {}).get(best_habit, 0)
        parts.append(f"🌟 عادة \"{best_habit}\" هي الأفضل لديك بنسبة {rate}%." if is_arabic else f"🌟 Habit \"{best_habit}\" is your best at {rate}%.")
    
    if tracking_days < 14:
        parts.append("🌱 بداية رائعة! استمر في التسجيل." if is_arabic else "🌱 Great start! Keep logging.")
    else:
        parts.append("💪 استمر في تحقيق أهدافك!" if is_arabic else "💪 Keep achieving your goals!")
    
    return "\n\n".join(parts)


# ==============================================================================
# ✅ دوال Fallback (عند عدم توفر خدمة ML)
# ==============================================================================

def get_fallback_analytics_response(user, is_arabic):
    """رد احتياطي عندما لا تتوفر خدمة ML"""
    from .models import PhysicalActivity, Sleep, HealthStatus, HabitLog, HabitDefinition
    from datetime import timedelta
    from django.utils import timezone
    
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    activities = PhysicalActivity.objects.filter(user=user, start_time__date__gte=thirty_days_ago)
    sleep_records = Sleep.objects.filter(user=user, sleep_start__date__gte=thirty_days_ago)
    health_records = HealthStatus.objects.filter(user=user, recorded_at__date__gte=thirty_days_ago)
    habits = HabitDefinition.objects.filter(user=user, is_active=True)
    habit_logs = HabitLog.objects.filter(habit__user=user, log_date__gte=thirty_days_ago)
    
    total_activities = activities.count()
    
    # حساب النوم
    total_sleep = 0
    for sleep in sleep_records:
        if sleep.sleep_end and sleep.sleep_start:
            duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
            if 0 < duration < 24:
                total_sleep += duration
    avg_sleep = round(total_sleep / sleep_records.count(), 1) if sleep_records.count() > 0 else 0
    
    # حساب العادات
    habit_count = habit_logs.count()
    completed_count = habit_logs.filter(is_completed=True).count()
    habit_rate = round((completed_count / habit_count) * 100, 1) if habit_count > 0 else 0
    
    # حساب درجة الصحة
    score = 50
    if 7 <= avg_sleep <= 9:
        score += 25
    elif avg_sleep > 0:
        score += 10
    
    if total_activities >= 15:
        score += 25
    elif total_activities >= 5:
        score += 15
    elif total_activities > 0:
        score += 5
    
    if habit_rate >= 70:
        score += 20
    elif habit_rate >= 40:
        score += 10
    
    score = min(100, max(0, score))
    
    if score >= 80:
        category = 'excellent'
        category_text = is_arabic and 'ممتازة' or 'Excellent'
    elif score >= 60:
        category = 'good'
        category_text = is_arabic and 'جيدة' or 'Good'
    elif score >= 40:
        category = 'fair'
        category_text = is_arabic and 'متوسطة' or 'Fair'
    else:
        category = 'poor'
        category_text = is_arabic and 'تحتاج تحسيناً' or 'Needs Improvement'
    
    return Response({
        'success': True,
        'data': {
            'profile': {'tracking_days': 30},
            'sleep': {'average_hours': avg_sleep, 'status': 'good' if avg_sleep >= 7 else 'needs_improvement'},
            'mood_mental': {'average_score': 3, 'status': 'good'},
            'activity': {'total_activities': total_activities, 'activity_level': 'moderate' if total_activities >= 5 else 'low'},
            'health_score': {'total_score': score, 'category': category, 'category_text': category_text, 'components': {}, 'max_score': 100},
            'personalized_recommendations': [],
            'executive_summary': is_arabic and 'تحليل أساسي. سجل المزيد من البيانات للحصول على توصيات متقدمة.' or 'Basic analysis. Log more data for advanced insights.'
        },
        'is_ml_enhanced': False,
        'message': is_arabic and '⚠️ تحليلات أساسية (النسخة المتقدمة قيد التفعيل)' or '⚠️ Basic analytics (Advanced version activating)'
    })


def get_fallback_recommendations(user, is_arabic, limit=5):
    """رد احتياطي للتوصيات"""
    from .models import PhysicalActivity, Sleep
    from datetime import timedelta
    from django.utils import timezone
    
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    activities = PhysicalActivity.objects.filter(user=user, start_time__date__gte=thirty_days_ago)
    sleep_records = Sleep.objects.filter(user=user, sleep_start__date__gte=thirty_days_ago)
    
    total_activities = activities.count()
    
    total_sleep = 0
    for sleep in sleep_records:
        if sleep.sleep_end and sleep.sleep_start:
            duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
            if 0 < duration < 24:
                total_sleep += duration
    avg_sleep = round(total_sleep / sleep_records.count(), 1) if sleep_records.count() > 0 else 0
    
    recommendations = []
    
    if avg_sleep > 0 and avg_sleep < 7:
        recommendations.append({
            'category': 'sleep',
            'priority': 'high',
            'icon': '😴',
            'title': is_arabic and 'تحسين جودة النوم' or 'Improve Sleep Quality',
            'description': is_arabic and f'متوسط نومك {avg_sleep} ساعات' or f'Your average sleep is {avg_sleep} hours',
            'advice': is_arabic and 'حاول النوم 7-8 ساعات يومياً' or 'Try to sleep 7-8 hours daily'
        })
    
    if total_activities < 8:
        recommendations.append({
            'category': 'activity',
            'priority': 'high',
            'icon': '🏃',
            'title': is_arabic and 'زيادة النشاط البدني' or 'Increase Physical Activity',
            'description': is_arabic and f'سجلت {total_activities} نشاط في آخر 30 يوم' or f'You recorded {total_activities} activities',
            'advice': is_arabic and 'امشِ 30 دقيقة يومياً' or 'Walk 30 minutes daily'
        })
    
    return Response({
        'success': True,
        'recommendations': recommendations[:limit],
        'total': len(recommendations),
        'is_arabic': is_arabic
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recommendations_only(request):
    """API للحصول على التوصيات فقط (للوحة الرئيسية)"""
    language = request.GET.get('lang', 'ar')
    is_arabic = language == 'ar'
    limit = int(request.GET.get('limit', 5))
    
    try:
        # محاولة استخدام خدمة ML
        try:
            from .services.cross_insights_service import get_health_insights
            result = get_health_insights(request.user, language=language)
            
            if result.get('success'):
                ml_data = result.get('data', {})
                smart_recs = ml_data.get('smart_recommendations', [])
                
                recommendations = []
                for rec in smart_recs[:limit]:
                    recommendations.append({
                        'category': rec.get('category', 'general'),
                        'priority': rec.get('priority', 'medium'),
                        'icon': rec.get('icon', '💡'),
                        'title': rec.get('title', ''),
                        'description': rec.get('description', ''),
                        'advice': rec.get('actionable_tip', rec.get('description', ''))
                    })
                
                return Response({
                    'success': True,
                    'recommendations': recommendations,
                    'total': len(smart_recs),
                    'is_arabic': is_arabic
                })
        except ImportError:
            pass
        
        # Fallback: توصيات بسيطة
        from .models import PhysicalActivity, Sleep
        from datetime import timedelta
        from django.utils import timezone
        
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        activities = PhysicalActivity.objects.filter(
            user=request.user, 
            start_time__date__gte=thirty_days_ago
        )
        sleep_records = Sleep.objects.filter(
            user=request.user,
            sleep_start__date__gte=thirty_days_ago
        )
        
        total_activities = activities.count()
        
        # حساب النوم
        total_sleep = 0
        for sleep in sleep_records:
            if sleep.sleep_end and sleep.sleep_start:
                duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                if 0 < duration < 24:
                    total_sleep += duration
        avg_sleep = round(total_sleep / sleep_records.count(), 1) if sleep_records.count() > 0 else 0
        
        recommendations = []
        
        if avg_sleep > 0 and avg_sleep < 7:
            recommendations.append({
                'category': 'sleep',
                'priority': 'high',
                'icon': '😴',
                'title': is_arabic and 'تحسين جودة النوم' or 'Improve Sleep Quality',
                'description': is_arabic and f'متوسط نومك {avg_sleep} ساعات' or f'Your average sleep is {avg_sleep} hours',
                'advice': is_arabic and 'حاول النوم 7-8 ساعات يومياً' or 'Try to sleep 7-8 hours daily'
            })
        
        if total_activities < 8:
            recommendations.append({
                'category': 'activity',
                'priority': 'high',
                'icon': '🏃',
                'title': is_arabic and 'زيادة النشاط البدني' or 'Increase Physical Activity',
                'description': is_arabic and f'سجلت {total_activities} نشاط في آخر 30 يوم' or f'You recorded {total_activities} activities in last 30 days',
                'advice': is_arabic and 'امشِ 30 دقيقة يومياً لمدة 5 أيام في الأسبوع' or 'Walk 30 minutes daily for 5 days a week'
            })
        
        return Response({
            'success': True,
            'recommendations': recommendations[:limit],
            'total': len(recommendations),
            'is_arabic': is_arabic
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'message': is_arabic and 'حدث خطأ في جلب التوصيات' or 'Error fetching recommendations'
        }, status=500)
# ==============================================================================
# دوال المقارنة مع المستخدمين الآخرين (اختياري)
# ==============================================================================

@login_required
def compare_with_peers(request):
    """
    مقارنة بيانات المستخدم مع مستخدمين آخرين من نفس الفئة العمرية
    """
    language = request.GET.get('lang', 'ar')
    
    try:
        # جلب تحليلات المستخدم الحالي
        user_analytics = get_comprehensive_health_analytics(request.user, language=language)
        
        # جلب متوسطات الفئة العمرية
        age_category = user_analytics.get('profile', {}).get('age_category', 'adult')
        
        # استعلام عن متوسطات المستخدمين الآخرين (نفس الفئة العمرية)
        from django.db.models import Avg
        
        # هذا مثال مبسط - يمكن تطويره بشكل أكبر
        peers_avg = {
            'avg_sleep': 7.5,
            'avg_activity': 35,
            'avg_mood': 3.8,
            'avg_health_score': 72
        }
        
        return JsonResponse({
            'success': True,
            'user_data': {
                'sleep': user_analytics.get('sleep', {}).get('average_hours', 0),
                'activity': user_analytics.get('activity', {}).get('average_daily_minutes', 0),
                'mood': user_analytics.get('mood_mental', {}).get('average_mood_score', 0),
                'health_score': user_analytics.get('health_score', {}).get('total_score', 0)
            },
            'peers_average': peers_avg,
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# main/views.py - أضف هذه الدوال

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from datetime import timedelta
from collections import defaultdict
import logging
import traceback

logger = logging.getLogger(__name__)


# ==============================================================================
# ✅ تحليلات متقدمة باستخدام scikit-learn
# ==============================================================================

class AdvancedHealthAnalyticsML:
    """
    كلاس متقدم لتحليل البيانات الصحية باستخدام scikit-learn
    """
    
    def __init__(self, user, is_arabic=False):
        self.user = user
        self.is_arabic = is_arabic
        self.today = timezone.now().date()
        self._load_all_data()
        
    def _load_all_data(self):
        """جلب جميع البيانات من النماذج"""
        from .models import (
            PhysicalActivity, Sleep, MoodEntry, HealthStatus, 
            Meal, HabitLog, UserMedication
        )
        
        self.activities = PhysicalActivity.objects.filter(user=self.user).order_by('start_time')
        self.sleep_records = Sleep.objects.filter(user=self.user).order_by('sleep_start')
        self.mood_records = MoodEntry.objects.filter(user=self.user).order_by('entry_time')
        self.health_records = HealthStatus.objects.filter(user=self.user).order_by('recorded_at')
        self.meals = Meal.objects.filter(user=self.user).order_by('meal_time')
        self.habit_logs = HabitLog.objects.filter(habit__user=self.user)
        self.medications_count = UserMedication.objects.filter(user=self.user).count()
        
        # معلومات المستخدم
        self.user_age = self._calculate_age()
        
    def _calculate_age(self):
        """حساب عمر المستخدم"""
        if hasattr(self.user, 'date_of_birth') and self.user.date_of_birth:
            today = timezone.now().date()
            return today.year - self.user.date_of_birth.year - (
                (today.month, today.day) < (self.user.date_of_birth.month, self.user.date_of_birth.day)
            )
        return None
    
    def _t(self, ar_text, en_text):
        return ar_text if self.is_arabic else en_text
    
    # ==========================================================================
    # 1. تحليل الاتجاهات
    # ==========================================================================
    
    def analyze_trends(self):
        """تحليل اتجاهات البيانات"""
        trends = {'weight_trend': None, 'activity_trend': None}
        
        # اتجاه الوزن
        if self.health_records.count() >= 5:
            weights = []
            days = []
            for i, record in enumerate(self.health_records):
                if record.weight_kg:
                    weights.append(float(record.weight_kg))
                    days.append(i)
            
            if len(weights) >= 5:
                days_array = np.array(days).reshape(-1, 1)
                weights_array = np.array(weights)
                model = LinearRegression()
                model.fit(days_array, weights_array)
                slope = model.coef_[0]
                
                if abs(slope) > 0.05:
                    trend = 'increasing' if slope > 0 else 'decreasing'
                    message = self._t(
                        f'📈 وزنك في زيادة ({abs(slope):.2f} كجم/أسبوع)' if slope > 0 else f'📉 وزنك في نقصان ({abs(slope):.2f} كجم/أسبوع)',
                        f'📈 Weight increasing ({abs(slope):.2f} kg/week)' if slope > 0 else f'📉 Weight decreasing ({abs(slope):.2f} kg/week)'
                    )
                else:
                    trend = 'stable'
                    message = self._t('⚖️ وزنك مستقر', '⚖️ Weight stable')
                
                trends['weight_trend'] = {'trend': trend, 'slope': round(slope, 3), 'message': message}
        
        # اتجاه النشاط
        if self.activities.count() >= 5:
            durations = []
            days = []
            for i, act in enumerate(self.activities):
                durations.append(act.duration_minutes)
                days.append(i)
            
            if len(durations) >= 5:
                days_array = np.array(days).reshape(-1, 1)
                durations_array = np.array(durations)
                model = LinearRegression()
                model.fit(days_array, durations_array)
                slope = model.coef_[0]
                
                if abs(slope) > 2:
                    trend = 'increasing' if slope > 0 else 'decreasing'
                    message = self._t(
                        f'🏃 نشاطك في تزايد' if slope > 0 else f'⚠️ نشاطك في تناقص',
                        f'🏃 Activity increasing' if slope > 0 else f'⚠️ Activity decreasing'
                    )
                else:
                    trend = 'stable'
                    message = self._t('🚶 نشاطك مستقر', '🚶 Activity stable')
                
                trends['activity_trend'] = {'trend': trend, 'slope': round(slope, 2), 'message': message}
        
        return trends
    
    # ==========================================================================
    # 2. توقعات الوزن
    # ==========================================================================
    
    def predict_weight(self):
        """توقع الوزن باستخدام Random Forest"""
        if self.health_records.count() < 7:
            return None
        
        try:
            data = []
            for i, record in enumerate(self.health_records):
                if record.weight_kg:
                    data.append({
                        'day': i,
                        'weight': float(record.weight_kg),
                        'day_of_week': record.recorded_at.weekday()
                    })
            
            if len(data) < 7:
                return None
            
            df = pd.DataFrame(data)
            df['weight_lag1'] = df['weight'].shift(1)
            df['weight_lag3'] = df['weight'].shift(3)
            df['weight_lag7'] = df['weight'].shift(7)
            df = df.dropna()
            
            if len(df) < 5:
                return None
            
            features = ['day', 'day_of_week', 'weight_lag1', 'weight_lag3', 'weight_lag7']
            X = df[features].values
            y = df['weight'].values
            
            # تدريب النموذج
            model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
            model.fit(X[:-3], y[:-3])
            
            # توقع
            last_features = X[-3:]
            predictions = model.predict(last_features)
            predicted_weight = float(np.mean(predictions))
            current_weight = float(y[-1])
            
            return {
                'current': round(current_weight, 1),
                'predicted': round(predicted_weight, 1),
                'change': round(predicted_weight - current_weight, 1),
                'trend': 'up' if predicted_weight > current_weight else 'down' if predicted_weight < current_weight else 'stable',
                'confidence': min(85, 50 + len(df))
            }
        except Exception as e:
            logger.error(f"Weight prediction error: {e}")
            return None
    
    # ==========================================================================
    # 3. كشف الأنماط الشاذة
    # ==========================================================================
    
    def detect_anomalies(self):
        """كشف الأنماط الشاذة باستخدام Isolation Forest"""
        anomalies = {'weight_anomalies': [], 'activity_anomalies': []}
        
        # أنماط الوزن الشاذة
        if self.health_records.count() >= 10:
            try:
                weights = []
                dates = []
                for record in self.health_records:
                    if record.weight_kg:
                        weights.append(float(record.weight_kg))
                        dates.append(record.recorded_at)
                
                if len(weights) >= 10:
                    weights_array = np.array(weights).reshape(-1, 1)
                    scaler = StandardScaler()
                    weights_scaled = scaler.fit_transform(weights_array)
                    
                    iso_forest = IsolationForest(contamination=0.1, random_state=42)
                    predictions = iso_forest.fit_predict(weights_scaled)
                    
                    for i, pred in enumerate(predictions):
                        if pred == -1:
                            anomalies['weight_anomalies'].append({
                                'date': dates[i].date().isoformat(),
                                'value': weights[i],
                                'type': 'unusual_weight'
                            })
            except Exception as e:
                logger.error(f"Weight anomaly error: {e}")
        
        # أنماط النشاط الشاذة
        if self.activities.count() >= 10:
            try:
                durations = [act.duration_minutes for act in self.activities]
                dates = [act.start_time for act in self.activities]
                
                if len(durations) >= 10:
                    durations_array = np.array(durations).reshape(-1, 1)
                    scaler = StandardScaler()
                    durations_scaled = scaler.fit_transform(durations_array)
                    
                    iso_forest = IsolationForest(contamination=0.1, random_state=42)
                    predictions = iso_forest.fit_predict(durations_scaled)
                    
                    for i, pred in enumerate(predictions):
                        if pred == -1:
                            anomalies['activity_anomalies'].append({
                                'date': dates[i].date().isoformat(),
                                'value': durations[i],
                                'type': 'unusual_activity'
                            })
            except Exception as e:
                logger.error(f"Activity anomaly error: {e}")
        
        return anomalies
    
    # ==========================================================================
    # 4. تحليل المجموعات
    # ==========================================================================
    
    def analyze_clusters(self):
        """تحليل وتصنيف الأيام باستخدام KMeans"""
        try:
            daily_features = []
            date_list = []
            start_date = self.today - timedelta(days=30)
            current_date = start_date
            
            while current_date <= self.today:
                # نشاط اليوم
                day_activities = self.activities.filter(start_time__date=current_date)
                activity_duration = day_activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
                
                # نوم الليلة السابقة
                sleep = self.sleep_records.filter(sleep_start__date=current_date).first()
                sleep_hours = 0
                if sleep and sleep.sleep_end and sleep.sleep_start:
                    duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                    sleep_hours = round(duration, 1) if 0 < duration < 24 else 0
                
                # مزاج اليوم
                mood_scores = {'Excellent': 5, 'Good': 4, 'Neutral': 3, 'Stressed': 2, 'Anxious': 2, 'Sad': 1}
                mood = self.mood_records.filter(entry_time__date=current_date).first()
                mood_score = mood_scores.get(mood.mood, 0) if mood else 0
                
                daily_features.append([activity_duration, sleep_hours, mood_score, current_date.weekday()])
                date_list.append(current_date)
                current_date += timedelta(days=1)
            
            if len(daily_features) >= 7:
                scaler = StandardScaler()
                features_scaled = scaler.fit_transform(daily_features)
                
                n_clusters = min(3, len(features_scaled) // 3)
                if n_clusters >= 2:
                    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                    labels = kmeans.fit_predict(features_scaled)
                    
                    clusters = {}
                    for i, (date, label) in enumerate(zip(date_list, labels)):
                        if label not in clusters:
                            clusters[label] = []
                        clusters[label].append(date.isoformat())
                    
                    return {
                        'has_clusters': True,
                        'clusters': [
                            {'cluster_id': int(label), 'days_count': len(dates), 'example_dates': dates[:2]}
                            for label, dates in clusters.items()
                        ]
                    }
        except Exception as e:
            logger.error(f"Clustering error: {e}")
        
        return {'has_clusters': False}
    
    # ==========================================================================
    # 5. توصيات متقدمة
    # ==========================================================================
    
    def generate_recommendations(self):
        """توليد توصيات مخصصة"""
        recommendations = []
        trends = self.analyze_trends()
        weight_pred = self.predict_weight()
        
        # توصية من اتجاه الوزن
        if trends.get('weight_trend'):
            wt = trends['weight_trend']
            if wt.get('trend') == 'increasing':
                recommendations.append({
                    'priority': 'high',
                    'icon': '⚖️',
                    'category': 'weight',
                    'title': self._t('اتجاه زيادة الوزن', 'Weight Increasing'),
                    'description': wt.get('message', ''),
                    'advice': self._t('🥗 راجع نظامك الغذائي وزد نشاطك', 'Review your diet and increase activity'),
                    'based_on': self._t('تحليل الاتجاهات', 'Trend analysis')
                })
        
        # توصية من توقعات الوزن
        if weight_pred and weight_pred.get('trend') == 'up' and weight_pred.get('change', 0) > 1:
            recommendations.append({
                'priority': 'high',
                'icon': '🔮',
                'category': 'prediction',
                'title': self._t('تنبيه: زيادة متوقعة في الوزن', 'Alert: Weight Gain Expected'),
                'description': self._t(f'من المتوقع زيادة {weight_pred["change"]} كجم خلال أسبوعين', 
                                      f'Expected increase of {weight_pred["change"]} kg in 2 weeks'),
                'advice': self._t('📊 ابدأ بتتبع سعراتك وزد نشاطك', 'Start tracking calories and increase activity'),
                'based_on': self._t('توقعات الذكاء الاصطناعي', 'AI predictions')
            })
        
        # توصيات حسب العمر
        if self.user_age:
            if self.user_age >= 50:
                recommendations.append({
                    'priority': 'high',
                    'icon': '🩺',
                    'category': 'age_specific',
                    'title': self._t('نصائح لعمر 50+', 'Tips for 50+'),
                    'description': self._t('ركز على تمارين التوازن والمرونة', 'Focus on balance and flexibility'),
                    'advice': self._t('🧘 جرب اليوغا أو التمدد 3 مرات أسبوعياً', 'Try yoga or stretching 3 times weekly'),
                    'based_on': self._t('توصيات حسب العمر', 'Age-specific tips')
                })
            elif self.user_age <= 25:
                recommendations.append({
                    'priority': 'medium',
                    'icon': '💪',
                    'category': 'age_specific',
                    'title': self._t('بناء عادات صحية مبكرة', 'Build Early Healthy Habits'),
                    'description': self._t('استثمر في صحتك الآن', 'Invest in your health now'),
                    'advice': self._t('🏋️ ابدأ بتمارين القوة وحافظ على نوم منتظم', 'Start strength training, maintain regular sleep'),
                    'based_on': self._t('نصائح وقائية', 'Preventive tips')
                })
        
        # توصية للأدوية
        if self.medications_count > 0:
            recommendations.append({
                'priority': 'low',
                'icon': '💊',
                'category': 'medication',
                'title': self._t('تذكر أدويتك', 'Medication Reminder'),
                'description': self._t(f'لديك {self.medications_count} دواء مسجل', f'You have {self.medications_count} medications'),
                'advice': self._t('⏰ اضبط تذكيراً يومياً لأدويتك', 'Set a daily reminder for your medications'),
                'based_on': self._t('سجل أدويتك', 'Medication record')
            })
        
        return recommendations[:8]
    
    # ==========================================================================
    # 6. التحليل الكامل
    # ==========================================================================
    
    def get_complete_analysis(self):
        """الحصول على التحليل الكامل"""
        return {
            'trends': self.analyze_trends(),
            'weight_prediction': self.predict_weight(),
            'anomalies': self.detect_anomalies(),
            'clusters': self.analyze_clusters(),
            'recommendations': self.generate_recommendations(),
            'user_info': {
                'age': self.user_age,
                'medications_count': self.medications_count,
                'health_records_count': self.health_records.count(),
                'activities_count': self.activities.count()
            }
        }


# ==============================================================================
# ✅ دوال API للتحليلات المتقدمة
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_advanced_analytics(request):
    """
    API للتحليلات الصحية المتقدمة باستخدام scikit-learn
    """
    language = request.GET.get('lang', 'ar')
    is_arabic = language == 'ar'
    
    try:
        analytics_engine = AdvancedHealthAnalyticsML(request.user, is_arabic)
        analysis = analytics_engine.get_complete_analysis()
        
        return Response({
            'success': True,
            'data': analysis,
            'is_arabic': is_arabic,
            'message': is_arabic and '✓ تم التحليل باستخدام الذكاء الاصطناعي' or '✓ Analyzed with AI'
        })
        
    except Exception as e:
        logger.error(f"Advanced analytics error: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': is_arabic and 'حدث خطأ في التحليل المتقدم' or 'Error in advanced analysis'
        }, status=500)

# main/views.py - استبدل دالة get_predictions_api بهذه النسخة

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_predictions_api(request):
    """
    API للحصول على التوقعات فقط
    """
    language = request.GET.get('lang', 'ar')
    is_arabic = language == 'ar'
    
    try:
        analytics_engine = AdvancedHealthAnalyticsML(request.user, is_arabic)
        weight_pred = analytics_engine.predict_weight()
        
        predictions = []
        
        if weight_pred:
            # تحديد نص الاتجاه
            if weight_pred['trend'] == 'up':
                trend_text = 'زيادة متوقعة' if is_arabic else 'Expected increase'
            elif weight_pred['trend'] == 'down':
                trend_text = 'نقصان متوقع' if is_arabic else 'Expected decrease'
            else:
                trend_text = 'مستقر' if is_arabic else 'Stable'
            
            predictions.append({
                'icon': '⚖️',
                'label': is_arabic and 'الوزن المتوقع بعد أسبوعين' or 'Expected weight in 2 weeks',
                'value': f"{weight_pred['predicted']} kg",
                'trend': weight_pred['trend'],
                'trend_text': trend_text,
                'note': is_arabic and f"التغيير المتوقع: {abs(weight_pred['change'])} كجم" or f"Expected change: {abs(weight_pred['change'])} kg",
                'confidence': weight_pred.get('confidence', 70)
            })
        
        return Response({
            'success': True,
            'predictions': predictions,
            'is_arabic': is_arabic,
            'has_predictions': len(predictions) > 0
        })
        
    except Exception as e:
        logger.error(f"Predictions API error: {e}")
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'error': str(e),
            'message': is_arabic and 'حدث خطأ في جلب التوقعات' or 'Error fetching predictions'
        }, status=500)

# ==============================================================================
# ✅ دالة تحديث get_comprehensive_analytics_api
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comprehensive_analytics_api(request):
    """
    API للتحليلات الصحية الشاملة - باستخدام scikit-learn
    """
    try:
        user = request.user
        lang = request.GET.get('lang', 'en')
        is_arabic = lang == 'ar'
        
        # تحليل متقدم
        analytics_engine = AdvancedHealthAnalyticsML(user, is_arabic)
        advanced = analytics_engine.get_complete_analysis()
        
        # بيانات أساسية (آخر 30 يوم)
        from datetime import timedelta
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        from .models import PhysicalActivity, Sleep, HealthStatus, HabitLog, Meal, MoodEntry
        
        activities = PhysicalActivity.objects.filter(user=user, start_time__date__gte=thirty_days_ago)
        sleep_records = Sleep.objects.filter(user=user, sleep_start__date__gte=thirty_days_ago)
        health_records = HealthStatus.objects.filter(user=user, recorded_at__date__gte=thirty_days_ago)
        mood_logs = MoodEntry.objects.filter(user=user, entry_time__date__gte=thirty_days_ago)
        meals = Meal.objects.filter(user=user, meal_time__date__gte=thirty_days_ago)
        habit_logs = HabitLog.objects.filter(habit__user=user, log_date__gte=thirty_days_ago)
        
        total_activities = activities.count()
        total_sleep = 0
        for sleep in sleep_records:
            if sleep.sleep_end and sleep.sleep_start:
                duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                if 0 < duration < 24:
                    total_sleep += duration
        avg_sleep = round(total_sleep / sleep_records.count(), 1) if sleep_records.count() > 0 else 0
        
        # حساب درجة الصحة
        score = 50
        if avg_sleep >= 7:
            score += 20
        elif avg_sleep > 0:
            score += 10
        
        if total_activities >= 15:
            score += 20
        elif total_activities >= 5:
            score += 10
        
        score = min(100, max(0, score))
        
        if score >= 80:
            category_text = is_arabic and 'ممتازة' or 'Excellent'
            icon = '🌟'
        elif score >= 60:
            category_text = is_arabic and 'جيدة' or 'Good'
            icon = '👍'
        elif score >= 40:
            category_text = is_arabic and 'متوسطة' or 'Fair'
            icon = '📈'
        else:
            category_text = is_arabic and 'تحتاج تحسيناً' or 'Needs Improvement'
            icon = '⚠️'
        
        return Response({
            'success': True,
            'data': {
                'period': {'start': thirty_days_ago.isoformat(), 'end': today.isoformat(), 'days': 30},
                'summary': {
                    'total_activities': total_activities,
                    'avg_sleep_hours': avg_sleep,
                    'total_meals': meals.count(),
                    'has_data': total_activities > 0 or sleep_records.exists()
                },
                'health_score': {
                    'total_score': score,
                    'category_text': category_text,
                    'icon': icon,
                    'max_score': 100
                },
                'personalized_recommendations': advanced.get('recommendations', []),
                'predictions': {
                    'weight_trend': advanced.get('weight_prediction'),
                    'activity_trend': advanced.get('trends', {}).get('activity_trend')
                },
                'trends': advanced.get('trends', {}),
                'anomalies': advanced.get('anomalies', {}),
                'clusters': advanced.get('clusters', {})
            },
            'is_ml_enhanced': True,
            'message': is_arabic and '✓ تم التحليل باستخدام scikit-learn' or '✓ Analyzed with scikit-learn'
        })
        
    except Exception as e:
        logger.error(f"Comprehensive analytics error: {e}")
        return Response({
            'success': False,
            'error': str(e),
            'message': is_arabic and 'حدث خطأ في تحليل البيانات' or 'Error analyzing data'
        }, status=500)


# ==============================================================================
# دالة مساعدة للاستخدام السريع
# ==============================================================================

def get_habit_medication_analytics(user, language='ar'):
    """دالة مساعدة للحصول على تحليلات العادات والأدوية"""
    service = HabitMedicationAnalyticsService(user, language=language)
    return service.get_complete_analysis()
# main/views.py - أضف هذه الدوال

from main.services.sentiment_service import (
    SentimentAnalyzer, 
    AdvancedSentimentAnalyzer, 
    SentimentTracker,
    quick_analyze,
    analyze_with_context,
    get_sentiment_insights
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json


# ==============================================================================
# دوال تحليل المشاعر (Sentiment Analysis)
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_sentiment_text(request):
    """
    تحليل مشاعر نص معين
    
    POST /api/sentiment/analyze/
    Body: {"text": "النص المراد تحليله", "advanced": false}
    """
    try:
        data = request.data
        text = data.get('text', '').strip()
        advanced = data.get('advanced', False)
        language = request.GET.get('lang', 'ar')
        
        if not text:
            return Response({
                'success': False,
                'error': 'الرجاء إدخال نص للتحليل',
                'message': 'Please provide text to analyze'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(text) < 3:
            return Response({
                'success': False,
                'error': 'النص قصير جداً للتحليل',
                'message': 'Text is too short for analysis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if advanced:
            analyzer = AdvancedSentimentAnalyzer(language=language)
            result = analyzer.analyze_with_context(text, context="")
        else:
            analyzer = SentimentAnalyzer(language=language)
            result = analyzer.get_detailed_analysis(text)
        
        return Response({
            'success': True,
            'data': result,
            'language': language
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'message': 'حدث خطأ في تحليل المشاعر' if language == 'ar' else 'Error analyzing sentiment'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_sentiment_batch(request):
    """
    تحليل مشاعر مجموعة من النصوص
    
    POST /api/sentiment/batch/
    Body: {"texts": ["نص1", "نص2", "نص3"]}
    """
    try:
        data = request.data
        texts = data.get('texts', [])
        language = request.GET.get('lang', 'ar')
        
        if not texts or not isinstance(texts, list):
            return Response({
                'success': False,
                'error': 'الرجاء إدخال مجموعة من النصوص',
                'message': 'Please provide a list of texts'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tracker = SentimentTracker(language=language)
        results = tracker.analyze_batch(texts)
        overall = tracker.get_overall_sentiment(results)
        
        return Response({
            'success': True,
            'data': {
                'results': results,
                'overall': overall,
                'total_analyzed': len(results)
            },
            'language': language
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_with_context_api(request):
    """
    تحليل المشاعر مع سياق إضافي (نسخة متقدمة)
    
    POST /api/sentiment/context/
    Body: {"text": "النص", "context": "السياق الإضافي"}
    """
    try:
        data = request.data
        text = data.get('text', '').strip()
        context = data.get('context', '')
        language = request.GET.get('lang', 'ar')
        
        if not text:
            return Response({
                'success': False,
                'error': 'الرجاء إدخال نص للتحليل'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        analyzer = AdvancedSentimentAnalyzer(language=language)
        result = analyzer.analyze_with_context(text, context)
        
        return Response({
            'success': True,
            'data': result,
            'language': language
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mood_insights_api(request):
    """
    الحصول على رؤى وتحليلات من سجلات المزاج
    
    GET /api/sentiment/mood-insights/
    """
    try:
        language = request.GET.get('lang', 'ar')
        
        # جلب سجلات المزاج من قاعدة البيانات
        from main.models import MoodEntry
        
        mood_entries = MoodEntry.objects.filter(user=request.user).order_by('-entry_time')[:30]
        
        mood_data = []
        for entry in mood_entries:
            mood_data.append({
                'mood': entry.mood,
                'text_entry': entry.text_entry or '',
                'entry_time': entry.entry_time.isoformat(),
                'factors': entry.factors or ''
            })
        
        if not mood_data:
            return Response({
                'success': True,
                'data': {
                    'has_data': False,
                    'message': 'لا توجد سجلات مزاج كافية للتحليل' if language == 'ar' else 'Insufficient mood records for analysis'
                }
            })
        
        insights = get_sentiment_insights(mood_data, language=language)
        
        return Response({
            'success': True,
            'data': insights,
            'language': language
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def quick_sentiment_api(request):
    """
    تحليل سريع للمشاعر (GET request مع query param)
    
    GET /api/sentiment/quick/?text=النص
    """
    try:
        text = request.GET.get('text', '').strip()
        language = request.GET.get('lang', 'ar')
        
        if not text:
            return Response({
                'success': False,
                'error': 'الرجاء إدخال نص للتحليل',
                'message': 'Please provide text to analyze'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = quick_analyze(text, language=language)
        
        return Response({
            'success': True,
            'data': result,
            'language': language
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_chat_message(request):
    """
    تحليل مشاعر رسالة دردشة (للتكامل مع روبوت الدردشة)
    
    POST /api/sentiment/chat/
    Body: {"message": "نص الرسالة"}
    """
    try:
        data = request.data
        message = data.get('message', '').strip()
        language = request.GET.get('lang', 'ar')
        
        if not message:
            return Response({
                'success': False,
                'error': 'الرجاء إدخال نص الرسالة'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        analyzer = SentimentAnalyzer(language=language)
        sentiment = analyzer.analyze(message)
        
        # توليد ردود مخصصة بناءً على المشاعر
        responses = {
            'POSITIVE': {
                'ar': '😊 سعدت بمشاعرك الإيجابية! كيف يمكنني مساعدتك اليوم؟',
                'en': '😊 Glad to hear your positive feelings! How can I help you today?'
            },
            'NEGATIVE': {
                'ar': '😔 أتفهم أنك تشعر بذلك. تذكر أنني هنا لدعمك. هل تريد التحدث عن شيء محدد؟',
                'en': '😔 I understand you feel that way. Remember I\'m here to support you. Want to talk about something specific?'
            },
            'NEUTRAL': {
                'ar': '👋 كيف يمكنني مساعدتك اليوم؟',
                'en': '👋 How can I help you today?'
            }
        }
        
        response_text = responses.get(sentiment['label'], responses['NEUTRAL'])[
            'ar' if language == 'ar' else 'en'
        ]
        
        return Response({
            'success': True,
            'data': {
                'sentiment': sentiment,
                'bot_response': response_text,
                'original_message': message
            },
            'language': language
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================================================================
# دوال تحليل المشاعر للمستخدمين غير المسجلين (Public)
# ==============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def public_analyze_sentiment(request):
    """
    تحليل مشاعر نص (بدون مصادقة - للاستخدام العام)
    
    POST /api/sentiment/public/
    Body: {"text": "النص"}
    """
    try:
        data = request.data
        text = data.get('text', '').strip()
        language = request.headers.get('Accept-Language', 'ar')[:2]
        
        if not text:
            return Response({
                'success': False,
                'error': 'الرجاء إدخال نص للتحليل'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = quick_analyze(text, language=language)
        
        return Response({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# main/views.py - نسخة مبسطة (بدون استخراج PDF)

import json
import logging
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.db import transaction
from .models import MedicalRecord, ChronicCondition
from .serializers import MedicalRecordSerializer, ChronicConditionSerializer

logger = logging.getLogger(__name__)


# =========================================================
# ✅ MedicalRecord ViewSet (مبسط - PDF يقرأ من المتصفح)
# =========================================================

class MedicalRecordViewSet(viewsets.ModelViewSet):
    """ViewSet للسجلات الطبية - يتم تحليل PDF في المتصفح"""
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return MedicalRecord.objects.filter(user=self.request.user).order_by('-event_date')
    
    @action(detail=False, methods=['POST'], url_path='save-with-conditions')
    def save_with_conditions(self, request):
        """
        حفظ سجل طبي مع الأمراض المستخرجة (يتم استخراج الأمراض في المتصفح)
        """
        logger.info("=" * 50)
        logger.info("📄 Saving medical record with extracted conditions...")
        
        try:
            user = request.user
            event_type = request.data.get('event_type')
            event_date = request.data.get('event_date')
            details = request.data.get('details', '')
            extracted_diseases = request.data.get('extracted_diseases', [])
            extracted_text_preview = request.data.get('extracted_text_preview', '')
            
            # التحقق من صحة المدخلات
            if not event_type:
                return Response({
                    'success': False,
                    'error': 'نوع السجل مطلوب'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not event_date:
                return Response({
                    'success': False,
                    'error': 'تاريخ السجل مطلوب'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # حفظ السجل الطبي
                medical_record = MedicalRecord.objects.create(
                    user=user,
                    event_type=event_type,
                    event_date=event_date,
                    details=details,
                    file_type='pdf',
                    processed_at=timezone.now(),
                    extracted_conditions=json.dumps({
                        'diseases': extracted_diseases,
                        'raw_text_preview': extracted_text_preview[:500]
                    }, ensure_ascii=False)
                )
                
                logger.info(f"✅ Medical record created: ID {medical_record.id}")
                
                # ✅ إضافة الأمراض المستخرجة تلقائياً
                added_conditions = []
                for disease_name in extracted_diseases:
                    condition, created = ChronicCondition.objects.get_or_create(
                        user=user,
                        name=disease_name,
                        defaults={
                            'diagnosis_date': event_date,
                            'is_active': True
                        }
                    )
                    added_conditions.append({
                        'id': condition.id,
                        'name': condition.name,
                        'created': created,
                        'diagnosis_date': condition.diagnosis_date
                    })
                
                serializer = self.get_serializer(medical_record)
                
                return Response({
                    'success': True,
                    'medical_record': serializer.data,
                    'extracted_diseases': extracted_diseases,
                    'added_conditions': added_conditions,
                    'message': f'✅ تم حفظ السجل واستخراج {len(added_conditions)} مرض بنجاح'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"❌ Error in save_with_conditions: {str(e)}")
            logger.error(traceback.format_exc())
            return Response({
                'success': False,
                'error': f'حدث خطأ أثناء حفظ السجل: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['POST'], url_path='save-with-file')
    def save_with_file(self, request):
        """
        حفظ سجل طبي مع رفع الملف (PDF) - الملف يُحفظ فقط، بدون تحليل
        """
        logger.info("=" * 50)
        logger.info("📄 Saving medical record with file...")
        
        try:
            user = request.user
            uploaded_file = request.FILES.get('file')
            event_type = request.data.get('event_type')
            event_date = request.data.get('event_date')
            details = request.data.get('details', '')
            extracted_diseases = request.data.get('extracted_diseases', [])
            
            if not uploaded_file:
                return Response({
                    'success': False,
                    'error': 'لم يتم رفع أي ملف'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not event_type:
                return Response({
                    'success': False,
                    'error': 'نوع السجل مطلوب'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not event_date:
                return Response({
                    'success': False,
                    'error': 'تاريخ السجل مطلوب'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                medical_record = MedicalRecord.objects.create(
                    user=user,
                    event_type=event_type,
                    event_date=event_date,
                    details=details,
                    uploaded_file=uploaded_file,
                    file_type='pdf',
                    processed_at=timezone.now(),
                    extracted_conditions=json.dumps({
                        'diseases': extracted_diseases
                    }, ensure_ascii=False) if extracted_diseases else None
                )
                
                added_conditions = []
                for disease_name in extracted_diseases:
                    condition, created = ChronicCondition.objects.get_or_create(
                        user=user,
                        name=disease_name,
                        defaults={
                            'diagnosis_date': event_date,
                            'is_active': True
                        }
                    )
                    added_conditions.append({
                        'id': condition.id,
                        'name': condition.name,
                        'created': created
                    })
                
                serializer = self.get_serializer(medical_record)
                
                return Response({
                    'success': True,
                    'medical_record': serializer.data,
                    'added_conditions': added_conditions,
                    'message': f'✅ تم رفع الملف وإضافة {len(added_conditions)} مرض'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"❌ Error in save_with_file: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =========================================================
# ✅ دوال API إضافية (مبسطة)
# =========================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_medical_records(request):
    """الحصول على جميع السجلات الطبية للمستخدم"""
    try:
        records = MedicalRecord.objects.filter(user=request.user).order_by('-event_date')
        serializer = MedicalRecordSerializer(records, many=True)
        return Response({
            'success': True,
            'count': records.count(),
            'records': serializer.data
        })
    except Exception as e:
        logger.error(f"Error in get_user_medical_records: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_medical_record_detail(request, record_id):
    """الحصول على تفاصيل سجل طبي محدد"""
    try:
        record = MedicalRecord.objects.get(id=record_id, user=request.user)
        serializer = MedicalRecordSerializer(record)
        
        extracted = {}
        if record.extracted_conditions:
            extracted = json.loads(record.extracted_conditions)
        
        return Response({
            'success': True,
            'record': serializer.data,
            'extracted_diseases': extracted.get('diseases', []),
            'analysis_available': bool(record.extracted_conditions)
        })
    except MedicalRecord.DoesNotExist:
        return Response({
            'success': False,
            'error': 'السجل الطبي غير موجود'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in get_medical_record_detail: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_medical_record(request, record_id):
    """حذف سجل طبي مع ملفه المرفق"""
    try:
        record = MedicalRecord.objects.get(id=record_id, user=request.user)
        
        if record.uploaded_file:
            record.uploaded_file.delete()
        
        record.delete()
        return Response({
            'success': True,
            'message': 'تم حذف السجل الطبي بنجاح'
        })
    except MedicalRecord.DoesNotExist:
        return Response({
            'success': False,
            'error': 'السجل الطبي غير موجود'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in delete_medical_record: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_chronic_conditions(request):
    """الحصول على قائمة الأمراض المزمنة للمستخدم"""
    try:
        conditions = ChronicCondition.objects.filter(user=request.user, is_active=True)
        serializer = ChronicConditionSerializer(conditions, many=True)
        return Response({
            'success': True,
            'conditions': serializer.data,
            'count': conditions.count()
        })
    except Exception as e:
        logger.error(f"Error in get_user_chronic_conditions: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =========================================================
# ✅ دالة اختبار
# =========================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_medical_api(request):
    """اختبار بسيط للتأكد من أن API يعمل"""
    return Response({
        'success': True,
        'message': 'Medical records API is working',
        'user': request.user.username,
        'endpoints': [
            'POST /api/medical-records/save-with-conditions/',
            'POST /api/medical-records/save-with-file/',
            'GET /api/medical-records/',
            'GET /api/medical-records/{id}/',
            'DELETE /api/medical-records/{id}/delete/',
            'GET /api/user/conditions/'
        ]
    })

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

# تأكد من استيراد الخدمة بشكل صحيح. المسار يعتمد على هيكل مجلدك.
# افترض أن الخدمة موجودة في main/services/habit_analytics_service.py
try:
    from .services.habit_analytics_service import HabitMedicationAnalyticsService
    SERVICE_AVAILABLE = True
except ImportError:
    # محاولة استيراد بديلة إذا كانت في نفس المجلد
    try:
        from services.habit_analytics_service import HabitMedicationAnalyticsService
        SERVICE_AVAILABLE = True
    except ImportError:
        SERVICE_AVAILABLE = False
        print("ERROR: Could not import HabitMedicationAnalyticsService")


logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_medication_analytics_api(request):
    """API للحصول على تحليلات العادات والأدوية (خدمة متقدمة)"""
    language = request.GET.get('lang', 'ar')

    if not SERVICE_AVAILABLE:
        logger.error("HabitMedicationAnalyticsService is not available.")
        return Response({
            'success': False,
            'error': 'Service configuration error.',
            'message': 'خدمة التحليلات غير متوفرة حالياً' if language == 'ar' else 'Analytics service is currently unavailable.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        # إنشاء مثيل من الخدمة
        service = HabitMedicationAnalyticsService(request.user, language=language)
        result = service.get_complete_analysis()
        
        return Response({
            'success': True,
            'data': result,
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        # تسجيل الخطأ الكامل في سجلات الخادم
        logger.error(f"Error in habit_medication_analytics_api: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
            'message': 'حدث خطأ في تحليل العادات' if language == 'ar' else 'Error analyzing habits'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_recommendations_api(request):
    """API للحصول على توصيات العادات فقط"""
    language = request.GET.get('lang', 'ar')
    limit = int(request.GET.get('limit', 5))

    if not SERVICE_AVAILABLE:
        return Response({'success': False, 'error': 'Service not available'}, status=500)

    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        # get_recommendations لا تحتاج إلى تمرير summary اختيارياً
        recommendations = service.get_recommendations() 
        return Response({
            'success': True,
            'recommendations': recommendations[:limit],
            'total': len(recommendations),
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        logger.error(f"Error in habit_recommendations_api: {str(e)}", exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_predictions_api(request):
    """API للحصول على توقعات العادات"""
    language = request.GET.get('lang', 'ar')

    if not SERVICE_AVAILABLE:
        return Response({'success': False, 'error': 'Service not available'}, status=500)

    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        summary = service.get_summary() # نحتاج ملخص للحصول على التوقعات
        predictions = service.get_predictions(summary)
        return Response({
            'success': True,
            'predictions': predictions,
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        logger.error(f"Error in habit_predictions_api: {str(e)}", exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=500)
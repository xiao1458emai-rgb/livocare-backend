from rest_framework import serializers
from datetime import datetime, timedelta  # 👈 أضف timedelta هنا
import pytz
from django.utils import timezone  # 👈 أضف هذا السطر
from .models import (
    CustomUser, PhysicalActivity, Sleep, MoodEntry, 
    HealthStatus, Meal, FoodItem, HabitDefinition, 
    HabitLog, HealthGoal, ChronicCondition, MedicalRecord, 
    Recommendation, ChatLog, Notification, EnvironmentData,Medication, UserMedication
)
from django.contrib.auth.hashers import make_password
class UserProfileSerializer(serializers.ModelSerializer):
    """سيرياليزر لعرض وتحديث بيانات المستخدم"""
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'date_of_birth', 'gender', 'phone_number', 
            'initial_weight', 'height', 'occupation_status',
            'health_goal', 'activity_level',           # ✅ أضف هذه
            'chronic_conditions', 'current_medications', # ✅ أضف هذه
            'is_active', 'date_joined'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'is_active']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True}
        }
# 2. Serializer للنشاط البدني
class PhysicalActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalActivity
        exclude = ('user',) 

# 3. Serializer لسجل النوم
class SleepSerializer(serializers.ModelSerializer):
    start_time = serializers.DateTimeField(source='sleep_start')
    end_time = serializers.DateTimeField(source='sleep_end')
    
    class Meta:
        model = Sleep
        fields = ['id', 'start_time', 'end_time', 'quality_rating', 'notes'] 
        read_only_fields = ['user', 'duration_hours'] 

    def create(self, validated_data):
        sleep_start = validated_data.pop('sleep_start')
        sleep_end = validated_data.pop('sleep_end')
        
        duration = sleep_end - sleep_start
        duration_hours = duration.total_seconds() / 3600
        
        sleep_record = Sleep.objects.create(
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            duration_hours=round(duration_hours, 2),
            **validated_data
        )
        return sleep_record
    
# 4. Serializer لسجل الحالة المزاجية
class MoodEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodEntry
        exclude = ('user',) 
      
# 5. القياسات الحيوية (الحالة الصحية)
class HealthStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthStatus
        exclude = ('user',)

# 6. ✅ الوجبات (محدث)
class MealSerializer(serializers.ModelSerializer):
    # ✅ إضافة حقل ingredients
    ingredients = serializers.JSONField(required=False, default=list)
    
    class Meta:
        model = Meal
        # ✅ تحديد الحقول بدلاً من exclude
        fields = [
            'id', 'meal_type', 'meal_time', 'notes',
            'ingredients',
            'total_calories', 'total_protein', 'total_carbs', 'total_fat'
        ]
        # ✅ جعل الإجماليات للقراءة فقط
        read_only_fields = ['total_calories', 'total_protein', 'total_carbs', 'total_fat']

# 7. المكون الغذائي (FoodItem) - للتوافق مع الإصدارات القديمة
class FoodItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = '__all__' 

# 8. تعريف العادة
class HabitDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitDefinition
        exclude = ('user',)

# 9. سجل العادات
class HabitLogSerializer(serializers.ModelSerializer):
    """سيرياليزر لسجل العادات"""
    habit_name = serializers.CharField(source='habit.name', read_only=True)
    habit_description = serializers.CharField(source='habit.description', read_only=True)
    
    class Meta:
        model = HabitLog
        fields = ['id', 'habit', 'habit_name', 'habit_description', 'log_date', 
                  'is_completed', 'actual_value', 'notes']
        read_only_fields = ('id',)
# 10. الهدف الصحي
class HealthGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthGoal
        exclude = ('user',)

# 11. الأمراض المزمنة
class ChronicConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChronicCondition
        exclude = ('user',)

# 12. السجل الطبي
class MedicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        exclude = ('user',)

# 13. التوصيات
class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        exclude = ('user',)
        read_only_fields = ('generated_at', 'is_actioned')

# 14. سجل الدردشة
class ChatLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatLog
        exclude = ('user',)
        read_only_fields = ('timestamp', 'sender', 'sentiment_score')

# 15. الإشعارات
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        exclude = ('user',)
        read_only_fields = ('sent_at', 'is_read')

# 16. البيانات البيئية
class EnvironmentDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvironmentData
        exclude = ('user',)

# 17. تسجيل المستخدم
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'password', 'password2', 'first_name', 'last_name')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "يجب أن تتطابق كلمتا المرور."})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

# 18. ✅ إضافة Serializer للتحليلات (اختياري)
class NutritionInsightsSerializer(serializers.Serializer):
    """Serializer لتحليلات التغذية"""
    total_meals = serializers.IntegerField()
    avg_calories = serializers.FloatField()
    avg_protein = serializers.FloatField()
    avg_carbs = serializers.FloatField()
    avg_fat = serializers.FloatField()
    total_protein = serializers.FloatField()
    total_carbs = serializers.FloatField()
    total_fat = serializers.FloatField()
    meal_distribution = serializers.DictField()
    trend = serializers.CharField()
    recommendations = serializers.ListField()
    date = serializers.CharField()
# في ملف serializers.py - تحديث NotificationSerializer

# ... (باقي الـ serializers كما هي)

# 15. الإشعارات - نسخة محسنة
class NotificationSerializer(serializers.ModelSerializer):
    """
    سيرياليزر محسن للإشعارات مع حقول إضافية
    """
    time_ago = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        # استخدام fields بدلاً من exclude لتحديد الحقول بدقة
        fields = [
            'id', 'type', 'priority', 'icon', 'title', 'message',
            'action_url', 'action_text', 'suggestions',
            'is_read', 'is_archived', 'sent_at', 'read_at', 'expires_at',
            'time_ago', 'is_expired'
        ]
        read_only_fields = ['sent_at', 'read_at']
    
    def get_time_ago(self, obj):
        """حساب الوقت المنقضي منذ الإرسال"""
        if not obj.sent_at:
            return ''
        
        delta = timezone.now() - obj.sent_at
        
        if delta < timedelta(minutes=1):
            return 'الآن'
        elif delta < timedelta(hours=1):
            minutes = int(delta.total_seconds() / 60)
            return f'منذ {minutes} دقيقة'
        elif delta < timedelta(days=1):
            hours = int(delta.total_seconds() / 3600)
            return f'منذ {hours} ساعة'
        elif delta < timedelta(days=7):
            days = delta.days
            return f'منذ {days} يوم'
        else:
            return obj.sent_at.strftime('%Y-%m-%d')
    
    def get_is_expired(self, obj):
        """التحقق مما إذا كان الإشعار منتهي الصلاحية"""
        if obj.expires_at:
            return timezone.now() > obj.expires_at
        return False
    
    def validate(self, data):
        """التحقق من صحة البيانات"""
        if data.get('expires_at') and data.get('sent_at'):
            if data['expires_at'] < data['sent_at']:
                raise serializers.ValidationError(
                    {"expires_at": "تاريخ الانتهاء يجب أن يكون بعد تاريخ الإرسال"}
                )
        return data


# 15.1 سيرياليزر لعدد الإشعارات غير المقروءة
class UnreadCountSerializer(serializers.Serializer):
    """سيرياليزر لعدد الإشعارات غير المقروءة"""
    count = serializers.IntegerField()


# 15.2 سيرياليزر لتحديث حالة الإشعار
class NotificationMarkReadSerializer(serializers.Serializer):
    """سيرياليزر لتحديد إشعار كمقروء"""
    notification_id = serializers.IntegerField(required=True)
    
    def validate_notification_id(self, value):
        """التحقق من وجود الإشعار"""
        if not Notification.objects.filter(id=value).exists():
            raise serializers.ValidationError("الإشعار غير موجود")
        return value


# 15.3 سيرياليزر لإنشاء إشعار جديد (للاستخدام الداخلي)
class NotificationCreateSerializer(serializers.ModelSerializer):
    """سيرياليزر لإنشاء إشعار جديد (للاستخدام من قبل النظام)"""
    
    class Meta:
        model = Notification
        fields = [
            'user', 'type', 'priority', 'icon', 'title', 'message',
            'action_url', 'action_text', 'suggestions', 'expires_at'
        ]
    
    def validate(self, data):
        """التحقق من صحة البيانات قبل الإنشاء"""
        if not data.get('title'):
            raise serializers.ValidationError({"title": "عنوان الإشعار مطلوب"})
        if not data.get('message'):
            raise serializers.ValidationError({"message": "نص الإشعار مطلوب"})
        return data
    
    def create(self, validated_data):
        """إنشاء إشعار جديد"""
        # التحقق من عدم وجود إشعار مكرر اليوم
        user = validated_data.get('user')
        title = validated_data.get('title')
        
        existing = Notification.objects.filter(
            user=user,
            title=title,
            sent_at__date=timezone.now().date()
        ).exists()
        
        if existing:
            raise serializers.ValidationError(
                {"detail": "تم إنشاء هذا الإشعار مسبقاً اليوم"}
            )
        
        return super().create(validated_data)


# 15.4 سيرياليزر لتصفية الإشعارات
class NotificationFilterSerializer(serializers.Serializer):
    """سيرياليزر لتصفية الإشعارات"""
    type = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_TYPES, 
        required=False,
        allow_null=True
    )
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        required=False,
        allow_null=True
    )
    is_read = serializers.BooleanField(required=False, allow_null=True)
    from_date = serializers.DateField(required=False, allow_null=True)
    to_date = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """التحقق من صحة نطاق التاريخ"""
        if data.get('from_date') and data.get('to_date'):
            if data['from_date'] > data['to_date']:
                raise serializers.ValidationError(
                    {"from_date": "تاريخ البداية يجب أن يكون قبل تاريخ النهاية"}
                )
        return data


# 15.5 سيرياليزر لإحصائيات الإشعارات
class NotificationStatsSerializer(serializers.Serializer):
    """سيرياليزر لإحصائيات الإشعارات"""
    total = serializers.IntegerField()
    unread = serializers.IntegerField()
    read = serializers.IntegerField()
    by_type = serializers.DictField()
    by_priority = serializers.DictField()
    last_7_days = serializers.IntegerField()
    last_30_days = serializers.IntegerField()


# 15.6 سيرياليزر لإعدادات الإشعارات (اختياري)
class NotificationPreferencesSerializer(serializers.Serializer):
    """سيرياليزر لإعدادات الإشعارات"""
    enable_health = serializers.BooleanField(default=True)
    enable_nutrition = serializers.BooleanField(default=True)
    enable_sleep = serializers.BooleanField(default=True)
    enable_mood = serializers.BooleanField(default=True)
    enable_habits = serializers.BooleanField(default=True)
    enable_alerts = serializers.BooleanField(default=True)
    enable_reminders = serializers.BooleanField(default=True)
    enable_achievements = serializers.BooleanField(default=True)
    enable_tips = serializers.BooleanField(default=True)
    
    quiet_hours_start = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_end = serializers.TimeField(required=False, allow_null=True)
    
    def validate_quiet_hours(self, data):
        """التحقق من صحة ساعات الهدوء"""
        start = data.get('quiet_hours_start')
        end = data.get('quiet_hours_end')
        
        if start and end and start >= end:
            raise serializers.ValidationError(
                {"quiet_hours_end": "وقت النهاية يجب أن يكون بعد وقت البداية"}
            )
        return data

# 5. القياسات الحيوية (الحالة الصحية) - نسخة محسنة
class HealthStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthStatus
        exclude = ('user',)
        # ✅ أضف read_only_fields للتأكد من إعادة البيانات
        read_only_fields = ('id', 'recorded_at')
    
    def create(self, validated_data):
        """إنشاء سجل صحي جديد وإعادة البيانات كاملة"""
        print(f"📝 HealthStatusSerializer.create - Data: {validated_data}")
        instance = HealthStatus.objects.create(**validated_data)
        print(f"✅ Created instance ID: {instance.id}")
        return instance
    
    def update(self, instance, validated_data):
        """تحديث سجل صحي موجود"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
# ==============================================================================
# 19. سيرياليزر للأدوية (Medication)
# ==============================================================================

class MedicationSerializer(serializers.ModelSerializer):
    """سيرياليزر للأدوية"""
    class Meta:
        model = Medication
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class UserMedicationSerializer(serializers.ModelSerializer):
    """سيرياليزر لأدوية المستخدم"""
    medication_name = serializers.CharField(source='medication.brand_name', read_only=True)
    medication_generic = serializers.CharField(source='medication.generic_name', read_only=True)
    
    class Meta:
        model = UserMedication
        fields = '__all__'
        read_only_fields = ('id', 'created_at')
from django.contrib import admin
from .models import (
    CustomUser, PhysicalActivity, Sleep, MoodEntry, HealthStatus, Meal,
    FoodItem, HabitDefinition, HabitLog, HealthGoal, ChronicCondition,
    MedicalRecord, Recommendation, ChatLog, Notification,EnvironmentData
)

# لإظهار كل النماذج في لوحة الإدارة
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'gender', 'date_of_birth')
    search_fields = ('username', 'email', 'phone_number')
    list_filter = ('gender', 'occupation_status')
    ordering = ('username',)


@admin.register(PhysicalActivity)
class PhysicalActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'duration_minutes', 'start_time')
    list_filter = ('activity_type',)
    search_fields = ('user__username',)


@admin.register(Sleep)
class SleepAdmin(admin.ModelAdmin):
    list_display = ('user', 'sleep_start', 'sleep_end', 'duration_hours', 'quality_rating')
    list_filter = ('quality_rating',)
    search_fields = ('user__username',)


@admin.register(MoodEntry)
class MoodEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'mood', 'entry_time')
    list_filter = ('mood',)
    search_fields = ('user__username',)


@admin.register(HealthStatus)
class HealthStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'recorded_at', 'weight_kg', 'blood_glucose')
    search_fields = ('user__username',)


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ('user', 'meal_type', 'meal_time', 'total_calories')
    list_filter = ('meal_type',)
    search_fields = ('user__username',)


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('meal', 'name', 'quantity', 'unit', 'calories')
    search_fields = ('meal__user__username', 'name')


@admin.register(HabitDefinition)
class HabitDefinitionAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'frequency', 'start_date')
    list_filter = ('frequency',)
    search_fields = ('user__username', 'name')


@admin.register(HabitLog)
class HabitLogAdmin(admin.ModelAdmin):
    list_display = ('habit', 'log_date', 'is_completed', 'actual_value')
    list_filter = ('is_completed',)
    search_fields = ('habit__user__username', 'habit__name')


@admin.register(HealthGoal)
class HealthGoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'target_value', 'current_value', 'unit', 'is_achieved')
    list_filter = ('is_achieved',)
    search_fields = ('user__username', 'title')


@admin.register(ChronicCondition)
class ChronicConditionAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'diagnosis_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'name')


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'event_date')
    search_fields = ('user__username', 'event_type')


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('user', 'recommendation_type', 'generated_at', 'is_actioned')
    list_filter = ('recommendation_type', 'is_actioned')
    search_fields = ('user__username',)


@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'timestamp', 'sender', 'sentiment_score')
    list_filter = ('sender',)
    search_fields = ('user__username',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'sent_at')
    list_filter = ('is_read',)
    search_fields = ('user__username', 'title')

# في نهاية ملف main/admin.py
# -----------------------------------------------------
# تسجيل نموذج البيانات البيئية
# -----------------------------------------------------
@admin.register(EnvironmentData)
class EnvironmentDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'temperature', 'weather_condition', 'mood_at_recording')
    list_filter = ('weather_condition',)
    search_fields = ('user__username', 'date')

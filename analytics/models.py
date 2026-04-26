from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ActivityInsight(models.Model):
    """تحليلات الأنشطة"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    weekly_total_duration = models.FloatField(default=0)
    weekly_total_calories = models.FloatField(default=0)
    recommendations = models.JSONField(default=list)
    
class SleepInsight(models.Model):
    """تحليلات النوم الذكية"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sleep_insights')
    date = models.DateField(auto_now_add=True)
    
    # إحصائيات الأسبوع
    weekly_total_hours = models.FloatField(default=0)
    weekly_avg_hours = models.FloatField(default=0)
    weekly_avg_quality = models.FloatField(default=0)
    
    # المقارنة مع الأسبوع الماضي
    hours_change_percentage = models.FloatField(default=0)
    quality_change_percentage = models.FloatField(default=0)
    
    # التوصيات الذكية
    recommendations = models.JSONField(default=list)
    
    # تحليل الاتجاه
    trend = models.CharField(max_length=20, choices=[
        ('improving', 'في تحسن'),
        ('declining', 'في تراجع'),
        ('stable', 'مستقر'),
        ('insufficient_data', 'بيانات غير كافية')
    ], default='insufficient_data')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']
    
    def __str__(self):
        return f"تحليل نوم {self.user.username} - {self.date}"
class HabitInsight(models.Model):
    """تحليلات العادات الذكية"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habit_insights')
    date = models.DateField(auto_now_add=True)
    
    # إحصائيات عامة
    total_habits = models.IntegerField(default=0)
    completed_today = models.IntegerField(default=0)
    completion_rate = models.FloatField(default=0)
    
    # أفضل العادات
    top_habits = models.JSONField(default=list)
    
    # التوصيات
    recommendations = models.JSONField(default=list)
    
    # الاتجاه
    trend = models.CharField(max_length=20, default='insufficient_data')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']

class MoodInsight(models.Model):
    """تحليلات المزاج الذكية"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mood_insights')
    date = models.DateField(auto_now_add=True)
    
    # إحصائيات عامة
    total_entries = models.IntegerField(default=0)
    total_days = models.IntegerField(default=0)
    most_common_mood = models.CharField(max_length=20, default='')
    
    # توزيع المزاج
    mood_distribution = models.JSONField(default=dict)
    
    # أنماط متكررة
    mood_patterns = models.JSONField(default=list)
    
    # التوصيات
    recommendations = models.JSONField(default=list)
    
    # الاتجاه
    trend = models.CharField(max_length=20, default='insufficient_data')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']

class NutritionInsight(models.Model):
    """تحليلات التغذية الذكية"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='nutrition_insights')
    date = models.DateField(auto_now_add=True)
    
    # إحصائيات عامة
    total_meals = models.IntegerField(default=0)
    total_calories = models.FloatField(default=0)
    total_protein = models.FloatField(default=0)
    total_carbs = models.FloatField(default=0)
    total_fat = models.FloatField(default=0)
    
    # المتوسطات
    avg_calories = models.FloatField(default=0)
    avg_protein = models.FloatField(default=0)
    avg_carbs = models.FloatField(default=0)
    avg_fat = models.FloatField(default=0)
    
    # توزيع الوجبات (إفطار، غداء، عشاء، وجبات خفيفة)
    meal_distribution = models.JSONField(default=dict)
    
    # التوصيات
    recommendations = models.JSONField(default=list)
    
    # الاتجاه
    trend = models.CharField(max_length=20, default='insufficient_data')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']
    
    def __str__(self):
        return f"تحليل تغذية {self.user.username} - {self.date}"
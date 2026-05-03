# analytics/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('activity-insights/', views.get_activity_insights, name='activity-insights'),
    path('sleep-insights/', views.get_sleep_insights, name='sleep-insights'),
    path('model-info/', views.get_model_info, name='model-info'),
    path('habit-insights/', views.get_habit_insights, name='habit-insights'),
    path('mood-insights/', views.get_mood_insights, name='mood-insights'),
    path('nutrition-insights/', views.get_nutrition_insights, name='nutrition-insights'),
    # ✅ أضف هذا السطر الجديد للتحليلات المتقدمة
    path('advanced/', views.get_advanced_analytics, name='advanced-analytics'),
]
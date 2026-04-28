"""
URL configuration for livocare project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from main.views import (
    RegisterUserView, HealthSummaryView, nutrition_insights,
    cron_daily_summary, cron_morning_tip, cron_smart_notifications,
    cron_test_simple
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from analytics import views as analytics_views

urlpatterns = [
    # ==========================================================================
    # 🔐 المصادقة والتسجيل
    # ==========================================================================
    path('api/auth/register/', RegisterUserView.as_view(), name='user_register'),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # ==========================================================================
    # 📊 التحليلات والملخصات
    # ==========================================================================
    path('api/health-summary/', HealthSummaryView.as_view(), name='health-summary'),
    path('api/analytics/sleep-insights/', analytics_views.get_sleep_insights, name='sleep-insights'),
    path('api/analytics/nutrition-insights/', nutrition_insights, name='nutrition-insights'),
    path('api/analytics/activity-insights/', analytics_views.get_activity_insights, name='activity-insights'),
    path('api/analytics/habit-insights/', analytics_views.get_habit_insights, name='habit-insights'),
    path('api/analytics/mood-insights/', analytics_views.get_mood_insights, name='mood-insights'),
    path('api/analytics/advanced/', analytics_views.get_advanced_analytics, name='advanced-analytics'),
    
    # ==========================================================================
    # 🗑️ أدوات مساعدة
    # ==========================================================================
    path('api/chat-logs/clear_all/', analytics_views.clear_all_chat_logs, name='clear-all-chat-logs'),
    path('api/analytics/model-info/', analytics_views.get_model_info, name='model-info'),
    
    # ==========================================================================
    # 🖥️ لوحة الإدارة
    # ==========================================================================
    path('admin/', admin.site.urls),
    
    # ==========================================================================
    # 📁 باقي المسارات (main app)
    # ==========================================================================
    path('api/', include('main.urls')),
    
    # ==========================================================================
    # 🤖 مسارات Cron Jobs (بدون مصادقة)
    # ==========================================================================
    path('cron/daily-summary/', cron_daily_summary, name='cron-daily-summary'),
    path('cron/morning-tip/', cron_morning_tip, name='cron-morning-tip'),
    path('cron/smart-notifications/', cron_smart_notifications, name='cron-smart-notifications'),
    path('cron/test/', cron_test_simple, name='cron-test'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
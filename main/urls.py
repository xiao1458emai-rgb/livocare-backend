# main/urls.py - النسخة النهائية المصححة (بدون تضارب في المسارات)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView 
from django.http import JsonResponse  
from main.views import (
    # ✅ جميع الدوال المستوردة
    scan_barcode, advanced_cross_insights, cross_insights, google_auth,
    trigger_notifications, generate_notifications_now,
    push_subscribe,
    RegisterUserView,
    manage_profile, change_password, delete_my_account,
    export_all_data, backup_data, restore_backup,
    user_settings, manage_goals,
    create_notification, get_notifications,
    mark_notification_read, mark_all_notifications_read,
    delete_notification, delete_all_read_notifications,
    get_my_notifications, get_notifications_simple, create_test_notifications,
    save_notification_from_sw, send_push_notification,
    check_and_send_smart_notifications, send_daily_summary_notification,
    send_morning_tip, send_notifications_to_all_users,
    cron_daily_summary, cron_morning_tip, cron_smart_notifications,
    cron_test_simple,
    get_weather, search_food, suggest_exercises, analyze_sentiment,
    get_smart_recommendations,
    search_medication, get_medication_details, get_user_medications,
    add_user_medication, delete_user_medication,
    get_user_achievements, test_websocket, smart_insights,
    # ✅ دوال ESP32
    esp32_update_health_status,
    esp32_get_latest_health_status,
    esp32_get_health_history,
)
from main import views

# =========================================================
# ✅ إنشاء الـ Router
# =========================================================
router = DefaultRouter()
router.register(r'activities', views.PhysicalActivityViewSet, basename='activities')
router.register(r'sleep', views.SleepViewSet, basename='sleep')
router.register(r'mood-logs', views.MoodEntryViewSet, basename='mood') 
router.register(r'health_status', views.HealthStatusViewSet, basename='health_status')
router.register(r'meals', views.MealViewSet, basename='meals')
router.register(r'food-items', views.FoodItemViewSet, basename='food-items')
router.register(r'habit-definitions', views.HabitDefinitionViewSet, basename='habit-definitions')
router.register(r'habit-logs', views.HabitLogViewSet, basename='habit-logs')
router.register(r'goals', views.HealthGoalViewSet, basename='goals')
router.register(r'conditions', views.ChronicConditionViewSet, basename='conditions')
router.register(r'medical-records', views.MedicalRecordViewSet, basename='medical-records')
router.register(r'recommendations', views.RecommendationViewSet, basename='recommendations')
router.register(r'chat-logs', views.ChatLogViewSet, basename='chat-logs')
router.register(r'notifications', views.NotificationViewSet, basename='notifications')
router.register(r'environment-data', views.EnvironmentDataViewSet, basename='environment-data')

# =========================================================
# ✅ مسارات ESP32
# =========================================================
esp32_urls = [
    path('esp32/update/', esp32_update_health_status, name='esp32-update'),
    path('esp32/latest/', esp32_get_latest_health_status, name='esp32-latest'),
    path('esp32/history/', esp32_get_health_history, name='esp32-history'),
]

# =========================================================
# ✅ المسارات الأساسية
# =========================================================
base_urls = [
    # 🔐 مصادقة Google
    path('auth/google/', google_auth, name='google_auth'), 
    
    # 🧠 التحليلات الذكية
    path('advanced-insights/', advanced_cross_insights, name='advanced-insights'),
    path('cross-insights/', cross_insights, name='cross-insights'),
    path('analytics/smart-insights/', smart_insights, name='smart-insights'),
    path('analytics/cross-insights/', cross_insights, name='cross-insights-alt'),
    path('blood-sugar/', views.get_blood_sugar, name='blood-sugar'),
    
    # 🌤️ الطقس
    path('weather/', get_weather, name='weather'),
    
    # 🥗 التغذية والبحث عن الطعام
    path('food/search/', search_food, name='food-search'),
    
    # 💪 التمارين الرياضية
    path('exercises/suggest/', suggest_exercises, name='exercise-suggest'),
    
    # 😊 تحليل المشاعر
    path('sentiment/analyze/', analyze_sentiment, name='sentiment-analyze'),
    
    # 💡 التوصيات الذكية
    path('smart-recommendations/', get_smart_recommendations, name='smart-recommendations'),
    
    # 📊 التقارير
    path('reports/all-data/', views.get_all_reports_data, name='reports-all-data'),
    path('health-summary/', views.HealthSummaryView.as_view(), name='health-summary'),
    
    # 📷 ماسح الباركود
    path('scan-barcode/', scan_barcode, name='scan-barcode'),
    
    # 🩺 الأدوية
    path('medications/search/', search_medication, name='search-medication'),
    path('medications/<int:medication_id>/', get_medication_details, name='medication-details'),
    path('medications/user/', get_user_medications, name='user-medications'),
    path('medications/user/add/', add_user_medication, name='add-user-medication'),
    path('medications/user/<int:user_med_id>/delete/', delete_user_medication, name='delete-user-medication'),
    
    # 📱 Push Notifications
    path('push-subscribe/', push_subscribe, name='push-subscribe'),
    path('send-push/', send_push_notification, name='send-push'),
    path('achievements/', get_user_achievements, name='achievements'),
    
    # 👤 إدارة الحساب
    path('profile/', manage_profile, name='manage_profile'),
    path('change-password/', change_password, name='change_password'),
    path('delete-account/', delete_my_account, name='delete_account'),
    path('export-data/', export_all_data, name='export_data'),
    path('backup/', backup_data, name='backup_data'),
    path('restore/', restore_backup, name='restore_backup'),
    path('settings/', user_settings, name='user_settings'),
    path('goals/', manage_goals, name='manage_goals'),
    
    # 🔔 إشعارات داخل التطبيق
    path('notifications/create/', create_notification, name='create-notification'),
    path('notifications/get/', get_notifications, name='get-notifications'),
    path('notifications/simple/', get_notifications_simple, name='notifications-simple'),
    path('notifications/create-test/', create_test_notifications, name='create-test-notifications'),
    path('notifications/<int:notification_id>/mark-read/', mark_notification_read, name='mark-notification-read'),
    path('notifications/mark-all-read/', mark_all_notifications_read, name='mark-all-notifications-read'),
    path('notifications/<int:notification_id>/delete/', delete_notification, name='delete-notification'),
    path('notifications/delete-all-read/', delete_all_read_notifications, name='delete-all-read-notifications'),
    path('my-notifications/', get_my_notifications, name='my-notifications'),
    path('sw-notification/', save_notification_from_sw, name='sw-notification'),
    
    # 🤖 إشعارات ذكية
    path('smart-notifications/', check_and_send_smart_notifications, name='smart-notifications'),
    path('daily-summary/', send_daily_summary_notification, name='daily-summary'),
    path('morning-tip/', send_morning_tip, name='morning-tip'),
    path('notify-all-users/', send_notifications_to_all_users, name='notify-all-users'),
    path('generate-notifications/', generate_notifications_now, name='generate-notifications'),
    
    # 🧪 اختبارات
    path('test-simple/', lambda request: JsonResponse({'status': 'ok', 'message': 'Test endpoint works!'}), name='test-simple'),
    path('test-websocket/', test_websocket, name='test-websocket'),
]

# =========================================================
# ✅ دمج جميع المسارات (بدون مسارات مكررة)
# =========================================================
urlpatterns = [
    path('', include(router.urls)),
    *esp32_urls,
    *base_urls,
]

# =========================================================
# ✅ معالجة الأخطاء
# =========================================================
def handler404(request, exception):
    from main.views import get_request_language
    is_arabic = get_request_language(request) == 'ar'
    return JsonResponse({
        'success': False,
        'error': 'الصفحة غير موجودة' if is_arabic else 'Page not found',
        'language': 'ar' if is_arabic else 'en'
    }, status=404)

def handler500(request):
    from main.views import get_request_language
    is_arabic = get_request_language(request) == 'ar'
    return JsonResponse({
        'success': False,
        'error': 'خطأ في الخادم الداخلي' if is_arabic else 'Internal server error',
        'language': 'ar' if is_arabic else 'en'
    }, status=500)
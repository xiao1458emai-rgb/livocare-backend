# main/tasks.py
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from .models import CustomUser, Notification, PhysicalActivity, Meal, Sleep
import requests

@shared_task
def send_daily_summary_notifications():
    """إرسال إشعارات ملخص اليوم لجميع المستخدمين في الساعة 8 مساءً"""
    
    today = timezone.now().date()
    users = CustomUser.objects.all()
    
    created_count = 0
    
    for user in users:
        # 1. جلب بيانات النشاط اليوم
        activities = PhysicalActivity.objects.filter(
            user=user, 
            start_time__date=today
        )
        total_minutes = activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        total_calories_burned = activities.aggregate(Sum('calories_burned'))['calories_burned__sum'] or 0
        
        # 2. جلب بيانات الوجبات
        meals = Meal.objects.filter(user=user, meal_time__date=today)
        total_calories_consumed = meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0
        
        # 3. جلب بيانات النوم
        sleep = Sleep.objects.filter(user=user, sleep_start__date=today).first()
        sleep_hours = sleep.duration_hours if sleep else 0
        
        # 4. بناء رسالة الإشعار
        message = f"📊 **ملخص يومك**\n\n"
        message += f"🚶 النشاط البدني: {total_minutes} دقيقة\n"
        message += f"🔥 السعرات المحروقة: {total_calories_burned}\n"
        message += f"🍽️ السعرات المتناولة: {total_calories_consumed}\n"
        
        if sleep_hours:
            message += f"😴 النوم: {sleep_hours} ساعات\n"
        
        # 5. إضافة تنبيهات
        if total_minutes < 30:
            message += f"\n⚠️ نشاطك اليومي منخفض! حاول المشي 30 دقيقة غداً."
        
        if total_calories_consumed < 1200:
            message += f"\n⚠️ سعراتك الحرارية منخفضة! تناول وجبات متوازنة."
        
        if sleep_hours and sleep_hours < 7:
            message += f"\n⚠️ نمط نومك غير كافٍ! حاول النوم مبكراً."
        
        # 6. حفظ الإشعار
        Notification.objects.create(
            user=user,
            title="🌙 ملخص يومك",
            message=message,
            type="summary",
            priority="medium",
            action_url="/dashboard",
            is_read=False
        )
        
        created_count += 1
        
        # 7. إرسال Push Notification (اختياري)
        send_push_notification(user.id, "🌙 ملخص يومك", message)
    
    return f"✅ تم إنشاء {created_count} إشعار ملخص يومي"

def send_push_notification(user_id, title, message):
    """إرسال إشعار فوري عبر خدمة الإشعارات"""
    try:
        requests.post(
            'https://notification-service-6nzm.onrender.com/notify/all',
            json={
                'title': title,
                'body': message[:200],  # اختصار الرسالة
                'url': '/notifications'
            },
            timeout=5
        )
    except Exception as e:
        print(f"Push notification error: {e}")


@shared_task
def send_meal_reminder():
    """إرسال تذكير بالوجبات في أوقات محددة"""
    now = timezone.now()
    current_hour = now.hour
    
    meal_type = None
    if current_hour == 8:
        meal_type = "🍳 الإفطار"
    elif current_hour == 13:
        meal_type = "🍲 الغداء"
    elif current_hour == 19:
        meal_type = "🍽️ العشاء"
    else:
        return "ليس وقت تذكير"
    
    users = CustomUser.objects.all()
    created_count = 0
    
    for user in users:
        Notification.objects.create(
            user=user,
            title=f"⏰ تذكير بـ {meal_type}",
            message=f"حان وقت {meal_type}! لا تنسَ تسجيل وجبتك الصحية.",
            type="reminder",
            priority="medium",
            action_url="/nutrition",
            is_read=False
        )
        created_count += 1
    
    return f"✅ تم إرسال {created_count} تذكير بـ {meal_type}"


@shared_task
def send_sleep_reminder():
    """تذكير بموعد النوم"""
    users = CustomUser.objects.all()
    created_count = 0
    
    for user in users:
        Notification.objects.create(
            user=user,
            title="🌙 وقت النوم",
            message="حان وقت النوم! النوم الكافي يحسن صحتك ونشاطك غداً.",
            type="reminder",
            priority="medium",
            action_url="/sleep",
            is_read=False
        )
        created_count += 1
    
    return f"✅ تم إرسال {created_count} تذكير بالنوم"
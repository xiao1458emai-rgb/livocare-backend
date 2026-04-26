# main/services/notification_service.py
import logging
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count, Avg, Sum
from django.contrib.auth import get_user_model
import random
import requests
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
User = get_user_model()

# ✅ روابط الخدمات الخارجية
NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL', 'https://notification-service-2xej.onrender.com')
EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'https://email-service-zc0r.onrender.com')

# ✅ نطاق التطبيق للروابط
APP_URL = os.environ.get('APP_URL', 'https://livocare-fronend.onrender.com')


class NotificationService:
    """خدمة إنشاء وإرسال الإشعارات التلقائية"""

    # ✅ قاموس الترجمة المركزي
    TRANSLATIONS = {
        # تنبيهات الوزن
        'high_weight_title': {'ar': '⚠️ ارتفاع الوزن', 'en': '⚠️ High Weight'},
        'high_weight_message': {'ar': 'وزنك {weight} كجم أعلى من المعدل الطبيعي', 'en': 'Your weight {weight} kg is above normal range'},
        'low_weight_title': {'ar': '⚠️ نقص الوزن', 'en': '⚠️ Low Weight'},
        'low_weight_message': {'ar': 'وزنك {weight} كجم أقل من المعدل الطبيعي', 'en': 'Your weight {weight} kg is below normal range'},
        
        # تنبيهات ضغط الدم
        'high_bp_title': {'ar': '⚠️ ضغط الدم مرتفع', 'en': '⚠️ High Blood Pressure'},
        'high_bp_message': {'ar': 'ضغطك {bp} mmHg', 'en': 'Your blood pressure is {bp} mmHg'},
        'low_bp_title': {'ar': '⚠️ ضغط الدم منخفض', 'en': '⚠️ Low Blood Pressure'},
        'low_bp_message': {'ar': 'ضغطك {bp} mmHg', 'en': 'Your blood pressure is {bp} mmHg'},
        
        # تنبيهات السكر
        'high_glucose_title': {'ar': '⚠️ ارتفاع السكر', 'en': '⚠️ High Blood Sugar'},
        'high_glucose_message': {'ar': 'نسبة السكر {glucose} mg/dL', 'en': 'Blood sugar level {glucose} mg/dL'},
        'low_glucose_title': {'ar': '🚨 انخفاض السكر', 'en': '🚨 Low Blood Sugar'},
        'low_glucose_message': {'ar': 'نسبة السكر {glucose} mg/dL', 'en': 'Blood sugar level {glucose} mg/dL'},
        
        # تنبيهات النوم
        'sleep_time_title': {'ar': '🌙 وقت النوم', 'en': '🌙 Bedtime'},
        'sleep_time_message': {'ar': 'حان وقت الاستعداد للنوم', 'en': 'Time to prepare for sleep'},
        'lack_sleep_title': {'ar': '😴 قلة النوم', 'en': '😴 Lack of Sleep'},
        'lack_sleep_message': {'ar': 'نمتَ {hours} ساعات فقط الليلة الماضية', 'en': 'You slept only {hours} hours last night'},
        'long_sleep_title': {'ar': '😴 نوم طويل', 'en': '😴 Long Sleep'},
        'long_sleep_message': {'ar': 'نمتَ {hours} ساعات', 'en': 'You slept {hours} hours'},
        
        # تنبيهات العادات
        'habit_reminder_title': {'ar': '💊 تذكير: {habit}', 'en': '💊 Reminder: {habit}'},
        'habit_reminder_message': {'ar': 'لم تسجل هذه العادة اليوم', 'en': 'You haven\'t logged this habit today'},
        
        # تنبيهات التغذية
        'breakfast_title': {'ar': '🌅 وجبة الإفطار', 'en': '🌅 Breakfast'},
        'breakfast_message': {'ar': 'لا تنسى وجبة الإفطار لبدء يومك بنشاط', 'en': 'Don\'t forget breakfast to start your day actively'},
        'lunch_title': {'ar': '☀️ وجبة الغداء', 'en': '☀️ Lunch'},
        'lunch_message': {'ar': 'حان وقت الغداء', 'en': 'Time for lunch'},
        'dinner_title': {'ar': '🌙 وجبة العشاء', 'en': '🌙 Dinner'},
        'dinner_message': {'ar': 'وجبة خفيفة قبل النوم', 'en': 'Light meal before bed'},
        
        # تنبيهات النشاط
        'activity_title': {'ar': '🚶 وقت النشاط', 'en': '🚶 Activity Time'},
        'activity_message': {'ar': 'لم تمارس أي نشاط بدني اليوم', 'en': 'You haven\'t done any physical activity today'},
        
        # إنجازات
        'achievement_health_title': {'ar': '🏆 {count} قراءة صحية!', 'en': '🏆 {count} Health Readings!'},
        'achievement_health_message': {'ar': 'مبروك! لقد سجلت {count} قراءة صحية', 'en': 'Congratulations! You\'ve logged {count} health readings'},
        'achievement_sleep_title': {'ar': '🌙 {weeks} أسابيع من تتبع النوم', 'en': '🌙 {weeks} Weeks of Sleep Tracking'},
        'achievement_sleep_message': {'ar': 'أكملت {nights} ليلة من تتبع نومك', 'en': 'You\'ve completed {nights} nights of sleep tracking'},
        
        # نصائح يومية
        'tip_water_title': {'ar': '💧 شرب الماء', 'en': '💧 Drink Water'},
        'tip_water_message': {'ar': 'اشرب كوباً من الماء قبل كل وجبة للمساعدة على الهضم', 'en': 'Drink a glass of water before each meal to aid digestion'},
        'tip_sleep_title': {'ar': '😴 النوم الجيد', 'en': '😴 Good Sleep'},
        'tip_sleep_message': {'ar': 'تجنب الشاشات قبل النوم بساعة لتحسين جودة النوم', 'en': 'Avoid screens an hour before bed to improve sleep quality'},
        'tip_walk_title': {'ar': '🚶 الحركة', 'en': '🚶 Movement'},
        'tip_walk_message': {'ar': 'المشي 10 دقائق بعد الأكل يساعد على الهضم ويحسن المزاج', 'en': 'Walking 10 minutes after meals aids digestion and improves mood'},
        'tip_nutrition_title': {'ar': '🥗 التغذية', 'en': '🥗 Nutrition'},
        'tip_nutrition_message': {'ar': 'أضف لوناً جديداً من الخضروات إلى وجبتك اليوم', 'en': 'Add a new color of vegetables to your daily meal'},
        'tip_meditation_title': {'ar': '🧘 التأمل', 'en': '🧘 Meditation'},
        'tip_meditation_message': {'ar': 'خذ 5 دقائق للتأمل والتنفس العميق لتقليل التوتر', 'en': 'Take 5 minutes for meditation and deep breathing to reduce stress'},
        'tip_journal_title': {'ar': '📝 اليوميات', 'en': '📝 Journaling'},
        'tip_journal_message': {'ar': 'دوّن 3 أشياء تشعر بالامتنان لها اليوم', 'en': 'Write down 3 things you\'re grateful for today'},
        'tip_stairs_title': {'ar': '🏃 النشاط', 'en': '🏃 Activity'},
        'tip_stairs_message': {'ar': 'حاول صعود الدرج بدلاً من المصعد لزيادة نشاطك', 'en': 'Try taking the stairs instead of the elevator to increase activity'},
        'tip_fruit_title': {'ar': '🍎 الفواكه', 'en': '🍎 Fruits'},
        'tip_fruit_message': {'ar': 'تناول فاكهة طازجة بدلاً من العصائر المعلبة', 'en': 'Eat fresh fruit instead of canned juices'},
        'tip_motivation_title': {'ar': '🌟 تحفيز', 'en': '🌟 Motivation'},
        'tip_motivation_message': {'ar': 'الاستمرارية أهم من الكمال. استمر في رحلتك الصحية!', 'en': 'Consistency is more important than perfection. Continue your health journey!'},
        
        # نصوص عامة
        'view_readings': {'ar': 'عرض القراءات', 'en': 'View Readings'},
        'view_details': {'ar': 'عرض التفاصيل', 'en': 'View Details'},
        'log_reading': {'ar': 'تسجيل قراءة جديدة', 'en': 'Log New Reading'},
        'log_sleep': {'ar': 'تسجيل النوم', 'en': 'Log Sleep'},
        'sleep_analysis': {'ar': 'تحليل النوم', 'en': 'Sleep Analysis'},
        'log_now': {'ar': 'سجل الآن', 'en': 'Log Now'},
        'log_meal': {'ar': 'تسجيل وجبة', 'en': 'Log Meal'},
        'log_activity': {'ar': 'تسجيل نشاط', 'en': 'Log Activity'},
        'share_achievement': {'ar': 'شارك إنجازك مع الأصدقاء', 'en': 'Share your achievement with friends'},
        'tracking_continue': {'ar': 'استمر في تتبع صحتك', 'en': 'Continue tracking your health'},
    }
    
    # ✅ قوائم الاقتراحات المترجمة
    SUGGESTIONS = {
        'high_weight': {
            'ar': ['استشر أخصائي تغذية', 'زد نشاطك البدني', 'قلل السكريات والدهون'],
            'en': ['Consult a nutritionist', 'Increase physical activity', 'Reduce sugars and fats']
        },
        'low_weight': {
            'ar': ['تحتاج تغذية غنية بالسعرات', 'استشر أخصائي تغذية', 'أضف وجبات خفيفة صحية'],
            'en': ['Need calorie-rich nutrition', 'Consult a nutritionist', 'Add healthy snacks']
        },
        'high_bp': {
            'ar': ['قلل الملح في الطعام', 'مارس المشي يومياً', 'استشر طبيباً للمتابعة'],
            'en': ['Reduce salt in food', 'Walk daily', 'Consult a doctor for follow-up']
        },
        'low_bp': {
            'ar': ['اشرب كمية كافية من الماء', 'تناول وجبات صغيرة متكررة', 'استشر طبيباً إذا استمر الانخفاض'],
            'en': ['Drink enough water', 'Eat small frequent meals', 'Consult a doctor if it persists']
        },
        'high_glucose': {
            'ar': ['قلل الحلويات والمشروبات السكرية', 'تناول وجبات صغيرة متعددة', 'مارس الرياضة بانتظام'],
            'en': ['Reduce sweets and sugary drinks', 'Eat small frequent meals', 'Exercise regularly']
        },
        'low_glucose': {
            'ar': ['تناول عصير فواكه طبيعي', 'كل تمرة أو قطعة حلوى صغيرة', 'لا تتأخر في وجباتك'],
            'en': ['Drink natural fruit juice', 'Eat a date or small candy', 'Don\'t delay your meals']
        },
        'sleep_time': {
            'ar': ['أطفئ الأضواء الزرقاء من الشاشات', 'اشرب كوباً من الشاي العشبي', 'اجعل غرفتك مظلمة وباردة'],
            'en': ['Turn off blue lights from screens', 'Drink a cup of herbal tea', 'Keep your room dark and cool']
        },
        'lack_sleep': {
            'ar': ['حاول النوم مبكراً الليلة', 'تجنب الكافيين بعد الساعة 4 مساءً', 'مارس نشاطاً مريحاً قبل النوم'],
            'en': ['Try to sleep earlier tonight', 'Avoid caffeine after 4 PM', 'Do relaxing activities before bed']
        },
        'long_sleep': {
            'ar': ['النوم الطويل قد يسبب الخمول', 'حاول تنظيم مواعيد نومك', 'استيقظ في وقت ثابت يومياً'],
            'en': ['Long sleep may cause lethargy', 'Try to organize your sleep schedule', 'Wake up at a fixed time daily']
        },
        'habit': {
            'ar': ['خذ دقيقة لتسجيل عادتك', 'حافظ على اتساق عاداتك اليومية'],
            'en': ['Take a minute to log your habit', 'Keep your daily habits consistent']
        },
        'breakfast': {
            'ar': ['🥚 بيض مع خبز أسمر', '🥣 شوفان مع فواكه', '🥑 توست مع أفوكادو'],
            'en': ['🥚 Eggs with whole wheat bread', '🥣 Oatmeal with fruits', '🥑 Avocado toast']
        },
        'lunch': {
            'ar': ['🍗 بروتين (دجاج/سمك)', '🥗 سلطة خضراء', '🍚 كربوهيدرات صحية'],
            'en': ['🍗 Protein (chicken/fish)', '🥗 Green salad', '🍚 Healthy carbs']
        },
        'dinner': {
            'ar': ['🥛 زبادي مع فواكه', '🍎 تفاح أو موز', '🌿 شاي أعشاب مهدئ'],
            'en': ['🥛 Yogurt with fruits', '🍎 Apple or banana', '🌿 Soothing herbal tea']
        },
        'activity': {
            'ar': ['🚶 امشِ 20-30 دقيقة', '🧘 تمارين تمدد خفيفة', '🏃 جرب تمريناً سريعاً لمدة 10 دقائق'],
            'en': ['🚶 Walk 20-30 minutes', '🧘 Light stretching exercises', '🏃 Try a quick 10-minute workout']
        },
        'achievement': {
            'ar': ['استمر في تتبع صحتك', 'شارك إنجازك مع الأصدقاء'],
            'en': ['Continue tracking your health', 'Share your achievement with friends']
        }
    }

    @staticmethod
    def _get_text(key: str, is_arabic: bool = True, **kwargs) -> str:
        """الحصول على النص المترجم حسب اللغة"""
        text_data = NotificationService.TRANSLATIONS.get(key, {})
        text = text_data.get('ar' if is_arabic else 'en', key)
        
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text

    @staticmethod
    def _get_suggestions(key: str, is_arabic: bool = True) -> List[str]:
        """الحصول على قائمة الاقتراحات المترجمة"""
        suggestions_data = NotificationService.SUGGESTIONS.get(key, {})
        return suggestions_data.get('ar' if is_arabic else 'en', [])

    @staticmethod
    def _get_user_language(user, request=None) -> bool:
        """
        استرجاع لغة المستخدم من:
        1. الطلب (request headers أو query params)
        2. ملف تعريف المستخدم (profile)
        3. افتراضي العربية
        """
        # 1. من الطلب (إذا وجد)
        if request:
            # من header
            lang_header = request.headers.get('Accept-Language', '')
            if lang_header:
                if lang_header.startswith('en'):
                    return False  # English
                elif lang_header.startswith('ar'):
                    return True   # Arabic
            
            # من query params
            lang_param = request.GET.get('lang')
            if lang_param:
                return lang_param == 'ar'
        
        # 2. من ملف تعريف المستخدم
        try:
            if hasattr(user, 'profile') and user.profile.language:
                return user.profile.language == 'ar'
        except:
            pass
        
        # 3. افتراضياً العربية
        return True

    @staticmethod
    def send_push_notification(user, title: str, message: str, icon: str = None, url: str = '/', priority: str = 'normal'):
        """إرسال إشعار فوري عبر الخدمة المستقلة"""
        if not user or not user.is_active:
            return False
        
        try:
            payload = {
                'user_id': user.id,
                'title': title,
                'body': message,
                'icon': icon or '/logo192.png',
                'url': url,
                'priority': priority
            }
            
            response = requests.post(
                f'{NOTIFICATION_SERVICE_URL}/api/notify/',
                json=payload,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"📱 Push sent to {user.username}: {title}")
                return True
            else:
                logger.warning(f"❌ Push failed for {user.username}: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Push timeout for {user.username}")
            return False
        except Exception as e:
            logger.error(f"❌ Push error for {user.username}: {e}")
            return False

    @staticmethod
    def send_email_notification(user, title: str, message: str, is_arabic=True):
        """إرسال إشعار عبر خدمة البريد المستقلة"""
        if not user or not user.email:
            logger.warning(f"❌ No email for {user.username if user else 'Unknown'}")
            return False
        
        app_name = 'LivoCare'
        visit_text = NotificationService._get_text('visit_text', is_arabic) or ('زيارة التطبيق' if is_arabic else 'Visit App')
        auto_notice = NotificationService._get_text('auto_notice', is_arabic) or ('هذا إشعار تلقائي من تطبيق LivoCare' if is_arabic else 'This is an automated notification from LivoCare')
        
        try:
            payload = {
                'to': user.email,
                'subject': f'🔔 {app_name}: {title}',
                'message': f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #4F46E5;">🔔 {title}</h2>
                    <p style="font-size: 16px; line-height: 1.5;">{message}</p>
                    <hr style="margin: 20px 0;">
                    <p style="color: #666; font-size: 12px;">
                        {auto_notice}<br>
                        <a href="{APP_URL}" style="color: #4F46E5;">{visit_text}</a>
                    </p>
                </div>
                """,
                'html': True
            }
            
            response = requests.post(
                f'{EMAIL_SERVICE_URL}/api/send/',
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"📧 Email sent to {user.email}: {title}")
                return True
            else:
                logger.warning(f"❌ Email failed for {user.email}: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Email timeout for {user.email}")
            return False
        except Exception as e:
            logger.error(f"❌ Email error for {user.email}: {e}")
            return False

    @staticmethod
    def save_notification(user, notif_data: Dict[str, Any]) -> bool:
        """حفظ الإشعار في قاعدة البيانات"""
        from main.models import Notification
        
        try:
            # التحقق من عدم وجود إشعار مكرر خلال الـ 6 ساعات الماضية
            six_hours_ago = timezone.now() - timedelta(hours=6)
            exists = Notification.objects.filter(
                user=user,
                type=notif_data.get('type', 'alert'),
                title=notif_data.get('title', ''),
                sent_at__gte=six_hours_ago
            ).exists()
            
            if exists:
                logger.debug(f"Duplicate notification skipped: {notif_data.get('title')}")
                return False
            
            Notification.objects.create(
                user=user,
                sent_at=timezone.now(),
                is_read=False,
                is_archived=False,
                **notif_data
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save notification: {e}")
            return False

    # =========================================================
    # 1. التنبيهات الصحية (مترجمة)
    # =========================================================
    
    @staticmethod
    def check_health_alerts(user, request=None) -> List[Dict[str, Any]]:
        """فحص التنبيهات الصحية"""
        from main.models import HealthStatus
        
        is_arabic = NotificationService._get_user_language(user, request)
        notifications = []
        latest = HealthStatus.objects.filter(user=user).order_by('-recorded_at').first()
        
        if not latest:
            return notifications
        
        # 1. فحص الوزن
        if latest.weight_kg:
            weight = float(latest.weight_kg)
            
            if weight > 100:
                title = NotificationService._get_text('high_weight_title', is_arabic)
                message = NotificationService._get_text('high_weight_message', is_arabic, weight=f"{weight:.1f}")
                suggestions = NotificationService._get_suggestions('high_weight', is_arabic)
                action_text = NotificationService._get_text('view_readings', is_arabic)
                
                notif = {
                    'type': 'health',
                    'priority': 'high',
                    'severity': 'warning',
                    'icon': '⚖️',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/health',
                    'action_text': action_text,
                    'value': weight
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='⚖️', url='/health')
                NotificationService.send_email_notification(user, title, message, is_arabic)
                
            elif weight < 50:
                title = NotificationService._get_text('low_weight_title', is_arabic)
                message = NotificationService._get_text('low_weight_message', is_arabic, weight=f"{weight:.1f}")
                suggestions = NotificationService._get_suggestions('low_weight', is_arabic)
                action_text = NotificationService._get_text('view_readings', is_arabic)
                
                notif = {
                    'type': 'health',
                    'priority': 'high',
                    'severity': 'warning',
                    'icon': '⚖️',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/health',
                    'action_text': action_text,
                    'value': weight
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='⚖️', url='/health')
        
        # 2. فحص ضغط الدم
        if latest.systolic_pressure and latest.diastolic_pressure:
            systolic = latest.systolic_pressure
            diastolic = latest.diastolic_pressure
            
            if systolic > 140 or diastolic > 90:
                title = NotificationService._get_text('high_bp_title', is_arabic)
                message = NotificationService._get_text('high_bp_message', is_arabic, bp=f"{systolic}/{diastolic}")
                suggestions = NotificationService._get_suggestions('high_bp', is_arabic)
                action_text = NotificationService._get_text('view_details', is_arabic)
                
                notif = {
                    'type': 'health',
                    'priority': 'urgent',
                    'severity': 'danger',
                    'icon': '❤️',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/health',
                    'action_text': action_text,
                    'value': systolic
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='❤️', url='/health', priority='high')
                NotificationService.send_email_notification(user, title, message, is_arabic)
                
            elif systolic < 90 or diastolic < 60:
                title = NotificationService._get_text('low_bp_title', is_arabic)
                message = NotificationService._get_text('low_bp_message', is_arabic, bp=f"{systolic}/{diastolic}")
                suggestions = NotificationService._get_suggestions('low_bp', is_arabic)
                action_text = NotificationService._get_text('view_details', is_arabic)
                
                notif = {
                    'type': 'health',
                    'priority': 'high',
                    'severity': 'warning',
                    'icon': '❤️',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/health',
                    'action_text': action_text,
                    'value': systolic
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='❤️', url='/health')
        
        # 3. فحص السكر
        if latest.blood_glucose:
            glucose = float(latest.blood_glucose)
            
            if glucose > 140:
                title = NotificationService._get_text('high_glucose_title', is_arabic)
                message = NotificationService._get_text('high_glucose_message', is_arabic, glucose=f"{glucose:.1f}")
                suggestions = NotificationService._get_suggestions('high_glucose', is_arabic)
                action_text = NotificationService._get_text('view_readings', is_arabic)
                
                notif = {
                    'type': 'health',
                    'priority': 'high',
                    'severity': 'warning',
                    'icon': '🩸',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/health',
                    'action_text': action_text,
                    'value': glucose
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='🩸', url='/health')
                NotificationService.send_email_notification(user, title, message, is_arabic)
                
            elif glucose < 70:
                title = NotificationService._get_text('low_glucose_title', is_arabic)
                message = NotificationService._get_text('low_glucose_message', is_arabic, glucose=f"{glucose:.1f}")
                suggestions = NotificationService._get_suggestions('low_glucose', is_arabic)
                action_text = NotificationService._get_text('log_reading', is_arabic)
                
                notif = {
                    'type': 'health',
                    'priority': 'urgent',
                    'severity': 'danger',
                    'icon': '🆘',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/health',
                    'action_text': action_text,
                    'value': glucose
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='🆘', url='/health', priority='high')
                NotificationService.send_email_notification(user, title, message, is_arabic)
        
        return notifications

    # =========================================================
    # 2. تنبيهات النوم (مترجمة)
    # =========================================================
    
    @staticmethod
    def check_sleep_alerts(user, request=None) -> List[Dict[str, Any]]:
        """فحص تنبيهات النوم"""
        from main.models import Sleep
        
        is_arabic = NotificationService._get_user_language(user, request)
        now = timezone.now()
        today = now.date()
        notifications = []
        
        # 1. تذكير بالنوم (بعد 9 مساءً)
        if 21 <= now.hour <= 23:
            slept_today = Sleep.objects.filter(
                user=user,
                sleep_start__date=today
            ).exists()
            
            if not slept_today:
                title = NotificationService._get_text('sleep_time_title', is_arabic)
                message = NotificationService._get_text('sleep_time_message', is_arabic)
                suggestions = NotificationService._get_suggestions('sleep_time', is_arabic)
                action_text = NotificationService._get_text('log_sleep', is_arabic)
                
                notif = {
                    'type': 'sleep',
                    'priority': 'medium',
                    'severity': 'info',
                    'icon': '🌙',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/sleep',
                    'action_text': action_text
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='🌙', url='/sleep')
        
        # 2. تحليل النوم (صباحاً)
        elif 7 <= now.hour <= 10:
            yesterday = today - timedelta(days=1)
            last_sleep = Sleep.objects.filter(
                user=user,
                sleep_start__date=yesterday
            ).first()
            
            if last_sleep and last_sleep.sleep_start and last_sleep.sleep_end:
                duration = (last_sleep.sleep_end - last_sleep.sleep_start).total_seconds() / 3600
                
                if duration < 6:
                    title = NotificationService._get_text('lack_sleep_title', is_arabic)
                    message = NotificationService._get_text('lack_sleep_message', is_arabic, hours=f"{duration:.1f}")
                    suggestions = NotificationService._get_suggestions('lack_sleep', is_arabic)
                    action_text = NotificationService._get_text('sleep_analysis', is_arabic)
                    
                    notif = {
                        'type': 'sleep',
                        'priority': 'high',
                        'severity': 'warning',
                        'icon': '😴',
                        'title': title,
                        'message': message,
                        'suggestions': suggestions,
                        'action_url': '/sleep',
                        'action_text': action_text,
                        'value': duration
                    }
                    notifications.append(notif)
                    NotificationService.send_push_notification(user, title, message, icon='😴', url='/sleep')
                    NotificationService.send_email_notification(user, title, message, is_arabic)
                    
                elif duration > 9:
                    title = NotificationService._get_text('long_sleep_title', is_arabic)
                    message = NotificationService._get_text('long_sleep_message', is_arabic, hours=f"{duration:.1f}")
                    suggestions = NotificationService._get_suggestions('long_sleep', is_arabic)
                    action_text = NotificationService._get_text('sleep_analysis', is_arabic)
                    
                    notif = {
                        'type': 'sleep',
                        'priority': 'medium',
                        'severity': 'info',
                        'icon': '😴',
                        'title': title,
                        'message': message,
                        'suggestions': suggestions,
                        'action_url': '/sleep',
                        'action_text': action_text,
                        'value': duration
                    }
                    notifications.append(notif)
                    NotificationService.send_push_notification(user, title, message, icon='😴', url='/sleep')
        
        return notifications

    # =========================================================
    # 3. تنبيهات العادات (مترجمة)
    # =========================================================
    
    @staticmethod
    def check_habit_alerts(user, request=None) -> List[Dict[str, Any]]:
        """فحص تنبيهات العادات"""
        from main.models import HabitDefinition, HabitLog
        
        is_arabic = NotificationService._get_user_language(user, request)
        today = timezone.now().date()
        now = timezone.now()
        notifications = []
        
        habits = HabitDefinition.objects.filter(user=user, is_active=True)
        
        for habit in habits:
            logged_today = HabitLog.objects.filter(
                habit=habit,
                log_date=today
            ).exists()
            
            if not logged_today and now.hour >= 18:
                title = NotificationService._get_text('habit_reminder_title', is_arabic, habit=habit.name)
                message = NotificationService._get_text('habit_reminder_message', is_arabic)
                suggestions = NotificationService._get_suggestions('habit', is_arabic)
                action_text = NotificationService._get_text('log_now', is_arabic)
                
                notif = {
                    'type': 'habit',
                    'priority': 'low',
                    'severity': 'info',
                    'icon': '💊',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': f'/habits/{habit.id}',
                    'action_text': action_text
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='💊', url=notif['action_url'])
        
        return notifications

    # =========================================================
    # 4. تنبيهات التغذية (مترجمة)
    # =========================================================
    
    @staticmethod
    def check_nutrition_alerts(user, request=None) -> List[Dict[str, Any]]:
        """فحص تنبيهات التغذية"""
        from main.models import Meal
        
        is_arabic = NotificationService._get_user_language(user, request)
        now = timezone.now()
        today = now.date()
        notifications = []
        
        meal_times = [
            {'type': 'Breakfast', 'start': 7, 'end': 9, 'icon': '🌅', 'title_key': 'breakfast_title', 'message_key': 'breakfast_message', 'suggestions_key': 'breakfast'},
            {'type': 'Lunch', 'start': 12, 'end': 14, 'icon': '☀️', 'title_key': 'lunch_title', 'message_key': 'lunch_message', 'suggestions_key': 'lunch'},
            {'type': 'Dinner', 'start': 18, 'end': 20, 'icon': '🌙', 'title_key': 'dinner_title', 'message_key': 'dinner_message', 'suggestions_key': 'dinner'}
        ]
        
        for meal in meal_times:
            if meal['start'] <= now.hour <= meal['end']:
                meal_exists = Meal.objects.filter(
                    user=user,
                    meal_type=meal['type'],
                    meal_time__date=today
                ).exists()
                
                if not meal_exists:
                    title = NotificationService._get_text(meal['title_key'], is_arabic)
                    message = NotificationService._get_text(meal['message_key'], is_arabic)
                    suggestions = NotificationService._get_suggestions(meal['suggestions_key'], is_arabic)
                    action_text = NotificationService._get_text('log_meal', is_arabic)
                    
                    notif = {
                        'type': 'nutrition',
                        'priority': 'medium' if meal['type'] != 'Dinner' else 'low',
                        'severity': 'info',
                        'icon': meal['icon'],
                        'title': title,
                        'message': message,
                        'suggestions': suggestions,
                        'action_url': '/nutrition',
                        'action_text': action_text
                    }
                    notifications.append(notif)
                    NotificationService.send_push_notification(user, title, message, icon=meal['icon'], url='/nutrition')
        
        return notifications

    # =========================================================
    # 5. تنبيهات النشاط البدني (مترجمة)
    # =========================================================
    
    @staticmethod
    def check_activity_alerts(user, request=None) -> List[Dict[str, Any]]:
        """فحص تنبيهات النشاط البدني"""
        from main.models import PhysicalActivity
        
        is_arabic = NotificationService._get_user_language(user, request)
        now = timezone.now()
        today = now.date()
        notifications = []
        
        if 16 <= now.hour <= 18:
            activity_today = PhysicalActivity.objects.filter(
                user=user,
                start_time__date=today
            ).exists()
            
            if not activity_today:
                title = NotificationService._get_text('activity_title', is_arabic)
                message = NotificationService._get_text('activity_message', is_arabic)
                suggestions = NotificationService._get_suggestions('activity', is_arabic)
                action_text = NotificationService._get_text('log_activity', is_arabic)
                
                notif = {
                    'type': 'activity',
                    'priority': 'medium',
                    'severity': 'info',
                    'icon': '🚶',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/activities',
                    'action_text': action_text
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='🚶', url='/activities')
        
        return notifications

    # =========================================================
    # 6. إنجازات المستخدم (مترجمة)
    # =========================================================
    
    @staticmethod
    def check_achievements(user, request=None) -> List[Dict[str, Any]]:
        """فحص إنجازات المستخدم"""
        from main.models import HealthStatus, Sleep
        
        is_arabic = NotificationService._get_user_language(user, request)
        notifications = []
        
        health_count = HealthStatus.objects.filter(user=user).count()
        achievement_milestones = [10, 25, 50, 100]
        
        for milestone in achievement_milestones:
            if health_count == milestone:
                title = NotificationService._get_text('achievement_health_title', is_arabic, count=milestone)
                message = NotificationService._get_text('achievement_health_message', is_arabic, count=milestone)
                suggestions = NotificationService._get_suggestions('achievement', is_arabic)
                action_text = NotificationService._get_text('view_readings', is_arabic)
                
                notif = {
                    'type': 'achievement',
                    'priority': 'low',
                    'severity': 'success',
                    'icon': '🏆',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/health',
                    'action_text': action_text
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='🏆', url='/health')
                NotificationService.send_email_notification(user, title, message, is_arabic)
                break
        
        sleep_count = Sleep.objects.filter(user=user).count()
        sleep_milestones = [7, 30, 100]
        
        for milestone in sleep_milestones:
            if sleep_count == milestone:
                weeks = milestone // 7
                title = NotificationService._get_text('achievement_sleep_title', is_arabic, weeks=weeks)
                message = NotificationService._get_text('achievement_sleep_message', is_arabic, nights=milestone)
                suggestions = NotificationService._get_suggestions('achievement', is_arabic)
                action_text = NotificationService._get_text('sleep_analysis', is_arabic)
                
                notif = {
                    'type': 'achievement',
                    'priority': 'low',
                    'severity': 'success',
                    'icon': '🌙',
                    'title': title,
                    'message': message,
                    'suggestions': suggestions,
                    'action_url': '/sleep',
                    'action_text': action_text
                }
                notifications.append(notif)
                NotificationService.send_push_notification(user, title, message, icon='🌙', url='/sleep')
                break
        
        return notifications

    # =========================================================
    # 7. النصائح اليومية (مترجمة)
    # =========================================================
    
    @staticmethod
    def get_daily_tip(is_arabic=True) -> Dict[str, Any]:
        """نصيحة يومية عشوائية"""
        tips_keys = [
            ('tip_water_title', 'tip_water_message', '💧'),
            ('tip_sleep_title', 'tip_sleep_message', '😴'),
            ('tip_walk_title', 'tip_walk_message', '🚶'),
            ('tip_nutrition_title', 'tip_nutrition_message', '🥗'),
            ('tip_meditation_title', 'tip_meditation_message', '🧘'),
            ('tip_journal_title', 'tip_journal_message', '📝'),
            ('tip_stairs_title', 'tip_stairs_message', '🏃'),
            ('tip_fruit_title', 'tip_fruit_message', '🍎'),
            ('tip_motivation_title', 'tip_motivation_message', '🌟'),
        ]
        
        title_key, message_key, icon = random.choice(tips_keys)
        
        return {
            'type': 'tip',
            'icon': icon,
            'title': NotificationService._get_text(title_key, is_arabic),
            'message': NotificationService._get_text(message_key, is_arabic)
        }

    # =========================================================
    # 8. الوظيفة الرئيسية - توليد جميع الإشعارات
    # =========================================================
    
    @staticmethod
    def generate_all_notifications(user, request=None) -> int:
        """توليد وإرسال جميع الإشعارات للمستخدم"""
        if not user or not user.is_active:
            logger.warning(f"User {user} is not active, skipping notifications")
            return 0
        
        is_arabic = NotificationService._get_user_language(user, request)
        all_notifications = []
        
        logger.info(f"🔔 Generating notifications for {user.username} (lang: {'ar' if is_arabic else 'en'})")
        
        # جمع جميع الإشعارات (تمرير request لكل دالة)
        all_notifications.extend(NotificationService.check_health_alerts(user, request))
        all_notifications.extend(NotificationService.check_sleep_alerts(user, request))
        all_notifications.extend(NotificationService.check_habit_alerts(user, request))
        all_notifications.extend(NotificationService.check_nutrition_alerts(user, request))
        all_notifications.extend(NotificationService.check_activity_alerts(user, request))
        all_notifications.extend(NotificationService.check_achievements(user, request))
        
        # نصيحة يومية (مرة واحدة في اليوم)
        tip_exists = NotificationService.notification_exists_today(user, 'tip')
        if not tip_exists and random.random() < 0.3:
            tip = NotificationService.get_daily_tip(is_arabic)
            all_notifications.append({
                'type': 'tip',
                'priority': 'low',
                'severity': 'info',
                'icon': tip['icon'],
                'title': tip['title'],
                'message': tip['message'],
                'action_url': '/',
                'action_text': NotificationService._get_text('view_readings', is_arabic)
            })
            NotificationService.send_push_notification(user, tip['title'], tip['message'], icon=tip['icon'], url='/')
        
        # حفظ الإشعارات في قاعدة البيانات
        created_count = 0
        for notif_data in all_notifications:
            if NotificationService.save_notification(user, notif_data):
                created_count += 1
        
        if created_count > 0:
            logger.info(f"✅ Created {created_count} notifications for {user.username}")
        else:
            logger.debug(f"No new notifications for {user.username}")
        
        return created_count
    
    @staticmethod
    def notification_exists_today(user, notif_type: str) -> bool:
        """التحقق من وجود إشعار من نوع معين اليوم"""
        from main.models import Notification
        
        today = timezone.now().date()
        return Notification.objects.filter(
            user=user,
            type=notif_type,
            sent_at__date=today
        ).exists()
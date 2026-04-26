# main/management/commands/generate_daily_notifications.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from main.models import Notification, HabitDefinition, HabitLog, HealthStatus, Sleep, MoodEntry
from main.services.notification_service import NotificationService

User = get_user_model()

class Command(BaseCommand):
    help = 'توليد الإشعارات اليومية لجميع المستخدمين'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='توليد الإشعارات حتى لو كانت موجودة مسبقاً'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='توليد الإشعارات لمستخدم محدد فقط'
        )
        parser.add_argument(
            '--lang',
            type=str,
            choices=['ar', 'en'],
            help='توليد الإشعارات بلغة محددة (تتجاوز لغة المستخدم)'
        )
    
    def get_user_language(self, user):
        """استرجاع لغة المستخدم من الإعدادات"""
        # محاولة جلب اللغة من user profile
        try:
            if hasattr(user, 'profile') and user.profile.language:
                return user.profile.language
        except:
            pass
        
        # محاولة جلب من user model مباشرة
        if hasattr(user, 'language') and user.language:
            return user.language
        
        # افتراضياً نرجع العربية
        return 'ar'
    
    def get_notification_text(self, key, is_arabic=True, **kwargs):
        """الحصول على نص الإشعار حسب اللغة مع دعم المتغيرات"""
        texts = {
            # توصيات الصحة العامة
            'health_checkup': {
                'ar': '🩺 فحص طبي دوري',
                'en': '🩺 Regular Checkup'
            },
            'health_checkup_body': {
                'ar': 'لا تنسى إجراء الفحوصات الدورية للاطمئنان على صحتك',
                'en': "Don't forget to schedule your regular health checkup"
            },
            # تذكير القياسات
            'measurement_reminder': {
                'ar': '📊 قياسات اليوم',
                'en': '📊 Today\'s Measurements'
            },
            'measurement_reminder_body': {
                'ar': 'سجل قراءاتك الصحية اليوم (الوزن، الضغط، السكر)',
                'en': 'Log your health readings today (weight, BP, glucose)'
            },
            # تذكير الأدوية
            'medication_reminder': {
                'ar': '💊 تذكير بالأدوية',
                'en': '💊 Medication Reminder'
            },
            'medication_reminder_body': {
                'ar': 'حان وقت تناول أدويتك المقررة',
                'en': 'Time to take your scheduled medications'
            },
            # تذكير النشاط
            'activity_reminder': {
                'ar': '🏃 تذكير بالنشاط',
                'en': '🏃 Activity Reminder'
            },
            'activity_reminder_body': {
                'ar': 'لم تسجل أي نشاط بدني اليوم، حاول ممارسة 30 دقيقة من المشي',
                'en': 'No physical activity logged today, try 30 minutes of walking'
            },
            # تذكير النوم
            'sleep_reminder': {
                'ar': '😴 وقت النوم',
                'en': '😴 Bedtime'
            },
            'sleep_reminder_body': {
                'ar': 'حان وقت النوم، حاول النوم 7-8 ساعات لتحسين صحتك',
                'en': 'Time to sleep, aim for 7-8 hours for better health'
            },
            # تذكير المزاج
            'mood_reminder': {
                'ar': '😊 كيف تشعر اليوم؟',
                'en': '😊 How are you feeling today?'
            },
            'mood_reminder_body': {
                'ar': 'سجل حالتك المزاجية اليومية لمتابعة صحتك النفسية',
                'en': 'Log your daily mood to track your mental health'
            },
            # إنجازات
            'achievement_streak': {
                'ar': '🏆 إنجاز جديد!',
                'en': '🏆 New Achievement!'
            },
            'achievement_streak_body': {
                'ar': 'مبروك! سجلت بياناتك لـ {days} أيام متتالية',
                'en': 'Congratulations! You\'ve logged data for {days} consecutive days'
            },
            # تحذيرات صحية
            'health_alert_high_bp': {
                'ar': '⚠️ تنبيه صحي: ضغط دم مرتفع',
                'en': '⚠️ Health Alert: High Blood Pressure'
            },
            'health_alert_high_bp_body': {
                'ar': 'قراءة ضغط الدم {value} أعلى من المعدل الطبيعي. استشر طبيبك',
                'en': 'Blood pressure reading {value} is above normal. Consult your doctor'
            },
            'health_alert_low_glucose': {
                'ar': '⚠️ تنبيه صحي: سكر دم منخفض',
                'en': '⚠️ Health Alert: Low Blood Sugar'
            },
            'health_alert_low_glucose_body': {
                'ar': 'قراءة السكر {value} mg/dL منخفضة. تناول وجبة خفيفة',
                'en': 'Blood sugar reading {value} mg/dL is low. Eat a light snack'
            },
            'health_alert_high_heart_rate': {
                'ar': '⚠️ تنبيه صحي: نبض مرتفع',
                'en': '⚠️ Health Alert: High Heart Rate'
            },
            'health_alert_high_heart_rate_body': {
                'ar': 'معدل نبضك {value} BPM أعلى من الطبيعي. خذ قسطاً من الراحة',
                'en': 'Your heart rate {value} BPM is above normal. Take a rest'
            },
            'health_alert_low_oxygen': {
                'ar': '⚠️ تنبيه صحي: أكسجين منخفض',
                'en': '⚠️ Health Alert: Low Oxygen'
            },
            'health_alert_low_oxygen_body': {
                'ar': 'نسبة الأكسجين {value}% منخفضة. تنفس بعمق واستشر طبيبك',
                'en': 'Oxygen level {value}% is low. Breathe deeply and consult your doctor'
            },
            # نصائح
            'tip_water': {
                'ar': '💧 نصيحة: اشرب ماء',
                'en': '💧 Tip: Drink Water'
            },
            'tip_water_body': {
                'ar': 'اشرب كوب ماء الآن للحفاظ على ترطيب جسمك',
                'en': 'Drink a glass of water now to stay hydrated'
            },
            'tip_break': {
                'ar': '🧘 نصيحة: خذ استراحة',
                'en': '🧘 Tip: Take a Break'
            },
            'tip_break_body': {
                'ar': 'قم بتمارين تمدد بسيطة كل ساعة لتجنب الإجهاد',
                'en': 'Do simple stretching exercises every hour to avoid stress'
            },
            'tip_meal': {
                'ar': '🥗 نصيحة: نظام غذائي متوازن',
                'en': '🥗 Tip: Balanced Diet'
            },
            'tip_meal_body': {
                'ar': 'تأكد من تناول الخضروات والبروتين في كل وجبة',
                'en': 'Make sure to eat vegetables and protein in every meal'
            },
            'tip_sleep': {
                'ar': '😴 نصيحة: جودة النوم',
                'en': '😴 Tip: Sleep Quality'
            },
            'tip_sleep_body': {
                'ar': 'ابتعد عن الشاشات قبل النوم بساعة للحصول على نوم أفضل',
                'en': 'Avoid screens an hour before bed for better sleep'
            },
            'tip_meditate': {
                'ar': '🧘 نصيحة: التأمل',
                'en': '🧘 Tip: Meditation'
            },
            'tip_meditate_body': {
                'ar': 'جرب التأمل لمدة 5 دقائق يومياً لتقليل التوتر',
                'en': 'Try meditating for 5 minutes daily to reduce stress'
            },
            'tip_movement': {
                'ar': '🏃 نصيحة: الحركة',
                'en': '🏃 Tip: Movement'
            },
            'tip_movement_body': {
                'ar': 'الوقوف والتحرك كل ساعة يحسن الدورة الدموية',
                'en': 'Standing and moving every hour improves circulation'
            },
            'tip_snack': {
                'ar': '🍎 نصيحة: الوجبات الخفيفة',
                'en': '🍎 Tip: Healthy Snacks'
            },
            'tip_snack_body': {
                'ar': 'اختر الفواكه والمكسرات كوجبات خفيفة صحية',
                'en': 'Choose fruits and nuts as healthy snacks'
            },
            # رسائل عامة
            'habit_not_logged': {
                'ar': 'لم تسجل هذه العادة اليوم',
                'en': 'You haven\'t logged this habit today'
            },
            'evening_checkin': {
                'ar': '🌙 تذكير المساء',
                'en': '🌙 Evening Reminder'
            },
            'morning_checkin': {
                'ar': '🌅 تذكير الصباح',
                'en': '🌅 Morning Reminder'
            },
            # رسائل النجاح
            'success_all_caught_up': {
                'ar': '✅ أحسنت! جميع بياناتك محدثة',
                'en': '✅ Great! All your data is up to date'
            },
            'success_great_habit': {
                'ar': '🌟 عادة رائعة! استمر بهذا المستوى',
                'en': '🌟 Great habit! Keep it up'
            }
        }
        
        lang = 'ar' if is_arabic else 'en'
        if key in texts:
            text = texts[key].get(lang, texts[key]['ar'])
            if kwargs:
                return text.format(**kwargs)
            return text
        return key
    
    def generate_health_alerts(self, user, today, is_arabic):
        """توليد تنبيهات صحية بناءً على آخر القراءات"""
        notifications = []
        
        # جلب آخر قراءة صحية
        last_health = HealthStatus.objects.filter(user=user).order_by('-recorded_at').first()
        
        if last_health:
            # تنبيه ضغط الدم المرتفع
            if last_health.systolic_pressure and last_health.systolic_pressure > 140:
                notifications.append({
                    'type': 'alert',
                    'priority': 'high',
                    'icon': '⚠️',
                    'title': self.get_notification_text('health_alert_high_bp', is_arabic),
                    'message': self.get_notification_text('health_alert_high_bp_body', is_arabic, 
                        value=f"{last_health.systolic_pressure}/{last_health.diastolic_pressure}")
                })
            
            # تنبيه السكر المنخفض
            if last_health.blood_glucose and last_health.blood_glucose < 70:
                notifications.append({
                    'type': 'alert',
                    'priority': 'high',
                    'icon': '⚠️',
                    'title': self.get_notification_text('health_alert_low_glucose', is_arabic),
                    'message': self.get_notification_text('health_alert_low_glucose_body', is_arabic, 
                        value=last_health.blood_glucose)
                })
            
            # تنبيه النبض المرتفع
            if last_health.heart_rate and last_health.heart_rate > 120:
                notifications.append({
                    'type': 'alert',
                    'priority': 'high',
                    'icon': '⚠️',
                    'title': self.get_notification_text('health_alert_high_heart_rate', is_arabic),
                    'message': self.get_notification_text('health_alert_high_heart_rate_body', is_arabic,
                        value=last_health.heart_rate)
                })
            
            # تنبيه الأكسجين المنخفض
            if last_health.spo2 and last_health.spo2 < 90:
                notifications.append({
                    'type': 'alert',
                    'priority': 'high',
                    'icon': '⚠️',
                    'title': self.get_notification_text('health_alert_low_oxygen', is_arabic),
                    'message': self.get_notification_text('health_alert_low_oxygen_body', is_arabic,
                        value=last_health.spo2)
                })
        
        return notifications
    
    def generate_habit_reminders(self, user, today, is_arabic):
        """توليد تذكيرات بالعادات غير المنجزة"""
        notifications = []
        habits = HabitDefinition.objects.filter(user=user, is_active=True)
        
        # تحديد عدد الإشعارات المسموحة يومياً لمنع الإزعاج
        max_habit_reminders = 3
        reminder_count = 0
        
        for habit in habits:
            if reminder_count >= max_habit_reminders:
                break
                
            logged_today = HabitLog.objects.filter(
                habit=habit,
                log_date=today
            ).exists()
            
            if not logged_today:
                # التحقق من عدم وجود إشعار مكرر
                existing = Notification.objects.filter(
                    user=user,
                    type='habit',
                    title__icontains=habit.name,
                    sent_at__date=today
                ).exists()
                
                if not existing:
                    # الكشف عن نوع العادة (دواء أم لا)
                    medication_keywords = ['دواء', 'medication', 'pill', 'ibuprofen', 'aspirin', 'tablet', 'capsule']
                    is_medication = any(k in habit.name.lower() for k in medication_keywords)
                    
                    notifications.append({
                        'type': 'habit',
                        'priority': 'low' if is_medication else 'medium',
                        'icon': '💊' if is_medication else '✅',
                        'title': f'{"💊" if is_medication else "✅"} {habit.name}',
                        'message': self.get_notification_text('medication_reminder_body', is_arabic) if is_medication 
                                  else self.get_notification_text('habit_not_logged', is_arabic),
                        'action_url': '/habits',
                        'action_text': 'سجل الآن' if is_arabic else 'Log now'
                    })
                    reminder_count += 1
        
        return notifications
    
    def generate_evening_reminder(self, user, today, current_hour, is_arabic):
        """توليد تذكير مسائي"""
        # بين 6 و 8 مساءً
        if 18 <= current_hour <= 20:
            existing = Notification.objects.filter(
                user=user,
                type='reminder',
                sent_at__date=today,
                title__icontains='تذكير المساء' if is_arabic else 'Evening'
            ).exists()
            
            if not existing:
                return [{
                    'type': 'reminder',
                    'priority': 'medium',
                    'icon': '🌙',
                    'title': self.get_notification_text('evening_checkin', is_arabic),
                    'message': self.get_notification_text('mood_reminder_body', is_arabic),
                    'action_url': '/mood',
                    'action_text': 'سجل الآن' if is_arabic else 'Log now'
                }]
        return []
    
    def generate_morning_reminder(self, user, today, current_hour, is_arabic):
        """توليد تذكير صباحي"""
        # بين 8 و 10 صباحاً
        if 8 <= current_hour <= 10:
            existing = Notification.objects.filter(
                user=user,
                type='reminder',
                sent_at__date=today,
                title__icontains='تذكير الصباح' if is_arabic else 'Morning'
            ).exists()
            
            if not existing:
                # التحقق من وجود بيانات صحية اليوم
                has_health_today = HealthStatus.objects.filter(
                    user=user,
                    recorded_at__date=today
                ).exists()
                
                if not has_health_today:
                    return [{
                        'type': 'reminder',
                        'priority': 'medium',
                        'icon': '🌅',
                        'title': self.get_notification_text('morning_checkin', is_arabic),
                        'message': self.get_notification_text('measurement_reminder_body', is_arabic),
                        'action_url': '/health',
                        'action_text': 'سجل الآن' if is_arabic else 'Log now'
                    }]
        return []
    
    def generate_streak_achievement(self, user, today, is_arabic):
        """توليد إنجاز للسلسلة المتتالية"""
        # حساب السلسلة المتتالية لتسجيل البيانات
        streak = 0
        check_date = today
        while True:
            has_any_data = (
                HabitLog.objects.filter(user=user, log_date=check_date).exists() or
                HealthStatus.objects.filter(user=user, recorded_at__date=check_date).exists() or
                Sleep.objects.filter(user=user, sleep_start__date=check_date).exists() or
                MoodEntry.objects.filter(user=user, entry_time__date=check_date).exists()
            )
            
            if has_any_data:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        # إنجاز لـ 7 و 14 و 21 و 30 يوم متتالية
        milestone_days = [7, 14, 21, 30, 60, 90]
        if streak in milestone_days:
            existing = Notification.objects.filter(
                user=user,
                type='achievement',
                sent_at__date=today
            ).exists()
            
            if not existing:
                return [{
                    'type': 'achievement',
                    'priority': 'low',
                    'icon': '🏆',
                    'title': self.get_notification_text('achievement_streak', is_arabic),
                    'message': self.get_notification_text('achievement_streak_body', is_arabic, days=streak),
                    'action_url': '/profile',
                    'action_text': 'عرض الإنجازات' if is_arabic else 'View achievements'
                }]
        return []
    
    def generate_daily_tips(self, user, today, is_arabic):
        """توليد نصائح يومية"""
        # التحقق من عدم وجود نصيحة اليوم
        existing = Notification.objects.filter(
            user=user,
            type='tip',
            sent_at__date=today
        ).exists()
        
        if not existing:
            # نصائح حسب اليوم من الأسبوع
            weekday = today.weekday()
            
            # قائمة النصائح مع مفاتيح الترجمة
            tip_keys = [
                ('tip_water', 'tip_water_body'),
                ('tip_break', 'tip_break_body'),
                ('tip_meal', 'tip_meal_body'),
                ('tip_sleep', 'tip_sleep_body'),
                ('tip_meditate', 'tip_meditate_body'),
                ('tip_movement', 'tip_movement_body'),
                ('tip_snack', 'tip_snack_body')
            ]
            
            title_key, body_key = tip_keys[weekday % len(tip_keys)]
            
            return [{
                'type': 'tip',
                'priority': 'low',
                'icon': '💡',
                'title': self.get_notification_text(title_key, is_arabic),
                'message': self.get_notification_text(body_key, is_arabic),
                'action_url': '/smart',
                'action_text': 'اكتشف المزيد' if is_arabic else 'Discover more'
            }]
        return []
    
    def generate_activity_reminder(self, user, today, is_arabic):
        """توليد تذكير بالنشاط البدني"""
        # التحقق من وجود نشاط اليوم (من العادات أو الأنشطة)
        has_activity_from_habits = HabitLog.objects.filter(
            habit__name__icontains='رياضة' if is_arabic else 'sport',
            log_date=today,
            is_completed=True
        ).exists()
        
        has_activity_from_activities = False  # يمكن إضافة التحقق من جدول الأنشطة إذا كان موجوداً
        
        if not has_activity_from_habits and not has_activity_from_activities:
            existing = Notification.objects.filter(
                user=user,
                type='reminder',
                sent_at__date=today,
                title__icontains='نشاط' if is_arabic else 'Activity'
            ).exists()
            
            if not existing:
                return [{
                    'type': 'reminder',
                    'priority': 'medium',
                    'icon': '🏃',
                    'title': self.get_notification_text('activity_reminder', is_arabic),
                    'message': self.get_notification_text('activity_reminder_body', is_arabic),
                    'action_url': '/activities',
                    'action_text': 'سجل الآن' if is_arabic else 'Log now'
                }]
        return []
    
    def handle(self, *args, **options):
        force = options['force']
        username = options['user']
        override_lang = options['lang']
        
        if username:
            users = User.objects.filter(username=username, is_active=True)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f'❌ المستخدم {username} غير موجود'))
                return
        else:
            users = User.objects.filter(is_active=True)
        
        today = timezone.now().date()
        current_hour = timezone.now().hour
        notification_count = 0
        
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"🔔 بدء توليد الإشعارات اليومية")
        self.stdout.write(f"📅 التاريخ: {today}")
        self.stdout.write(f"🕐 الساعة: {current_hour}:00")
        self.stdout.write(f"👥 عدد المستخدمين: {users.count()}")
        if override_lang:
            self.stdout.write(f"🌐 لغة متجاوزة: {override_lang}")
        self.stdout.write(f"{'='*50}")
        
        for user in users:
            user_notifications = 0
            
            # تحديد لغة المستخدم (مع إمكانية التجاوز)
            if override_lang:
                is_arabic = override_lang == 'ar'
                lang_display = 'العربية' if is_arabic else 'English'
                self.stdout.write(f"\n👤 جاري معالجة المستخدم: {user.username} ({lang_display} - متجاوزة)")
            else:
                is_arabic = self.get_user_language(user) == 'ar'
                lang_display = 'العربية' if is_arabic else 'English'
                self.stdout.write(f"\n👤 جاري معالجة المستخدم: {user.username} ({lang_display})")
            
            # توليد التنبيهات الصحية
            health_alerts = self.generate_health_alerts(user, today, is_arabic)
            for alert in health_alerts:
                if force or not Notification.objects.filter(
                    user=user, type='alert', sent_at__date=today
                ).exists():
                    Notification.objects.create(
                        user=user,
                        type=alert['type'],
                        priority=alert['priority'],
                        icon=alert['icon'],
                        title=alert['title'],
                        message=alert['message'],
                        sent_at=timezone.now(),
                        is_read=False
                    )
                    user_notifications += 1
                    self.stdout.write(f"   ✅ تنبيه صحي")
            
            # توليد تذكيرات العادات
            habit_reminders = self.generate_habit_reminders(user, today, is_arabic)
            for reminder in habit_reminders:
                Notification.objects.create(
                    user=user,
                    type=reminder['type'],
                    priority=reminder['priority'],
                    icon=reminder['icon'],
                    title=reminder['title'],
                    message=reminder['message'],
                    action_url=reminder.get('action_url', ''),
                    action_text=reminder.get('action_text', ''),
                    sent_at=timezone.now(),
                    is_read=False
                )
                user_notifications += 1
                self.stdout.write(f"   ✅ تذكير عادة")
            
            # توليد تذكير صباحي
            morning_reminders = self.generate_morning_reminder(user, today, current_hour, is_arabic)
            for reminder in morning_reminders:
                Notification.objects.create(
                    user=user,
                    type=reminder['type'],
                    priority=reminder['priority'],
                    icon=reminder['icon'],
                    title=reminder['title'],
                    message=reminder['message'],
                    action_url=reminder.get('action_url', ''),
                    action_text=reminder.get('action_text', ''),
                    sent_at=timezone.now(),
                    is_read=False
                )
                user_notifications += 1
                self.stdout.write(f"   ✅ تذكير صباحي")
            
            # توليد تذكير مسائي
            evening_reminders = self.generate_evening_reminder(user, today, current_hour, is_arabic)
            for reminder in evening_reminders:
                Notification.objects.create(
                    user=user,
                    type=reminder['type'],
                    priority=reminder['priority'],
                    icon=reminder['icon'],
                    title=reminder['title'],
                    message=reminder['message'],
                    action_url=reminder.get('action_url', ''),
                    action_text=reminder.get('action_text', ''),
                    sent_at=timezone.now(),
                    is_read=False
                )
                user_notifications += 1
                self.stdout.write(f"   ✅ تذكير مسائي")
            
            # توليد تذكير بالنشاط
            activity_reminders = self.generate_activity_reminder(user, today, is_arabic)
            for reminder in activity_reminders:
                Notification.objects.create(
                    user=user,
                    type=reminder['type'],
                    priority=reminder['priority'],
                    icon=reminder['icon'],
                    title=reminder['title'],
                    message=reminder['message'],
                    action_url=reminder.get('action_url', ''),
                    action_text=reminder.get('action_text', ''),
                    sent_at=timezone.now(),
                    is_read=False
                )
                user_notifications += 1
                self.stdout.write(f"   ✅ تذكير نشاط")
            
            # توليد إنجازات السلسلة المتتالية
            achievements = self.generate_streak_achievement(user, today, is_arabic)
            for achievement in achievements:
                Notification.objects.create(
                    user=user,
                    type=achievement['type'],
                    priority=achievement['priority'],
                    icon=achievement['icon'],
                    title=achievement['title'],
                    message=achievement['message'],
                    action_url=achievement.get('action_url', ''),
                    action_text=achievement.get('action_text', ''),
                    sent_at=timezone.now(),
                    is_read=False
                )
                user_notifications += 1
                self.stdout.write(f"   ✅ إنجاز سلسلة متتالية")
            
            # توليد نصائح يومية
            tips = self.generate_daily_tips(user, today, is_arabic)
            for tip in tips:
                Notification.objects.create(
                    user=user,
                    type=tip['type'],
                    priority=tip['priority'],
                    icon=tip['icon'],
                    title=tip['title'],
                    message=tip['message'],
                    action_url=tip.get('action_url', ''),
                    action_text=tip.get('action_text', ''),
                    sent_at=timezone.now(),
                    is_read=False
                )
                user_notifications += 1
                self.stdout.write(f"   ✅ نصيحة يومية")
            
            if user_notifications > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'   📊 تم إنشاء {user_notifications} إشعار لـ {user.username}')
                )
                notification_count += user_notifications
            else:
                self.stdout.write(f'   ℹ️ لا توجد إشعارات جديدة لـ {user.username}')
        
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(
            self.style.SUCCESS(f'📊 الإجمالي: {notification_count} إشعار لـ {users.count()} مستخدم')
        )
        self.stdout.write(f"{'='*50}\n")
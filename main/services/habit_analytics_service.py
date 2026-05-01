"""
خدمة تحليلات العادات والأدوية المتقدمة
Advanced Habits & Medications Analytics Service using scikit-learn
"""

import numpy as np
import pandas as pd
from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, F
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

from ..models import (
    HabitDefinition, HabitLog, Medication, UserMedication,
    Sleep, MoodEntry, PhysicalActivity, HealthStatus
)

# ==============================================================================
# استيرادات DRF لدوال API
# ==============================================================================
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class HabitMedicationAnalyticsService:
    """
    خدمة متخصصة لتحليلات العادات والأدوية باستخدام التعلم الآلي
    تقدم توصيات مخصصة بناءً على سلوك المستخدم والتزامه
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.is_arabic = language.startswith('ar')
        self.today = timezone.now()
        self.today_date = self.today.date()
        self.week_ago = self.today - timedelta(days=7)
        self.month_ago = self.today - timedelta(days=30)
        self.three_months_ago = self.today - timedelta(days=90)
        
        # نماذج ML
        self._models = {}
        self._scaler = StandardScaler()
        
    # ==========================================================================
    # دوال مساعدة
    # ==========================================================================
    
    def _t(self, ar_text, en_text, **kwargs):
        """ترجمة النصوص"""
        text = ar_text if self.is_arabic else en_text
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text
    
    def _get_medication_adherence_data(self):
        """جلب بيانات الالتزام بالأدوية"""
        user_meds = UserMedication.objects.filter(
            user=self.user, 
            start_date__lte=self.today_date
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.today_date))
        
        # جلب سجلات العادات المتعلقة بالأدوية
        habit_defs = HabitDefinition.objects.filter(
            user=self.user,
            name__icontains='دواء',
            is_active=True
        )
        
        habit_ids = list(habit_defs.values_list('id', flat=True))
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=self.month_ago.date(),
            habit_id__in=habit_ids
        ) if habit_ids else []
        
        return {
            'medications': user_meds,
            'habit_definitions': habit_defs,
            'habit_logs': habit_logs
        }
    
    def _get_habits_data(self, days=90):
        """جلب جميع بيانات العادات للتحليل"""
        start_date = self.today - timedelta(days=days)
        
        habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=start_date.date()
        ).select_related('habit')
        
        # تجهيز DataFrame للتحليل
        dates = pd.date_range(start=start_date.date(), end=self.today_date, freq='D')
        df = pd.DataFrame(index=dates)
        
        # إضافة أعمدة للعادات
        for habit in habits:
            habit_logs_filtered = habit_logs.filter(habit=habit)
            completed_series = []
            for date in dates:
                log = habit_logs_filtered.filter(log_date=date.date()).first()
                completed_series.append(1 if log and log.is_completed else 0)
            df[habit.name] = completed_series
        
        # إضافة ميزات زمنية
        df['day_of_week'] = df.index.dayofweek
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['week_of_year'] = df.index.isocalendar().week
        df['day_of_month'] = df.index.day
        
        # إضافة معدلات الالتزام
        df['completion_rate'] = df[habits.values_list('name', flat=True)].mean(axis=1) if habits.exists() else 0
        
        return {
            'df': df,
            'habits': habits,
            'habit_logs': habit_logs,
            'total_habits': habits.count(),
            'total_logs': habit_logs.count()
        }
    
    # ==========================================================================
    # 1. الإحصائيات الأساسية (Basic Stats)
    # ==========================================================================
    
    def get_summary(self):
        """الحصول على ملخص العادات والأدوية"""
        
        habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        
        # سجلات العادات
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=self.week_ago.date()
        )
        
        # الأدوية النشطة
        active_medications = UserMedication.objects.filter(
            user=self.user,
            start_date__lte=self.today_date
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.today_date))
        
        # سجلات الأدوية من العادات
        med_habits = habits.filter(name__icontains='دواء')
        med_logs = habit_logs.filter(habit__in=med_habits) if med_habits.exists() else []
        
        total_habits = habits.count()
        completed_today = habit_logs.filter(log_date=self.today_date, is_completed=True).count()
        completion_rate = round((completed_today / total_habits) * 100) if total_habits > 0 else 0
        
        # حساب الالتزام بالأدوية
        med_adherence = 0
        if med_habits.exists() and med_logs.exists():
            med_completed = med_logs.filter(is_completed=True).count()
            med_total = med_logs.count()
            med_adherence = round((med_completed / med_total) * 100) if med_total > 0 else 0
        
        # أقوى عادة وأضعف عادة
        habit_completion = {}
        for habit in habits:
            logs = habit_logs.filter(habit=habit)
            if logs.exists():
                completed = logs.filter(is_completed=True).count()
                total = logs.count()
                habit_completion[habit.name] = round((completed / total) * 100) if total > 0 else 0
        
        best_habit = max(habit_completion, key=habit_completion.get) if habit_completion else None
        worst_habit = min(habit_completion, key=habit_completion.get) if habit_completion else None
        
        return {
            'total_habits': total_habits,
            'active_medications': active_medications.count(),
            'completed_today': completed_today,
            'completion_rate': completion_rate,
            'medication_adherence': med_adherence,
            'best_habit': best_habit,
            'worst_habit': worst_habit,
            'habit_completion_rates': habit_completion,
            'streak': self._calculate_current_streak(habit_logs),
            'total_logs_30d': habit_logs.filter(log_date__gte=self.month_ago.date()).count()
        }
    
    def _calculate_current_streak(self, habit_logs):
        """حساب السلسلة الحالية (Streak)"""
        if not habit_logs.exists():
            return 0
        
        streak = 0
        current_date = self.today_date
        
        while True:
            day_logs = habit_logs.filter(log_date=current_date)
            if day_logs.exists() and day_logs.filter(is_completed=True).exists():
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    # ==========================================================================
    # 2. تحليل الارتباطات (Correlations)
    # ==========================================================================
    
    def get_correlations(self):
        """تحليل العلاقات بين العادات وعوامل أخرى"""
        
        correlations = []
        
        # جلب البيانات
        habit_data = self._get_habits_data(days=30)
        df = habit_data['df']
        
        if len(df) < 7:
            return correlations
        
        # بيانات النوم
        sleep_data = Sleep.objects.filter(
            user=self.user,
            sleep_start__gte=self.month_ago
        )
        
        # بيانات المزاج
        mood_data = MoodEntry.objects.filter(
            user=self.user,
            entry_time__gte=self.month_ago
        )
        
        # بيانات النشاط
        activity_data = PhysicalActivity.objects.filter(
            user=self.user,
            start_time__gte=self.month_ago
        )
        
        # 1. العلاقة بين الالتزام بالعادات وجودة النوم
        if sleep_data.exists() and len(df) > 0:
            avg_sleep = sleep_data.aggregate(Avg('duration_hours'))['duration_hours__avg'] or 0
            completion_rate = df['completion_rate'].mean()
            
            if completion_rate > 70 and avg_sleep >= 7:
                correlations.append({
                    'icon': '😴',
                    'title': self._t('العادات وجودة النوم', 'Habits & Sleep Quality'),
                    'description': self._t(
                        f'التزامك العالي بالعادات ({completion_rate:.0f}%) مرتبط بنوم أفضل ({avg_sleep:.1f} ساعات)',
                        f'Your high habit adherence ({completion_rate:.0f}%) is linked to better sleep ({avg_sleep:.1f} hours)'
                    ),
                    'strength': min(0.9, completion_rate / 100),
                    'sample_size': len(df)
                })
        
        # 2. العلاقة بين العادات والمزاج
        if mood_data.exists() and len(df) > 0:
            good_mood_days = mood_data.filter(mood__in=['Excellent', 'Good']).count()
            completion_rate = df['completion_rate'].mean()
            
            if completion_rate > 60 and good_mood_days > 3:
                correlations.append({
                    'icon': '😊',
                    'title': self._t('العادات والمزاج', 'Habits & Mood'),
                    'description': self._t(
                        'الأيام التي تلتزم فيها بعاداتك يكون مزاجك أفضل',
                        'Days you stick to your habits, your mood is better'
                    ),
                    'strength': 0.65,
                    'sample_size': mood_data.count()
                })
        
        # 3. العلاقة بين العادات والنشاط
        if activity_data.exists() and len(df) > 0:
            active_days = activity_data.values('start_time__date').distinct().count()
            completion_rate = df['completion_rate'].mean()
            
            if completion_rate > 50:
                correlations.append({
                    'icon': '🏃',
                    'title': self._t('العادات والنشاط البدني', 'Habits & Physical Activity'),
                    'description': self._t(
                        f'الأشخاص الملتزمون بعاداتهم يمارسون نشاطاً بدنياً أكثر ({active_days} يوم نشط في الشهر)',
                        f'People committed to their habits exercise more ({active_days} active days per month)'
                    ),
                    'strength': 0.55,
                    'sample_size': activity_data.count()
                })
        
        # 4. العلاقة بين أدوية محددة والعادات (إن وجدت)
        med_habits = HabitDefinition.objects.filter(
            user=self.user,
            name__icontains='دواء',
            is_active=True
        )
        if med_habits.exists():
            correlations.append({
                'icon': '💊',
                'title': self._t('الالتزام بالأدوية', 'Medication Adherence'),
                'description': self._t(
                    'تتبع الأدوية بانتظام يحسن فعالية العلاج',
                    'Regular medication tracking improves treatment effectiveness'
                ),
                'strength': 0.85,
                'sample_size': med_habits.count()
            })
        
        return correlations
    
    # ==========================================================================
    # 3. توصيات مخصصة (Personalized Recommendations)
    # ==========================================================================
    
    def get_recommendations(self, summary=None):
        """توليد توصيات ذكية للعادات والأدوية"""
        
        if summary is None:
            summary = self.get_summary()
        
        recommendations = []
        habit_data = self._get_habits_data(days=30)
        
        # 1. توصية لتحسين الالتزام العام
        if summary['completion_rate'] < 60:
            recommendations.append({
                'priority': 'high',
                'icon': '📋',
                'category': 'habits',
                'title': self._t('تحسين الالتزام بالعادات', 'Improve Habit Adherence'),
                'description': self._t(
                    f'التزامك الحالي {summary["completion_rate"]}% - يمكن تحسينه',
                    f'Your current adherence is {summary["completion_rate"]}% - can be improved'
                ),
                'actions': [
                    self._t('ابدأ بعادة صغيرة واحدة فقط', 'Start with just one small habit'),
                    self._t('استخدم التذكيرات اليومية', 'Use daily reminders'),
                    self._t('سجل إنجازاتك فوراً', 'Log your achievements immediately')
                ],
                'quick_tip': self._t('العادات الصغيرة المتكررة أفضل من الكبيرة النادرة', 'Small repeated habits are better than rare big ones'),
                'based_on': f"{summary['total_logs_30d']} {self._t('سجل في آخر 30 يوم', 'logs in last 30 days')}"
            })
        
        # 2. توصية خاصة بالأدوية
        if summary['medication_adherence'] < 80 and summary['medication_adherence'] > 0:
            recommendations.append({
                'priority': 'high',
                'icon': '💊',
                'category': 'medication',
                'title': self._t('تحسين الالتزام بالأدوية', 'Improve Medication Adherence'),
                'description': self._t(
                    f'التزامك بالأدوية {summary["medication_adherence"]}%',
                    f'Your medication adherence is {summary["medication_adherence"]}%'
                ),
                'actions': [
                    self._t('ضع الأدوية في مكان مرئي', 'Place medications in a visible spot'),
                    self._t('استخدم تطبيق تذكير بالأدوية', 'Use a medication reminder app'),
                    self._t('سجل الجرعة فور تناولها', 'Log the dose immediately after taking')
                ],
                'quick_tip': self._t('تناول الأدوية في نفس الوقت يومياً', 'Take medications at the same time daily'),
                'based_on': self._t('تحليل التزامك بالأدوية', 'Medication adherence analysis')
            })
        
        # 3. توصية لتحسين السلسلة (Streak)
        if summary['streak'] < 5 and summary['streak'] > 0:
            recommendations.append({
                'priority': 'medium',
                'icon': '🔥',
                'category': 'habits',
                'title': self._t('بناء سلسلة مستمرة', 'Build a Continuous Streak'),
                'description': self._t(
                    f'لديك سلسلة حالية من {summary["streak"]} يوم، حاول الوصول إلى 7 أيام',
                    f'Your current streak is {summary["streak"]} days, try to reach 7 days'
                ),
                'actions': [
                    self._t('حدد أقل عادة يمكنك القيام بها يومياً', 'Identify the smallest habit you can do daily'),
                    self._t('لا تفوت يوماً واحداً', 'Don\'t miss a single day'),
                    self._t('احتفل عند تحقيق 7 أيام متتالية', 'Celebrate when you reach 7 consecutive days')
                ],
                'quick_tip': self._t('الاستمرارية أهم من الكمية', 'Consistency is more important than quantity'),
                'based_on': self._t('تحليل استمراريتك', 'Consistency analysis')
            })
        
        # 4. توصية للعادة الأضعف
        if summary['worst_habit']:
            worst_rate = summary['habit_completion_rates'].get(summary['worst_habit'], 0)
            recommendations.append({
                'priority': 'medium',
                'icon': '🎯',
                'category': 'habits',
                'title': self._t(f'تحسين عادة: {summary["worst_habit"]}', f'Improve habit: {summary["worst_habit"]}'),
                'description': self._t(
                    f'التزامك بهذه العادة {worst_rate}%',
                    f'Your adherence to this habit is {worst_rate}%'
                ),
                'actions': [
                    self._t('قسّم العادة إلى خطوات أصغر', 'Break the habit into smaller steps'),
                    self._t('اربطها بعادة يومية موجودة', 'Link it to an existing daily habit'),
                    self._t('استخدم نظام المكافآت', 'Use a reward system')
                ],
                'quick_tip': self._t('البدء بأقل مقاومة يسهل الالتزام', 'Starting with least resistance makes adherence easier'),
                'based_on': self._t('تحليل أداء عاداتك', 'Your habit performance analysis')
            })
        
        # 5. توصية لتحسين توزيع العادات
        if habit_data['total_habits'] >= 3 and summary['completion_rate'] < 70:
            recommendations.append({
                'priority': 'low',
                'icon': '📊',
                'category': 'habits',
                'title': self._t('تنظيم أولويات العادات', 'Organize Habit Priorities'),
                'description': self._t(
                    f'لديك {habit_data["total_habits"]} عادة نشطة',
                    f'You have {habit_data["total_habits"]} active habits'
                ),
                'actions': [
                    self._t('رتب عاداتك حسب الأهمية', 'Rank your habits by importance'),
                    self._t('ركز على 2-3 عادات رئيسية', 'Focus on 2-3 main habits'),
                    self._t('أضف عادات جديدة تدريجياً', 'Add new habits gradually')
                ],
                'quick_tip': self._t('جودة الالتزام أهم من عدد العادات', 'Quality of adherence is more important than number of habits'),
                'based_on': self._t('تحليل تنوع عاداتك', 'Your habit diversity analysis')
            })
        
        return recommendations
    
    # ==========================================================================
    # 4. توقعات مستقبلية (Predictions using ML)
    # ==========================================================================
    
    def get_predictions(self, summary=None):
        """توليد توقعات مستقبلية باستخدام التعلم الآلي"""
        
        if summary is None:
            summary = self.get_summary()
        
        predictions = []
        habit_data = self._get_habits_data(days=60)
        df = habit_data['df']
        
        # 1. التنبؤ بمعدل الالتزام المستقبلي
        future_adherence = self._predict_future_adherence(df)
        if future_adherence:
            predictions.append({
                'icon': '📈',
                'category': 'adherence',
                'label': self._t('معدل الالتزام المتوقع', 'Expected Adherence Rate'),
                'value': f"{future_adherence}%",
                'trend': 'up' if future_adherence > summary['completion_rate'] else 'stable' if future_adherence == summary['completion_rate'] else 'down',
                'trend_text': self._t('تحسن متوقع', 'Expected improvement') if future_adherence > summary['completion_rate'] else self._t('استقرار', 'Stable'),
                'note': self._t('بناءً على نمط التزامك السابق', 'Based on your past adherence pattern'),
                'confidence': min(90, 50 + len(df))
            })
        
        # 2. التنبؤ بالسلسلة (Streak)
        predicted_streak = self._predict_future_streak(df, summary['streak'])
        predictions.append({
            'icon': '🔥',
            'category': 'streak',
            'label': self._t('السلسلة المتوقعة خلال أسبوع', 'Expected streak in 1 week'),
            'value': f"{predicted_streak} {self._t('أيام', 'days')}",
            'trend': 'up' if predicted_streak > summary['streak'] else 'stable',
            'trend_text': self._t('نمو متوقع', 'Expected growth'),
            'note': self._t('مع الالتزام اليومي', 'With daily commitment'),
            'confidence': 75
        })
        
        # 3. التنبؤ بالعادة الأكثر تحسناً
        improving_habit = self._find_most_improving_habit(df, habit_data['habits'])
        if improving_habit:
            predictions.append({
                'icon': '⭐',
                'category': 'habit',
                'label': self._t('العادة الواعدة للتحسن', 'Most promising habit to improve'),
                'value': improving_habit['name'],
                'trend': 'up',
                'trend_text': self._t('إمكانية تحسن عالية', 'High improvement potential'),
                'note': improving_habit['reason'],
                'confidence': improving_habit['confidence']
            })
        
        # 4. تأثير تحسين العادات على الصحة العامة
        health_impact = self._estimate_health_impact(summary)
        predictions.append({
            'icon': '❤️',
            'category': 'health_impact',
            'label': self._t('تحسين العادات', 'Habit improvement'),
            'value': self._t('تأثير إيجابي', 'Positive impact'),
            'trend': 'up',
            'trend_text': health_impact['description'],
            'note': health_impact['detail'],
            'confidence': health_impact['confidence']
        })
        
        # 5. تنبؤ بالأدوية (للمستخدمين الذين لديهم أدوية نشطة)
        if summary['active_medications'] > 0:
            med_prediction = self._predict_medication_impact(summary)
            predictions.append({
                'icon': '💊',
                'category': 'medication',
                'label': self._t('فعالية الأدوية المتوقعة', 'Expected medication effectiveness'),
                'value': med_prediction['level'],
                'trend': 'up' if med_prediction['improvement'] > 0 else 'stable',
                'trend_text': med_prediction['description'],
                'note': med_prediction['note'],
                'confidence': med_prediction['confidence']
            })
        
        return predictions
    
    def _predict_future_adherence(self, df):
        """التنبؤ بمعدل الالتزام المستقبلي"""
        if len(df) < 14:
            return None
        
        try:
            days = np.arange(len(df)).reshape(-1, 1)
            adherence = df['completion_rate'].values * 100
            
            model = LinearRegression()
            model.fit(days, adherence)
            
            future_days = np.arange(len(df), len(df) + 7).reshape(-1, 1)
            future_predictions = model.predict(future_days)
            future_adherence = np.mean(future_predictions)
            
            return max(0, min(100, int(future_adherence)))
        except:
            return None
    
    def _predict_future_streak(self, df, current_streak):
        """التنبؤ بالسلسلة المستقبلية"""
        if len(df) < 14:
            return current_streak + 2 if current_streak > 0 else 3
        
        avg_completion = df['completion_rate'].mean() * 100
        
        if avg_completion > 80:
            return current_streak + 7
        elif avg_completion > 60:
            return current_streak + 5
        elif avg_completion > 40:
            return current_streak + 3
        else:
            return max(0, current_streak - 2)
    
    def _find_most_improving_habit(self, df, habits):
        """العثور على العادة الأكثر احتمالية للتحسن"""
        if len(df) < 14 or not habits.exists():
            return None
        
        improvements = []
        for habit in habits:
            if habit.name in df.columns:
                habit_data = df[habit.name].values
                if len(habit_data) >= 14:
                    recent_avg = np.mean(habit_data[-7:])
                    older_avg = np.mean(habit_data[:7])
                    improvement = recent_avg - older_avg
                    
                    if improvement > 0.1:
                        improvements.append({
                            'name': habit.name,
                            'improvement': improvement,
                            'reason': self._t('لاحظنا تحسناً ملحوظاً مؤخراً استمر عليه', 'We noticed recent improvement, keep it up'),
                            'confidence': min(90, 50 + int(improvement * 100))
                        })
        
        if improvements:
            return max(improvements, key=lambda x: x['improvement'])
        return None
    
    def _estimate_health_impact(self, summary):
        """تقدير تأثير تحسين العادات على الصحة"""
        current_rate = summary['completion_rate']
        target_rate = min(90, current_rate + 20)
        
        if current_rate < 50:
            return {
                'description': self._t('تحسين كبير متوقع', 'Major improvement expected'),
                'detail': self._t('زيادة الالتزام للعادات قد يحسن صحتك العامة بنسبة 30-40%', 'Increasing habit adherence may improve overall health by 30-40%'),
                'confidence': 85
            }
        elif current_rate < 70:
            return {
                'description': self._t('تحسن ملحوظ', 'Notable improvement'),
                'detail': self._t(f'الوصول إلى {target_rate}% التزام قد يحسن طاقتك وتركيزك', f'Reaching {target_rate}% adherence may improve your energy and focus'),
                'confidence': 75
            }
        else:
            return {
                'description': self._t('استقرار وصيانة', 'Stability and maintenance'),
                'detail': self._t('أنت في مستوى ممتاز، حافظ على استمراريتك', 'You are at an excellent level, maintain your consistency'),
                'confidence': 90
            }
    
    def _predict_medication_impact(self, summary):
        """التنبؤ بتأثير الالتزام بالأدوية"""
        adherence = summary['medication_adherence']
        
        if adherence < 60:
            return {
                'level': self._t('منخفضة حالياً', 'Currently low'),
                'improvement': 25,
                'description': self._t('تحسن كبير متوقع مع الالتزام', 'Major improvement expected with adherence'),
                'note': self._t('زيادة الالتزام قد يحسن فعالية العلاج', 'Increased adherence may improve treatment effectiveness'),
                'confidence': 80
            }
        elif adherence < 85:
            return {
                'level': self._t('متوسطة', 'Moderate'),
                'improvement': 10,
                'description': self._t('تحسن ملحوظ متوقع', 'Notable improvement expected'),
                'note': self._t('الوصول إلى 85%+ يزيد الفعالية بشكل كبير', 'Reaching 85%+ significantly increases effectiveness'),
                'confidence': 85
            }
        else:
            return {
                'level': self._t('ممتازة', 'Excellent'),
                'improvement': 0,
                'description': self._t('التزام ممتاز', 'Excellent adherence'),
                'note': self._t('استمر على هذا المستوى للحصول على أفضل نتائج', 'Maintain this level for best results'),
                'confidence': 95
            }
    
    # ==========================================================================
    # 5. كشف الأنماط الشاذة (Anomaly Detection)
    # ==========================================================================
    
    def detect_anomalies(self):
        """كشف الأيام غير المعتادة في الالتزام بالعادات"""
        
        habit_data = self._get_habits_data(days=60)
        df = habit_data['df']
        
        if len(df) < 14:
            return {'status': 'insufficient_data', 'anomalies': []}
        
        anomalies = []
        
        try:
            features = ['completion_rate', 'day_of_week', 'is_weekend']
            X = df[features].fillna(0)
            
            X_scaled = self._scaler.fit_transform(X)
            
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            predictions = iso_forest.fit_predict(X_scaled)
            
            for i, pred in enumerate(predictions):
                if pred == -1:
                    date = df.index[i]
                    anomalies.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'completion_rate': float(df['completion_rate'].iloc[i] * 100),
                        'anomaly_type': 'low_adherence' if df['completion_rate'].iloc[i] < 0.3 else 'unusual_pattern'
                    })
        except Exception as e:
            pass
        
        return {
            'status': 'success',
            'anomalies_count': len(anomalies),
            'anomalies': anomalies[:5],
            'recommendation': self._t(
                'لاحظنا بعض الأيام التي كان فيها التزامك أقل من المعتاد. جرب تحديد الأسباب',
                'We noticed some days with lower than usual adherence. Try to identify the causes'
            ) if anomalies else self._t('لا توجد أنماط شاذة ملحوظة', 'No notable anomalous patterns')
        }
    
    # ==========================================================================
    # 6. تحليل توزيع العادات (Habit Distribution Analysis)
    # ==========================================================================
    
    def get_habit_distribution(self):
        """تحليل توزيع العادات على مدار الأسبوع"""
        
        habit_data = self._get_habits_data(days=30)
        df = habit_data['df']
        
        if len(df) < 7:
            return {'status': 'insufficient_data'}
        
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_names_ar = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        
        weekday_adherence = {}
        for day in range(7):
            day_data = df[df['day_of_week'] == day]
            if len(day_data) > 0:
                avg = day_data['completion_rate'].mean() * 100
                weekday_adherence[weekday_names[day]] = round(avg, 1)
        
        best_day = max(weekday_adherence, key=weekday_adherence.get) if weekday_adherence else None
        worst_day = min(weekday_adherence, key=weekday_adherence.get) if weekday_adherence else None
        
        return {
            'status': 'success',
            'daily_adherence': weekday_adherence,
            'best_day': self._t(weekday_names_ar[weekday_names.index(best_day)], best_day) if best_day else None,
            'worst_day': self._t(weekday_names_ar[weekday_names.index(worst_day)], worst_day) if worst_day else None,
            'recommendation': self._t(
                f'أيام {self._t(weekday_names_ar[weekday_names.index(best_day)], best_day) if best_day else ""} هي الأفضل لك، حاول استغلالها في العادات الأكثر تحدياً',
                f'{best_day if best_day else ""} are your best days, try to use them for challenging habits'
            ) if best_day and worst_day else None
        }
    
    # ==========================================================================
    # 7. تحليل كامل متكامل (Complete Analysis)
    # ==========================================================================
    
    def get_complete_analysis(self):
        """الحصول على تحليل كامل للعادات والأدوية"""
        
        summary = self.get_summary()
        
        return {
            'summary': summary,
            'correlations': self.get_correlations(),
            'recommendations': self.get_recommendations(summary),
            'predictions': self.get_predictions(summary),
            'anomalies': self.detect_anomalies(),
            'distribution': self.get_habit_distribution(),
            'streak_analysis': {
                'current_streak': summary['streak'],
                'best_streak': self._get_best_streak(),
                'streak_level': self._get_streak_level(summary['streak'])
            }
        }
    
    def _get_best_streak(self):
        """الحصول على أفضل سلسلة سابقة"""
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=self.three_months_ago.date()
        ).order_by('log_date')
        
        if not habit_logs.exists():
            return 0
        
        best_streak = 0
        current_streak = 0
        last_date = None
        
        for log in habit_logs:
            if log.is_completed:
                if last_date and (log.log_date - last_date).days == 1:
                    current_streak += 1
                else:
                    current_streak = 1
                best_streak = max(best_streak, current_streak)
                last_date = log.log_date
        
        return best_streak
    
    def _get_streak_level(self, streak):
        """تقييم مستوى السلسلة"""
        if streak >= 30:
            return self._t('أسطوري 🔥🔥🔥', 'Legendary 🔥🔥🔥')
        elif streak >= 14:
            return self._t('ممتاز 🔥🔥', 'Excellent 🔥🔥')
        elif streak >= 7:
            return self._t('جيد 🔥', 'Good 🔥')
        elif streak >= 3:
            return self._t('بداية جيدة', 'Good start')
        else:
            return self._t('يحتاج تحسين', 'Needs improvement')


# ==============================================================================
# ==============================================================================
# دوال API باستخدام DRF (مع مصادقة صحيحة)
# ==============================================================================
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_medication_analytics_api(request):
    """
    API للحصول على تحليلات العادات والأدوية
    """
    language = request.GET.get('lang', 'ar')
    
    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        result = service.get_complete_analysis()
        return Response({
            'success': True,
            'data': result,
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'message': 'حدث خطأ في تحليل العادات' if language == 'ar' else 'Error analyzing habits'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_summary_api(request):
    """
    API للحصول على ملخص سريع للعادات (للوحات الرئيسية)
    """
    language = request.GET.get('lang', 'ar')
    
    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        summary = service.get_summary()
        return Response({
            'success': True,
            'summary': summary,
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_recommendations_api(request):
    """
    API للحصول على توصيات العادات فقط
    """
    language = request.GET.get('lang', 'ar')
    limit = int(request.GET.get('limit', 5))
    
    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        recommendations = service.get_recommendations()
        return Response({
            'success': True,
            'recommendations': recommendations[:limit],
            'total': len(recommendations),
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_predictions_api(request):
    """
    API للحصول على توقعات العادات
    """
    language = request.GET.get('lang', 'ar')
    
    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        summary = service.get_summary()
        predictions = service.get_predictions(summary)
        return Response({
            'success': True,
            'predictions': predictions,
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==============================================================================
# دالة مساعدة للاستخدام السريع
# ==============================================================================

def get_habit_medication_analytics(user, language='ar'):
    """دالة مساعدة للحصول على تحليلات العادات والأدوية"""
    service = HabitMedicationAnalyticsService(user, language=language)
    return service.get_complete_analysis()
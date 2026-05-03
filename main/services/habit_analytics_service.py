"""
خدمة تحليلات العادات والأدوية المتقدمة - نسخة خفيفة (10 أيام فقط)
"""

import numpy as np
import pandas as pd
from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, F
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

from ..models import (
    HabitDefinition, HabitLog, Medication, UserMedication,
    Sleep, MoodEntry, PhysicalActivity, HealthStatus
)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class HabitMedicationAnalyticsService:
    """
    خدمة متخصصة لتحليلات العادات والأدوية - نسخة خفيفة (10 أيام فقط)
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.is_arabic = language.startswith('ar')
        self.today = timezone.now()
        self.today_date = self.today.date()
        self.week_ago = self.today - timedelta(days=7)
        
        # ✅ تغيير جوهري: 10 أيام فقط بدلاً من 30/60/90
        self.analysis_days = 10  # ✅ فقط 10 أيام
        self.analysis_start = self.today - timedelta(days=self.analysis_days)
        
        # نماذج ML
        self._models = {}
        self._scaler = StandardScaler()
        
    def _t(self, ar_text, en_text, **kwargs):
        """ترجمة النصوص"""
        text = ar_text if self.is_arabic else en_text
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text
    
    def _get_habits_data(self):
        """جلب بيانات العادات للتحليل (آخر 10 أيام فقط)"""
        habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=self.analysis_start.date()
        ).select_related('habit')
        
        # ✅ تجهيز DataFrame للتحليل (10 أيام فقط)
        dates = pd.date_range(start=self.analysis_start.date(), end=self.today_date, freq='D')
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
        
        # إضافة معدلات الالتزام
        if habits.exists():
            df['completion_rate'] = df[habits.values_list('name', flat=True)].mean(axis=1)
        else:
            df['completion_rate'] = 0
        
        return {
            'df': df,
            'habits': habits,
            'habit_logs': habit_logs,
            'total_habits': habits.count(),
            'total_logs': habit_logs.count()
        }
    
    def get_summary(self):
        """الحصول على ملخص العادات والأدوية (آخر 10 أيام)"""
        
        habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        
        # ✅ سجلات آخر 10 أيام فقط
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=self.analysis_start.date()
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
        
        # حساب الالتزام بالأدوية (آخر 10 أيام)
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
            'analysis_days': self.analysis_days
        }
    
    def _calculate_current_streak(self, habit_logs):
        """حساب السلسلة الحالية (Streak)"""
        if not habit_logs.exists():
            return 0
        
        streak = 0
        current_date = self.today_date
        
        for _ in range(self.analysis_days):  # ✅ فقط خلال أيام التحليل
            day_logs = habit_logs.filter(log_date=current_date)
            if day_logs.exists() and day_logs.filter(is_completed=True).exists():
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    def get_correlations(self):
        """تحليل العلاقات بين العادات وعوامل أخرى (بيانات محدودة)"""
        
        correlations = []
        habit_data = self._get_habits_data()
        df = habit_data['df']
        
        if len(df) < 3:  # ✅ أقل من 3 أيام فقط
            return correlations
        
        # بيانات النوم (آخر 10 أيام)
        sleep_data = Sleep.objects.filter(
            user=self.user,
            sleep_start__gte=self.analysis_start
        )
        
        # بيانات المزاج (آخر 10 أيام)
        mood_data = MoodEntry.objects.filter(
            user=self.user,
            entry_time__gte=self.analysis_start
        )
        
        if sleep_data.exists() and len(df) > 0:
            avg_sleep = sleep_data.aggregate(Avg('duration_hours'))['duration_hours__avg'] or 0
            completion_rate = df['completion_rate'].mean() * 100
            
            if completion_rate > 70 and avg_sleep >= 7:
                correlations.append({
                    'icon': '😴',
                    'title': self._t('العادات وجودة النوم', 'Habits & Sleep Quality'),
                    'description': self._t(
                        f'التزامك العالي ({completion_rate:.0f}%) مرتبط بنوم أفضل',
                        f'Your high adherence ({completion_rate:.0f}%) is linked to better sleep'
                    ),
                    'strength': min(0.9, completion_rate / 100),
                    'sample_size': len(df)
                })
        
        if mood_data.exists() and len(df) > 0:
            good_mood_days = mood_data.filter(mood__in=['Excellent', 'Good']).count()
            if good_mood_days > 1:
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
        
        return correlations
    
    def get_recommendations(self, summary=None):
        """توليد توصيات ذكية للعادات والأدوية"""
        
        if summary is None:
            summary = self.get_summary()
        
        recommendations = []
        habit_data = self._get_habits_data()
        
        if summary['completion_rate'] < 60 and summary['total_habits'] > 0:
            recommendations.append({
                'priority': 'high',
                'icon': '📋',
                'category': 'habits',
                'title': self._t('تحسين الالتزام بالعادات', 'Improve Habit Adherence'),
                'description': self._t(
                    f'التزامك الحالي {summary["completion_rate"]}%',
                    f'Your current adherence is {summary["completion_rate"]}%'
                ),
                'actions': [
                    self._t('حدد عادة واحدة صغيرة والتزم بها', 'Pick one small habit and stick to it'),
                    self._t('استخدم التذكيرات', 'Use reminders'),
                    self._t('سجل إنجازاتك فوراً', 'Log your achievements immediately')
                ],
                'quick_tip': self._t('الاستمرارية أهم من الكمية', 'Consistency is more important than quantity')
            })
        
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
                    self._t('تناول الدواء في نفس الوقت يومياً', 'Take medication at the same time daily'),
                    self._t('سجل الجرعة فور تناولها', 'Log the dose immediately after taking')
                ],
                'quick_tip': self._t('التنظيم يساعد على الالتزام', 'Organization helps with adherence')
            })
        
        if summary['streak'] > 0 and summary['streak'] < 3:
            recommendations.append({
                'priority': 'medium',
                'icon': '🔥',
                'category': 'habits',
                'title': self._t('حافظ على استمراريتك', 'Maintain Your Streak'),
                'description': self._t(
                    f'لديك سلسلة حالية من {summary["streak"]} يوم',
                    f'Your current streak is {summary["streak"]} days'
                ),
                'actions': [
                    self._t('لا تفوت يوماً واحداً', "Don't miss a single day"),
                    self._t('احتفل عند تحقيق 7 أيام', 'Celebrate when you reach 7 days')
                ],
                'quick_tip': self._t('كل يوم مهم في رحلتك', 'Every day matters in your journey')
            })
        
        return recommendations
    
    def get_predictions(self, summary=None):
        """توليد توقعات بسيطة (بدون ML معقد)"""
        
        predictions = []
        
        if summary and summary['streak'] > 0:
            predicted_streak = min(7, summary['streak'] + 2)
            predictions.append({
                'icon': '🔥',
                'category': 'streak',
                'label': self._t('السلسلة المتوقعة', 'Expected streak'),
                'value': f"{predicted_streak} {self._t('أيام', 'days')}",
                'trend': 'up',
                'trend_text': self._t('استمر هكذا', 'Keep it up'),
                'note': self._t('مع الالتزام اليومي', 'With daily commitment'),
                'confidence': 70
            })
        
        if summary and summary['completion_rate'] > 0:
            future_rate = min(90, summary['completion_rate'] + 10)
            predictions.append({
                'icon': '📈',
                'category': 'adherence',
                'label': self._t('معدل الالتزام المتوقع', 'Expected adherence'),
                'value': f"{future_rate}%",
                'trend': 'up' if future_rate > summary['completion_rate'] else 'stable',
                'trend_text': self._t('تحسن متوقع', 'Expected improvement'),
                'note': self._t('مع الاستمرارية', 'With consistency'),
                'confidence': 75
            })
        
        return predictions
    
    def detect_anomalies(self):
        """كشف الأيام غير المعتادة (نسخة مبسطة)"""
        
        habit_data = self._get_habits_data()
        df = habit_data['df']
        
        if len(df) < 5:
            return {'status': 'insufficient_data', 'anomalies': [], 'anomalies_count': 0}
        
        anomalies = []
        avg_rate = df['completion_rate'].mean()
        std_rate = df['completion_rate'].std()
        
        for i, row in df.iterrows():
            rate = row['completion_rate']
            if rate < avg_rate - (std_rate * 1.5) and rate < 0.3:
                anomalies.append({
                    'date': i.strftime('%Y-%m-%d'),
                    'completion_rate': float(rate * 100),
                    'anomaly_type': 'low_adherence'
                })
        
        return {
            'status': 'success',
            'anomalies_count': len(anomalies),
            'anomalies': anomalies[:3],
            'recommendation': self._t(
                'لاحظنا بعض الأيام التي كان فيها التزامك أقل من المعتاد',
                'We noticed some days with lower than usual adherence'
            ) if anomalies else self._t('التزامك جيد ومستقر', 'Your adherence is good and stable')
        }
    
    def get_habit_distribution(self):
        """تحليل توزيع العادات على مدار الأسبوع (نسخة مبسطة)"""
        
        habit_data = self._get_habits_data()
        df = habit_data['df']
        
        if len(df) < 5:
            return {'status': 'insufficient_data'}
        
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
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
            'best_day': best_day,
            'worst_day': worst_day,
            'recommendation': self._t(
                f'أيام {best_day} هي الأفضل لك' if best_day else '',
                f'{best_day} are your best days' if best_day else ''
            ) if best_day else None
        }
    
    def get_complete_analysis(self):
        """الحصول على تحليل كامل للعادات والأدوية (10 أيام)"""
        
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
                'best_streak': summary['streak'],
                'streak_level': self._get_streak_level(summary['streak'])
            }
        }
    
    def _get_streak_level(self, streak):
        """تقييم مستوى السلسلة"""
        if streak >= 7:
            return self._t('ممتاز 🔥', 'Excellent 🔥')
        elif streak >= 3:
            return self._t('جيد', 'Good')
        elif streak >= 1:
            return self._t('بداية جيدة', 'Good start')
        else:
            return self._t('يحتاج تحسين', 'Needs improvement')


# ==============================================================================
# دوال API
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_medication_analytics_api(request):
    """
    API للحصول على تحليلات العادات والأدوية (نسخة خفيفة - 10 أيام فقط)
    """
    language = request.GET.get('lang', 'ar')
    
    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        result = service.get_complete_analysis()
        return Response({
            'success': True,
            'data': result,
            'is_arabic': language == 'ar',
            'message': f'تم التحليل بناءً على آخر {result["summary"]["analysis_days"]} أيام'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'message': 'حدث خطأ في تحليل العادات' if language == 'ar' else 'Error analyzing habits'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
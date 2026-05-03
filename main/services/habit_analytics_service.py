"""
خدمة تحليلات العادات والأدوية المتقدمة - نسخة خفيفة (10 أيام فقط) - مصححة
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
        self.analysis_days = 10
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
    
    def _is_medication(self, habit):
        """✅ دالة مساعدة لتحديد إذا كانت العادة دواء أم لا"""
        text = (habit.name + ' ' + (habit.description or '')).lower()
        
        # كلمات مفتاحية للأدوية
        medication_keywords = [
            'دواء', 'medication', 'حبة', 'pill', 'علاج', 'treatment',
            'ibuprofen', 'paracetamol', 'advil', 'tylenol', 'aspirin',
            'metformin', 'lisinopril', 'amlodipine', 'atorvastatin',
            'simvastatin', 'oxytocin', 'pitocin', 'valproate',
            'amitriptyline', 'propranolol', 'mg', 'ملجم', 'جرعة', 'dose',
            'injection', 'tablet', 'capsule', 'syrup', 'suspension'
        ]
        
        # أيقونات الدواء في الوصف
        medication_icons = ['💊', '🏭', '💉', '📦', '🔢']
        
        for keyword in medication_keywords:
            if keyword in text:
                return True
        
        for icon in medication_icons:
            if icon in (habit.description or ''):
                return True
        
        return False
    
    def _get_habits_data(self):
        """جلب بيانات العادات للتحليل (آخر 10 أيام فقط)"""
        all_habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        
        # ✅ تقسيم العادات إلى عادات وأدوية
        habits = [h for h in all_habits if not self._is_medication(h)]
        medications = [h for h in all_habits if self._is_medication(h)]
        
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=self.analysis_start.date()
        ).select_related('habit')
        
        # ✅ تجهيز DataFrame للتحليل (10 أيام فقط)
        dates = pd.date_range(start=self.analysis_start.date(), end=self.today_date, freq='D')
        df = pd.DataFrame(index=dates)
        
        # إضافة أعمدة للعادات فقط (وليس الأدوية)
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
        if habits:
            df['completion_rate'] = df[[h.name for h in habits]].mean(axis=1)
        else:
            df['completion_rate'] = 0
        
        return {
            'df': df,
            'habits': habits,
            'medications': medications,
            'habit_logs': habit_logs,
            'total_habits': len(habits),
            'total_medications': len(medications),
            'total_logs': habit_logs.count()
        }
    
    def get_summary(self):
        """الحصول على ملخص العادات والأدوية (آخر 10 أيام)"""
        
        habit_data = self._get_habits_data()
        habits = habit_data['habits']
        medications = habit_data['medications']
        
        # ✅ سجلات آخر 10 أيام فقط
        habit_logs = habit_data['habit_logs']
        
        # ✅ الأدوية النشطة من UserMedication (إن وجدت)
        active_medications_db = UserMedication.objects.filter(
            user=self.user,
            start_date__lte=self.today_date
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.today_date))
        
        # ✅ إجمالي الأدوية = أدوية من العادات + أدوية من UserMedication
        total_medications = len(medications) + active_medications_db.count()
        
        total_habits = len(habits)
        
        # ✅ تصحيح: حساب الإنجاز اليومي (من العادات فقط)
        today_logs = habit_logs.filter(log_date=self.today_date)
        completed_today_habits = today_logs.filter(habit__in=habits, is_completed=True).count()
        completion_rate = round((completed_today_habits / total_habits) * 100) if total_habits > 0 else 0
        
        # ✅ حساب الالتزام بالأدوية من سجلات الأدوية فقط
        med_adherence = 0
        if medications:
            med_logs = habit_logs.filter(habit__in=medications)
            med_total = med_logs.count()
            if med_total > 0:
                med_completed = med_logs.filter(is_completed=True).count()
                med_adherence = round((med_completed / med_total) * 100)
            else:
                med_adherence = 0
        
        # ✅ إضافة إجمالي العناصر اليومية المكتملة (للعرض)
        completed_today_total = today_logs.filter(is_completed=True).count()
        
        # ✅ أقوى عادة وأضعف عادة
        habit_completion = {}
        for habit in habits:
            logs = habit_logs.filter(habit=habit)
            if logs.exists():
                completed = logs.filter(is_completed=True).count()
                total = logs.count()
                habit_completion[habit.name] = round((completed / total) * 100) if total > 0 else 0
        
        best_habit = max(habit_completion, key=habit_completion.get) if habit_completion else None
        
        # ✅ حساب السلسلة (Streak)
        streak = 0
        current_date = self.today_date
        habit_ids = [h.id for h in habits]
        
        for _ in range(self.analysis_days):
            day_logs = habit_logs.filter(log_date=current_date, habit_id__in=habit_ids)
            if day_logs.exists() and day_logs.filter(is_completed=True).exists():
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return {
            'total_habits': total_habits,
            'total_medications': total_medications,
            'active_medications': total_medications,
            'completed_today_habits': completed_today_habits,  # ✅ فقط العادات
            'completed_today_total': completed_today_total,    # ✅ العادات + الأدوية
            'completion_rate': completion_rate,               # ✅ نسبة العادات فقط
            'medication_adherence': med_adherence,            # ✅ نسبة الأدوية فقط
            'best_habit': best_habit,
            'habit_completion_rates': habit_completion,
            'streak': streak,
            'analysis_days': self.analysis_days
        }
    
    def get_correlations(self):
        """تحليل العلاقات بين العادات وعوامل أخرى - فقط إذا كان هناك بيانات كافية"""
        
        correlations = []
        habit_data = self._get_habits_data()
        df = habit_data['df']
        
        # ✅ تحتاج على الأقل 5 أيام من البيانات لتحليل ذي معنى
        if len(df) < 5:
            return correlations
        
        # ✅ تحتاج إلى عادات نشطة على الأقل
        if len(habit_data['habits']) < 2:
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
        
        # ✅ التحقق من وجود بيانات كافية للنوم
        if sleep_data.exists() and len(df) >= 5:
            avg_sleep = sleep_data.aggregate(Avg('duration_hours'))['duration_hours__avg'] or 0
            completion_rates = df['completion_rate'].dropna()
            if len(completion_rates) > 0:
                completion_rate = completion_rates.mean() * 100
                
                if completion_rate > 50 and avg_sleep >= 7:
                    correlations.append({
                        'icon': '😴',
                        'title': self._t('العادات وجودة النوم', 'Habits & Sleep Quality'),
                        'description': self._t(
                            f'التزامك بالعادات ({completion_rate:.0f}%) مرتبط بنوم {avg_sleep:.0f} ساعات',
                            f'Your habit adherence ({completion_rate:.0f}%) is linked to {avg_sleep:.0f} hours of sleep'
                        ),
                        'strength': min(0.7, completion_rate / 100),
                        'sample_size': len(df)
                    })
        
        # ✅ التحقق من وجود بيانات كافية للمزاج
        if mood_data.exists() and len(df) >= 5:
            good_mood_count = mood_data.filter(mood__in=['Excellent', 'Good']).count()
            total_moods = mood_data.count()
            
            if total_moods >= 3:
                good_mood_rate = (good_mood_count / total_moods) * 100
                completion_rates = df['completion_rate'].dropna()
                
                if len(completion_rates) > 0:
                    completion_rate = completion_rates.mean() * 100
                    
                    if completion_rate > 40 and good_mood_rate > 50:
                        correlations.append({
                            'icon': '😊',
                            'title': self._t('العادات والمزاج', 'Habits & Mood'),
                            'description': self._t(
                                'الأيام التي تلتزم فيها بعاداتك غالباً ما يكون مزاجك أفضل',
                                'Days you stick to your habits, your mood tends to be better'
                            ),
                            'strength': min(0.6, (completion_rate / 100) * (good_mood_rate / 100)),
                            'sample_size': min(len(df), total_moods)
                        })
        
        return correlations
    
    def get_recommendations(self, summary=None):
        """توليد توصيات ذكية للعادات والأدوية"""
        
        if summary is None:
            summary = self.get_summary()
        
        recommendations = []
        
        # ✅ توصية لتحسين الإنجاز اليومي
        if summary['completion_rate'] < 70 and summary['completion_rate'] > 0:
            recommendations.append({
                'priority': 'high',
                'icon': '📋',
                'category': 'habits',
                'title': self._t('حافظ على إنجاز عاداتك اليومية', 'Keep Up With Your Daily Habits'),
                'description': self._t(
                    f'أنجزت {summary["completed_today"]} من أصل {summary["total_habits"]} عادة اليوم ({summary["completion_rate"]}%)',
                    f'You completed {summary["completed_today"]} out of {summary["total_habits"]} habits today ({summary["completion_rate"]}%)'
                ),
                'actions': [
                    self._t('حدد وقتاً محدداً لكل عادة', 'Set a specific time for each habit'),
                    self._t('استخدم التذكيرات', 'Use reminders'),
                    self._t('ابدأ بعادة صغيرة واحدة فقط', 'Start with just one small habit')
                ],
                'quick_tip': self._t('الاستمرارية أهم من الكمية', 'Consistency is more important than quantity')
            })
        
        # ✅ توصية للأدوية
        if summary['total_medications'] > 0:
            if summary['medication_adherence'] < 70:
                recommendations.append({
                    'priority': 'high',
                    'icon': '💊',
                    'category': 'medication',
                    'title': self._t('تتبع أدويتك بانتظام', 'Track Your Medications Regularly'),
                    'description': self._t(
                        f'لديك {summary["total_medications"]} دواء، نسبة التزامك {summary["medication_adherence"]}%',
                        f'You have {summary["total_medications"]} medications, adherence is {summary["medication_adherence"]}%'
                    ),
                    'actions': [
                        self._t('سجل الجرعة فور تناولها', 'Log the dose immediately after taking'),
                        self._t('اضبط منبهاً لتذكيرك', 'Set an alarm to remind you'),
                        self._t('ضع الأدوية في مكان مرئي', 'Place medications in a visible spot')
                    ],
                    'quick_tip': self._t('تناول الأدوية في نفس الوقت يومياً', 'Take medications at the same time daily')
                })
            elif summary['medication_adherence'] >= 70 and summary['medication_adherence'] < 100:
                recommendations.append({
                    'priority': 'medium',
                    'icon': '💊',
                    'category': 'medication',
                    'title': self._t('أداء جيد في الأدوية', 'Good Medication Performance'),
                    'description': self._t(
                        f'التزامك بالأدوية {summary["medication_adherence"]}%، استمر',
                        f'Your medication adherence is {summary["medication_adherence"]}%, keep it up'
                    ),
                    'actions': [
                        self._t('استمر على هذا المستوى', 'Maintain this level'),
                        self._t('لا تنسَ تسجيل الجرعات', "Don't forget to log your doses")
                    ],
                    'quick_tip': self._t('الانتظام يحسن فعالية العلاج', 'Regularity improves treatment effectiveness')
                })
        
        # ✅ توصية للسلسلة (Streak)
        if summary['streak'] > 0 and summary['streak'] < 5:
            if summary['streak'] == 1:
                recommendations.append({
                    'priority': 'medium',
                    'icon': '🔥',
                    'category': 'habits',
                    'title': self._t('بداية جيدة! حافظ على استمراريتك', 'Good Start! Keep Your Streak Going'),
                    'description': self._t(
                        f'لديك سلسلة حالية من {summary["streak"]} يوم، حاول الوصول إلى 7 أيام',
                        f'Your current streak is {summary["streak"]} day, try to reach 7 days'
                    ),
                    'actions': [
                        self._t('لا تفوت يوماً واحداً', "Don't miss a single day"),
                        self._t('احتفل عند تحقيق 7 أيام', 'Celebrate when you reach 7 days')
                    ],
                    'quick_tip': self._t('كل يوم مهم في رحلتك', 'Every day matters in your journey')
                })
        elif summary['streak'] >= 5:
            recommendations.append({
                'priority': 'low',
                'icon': '🏆',
                'category': 'habits',
                'title': self._t('سلسلة رائعة! استمر', 'Great Streak! Keep Going'),
                'description': self._t(
                    f'لديك سلسلة مستمرة لمدة {summary["streak"]} يوم',
                    f'You have a {summary["streak"]}-day streak'
                ),
                'actions': [
                    self._t('استمر في تحقيق أهدافك اليومية', 'Keep achieving your daily goals'),
                    self._t('شارك إنجازك مع الأصدقاء', 'Share your achievement with friends')
                ],
                'quick_tip': self._t('الاستمرارية تصنع العادات', 'Consistency builds habits')
            })
        
        return recommendations
    
    def get_predictions(self, summary=None):
        """توليد توقعات بسيطة (بدون ML معقد)"""
        
        if summary is None:
            summary = self.get_summary()
        
        predictions = []
        
        # ✅ توقع السلسلة
        if summary['streak'] > 0:
            predicted_streak = min(7, summary['streak'] + 2) if summary['streak'] < 7 else summary['streak']
            predictions.append({
                'icon': '🔥',
                'category': 'streak',
                'label': self._t('السلسلة المتوقعة خلال أسبوع', 'Expected streak in 1 week'),
                'value': f"{predicted_streak} {self._t('أيام', 'days')}",
                'trend': 'up' if predicted_streak > summary['streak'] else 'stable',
                'trend_text': self._t('استمر هكذا', 'Keep it up'),
                'note': self._t('مع الالتزام اليومي', 'With daily commitment'),
                'confidence': 70
            })
        
        # ✅ توقع تحسين الإنجاز
        if summary['completion_rate'] < 100:
            improvement = min(30, 100 - summary['completion_rate'])
            future_rate = min(100, summary['completion_rate'] + improvement)
            predictions.append({
                'icon': '📈',
                'category': 'adherence',
                'label': self._t('معدل الإنجاز المتوقع', 'Expected completion rate'),
                'value': f"{future_rate}%",
                'trend': 'up' if future_rate > summary['completion_rate'] else 'stable',
                'trend_text': self._t('تحسن متوقع مع الاستمرار', 'Expected improvement with consistency'),
                'note': self._t('حاول تحقيق جميع عاداتك اليومية', 'Try to complete all your daily habits'),
                'confidence': 75
            })
        
        # ✅ توقع الالتزام بالأدوية (إذا كانت موجودة)
        if summary['total_medications'] > 0:
            if summary['medication_adherence'] < 100:
                future_adherence = min(100, summary['medication_adherence'] + 15)
                predictions.append({
                    'icon': '💊',
                    'category': 'medication',
                    'label': self._t('الالتزام بالأدوية المتوقع', 'Expected medication adherence'),
                    'value': f"{future_adherence}%",
                    'trend': 'up' if future_adherence > summary['medication_adherence'] else 'stable',
                    'trend_text': self._t('تحسن مع التذكير', 'Improvement with reminders'),
                    'note': self._t('سجل أدويتك يومياً', 'Log your medications daily'),
                    'confidence': 80
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
                f'أيام {self._t(weekday_names_ar[weekday_names.index(best_day)], best_day) if best_day else ""} هي الأفضل لك' if best_day else '',
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
"""
محرك الذكاء الاصطناعي للتحليلات الصحية المتقاطعة - النسخة الشاملة
تحليل كامل لكل البيانات المخزنة دون حدود زمنية
"""

from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, F, Min, Max, StdDev
from django.conf import settings
from main.models import (
    HealthStatus, PhysicalActivity, Sleep, 
    MoodEntry, Meal, HabitLog, HabitDefinition,
    CustomUser, UserMedication, ChronicCondition
)
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import NearestNeighbors
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class HealthInsightsEngineML:
    """
    محرك متقدم لتحليل البيانات الصحية باستخدام خوارزميات التعلم الآلي
    يحلل جميع البيانات المخزنة دون حدود زمنية
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.today = timezone.now().date()
        self.is_arabic = language == 'ar'
        
        # ✅ جلب جميع البيانات (بدون حدود زمنية)
        self._load_all_user_data()
        self._load_all_health_records()
        self._load_all_activities()
        self._load_all_sleep()
        self._load_all_mood()
        self._load_all_meals()
        self._load_all_habits()
        self._load_all_medications()
        self._load_all_conditions()
        
        # حساب الإحصائيات الأساسية
        self._calculate_basic_stats()
        
    def _load_all_user_data(self):
        """تحميل وتحليل جميع بيانات المستخدم الشخصية"""
        self.user_age = None
        self.user_gender = self.user.gender if hasattr(self.user, 'gender') else None
        self.user_height = None
        self.user_initial_weight = None
        self.user_health_goal = self.user.health_goal if hasattr(self.user, 'health_goal') else None
        self.user_activity_level = self.user.activity_level if hasattr(self.user, 'activity_level') else None
        self.user_occupation = self.user.occupation_status if hasattr(self.user, 'occupation_status') else None
        self.user_registered_date = self.user.date_joined.date() if hasattr(self.user, 'date_joined') else self.today
        
        # حساب العمر
        try:
            if hasattr(self.user, 'date_of_birth') and self.user.date_of_birth:
                today = timezone.now().date()
                self.user_age = today.year - self.user.date_of_birth.year - (
                    (today.month, today.day) < (self.user.date_of_birth.month, self.user.date_of_birth.day)
                )
        except:
            pass
        
        # الطول والوزن الأولي
        if hasattr(self.user, 'height') and self.user.height:
            self.user_height = float(self.user.height)
        
        if hasattr(self.user, 'initial_weight') and self.user.initial_weight:
            self.user_initial_weight = float(self.user.initial_weight)
        
        # حساب BMI
        self.user_bmi = None
        if self.user_height and self.user_initial_weight:
            height_m = self.user_height / 100
            self.user_bmi = round(self.user_initial_weight / (height_m ** 2), 1)
    
    def _load_all_health_records(self):
        """جلب جميع سجلات الصحة"""
        self.health_records = HealthStatus.objects.filter(user=self.user).order_by('recorded_at')
        self.health_count = self.health_records.count()
        self.first_health_record = self.health_records.first()
        self.last_health_record = self.health_records.last()
    
    def _load_all_activities(self):
        """جلب جميع الأنشطة"""
        self.activities = PhysicalActivity.objects.filter(user=self.user).order_by('start_time')
        self.activity_count = self.activities.count()
        self.total_activity_duration = self.activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        self.total_calories_burned = self.activities.aggregate(Sum('calories_burned'))['calories_burned__sum'] or 0
    
    def _load_all_sleep(self):
        """جلب جميع سجلات النوم"""
        self.sleep_records = Sleep.objects.filter(user=self.user).order_by('sleep_start')
        self.sleep_count = self.sleep_records.count()
        
        # حساب متوسط مدة النوم
        total_sleep = 0
        for sleep in self.sleep_records:
            if sleep.sleep_end and sleep.sleep_start:
                duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                if 0 < duration < 24:
                    total_sleep += duration
        self.avg_sleep_hours = round(total_sleep / self.sleep_count, 1) if self.sleep_count > 0 else 0
    
    def _load_all_mood(self):
        """جلب جميع سجلات المزاج"""
        self.mood_records = MoodEntry.objects.filter(user=self.user).order_by('entry_time')
        self.mood_count = self.mood_records.count()
        
        mood_scores = {'Excellent': 5, 'Good': 4, 'Neutral': 3, 'Stressed': 2, 'Anxious': 2, 'Sad': 1}
        total_score = sum(mood_scores.get(m.mood, 3) for m in self.mood_records)
        self.avg_mood_score = round(total_score / self.mood_count, 1) if self.mood_count > 0 else 0
    
    def _load_all_meals(self):
        """جلب جميع الوجبات"""
        self.meals = Meal.objects.filter(user=self.user).order_by('meal_time')
        self.meal_count = self.meals.count()
        self.total_calories_intake = self.meals.aggregate(Sum('total_calories'))['total_calories__sum'] or 0
        self.avg_calories_per_meal = round(self.total_calories_intake / self.meal_count, 1) if self.meal_count > 0 else 0
    
    def _load_all_habits(self):
        """جلب جميع العادات"""
        self.habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        self.habit_logs = HabitLog.objects.filter(habit__user=self.user).select_related('habit')
        self.habit_count = self.habits.count()
        
        # حساب نسبة إنجاز كل عادة
        self.habit_completion_rates = {}
        for habit in self.habits:
            logs = self.habit_logs.filter(habit=habit)
            if logs.exists():
                completed = logs.filter(is_completed=True).count()
                total = logs.count()
                self.habit_completion_rates[habit.name] = round((completed / total) * 100, 1) if total > 0 else 0
    
    def _load_all_medications(self):
        """جلب جميع الأدوية"""
        self.medications = UserMedication.objects.filter(user=self.user).select_related('medication')
        self.medication_count = self.medications.count()
    
    def _load_all_conditions(self):
        """جلب جميع الأمراض المزمنة"""
        self.conditions = ChronicCondition.objects.filter(user=self.user, is_active=True)
        self.conditions_count = self.conditions.count()
    
    def _calculate_basic_stats(self):
        """حساب الإحصائيات الأساسية لجميع البيانات"""
        # الفترة الزمنية
        dates = []
        if self.health_records.exists():
            dates.extend([r.recorded_at.date() for r in self.health_records])
        if self.activities.exists():
            dates.extend([a.start_time.date() for a in self.activities])
        if self.sleep_records.exists():
            dates.extend([s.sleep_start.date() for s in self.sleep_records])
        
        if dates:
            self.first_record_date = min(dates)
            self.last_record_date = max(dates)
            self.tracking_days = (self.last_record_date - self.first_record_date).days
        else:
            self.first_record_date = self.today
            self.last_record_date = self.today
            self.tracking_days = 0
        
        # تقدم الوزن
        self.weight_progress = None
        if self.health_records.exists() and self.health_records.first().weight_kg and self.health_records.last().weight_kg:
            first_weight = float(self.health_records.first().weight_kg)
            last_weight = float(self.health_records.last().weight_kg)
            self.weight_change = round(last_weight - first_weight, 1)
            self.weight_change_percentage = round((self.weight_change / first_weight) * 100, 1) if first_weight > 0 else 0
    
    def _t(self, ar_text, en_text, **kwargs):
        """ترجمة النصوص"""
        text = ar_text if self.is_arabic else en_text
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text
    
    # ==========================================================================
    # ✅ تحليل شامل لجميع البيانات
    # ==========================================================================
    
    def analyze_lifetime_health_summary(self):
        """تحليل شامل لكل البيانات المخزنة"""
        
        # تحديد مستوى النشاط بناءً على البيانات الفعلية
        if self.activity_count > 0:
            avg_weekly_activity = (self.total_activity_duration / self.tracking_days) * 7 if self.tracking_days > 0 else 0
            if avg_weekly_activity >= 150:
                actual_activity_level = 'high'
            elif avg_weekly_activity >= 75:
                actual_activity_level = 'medium'
            else:
                actual_activity_level = 'low'
        else:
            actual_activity_level = 'none'
        
        # تحديد انتظام النوم
        sleep_regularity = 'good'
        if self.sleep_count > 10:
            durations = []
            for sleep in self.sleep_records:
                if sleep.sleep_end and sleep.sleep_start:
                    duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                    if 0 < duration < 24:
                        durations.append(duration)
            if durations and len(durations) > 5:
                std_dev = np.std(durations)
                if std_dev > 2:
                    sleep_regularity = 'irregular'
                elif std_dev > 1:
                    sleep_regularity = 'moderate'
        
        return {
            'tracking_period': {
                'start_date': self.first_record_date.isoformat(),
                'end_date': self.last_record_date.isoformat(),
                'total_days': self.tracking_days,
                'total_weeks': round(self.tracking_days / 7, 1)
            },
            'activity_summary': {
                'total_activities': self.activity_count,
                'total_duration_minutes': self.total_activity_duration,
                'total_calories_burned': self.total_calories_burned,
                'avg_weekly_activity': round((self.total_activity_duration / self.tracking_days) * 7, 1) if self.tracking_days > 0 else 0,
                'actual_activity_level': actual_activity_level
            },
            'sleep_summary': {
                'total_nights': self.sleep_count,
                'average_hours': self.avg_sleep_hours,
                'regularity': sleep_regularity
            },
            'mood_summary': {
                'total_entries': self.mood_count,
                'average_score': self.avg_mood_score,
                'average_rating': self._t(
                    self._get_mood_text(self.avg_mood_score),
                    self._get_mood_text(self.avg_mood_score)
                )
            },
            'nutrition_summary': {
                'total_meals': self.meal_count,
                'total_calories': self.total_calories_intake,
                'average_calories_per_day': round(self.total_calories_intake / self.tracking_days, 1) if self.tracking_days > 0 else 0
            },
            'weight_summary': {
                'initial_weight': self.user_initial_weight,
                'latest_weight': float(self.health_records.last().weight_kg) if self.health_records.last() and self.health_records.last().weight_kg else None,
                'weight_change': self.weight_change,
                'weight_change_percentage': self.weight_change_percentage,
                'trend': 'gaining' if self.weight_change > 0 else 'losing' if self.weight_change < 0 else 'stable'
            },
            'habits_summary': {
                'total_habits': self.habit_count,
                'best_habit': max(self.habit_completion_rates, key=self.habit_completion_rates.get) if self.habit_completion_rates else None,
                'worst_habit': min(self.habit_completion_rates, key=self.habit_completion_rates.get) if self.habit_completion_rates else None,
                'completion_rates': self.habit_completion_rates
            },
            'health_stats': {
                'total_health_records': self.health_count,
                'medications_count': self.medication_count,
                'chronic_conditions_count': self.conditions_count
            }
        }
    
    def _get_mood_text(self, score):
        """تحويل درجة المزاج إلى نص"""
        if score >= 4.5:
            return 'ممتاز' if self.is_arabic else 'Excellent'
        elif score >= 3.5:
            return 'جيد' if self.is_arabic else 'Good'
        elif score >= 2.5:
            return 'محايد' if self.is_arabic else 'Neutral'
        elif score >= 1.5:
            return 'منخفض' if self.is_arabic else 'Low'
        else:
            return 'سيء' if self.is_arabic else 'Poor'
    
    def generate_smart_recommendations(self):
        """
        توليد توصيات ذكية بناءً على تحليل كامل لجميع البيانات
        """
        recommendations = []
        summary = self.analyze_lifetime_health_summary()
        
        # 1. توصيات النشاط البدني
        if summary['activity_summary']['actual_activity_level'] == 'none':
            recommendations.append({
                'priority': 'high',
                'icon': '🏃',
                'category': 'activity',
                'title': self._t('ابدأ رحلة النشاط البدني', 'Start Your Physical Activity Journey'),
                'description': self._t('لم يتم تسجيل أي نشاط بدني بعد. ابدأ بالمشي 10 دقائق يومياً', 'No physical activity recorded yet. Start with 10 minutes of walking daily'),
                'actionable_tip': self._t('🚶 المشي لمدة 10 دقائق بعد كل وجبة', '🚶 Walk for 10 minutes after each meal')
            })
        elif summary['activity_summary']['actual_activity_level'] == 'low':
            recommendations.append({
                'priority': 'high',
                'icon': '📈',
                'category': 'activity',
                'title': self._t('زد نشاطك البدني', 'Increase Your Physical Activity'),
                'description': self._t(f'متوسط نشاطك الأسبوعي {summary["activity_summary"]["avg_weekly_activity"]} دقيقة، الهدف 150 دقيقة', 
                                      f'Your weekly average is {summary["activity_summary"]["avg_weekly_activity"]} minutes, target is 150 minutes'),
                'actionable_tip': self._t('🎯 أضف 15 دقيقة مشي إضافية يومياً', '🎯 Add 15 extra minutes of walking daily')
            })
        
        # 2. توصيات النوم
        if summary['sleep_summary']['average_hours'] < 7 and summary['sleep_summary']['average_hours'] > 0:
            recommendations.append({
                'priority': 'high',
                'icon': '😴',
                'category': 'sleep',
                'title': self._t('حسّن جودة نومك', 'Improve Your Sleep Quality'),
                'description': self._t(f'متوسط نومك {summary["sleep_summary"]["average_hours"]} ساعات، أقل من الموصى به (7-9 ساعات)',
                                      f'Your average sleep is {summary["sleep_summary"]["average_hours"]} hours, below recommended (7-9 hours)'),
                'actionable_tip': self._t('🌙 ثبّت موعد نومك واسترخِ قبل النوم بساعة', '🌙 Set a consistent bedtime and relax one hour before sleep')
            })
        elif summary['sleep_summary']['average_hours'] > 9 and summary['sleep_summary']['average_hours'] > 0:
            recommendations.append({
                'priority': 'medium',
                'icon': '⏰',
                'category': 'sleep',
                'title': self._t('نومك طويل جداً', 'You\'re Sleeping Too Much'),
                'description': self._t(f'متوسط نومك {summary["sleep_summary"]["average_hours"]} ساعات، النوم الزائد قد يسبب الخمول',
                                      f'Your average sleep is {summary["sleep_summary"]["average_hours"]} hours, oversleeping may cause lethargy'),
                'actionable_tip': self._t('⏰ حدد منبهاً للاستيقاظ في نفس الوقت يومياً', '⏰ Set an alarm to wake up at the same time daily')
            })
        
        # 3. توصيات الوزن
        if summary['weight_summary']['weight_change']:
            if abs(summary['weight_summary']['weight_change']) > 2:
                if summary['weight_summary']['trend'] == 'gaining':
                    recommendations.append({
                        'priority': 'high',
                        'icon': '⚖️',
                        'category': 'weight',
                        'title': self._t('انتبه لزيادة الوزن', 'Watch Your Weight Gain'),
                        'description': self._t(f'وزنك زاد {abs(summary["weight_summary"]["weight_change"])} كجم خلال فترة المتابعة',
                                              f'Your weight increased by {abs(summary["weight_summary"]["weight_change"])} kg during tracking'),
                        'actionable_tip': self._t('🥗 قلل السكريات وزد الخضروات في وجباتك', '🥗 Reduce sugars and increase vegetables in your meals')
                    })
                elif summary['weight_summary']['trend'] == 'losing' and summary['weight_summary']['weight_change'] < -2:
                    recommendations.append({
                        'priority': 'high',
                        'icon': '⚖️',
                        'category': 'weight',
                        'title': self._t('انتبه لنقص الوزن', 'Watch Your Weight Loss'),
                        'description': self._t(f'وزنك نقص {abs(summary["weight_summary"]["weight_change"])} كجم خلال فترة المتابعة',
                                              f'Your weight decreased by {abs(summary["weight_summary"]["weight_change"])} kg during tracking'),
                        'actionable_tip': self._t('🍚 أضف وجبة خفيفة صحية إضافية يومياً', '🍚 Add an extra healthy snack daily')
                    })
        
        # 4. توصيات العادات
        if summary['habits_summary']['best_habit']:
            recommendations.append({
                'priority': 'low',
                'icon': '🌟',
                'category': 'habits',
                'title': self._t('استمرارية ممتازة', 'Excellent Consistency'),
                'description': self._t(f'عادة "{summary["habits_summary"]["best_habit"]}" هي الأفضل لديك بنسبة {summary["habits_summary"]["completion_rates"][summary["habits_summary"]["best_habit"]]}%',
                                      f'Habit "{summary["habits_summary"]["best_habit"]}" is your best with {summary["habits_summary"]["completion_rates"][summary["habits_summary"]["best_habit"]]}% completion'),
                'actionable_tip': self._t('🎯 حاول تطبيق نفس الالتزام على عادات أخرى', '🎯 Try to apply the same commitment to other habits')
            })
        
        # 5. توصية عامة للمبتدئين
        if self.tracking_days < 14:
            recommendations.append({
                'priority': 'medium',
                'icon': '🌱',
                'category': 'general',
                'title': self._t('بداية رائعة!', 'Great Start!'),
                'description': self._t(f'أنت تتابع صحتك منذ {self.tracking_days} يوماً. استمر في التسجيل للحصول على تحليلات أعمق',
                                      f'You\'ve been tracking for {self.tracking_days} days. Keep logging for deeper insights'),
                'actionable_tip': self._t('📝 سجل بياناتك يومياً للحصول على توصيات أكثر دقة', '📝 Log your data daily for more accurate recommendations')
            })
        
        # 6. توصية للمستخدمين النشطين
        if self.tracking_days > 30 and self.activity_count > 20:
            recommendations.append({
                'priority': 'low',
                'icon': '🏆',
                'category': 'motivation',
                'title': self._t('ملتزم ونشط!', 'Committed and Active!'),
                'description': self._t(f'أحسنت! سجلت {self.activity_count} نشاط و {self.meal_count} وجبة',
                                      f'Great job! You\'ve recorded {self.activity_count} activities and {self.meal_count} meals'),
                'actionable_tip': self._t('🎉 كافئ نفسك على هذا الالتزام الرائع', '🎉 Reward yourself for this great commitment')
            })
        
        return recommendations
    
    def predict_with_all_data(self):
        """
        توقعات مستقبلية باستخدام جميع البيانات المتاحة
        """
        predictions = {
            'weight_trend': None,
            'activity_forecast': None,
            'mood_forecast': None
        }
        
        # توقع اتجاه الوزن إذا كانت البيانات كافية
        if self.health_records.count() >= 10:
            try:
                weights = []
                dates = []
                for record in self.health_records:
                    if record.weight_kg:
                        weights.append(float(record.weight_kg))
                        dates.append(record.recorded_at.toordinal())
                
                if len(weights) >= 7:
                    # الانحدار الخطي للتنبؤ
                    dates_array = np.array(dates).reshape(-1, 1)
                    weights_array = np.array(weights)
                    model = LinearRegression()
                    model.fit(dates_array, weights_array)
                    
                    future_ordinal = dates_array[-1][0] + 14  # توقع بعد أسبوعين
                    predicted_weight = model.predict([[future_ordinal]])[0]
                    current_weight = weights[-1]
                    
                    predictions['weight_trend'] = {
                        'current': round(current_weight, 1),
                        'predicted_2weeks': round(predicted_weight, 1),
                        'trend': 'up' if predicted_weight > current_weight else 'down' if predicted_weight < current_weight else 'stable',
                        'change': round(predicted_weight - current_weight, 1),
                        'confidence': round(min(90, 50 + len(weights) * 2), 1)
                    }
            except Exception as e:
                print(f"Weight prediction error: {e}")
        
        # تحليل الموسمية للمزاج
        if self.mood_records.count() >= 14:
            mood_scores = {'Excellent': 5, 'Good': 4, 'Neutral': 3, 'Stressed': 2, 'Anxious': 2, 'Sad': 1}
            scores = []
            for mood in self.mood_records:
                score = mood_scores.get(mood.mood, 3)
                scores.append(score)
            
            recent_scores = scores[-14:]
            recent_avg = sum(recent_scores) / len(recent_scores)
            overall_avg = sum(scores) / len(scores)
            
            predictions['mood_forecast'] = {
                'recent_average': round(recent_avg, 1),
                'overall_average': round(overall_avg, 1),
                'trend': 'improving' if recent_avg > overall_avg else 'declining' if recent_avg < overall_avg else 'stable',
                'message': self._t(
                    'مزاجك في تحسن مؤخراً، استمر!' if recent_avg > overall_avg else
                    'لاحظنا انخفاضاً في مزاجك مؤخراً، خذ وقتاً للراحة' if recent_avg < overall_avg else
                    'مزاجك مستقر، حافظ على نمط حياتك',
                    'Your mood has been improving recently, keep it up!' if recent_avg > overall_avg else
                    'We noticed a recent decline in your mood, take time to rest' if recent_avg < overall_avg else
                    'Your mood is stable, maintain your lifestyle'
                )
            }
        
        return predictions
    
    def get_correlations(self):
        """
        اكتشاف الارتباطات بين الأنشطة المختلفة
        """
        correlations = []
        
        # العلاقة بين النشاط والنوم
        if self.activity_count > 10 and self.sleep_count > 10:
            # حساب الأيام التي تلتزم فيها بالتمارين
            activity_days = set(a.start_time.date() for a in self.activities if a.duration_minutes >= 20)
            good_sleep_days = set()
            for sleep in self.sleep_records:
                if sleep.sleep_end and sleep.sleep_start:
                    duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                    if 7 <= duration <= 9:
                        good_sleep_days.add(sleep.sleep_start.date())
            
            overlap = activity_days.intersection(good_sleep_days)
            if len(activity_days) > 0:
                correlation_rate = (len(overlap) / len(activity_days)) * 100
                
                if correlation_rate > 60:
                    correlations.append({
                        'icon': '😴🏃',
                        'title': self._t('النشاط والنوم', 'Activity & Sleep'),
                        'description': self._t(f'في {correlation_rate:.0f}% من أيام تمرينك، تحصل على نوم جيد', 
                                              f'On {correlation_rate:.0f}% of your exercise days, you get good sleep'),
                        'strength': round(correlation_rate / 100, 2)
                    })
        
        # العلاقة بين العادات والمزاج
        if self.habit_logs.count() > 20 and self.mood_count > 10:
            good_mood_days = set()
            for mood in self.mood_records:
                if mood.mood in ['Excellent', 'Good']:
                    good_mood_days.add(mood.entry_time.date())
            
            habit_completion_days = set()
            for log in self.habit_logs:
                if log.is_completed:
                    habit_completion_days.add(log.log_date)
            
            overlap = habit_completion_days.intersection(good_mood_days)
            if len(habit_completion_days) > 0:
                correlation_rate = (len(overlap) / len(habit_completion_days)) * 100
                
                if correlation_rate > 50:
                    correlations.append({
                        'icon': '✅😊',
                        'title': self._t('العادات والمزاج', 'Habits & Mood'),
                        'description': self._t(f'عندما تلتزم بعاداتك، يكون مزاجك أفضل بنسبة {correlation_rate:.0f}%',
                                              f'When you stick to your habits, your mood is {correlation_rate:.0f}% better'),
                        'strength': round(correlation_rate / 100, 2)
                    })
        
        return correlations
    
    def analyze_all(self):
        """التحليل الشامل لكل البيانات"""
        return {
            'lifetime_summary': self.analyze_lifetime_health_summary(),
            'smart_recommendations': self.generate_smart_recommendations(),
            'predictions': self.predict_with_all_data(),
            'correlations': self.get_correlations(),
            'user_info': {
                'age': self.user_age,
                'gender': self.user_gender,
                'height_cm': self.user_height,
                'health_goal': self.user_health_goal,
                'tracking_since': self.first_record_date.isoformat(),
                'total_tracking_days': self.tracking_days
            }
        }


# ==============================================================================
# الخدمة الرئيسية
# ==============================================================================

class CrossInsightsMLService:
    """الخدمة الرئيسية للتحليلات المتقاطعة الشاملة"""
    
    def __init__(self, user):
        self.user = user
        self.engine = HealthInsightsEngineML(user)
    
    def get_complete_analysis(self):
        """الحصول على تحليل كامل وشامل لجميع البيانات"""
        try:
            analysis = self.engine.analyze_all()
            
            return {
                'success': True,
                'is_arabic': self.engine.is_arabic,
                'data': analysis,
                'timestamp': timezone.now().isoformat(),
                'user_name': self.user.get_full_name() or self.user.username,
                'data_coverage': {
                    'total_days_tracked': self.engine.tracking_days,
                    'total_records': self.engine.health_count + self.engine.activity_count + self.engine.sleep_count + self.engine.mood_count,
                    'has_sufficient_data': self.engine.tracking_days >= 7
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'حدث خطأ أثناء تحليل البيانات' if self.engine.is_arabic else 'An error occurred while analyzing data'
            }


def get_health_insights(user, language='ar'):
    """دالة مساعدة للحصول على التحليلات الصحية للمستخدم"""
    service = CrossInsightsMLService(user)
    service.engine.language = language
    service.engine.is_arabic = language == 'ar'
    return service.get_complete_analysis()
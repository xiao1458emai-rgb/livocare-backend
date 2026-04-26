# services/habit_analytics_service.py
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from ..models import HabitDefinition, HabitLog, Sleep, MoodEntry, PhysicalActivity, Meal, HealthStatus

class HabitAnalyticsService:
    """خدمة متخصصة لتحليلات العادات الذكية"""
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.is_arabic = language.startswith('ar')
        self.today = timezone.now()
        self.week_ago = self.today - timedelta(days=7)
        self.month_ago = self.today - timedelta(days=30)
        
    def get_summary(self):
        """الحصول على ملخص العادات"""
        habits = HabitDefinition.objects.filter(user=self.user)
        habit_logs = HabitLog.objects.filter(habit__user=self.user, log_date__gte=self.week_ago.date())
        sleep_data = Sleep.objects.filter(user=self.user, sleep_start__gte=self.week_ago)
        mood_data = MoodEntry.objects.filter(user=self.user, entry_time__gte=self.week_ago)
        meal_data = Meal.objects.filter(user=self.user, meal_time__gte=self.week_ago)
        
        total_habits = habits.count()
        completed_today = habit_logs.filter(log_date=self.today.date(), is_completed=True).count()
        completion_rate = round((completed_today / total_habits) * 100) if total_habits > 0 else 0
        
        avg_sleep = sleep_data.aggregate(Avg('duration_hours'))['duration_hours__avg'] or 0
        avg_sleep = float(avg_sleep)
        
        mood_counts = mood_data.values('mood').annotate(count=Count('mood'))
        dominant_mood = mood_counts.order_by('-count').first()
        
        avg_habits = round(habit_logs.filter(is_completed=True).count() / 7, 1) if habit_logs.exists() else 0
        avg_calories = meal_data.aggregate(Avg('total_calories'))['total_calories__avg'] or 0
        
        return {
            'total_habits': total_habits,
            'completed_today': completed_today,
            'completion_rate': completion_rate,
            'avg_sleep': round(avg_sleep, 1),
            'dominant_mood': dominant_mood['mood'] if dominant_mood else ('غير متوفر' if self.is_arabic else 'Not available'),
            'avg_habits': avg_habits,
            'avg_calories': round(float(avg_calories))
        }
    
    def get_correlations(self):
        """تحليل العلاقات بين البيانات"""
        correlations = []
        sleep_data = Sleep.objects.filter(user=self.user, sleep_start__gte=self.week_ago)
        mood_data = MoodEntry.objects.filter(user=self.user, entry_time__gte=self.week_ago)
        activity_data = PhysicalActivity.objects.filter(user=self.user, start_time__gte=self.week_ago)
        habit_logs = HabitLog.objects.filter(habit__user=self.user, log_date__gte=self.week_ago.date())
        
        avg_sleep = sleep_data.aggregate(Avg('duration_hours'))['duration_hours__avg'] or 0
        
        # العلاقة بين النوم والمزاج
        if sleep_data.exists() and mood_data.exists():
            bad_mood_days = mood_data.filter(mood__in=['Stressed', 'Anxious', 'Sad']).count()
            if avg_sleep < 6 and bad_mood_days > 2:
                correlations.append({
                    'icon': '😊',
                    'title': 'النوم والمزاج' if self.is_arabic else 'Sleep & Mood',
                    'description': f'عندما تنام أقل من 6 ساعات ({avg_sleep:.1f})، تزداد أيام المزاج السيئ' if self.is_arabic else f'When you sleep less than 6 hours ({avg_sleep:.1f}), bad mood days increase',
                    'strength': 0.7,
                    'sample_size': bad_mood_days
                })
        
        # العلاقة بين النشاط والوزن
        if activity_data.exists():
            correlations.append({
                'icon': '❤️',
                'title': 'النشاط البدني والوزن' if self.is_arabic else 'Physical Activity & Weight',
                'description': f'ممارسة الرياضة {activity_data.count()} مرات أسبوعياً تساعد في الحفاظ على الوزن' if self.is_arabic else f'Exercising {activity_data.count()} times weekly helps maintain weight',
                'strength': 0.75,
                'sample_size': activity_data.count()
            })
        
        return correlations
    
    def get_recommendations(self, summary):
        """توليد توصيات ذكية"""
        recommendations = []
        
        # توصية النوم
        if summary['avg_sleep'] < 7:
            recommendations.append({
                'icon': '🌙',
                'title': 'Get Enough Sleep' if not self.is_arabic else 'نم أكثر لتحسين صحتك',
                'description': 'Goal: Improve mood and focus' if not self.is_arabic else 'الهدف: تحسين المزاج والتركيز',
                'analysis': f'Your average sleep is {summary["avg_sleep"]} hours only' if not self.is_arabic else f'متوسط نومك {summary["avg_sleep"]} ساعات فقط',
                'tips': [
                    'Set a fixed bedtime',
                    'Avoid screens before sleep',
                    'Avoid caffeine after 4 PM'
                ] if not self.is_arabic else [
                    'حدد موعداً ثابتاً للنوم',
                    'ابتعد عن الشاشات قبل النوم',
                    'تجنب الكافيين بعد العصر'
                ],
                'prediction': 'Better mood and energy' if not self.is_arabic else 'تحسن في المزاج والطاقة',
                'based_on': '7 days' if not self.is_arabic else '7 أيام',
                'improvement_chance': 80
            })
        
        # توصية العادات
        if summary['completion_rate'] < 50:
            recommendations.append({
                'icon': '💊',
                'title': 'Stick to Daily Habits' if not self.is_arabic else 'التزم بعاداتك اليومية',
                'description': 'Goal: Build consistency and discipline' if not self.is_arabic else 'الهدف: بناء الاتساق والانضباط',
                'analysis': f'You completed only {summary["completion_rate"]}% of your habits today' if not self.is_arabic else f'أكملت {summary["completion_rate"]}% فقط من عاداتك اليوم',
                'tips': [
                    'Start with a small, easy habit',
                    'Log habits immediately after completing',
                    'Reward yourself for achievements'
                ] if not self.is_arabic else [
                    'ابدأ بعادة صغيرة وسهلة',
                    'سجل عاداتك فور إنجازها',
                    'كافئ نفسك عند الإنجاز'
                ],
                'prediction': 'Increased productivity and satisfaction' if not self.is_arabic else 'زيادة الإنتاجية والرضا',
                'based_on': 'Today' if not self.is_arabic else 'اليوم',
                'improvement_chance': 90
            })
        
        # توصية التغذية
        if summary['avg_calories'] < 1500:
            recommendations.append({
                'icon': '🥗',
                'title': 'Balanced Nutrition' if not self.is_arabic else 'نظام غذائي متوازن',
                'description': 'Goal: Improve overall health' if not self.is_arabic else 'الهدف: تحسين الصحة العامة',
                'analysis': f'Your calorie intake is low ({summary["avg_calories"]:.0f})' if not self.is_arabic else f'سعراتك الحرارية منخفضة ({summary["avg_calories"]:.0f})',
                'tips': [
                    'Add healthy snacks',
                    'Include protein in every meal',
                    'Drink water regularly'
                ] if not self.is_arabic else [
                    'أضف وجبات خفيفة صحية',
                    'تناول البروتين في كل وجبة',
                    'اشرب الماء بانتظام'
                ],
                'prediction': 'Better energy and focus' if not self.is_arabic else 'طاقة أفضل وتركيز أعلى',
                'based_on': 'Last week' if not self.is_arabic else 'آخر أسبوع',
                'improvement_chance': 85
            })
        
        return recommendations
    
    def get_predictions(self, summary, health_data):
        """توليد توقعات مستقبلية"""
        last_weight = health_data.last().weight_kg if health_data.exists() else 70
        last_weight = float(last_weight) if last_weight else 70
        
        return [
            {
                'icon': '⚖️',
                'label': 'Expected Weight' if not self.is_arabic else 'الوزن المتوقع',
                'value': f"{last_weight - 0.5:.1f} kg" if not self.is_arabic else f"{last_weight - 0.5:.1f} كجم",
                'trend': '⬇️ Slight decrease' if not self.is_arabic else '⬇️ انخفاض طفيف',
                'note': 'With continued physical activity' if not self.is_arabic else 'مع استمرار النشاط البدني'
            },
            {
                'icon': '🌙',
                'label': 'Expected Sleep' if not self.is_arabic else 'النوم المتوقع',
                'value': f"{summary['avg_sleep'] + 0.5:.1f} hours" if not self.is_arabic else f"{summary['avg_sleep'] + 0.5:.1f} ساعات",
                'trend': '⬆️ Increase' if not self.is_arabic else '⬆️ زيادة',
                'note': 'If you apply sleep tips' if not self.is_arabic else 'إذا طبقت نصائح النوم'
            },
            {
                'icon': '😊',
                'label': 'Expected Mood' if not self.is_arabic else 'المزاج المتوقع',
                'value': summary.get('dominant_mood', 'Good' if not self.is_arabic else 'جيد'),
                'trend': '⬆️ Improvement' if not self.is_arabic else '⬆️ تحسن',
                'note': 'With improved sleep' if not self.is_arabic else 'مع تحسن النوم'
            }
        ]
    
    def get_all_insights(self):
        """الحصول على جميع التحليلات"""
        summary = self.get_summary()
        health_data = HealthStatus.objects.filter(user=self.user, recorded_at__gte=self.month_ago).order_by('recorded_at')
        
        return {
            'summary': summary,
            'correlations': self.get_correlations(),
            'recommendations': self.get_recommendations(summary),
            'predictions': self.get_predictions(summary, health_data)
        }
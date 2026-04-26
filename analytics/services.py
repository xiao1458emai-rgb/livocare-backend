# analytics/services.py
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Avg, Count
from main.models import Sleep, HabitDefinition, HabitLog, MoodEntry
from .models import SleepInsight, HabitInsight, MoodInsight, NutritionInsight

# ==============================================================================
# 🛌 خدمة تحليلات النوم - نسخة معدلة مع DELETE + CREATE
# ==============================================================================

class SleepAnalyticsService:
    """خدمة تحليلات النوم الذكية"""
    
    def __init__(self, user):
        self.user = user
        self.today = timezone.now().date()
        
    def generate_weekly_insights(self):
        """توليد تحليلات أسبوعية للنوم"""
        
        print(f"🔍 توليد تحليلات للمستخدم: {self.user.username}")
        print(f"📅 اليوم: {self.today}")
        print("="*40)
        print("⚙️ استخدام الكود الجديد مع DELETE + CREATE (حذف الكل)")
        
        # حساب تواريخ الأسبوع الحالي والماضي
        week_ago = self.today - timedelta(days=7)
        two_weeks_ago = self.today - timedelta(days=14)
        
        print(f"📅 الأسبوع الحالي: من {week_ago} إلى {self.today}")
        
        # ✅ جلب نوم الأسبوع الحالي (باستخدام وقت الاستيقاظ)
        current_week_sleep = Sleep.objects.filter(
            user=self.user,
            sleep_end__date__gte=week_ago,
            sleep_end__date__lte=self.today
        )
        
        print(f"📊 عدد سجلات الأسبوع الحالي: {current_week_sleep.count()}")
        
        # عرض كل سجل للتشخيص
        for sleep in current_week_sleep:
            print(f"   📅 {sleep.sleep_start} → {sleep.sleep_end}")
            print(f"      المدة المخزنة: {sleep.duration_hours}")
            print(f"      الجودة: {sleep.quality_rating}")
        
        # جلب نوم الأسبوع الماضي للمقارنة
        last_week_sleep = Sleep.objects.filter(
            user=self.user,
            sleep_end__date__gte=two_weeks_ago,
            sleep_end__date__lt=week_ago
        )
        
        # تحليل الأسبوع الحالي
        current_stats = self._calculate_stats(current_week_sleep)
        last_stats = self._calculate_stats(last_week_sleep)
        
        print(f"📊 إحصائيات الأسبوع الحالي: {current_stats}")
        
        # حساب نسب التغيير
        hours_change = self._calculate_percentage_change(
            last_stats['total_hours'], 
            current_stats['total_hours']
        )
        
        quality_change = self._calculate_percentage_change(
            last_stats['avg_quality'],
            current_stats['avg_quality']
        )
        
        # تحليل الاتجاه
        trend = self._analyze_trend(current_stats, hours_change)
        
        # توليد توصيات ذكية
        recommendations = self._generate_recommendations(
            current_stats, 
            hours_change,
            quality_change,
            trend
        )
        
        # ✅ حذف جميع التحليلات القديمة (لنفس المستخدم)
        old_insights = SleepInsight.objects.filter(user=self.user)
        old_count = old_insights.count()
        print(f"🗑️ عدد جميع التحليلات القديمة: {old_count}")
        
        if old_count > 0:
            print(f"📝 التحليلات القديمة:")
            for insight in old_insights:
                print(f"   - ID={insight.id}, date={insight.date}, avg_hours={insight.weekly_avg_hours}")
            deleted = old_insights.delete()
            print(f"✅ تم حذف {deleted} تحليل قديم")
        
        # ✅ إنشاء تحليل جديد
        print("📝 إنشاء تحليل جديد...")
        insight = SleepInsight.objects.create(
            user=self.user,
            date=self.today,
            weekly_total_hours=current_stats['total_hours'],
            weekly_avg_hours=current_stats['avg_hours'],
            weekly_avg_quality=current_stats['avg_quality'],
            hours_change_percentage=hours_change,
            quality_change_percentage=quality_change,
            recommendations=recommendations,
            trend=trend
        )
        
        print(f"✅ تم إنشاء تحليل النوم الجديد (ID: {insight.id})")
        print(f"   📊 total={insight.weekly_total_hours}, avg={insight.weekly_avg_hours}, quality={insight.weekly_avg_quality}")
        print("="*40)
        return insight

    def _calculate_stats(self, sleep_entries):
        """حساب إحصائيات مجموعة من سجلات النوم"""
        if not sleep_entries.exists():
            return {
                'total_hours': 0,
                'avg_hours': 0,
                'avg_quality': 0,
                'count': 0
            }
        
        total_hours = 0
        total_quality = 0
        count = 0
        
        for sleep in sleep_entries:
            if sleep.duration_hours:
                try:
                    hours = float(sleep.duration_hours)
                    if hours <= 24:
                        total_hours += hours
                        count += 1
                        print(f"✅ سجل {sleep.id}: {hours} ساعات (من duration_hours)")
                    else:
                        print(f"⚠️ سجل {sleep.id}: مدة غير معقولة {hours} ساعات - يتم تجاهلها")
                except (TypeError, ValueError):
                    if sleep.sleep_start and sleep.sleep_end:
                        duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                        if duration <= 24:
                            total_hours += duration
                            count += 1
                            print(f"✅ سجل {sleep.id}: {duration} ساعات (محسوب يدوياً)")
                        else:
                            print(f"⚠️ سجل {sleep.id}: مدة غير معقولة {duration} ساعات - يتم تجاهلها")
            else:
                if sleep.sleep_start and sleep.sleep_end:
                    duration = (sleep.sleep_end - sleep.sleep_start).total_seconds() / 3600
                    if duration <= 24:
                        total_hours += duration
                        count += 1
                        print(f"✅ سجل {sleep.id}: {duration} ساعات (محسوب يدوياً - لا يوجد duration_hours)")
                    else:
                        print(f"⚠️ سجل {sleep.id}: مدة غير معقولة {duration} ساعات - يتم تجاهلها")
            
            if sleep.quality_rating:
                total_quality += sleep.quality_rating
        
        avg_hours = round(total_hours / count, 1) if count > 0 else 0
        avg_quality = round(total_quality / count, 1) if count > 0 else 0
        
        stats = {
            'total_hours': round(total_hours, 1),
            'avg_hours': avg_hours,
            'avg_quality': avg_quality,
            'count': count
        }
        
        print(f"📊 إحصائيات المجموعة: {stats}")
        return stats
    
    def _calculate_percentage_change(self, old_value, new_value):
        """حساب نسبة التغير"""
        if old_value == 0:
            return 100 if new_value > 0 else 0
        return round(((new_value - old_value) / old_value) * 100, 1)
    
    def _analyze_trend(self, stats, hours_change):
        """تحليل اتجاه النوم"""
        if stats['count'] < 3:
            return 'insufficient_data'
        
        if hours_change > 10:
            return 'improving'
        elif hours_change < -10:
            return 'declining'
        else:
            return 'stable'
    
    def _generate_recommendations(self, stats, hours_change, quality_change, trend):
        """توليد توصيات النوم"""
        recommendations = []
        
        if stats['count'] == 0:
            recommendations.append({
                'type': 'motivation',
                'message': '🌙 لم تسجل أي نوم هذا الأسبوع. تتبع نومك لتحسين جودة حياتك!',
                'priority': 'high'
            })
        elif stats['avg_hours'] < 7:
            recommendations.append({
                'type': 'warning',
                'message': f'⚠️ متوسط نومك {stats["avg_hours"]} ساعات فقط. البالغون يحتاجون 7-9 ساعات يومياً',
                'priority': 'high'
            })
        elif stats['avg_hours'] > 9:
            recommendations.append({
                'type': 'info',
                'message': '💤 تنام أكثر من المعدل الطبيعي. حاول تحسين جودة النوم بدل الكمية',
                'priority': 'medium'
            })
        else:
            recommendations.append({
                'type': 'success',
                'message': '✅ ممتاز! أنت تحصل على قسط كافٍ من النوم',
                'priority': 'low'
            })
        
        if stats['avg_quality'] < 3 and stats['count'] > 0:
            recommendations.append({
                'type': 'tip',
                'message': '😴 جودة نومك منخفضة. جرب: تجنب الكافيين قبل النوم، وابتعد عن الشاشات بساعة',
                'priority': 'high'
            })
        
        if hours_change > 20:
            recommendations.append({
                'type': 'praise',
                'message': '🌟 تحسن ملحوظ في عدد ساعات النوم! استمر بهذا الانتظام',
                'priority': 'medium'
            })
        elif hours_change < -20:
            recommendations.append({
                'type': 'warning',
                'message': '⚠️ نومك أقل من الأسبوع الماضي. حاول النوم مبكراً',
                'priority': 'high'
            })
        
        return recommendations


# ==============================================================================
# 💊 خدمة تحليلات العادات - نسخة معدلة مع تشخيص DELETE
# ==============================================================================

class HabitAnalyticsService:
    """خدمة تحليلات العادات الذكية"""
    
    def __init__(self, user):
        self.user = user
        self.today = timezone.now().date()
        
    def generate_insights(self):
        """توليد تحليلات العادات"""
        
        print(f"🔍 توليد تحليلات العادات للمستخدم: {self.user.username}")
        print(f"📅 اليوم: {self.today}")
        print("="*40)
        print("⚙️ استخدام الكود الجديد مع DELETE + CREATE (حذف الكل)")
        
        # جلب جميع العادات
        habits = HabitDefinition.objects.filter(user=self.user)
        total_habits = habits.count()
        print(f"📋 عدد العادات: {total_habits}")
        
        # جلب سجلات اليوم
        today_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date=self.today,
            is_completed=True
        )
        completed_today = today_logs.count()
        print(f"✅ مكتمل اليوم: {completed_today}")
        
        # حساب نسبة الإنجاز
        completion_rate = 0
        if total_habits > 0:
            completion_rate = round((completed_today / total_habits) * 100, 1)
        print(f"📊 نسبة الإنجاز: {completion_rate}%")
        
        # حساب أفضل العادات
        top_habits = self._calculate_top_habits(habits)
        print(f"🏆 أفضل العادات: {len(top_habits)}")
        
        # تحليل الاتجاه
        trend = self._analyze_trend()
        print(f"📈 الاتجاه: {trend}")
        
        # توليد توصيات
        recommendations = self._generate_recommendations(
            total_habits, completed_today, completion_rate, trend
        )
        print(f"💡 التوصيات: {len(recommendations)}")
        
        # ✅ حذف جميع التحليلات القديمة (لنفس المستخدم)
        old_insights = HabitInsight.objects.filter(user=self.user)
        old_count = old_insights.count()
        print(f"🗑️ عدد جميع التحليلات القديمة: {old_count}")
        
        if old_count > 0:
            print(f"📝 التحليلات القديمة:")
            for insight in old_insights:
                print(f"   - ID={insight.id}, date={insight.date}, completed_today={insight.completed_today}")
            deleted = old_insights.delete()
            print(f"✅ تم حذف {deleted} تحليل قديم")
        
        # ✅ إنشاء تحليل جديد
        print("📝 إنشاء تحليل جديد...")
        insight = HabitInsight.objects.create(
            user=self.user,
            date=self.today,
            total_habits=total_habits,
            completed_today=completed_today,
            completion_rate=completion_rate,
            top_habits=top_habits,
            recommendations=recommendations,
            trend=trend
        )
        
        print(f"✅ تم إنشاء تحليل العادات الجديد: completed_today={completed_today}, rate={completion_rate}%")
        print("="*40)
        return insight
    
    def _calculate_top_habits(self, habits):
        """حساب أفضل العادات أداءً"""
        top_habits = []
        
        for habit in habits:
            # حساب نسبة الإنجاز لآخر 30 يوم
            thirty_days_ago = self.today - timedelta(days=30)
            logs_count = HabitLog.objects.filter(
                habit=habit,
                log_date__gte=thirty_days_ago,
                is_completed=True
            ).count()
            
            completion_rate = round((logs_count / 30) * 100, 1)
            
            top_habits.append({
                'id': habit.id,
                'name': habit.name,
                'completion_rate': completion_rate
            })
        
        # ترتيب تنازلي وأخذ أول 5
        top_habits.sort(key=lambda x: x['completion_rate'], reverse=True)
        return top_habits[:5]
    
    def _analyze_trend(self):
        """تحليل اتجاه الالتزام"""
        # حساب متوسط الإنجاز لآخر 7 أيام
        week_ago = self.today - timedelta(days=7)
        two_weeks_ago = self.today - timedelta(days=14)
        
        current_week_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=week_ago,
            is_completed=True
        ).count()
        
        last_week_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=two_weeks_ago,
            log_date__lt=week_ago,
            is_completed=True
        ).count()
        
        print(f"   📊 هذا الأسبوع: {current_week_logs} إكمال")
        print(f"   📊 الأسبوع الماضي: {last_week_logs} إكمال")
        
        if current_week_logs > last_week_logs:
            return 'improving'
        elif current_week_logs < last_week_logs:
            return 'declining'
        elif current_week_logs > 0:
            return 'stable'
        else:
            return 'insufficient_data'
    
    def _generate_recommendations(self, total_habits, completed_today, completion_rate, trend):
        """توليد توصيات ذكية للعادات"""
        recommendations = []
        
        if total_habits == 0:
            recommendations.append({
                'type': 'motivation',
                'message': '💪 ابدأ بإضافة أول عادة صحية لك اليوم!',
                'priority': 'high'
            })
        elif completion_rate < 50:
            recommendations.append({
                'type': 'warning',
                'message': f'⚠️ نسبة إنجازك اليوم {completion_rate}%. حاول التركيز على العادات الأهم',
                'priority': 'high'
            })
        elif completion_rate > 80:
            recommendations.append({
                'type': 'praise',
                'message': '🌟 ممتاز! أنت ملتزم جداً بعاداتك. استمر!',
                'priority': 'low'
            })
        
        if trend == 'improving':
            recommendations.append({
                'type': 'success',
                'message': '📈 أداؤك في تحسن مستمر! حافظ على هذا التقدم',
                'priority': 'medium'
            })
        elif trend == 'declining':
            recommendations.append({
                'type': 'warning',
                'message': '📉 أداؤك في تراجع. خذ استراحة قصيرة ثم عاد بقوة',
                'priority': 'high'
            })
        
        # نصيحة عامة إذا كان هناك عادات
        if total_habits > 0 and completion_rate < 100:
            recommendations.append({
                'type': 'tip',
                'message': '💡 جرب ربط العادات الجديدة بعادات موجودة (مثلاً: تأمل بعد تنظيف الأسنان)',
                'priority': 'low'
            })
        
        return recommendations


# ==============================================================================
# 😊 خدمة تحليلات المزاج - النسخة النهائية مع DELETE + CREATE
# ==============================================================================

class MoodAnalyticsService:
    """خدمة تحليلات المزاج الذكية"""
    
    def __init__(self, user):
        self.user = user
        self.today = timezone.now().date()
    
    def generate_insights(self):
        """توليد تحليلات المزاج"""
        
        print(f"🔍 توليد تحليلات المزاج للمستخدم: {self.user.username}")
        print(f"📅 اليوم: {self.today}")
        print("="*40)
        print("⚙️ استخدام الكود الجديد مع DELETE + CREATE (حذف الكل)")
        
        # جلب جميع سجلات المزاج
        all_entries = MoodEntry.objects.filter(user=self.user)
        total_entries = all_entries.count()
        print(f"📊 إجمالي السجلات: {total_entries}")
        
        # حساب عدد الأيام
        unique_dates = all_entries.dates('entry_time', 'day').count()
        print(f"📅 أيام بالتتبع: {unique_dates}")
        
        # حساب توزيع المزاج
        mood_distribution = self._calculate_mood_distribution(all_entries)
        print(f"📊 توزيع المزاج: {mood_distribution}")
        
        # تحديد المزاج الأكثر شيوعاً
        most_common_mood = self._get_most_common_mood(mood_distribution)
        print(f"😊 المزاج الأكثر شيوعاً: {most_common_mood}")
        
        # تحليل الأنماط
        mood_patterns = self._analyze_patterns(all_entries)
        print(f"🔄 أنماط متكررة: {len(mood_patterns)}")
        
        # تحليل الاتجاه
        trend = self._analyze_trend(all_entries)
        print(f"📈 الاتجاه: {trend}")
        
        # توليد توصيات
        recommendations = self._generate_recommendations(
            total_entries, unique_dates, most_common_mood, trend
        )
        
        # ✅ حذف جميع التحليلات القديمة (لنفس المستخدم)
        old_insights = MoodInsight.objects.filter(user=self.user)
        old_count = old_insights.count()
        print(f"🗑️ عدد جميع التحليلات القديمة: {old_count}")
        
        if old_count > 0:
            print(f"📝 التحليلات القديمة:")
            for insight in old_insights:
                print(f"   - ID={insight.id}, date={insight.date}, total_entries={insight.total_entries}")
            deleted = old_insights.delete()
            print(f"✅ تم حذف {deleted} تحليل قديم")
        
        # ✅ إنشاء تحليل جديد
        print("📝 إنشاء تحليل جديد...")
        insight = MoodInsight.objects.create(
            user=self.user,
            date=self.today,
            total_entries=total_entries,
            total_days=unique_dates,
            most_common_mood=most_common_mood,
            mood_distribution=mood_distribution,
            mood_patterns=mood_patterns,
            recommendations=recommendations,
            trend=trend
        )
        
        print(f"✅ تم إنشاء تحليل المزاج الجديد (ID: {insight.id})")
        print("="*40)
        return insight
    
    def _calculate_mood_distribution(self, entries):
        distribution = {}
        for entry in entries:
            mood = entry.mood
            distribution[mood] = distribution.get(mood, 0) + 1
        return distribution
    
    def _get_most_common_mood(self, distribution):
        if not distribution:
            return 'لا يوجد'
        return max(distribution, key=distribution.get)
    
    def _analyze_patterns(self, entries):
        patterns = []
        factors_count = {}
        for entry in entries:
            if entry.factors:
                factors = entry.factors.split(',')
                for factor in factors:
                    factor = factor.strip()
                    if factor:
                        factors_count[factor] = factors_count.get(factor, 0) + 1
        
        for factor, count in sorted(factors_count.items(), key=lambda x: x[1], reverse=True)[:3]:
            if count >= 3:
                patterns.append(f"العامل '{factor}' تكرر {count} مرات")
        
        return patterns
    
    def _analyze_trend(self, entries):
        if entries.count() < 3:
            return 'insufficient_data'
        
        week_ago = timezone.now() - timedelta(days=7)
        recent_entries = entries.filter(entry_time__gte=week_ago)
        
        if recent_entries.count() < 3:
            return 'insufficient_data'
        
        mood_values = {
            'Excellent': 5, 'Good': 4, 'Neutral': 3,
            'Stressed': 2, 'Anxious': 1, 'Sad': 1
        }
        
        recent_avg = sum(mood_values.get(entry.mood, 3) for entry in recent_entries) / recent_entries.count()
        
        older_entries = entries.filter(entry_time__lt=week_ago)
        if older_entries.count() > 0:
            older_avg = sum(mood_values.get(entry.mood, 3) for entry in older_entries) / older_entries.count()
            
            if recent_avg > older_avg + 0.5:
                return 'improving'
            elif recent_avg < older_avg - 0.5:
                return 'declining'
            else:
                return 'stable'
        
        return 'stable'
    
    def _generate_recommendations(self, total_entries, total_days, most_common_mood, trend):
        recommendations = []
        
        if total_entries == 0:
            recommendations.append({
                'type': 'motivation',
                'message': '😊 ابدأ بتسجيل مشاعرك يومياً لتفهم نفسك أكثر!',
                'priority': 'high'
            })
        elif total_days < 7:
            recommendations.append({
                'type': 'info',
                'message': '📝 استمر في تسجيل مزاجك يومياً لتحصل على تحليلات أدق',
                'priority': 'medium'
            })
        
        if most_common_mood in ['Stressed', 'Anxious', 'Sad']:
            recommendations.append({
                'type': 'warning',
                'message': f'😔 {most_common_mood} هو أكثر مشاعرك تكراراً. جرب تقنيات الاسترخاء',
                'priority': 'high'
            })
        elif most_common_mood in ['Excellent', 'Good']:
            recommendations.append({
                'type': 'praise',
                'message': f'🌟 رائع! {most_common_mood} هو المسيطر على مشاعرك',
                'priority': 'low'
            })
        
        if trend == 'improving':
            recommendations.append({
                'type': 'success',
                'message': '📈 مزاجك في تحسن مستمر! حافظ على عاداتك الإيجابية',
                'priority': 'medium'
            })
        elif trend == 'declining':
            recommendations.append({
                'type': 'warning',
                'message': '📉 مزاجك في تراجع. خذ قسطاً من الراحة وتحدث مع صديق',
                'priority': 'high'
            })
        
        return recommendations


# ==============================================================================
# 🥗 خدمة تحليلات التغذية - مع DELETE + CREATE
# ==============================================================================

class NutritionAnalyticsService:
    """خدمة تحليلات التغذية الذكية"""
    
    def __init__(self, user):
        self.user = user
        self.today = timezone.now().date()
    
    def generate_insights(self):
        """توليد تحليلات التغذية"""
        
        print(f"🔍 توليد تحليلات التغذية للمستخدم: {self.user.username}")
        print(f"📅 اليوم: {self.today}")
        print("="*40)
        print("⚙️ استخدام الكود الجديد مع DELETE + CREATE")
        
        # استيراد النماذج من main
        from main.models import Meal, FoodItem
        
        # جلب جميع الوجبات
        meals = Meal.objects.filter(user=self.user)
        total_meals = meals.count()
        print(f"🍽️ إجمالي الوجبات: {total_meals}")
        
        # حساب إجمالي القيم الغذائية
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        meal_distribution = {}
        
        for meal in meals:
            # توزيع أنواع الوجبات
            meal_type = meal.meal_type
            meal_distribution[meal_type] = meal_distribution.get(meal_type, 0) + 1
            
            # جلب مكونات الوجبة
            food_items = FoodItem.objects.filter(meal=meal)
            for item in food_items:
                total_calories += float(item.calories or 0)
                total_protein += float(item.protein_g or 0)
                total_carbs += float(item.carbs_g or 0)
                total_fat += float(item.fat_g or 0)
        
        print(f"🔥 إجمالي السعرات: {total_calories}")
        print(f"🥩 إجمالي البروتين: {total_protein}g")
        print(f"🍚 إجمالي الكربوهيدرات: {total_carbs}g")
        print(f"🫒 إجمالي الدهون: {total_fat}g")
        print(f"📊 توزيع الوجبات: {meal_distribution}")
        
        # حساب المتوسطات
        avg_calories = round(total_calories / total_meals, 1) if total_meals > 0 else 0
        avg_protein = round(total_protein / total_meals, 1) if total_meals > 0 else 0
        avg_carbs = round(total_carbs / total_meals, 1) if total_meals > 0 else 0
        avg_fat = round(total_fat / total_meals, 1) if total_meals > 0 else 0
        
        print(f"📊 متوسط السعرات: {avg_calories}")
        print(f"📊 متوسط البروتين: {avg_protein}g")
        
        # تحليل الاتجاه (مقارنة مع آخر 7 أيام)
        trend = self._analyze_trend(meals)
        
        # توليد توصيات
        recommendations = self._generate_recommendations(
            total_meals, avg_calories, avg_protein, avg_carbs, avg_fat, meal_distribution
        )
        
        # ✅ حذف التحليل القديم
        old_insights = NutritionInsight.objects.filter(user=self.user)
        old_count = old_insights.count()
        print(f"🗑️ عدد التحليلات القديمة: {old_count}")
        
        if old_count > 0:
            print(f"📝 التحليلات القديمة:")
            for insight in old_insights:
                print(f"   - ID={insight.id}, date={insight.date}, total_meals={insight.total_meals}")
            deleted = old_insights.delete()
            print(f"✅ تم حذف {deleted} تحليل قديم")
        
        # ✅ إنشاء تحليل جديد
        print("📝 إنشاء تحليل جديد...")
        insight = NutritionInsight.objects.create(
            user=self.user,
            date=self.today,
            total_meals=total_meals,
            total_calories=total_calories,
            total_protein=total_protein,
            total_carbs=total_carbs,
            total_fat=total_fat,
            avg_calories=avg_calories,
            avg_protein=avg_protein,
            avg_carbs=avg_carbs,
            avg_fat=avg_fat,
            meal_distribution=meal_distribution,
            recommendations=recommendations,
            trend=trend
        )
        
        print(f"✅ تم إنشاء تحليل التغذية الجديد (ID: {insight.id})")
        print("="*40)
        return insight
    
    def _analyze_trend(self, meals):
        """تحليل اتجاه التغذية"""
        if meals.count() < 3:
            return 'insufficient_data'
        
        week_ago = self.today - timedelta(days=7)
        recent_meals = meals.filter(meal_time__date__gte=week_ago)
        
        if recent_meals.count() < 3:
            return 'insufficient_data'
        
        # مقارنة بسيطة - يمكن تطويرها لاحقاً
        return 'stable'
    
    def _generate_recommendations(self, total_meals, avg_calories, avg_protein, avg_carbs, avg_fat, meal_distribution):
        """توليد توصيات غذائية ذكية"""
        recommendations = []
        
        if total_meals == 0:
            recommendations.append({
                'type': 'motivation',
                'message': '🥗 ابدأ بتسجيل وجباتك اليومية لتحليل نظامك الغذائي!',
                'priority': 'high'
            })
        elif total_meals < 5:
            recommendations.append({
                'type': 'info',
                'message': '📝 استمر في تسجيل وجباتك للحصول على تحليلات أدق',
                'priority': 'medium'
            })
        else:
            recommendations.append({
                'type': 'success',
                'message': f'✅ رائع! سجلت {total_meals} وجبة حتى الآن',
                'priority': 'low'
            })
        
        if avg_calories > 0:
            if avg_calories < 1500:
                recommendations.append({
                    'type': 'warning',
                    'message': f'⚠️ متوسط سعراتك منخفض ({avg_calories}). حاول زيادة السعرات بشكل صحي',
                    'priority': 'high'
                })
            elif avg_calories > 3000:
                recommendations.append({
                    'type': 'warning',
                    'message': f'⚠️ متوسط سعراتك مرتفع ({avg_calories}). راجع أحجام الوجبات',
                    'priority': 'high'
                })
            else:
                recommendations.append({
                    'type': 'success',
                    'message': f'✅ متوسط سعراتك {avg_calories} - مناسب!',
                    'priority': 'low'
                })
        
        if avg_protein < 50 and total_meals > 0:
            recommendations.append({
                'type': 'tip',
                'message': '💪 تناول المزيد من البروتين: دجاج، سمك، بيض، بقوليات',
                'priority': 'medium'
            })
        
        if 'Breakfast' not in meal_distribution:
            recommendations.append({
                'type': 'tip',
                'message': '🌅 لا تهمل وجبة الإفطار - أهم وجبة في اليوم',
                'priority': 'medium'
            })
        
        if 'Lunch' not in meal_distribution:
            recommendations.append({
                'type': 'tip',
                'message': '🍲 حاول تسجيل وجبة الغداء بانتظام',
                'priority': 'medium'
            })
        
        if 'Dinner' not in meal_distribution:
            recommendations.append({
                'type': 'tip',
                'message': '🌙 العشاء الخفيف يساعد على نوم أفضل',
                'priority': 'low'
            })
        
        return recommendations
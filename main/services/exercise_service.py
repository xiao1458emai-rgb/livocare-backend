# main/services/analytics/exercise_service.py
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, Min, Max, StdDev
from django.db.models.functions import ExtractDay, ExtractWeek, ExtractMonth
import joblib
import os
import json
from ..models import (
    HealthStatus, Sleep, MoodEntry, Meal, PhysicalActivity, 
    HabitLog, EnvironmentData, FoodItem, CustomUser
)

class AdvancedHealthAnalytics:
    """
    نظام تحليلات متقدم يستخدم التعلم الآلي لتحليل الصحة الشاملة
    Advanced analytics system using machine learning for comprehensive health analysis
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language  # 'ar' for Arabic, 'en' for English
        self.models_path = 'ml_models/'
        self._ensure_models_dir()
        
        # ✅ جلب معلومات المستخدم الشخصية
        self.user_profile = self._get_user_profile()
        self.user_age = self._calculate_age()
        self.user_gender = self._get_gender()
        self.user_height = self._get_height()
    
    def _get_user_profile(self):
        """جلب الملف الشخصي للمستخدم"""
        try:
            if hasattr(self.user, 'profile'):
                return self.user.profile
            return None
        except:
            return None
    
    def _calculate_age(self):
        """حساب العمر"""
        try:
            if self.user_profile and hasattr(self.user_profile, 'birth_date') and self.user_profile.birth_date:
                today = timezone.now().date()
                return today.year - self.user_profile.birth_date.year - (
                    (today.month, today.day) < (self.user_profile.birth_date.month, self.user_profile.birth_date.day)
                )
        except:
            pass
        return None
    
    def _get_gender(self):
        """جلب الجنس"""
        try:
            if self.user_profile and hasattr(self.user_profile, 'gender'):
                return self.user_profile.gender
        except:
            pass
        return 'unknown'
    
    def _get_height(self):
        """جلب الطول"""
        try:
            if self.user_profile and hasattr(self.user_profile, 'height_cm'):
                return self.user_profile.height_cm
        except:
            pass
        return None
    
    def _t(self, ar_text, en_text, **kwargs):
        """ترجمة النصوص حسب اللغة المحددة"""
        text = ar_text if self.language == 'ar' else en_text
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text
    
    def _ensure_models_dir(self):
        """التأكد من وجود مجلد النماذج"""
        if not os.path.exists(self.models_path):
            os.makedirs(self.models_path)
    
    def collect_all_health_data(self, days=90):
        """جمع كل البيانات الصحية للمستخدم - موسعة لـ 90 يوماً"""
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # 1. البيانات الحيوية
        health_data = list(HealthStatus.objects.filter(
            user=self.user, 
            recorded_at__range=[start_date, end_date]
        ).order_by('recorded_at'))
        
        # 2. بيانات النوم
        sleep_data = list(Sleep.objects.filter(
            user=self.user,
            sleep_start__range=[start_date, end_date]
        ).order_by('sleep_start'))
        
        # 3. بيانات المزاج
        mood_data = list(MoodEntry.objects.filter(
            user=self.user,
            entry_time__range=[start_date, end_date]
        ).order_by('entry_time'))
        
        # 4. بيانات التغذية
        meal_data = list(Meal.objects.filter(
            user=self.user,
            meal_time__range=[start_date, end_date]
        ).order_by('meal_time'))
        
        # 5. بيانات النشاط
        activity_data = list(PhysicalActivity.objects.filter(
            user=self.user,
            start_time__range=[start_date, end_date]
        ).order_by('start_time'))
        
        # 6. بيانات العادات
        habit_logs = list(HabitLog.objects.filter(
            habit__user=self.user,
            log_date__range=[start_date.date(), end_date.date()]
        ))
        
        # 7. بيانات الطقس
        weather_data = self._get_weather_data(start_date, end_date)
        
        return {
            'health': health_data,
            'sleep': sleep_data,
            'mood': mood_data,
            'nutrition': meal_data,
            'activity': activity_data,
            'habits': habit_logs,
            'weather': weather_data
        }
    
    def _get_weather_data(self, start_date, end_date):
        """جلب بيانات الطقس للفترة"""
        try:
            from ..models import EnvironmentData
            
            if hasattr(EnvironmentData, 'recorded_at'):
                field_name = 'recorded_at'
            elif hasattr(EnvironmentData, 'date'):
                field_name = 'date'
            else:
                return []
            
            filter_kwargs = {
                'user': self.user,
                f'{field_name}__range': [start_date, end_date]
            }
            
            return EnvironmentData.objects.filter(**filter_kwargs).order_by(field_name)
            
        except Exception as e:
            return []
    
    def prepare_features(self, raw_data):
        """تحويل البيانات الخام إلى مصفوفة features للتعلم الآلي"""
        
        features = []
        targets = {
            'weight': [],
            'mood': [],
            'sleep_quality': [],
            'calories': []
        }
        
        dates = pd.date_range(
            start=raw_data['health'][0].recorded_at.date() if raw_data['health'] else timezone.now().date() - timedelta(days=30),
            end=timezone.now().date(),
            freq='D'
        )
        
        df = pd.DataFrame(index=dates)
        
        df['day_of_week'] = df.index.dayofweek
        df['month'] = df.index.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['day_of_year'] = df.index.dayofyear
        
        daily_stats = {}
        
        for date in dates:
            date_str = date.strftime('%Y-%m-%d')
            daily_stats[date_str] = self._calculate_daily_stats(raw_data, date)
        
        for col in ['weight', 'sleep_hours', 'sleep_quality', 'mood_score', 
                   'calories', 'protein', 'carbs', 'fats', 'activity_minutes', 
                   'habits_completed', 'avg_temp', 'humidity', 'steps', 'heart_rate_avg']:
            df[col] = [daily_stats[d.strftime('%Y-%m-%d')].get(col, 0) for d in dates]
        
        # ميزات متقدمة
        df['weight_change'] = df['weight'].diff()
        df['weight_change_3d'] = df['weight'].diff(3)
        df['sleep_7d_avg'] = df['sleep_hours'].rolling(window=7, min_periods=1).mean()
        df['sleep_7d_std'] = df['sleep_hours'].rolling(window=7, min_periods=1).std()
        df['calories_7d_avg'] = df['calories'].rolling(window=7, min_periods=1).mean()
        df['calories_7d_std'] = df['calories'].rolling(window=7, min_periods=1).std()
        df['mood_3d_avg'] = df['mood_score'].rolling(window=3, min_periods=1).mean()
        df['mood_7d_avg'] = df['mood_score'].rolling(window=7, min_periods=1).mean()
        df['activity_7d_avg'] = df['activity_minutes'].rolling(window=7, min_periods=1).mean()
        df['protein_carbs_ratio'] = df['protein'] / (df['carbs'] + 1)
        df['sleep_mood_product'] = df['sleep_hours'] * df['mood_score']
        
        return df
    
    def _calculate_daily_stats(self, raw_data, date):
        """حساب الإحصائيات اليومية الموسعة"""
        stats = {}
        
        # الوزن
        weight_records = [h for h in raw_data['health'] 
                         if h.recorded_at.date() == date and h.weight_kg]
        if weight_records:
            stats['weight'] = weight_records[-1].weight_kg
        
        # ضغط الدم
        bp_records = [h for h in raw_data['health'] 
                     if h.recorded_at.date() == date and h.systolic_pressure and h.diastolic_pressure]
        if bp_records:
            stats['systolic_avg'] = np.mean([h.systolic_pressure for h in bp_records])
            stats['diastolic_avg'] = np.mean([h.diastolic_pressure for h in bp_records])
        
        # السكر
        glucose_records = [h for h in raw_data['health'] 
                          if h.recorded_at.date() == date and h.blood_glucose]
        if glucose_records:
            stats['glucose_avg'] = np.mean([h.blood_glucose for h in glucose_records])
        
        # معدل ضربات القلب
        hr_records = [h for h in raw_data['health'] 
                     if h.recorded_at.date() == date and h.heart_rate]
        if hr_records:
            stats['heart_rate_avg'] = np.mean([h.heart_rate for h in hr_records])
        
        # النوم
        sleep_records = [s for s in raw_data['sleep'] 
                        if s.sleep_start.date() == date and s.sleep_end]
        if sleep_records:
            total_sleep = 0
            total_quality = 0
            total_deep_sleep = 0
            for sleep in sleep_records:
                duration = (sleep.sleep_end - sleep.sleep_start).seconds / 3600
                total_sleep += duration
                if sleep.quality_rating:
                    total_quality += sleep.quality_rating
                if hasattr(sleep, 'deep_sleep_minutes') and sleep.deep_sleep_minutes:
                    total_deep_sleep += sleep.deep_sleep_minutes
            stats['sleep_hours'] = total_sleep
            stats['sleep_quality'] = total_quality / len(sleep_records) if sleep_records else 0
            stats['deep_sleep_minutes'] = total_deep_sleep
        
        # المزاج
        mood_records = [m for m in raw_data['mood'] if m.entry_time.date() == date]
        if mood_records:
            mood_scores = {
                'excellent': 5, 'good': 4, 'neutral': 3,
                'stressed': 2, 'anxious': 2, 'sad': 1, 'depressed': 0
            }
            stats['mood_score'] = mood_scores.get(mood_records[-1].mood, 3)
            stats['mood_note'] = mood_records[-1].notes if hasattr(mood_records[-1], 'notes') else None
        
        # التغذية
        meal_records = [m for m in raw_data['nutrition'] if m.meal_time.date() == date]
        if meal_records:
            stats['calories'] = sum(m.total_calories or 0 for m in meal_records)
            stats['protein'] = sum(m.total_protein or 0 for m in meal_records)
            stats['carbs'] = sum(m.total_carbs or 0 for m in meal_records)
            stats['fats'] = sum(m.total_fats or 0 for m in meal_records)
            stats['meals_count'] = len(meal_records)
        
        # النشاط
        activity_records = [a for a in raw_data['activity'] if a.start_time.date() == date]
        if activity_records:
            stats['activity_minutes'] = sum(a.duration_minutes or 0 for a in activity_records)
            stats['calories_burned'] = sum(a.calories_burned or 0 for a in activity_records)
            stats['steps'] = sum(getattr(a, 'steps', 0) or 0 for a in activity_records)
            stats['activities_count'] = len(activity_records)
        
        # العادات
        habit_records = [h for h in raw_data['habits'] if h.log_date == date]
        stats['habits_completed'] = len(habit_records)
        
        # الطقس
        weather_records = [w for w in raw_data['weather'] if w.recorded_at.date() == date]
        if weather_records:
            stats['avg_temp'] = np.mean([w.temperature for w in weather_records])
            stats['humidity'] = np.mean([w.humidity for w in weather_records])
        
        return stats
    
    # ==================== التحليلات الشاملة الجديدة ====================
    
    def get_comprehensive_analytics(self):
        """
        تحليلات شاملة وكاملة لحالة المستخدم
        Comprehensive analytics covering all health aspects
        """
        
        raw_data = self.collect_all_health_data(days=90)
        df = self.prepare_features(raw_data)
        
        # الحصول على آخر القياسات
        latest_health = raw_data['health'][-1] if raw_data['health'] else None
        
        # حساب مؤشر كتلة الجسم
        bmi = None
        bmi_category = None
        if latest_health and latest_health.weight_kg and self.user_height:
            height_m = self.user_height / 100
            bmi = round(latest_health.weight_kg / (height_m ** 2), 1)
            bmi_category = self._get_bmi_category(bmi)
        
        return {
            # 1. الملف الشخصي
            'profile': self._analyze_profile(),
            
            # 2. العلامات الحيوية
            'vital_signs': self._analyze_vital_signs(latest_health, raw_data),
            
            # 3. تحليل الوزن و BMI
            'weight_bmi_analysis': self._analyze_weight_bmi(latest_health, raw_data, df, bmi, bmi_category),
            
            # 4. تحليل النوم
            'sleep_analysis': self._analyze_sleep(raw_data, df),
            
            # 5. تحليل المزاج
            'mood_analysis': self._analyze_mood(raw_data, df),
            
            # 6. تحليل التغذية
            'nutrition_analysis': self._analyze_nutrition(raw_data, df),
            
            # 7. تحليل النشاط البدني
            'activity_analysis': self._analyze_activity(raw_data, df),
            
            # 8. تحليل العادات
            'habits_analysis': self._analyze_habits(raw_data, df),
            
            # 9. تحليل الارتباطات
            'correlations': self._analyze_correlations(df),
            
            # 10. الأنماط المكتشفة
            'patterns': self._analyze_patterns_clustering(df),
            
            # 11. الاتجاهات والتوقعات
            'trends_predictions': self._analyze_trends_predictions(raw_data, df),
            
            # 12. المخاطر الصحية
            'health_risks': self._analyze_health_risks(latest_health, raw_data, df, bmi_category),
            
            # 13. نقاط القوة والضعف
            'strengths_weaknesses': self._analyze_strengths_weaknesses(raw_data, df),
            
            # 14. التوصيات الذكية
            'recommendations': self._generate_comprehensive_recommendations(raw_data, df, bmi_category),
            
            # 15. النتيجة الصحية الشاملة
            'health_score': self._calculate_health_score(raw_data, df),
            
            # 16. ملخص تنفيذي
            'executive_summary': self._generate_executive_summary(raw_data, df, bmi_category),
        }
    
    def _analyze_profile(self):
        """تحليل الملف الشخصي للمستخدم"""
        return {
            'age': self.user_age,
            'gender': self.user_gender,
            'height_cm': self.user_height,
            'has_complete_profile': bool(self.user_age and self.user_gender and self.user_height),
            'missing_fields': self._get_missing_profile_fields(),
            'health_goals': self._get_user_goals(),
        }
    
    def _get_missing_profile_fields(self):
        """تحديد الحقول الناقصة في الملف الشخصي"""
        missing = []
        if not self.user_age:
            missing.append('age')
        if not self.user_gender or self.user_gender == 'unknown':
            missing.append('gender')
        if not self.user_height:
            missing.append('height')
        return missing
    
    def _get_user_goals(self):
        """جلب أهداف المستخدم الصحية"""
        try:
            from ..models import HealthGoal
            goals = HealthGoal.objects.filter(user=self.user, is_active=True)
            return [
                {
                    'title': goal.title,
                    'target_value': goal.target_value,
                    'current_value': goal.current_value,
                    'deadline': goal.deadline,
                    'progress': (goal.current_value / goal.target_value * 100) if goal.target_value else 0
                }
                for goal in goals
            ]
        except:
            return []
    
    def _analyze_vital_signs(self, latest_health, raw_data):
        """تحليل العلامات الحيوية"""
        
        if not latest_health:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات كافية', 'Insufficient data')}
        
        # تحليل ضغط الدم
        bp_status = 'normal'
        bp_message = self._t('طبيعي', 'Normal')
        if latest_health.systolic_pressure and latest_health.diastolic_pressure:
            if latest_health.systolic_pressure > 140 or latest_health.diastolic_pressure > 90:
                bp_status = 'high'
                bp_message = self._t('مرتفع - استشر طبيبك', 'High - consult your doctor')
            elif latest_health.systolic_pressure < 90 or latest_health.diastolic_pressure < 60:
                bp_status = 'low'
                bp_message = self._t('منخفض - تأكد من شرب السوائل', 'Low - ensure adequate hydration')
        
        # تحليل السكر
        glucose_status = 'normal'
        glucose_message = self._t('طبيعي', 'Normal')
        if latest_health.blood_glucose:
            if latest_health.blood_glucose > 140:
                glucose_status = 'high'
                glucose_message = self._t('مرتفع - تجنب السكريات', 'High - avoid sugars')
            elif latest_health.blood_glucose < 70:
                glucose_status = 'low'
                glucose_message = self._t('منخفض - تناول سكراً سريعاً', 'Low - eat fast-acting sugar')
        
        # تحليل النبض
        hr_status = 'normal'
        hr_message = self._t('طبيعي', 'Normal')
        if latest_health.heart_rate:
            if latest_health.heart_rate > 100:
                hr_status = 'high'
                hr_message = self._t('مرتفع - هل أنت متوتر؟', 'High - are you stressed?')
            elif latest_health.heart_rate < 60:
                hr_status = 'low'
                hr_message = self._t('منخفض - إذا كنت رياضياً فهذا طبيعي', 'Low - normal if you are athletic')
        
        # تحليل الأكسجين
        spo2_status = 'normal'
        spo2_message = self._t('طبيعي', 'Normal')
        if latest_health.spo2:
            if latest_health.spo2 < 95:
                spo2_status = 'low'
                spo2_message = self._t('منخفض - تمارين التنفس قد تساعد', 'Low - breathing exercises may help')
        
        return {
            'weight': latest_health.weight_kg,
            'blood_pressure': {
                'systolic': latest_health.systolic_pressure,
                'diastolic': latest_health.diastolic_pressure,
                'status': bp_status,
                'message': bp_message
            },
            'blood_glucose': {
                'value': latest_health.blood_glucose,
                'status': glucose_status,
                'message': glucose_message
            },
            'heart_rate': {
                'value': latest_health.heart_rate,
                'status': hr_status,
                'message': hr_message
            },
            'oxygen_level': {
                'value': latest_health.spo2,
                'status': spo2_status,
                'message': spo2_message
            },
            'recorded_at': latest_health.recorded_at,
        }
    
    def _analyze_weight_bmi(self, latest_health, raw_data, df, bmi, bmi_category):
        """تحليل الوزن و BMI المتقدم"""
        
        if not latest_health or not latest_health.weight_kg:
            return {'status': 'no_data'}
        
        current_weight = latest_health.weight_kg
        
        # حساب الوزن المثالي
        ideal_weight_min = None
        ideal_weight_max = None
        if self.user_height:
            ideal_weight_min = round(18.5 * ((self.user_height / 100) ** 2), 1)
            ideal_weight_max = round(24.9 * ((self.user_height / 100) ** 2), 1)
        
        # تحليل اتجاه الوزن
        weight_trend = 'stable'
        weight_change = 0
        if len(raw_data['health']) >= 2:
            oldest_weight = raw_data['health'][0].weight_kg
            weight_change = current_weight - oldest_weight
            if weight_change > 2:
                weight_trend = 'increasing'
            elif weight_change < -2:
                weight_trend = 'decreasing'
        
        # الوزن المستهدف
        target_weight = None
        if ideal_weight_min and ideal_weight_max:
            if current_weight > ideal_weight_max:
                target_weight = ideal_weight_max
            elif current_weight < ideal_weight_min:
                target_weight = ideal_weight_min
        
        return {
            'current_weight': current_weight,
            'bmi': bmi,
            'bmi_category': bmi_category,
            'ideal_weight_range': {'min': ideal_weight_min, 'max': ideal_weight_max},
            'weight_to_lose': round(current_weight - ideal_weight_max, 1) if ideal_weight_max and current_weight > ideal_weight_max else 0,
            'weight_to_gain': round(ideal_weight_min - current_weight, 1) if ideal_weight_min and current_weight < ideal_weight_min else 0,
            'weight_trend': weight_trend,
            'weight_change_90d': round(weight_change, 1),
            'target_weight': target_weight,
            'weight_history': [{'date': h.recorded_at, 'weight': h.weight_kg} for h in raw_data['health'][-30:]],
        }
    
    def _analyze_sleep(self, raw_data, df):
        """تحليل النوم المتقدم"""
        
        sleep_records = raw_data['sleep']
        if not sleep_records:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات نوم كافية', 'Insufficient sleep data')}
        
        # حساب المتوسطات
        avg_sleep_hours = df['sleep_hours'].mean()
        avg_sleep_quality = df['sleep_quality'].mean()
        avg_deep_sleep = df['deep_sleep_minutes'].mean() if 'deep_sleep_minutes' in df.columns else 0
        
        # أفضل وأسوأ أيام النوم
        best_sleep_day = df.loc[df['sleep_hours'].idxmax()] if len(df) > 0 else None
        worst_sleep_day = df.loc[df['sleep_hours'].idxmin()] if len(df) > 0 else None
        
        # توزيع جودة النوم
        quality_distribution = {
            'excellent': len(df[df['sleep_quality'] >= 4]),
            'good': len(df[(df['sleep_quality'] >= 3) & (df['sleep_quality'] < 4)]),
            'fair': len(df[(df['sleep_quality'] >= 2) & (df['sleep_quality'] < 3)]),
            'poor': len(df[df['sleep_quality'] < 2]),
        }
        
        # تقييم النوم
        sleep_score = 0
        if 7 <= avg_sleep_hours <= 9:
            sleep_score += 40
        elif 6 <= avg_sleep_hours < 7 or 9 < avg_sleep_hours <= 10:
            sleep_score += 20
        else:
            sleep_score += 0
        
        if avg_sleep_quality >= 4:
            sleep_score += 40
        elif avg_sleep_quality >= 3:
            sleep_score += 20
        
        if avg_deep_sleep >= 90:
            sleep_score += 20
        elif avg_deep_sleep >= 60:
            sleep_score += 10
        
        return {
            'average_sleep_hours': round(avg_sleep_hours, 1),
            'average_sleep_quality': round(avg_sleep_quality, 1),
            'average_deep_sleep_minutes': round(avg_deep_sleep),
            'total_sleep_records': len(sleep_records),
            'best_sleep_day': best_sleep_day,
            'worst_sleep_day': worst_sleep_day,
            'quality_distribution': quality_distribution,
            'sleep_score': min(100, sleep_score),
            'recommendation': self._get_sleep_recommendation(avg_sleep_hours, avg_sleep_quality),
        }
    
    def _get_sleep_recommendation(self, avg_hours, avg_quality):
        """توصيات تحسين النوم"""
        if avg_hours < 6:
            return self._t(
                'تنام قليلاً جداً. حاول النوم مبكراً بـ 30 دقيقة وتجنب الكافيين بعد العصر',
                'You sleep too little. Try sleeping 30 minutes earlier and avoid caffeine after 4 PM'
            )
        elif avg_hours > 9:
            return self._t(
                'تنام كثيراً. حاول تقليل ساعات النوم تدريجياً',
                'You sleep too much. Try gradually reducing your sleep hours'
            )
        elif avg_quality < 3:
            return self._t(
                'جودة نومك منخفضة. جرب تهيئة غرفة نوم مريحة ومظلمة',
                'Your sleep quality is low. Try creating a comfortable, dark bedroom'
            )
        else:
            return self._t('نومك جيد! حافظ على روتينك', 'Your sleep is good! Maintain your routine')
    
    def _analyze_mood(self, raw_data, df):
        """تحليل المزاج المتقدم"""
        
        mood_records = raw_data['mood']
        if not mood_records:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات مزاج كافية', 'Insufficient mood data')}
        
        avg_mood = df['mood_score'].mean()
        
        # توزيع المزاج
        mood_distribution = {}
        mood_scores = {'excellent': 5, 'good': 4, 'neutral': 3, 'stressed': 2, 'anxious': 2, 'sad': 1, 'depressed': 0}
        for mood_name, score in mood_scores.items():
            count = len([m for m in mood_records if m.mood == mood_name])
            if count > 0:
                mood_distribution[mood_name] = count
        
        # اتجاه المزاج
        recent_mood = df['mood_score'].tail(7).mean() if len(df) >= 7 else avg_mood
        previous_mood = df['mood_score'].head(7).mean() if len(df) >= 14 else avg_mood
        mood_trend = 'improving' if recent_mood > previous_mood else 'declining' if recent_mood < previous_mood else 'stable'
        
        return {
            'average_mood_score': round(avg_mood, 1),
            'mood_distribution': mood_distribution,
            'mood_trend': mood_trend,
            'total_mood_records': len(mood_records),
            'last_mood': mood_records[-1].mood if mood_records else None,
            'recommendation': self._get_mood_recommendation(avg_mood, mood_trend),
        }
    
    def _get_mood_recommendation(self, avg_mood, trend):
        """توصيات تحسين المزاج"""
        if avg_mood < 2.5:
            return self._t(
                'مزاجك منخفض. جرب ممارسة الرياضة، التأمل، أو التحدث مع شخص تثق به',
                'Your mood is low. Try exercising, meditating, or talking to someone you trust'
            )
        elif trend == 'declining':
            return self._t(
                'مزاجك في تراجع. لاحظ ما يسبب لك التوتر وحاول معالجته',
                'Your mood is declining. Notice what causes you stress and try to address it'
            )
        else:
            return self._t('مزاجك جيد! استمر في العادات الإيجابية', 'Your mood is good! Continue positive habits')
    
    def _analyze_nutrition(self, raw_data, df):
        """تحليل التغذية المتقدم"""
        
        meal_records = raw_data['nutrition']
        if not meal_records:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات تغذية كافية', 'Insufficient nutrition data')}
        
        avg_calories = df['calories'].mean()
        avg_protein = df['protein'].mean()
        avg_carbs = df['carbs'].mean()
        avg_fats = df['fats'].mean()
        avg_meals_per_day = df['meals_count'].mean() if 'meals_count' in df.columns else 0
        
        # توزيع المغذيات
        total_macros = avg_protein + avg_carbs + avg_fats
        if total_macros > 0:
            protein_percent = (avg_protein * 4 / avg_calories * 100) if avg_calories > 0 else 0
            carbs_percent = (avg_carbs * 4 / avg_calories * 100) if avg_calories > 0 else 0
            fats_percent = (avg_fats * 9 / avg_calories * 100) if avg_calories > 0 else 0
        else:
            protein_percent = carbs_percent = fats_percent = 0
        
        # تقييم التغذية
        nutrition_score = 0
        if 1800 <= avg_calories <= 2500:
            nutrition_score += 30
        elif 1500 <= avg_calories < 1800 or 2500 < avg_calories <= 3000:
            nutrition_score += 15
        
        if 15 <= protein_percent <= 25:
            nutrition_score += 35
        elif 10 <= protein_percent < 15 or 25 < protein_percent <= 35:
            nutrition_score += 20
        
        if 45 <= carbs_percent <= 65:
            nutrition_score += 35
        elif 35 <= carbs_percent < 45 or 65 < carbs_percent <= 75:
            nutrition_score += 20
        
        return {
            'average_daily_calories': round(avg_calories),
            'average_protein_g': round(avg_protein, 1),
            'average_carbs_g': round(avg_carbs, 1),
            'average_fats_g': round(avg_fats, 1),
            'average_meals_per_day': round(avg_meals_per_day, 1),
            'macros_percentage': {
                'protein': round(protein_percent),
                'carbs': round(carbs_percent),
                'fats': round(fats_percent)
            },
            'nutrition_score': min(100, nutrition_score),
            'recommendation': self._get_nutrition_recommendation(avg_calories, protein_percent),
        }
    
    def _get_nutrition_recommendation(self, avg_calories, protein_percent):
        """توصيات تحسين التغذية"""
        recommendations = []
        if avg_calories > 2500:
            recommendations.append(self._t('قلل السعرات الحرارية وركز على الخضروات', 'Reduce calories and focus on vegetables'))
        elif avg_calories < 1500:
            recommendations.append(self._t('زود السعرات الحرارية وتناول وجبات متوازنة', 'Increase calories and eat balanced meals'))
        
        if protein_percent < 15:
            recommendations.append(self._t('زود البروتين (لحوم، بيض، بقوليات)', 'Increase protein (meat, eggs, legumes)'))
        elif protein_percent > 30:
            recommendations.append(self._t('قلل البروتين قليلاً وزد الخضروات', 'Reduce protein slightly and increase vegetables'))
        
        return ' '.join(recommendations) if recommendations else self._t('تغذيتك متوازنة! استمر', 'Your nutrition is balanced! Continue')
    
    def _analyze_activity(self, raw_data, df):
        """تحليل النشاط البدني المتقدم"""
        
        activity_records = raw_data['activity']
        if not activity_records:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات نشاط كافية', 'Insufficient activity data')}
        
        avg_activity_minutes = df['activity_minutes'].mean()
        total_activity_minutes = df['activity_minutes'].sum()
        total_calories_burned = df['calories_burned'].sum() if 'calories_burned' in df.columns else 0
        
        # تنوع الأنشطة
        activity_types = {}
        for act in activity_records:
            activity_types[act.activity_type] = activity_types.get(act.activity_type, 0) + 1
        
        # تقييم النشاط
        activity_score = 0
        if avg_activity_minutes >= 30:
            activity_score += 50
        elif avg_activity_minutes >= 15:
            activity_score += 25
        
        if len(activity_types) >= 3:
            activity_score += 30
        elif len(activity_types) >= 2:
            activity_score += 15
        
        if total_calories_burned > 5000:
            activity_score += 20
        elif total_calories_burned > 2000:
            activity_score += 10
        
        return {
            'average_daily_activity_minutes': round(avg_activity_minutes, 1),
            'total_activity_minutes_90d': round(total_activity_minutes),
            'total_calories_burned_90d': round(total_calories_burned),
            'activity_types': activity_types,
            'total_activities': len(activity_records),
            'activity_score': min(100, activity_score),
            'recommendation': self._get_activity_recommendation(avg_activity_minutes, len(activity_types)),
        }
    
    def _get_activity_recommendation(self, avg_minutes, num_types):
        """توصيات تحسين النشاط"""
        if avg_minutes < 15:
            return self._t(
                'نشاطك قليل جداً. ابدأ بالمشي 10 دقائق يومياً وزد تدريجياً',
                'Your activity is very low. Start with 10 minutes of walking daily and gradually increase'
            )
        elif avg_minutes < 30:
            return self._t(
                'نشاطك جيد لكن يمكن تحسينه. حاول الوصول إلى 30 دقيقة يومياً',
                'Your activity is good but can be improved. Try to reach 30 minutes daily'
            )
        elif num_types < 2:
            return self._t(
                'نشاطك ممتاز! جرب تنويع الأنشطة لتمرين عضلات مختلفة',
                'Your activity is excellent! Try varying activities to exercise different muscles'
            )
        else:
            return self._t('نشاطك ممتاز! استمر في هذا المستوى العالي', 'Your activity is excellent! Maintain this high level')
    
    def _analyze_habits(self, raw_data, df):
        """تحليل العادات"""
        
        habit_logs = raw_data['habits']
        if not habit_logs:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات عادات كافية', 'Insufficient habit data')}
        
        avg_habits_per_day = df['habits_completed'].mean()
        total_habits_completed = df['habits_completed'].sum()
        consistency_rate = (len([h for h in habit_logs if h.is_completed]) / len(habit_logs) * 100) if habit_logs else 0
        
        return {
            'average_habits_per_day': round(avg_habits_per_day, 1),
            'total_habits_completed_90d': round(total_habits_completed),
            'consistency_rate': round(consistency_rate),
            'total_habit_logs': len(habit_logs),
            'recommendation': self._get_habits_recommendation(avg_habits_per_day, consistency_rate),
        }
    
    def _get_habits_recommendation(self, avg_habits, consistency):
        """توصيات تحسين العادات"""
        if avg_habits < 2:
            return self._t('حاول إضافة عادة صحية واحدة صغيرة كل أسبوع', 'Try adding one small healthy habit each week')
        elif consistency < 70:
            return self._t('حاول استخدام تذكيرات يومية لتحسين الالتزام بالعادات', 'Try using daily reminders to improve habit adherence')
        else:
            return self._t('رائع! أنت ملتزم بعاداتك الصحية. استمر', 'Great! You are committed to your healthy habits. Continue')
    
    def _analyze_correlations(self, df):
        """تحليل الارتباطات بين المتغيرات المختلفة"""
        
        if len(df) < 14:
            return {'status': 'insufficient_data'}
        
        correlations = {}
        
        # النوم والمزاج
        sleep_mood_corr = df['sleep_hours'].corr(df['mood_score']) if 'sleep_hours' in df and 'mood_score' in df else 0
        correlations['sleep_mood'] = round(sleep_mood_corr, 2)
        
        # النشاط والمزاج
        activity_mood_corr = df['activity_minutes'].corr(df['mood_score']) if 'activity_minutes' in df and 'mood_score' in df else 0
        correlations['activity_mood'] = round(activity_mood_corr, 2)
        
        # السعرات والوزن
        calories_weight_corr = df['calories'].corr(df['weight_change']) if 'calories' in df and 'weight_change' in df else 0
        correlations['calories_weight'] = round(calories_weight_corr, 2)
        
        # النوم والنشاط
        sleep_activity_corr = df['sleep_hours'].corr(df['activity_minutes']) if 'sleep_hours' in df and 'activity_minutes' in df else 0
        correlations['sleep_activity'] = round(sleep_activity_corr, 2)
        
        # تفسير الارتباطات
        interpretations = []
        if sleep_mood_corr > 0.5:
            interpretations.append(self._t('نومك يؤثر إيجاباً على مزاجك', 'Your sleep positively affects your mood'))
        elif sleep_mood_corr < -0.3:
            interpretations.append(self._t('يبدو أن هناك علاقة عكسية بين نومك ومزاجك', 'There seems to be an inverse relationship between your sleep and mood'))
        
        if activity_mood_corr > 0.4:
            interpretations.append(self._t('النشاط البدني يحسن مزاجك بشكل ملحوظ', 'Physical activity significantly improves your mood'))
        
        return {
            'values': correlations,
            'interpretations': interpretations,
        }
    
    def _analyze_patterns_clustering(self, df):
        """تحليل الأنماط باستخدام clustering"""
        
        if len(df) < 14:
            return []
        
        pattern_features = ['sleep_hours', 'mood_score', 'calories', 'activity_minutes']
        available_features = [col for col in pattern_features if col in df.columns]
        
        if len(available_features) < 3:
            return []
        
        X = df[available_features].fillna(0)
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        n_clusters = min(3, len(X))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(X_scaled)
        
        patterns = []
        for i in range(kmeans.n_clusters):
            cluster_days = df.iloc[clusters == i]
            if len(cluster_days) > 0:
                pattern = {
                    'type': self._t(f'نمط {i+1}', f'Pattern {i+1}'),
                    'description': self._describe_pattern_detailed(cluster_days),
                    'frequency': len(cluster_days),
                    'percentage': round(len(cluster_days) / len(df) * 100),
                    'average_sleep': round(cluster_days['sleep_hours'].mean(), 1),
                    'average_mood': round(cluster_days['mood_score'].mean(), 1),
                    'average_calories': round(cluster_days['calories'].mean()),
                    'average_activity': round(cluster_days['activity_minutes'].mean(), 1),
                }
                patterns.append(pattern)
        
        return patterns
    
    def _describe_pattern_detailed(self, cluster_days):
        """وصف مفصل للنمط المكتشف"""
        avg_sleep = cluster_days['sleep_hours'].mean()
        avg_mood = cluster_days['mood_score'].mean()
        
        sleep_desc = self._t(
            "نوم قليل" if avg_sleep < 6 else "نوم كثير" if avg_sleep > 8 else "نوم مثالي",
            "Low sleep" if avg_sleep < 6 else "High sleep" if avg_sleep > 8 else "Ideal sleep"
        )
        
        mood_desc = self._t(
            "مزاج ممتاز" if avg_mood > 4 else "مزاج جيد" if avg_mood > 3 else "مزاج منخفض",
            "Excellent mood" if avg_mood > 4 else "Good mood" if avg_mood > 3 else "Low mood"
        )
        
        return self._t(f"{sleep_desc} مع {mood_desc}", f"{sleep_desc} with {mood_desc}")
    
    def _analyze_trends_predictions(self, raw_data, df):
        """تحليل الاتجاهات والتوقعات المستقبلية"""
        
        predictions = self.predict_future_weight(days=7) if len(raw_data['health']) > 14 else None
        
        return {
            'weight_trend_7d': list(df['weight'].tail(7)) if 'weight' in df else [],
            'weight_predictions_7d': predictions,
            'sleep_trend': self._t('تحسن', 'Improving') if len(df) >= 14 and df['sleep_hours'].tail(7).mean() > df['sleep_hours'].head(7).mean() else self._t('تراجع', 'Declining'),
            'mood_trend': self._t('تحسن', 'Improving') if len(df) >= 14 and df['mood_score'].tail(7).mean() > df['mood_score'].head(7).mean() else self._t('تراجع', 'Declining'),
            'activity_trend': self._t('تحسن', 'Improving') if len(df) >= 14 and df['activity_minutes'].tail(7).mean() > df['activity_minutes'].head(7).mean() else self._t('تراجع', 'Declining'),
        }
    
    def _analyze_health_risks(self, latest_health, raw_data, df, bmi_category):
        """تحليل المخاطر الصحية"""
        
        risks = []
        
        # مخاطر BMI
        if bmi_category in ['سمنة درجة ثانية', 'سمنة مفرطة', 'Obesity Class II', 'Extreme Obesity']:
            risks.append({
                'type': 'obesity',
                'severity': 'high',
                'condition': self._t('السمنة', 'Obesity'),
                'message': self._t('وزنك يشكل خطراً على صحتك، ننصح باستشارة طبيب', 'Your weight poses a health risk, we recommend consulting a doctor'),
            })
        elif bmi_category in ['سمنة درجة أولى', 'Obesity Class I']:
            risks.append({
                'type': 'overweight',
                'severity': 'moderate',
                'condition': self._t('زيادة الوزن', 'Overweight'),
                'message': self._t('وزنك أعلى من المعدل الطبيعي، ننصح ببرنامج غذائي', 'Your weight is above normal, we recommend a dietary program'),
            })
        elif bmi_category == 'نقص الوزن' or bmi_category == 'Underweight':
            risks.append({
                'type': 'underweight',
                'severity': 'moderate',
                'condition': self._t('نقص الوزن', 'Underweight'),
                'message': self._t('وزنك أقل من المعدل الطبيعي، قد يؤثر على مناعتك', 'Your weight is below normal, may affect your immunity'),
            })
        
        # مخاطر ضغط الدم
        if latest_health and latest_health.systolic_pressure and latest_health.systolic_pressure > 140:
            risks.append({
                'type': 'hypertension',
                'severity': 'high',
                'condition': self._t('ارتفاع ضغط الدم', 'High Blood Pressure'),
                'message': self._t('ضغط دمك مرتفع - يزيد خطر أمراض القلب', 'Your blood pressure is high - increases heart disease risk'),
            })
        
        # مخاطر السكر
        if latest_health and latest_health.blood_glucose and latest_health.blood_glucose > 140:
            risks.append({
                'type': 'hyperglycemia',
                'severity': 'high',
                'condition': self._t('ارتفاع السكر', 'High Blood Sugar'),
                'message': self._t('سكر دمك مرتفع - قد يشير إلى مقدمات السكري', 'Your blood sugar is high - may indicate prediabetes'),
            })
        
        # مخاطر قلة النوم
        avg_sleep = df['sleep_hours'].mean() if 'sleep_hours' in df else 0
        if avg_sleep < 6:
            risks.append({
                'type': 'sleep_deprivation',
                'severity': 'moderate',
                'condition': self._t('قلة النوم المزمنة', 'Chronic Sleep Deprivation'),
                'message': self._t('قلة النوم تؤثر على الصحة النفسية والجسدية', 'Lack of sleep affects mental and physical health'),
            })
        
        # مخاطر قلة النشاط
        avg_activity = df['activity_minutes'].mean() if 'activity_minutes' in df else 0
        if avg_activity < 15:
            risks.append({
                'type': 'sedentary',
                'severity': 'moderate',
                'condition': self._t('نمط حياة خامل', 'Sedentary Lifestyle'),
                'message': self._t('قلة الحركة تزيد خطر السمنة وأمراض القلب', 'Lack of movement increases risk of obesity and heart disease'),
            })
        
        return risks
    
    def _analyze_strengths_weaknesses(self, raw_data, df):
        """تحليل نقاط القوة والضعف"""
        
        strengths = []
        weaknesses = []
        
        # نقاط القوة
        avg_sleep = df['sleep_hours'].mean() if 'sleep_hours' in df else 0
        if 7 <= avg_sleep <= 9:
            strengths.append(self._t('نوم مثالي', 'Ideal sleep duration'))
        
        avg_mood = df['mood_score'].mean() if 'mood_score' in df else 0
        if avg_mood >= 3.5:
            strengths.append(self._t('مزاج مستقر وإيجابي', 'Stable and positive mood'))
        
        avg_activity = df['activity_minutes'].mean() if 'activity_minutes' in df else 0
        if avg_activity >= 30:
            strengths.append(self._t('نشاط بدني ممتاز', 'Excellent physical activity'))
        
        avg_habits = df['habits_completed'].mean() if 'habits_completed' in df else 0
        if avg_habits >= 2:
            strengths.append(self._t('التزام جيد بالعادات الصحية', 'Good commitment to healthy habits'))
        
        avg_meals = df['meals_count'].mean() if 'meals_count' in df else 0
        if avg_meals >= 3:
            strengths.append(self._t('انتظام في الوجبات', 'Regular meals'))
        
        # نقاط الضعف
        if avg_sleep < 6:
            weaknesses.append(self._t('قلة النوم المزمنة', 'Chronic sleep deprivation'))
        elif avg_sleep > 9:
            weaknesses.append(self._t('النوم الزائد', 'Excessive sleep'))
        
        if avg_mood < 2.5:
            weaknesses.append(self._t('تقلبات مزاجية متكررة', 'Frequent mood swings'))
        
        if avg_activity < 15:
            weaknesses.append(self._t('نشاط بدني قليل جداً', 'Very low physical activity'))
        elif avg_activity < 30:
            weaknesses.append(self._t('نشاط بدني أقل من الموصى به', 'Physical activity below recommendation'))
        
        if avg_habits < 1:
            weaknesses.append(self._t('عدم الالتزام بالعادات الصحية', 'No commitment to healthy habits'))
        
        return {
            'strengths': strengths,
            'weaknesses': weaknesses,
        }
    
    def _calculate_health_score(self, raw_data, df):
        """حساب النتيجة الصحية الشاملة من 0-100"""
        
        scores = []
        
        # 1. مكون النوم (وزن 20%)
        if 'sleep_hours' in df and len(df) > 0:
            avg_sleep = df['sleep_hours'].mean()
            if 7 <= avg_sleep <= 9:
                sleep_score = 20
            elif 6 <= avg_sleep < 7 or 9 < avg_sleep <= 10:
                sleep_score = 15
            elif avg_sleep < 5 or avg_sleep > 11:
                sleep_score = 5
            else:
                sleep_score = 10
            scores.append(('sleep', sleep_score))
        
        # 2. مكون المزاج (وزن 20%)
        if 'mood_score' in df and len(df) > 0:
            avg_mood = df['mood_score'].mean()
            mood_score = int(avg_mood * 4)  # 5*4 = 20
            scores.append(('mood', mood_score))
        
        # 3. مكون التغذية (وزن 20%)
        if 'calories' in df and len(df) > 0:
            avg_calories = df['calories'].mean()
            if 1800 <= avg_calories <= 2500:
                nutrition_score = 15
            elif 1500 <= avg_calories < 1800 or 2500 < avg_calories <= 3000:
                nutrition_score = 10
            else:
                nutrition_score = 5
            
            # إضافة للمغذيات
            if 'protein' in df and df['protein'].mean() > 50:
                nutrition_score += 5
            scores.append(('nutrition', nutrition_score))
        
        # 4. مكون النشاط (وزن 20%)
        if 'activity_minutes' in df and len(df) > 0:
            avg_activity = df['activity_minutes'].mean()
            if avg_activity >= 30:
                activity_score = 20
            elif avg_activity >= 20:
                activity_score = 15
            elif avg_activity >= 10:
                activity_score = 10
            else:
                activity_score = 5
            scores.append(('activity', activity_score))
        
        # 5. مكون العادات (وزن 20%)
        if 'habits_completed' in df and len(df) > 0:
            avg_habits = df['habits_completed'].mean()
            if avg_habits >= 3:
                habits_score = 20
            elif avg_habits >= 2:
                habits_score = 15
            elif avg_habits >= 1:
                habits_score = 10
            else:
                habits_score = 5
            scores.append(('habits', habits_score))
        
        # حساب المجموع
        total_score = sum(score for _, score in scores)
        
        # تحديد التصنيف
        if total_score >= 80:
            category = 'excellent'
            category_text = self._t('ممتازة', 'Excellent')
        elif total_score >= 65:
            category = 'good'
            category_text = self._t('جيدة', 'Good')
        elif total_score >= 50:
            category = 'fair'
            category_text = self._t('متوسطة', 'Fair')
        elif total_score >= 35:
            category = 'poor'
            category_text = self._t('سيئة', 'Poor')
        else:
            category = 'critical'
            category_text = self._t('حرجة', 'Critical')
        
        return {
            'total_score': total_score,
            'category': category,
            'category_text': category_text,
            'components': dict(scores),
        }
    
    def _generate_comprehensive_recommendations(self, raw_data, df, bmi_category):
        """توليد توصيات شاملة مخصصة"""
        
        recommendations = []
        
        # توصيات الوزن و BMI
        if bmi_category:
            if 'سمنة' in bmi_category or 'Obesity' in bmi_category:
                recommendations.append({
                    'category': 'weight',
                    'priority': 'high',
                    'icon': '⚖️',
                    'title': self._t('برنامج إنقاص الوزن', 'Weight Loss Program'),
                    'action': self._t('استشر أخصائي تغذية واتبع نظاماً غذائياً متوازناً', 'Consult a nutritionist and follow a balanced diet'),
                    'daily_tip': self._t('قلل السكريات والمقليات، وزد الخضروات والبروتين', 'Reduce sugars and fried foods, increase vegetables and protein'),
                })
            elif 'نقص' in bmi_category or 'Underweight' in bmi_category:
                recommendations.append({
                    'category': 'weight',
                    'priority': 'high',
                    'icon': '💪',
                    'title': self._t('زيادة الوزن الصحي', 'Healthy Weight Gain'),
                    'action': self._t('تناول وجبات متكررة غنية بالبروتين والدهون الصحية', 'Eat frequent meals rich in protein and healthy fats'),
                    'daily_tip': self._t('أضف المكسرات والأفوكادو وزيت الزيتون إلى وجباتك', 'Add nuts, avocado, and olive oil to your meals'),
                })
        
        # توصيات النوم
        avg_sleep = df['sleep_hours'].mean() if 'sleep_hours' in df else 0
        if avg_sleep < 6:
            recommendations.append({
                'category': 'sleep',
                'priority': 'high',
                'icon': '🌙',
                'title': self._t('تحسين جودة النوم', 'Improve Sleep Quality'),
                'action': self._t('ثبّت موعد النوم والاستيقاظ وتجنب الشاشات قبل النوم', 'Set a fixed sleep/wake time and avoid screens before bed'),
                'daily_tip': self._t('اخلد إلى النوم مبكراً بـ 20 دقيقة هذا الأسبوع', 'Go to bed 20 minutes earlier this week'),
            })
        elif avg_sleep > 9:
            recommendations.append({
                'category': 'sleep',
                'priority': 'medium',
                'icon': '⏰',
                'title': self._t('تنظيم ساعات النوم', 'Regulate Sleep Hours'),
                'action': self._t('قلل ساعات النوم تدريجياً إلى 8 ساعات', 'Gradually reduce sleep hours to 8'),
                'daily_tip': self._t('استخدم منبهاً للاستيقاظ في نفس الوقت يومياً', 'Use an alarm to wake up at the same time daily'),
            })
        
        # توصيات النشاط
        avg_activity = df['activity_minutes'].mean() if 'activity_minutes' in df else 0
        if avg_activity < 30:
            recommendations.append({
                'category': 'activity',
                'priority': 'high',
                'icon': '🏃',
                'title': self._t('زيادة النشاط البدني', 'Increase Physical Activity'),
                'action': self._t('امشِ 30 دقيقة يومياً لمدة 5 أيام في الأسبوع', 'Walk 30 minutes daily for 5 days per week'),
                'daily_tip': self._t('استخدم الدرج بدلاً من المصعد وامشِ أثناء المكالمات', 'Use stairs instead of elevator and walk during calls'),
            })
        
        # توصيات التغذية
        avg_calories = df['calories'].mean() if 'calories' in df else 0
        if avg_calories > 2500:
            recommendations.append({
                'category': 'nutrition',
                'priority': 'medium',
                'icon': '🥗',
                'title': self._t('تقليل السعرات الحرارية', 'Reduce Calories'),
                'action': self._t('استخدم صحون أصغر وتناول الخضروات أولاً', 'Use smaller plates and eat vegetables first'),
                'daily_tip': self._t('اشرب كوب ماء قبل كل وجبة', 'Drink a glass of water before each meal'),
            })
        elif avg_calories < 1500 and avg_calories > 0:
            recommendations.append({
                'category': 'nutrition',
                'priority': 'medium',
                'icon': '🍽️',
                'title': self._t('زيادة السعرات الحرارية', 'Increase Calories'),
                'action': self._t('أضف وجبة خفيفة صحية بين الوجبات الرئيسية', 'Add a healthy snack between main meals'),
                'daily_tip': self._t('تناول حفنة من المكسرات كوجبة خفيفة', 'Eat a handful of nuts as a snack'),
            })
        
        # توصيات المزاج
        avg_mood = df['mood_score'].mean() if 'mood_score' in df else 0
        if avg_mood < 2.5:
            recommendations.append({
                'category': 'mood',
                'priority': 'high',
                'icon': '😊',
                'title': self._t('تحسين الصحة النفسية', 'Improve Mental Health'),
                'action': self._t('مارس التأمل 10 دقائق يومياً وتواصل مع الأصدقاء', 'Practice meditation 10 minutes daily and connect with friends'),
                'daily_tip': self._t('اكتب 3 أشياء تشعر بالامتنان لها يومياً', 'Write 3 things you are grateful for daily'),
            })
        
        return recommendations
    
    def _generate_executive_summary(self, raw_data, df, bmi_category):
        """توليد ملخص تنفيذي شامل"""
        
        # حساب الإحصائيات الرئيسية
        total_days = len(df)
        avg_sleep = df['sleep_hours'].mean() if 'sleep_hours' in df else 0
        avg_mood = df['mood_score'].mean() if 'mood_score' in df else 0
        avg_activity = df['activity_minutes'].mean() if 'activity_minutes' in df else 0
        total_calories_burned = df['calories_burned'].sum() if 'calories_burned' in df else 0
        
        # إنشاء الملخص
        if self.language == 'ar':
            summary = f"""📊 **ملخص صحتك الشامل لآخر {total_days} يوماً**

⚖️ **الوزن و BMI**: {bmi_category if bmi_category else 'غير متوفر'}

🌙 **النوم**: بمعدل {avg_sleep:.1f} ساعات ليلاً

😊 **المزاج**: {'جيد' if avg_mood >= 3 else 'يحتاج تحسين'} ({avg_mood:.1f}/5)

🏃 **النشاط**: {avg_activity:.0f} دقيقة نشاط يومياً

🔥 **السعرات المحروقة**: {total_calories_burned:.0f} سعرة خلال الفترة

💪 **التقدم العام**: {'مرتفع' if avg_activity >= 30 and 7 <= avg_sleep <= 9 else 'متوسط' if avg_activity >= 15 else 'يحتاج تحسين'}
"""
        else:
            summary = f"""📊 **Your Comprehensive Health Summary for the last {total_days} days**

⚖️ **Weight & BMI**: {bmi_category if bmi_category else 'N/A'}

🌙 **Sleep**: Average {avg_sleep:.1f} hours nightly

😊 **Mood**: {'Good' if avg_mood >= 3 else 'Needs improvement'} ({avg_mood:.1f}/5)

🏃 **Activity**: {avg_activity:.0f} minutes of daily activity

🔥 **Calories Burned**: {total_calories_burned:.0f} calories during the period

💪 **Overall Progress**: {'High' if avg_activity >= 30 and 7 <= avg_sleep <= 9 else 'Medium' if avg_activity >= 15 else 'Needs improvement'}
"""
        
        return summary
    
    def _get_bmi_category(self, bmi):
        """تصنيف BMI"""
        if bmi < 18.5:
            return self._t('نقص الوزن', 'Underweight')
        elif 18.5 <= bmi < 25:
            return self._t('وزن طبيعي', 'Normal weight')
        elif 25 <= bmi < 30:
            return self._t('زيادة وزن', 'Overweight')
        elif 30 <= bmi < 35:
            return self._t('سمنة درجة أولى', 'Obesity Class I')
        elif 35 <= bmi < 40:
            return self._t('سمنة درجة ثانية', 'Obesity Class II')
        else:
            return self._t('سمنة مفرطة', 'Extreme Obesity')

    def train_weight_prediction_model(self):
        """تدريب نموذج للتنبؤ بالوزن"""
        
        # جمع البيانات
        raw_data = self.collect_all_health_data(days=90)
        df = self.prepare_features(raw_data)
        
        # إزالة القيم الفارغة
        df = df.dropna(subset=['weight'])
        
        if len(df) < 14:  #需要有14 يوم على الأقل
            return None
        
        # اختيار الميزات
        feature_cols = ['day_of_week', 'month', 'is_weekend', 
                       'sleep_hours', 'sleep_quality', 'mood_score',
                       'calories', 'protein', 'activity_minutes', 
                       'habits_completed', 'avg_temp', 'humidity',
                       'sleep_7d_avg', 'calories_7d_avg']
        
        # الميزات المتوفرة فقط
        available_features = [col for col in feature_cols if col in df.columns]
        
        X = df[available_features].fillna(0)
        y = df['weight']
        
        # تدريب النموذج
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        # حفظ النموذج
        joblib.dump(model, f'{self.models_path}weight_model_{self.user.id}.pkl')
        
        return model
    
    def predict_future_weight(self, days=7):
        """التنبؤ بالوزن المستقبلي"""
        
        model_path = f'{self.models_path}weight_model_{self.user.id}.pkl'
        if not os.path.exists(model_path):
            model = self.train_weight_prediction_model()
        else:
            model = joblib.load(model_path)
        
        if not model:
            return None
        
        # تجهيز بيانات للتنبؤ
        raw_data = self.collect_all_health_data(days=30)
        df = self.prepare_features(raw_data)
        
        # الحصول على أسماء الميزات التي تدرّب عليها النموذج
        feature_names = model.feature_names_in_ if hasattr(model, 'feature_names_in_') else None
        
        # آخر 7 أيام للتنبؤ
        last_week = df.tail(7).copy()
        
        predictions = []
        for i in range(days):
            # استخدام متوسط آخر 7 أيام للتنبؤ
            pred_features = last_week.mean().to_frame().T
            
            # التأكد من تطابق الميزات مع النموذج
            if feature_names is not None:
                # إعادة ترتيب الميزات حسب ما يتوقعه النموذج
                pred_features = pred_features[feature_names]
            else:
                # إذا لم يكن هناك feature_names، استخدم أول 14 ميزة فقط
                pred_features = pred_features.iloc[:, :14]
            
            pred = model.predict(pred_features)[0]
            predictions.append(pred)
            
            # تحديث للتنبؤ التالي
            last_week = last_week.shift(-1)
            last_week.iloc[-1] = last_week.iloc[-2]  # تقريبي
        
        return predictions
    
    def detect_health_patterns(self):
        """اكتشاف الأنماط الصحية باستخدام clustering"""
        
        raw_data = self.collect_all_health_data(days=60)
        df = self.prepare_features(raw_data)
        
        # اختيار ميزات للتحليل
        pattern_features = ['sleep_hours', 'mood_score', 'calories', 
                           'activity_minutes', 'habits_completed']
        
        available_features = [col for col in pattern_features if col in df.columns]
        X = df[available_features].fillna(0)
        
        if len(X) < 7:
            return []
        
        # تطبيع البيانات
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # تجميع الأيام المتشابهة
        kmeans = KMeans(n_clusters=min(3, len(X)), random_state=42)
        clusters = kmeans.fit_predict(X_scaled)
        
        # تحليل كل cluster
        patterns = []
        for i in range(kmeans.n_clusters):
            cluster_days = df.iloc[clusters == i]
            if len(cluster_days) > 0:
                pattern = {
                    'type': self._t(f'نمط {i+1}', f'Pattern {i+1}'),
                    'description': self._describe_pattern(cluster_days),
                    'frequency': self._t(f"{len(cluster_days)} يوم", f"{len(cluster_days)} days"),
                    'avg_sleep': cluster_days['sleep_hours'].mean(),
                    'avg_mood': cluster_days['mood_score'].mean(),
                    'avg_calories': cluster_days['calories'].mean()
                }
                patterns.append(pattern)
        
        return patterns
    
    def _describe_pattern(self, cluster_days):
        """وصف النمط المكتشف"""
        avg_sleep = cluster_days['sleep_hours'].mean()
        avg_mood = cluster_days['mood_score'].mean()
        avg_calories = cluster_days['calories'].mean()
        
        sleep_desc = self._t(
            "نوم قليل" if avg_sleep < 6 else "نوم كثير" if avg_sleep > 8 else "نوم مثالي",
            "Low sleep" if avg_sleep < 6 else "Excessive sleep" if avg_sleep > 8 else "Ideal sleep"
        )
        
        mood_desc = self._t(
            "مزاج ممتاز" if avg_mood > 4 else "مزاج جيد" if avg_mood > 3 else "مزاج منخفض",
            "Excellent mood" if avg_mood > 4 else "Good mood" if avg_mood > 3 else "Low mood"
        )
        
        return self._t(
            f"{sleep_desc}، {mood_desc}، سعرات {int(avg_calories)}",
            f"{sleep_desc}, {mood_desc}, {int(avg_calories)} calories"
        )
    
    def generate_smart_recommendations(self):
        """توليد توصيات ذكية شاملة"""
        
        raw_data = self.collect_all_health_data(days=30)
        df = self.prepare_features(raw_data)
        
        recommendations = []
        
        # 1. تحليل النوم
        avg_sleep = df['sleep_hours'].mean()
        if avg_sleep < 6:
            recommendations.append({
                'category': 'sleep',
                'type': 'warning',
                'priority': 'high',
                'icon': '🌙',
                'message': self._t(
                    f'متوسط نومك {avg_sleep:.1f} ساعات فقط! هذا أقل من المعدل الصحي.',
                    f'Your average sleep is only {avg_sleep:.1f} hours! This is below the healthy range.'
                ),
                'advice': self._t(
                    'حاول النوم مبكراً وتجنب الشاشات قبل النوم',
                    'Try to sleep earlier and avoid screens before bedtime'
                )
            })
        elif avg_sleep > 9:
            recommendations.append({
                'category': 'sleep',
                'type': 'tip',
                'priority': 'medium',
                'icon': '🌙',
                'message': self._t(
                    f'تنام {avg_sleep:.1f} ساعات في المتوسط، قد يكون أكثر من اللازم',
                    f'You sleep an average of {avg_sleep:.1f} hours, which may be too much'
                ),
                'advice': self._t(
                    'حاول تقليل ساعات النوم تدريجياً',
                    'Try to gradually reduce your sleep hours'
                )
            })
        
        # 2. تحليل المزاج
        avg_mood = df['mood_score'].mean()
        if avg_mood < 2.5:
            recommendations.append({
                'category': 'mood',
                'type': 'warning',
                'priority': 'high',
                'icon': '😔',
                'message': self._t(
                    'مزاجك منخفض مؤخراً',
                    'Your mood has been low lately'
                ),
                'advice': self._t(
                    'جرب تمارين التأمل، تحدث مع صديق، أو مارس هواية تحبها',
                    'Try meditation, talk to a friend, or engage in a hobby you enjoy'
                )
            })
        
        # 3. تحليل التغذية
        avg_calories = df['calories'].mean()
        user_weight = raw_data['health'][-1].weight_kg if raw_data['health'] else None
        if user_weight:
            recommended_calories = user_weight * 24  # تقريبي
            if avg_calories > recommended_calories * 1.2:
                recommendations.append({
                    'category': 'nutrition',
                    'type': 'warning',
                    'priority': 'medium',
                    'icon': '🍔',
                    'message': self._t(
                        'تستهلك سعرات حرارية أكثر من الموصى به',
                        'You are consuming more calories than recommended'
                    ),
                    'advice': self._t(
                        'حاول تقليل النشويات والدهون، وزد الخضروات',
                        'Try to reduce carbs and fats, and increase vegetables'
                    )
                })
        
        # 4. تحليل النشاط
        avg_activity = df['activity_minutes'].mean()
        if avg_activity < 15:
            recommendations.append({
                'category': 'activity',
                'type': 'motivation',
                'priority': 'medium',
                'icon': '🚶',
                'message': self._t(
                    'نشاطك البدني قليل هذا الأسبوع',
                    'Your physical activity is low this week'
                ),
                'advice': self._t(
                    'ابدأ بالمشي 10 دقائق يومياً وزد المدة تدريجياً',
                    'Start walking 10 minutes daily and gradually increase'
                )
            })
        
        # 5. تحليل العادات
        avg_habits = df['habits_completed'].mean()
        if avg_habits < 3 and df['habits_completed'].max() > 0:
            recommendations.append({
                'category': 'habits',
                'type': 'tip',
                'priority': 'low',
                'icon': '💊',
                'message': self._t(
                    f'تلتزم بـ {avg_habits:.0f} عادة يومياً في المتوسط',
                    f'You maintain an average of {avg_habits:.0f} habits daily'
                ),
                'advice': self._t(
                    'حاول إضافة عادة صغيرة جديدة كل أسبوع',
                    'Try adding one small new habit each week'
                )
            })
        
        # 6. تحليل ارتباط النوم بالمزاج
        sleep_mood_corr = df[['sleep_hours', 'mood_score']].corr().iloc[0,1]
        if sleep_mood_corr > 0.5:
            recommendations.append({
                'category': 'insight',
                'type': 'info',
                'priority': 'low',
                'icon': '🔗',
                'message': self._t(
                    'لاحظت أن نومك يؤثر إيجاباً على مزاجك!',
                    'I noticed that your sleep positively affects your mood!'
                ),
                'advice': self._t(
                    'حافظ على نمط نومك الحالي',
                    'Maintain your current sleep pattern'
                )
            })
        elif sleep_mood_corr < -0.3:
            recommendations.append({
                'category': 'insight',
                'type': 'warning',
                'priority': 'medium',
                'icon': '⚠️',
                'message': self._t(
                    'يبدو أن هناك علاقة عكسية بين نومك ومزاجك',
                    'There seems to be an inverse relationship between your sleep and mood'
                ),
                'advice': self._t(
                    'جرب تغيير وقت نومك أو مدته',
                    'Try changing your sleep time or duration'
                )
            })
        
        # 7. تنبؤات مستقبلية
        weight_pred = self.predict_future_weight(days=3)
        if weight_pred:
            avg_pred = np.mean(weight_pred)
            current_weight = raw_data['health'][-1].weight_kg if raw_data['health'] else None
            if current_weight and abs(avg_pred - current_weight) > 2:
                recommendations.append({
                    'category': 'prediction',
                    'type': 'info',
                    'priority': 'low',
                    'icon': '🔮',
                    'message': self._t(
                        f'أتوقع أن يصل وزنك إلى {avg_pred:.1f} كجم خلال 3 أيام',
                        f'I predict your weight will reach {avg_pred:.1f} kg in 3 days'
                    ),
                    'advice': self._t(
                        'حافظ على روتينك الحالي إذا كان الهدف هو الاستقرار',
                        'Maintain your current routine if stability is your goal'
                    )
                })
        
        return recommendations
    
    def get_comprehensive_analytics(self):
        """الحصول على تحليلات شاملة"""
        
        raw_data = self.collect_all_health_data(days=30)
        df = self.prepare_features(raw_data)
        
        # الأنماط
        patterns = self.detect_health_patterns()
        
        # التوصيات
        recommendations = self.generate_smart_recommendations()
        
        # إحصائيات عامة
        stats = {
            'avg_sleep': df['sleep_hours'].mean(),
            'avg_mood': df['mood_score'].mean(),
            'avg_calories': df['calories'].mean(),
            'avg_activity': df['activity_minutes'].mean(),
            'avg_habits': df['habits_completed'].mean(),
            'sleep_trend': self._t('تحسن', 'Improving') if df['sleep_hours'].iloc[-3:].mean() > df['sleep_hours'].iloc[:3].mean() else self._t('تراجع', 'Declining'),
            'mood_trend': self._t('تحسن', 'Improving') if df['mood_score'].iloc[-3:].mean() > df['mood_score'].iloc[:3].mean() else self._t('تراجع', 'Declining')
        }
        
        # نقاط القوة والضعف
        strengths = []
        weaknesses = []
        
        if stats['avg_sleep'] >= 7:
            strengths.append(self._t('نوم جيد', 'Good sleep'))
        else:
            weaknesses.append(self._t('قلة النوم', 'Lack of sleep'))
        
        if stats['avg_mood'] >= 3.5:
            strengths.append(self._t('مزاج مستقر', 'Stable mood'))
        else:
            weaknesses.append(self._t('تقلبات مزاجية', 'Mood swings'))
        
        if stats['avg_calories'] > 0:
            if 1800 < stats['avg_calories'] < 2500:
                strengths.append(self._t('تغذية متوازنة', 'Balanced nutrition'))
            else:
                weaknesses.append(self._t('تغذية غير متوازنة', 'Unbalanced nutrition'))
        
        return {
            'stats': stats,
            'patterns': patterns,
            'recommendations': recommendations,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'prediction': self.predict_future_weight(days=7)
        }
"""
خدمة التحليلات الصحية الشاملة - Comprehensive Health Analytics Service
تدمج جميع نماذج التطبيق وتقدم تحليلات متقدمة وتوصيات مخصصة باستخدام ML
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, Min, Max, StdDev
from django.db.models.functions import TruncDate, ExtractDay, ExtractWeek
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')

from ..models import (
    CustomUser, HealthStatus, PhysicalActivity, Sleep, MoodEntry, 
    Meal, FoodItem, HabitDefinition, HabitLog, HealthGoal,
    ChronicCondition, MedicalRecord, Notification, EnvironmentData,
    Achievement
)


class ComprehensiveHealthAnalytics:
    """
    نظام تحليلات صحي شامل - يدمج جميع جوانب المستخدم
    يقدم توصيات مخصصة بناءً على الحالة الصحية الفردية
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.today = timezone.now().date()
        self.is_arabic = language == 'ar'
        
        # جلب بيانات المستخدم الشخصية
        self._load_user_profile()
        
        # تخزين البيانات للتحليل
        self._cache = {}
        
    def _t(self, ar_text, en_text, **kwargs):
        """ترجمة النصوص"""
        text = ar_text if self.is_arabic else en_text
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text
    
    def _load_user_profile(self):
        """تحميل كامل بيانات المستخدم من CustomUser"""
        self.user_age = None
        self.user_gender = self.user.gender if hasattr(self.user, 'gender') else None
        self.user_height = float(self.user.height) if hasattr(self.user, 'height') and self.user.height else None
        self.user_initial_weight = float(self.user.initial_weight) if hasattr(self.user, 'initial_weight') and self.user.initial_weight else None
        self.user_health_goal = self.user.health_goal if hasattr(self.user, 'health_goal') else None
        self.user_activity_level = self.user.activity_level if hasattr(self.user, 'activity_level') else None
        self.user_occupation = self.user.occupation_status if hasattr(self.user, 'occupation_status') else None
        
        # حساب العمر
        if hasattr(self.user, 'date_of_birth') and self.user.date_of_birth:
            today = timezone.now().date()
            self.user_age = today.year - self.user.date_of_birth.year - (
                (today.month, today.day) < (self.user.date_of_birth.month, self.user.date_of_birth.day)
            )
        
        # حساب BMI
        self.user_bmi = None
        if self.user_height and self.user_initial_weight:
            height_m = self.user_height / 100
            self.user_bmi = round(self.user_initial_weight / (height_m ** 2), 1)
        
        # الأمراض المزمنة
        self.chronic_conditions = list(ChronicCondition.objects.filter(
            user=self.user, is_active=True
        ).values_list('name', flat=True))
    
    # ==========================================================================
    # 1. جمع البيانات الشامل من جميع النماذج
    # ==========================================================================
    
    def collect_all_data(self, days=90):
        """جمع جميع بيانات المستخدم من كل نماذج التطبيق"""
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        data = {
            # البيانات الحيوية
            'health': list(HealthStatus.objects.filter(
                user=self.user, recorded_at__range=[start_date, end_date]
            ).order_by('recorded_at')),
            
            # النشاط البدني
            'activities': list(PhysicalActivity.objects.filter(
                user=self.user, start_time__range=[start_date, end_date]
            ).order_by('start_time')),
            
            # النوم
            'sleep': list(Sleep.objects.filter(
                user=self.user, sleep_start__range=[start_date, end_date]
            ).order_by('sleep_start')),
            
            # المزاج
            'moods': list(MoodEntry.objects.filter(
                user=self.user, entry_time__range=[start_date, end_date]
            ).order_by('entry_time')),
            
            # التغذية
            'meals': list(Meal.objects.filter(
                user=self.user, meal_time__range=[start_date, end_date]
            ).order_by('meal_time').prefetch_related('food_items')),
            
            # العادات
            'habit_definitions': list(HabitDefinition.objects.filter(user=self.user, is_active=True)),
            'habit_logs': list(HabitLog.objects.filter(
                habit__user=self.user, log_date__range=[start_date.date(), end_date.date()]
            ).select_related('habit')),
            
            # الأهداف الصحية
            'goals': list(HealthGoal.objects.filter(user=self.user)),
            
            # الأمراض المزمنة
            'chronic_conditions': self.chronic_conditions,
            
            # السجلات الطبية
            'medical_records': list(MedicalRecord.objects.filter(
                user=self.user, event_date__range=[start_date.date(), end_date.date()]
            )),
            
            # البيانات البيئية
            'environment': list(EnvironmentData.objects.filter(
                user=self.user, date__range=[start_date.date(), end_date.date()]
            ).order_by('date')),
            
            # الإنجازات
            'achievements': list(Achievement.objects.filter(user=self.user)),
        }
        
        return data
    
    # ==========================================================================
    # 2. التحليل الشامل لكل جانب
    # ==========================================================================
    
    def get_complete_analysis(self):
        """تحليل شامل لكل جوانب المستخدم"""
        
        data = self.collect_all_data(days=90)
        
        return {
            # الملف الشخصي
            'profile': self._analyze_profile_complete(),
            
            # الوزن و BMI
            'weight_bmi': self._analyze_weight_bmi_advanced(data),
            
            # العلامات الحيوية
            'vital_signs': self._analyze_vital_signs_advanced(data),
            
            # النوم
            'sleep': self._analyze_sleep_advanced(data),
            
            # المزاج والصحة النفسية
            'mood_mental': self._analyze_mood_advanced(data),
            
            # التغذية
            'nutrition': self._analyze_nutrition_advanced(data),
            
            # النشاط البدني
            'activity': self._analyze_activity_advanced(data),
            
            # العادات والالتزام
            'habits': self._analyze_habits_advanced(data),
            
            # الأهداف الصحية
            'goals': self._analyze_goals_progress(data),
            
            # الأمراض المزمنة والمخاطر
            'health_risks': self._analyze_health_risks_complete(data),
            
            # الأنماط والارتباطات
            'patterns_correlations': self._analyze_patterns_ml(data),
            
            # التوقعات المستقبلية
            'predictions': self._predict_future_trends(data),
            
            # النتيجة الصحية الشاملة
            'health_score': self._calculate_holistic_health_score(data),
            
            # التوصيات المخصصة (الأهم)
            'personalized_recommendations': self._generate_personalized_recommendations(data),
            
            # ملخص تنفيذي
            'executive_summary': self._generate_executive_summary(data),
        }
    
    # ==========================================================================
    # 3. تحليل الملف الشخصي
    # ==========================================================================
    
    def _analyze_profile_complete(self):
        """تحليل كامل للملف الشخصي"""
        return {
            'age': self.user_age,
            'gender': self._t('ذكر', 'Male') if self.user_gender == 'M' else self._t('أنثى', 'Female') if self.user_gender == 'F' else None,
            'height_cm': self.user_height,
            'initial_weight_kg': self.user_initial_weight,
            'bmi': self.user_bmi,
            'bmi_category': self._get_bmi_category_text(),
            'health_goal': self.user_health_goal,
            'activity_level': self.user_activity_level,
            'occupation': self.user_occupation,
            'chronic_conditions': self.chronic_conditions,
            'profile_completeness': self._calculate_profile_completeness(),
            'missing_data': self._get_missing_profile_fields(),
            'age_category': self._get_age_category(),
            'risk_level': self._calculate_basic_risk_level(),
        }
    
    def _get_bmi_category_text(self):
        """نص فئة BMI"""
        if not self.user_bmi:
            return self._t('غير محدد', 'Unknown')
        if self.user_bmi < 18.5:
            return self._t('نقص الوزن', 'Underweight')
        elif self.user_bmi < 25:
            return self._t('وزن طبيعي', 'Normal')
        elif self.user_bmi < 30:
            return self._t('زيادة وزن', 'Overweight')
        elif self.user_bmi < 35:
            return self._t('سمنة درجة أولى', 'Obesity Class I')
        elif self.user_bmi < 40:
            return self._t('سمنة درجة ثانية', 'Obesity Class II')
        else:
            return self._t('سمنة مفرطة', 'Extreme Obesity')
    
    def _calculate_profile_completeness(self):
        """حساب نسبة اكتمال الملف الشخصي"""
        fields = [
            self.user_age, self.user_gender, self.user_height,
            self.user_initial_weight, self.user_health_goal,
            self.user_activity_level
        ]
        completed = sum(1 for f in fields if f)
        return round(completed / len(fields) * 100)
    
    def _get_missing_profile_fields(self):
        """الحقول الناقصة في الملف الشخصي"""
        missing = []
        if not self.user_age: missing.append('age')
        if not self.user_gender: missing.append('gender')
        if not self.user_height: missing.append('height')
        if not self.user_initial_weight: missing.append('initial_weight')
        if not self.user_health_goal: missing.append('health_goal')
        if not self.user_activity_level: missing.append('activity_level')
        return missing
    
    def _get_age_category(self):
        """فئة عمرية"""
        if not self.user_age:
            return 'unknown'
        if self.user_age < 18: return 'adolescent'
        if self.user_age < 30: return 'young_adult'
        if self.user_age < 50: return 'adult'
        if self.user_age < 70: return 'senior'
        return 'elderly'
    
    def _calculate_basic_risk_level(self):
        """مستوى الخطر الأساسي"""
        risk_score = 0
        if self.user_age and self.user_age > 50:
            risk_score += 2
        if self.user_bmi and self.user_bmi > 30:
            risk_score += 2
        if self.chronic_conditions:
            risk_score += len(self.chronic_conditions)
        if risk_score >= 3:
            return self._t('مرتفع', 'High')
        elif risk_score >= 1:
            return self._t('متوسط', 'Medium')
        return self._t('منخفض', 'Low')
    
    # ==========================================================================
    # 4. تحليل الوزن و BMI المتقدم
    # ==========================================================================
    
    def _analyze_weight_bmi_advanced(self, data):
        """تحليل متقدم للوزن و BMI"""
        
        health_records = data['health']
        if not health_records:
            return {'status': 'no_data'}
        
        latest_weight = float(health_records[-1].weight_kg) if health_records[-1].weight_kg else None
        oldest_weight = float(health_records[0].weight_kg) if health_records[0].weight_kg else None
        
        # حساب التغير في الوزن
        weight_change = None
        if latest_weight and oldest_weight:
            weight_change = round(latest_weight - oldest_weight, 1)
        
        # حساب الوزن المثالي
        ideal_weight_min = None
        ideal_weight_max = None
        if self.user_height:
            height_m = self.user_height / 100
            ideal_weight_min = round(18.5 * (height_m ** 2), 1)
            ideal_weight_max = round(24.9 * (height_m ** 2), 1)
        
        # تحديد الهدف
        target_weight = None
        if ideal_weight_min and ideal_weight_max and latest_weight:
            if latest_weight > ideal_weight_max:
                target_weight = ideal_weight_max
            elif latest_weight < ideal_weight_min:
                target_weight = ideal_weight_min
        
        return {
            'current_weight': latest_weight,
            'initial_weight': oldest_weight,
            'weight_change_90d': weight_change,
            'bmi': self.user_bmi,
            'bmi_category': self._get_bmi_category_text(),
            'ideal_weight_range': {'min': ideal_weight_min, 'max': ideal_weight_max},
            'weight_to_lose': round(latest_weight - ideal_weight_max, 1) if ideal_weight_max and latest_weight and latest_weight > ideal_weight_max else 0,
            'weight_to_gain': round(ideal_weight_min - latest_weight, 1) if ideal_weight_min and latest_weight and latest_weight < ideal_weight_min else 0,
            'target_weight': target_weight,
            'trend': self._calculate_weight_trend(health_records),
            'history': [{'date': h.recorded_at.date(), 'weight': float(h.weight_kg)} for h in health_records[-30:] if h.weight_kg]
        }
    
    def _calculate_weight_trend(self, health_records):
        """حساب اتجاه الوزن"""
        if len(health_records) < 7:
            return 'stable'
        
        recent_weights = [float(h.weight_kg) for h in health_records[-7:] if h.weight_kg]
        if len(recent_weights) < 2:
            return 'stable'
        
        if recent_weights[-1] > recent_weights[0] + 0.5:
            return 'increasing'
        elif recent_weights[-1] < recent_weights[0] - 0.5:
            return 'decreasing'
        return 'stable'
    
    # ==========================================================================
    # 5. تحليل العلامات الحيوية المتقدم
    # ==========================================================================
    
    def _analyze_vital_signs_advanced(self, data):
        """تحليل متقدم للعلامات الحيوية مع مراعاة العمر والأمراض المزمنة"""
        
        health_records = data['health']
        if not health_records:
            return {'status': 'no_data'}
        
        latest = health_records[-1]
        
        # النطاقات الطبيعية حسب العمر
        ranges = self._get_normal_ranges_by_age()
        
        alerts = []
        
        # تحليل ضغط الدم
        bp_status = 'normal'
        if latest.systolic_pressure and latest.diastolic_pressure:
            if latest.systolic_pressure > ranges['systolic']['max'] or latest.diastolic_pressure > ranges['diastolic']['max']:
                bp_status = 'high'
                alerts.append({
                    'type': 'blood_pressure',
                    'severity': 'high',
                    'message': self._t('⚠️ ضغط الدم مرتفع', '⚠️ High blood pressure'),
                    'advice': self._t('قلل الملح، زد البوتاسيوم، واستشر طبيبك', 'Reduce salt, increase potassium, consult your doctor')
                })
            elif latest.systolic_pressure < ranges['systolic']['min'] or latest.diastolic_pressure < ranges['diastolic']['min']:
                bp_status = 'low'
                alerts.append({
                    'type': 'blood_pressure',
                    'severity': 'medium',
                    'message': self._t('⚠️ ضغط الدم منخفض', '⚠️ Low blood pressure'),
                    'advice': self._t('اشرب كمية كافية من الماء', 'Drink enough water')
                })
        
        # تحليل السكر (مهم لمرضى السكري)
        glucose_status = 'normal'
        if latest.blood_glucose:
            glucose = float(latest.blood_glucose)
            if glucose > ranges['glucose']['max']:
                glucose_status = 'high'
                alerts.append({
                    'type': 'glucose',
                    'severity': 'high' if 'diabetes' in [c.lower() for c in self.chronic_conditions] else 'medium',
                    'message': self._t(f'⚠️ سكر الدم مرتفع: {glucose} mg/dL', f'⚠️ High blood sugar: {glucose} mg/dL'),
                    'advice': self._t('تجنب السكريات البسيطة ومارس المشي', 'Avoid simple sugars and walk')
                })
            elif glucose < ranges['glucose']['min']:
                glucose_status = 'low'
                alerts.append({
                    'type': 'glucose',
                    'severity': 'high',
                    'message': self._t(f'🚨 سكر الدم منخفض: {glucose} mg/dL', f'🚨 Low blood sugar: {glucose} mg/dL'),
                    'advice': self._t('تناول مصدر سكر سريع فوراً (تمر، عصير، عسل)', 'Eat quick sugar source immediately')
                })
        
        return {
            'recorded_at': latest.recorded_at,
            'blood_pressure': {
                'systolic': latest.systolic_pressure,
                'diastolic': latest.diastolic_pressure,
                'status': bp_status,
                'normal_range': f"{ranges['systolic']['min']}-{ranges['systolic']['max']}/{ranges['diastolic']['min']}-{ranges['diastolic']['max']}"
            },
            'blood_glucose': {
                'value': latest.blood_glucose,
                'status': glucose_status,
                'normal_range': f"{ranges['glucose']['min']}-{ranges['glucose']['max']} mg/dL"
            },
            'heart_rate': {
                'value': latest.heart_rate,
                'status': 'normal' if not latest.heart_rate or (60 <= latest.heart_rate <= 100) else ('high' if latest.heart_rate > 100 else 'low'),
                'normal_range': '60-100 BPM'
            },
            'oxygen_level': {
                'value': latest.spo2,
                'status': 'normal' if not latest.spo2 or latest.spo2 >= 95 else 'low',
                'normal_range': '95-100%'
            },
            'temperature': {
                'value': latest.body_temperature,
                'status': 'normal' if not latest.body_temperature or (36.5 <= float(latest.body_temperature) <= 37.5) else ('high' if float(latest.body_temperature) > 37.5 else 'low'),
                'normal_range': '36.5-37.5 °C'
            },
            'alerts': alerts,
            'risk_level': 'high' if any(a['severity'] == 'high' for a in alerts) else ('medium' if alerts else 'low')
        }
    
    def _get_normal_ranges_by_age(self):
        """النطاقات الطبيعية حسب العمر"""
        if self.user_age and self.user_age > 60:
            return {
                'systolic': {'min': 90, 'max': 150},
                'diastolic': {'min': 60, 'max': 90},
                'glucose': {'min': 70, 'max': 140},
                'heart_rate': {'min': 60, 'max': 100}
            }
        elif self.user_age and self.user_age < 18:
            return {
                'systolic': {'min': 90, 'max': 120},
                'diastolic': {'min': 50, 'max': 80},
                'glucose': {'min': 70, 'max': 140},
                'heart_rate': {'min': 70, 'max': 110}
            }
        else:
            return {
                'systolic': {'min': 90, 'max': 130},
                'diastolic': {'min': 60, 'max': 85},
                'glucose': {'min': 70, 'max': 140},
                'heart_rate': {'min': 60, 'max': 100}
            }
    
    # ==========================================================================
    # 6. تحليل النوم المتقدم
    # ==========================================================================
    
    def _analyze_sleep_advanced(self, data):
        """تحليل متقدم للنوم مع توصيات مخصصة"""
        
        sleep_records = data['sleep']
        if not sleep_records:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات نوم كافية', 'Insufficient sleep data')}
        
        # حساب المتوسطات
        sleep_hours = []
        sleep_qualities = []
        for sleep in sleep_records:
            if sleep.sleep_start and sleep.sleep_end:
                hours = (sleep.sleep_end - sleep.sleep_start).seconds / 3600
                sleep_hours.append(hours)
                sleep_qualities.append(sleep.quality_rating if sleep.quality_rating else 3)
        
        avg_hours = round(np.mean(sleep_hours), 1) if sleep_hours else 0
        avg_quality = round(np.mean(sleep_qualities), 1) if sleep_qualities else 0
        
        # تحليل الانتظام
        bed_times = [s.sleep_start.hour + s.sleep_start.minute/60 for s in sleep_records if s.sleep_start]
        bed_time_std = np.std(bed_times) if len(bed_times) > 1 else 0
        
        # تقييم النوم
        sleep_score = 0
        if 7 <= avg_hours <= 9:
            sleep_score += 40
        elif 6 <= avg_hours < 7 or 9 < avg_hours <= 10:
            sleep_score += 25
        else:
            sleep_score += 10
        
        if avg_quality >= 4:
            sleep_score += 40
        elif avg_quality >= 3:
            sleep_score += 25
        
        if bed_time_std < 1:
            sleep_score += 20
        elif bed_time_std < 2:
            sleep_score += 10
        
        # توصيات مخصصة
        recommendations = []
        if avg_hours < 7:
            recommendations.append({
                'icon': '🌙',
                'title': self._t('زيادة ساعات النوم', 'Increase sleep hours'),
                'advice': self._t('حاول النوم مبكراً بـ 30 دقيقة تدريجياً', 'Try sleeping 30 minutes earlier gradually')
            })
        if avg_quality < 3.5:
            recommendations.append({
                'icon': '😴',
                'title': self._t('تحسين جودة النوم', 'Improve sleep quality'),
                'advice': self._t('تجنب الكافيين قبل النوم بـ 6 ساعات وحافظ على غرفة مظلمة وهادئة', 'Avoid caffeine 6 hours before bed, keep room dark and quiet')
            })
        if bed_time_std > 1.5:
            recommendations.append({
                'icon': '⏰',
                'title': self._t('تنظيم مواعيد النوم', 'Regular sleep schedule'),
                'advice': self._t('ثبت موعد النوم والاستيقاظ حتى في عطلات نهاية الأسبوع', 'Fix sleep and wake times even on weekends')
            })
        
        return {
            'average_hours': avg_hours,
            'average_quality': avg_quality,
            'total_records': len(sleep_records),
            'sleep_score': min(100, sleep_score),
            'regularity': 'منتظم' if bed_time_std < 1 else self._t('غير منتظم', 'Irregular'),
            'bed_time_consistency_hours': round(bed_time_std, 1),
            'recommendations': recommendations,
            'trend': self._t('تحسن', 'Improving') if len(sleep_hours) >= 14 and np.mean(sleep_hours[-7:]) > np.mean(sleep_hours[:7]) else self._t('تراجع', 'Declining')
        }
    
    # ==========================================================================
    # 7. تحليل المزاج المتقدم
    # ==========================================================================
    
    def _analyze_mood_advanced(self, data):
        """تحليل متقدم للمزاج والصحة النفسية"""
        
        mood_records = data['moods']
        if not mood_records:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات مزاج كافية', 'Insufficient mood data')}
        
        # تحويل المزاج إلى درجات
        mood_score_map = {
            'Excellent': 5, 'Good': 4, 'Neutral': 3,
            'Stressed': 2, 'Anxious': 2, 'Sad': 1, 'Depressed': 0
        }
        
        mood_scores = [mood_score_map.get(m.mood, 3) for m in mood_records]
        avg_mood = round(np.mean(mood_scores), 1)
        
        # توزيع المزاج
        mood_distribution = {}
        for mood in mood_records:
            mood_distribution[mood.mood] = mood_distribution.get(mood.mood, 0) + 1
        
        # اتجاه المزاج
        recent_mood = np.mean(mood_scores[-7:]) if len(mood_scores) >= 7 else avg_mood
        previous_mood = np.mean(mood_scores[:7]) if len(mood_scores) >= 14 else avg_mood
        trend = 'improving' if recent_mood > previous_mood else ('declining' if recent_mood < previous_mood else 'stable')
        
        # توصيات مخصصة
        recommendations = []
        if avg_mood < 2.5:
            recommendations.append({
                'icon': '😔',
                'title': self._t('دعم الصحة النفسية', 'Mental Health Support'),
                'advice': self._t('جرب التأمل اليومي لمدة 5 دقائق، وتحدث مع شخص تثق به', 'Try daily meditation for 5 minutes, talk to someone you trust')
            })
        if trend == 'declining':
            recommendations.append({
                'icon': '📉',
                'title': self._t('مراقبة المزاج', 'Mood Monitoring'),
                'advice': self._t('تتبع العوامل المؤثرة على مزاجك وحاول معالجتها', 'Track factors affecting your mood and try to address them')
            })
        
        return {
            'average_mood_score': avg_mood,
            'mood_level': self._t('ممتاز', 'Excellent') if avg_mood >= 4.5 else self._t('جيد', 'Good') if avg_mood >= 3.5 else self._t('متوسط', 'Fair') if avg_mood >= 2.5 else self._t('منخفض', 'Low'),
            'mood_distribution': mood_distribution,
            'total_records': len(mood_records),
            'trend': trend,
            'recent_mood': recent_mood,
            'recommendations': recommendations
        }
    
    # ==========================================================================
    # 8. تحليل التغذية المتقدم
    # ==========================================================================
    
    def _analyze_nutrition_advanced(self, data):
        """تحليل متقدم للتغذية والنظام الغذائي"""
        
        meals = data['meals']
        if not meals:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات تغذية كافية', 'Insufficient nutrition data')}
        
        # حساب المتوسطات اليومية
        daily_calories = {}
        daily_protein = {}
        daily_carbs = {}
        daily_fats = {}
        
        for meal in meals:
            date = meal.meal_time.date()
            daily_calories[date] = daily_calories.get(date, 0) + (meal.total_calories or 0)
            daily_protein[date] = daily_protein.get(date, 0) + (meal.total_protein or 0)
            daily_carbs[date] = daily_carbs.get(date, 0) + (meal.total_carbs or 0)
            daily_fats[date] = daily_fats.get(date, 0) + (meal.total_fat or 0)
        
        avg_calories = round(np.mean(list(daily_calories.values()))) if daily_calories else 0
        avg_protein = round(np.mean(list(daily_protein.values())), 1) if daily_protein else 0
        
        # حساب السعرات الموصى بها حسب الوزن والهدف
        recommended_calories = self._calculate_recommended_calories()
        
        # توزيع الوجبات
        meal_type_distribution = {}
        for meal in meals:
            meal_type_distribution[meal.meal_type] = meal_type_distribution.get(meal.meal_type, 0) + 1
        
        # توصيات مخصصة
        recommendations = []
        if avg_calories > recommended_calories * 1.1:
            recommendations.append({
                'icon': '🍽️',
                'title': self._t('تقليل السعرات', 'Reduce Calories'),
                'advice': self._t('قلل من الكربوهيدرات البسيطة والدهون المشبعة، زد الخضروات', 'Reduce simple carbs and saturated fats, increase vegetables')
            })
        elif avg_calories < recommended_calories * 0.9 and avg_calories > 0:
            recommendations.append({
                'icon': '🥗',
                'title': self._t('زيادة السعرات', 'Increase Calories'),
                'advice': self._t('أضف وجبات خفيفة صحية بين الوجبات الرئيسية', 'Add healthy snacks between main meals')
            })
        
        return {
            'average_daily_calories': avg_calories,
            'average_daily_protein_g': avg_protein,
            'recommended_calories': recommended_calories,
            'meal_type_distribution': meal_type_distribution,
            'total_meals': len(meals),
            'recommendations': recommendations
        }
    
    def _calculate_recommended_calories(self):
        """حساب السعرات الموصى بها حسب الوزن والهدف"""
        latest_weight = self._get_latest_weight()
        if not latest_weight:
            return 2000
        
        # BMR باستخدام Mifflin-St Jeor
        if self.user_gender == 'F':
            bmr = (10 * latest_weight) + (6.25 * (self.user_height or 170)) - (5 * (self.user_age or 30)) - 161
        else:
            bmr = (10 * latest_weight) + (6.25 * (self.user_height or 170)) - (5 * (self.user_age or 30)) + 5
        
        # معامل النشاط
        activity_factors = {'low': 1.2, 'medium': 1.375, 'high': 1.55}
        factor = activity_factors.get(self.user_activity_level or 'medium', 1.375)
        
        tdee = bmr * factor
        
        # تعديل حسب الهدف
        if self.user_health_goal == 'loss':
            return max(1200, tdee - 500)
        elif self.user_health_goal == 'gain':
            return tdee + 300
        else:
            return tdee
    
    def _get_latest_weight(self):
        """آخر وزن مسجل"""
        latest = HealthStatus.objects.filter(user=self.user, weight_kg__isnull=False).order_by('-recorded_at').first()
        return float(latest.weight_kg) if latest else None
    
    # ==========================================================================
    # 9. تحليل النشاط البدني المتقدم
    # ==========================================================================
    
    def _analyze_activity_advanced(self, data):
        """تحليل متقدم للنشاط البدني"""
        
        activities = data['activities']
        if not activities:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات نشاط كافية', 'Insufficient activity data')}
        
        total_duration = sum(a.duration_minutes or 0 for a in activities)
        total_calories = sum(a.calories_burned or 0 for a in activities)
        avg_daily_duration = total_duration / 90 if len(activities) > 0 else 0
        
        # تنوع الأنشطة
        activity_types = {}
        for act in activities:
            activity_types[act.activity_type] = activity_types.get(act.activity_type, 0) + 1
        
        # توصيات مخصصة
        recommendations = []
        if avg_daily_duration < 30:
            recommendations.append({
                'icon': '🚶',
                'title': self._t('زيادة النشاط البدني', 'Increase Physical Activity'),
                'advice': self._t('امشِ 30 دقيقة يومياً لمدة 5 أيام في الأسبوع', 'Walk 30 minutes daily for 5 days per week')
            })
        if len(activity_types) < 2:
            recommendations.append({
                'icon': '🏋️',
                'title': self._t('تنويع التمارين', 'Diversify Workouts'),
                'advice': self._t('أضف تمارين مقاومة أو مرونة إلى روتينك', 'Add resistance or flexibility exercises to your routine')
            })
        
        return {
            'total_activities': len(activities),
            'total_duration_minutes': total_duration,
            'total_calories_burned': total_calories,
            'average_daily_minutes': round(avg_daily_duration, 1),
            'activity_types': activity_types,
            'recommendations': recommendations,
            'activity_level': self._t('ممتاز', 'Excellent') if avg_daily_duration >= 30 else self._t('جيد', 'Good') if avg_daily_duration >= 15 else self._t('منخفض', 'Low')
        }
    
    # ==========================================================================
    # 10. تحليل العادات
    # ==========================================================================
    
    def _analyze_habits_advanced(self, data):
        """تحليل العادات والالتزام"""
        
        habit_logs = data['habit_logs']
        habit_defs = data['habit_definitions']
        
        if not habit_logs:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات عادات كافية', 'Insufficient habit data')}
        
        # حساب نسبة الالتزام
        completed = sum(1 for log in habit_logs if log.is_completed)
        completion_rate = (completed / len(habit_logs) * 100) if habit_logs else 0
        
        # العادات الأكثر التزاماً
        habit_completion = {}
        for log in habit_logs:
            habit_completion[log.habit.name] = habit_completion.get(log.habit.name, {'completed': 0, 'total': 0})
            habit_completion[log.habit.name]['total'] += 1
            if log.is_completed:
                habit_completion[log.habit.name]['completed'] += 1
        
        for habit, stats in habit_completion.items():
            stats['rate'] = round(stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        
        return {
            'total_habits': len(habit_defs),
            'total_logs': len(habit_logs),
            'completion_rate': round(completion_rate),
            'habit_completion': habit_completion,
            'best_habit': max(habit_completion.items(), key=lambda x: x[1]['rate'])[0] if habit_completion else None,
            'recommendation': self._get_habits_recommendation(completion_rate)
        }
    
    def _get_habits_recommendation(self, completion_rate):
        """توصيات تحسين العادات"""
        if completion_rate < 50:
            return self._t('حاول البدء بعادة صغيرة واحدة فقط وركز على التزام بها يومياً', 'Start with one small habit and focus on daily commitment')
        elif completion_rate < 80:
            return self._t('أنت في الطريق الصحيح! استخدم التذكيرات لتحسين الالتزام', 'You are on the right track! Use reminders to improve consistency')
        return self._t('رائع! أنت ملتزم بعاداتك الصحية. حافظ على هذا المستوى', 'Great! You are committed to your healthy habits. Maintain this level')
    
    # ==========================================================================
    # 11. تحليل الأهداف
    # ==========================================================================
    
    def _analyze_goals_progress(self, data):
        """تحليل التقدم في الأهداف الصحية"""
        
        goals = data['goals']
        if not goals:
            return {'status': 'no_data', 'message': self._t('لا توجد أهداف صحية مسجلة', 'No health goals recorded')}
        
        goals_progress = []
        for goal in goals:
            progress = (goal.current_value / goal.target_value * 100) if goal.target_value else 0
            goals_progress.append({
                'title': goal.title,
                'target': goal.target_value,
                'current': goal.current_value,
                'unit': goal.unit,
                'progress': round(progress),
                'achieved': goal.is_achieved,
                'deadline': goal.target_date
            })
        
        return {
            'total_goals': len(goals),
            'achieved_goals': sum(1 for g in goals if g.is_achieved),
            'goals': goals_progress,
            'recommendation': self._get_goals_recommendation(goals_progress)
        }
    
    def _get_goals_recommendation(self, goals_progress):
        """توصيات للأهداف"""
        active_goals = [g for g in goals_progress if not g['achieved']]
        if not active_goals:
            return self._t('مبروك! حققت جميع أهدافك. حان وقت تحديد أهداف جديدة', 'Congratulations! You achieved all your goals. Time to set new ones')
        return self._t('راجع أهدافك أسبوعياً وقسمها إلى خطوات صغيرة قابلة للتحقيق', 'Review your goals weekly and break them into small achievable steps')
    
    # ==========================================================================
    # 12. تحليل المخاطر الصحية الكامل
    # ==========================================================================
    
    def _analyze_health_risks_complete(self, data):
        """تحليل كامل للمخاطر الصحية"""
        
        risks = []
        
        # مخاطر BMI
        if self.user_bmi:
            if self.user_bmi >= 30:
                risks.append({
                    'type': 'obesity',
                    'severity': 'high',
                    'condition': self._t('السمنة', 'Obesity'),
                    'message': self._t('السمنة تزيد خطر أمراض القلب والسكري والضغط', 'Obesity increases risk of heart disease, diabetes, and hypertension')
                })
            elif self.user_bmi < 18.5:
                risks.append({
                    'type': 'underweight',
                    'severity': 'medium',
                    'condition': self._t('نقص الوزن', 'Underweight'),
                    'message': self._t('نقص الوزن قد يؤثر على المناعة وكثافة العظام', 'Underweight may affect immunity and bone density')
                })
        
        # مخاطر ضغط الدم
        latest_health = data['health'][-1] if data['health'] else None
        if latest_health and latest_health.systolic_pressure:
            if latest_health.systolic_pressure > 140:
                risks.append({
                    'type': 'hypertension',
                    'severity': 'high',
                    'condition': self._t('ارتفاع ضغط الدم', 'High Blood Pressure'),
                    'message': self._t('ارتفاع الضغط يزيد خطر النوبات القلبية والسكتات الدماغية', 'High BP increases risk of heart attacks and strokes')
                })
        
        # مخاطر السكر
        if latest_health and latest_health.blood_glucose:
            glucose = float(latest_health.blood_glucose)
            if glucose > 140:
                risks.append({
                    'type': 'hyperglycemia',
                    'severity': 'high',
                    'condition': self._t('ارتفاع السكر', 'High Blood Sugar'),
                    'message': self._t('قد يشير إلى مقدمات السكري أو السكري', 'May indicate prediabetes or diabetes')
                })
        
        # مخاطر قلة النوم
        sleep_records = data['sleep']
        if sleep_records:
            avg_sleep = self._analyze_sleep_advanced(data).get('average_hours', 0)
            if avg_sleep < 6:
                risks.append({
                    'type': 'sleep_deprivation',
                    'severity': 'medium',
                    'condition': self._t('قلة النوم المزمنة', 'Chronic Sleep Deprivation'),
                    'message': self._t('قلة النوم تؤثر على الصحة النفسية والجسدية', 'Sleep deprivation affects mental and physical health')
                })
        
        # الأمراض المزمنة الموجودة
        for condition in self.chronic_conditions:
            risks.append({
                'type': 'chronic',
                'severity': 'medium',
                'condition': condition,
                'message': self._t(f'لديك {condition} - يوصى بالمتابعة الدورية', f'You have {condition} - regular follow-up recommended')
            })
        
        return {
            'risks': risks,
            'total_risks': len(risks),
            'high_risks': len([r for r in risks if r['severity'] == 'high']),
            'risk_level': 'high' if any(r['severity'] == 'high' for r in risks) else ('medium' if risks else 'low')
        }
    
    # ==========================================================================
    # 13. تحليل الأنماط باستخدام ML
    # ==========================================================================
    
    def _analyze_patterns_ml(self, data):
        """اكتشاف الأنماط باستخدام خوارزميات التعلم الآلي"""
        
        # تجهيز البيانات للتحليل
        df = self._prepare_dataframe_for_ml(data)
        if df is None or len(df) < 14:
            return {'status': 'insufficient_data'}
        
        patterns = []
        
        # 1. تجميع الأيام المتشابهة
        try:
            features = ['sleep_hours', 'mood_score', 'calories', 'activity_minutes']
            available = [f for f in features if f in df.columns]
            X = df[available].fillna(0)
            
            if len(X) >= 7:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                
                n_clusters = min(3, len(X))
                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                clusters = kmeans.fit_predict(X_scaled)
                
                for i in range(kmeans.n_clusters):
                    cluster_data = df.iloc[clusters == i]
                    if len(cluster_data) > 0:
                        patterns.append({
                            'name': self._t(f'نمط {i+1}', f'Pattern {i+1}'),
                            'description': self._describe_pattern(cluster_data),
                            'frequency': len(cluster_data),
                            'characteristics': {
                                'avg_sleep': round(cluster_data['sleep_hours'].mean(), 1),
                                'avg_mood': round(cluster_data['mood_score'].mean(), 1),
                                'avg_calories': round(cluster_data['calories'].mean()),
                                'avg_activity': round(cluster_data['activity_minutes'].mean(), 1)
                            }
                        })
        except Exception as e:
            pass
        
        # 2. اكتشاف الحالات الشاذة
        anomalies = []
        try:
            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            anomaly_pred = iso_forest.fit_predict(X_scaled) if 'X_scaled' in locals() else []
            for i, pred in enumerate(anomaly_pred):
                if pred == -1:
                    anomalies.append(df.index[i].strftime('%Y-%m-%d') if hasattr(df.index[i], 'strftime') else str(df.index[i]))
        except:
            pass
        
        # 3. الارتباطات
        correlations = {}
        if 'sleep_hours' in df and 'mood_score' in df:
            correlations['sleep_mood'] = round(df['sleep_hours'].corr(df['mood_score']), 2)
        if 'activity_minutes' in df and 'mood_score' in df:
            correlations['activity_mood'] = round(df['activity_minutes'].corr(df['mood_score']), 2)
        if 'calories' in df and 'weight_change' in df:
            correlations['calories_weight'] = round(df['calories'].corr(df['weight_change']), 2)
        
        return {
            'patterns': patterns,
            'anomalies_count': len(anomalies),
            'anomaly_dates': anomalies[:5],
            'correlations': correlations,
            'insights': self._generate_pattern_insights(correlations)
        }
    
    def _prepare_dataframe_for_ml(self, data):
        """تحضير DataFrame للتحليل"""
        import pandas as pd
        
        health_records = data['health']
        if not health_records:
            return None
        
        dates = pd.date_range(
            start=health_records[0].recorded_at.date(),
            end=timezone.now().date(),
            freq='D'
        )
        
        df = pd.DataFrame(index=dates)
        
        # إضافة الميزات الزمنية
        df['day_of_week'] = df.index.dayofweek
        df['month'] = df.index.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # إضافة البيانات
        for date in dates:
            date_str = date.strftime('%Y-%m-%d')
            day_stats = self._calculate_daily_stats_ml(data, date)
            for key, value in day_stats.items():
                df.loc[date, key] = value
        
        # إضافة الميزات المتقدمة
        if 'weight' in df.columns:
            df['weight_change'] = df['weight'].diff()
        if 'sleep_hours' in df.columns:
            df['sleep_7d_avg'] = df['sleep_hours'].rolling(7, min_periods=1).mean()
        if 'calories' in df.columns:
            df['calories_7d_avg'] = df['calories'].rolling(7, min_periods=1).mean()
        if 'activity_minutes' in df.columns:
            df['activity_7d_avg'] = df['activity_minutes'].rolling(7, min_periods=1).mean()
        
        return df
    
    def _calculate_daily_stats_ml(self, data, date):
        """حساب إحصائيات يومية للتحليل"""
        stats = {}
        
        # الوزن
        for h in data['health']:
            if h.recorded_at.date() == date and h.weight_kg:
                stats['weight'] = float(h.weight_kg)
                break
        
        # النوم
        sleep_hours = 0
        sleep_quality = 0
        sleep_count = 0
        for s in data['sleep']:
            if s.sleep_start.date() == date and s.sleep_end:
                hours = (s.sleep_end - s.sleep_start).seconds / 3600
                sleep_hours += hours
                sleep_quality += s.quality_rating if s.quality_rating else 3
                sleep_count += 1
        if sleep_count > 0:
            stats['sleep_hours'] = sleep_hours
            stats['sleep_quality'] = sleep_quality / sleep_count
        
        # المزاج
        for m in data['moods']:
            if m.entry_time.date() == date:
                mood_map = {'Excellent': 5, 'Good': 4, 'Neutral': 3, 'Stressed': 2, 'Anxious': 2, 'Sad': 1}
                stats['mood_score'] = mood_map.get(m.mood, 3)
                break
        
        # السعرات
        calories = 0
        for meal in data['meals']:
            if meal.meal_time.date() == date:
                calories += meal.total_calories or 0
        if calories > 0:
            stats['calories'] = calories
        
        # النشاط
        activity_minutes = 0
        for act in data['activities']:
            if act.start_time.date() == date:
                activity_minutes += act.duration_minutes or 0
        if activity_minutes > 0:
            stats['activity_minutes'] = activity_minutes
        
        # العادات
        habits_completed = 0
        for log in data['habit_logs']:
            if log.log_date == date and log.is_completed:
                habits_completed += 1
        if habits_completed > 0:
            stats['habits_completed'] = habits_completed
        
        return stats
    
    def _describe_pattern(self, cluster_data):
        """وصف النمط المكتشف"""
        sleep = cluster_data['sleep_hours'].mean()
        mood = cluster_data['mood_score'].mean()
        
        sleep_desc = self._t('نوم مثالي', 'Ideal sleep') if 7 <= sleep <= 9 else self._t('نوم غير منتظم', 'Irregular sleep')
        mood_desc = self._t('مزاج جيد', 'Good mood') if mood >= 3.5 else self._t('مزاج متغير', 'Variable mood')
        
        return f"{sleep_desc} • {mood_desc}"
    
    def _generate_pattern_insights(self, correlations):
        """توليد رؤى من الارتباطات"""
        insights = []
        
        if correlations.get('sleep_mood', 0) > 0.5:
            insights.append(self._t('نومك يؤثر إيجاباً على مزاجك - حافظ على نمط نومك', 'Your sleep positively affects your mood - maintain your sleep pattern'))
        elif correlations.get('activity_mood', 0) > 0.4:
            insights.append(self._t('النشاط البدني يحسن مزاجك - استمر في الحركة', 'Physical activity improves your mood - keep moving'))
        
        return insights
    
    # ==========================================================================
    # 14. التوقعات المستقبلية
    # ==========================================================================
    
    def _predict_future_trends(self, data):
        """التنبؤ بالاتجاهات المستقبلية"""
        
        predictions = {}
        
        # التنبؤ بالوزن
        weight_pred = self._predict_weight_with_ml(data)
        if weight_pred:
            predictions['weight'] = weight_pred
        
        return predictions
    
    def _predict_weight_with_ml(self, data):
        """التنبؤ بالوزن باستخدام ML"""
        
        df = self._prepare_dataframe_for_ml(data)
        if df is None or 'weight' not in df.columns or len(df) < 14:
            return None
        
        # تجهيز البيانات للتدريب
        feature_cols = ['day_of_week', 'is_weekend', 'sleep_hours', 'calories', 'activity_minutes']
        available = [c for c in feature_cols if c in df.columns]
        
        if len(available) < 2:
            return None
        
        X = df[available].fillna(0)[:-7]
        y = df['weight'][:-7]
        
        if len(X) < 7:
            return None
        
        # تدريب النموذج
        model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=3)
        model.fit(X, y)
        
        # التنبؤ بالأيام القادمة
        last_features = df[available].fillna(0).iloc[-7:]
        predictions = []
        
        for i in range(7):
            pred = model.predict(last_features.iloc[i:i+1])[0]
            predictions.append(round(pred, 1))
        
        current_weight = df['weight'].iloc[-1]
        
        return {
            'current': round(current_weight, 1),
            'predictions': predictions,
            'trend': 'زيادة' if predictions[-1] > current_weight else 'نقصان' if predictions[-1] < current_weight else 'ثبات',
            'confidence': round(model.score(X, y) * 100, 1) if hasattr(model, 'score') else 75
        }
    
    # ==========================================================================
    # 15. النتيجة الصحية الشاملة
    # ==========================================================================
    
    def _calculate_holistic_health_score(self, data):
        """حساب النتيجة الصحية الشاملة (0-100)"""
        
        score = 50  # أساس
        components = {}
        
        # مكون النوم (وزن 20)
        sleep_analysis = self._analyze_sleep_advanced(data)
        if sleep_analysis.get('sleep_score'):
            sleep_score = sleep_analysis['sleep_score'] * 0.2
            components['sleep'] = round(sleep_score, 1)
            score += sleep_score
        
        # مكون المزاج (وزن 20)
        mood_analysis = self._analyze_mood_advanced(data)
        if mood_analysis.get('average_mood_score'):
            mood_score = (mood_analysis['average_mood_score'] / 5) * 20
            components['mood'] = round(mood_score, 1)
            score += mood_score
        
        # مكون التغذية (وزن 20)
        nutrition_analysis = self._analyze_nutrition_advanced(data)
        if nutrition_analysis.get('average_daily_calories'):
            recommended = nutrition_analysis.get('recommended_calories', 2000)
            actual = nutrition_analysis['average_daily_calories']
            if recommended > 0:
                ratio = min(1, actual / recommended) if actual < recommended else min(1, recommended / actual)
                nutrition_score = ratio * 20
                components['nutrition'] = round(nutrition_score, 1)
                score += nutrition_score
        
        # مكون النشاط (وزن 20)
        activity_analysis = self._analyze_activity_advanced(data)
        if activity_analysis.get('average_daily_minutes'):
            daily_minutes = activity_analysis['average_daily_minutes']
            if daily_minutes >= 30:
                activity_score = 20
            elif daily_minutes >= 15:
                activity_score = 15
            elif daily_minutes >= 5:
                activity_score = 10
            else:
                activity_score = 5
            components['activity'] = activity_score
            score += activity_score
        
        # مكون العادات (وزن 20)
        habits_analysis = self._analyze_habits_advanced(data)
        if habits_analysis.get('completion_rate'):
            habits_score = (habits_analysis['completion_rate'] / 100) * 20
            components['habits'] = round(habits_score, 1)
            score += habits_score
        
        # تحديد التصنيف
        total_score = min(100, int(score))
        if total_score >= 80:
            category = 'excellent'
            category_text = self._t('ممتازة 🌟', 'Excellent 🌟')
        elif total_score >= 65:
            category = 'good'
            category_text = self._t('جيدة ✅', 'Good ✅')
        elif total_score >= 50:
            category = 'fair'
            category_text = self._t('متوسطة 📊', 'Fair 📊')
        else:
            category = 'poor'
            category_text = self._t('تحتاج تحسين ⚠️', 'Needs Improvement ⚠️')
        
        return {
            'total_score': total_score,
            'category': category,
            'category_text': category_text,
            'components': components
        }
    
    # ==========================================================================
    # 16. التوصيات المخصصة (الأهم)
    # ==========================================================================
    
    def _generate_personalized_recommendations(self, data):
        """
        توليد توصيات مخصصة بالكامل حسب حالة المستخدم
        تدمج جميع جوانب التحليل
        """
        
        recommendations = []
        
        # 1. توصيات الوزن و BMI
        weight_bmi = self._analyze_weight_bmi_advanced(data)
        if weight_bmi.get('weight_to_lose', 0) > 5:
            recommendations.append({
                'priority': 'high',
                'category': 'weight',
                'icon': '⚖️',
                'title': self._t('خسارة الوزن الصحية', 'Healthy Weight Loss'),
                'description': self._t(f'تحتاج لخسارة {weight_bmi["weight_to_lose"]} كجم للوصول للوزن المثالي', f'Need to lose {weight_bmi["weight_to_lose"]} kg to reach ideal weight'),
                'actions': [
                    self._t('قلل 300-500 سعرة حرارية يومياً', 'Reduce 300-500 calories daily'),
                    self._t('زد النشاط البدني إلى 30 دقيقة يومياً', 'Increase physical activity to 30 minutes daily'),
                    self._t('تناول البروتين مع كل وجبة لزيادة الشبع', 'Eat protein with every meal for satiety')
                ],
                'quick_tip': self._t('اشرب كوب ماء قبل كل وجبة', 'Drink a glass of water before each meal')
            })
        elif weight_bmi.get('weight_to_gain', 0) > 2:
            recommendations.append({
                'priority': 'high',
                'category': 'weight',
                'icon': '💪',
                'title': self._t('زيادة الوزن الصحي', 'Healthy Weight Gain'),
                'description': self._t(f'تحتاج لزيادة {weight_bmi["weight_to_gain"]} كجم للوصول للوزن المثالي', f'Need to gain {weight_bmi["weight_to_gain"]} kg to reach ideal weight'),
                'actions': [
                    self._t('أضف 300-500 سعرة حرارية يومياً', 'Add 300-500 calories daily'),
                    self._t('تناول وجبات متكررة (5-6 وجبات صغيرة)', 'Eat frequent meals (5-6 small meals)'),
                    self._t('مارس تمارين المقاومة لبناء العضلات', 'Practice resistance training to build muscle')
                ],
                'quick_tip': self._t('أضف المكسرات وزبدة الفول السوداني لوجباتك', 'Add nuts and peanut butter to your meals')
            })
        
        # 2. توصيات النوم
        sleep_analysis = self._analyze_sleep_advanced(data)
        for rec in sleep_analysis.get('recommendations', []):
            recommendations.append({
                'priority': 'high' if sleep_analysis.get('sleep_score', 100) < 50 else 'medium',
                'category': 'sleep',
                **rec
            })
        
        # 3. توصيات المزاج
        mood_analysis = self._analyze_mood_advanced(data)
        for rec in mood_analysis.get('recommendations', []):
            recommendations.append({
                'priority': 'high' if mood_analysis.get('average_mood_score', 3) < 2.5 else 'medium',
                'category': 'mood',
                **rec
            })
        
        # 4. توصيات التغذية
        nutrition_analysis = self._analyze_nutrition_advanced(data)
        for rec in nutrition_analysis.get('recommendations', []):
            recommendations.append({
                'priority': 'medium',
                'category': 'nutrition',
                **rec
            })
        
        # 5. توصيات النشاط
        activity_analysis = self._analyze_activity_advanced(data)
        for rec in activity_analysis.get('recommendations', []):
            recommendations.append({
                'priority': 'high' if activity_analysis.get('average_daily_minutes', 0) < 15 else 'medium',
                'category': 'activity',
                **rec
            })
        
        # 6. توصيات العادات
        habits_analysis = self._analyze_habits_advanced(data)
        if habits_analysis.get('completion_rate', 100) < 70:
            recommendations.append({
                'priority': 'medium',
                'category': 'habits',
                'icon': '📅',
                'title': self._t('تحسين الالتزام بالعادات', 'Improve Habit Consistency'),
                'description': habits_analysis.get('recommendation', ''),
                'actions': [
                    self._t('استخدم التذكيرات اليومية', 'Use daily reminders'),
                    self._t('تتبع تقدمك يومياً', 'Track your progress daily'),
                    self._t('كافئ نفسك عند تحقيق التقدم', 'Reward yourself for progress')
                ]
            })
        
        # 7. توصيات المخاطر الصحية
        risks_analysis = self._analyze_health_risks_complete(data)
        for risk in risks_analysis.get('risks', [])[:3]:
            if risk['severity'] == 'high':
                recommendations.append({
                    'priority': 'urgent',
                    'category': 'risk',
                    'icon': '⚠️',
                    'title': self._t('تنبيه صحي: {condition}', 'Health Alert: {condition}', condition=risk['condition']),
                    'description': risk['message'],
                    'actions': [
                        self._t('استشر طبيبك للمتابعة', 'Consult your doctor for follow-up'),
                        self._t('راقب الأعراض بانتظام', 'Monitor symptoms regularly')
                    ]
                })
        
        # 8. توصيات العمر والمرحلة العمرية
        age_category = self._get_age_category()
        if age_category == 'senior' or age_category == 'elderly':
            recommendations.append({
                'priority': 'medium',
                'category': 'age_specific',
                'icon': '🩺',
                'title': self._t('نصائح لكبار السن', 'Senior Health Tips'),
                'description': self._t('اهتم بفحوصاتك الدورية وحافظ على نشاطك', 'Take care of regular checkups and maintain activity'),
                'actions': [
                    self._t('فحص ضغط الدم والكوليسترول بانتظام', 'Regular blood pressure and cholesterol checks'),
                    self._t('تمارين التوازن لتجنب السقوط', 'Balance exercises to prevent falls'),
                    self._t('تناول الكالسيوم وفيتامين د', 'Take calcium and vitamin D')
                ]
            })
        
        # 9. توصيات الأمراض المزمنة
        for condition in self.chronic_conditions:
            condition_lower = condition.lower()
            if 'diabetes' in condition_lower or 'سكري' in condition_lower:
                recommendations.append({
                    'priority': 'high',
                    'category': 'chronic_condition',
                    'icon': '🩸',
                    'title': self._t('إدارة السكري', 'Diabetes Management'),
                    'description': self._t('راقب سكر الدم بانتظام واتبع نظاماً غذائياً مناسباً', 'Monitor blood sugar regularly and follow an appropriate diet'),
                    'actions': [
                        self._t('تجنب السكريات البسيطة', 'Avoid simple sugars'),
                        self._t('مارس المشي لمدة 30 دقيقة يومياً', 'Walk 30 minutes daily'),
                        self._t('تناول وجبات صغيرة ومتكررة', 'Eat small, frequent meals')
                    ]
                })
            elif 'pressure' in condition_lower or 'ضغط' in condition_lower:
                recommendations.append({
                    'priority': 'high',
                    'category': 'chronic_condition',
                    'icon': '❤️',
                    'title': self._t('إدارة ضغط الدم', 'Blood Pressure Management'),
                    'description': self._t('حافظ على ضغط دمك في النطاق الطبيعي', 'Keep your blood pressure in normal range'),
                    'actions': [
                        self._t('قلل الملح في الطعام', 'Reduce salt in food'),
                        self._t('زد البوتاسيوم (موز، خضروات)', 'Increase potassium (bananas, vegetables)'),
                        self._t('مارس تمارين الاسترخاء', 'Practice relaxation exercises')
                    ]
                })
        
        # ترتيب حسب الأولوية
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 4))
        
        return recommendations[:10]  # أقصى 10 توصيات
    
    # ==========================================================================
    # 17. الملخص التنفيذي
    # ==========================================================================
    
    def _generate_executive_summary(self, data):
        """توليد ملخص تنفيذي شامل"""
        
        health_score = self._calculate_holistic_health_score(data)
        risks = self._analyze_health_risks_complete(data)
        weight_bmi = self._analyze_weight_bmi_advanced(data)
        sleep_analysis = self._analyze_sleep_advanced(data)
        mood_analysis = self._analyze_mood_advanced(data)
        activity_analysis = self._analyze_activity_advanced(data)
        
        if self.is_arabic:
            summary = f"""📊 **ملخص صحتك الشامل**

👤 **الملف الشخصي**: {self.user_age} سنة، {self._get_bmi_category_text()} (BMI {self.user_bmi})
⚖️ **الوزن**: {weight_bmi.get('current_weight', 'غير متوفر')} كجم
🌙 **النوم**: {sleep_analysis.get('average_hours', 0)} ساعات ليلاً، جودة {sleep_analysis.get('average_quality', 0)}/5
😊 **المزاج**: {mood_analysis.get('mood_level', 'غير متوفر')} ({mood_analysis.get('average_mood_score', 0)}/5)
🏃 **النشاط**: {activity_analysis.get('average_daily_minutes', 0)} دقيقة يومياً
🎯 **النتيجة الصحية**: {health_score.get('total_score', 0)}/100 ({health_score.get('category_text', '')})

⚠️ **المخاطر**: {risks.get('total_risks', 0)} عامل خطر ({risks.get('high_risks', 0)} عالي)
💡 **توصيات عاجلة**: {len([r for r in self._generate_personalized_recommendations(data) if r.get('priority') in ['urgent', 'high']])} توصية ذات أولوية
"""
        else:
            summary = f"""📊 **Your Comprehensive Health Summary**

👤 **Profile**: {self.user_age} years, {self._get_bmi_category_text()} (BMI {self.user_bmi})
⚖️ **Weight**: {weight_bmi.get('current_weight', 'N/A')} kg
🌙 **Sleep**: {sleep_analysis.get('average_hours', 0)} hours nightly, quality {sleep_analysis.get('average_quality', 0)}/5
😊 **Mood**: {mood_analysis.get('mood_level', 'N/A')} ({mood_analysis.get('average_mood_score', 0)}/5)
🏃 **Activity**: {activity_analysis.get('average_daily_minutes', 0)} minutes daily
🎯 **Health Score**: {health_score.get('total_score', 0)}/100 ({health_score.get('category_text', '')})

⚠️ **Risks**: {risks.get('total_risks', 0)} risk factors ({risks.get('high_risks', 0)} high)
💡 **Urgent Recommendations**: {len([r for r in self._generate_personalized_recommendations(data) if r.get('priority') in ['urgent', 'high']])} priority recommendations
"""
        
        return summary


# ==============================================================================
# دالة مساعدة للاستخدام السريع
# ==============================================================================

def get_comprehensive_health_analytics(user, language='ar'):
    """دالة مساعدة للحصول على التحليلات الصحية الشاملة"""
    engine = ComprehensiveHealthAnalytics(user, language=language)
    return engine.get_complete_analysis()
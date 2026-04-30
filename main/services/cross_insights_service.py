"""
محرك الذكاء الاصطناعي للتحليلات الصحية المتقاطعة - النسخة المتطورة
Advanced Cross-Data Analysis Engine with Deep Health Analytics
"""
from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, F, Min, Max
from django.db.models.functions import TruncDate, ExtractDay, ExtractWeek
from main.models import (
    HealthStatus, PhysicalActivity, Sleep, 
    MoodEntry, Meal, HabitLog, CustomUser
)
import math


class HealthInsightsEngine:
    """
    محرك متقدم لتحليل البيانات الصحية وإيجاد العلاقات الخفية
    Advanced engine for analyzing health data with deep personalization
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.today = timezone.now().date()
        self.week_ago = self.today - timedelta(days=7)
        self.month_ago = self.today - timedelta(days=30)
        self.three_months_ago = self.today - timedelta(days=90)
        self.is_arabic = language == 'ar'
        
        # ✅ جلب البيانات الشخصية للمستخدم
        self.user_profile = self._get_user_profile()
        self.user_age = self._calculate_age()
        self.user_bmi = None
        self.user_body_fat = None
        
    def _get_user_profile(self):
        """جلب الملف الشخصي للمستخدم مع جميع البيانات"""
        try:
            if hasattr(self.user, 'profile'):
                return self.user.profile
            return None
        except:
            return None
    
    def _calculate_age(self):
        """حساب العمر من تاريخ الميلاد"""
        try:
            if self.user_profile and self.user_profile.birth_date:
                today = timezone.now().date()
                return today.year - self.user_profile.birth_date.year - (
                    (today.month, today.day) < (self.user_profile.birth_date.month, self.user_profile.birth_date.day)
                )
        except:
            pass
        return None
    
    def _calculate_bmi(self, weight_kg, height_cm):
        """حساب مؤشر كتلة الجسم BMI"""
        if weight_kg and height_cm and height_cm > 0:
            height_m = height_cm / 100
            return round(weight_kg / (height_m ** 2), 1)
        return None
    
    def _calculate_body_fat_percentage(self, bmi, age, gender):
        """تقدير نسبة الدهون في الجسم"""
        if not bmi or not age:
            return None
        
        # صيغة تقريبية لنسبة الدهون
        if gender == 'male':
            body_fat = (1.20 * bmi) + (0.23 * age) - 16.2
        elif gender == 'female':
            body_fat = (1.20 * bmi) + (0.23 * age) - 5.4
        else:
            body_fat = (1.20 * bmi) + (0.23 * age) - 10.8
        
        return round(max(5, min(50, body_fat)), 1)
    
    def _calculate_bmr_precise(self, weight_kg, height_cm, age, gender):
        """حساب معدل الأيض الأساسي BMR باستخدام صيغة Mifflin-St Jeor"""
        if not all([weight_kg, height_cm, age, gender]):
            return None
        
        if gender == 'male':
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
        elif gender == 'female':
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
        else:
            # متوسط للجنسين
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 78
        
        return round(bmr)
    
    def _get_activity_multiplier(self, activity_level):
        """معامل النشاط لحساب السعرات اليومية"""
        multipliers = {
            'sedentary': 1.2,      # قليل الحركة
            'light': 1.375,        # نشاط خفيف
            'moderate': 1.55,      # نشاط متوسط
            'active': 1.725,       # نشاط عالي
            'very_active': 1.9,    # نشاط شديد
        }
        return multipliers.get(activity_level, 1.375)
    
    def _get_bmi_category(self, bmi):
        """تصنيف BMI مع التوصيات"""
        if bmi < 18.5:
            return {
                'category': 'نقص الوزن' if self.is_arabic else 'Underweight',
                'severity': 'warning',
                'color': 'orange',
                'recommendation_ar': 'تحتاج لزيادة السعرات الحرارية مع التركيز على البروتين والدهون الصحية',
                'recommendation_en': 'Need to increase calories with focus on protein and healthy fats',
                'risk_level': 'moderate'
            }
        elif 18.5 <= bmi < 25:
            return {
                'category': 'وزن طبيعي' if self.is_arabic else 'Normal weight',
                'severity': 'good',
                'color': 'green',
                'recommendation_ar': 'حافظ على وزنك الصحي واستمر في نمط الحياة المتوازن',
                'recommendation_en': 'Maintain your healthy weight and continue balanced lifestyle',
                'risk_level': 'low'
            }
        elif 25 <= bmi < 30:
            return {
                'category': 'زيادة وزن' if self.is_arabic else 'Overweight',
                'severity': 'warning',
                'color': 'orange',
                'recommendation_ar': 'انصح بتقليل السعرات الحرارية وزيادة النشاط البدني',
                'recommendation_en': 'Recommend reducing calories and increasing physical activity',
                'risk_level': 'moderate'
            }
        elif 30 <= bmi < 35:
            return {
                'category': 'سمنة درجة أولى' if self.is_arabic else 'Obesity Class I',
                'severity': 'high',
                'color': 'red',
                'recommendation_ar': 'يُنصح بمراجعة أخصائي تغذية وبرنامج رياضي مكثف',
                'recommendation_en': 'Consult a nutritionist and follow an intensive exercise program',
                'risk_level': 'high'
            }
        elif 35 <= bmi < 40:
            return {
                'category': 'سمنة درجة ثانية' if self.is_arabic else 'Obesity Class II',
                'severity': 'critical',
                'color': 'darkred',
                'recommendation_ar': 'حالة صحية تتطلب تدخلاً طبياً عاجلاً ونظاماً صارماً',
                'recommendation_en': 'Health condition requiring urgent medical intervention',
                'risk_level': 'critical'
            }
        else:
            return {
                'category': 'سمنة مفرطة' if self.is_arabic else 'Extreme Obesity',
                'severity': 'critical',
                'color': 'darkred',
                'recommendation_ar': 'حالة خطيرة جداً، استشارة طبية فورية ضرورية',
                'recommendation_en': 'Extremely serious, immediate medical consultation required',
                'risk_level': 'critical'
            }
    
    def _t(self, ar_text, en_text, **kwargs):
        """ترجمة النصوص حسب اللغة المحددة"""
        text = ar_text if self.is_arabic else en_text
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text
    
    def analyze_all(self):
        """تحليل جميع الجوانب الصحية وإرجاع توصيات ذكية"""
        return {
            'user_profile_analysis': self.analyze_user_profile(),
            'vital_signs_analysis': self.analyze_vital_signs(),
            'bmi_deep_analysis': self.analyze_bmi_deep(),
            'body_composition_analysis': self.analyze_body_composition(),
            'metabolic_analysis': self.analyze_metabolic_health(),
            'activity_nutrition_correlation': self.analyze_activity_nutrition(),
            'sleep_mood_correlation': self.analyze_sleep_mood(),
            'weight_trend_analysis': self.analyze_weight_trends(),
            'blood_pressure_insights': self.analyze_blood_pressure(),
            'glucose_risk_assessment': self.analyze_glucose_risks(),
            'energy_consumption_alert': self.analyze_energy_consumption(),
            'pulse_pressure_analysis': self.analyze_pulse_pressure(),
            'pre_exercise_recommendation': self.analyze_pre_exercise_risk(),
            'age_related_risks': self.analyze_age_related_risks(),
            'lifestyle_score': self.calculate_lifestyle_score(),
            'personalized_recommendations': self.generate_personalized_recommendations(),
            'predictive_alerts': self.generate_predictive_alerts(),
            'health_goals_suggestions': self.suggest_health_goals(),
        }
    
    def analyze_user_profile(self):
        """تحليل الملف الشخصي للمستخدم"""
        profile_data = {
            'age': self.user_age,
            'gender': self.user_profile.gender if self.user_profile else None,
            'height_cm': self.user_profile.height_cm if self.user_profile else None,
            'occupation': self.user_profile.occupation if self.user_profile else None,
            'activity_level': self.user_profile.activity_level if self.user_profile else None,
            'smoking': self.user_profile.smoking if self.user_profile else None,
            'chronic_diseases': [],
        }
        
        # جلب الأمراض المزمنة
        if hasattr(self.user, 'chronic_conditions'):
            profile_data['chronic_diseases'] = list(self.user.chronic_conditions.values_list('name', flat=True))
        
        # تحليل المخاطر حسب العمر
        age_risks = []
        if self.user_age:
            if self.user_age < 18:
                age_risks.append({
                    'risk': 'مراهق',
                    'advice_ar': 'ركز على النمو الصحي والتغذية المتوازنة',
                    'advice_en': 'Focus on healthy growth and balanced nutrition'
                })
            elif 18 <= self.user_age < 30:
                age_risks.append({
                    'risk': 'شاب',
                    'advice_ar': 'بناء عادات صحية تدوم مدى الحياة',
                    'advice_en': 'Build lifelong healthy habits'
                })
            elif 30 <= self.user_age < 50:
                age_risks.append({
                    'risk': 'متوسط العمر',
                    'advice_ar': 'مراقبة الضغط والسكر والكوليسترول',
                    'advice_en': 'Monitor blood pressure, sugar, and cholesterol'
                })
            elif 50 <= self.user_age < 70:
                age_risks.append({
                    'risk': 'كبار السن',
                    'advice_ar': 'فحوصات دورية شاملة والحفاظ على النشاط',
                    'advice_en': 'Regular comprehensive checkups and maintain activity'
                })
            else:
                age_risks.append({
                    'risk': 'متقدم في السن',
                    'advice_ar': 'رعاية صحية مكثفة ومتابعة دائمة',
                    'advice_en': 'Intensive healthcare and constant monitoring'
                })
        
        # تحليل المخاطر حسب الوظيفة
        occupation_risks = []
        if profile_data['occupation']:
            sedentary_jobs = ['office', 'programmer', 'accountant', 'teacher', 'admin']
            active_jobs = ['construction', 'nurse', 'athlete', 'trainer']
            
            if any(job in profile_data['occupation'].lower() for job in sedentary_jobs):
                occupation_risks.append({
                    'risk': 'عمل مكتبي',
                    'advice_ar': 'خذ فترات راحة للحركة كل ساعة، تمرن بعد العمل',
                    'advice_en': 'Take movement breaks every hour, exercise after work'
                })
        
        return {
            'profile': profile_data,
            'age_risks': age_risks,
            'occupation_risks': occupation_risks,
            'complete_profile': bool(profile_data['height_cm'] and profile_data['gender'] and self.user_age),
            'missing_data': self._get_missing_profile_fields(profile_data)
        }
    
    def _get_missing_profile_fields(self, profile_data):
        """تحديد البيانات الناقصة في الملف الشخصي"""
        missing = []
        if not profile_data['height_cm']:
            missing.append('الطول' if self.is_arabic else 'height')
        if not profile_data['gender']:
            missing.append('الجنس' if self.is_arabic else 'gender')
        if not self.user_age:
            missing.append('تاريخ الميلاد' if self.is_arabic else 'birth date')
        if not profile_data['activity_level']:
            missing.append('مستوى النشاط' if self.is_arabic else 'activity level')
        return missing
    
    def analyze_bmi_deep(self):
        """تحليل عميق لمؤشر كتلة الجسم"""
        latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
        
        if not latest or not latest.weight_kg:
            return {'status': 'insufficient_data', 'message': self._t('لا توجد بيانات وزن كافية', 'Insufficient weight data')}
        
        weight = float(latest.weight_kg)
        height_cm = self.user_profile.height_cm if self.user_profile else None
        
        if not height_cm:
            return {'status': 'missing_height', 'message': self._t('الطول غير مسجل، يرجى إضافته للحصول على تحليل دقيق', 'Height not recorded, please add for accurate analysis')}
        
        # حساب BMI
        self.user_bmi = self._calculate_bmi(weight, height_cm)
        bmi_category = self._get_bmi_category(self.user_bmi)
        
        # حساب الوزن المثالي
        ideal_weight_min = 18.5 * ((height_cm / 100) ** 2)
        ideal_weight_max = 24.9 * ((height_cm / 100) ** 2)
        ideal_weight = round((ideal_weight_min + ideal_weight_max) / 2, 1)
        weight_to_lose = weight - ideal_weight_max if weight > ideal_weight_max else 0
        weight_to_gain = ideal_weight_min - weight if weight < ideal_weight_min else 0
        
        # نطاق الوزن الصحي حسب الجنس
        if self.user_profile and self.user_profile.gender == 'female':
            healthy_range = self._t('50-70 كجم للنساء', '50-70 kg for women')
        else:
            healthy_range = self._t('60-80 كجم للرجال', '60-80 kg for men')
        
        return {
            'bmi': self.user_bmi,
            'category': bmi_category['category'],
            'severity': bmi_category['severity'],
            'color': bmi_category['color'],
            'recommendation': bmi_category['recommendation_ar' if self.is_arabic else 'recommendation_en'],
            'risk_level': bmi_category['risk_level'],
            'ideal_weight': ideal_weight,
            'weight_to_lose': round(weight_to_lose, 1),
            'weight_to_gain': round(weight_to_gain, 1),
            'current_weight': weight,
            'height_cm': height_cm,
            'healthy_range': healthy_range,
            'time_to_goal': self._estimate_time_to_goal(weight_to_lose, weight_to_gain),
        }
    
    def _estimate_time_to_goal(self, weight_to_lose, weight_to_gain):
        """تقدير الوقت اللازم للوصول للوزن المثالي"""
        if weight_to_lose > 0:
            # فقدان 0.5 كجم أسبوعياً هو المعدل الصحي
            weeks = weight_to_lose / 0.5
            return {
                'action': 'lose',
                'weeks': round(weeks),
                'message_ar': f'تحتاج حوالي {round(weeks)} أسبوعاً لخسارة {weight_to_lose} كجم بمعدل 0.5 كجم أسبوعياً',
                'message_en': f'Need about {round(weeks)} weeks to lose {weight_to_lose} kg at 0.5 kg per week'
            }
        elif weight_to_gain > 0:
            weeks = weight_to_gain / 0.3
            return {
                'action': 'gain',
                'weeks': round(weeks),
                'message_ar': f'تحتاج حوالي {round(weeks)} أسبوعاً لاكتساب {weight_to_gain} كجم بمعدل 0.3 كجم أسبوعياً',
                'message_en': f'Need about {round(weeks)} weeks to gain {weight_to_gain} kg at 0.3 kg per week'
            }
        return {'action': 'maintain', 'message_ar': 'أنت في وزن صحي، حافظ عليه', 'message_en': 'You are at healthy weight, maintain it'}
    
    def analyze_body_composition(self):
        """تحليل تكوين الجسم"""
        if not self.user_bmi:
            latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
            if latest and latest.weight_kg and self.user_profile and self.user_profile.height_cm:
                self.user_bmi = self._calculate_bmi(float(latest.weight_kg), self.user_profile.height_cm)
        
        if not self.user_bmi or not self.user_age:
            return {'status': 'insufficient_data'}
        
        gender = self.user_profile.gender if self.user_profile else 'unknown'
        
        # حساب نسبة الدهون
        body_fat = self._calculate_body_fat_percentage(self.user_bmi, self.user_age, gender)
        
        # تصنيف نسبة الدهون
        if gender == 'male':
            if body_fat < 8:
                category = 'رياضي محترف' if self.is_arabic else 'Athlete'
            elif body_fat < 15:
                category = 'رياضي' if self.is_arabic else 'Fit'
            elif body_fat < 22:
                category = 'طبيعي' if self.is_arabic else 'Normal'
            elif body_fat < 28:
                category = 'مرتفع' if self.is_arabic else 'High'
            else:
                category = 'خطير' if self.is_arabic else 'Dangerous'
        else:
            if body_fat < 14:
                category = 'رياضي محترف' if self.is_arabic else 'Athlete'
            elif body_fat < 21:
                category = 'رياضي' if self.is_arabic else 'Fit'
            elif body_fat < 28:
                category = 'طبيعي' if self.is_arabic else 'Normal'
            elif body_fat < 33:
                category = 'مرتفع' if self.is_arabic else 'High'
            else:
                category = 'خطير' if self.is_arabic else 'Dangerous'
        
        # كتلة العضلات المقدرة
        lean_mass = 100 - body_fat
        estimated_muscle = round((lean_mass / 100) * 70, 1)  # تقدير تقريبي
        
        return {
            'body_fat_percentage': body_fat,
            'body_fat_category': category,
            'estimated_muscle_mass_kg': estimated_muscle,
            'muscle_category': 'جيد' if lean_mass > 70 else 'يحتاج تحسين',
            'recommendation': self._get_body_composition_recommendation(category, gender),
        }
    
    def _get_body_composition_recommendation(self, category, gender):
        """توصيات تحسين تكوين الجسم"""
        if category in ['رياضي محترف', 'رياضي', 'Athlete', 'Fit']:
            return self._t('ممتاز! استمر في تمارين المقاومة للحفاظ على الكتلة العضلية', 'Excellent! Continue resistance training to maintain muscle mass')
        elif category == 'طبيعي' or category == 'Normal':
            return self._t('جيد. حاول زيادة تمارين القوة لتحسين نسبة الدهون للعضلات', 'Good. Try to increase strength training to improve fat-to-muscle ratio')
        elif category == 'مرتفع' or category == 'High':
            return self._t('يُنصح بزيادة النشاط الهوائي وتمارين المقاومة لتقليل الدهون', 'Recommended to increase aerobic activity and resistance training to reduce fat')
        else:
            return self._t('حالة تستدعي التدخل الطبي والرياضي الفوري', 'Condition requiring immediate medical and exercise intervention')
    
    def analyze_metabolic_health(self):
        """تحليل الصحة الأيضية"""
        latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
        
        if not latest:
            return {'status': 'insufficient_data'}
        
        # حساب BMR الدقيق
        weight = float(latest.weight_kg) if latest.weight_kg else None
        height_cm = self.user_profile.height_cm if self.user_profile else None
        gender = self.user_profile.gender if self.user_profile else 'unknown'
        
        bmr = None
        if all([weight, height_cm, self.user_age, gender]):
            bmr = self._calculate_bmr_precise(weight, height_cm, self.user_age, gender)
        
        # حساب TDEE (إجمالي السعرات اليومية)
        activity_level = self.user_profile.activity_level if self.user_profile else 'moderate'
        multiplier = self._get_activity_multiplier(activity_level)
        tdee = bmr * multiplier if bmr else None
        
        # مقارنة مع السعرات المتناولة فعلياً
        today = timezone.now().date()
        today_calories = Meal.objects.filter(user=self.user, meal_time__date=today).aggregate(Sum('total_calories'))['total_calories__sum'] or 0
        
        return {
            'bmr': bmr,
            'tdee': round(tdee) if tdee else None,
            'activity_multiplier': multiplier,
            'calorie_status': 'excess' if today_calories > (tdee or 0) else 'deficit' if today_calories < (tdee or 0) else 'maintenance',
            'calorie_diff': today_calories - round(tdee) if tdee else 0,
            'metabolic_rate_category': self._get_metabolic_category(bmr, weight) if bmr else None,
        }
    
    def _get_metabolic_category(self, bmr, weight):
        """تصنيف معدل الأيض"""
        bmr_per_kg = bmr / weight if weight else 0
        if bmr_per_kg > 25:
            return 'معدل حرق عالي' if self.is_arabic else 'High metabolism'
        elif bmr_per_kg > 20:
            return 'معدل حرق طبيعي' if self.is_arabic else 'Normal metabolism'
        else:
            return 'معدل حرق منخفض' if self.is_arabic else 'Low metabolism'
    
    def analyze_age_related_risks(self):
        """تحليل المخاطر المرتبطة بالعمر"""
        if not self.user_age:
            return {'status': 'age_not_available'}
        
        risks = []
        
        # مخاطر حسب العمر
        if self.user_age >= 40:
            risks.append({
                'condition': 'ضغط الدم' if self.is_arabic else 'High Blood Pressure',
                'risk': 'مرتفع' if self.is_arabic else 'High',
                'check_frequency': 'كل 6 أشهر' if self.is_arabic else 'Every 6 months'
            })
        
        if self.user_age >= 45:
            risks.append({
                'condition': 'السكري' if self.is_arabic else 'Diabetes',
                'risk': 'متوسط' if self.is_arabic else 'Moderate',
                'check_frequency': 'سنوياً' if self.is_arabic else 'Annually'
            })
        
        if self.user_age >= 50:
            risks.append({
                'condition': 'الكوليسترول' if self.is_arabic else 'Cholesterol',
                'risk': 'مرتفع' if self.is_arabic else 'High',
                'check_frequency': 'كل 6 أشهر' if self.is_arabic else 'Every 6 months'
            })
        
        if self.user_profile and self.user_profile.smoking:
            risks.append({
                'condition': 'أمراض القلب والرئة' if self.is_arabic else 'Heart & Lung Disease',
                'risk': 'مرتفع جداً' if self.is_arabic else 'Very High',
                'check_frequency': 'كل 3 أشهر' if self.is_arabic else 'Every 3 months'
            })
        
        return {
            'age': self.user_age,
            'risks': risks,
            'screening_recommendations': self._get_screening_recommendations(),
            'preventive_measures': self._get_preventive_measures(),
        }
    
    def _get_screening_recommendations(self):
        """توصيات الفحوصات الدورية"""
        recommendations = []
        
        if not self.user_age:
            return recommendations
        
        if self.user_age >= 20:
            recommendations.append(self._t('فحص ضغط الدم كل سنتين', 'Blood pressure check every 2 years'))
        if self.user_age >= 30:
            recommendations.append(self._t('فحص الكوليسترول كل 5 سنوات', 'Cholesterol check every 5 years'))
        if self.user_age >= 35 and self.user_profile and self.user_profile.gender == 'female':
            recommendations.append(self._t('فحص الثدي (ماموغرام) سنوياً', 'Annual mammogram'))
        if self.user_age >= 40:
            recommendations.append(self._t('فحص السكر كل 3 سنوات', 'Blood sugar check every 3 years'))
        if self.user_age >= 50:
            recommendations.append(self._t('فحص القولون كل 10 سنوات', 'Colonoscopy every 10 years'))
        
        return recommendations
    
    def _get_preventive_measures(self):
        """الإجراءات الوقائية حسب العمر"""
        measures = []
        
        if self.user_age:
            if self.user_age < 30:
                measures.append(self._t('بناء عادات صحية مبكرة', 'Build early healthy habits'))
            elif self.user_age < 50:
                measures.append(self._t('مراقبة العلامات الحيوية وتعديل نمط الحياة', 'Monitor vital signs and adjust lifestyle'))
            else:
                measures.append(self._t('فحوصات دورية شاملة والحفاظ على النشاط', 'Comprehensive regular checkups and maintain activity'))
        
        if self.user_profile and self.user_profile.smoking:
            measures.append(self._t('برنامج للإقلاع عن التدخين', 'Smoking cessation program'))
        
        return measures
    
    def calculate_lifestyle_score(self):
        """حساب درجة نمط الحياة الصحية (0-100)"""
        score = 70  # درجة أساسية
        details = []
        
        # تحليل النشاط البدني
        weekly_activities = PhysicalActivity.objects.filter(
            user=self.user, start_time__date__gte=self.week_ago
        )
        total_weekly_minutes = weekly_activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        
        if total_weekly_minutes >= 150:
            score += 15
            details.append(self._t('✅ نشاط ممتاز: أكثر من 150 دقيقة أسبوعياً', 'Excellent activity: over 150 minutes weekly'))
        elif total_weekly_minutes >= 75:
            score += 8
            details.append(self._t('⚠️ نشاط جيد: يوصى بزيادته إلى 150 دقيقة', 'Good activity: recommended to increase to 150 minutes'))
        else:
            score -= 10
            details.append(self._t('⚠️ نشاط قليل: يجب زيادة النشاط البدني', 'Low activity: need to increase physical activity'))
        
        # تحليل النوم
        sleeps = Sleep.objects.filter(user=self.user, sleep_start__date__gte=self.week_ago)
        if sleeps.exists():
            total_sleep = 0
            for sleep in sleeps:
                if sleep.sleep_start and sleep.sleep_end:
                    duration = (sleep.sleep_end - sleep.sleep_start).seconds / 3600
                    total_sleep += duration
            avg_sleep = total_sleep / sleeps.count()
            
            if 7 <= avg_sleep <= 9:
                score += 10
                details.append(self._t('✅ نوم مثالي: 7-9 ساعات ليلاً', 'Perfect sleep: 7-9 hours nightly'))
            elif 6 <= avg_sleep < 7 or 9 < avg_sleep <= 10:
                score += 5
                details.append(self._t('⚠️ نوم مقبول: حاول تحسين جودة النوم', 'Acceptable sleep: try to improve sleep quality'))
            else:
                score -= 10
                details.append(self._t('⚠️ نوم غير صحي: يوصى بتنظيم مواعيد النوم', 'Unhealthy sleep: recommended to regulate sleep schedule'))
        
        # تحليل التغذية
        meals = Meal.objects.filter(user=self.user, meal_time__date=self.today)
        if meals.count() >= 3:
            score += 5
            details.append(self._t('✅ منتظم في الوجبات', 'Regular meals'))
        
        # تحليل الحالة المزاجية
        mood = MoodEntry.objects.filter(user=self.user).order_by('-entry_time').first()
        if mood:
            good_moods = ['happy', 'excited', 'good', 'energetic']
            if mood.mood in good_moods:
                score += 5
                details.append(self._t('✅ مزاج إيجابي يؤثر صحياً على الجسم', 'Positive mood positively affects health'))
        
        score = max(0, min(100, score))
        
        return {
            'score': score,
            'category': self._get_lifestyle_category(score),
            'details': details,
            'recommendations': self._get_lifestyle_recommendations(score, details),
        }
    
    def _get_lifestyle_category(self, score):
        """تصنيف نمط الحياة"""
        if score >= 80:
            return self._t('ممتاز 🌟', 'Excellent 🌟')
        elif score >= 60:
            return self._t('جيد 👍', 'Good 👍')
        elif score >= 40:
            return self._t('مقبول 📊', 'Fair 📊')
        else:
            return self._t('يحتاج تحسين ⚠️', 'Needs improvement ⚠️')
    
    def _get_lifestyle_recommendations(self, score, details):
        """توصيات تحسين نمط الحياة"""
        recommendations = []
        
        if 'نشاط قليل' in str(details):
            recommendations.append(self._t('🏃 ابدأ بالمشي 20 دقيقة يومياً', '🏃 Start with 20 minutes of walking daily'))
        
        if 'نوم غير صحي' in str(details):
            recommendations.append(self._t('😴 ثبّت موعد النوم والاستيقاظ يومياً', '😴 Set a consistent sleep and wake time daily'))
        
        if 'منتظم في الوجبات' not in str(details):
            recommendations.append(self._t('🥗 نظّم وجباتك الثلاث الرئيسية يومياً', '🥗 Organize your three main meals daily'))
        
        if score < 50:
            recommendations.append(self._t('📱 استخدم تذكيرات يومية للعادات الصحية', '📱 Use daily reminders for healthy habits'))
        
        return recommendations
    
    def generate_personalized_recommendations(self):
        """توليد توصيات شخصية متكاملة"""
        recommendations = []
        
        # توصيات الوزن
        bmi_analysis = self.analyze_bmi_deep()
        if bmi_analysis.get('status') != 'insufficient_data' and bmi_analysis.get('bmi'):
            if bmi_analysis['weight_to_lose'] > 0:
                recommendations.append({
                    'type': 'weight_loss',
                    'priority': 'high',
                    'icon': '⚖️',
                    'title': self._t('برنامج خسارة الوزن', 'Weight Loss Program'),
                    'description': bmi_analysis.get('time_to_goal', {}).get(f'message_{self.language}', ''),
                    'actions': [
                        self._t('قلل 500 سعرة حرارية يومياً', 'Reduce 500 calories daily'),
                        self._t('مارس المشي 45 دقيقة يومياً', 'Walk 45 minutes daily'),
                        self._t('تناول البروتين في كل وجبة', 'Eat protein with every meal'),
                    ]
                })
            
            elif bmi_analysis['weight_to_gain'] > 0:
                recommendations.append({
                    'type': 'weight_gain',
                    'priority': 'high',
                    'icon': '💪',
                    'title': self._t('زيادة الوزن الصحي', 'Healthy Weight Gain'),
                    'description': bmi_analysis.get('time_to_goal', {}).get(f'message_{self.language}', ''),
                    'actions': [
                        self._t('زد 300-500 سعرة حرارية يومياً', 'Increase 300-500 calories daily'),
                        self._t('تمارين المقاومة 3 مرات أسبوعياً', 'Resistance training 3 times weekly'),
                        self._t('تناول بروتين إضافي بعد التمرين', 'Extra protein after workout'),
                    ]
                })
        
        # توصيات النشاط حسب العمر والوظيفة
        profile = self.analyze_user_profile()
        if profile.get('occupation_risks'):
            recommendations.append({
                'type': 'activity',
                'priority': 'medium',
                'icon': '🪑',
                'title': self._t('نصائح للعمل المكتبي', 'Office Work Tips'),
                'description': profile['occupation_risks'][0]['advice_ar' if self.is_arabic else 'advice_en'],
                'actions': [
                    self._t('قف وتمدد كل ساعة', 'Stand and stretch every hour'),
                    self._t('استخدم كرسي مريح للظهر', 'Use an ergonomic chair'),
                    self._t('مارس تمارين الرقبة والكتفين', 'Do neck and shoulder exercises'),
                ]
            })
        
        # توصيات حسب العمر
        age_risks = self.analyze_age_related_risks()
        if age_risks.get('risks'):
            recommendations.append({
                'type': 'preventive',
                'priority': 'high',
                'icon': '🩺',
                'title': self._t('فحوصات وقائية موصى بها', 'Recommended Preventive Screenings'),
                'description': self._t('بناءً على عمرك وخطرتك الصحية', 'Based on your age and health risks'),
                'actions': [f"📋 {r.get('condition')}" for r in age_risks['risks'][:3]],
            })
        
        # توصيات الصحة الأيضية
        metabolic = self.analyze_metabolic_health()
        if metabolic.get('calorie_status') == 'excess':
            recommendations.append({
                'type': 'diet',
                'priority': 'medium',
                'icon': '🍽️',
                'title': self._t('تعديل السعرات الحرارية', 'Calorie Adjustment'),
                'description': self._t(f"تتناول {abs(metabolic['calorie_diff'])} سعرة إضافية يومياً", f"Consuming {abs(metabolic['calorie_diff'])} extra calories daily"),
                'actions': [
                    self._t('قلل من السكريات والمقليات', 'Reduce sugars and fried foods'),
                    self._t('استخدم صحون أصغر للتحكم بالكميات', 'Use smaller plates for portion control'),
                ]
            })
        
        return recommendations
    
    def suggest_health_goals(self):
        """اقتراح أهداف صحية ذكية"""
        goals = []
        lifestyle = self.calculate_lifestyle_score()
        bmi_analysis = self.analyze_bmi_deep()
        
        # أهداف الوزن
        if bmi_analysis.get('status') != 'insufficient_data':
            if bmi_analysis.get('weight_to_lose', 0) > 5:
                goals.append({
                    'category': 'weight',
                    'title': self._t(f'خسارة {round(bmi_analysis["weight_to_lose"])} كجم', f'Lose {round(bmi_analysis["weight_to_lose"])} kg'),
                    'deadline': '3 أشهر' if self.is_arabic else '3 months',
                    'difficulty': 'medium',
                    'reward': self._t('🎯 تحسين الصحة العامة وتقليل مخاطر الأمراض', '🎯 Improve overall health and reduce disease risks')
                })
            
            elif bmi_analysis.get('weight_to_gain', 0) > 2:
                goals.append({
                    'category': 'weight',
                    'title': self._t(f'زيادة {round(bmi_analysis["weight_to_gain"])} كجم كتلة عضلية', f'Gain {round(bmi_analysis["weight_to_gain"])} kg of muscle mass'),
                    'deadline': '4 أشهر' if self.is_arabic else '4 months',
                    'difficulty': 'medium',
                    'reward': self._t('💪 تحسين القوة واللياقة البدنية', '💪 Improve strength and fitness')
                })
        
        # أهداف النشاط
        weekly_activities = PhysicalActivity.objects.filter(
            user=self.user, start_time__date__gte=self.week_ago
        )
        total_minutes = weekly_activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
        
        if total_minutes < 150:
            goals.append({
                'category': 'activity',
                'title': self._t('المشي 30 دقيقة يومياً لمدة 5 أيام في الأسبوع', 'Walk 30 minutes daily for 5 days per week'),
                'deadline': 'شهر واحد' if self.is_arabic else '1 month',
                'difficulty': 'easy',
                'reward': self._t('🏆 تحسين صحة القلب والجهاز التنفسي', '🏆 Improve cardiovascular and respiratory health')
            })
        
        # أهداف النوم
        sleeps = Sleep.objects.filter(user=self.user, sleep_start__date__gte=self.week_ago)
        if sleeps.exists():
            avg_sleep = sleeps.aggregate(Avg('duration'))['duration__avg'] or 0
            if avg_sleep < 7 or avg_sleep > 9:
                goals.append({
                    'category': 'sleep',
                    'title': self._t('تنظيم النوم: 8 ساعات يومياً', 'Sleep regulation: 8 hours daily'),
                    'deadline': 'أسبوعين' if self.is_arabic else '2 weeks',
                    'difficulty': 'easy',
                    'reward': self._t('😴 تحسين التركيز والمزاج والطاقة', '😴 Improve focus, mood and energy')
                })
        
        return goals
    
    def analyze_vital_signs(self):
        """تحليل العلامات الحيوية الحالية"""
        latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
        
        if not latest:
            return {'status': 'no_data', 'message': self._t('لا توجد بيانات كافية', 'Insufficient data')}
        
        insights = []
        alerts = []
        
        # تحليل الوزن
        weight = latest.weight_kg
        if weight:
            weight = float(weight)
            if weight < 50:
                insights.append({
                    'type': 'weight',
                    'severity': 'warning',
                    'message': self._t('⚠️ وزنك منخفض جداً', '⚠️ Your weight is very low'),
                    'details': self._t(f'{weight} كجم أقل من المعدل الطبيعي', f'{weight} kg below normal'),
                    'recommendation': self._t('تحتاج لزيادة السعرات الحرارية والبروتين', 'You need to increase calories and protein')
                })
            elif weight > 100:
                insights.append({
                    'type': 'weight',
                    'severity': 'warning',
                    'message': self._t('⚠️ وزنك مرتفع', '⚠️ Your weight is high'),
                    'details': self._t(f'{weight} كجم أعلى من المعدل', f'{weight} kg above normal'),
                    'recommendation': self._t('جرب المشي 30 دقيقة يومياً وقلل السكريات', 'Try walking 30 minutes daily and reduce sugars')
                })
            else:
                insights.append({
                    'type': 'weight',
                    'severity': 'good',
                    'message': self._t('✅ وزنك في المعدل المثالي', '✅ Your weight is ideal'),
                    'details': self._t(f'{weight} كجم', f'{weight} kg'),
                    'recommendation': self._t('حافظ على نظامك الحالي', 'Maintain your current routine')
                })
        
        # تحليل ضغط الدم
        systolic = latest.systolic_pressure
        diastolic = latest.diastolic_pressure
        pulse_pressure = (systolic - diastolic) if systolic and diastolic else None
        
        if systolic and diastolic:
            if pulse_pressure > 60:
                alerts.append({
                    'type': 'pulse_pressure',
                    'severity': 'high',
                    'message': self._t('❤️‍🩹 فرق الضغط كبير جداً', '❤️‍🩹 Pulse pressure is very high'),
                    'details': self._t(f'الفرق {pulse_pressure} مم زئبق (الطبيعي 40-60)', f'Difference {pulse_pressure} mmHg (normal 40-60)'),
                    'recommendation': self._t('قد يشير لصلابة الشرايين، استشر طبيباً', 'May indicate arterial stiffness, consult a doctor')
                })
            elif pulse_pressure < 30:
                alerts.append({
                    'type': 'pulse_pressure',
                    'severity': 'low',
                    'message': self._t('💓 فرق الضغط منخفض', '💓 Pulse pressure is low'),
                    'details': self._t(f'الفرق {pulse_pressure} مم زئبق', f'Difference {pulse_pressure} mmHg'),
                    'recommendation': self._t('قد يشير لضعف القلب، راقب الأعراض', 'May indicate heart weakness, monitor symptoms')
                })
        
        # تحليل الجلوكوز
        glucose = latest.blood_glucose
        if glucose:
            glucose = float(glucose)
            if glucose > 140:
                insights.append({
                    'type': 'glucose',
                    'severity': 'high',
                    'message': self._t('🩸 سكر الدم مرتفع', '🩸 Blood sugar is high'),
                    'details': self._t(f'{glucose} mg/dL أعلى من الطبيعي', f'{glucose} mg/dL above normal'),
                    'recommendation': self._t('قلل الكربوهيدرات البسيطة وامش 15 دقيقة', 'Reduce simple carbs and walk 15 minutes')
                })
            elif glucose < 70:
                insights.append({
                    'type': 'glucose',
                    'severity': 'low',
                    'message': self._t('🆘 سكر الدم منخفض!', '🆘 Blood sugar is low!'),
                    'details': self._t(f'{glucose} mg/dL أقل من الطبيعي', f'{glucose} mg/dL below normal'),
                    'recommendation': self._t('تناول مصدر سكر سريع (عصير، تمر)', 'Eat a quick sugar source (juice, dates)')
                })
        
        return {
            'vital_signs': {
                'weight': float(weight) if weight else None,
                'blood_pressure': f"{systolic}/{diastolic}" if systolic and diastolic else None,
                'glucose': float(glucose) if glucose else None,
                'recorded_at': latest.recorded_at
            },
            'insights': insights,
            'alerts': alerts,
            'pulse_pressure': pulse_pressure
        }
    
    def analyze_energy_consumption(self):
        """تحليل استهلاك الطاقة"""
        latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
        
        if not latest or not latest.weight_kg:
            return {'status': 'insufficient_data'}
        
        weight = float(latest.weight_kg)
        bmr = weight * 22
        
        weekly_activity = PhysicalActivity.objects.filter(
            user=self.user, start_time__date__gte=self.week_ago
        ).aggregate(Sum('calories_burned'))['calories_burned__sum'] or 0
        
        daily_activity = weekly_activity / 7
        total_daily_burn = bmr + daily_activity
        
        avg_daily_intake = Meal.objects.filter(
            user=self.user, meal_time__date__gte=self.week_ago
        ).aggregate(Avg('total_calories'))['total_calories__avg'] or 0
        
        return {
            'weight': weight,
            'bmr': int(bmr),
            'daily_activity_burn': int(daily_activity),
            'total_daily_burn': int(total_daily_burn),
            'avg_daily_intake': int(avg_daily_intake),
            'deficit': int(total_daily_burn - avg_daily_intake)
        }
    
    def analyze_pulse_pressure(self):
        """تحليل ضغط النبض"""
        latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
        
        if not latest or not latest.systolic_pressure or not latest.diastolic_pressure:
            return {'status': 'insufficient_data'}
        
        systolic = latest.systolic_pressure
        diastolic = latest.diastolic_pressure
        pulse_pressure = systolic - diastolic
        
        return {
            'systolic': systolic,
            'diastolic': diastolic,
            'pulse_pressure': pulse_pressure,
            'severity': 'critical' if pulse_pressure < 15 else 'warning' if pulse_pressure < 30 else 'normal'
        }
    
    def analyze_pre_exercise_risk(self):
        """تحليل مخاطر التمرين"""
        latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
        
        if not latest:
            return {'status': 'insufficient_data'}
        
        glucose = latest.blood_glucose
        systolic = latest.systolic_pressure
        diastolic = latest.diastolic_pressure
        
        recommendations = []
        
        if glucose and glucose < 100:
            glucose = float(glucose)
            if glucose < 80:
                recommendations.append({
                    'type': 'critical',
                    'icon': '🚨',
                    'title': self._t('خطر انخفاض السكر', 'Low Blood Sugar Risk'),
                    'message': self._t('سكر الدم منخفض قبل التمرين', 'Blood sugar is low before exercise'),
                    'advice': self._t('تناول وجبة خفيفة تحتوي على كربوهيدرات قبل التمرين', 'Eat a light carbohydrate-rich meal before exercise')
                })
        
        if systolic and diastolic:
            if systolic > 140 or diastolic > 90:
                recommendations.append({
                    'type': 'warning',
                    'icon': '❤️',
                    'title': self._t('ضغط الدم مرتفع', 'High Blood Pressure'),
                    'message': self._t('ضغطك مرتفع للتمرين المكثف', 'Your blood pressure is high for intense exercise'),
                    'advice': self._t('مارس المشي بدلاً من الركض', 'Try walking instead of running')
                })
        
        return {
            'glucose': float(glucose) if glucose else None,
            'blood_pressure': f"{systolic}/{diastolic}" if systolic and diastolic else None,
            'recommendations': recommendations
        }
    
    def analyze_activity_nutrition(self):
        """تحليل العلاقة بين النشاط والتغذية"""
        activities = PhysicalActivity.objects.filter(
            user=self.user, start_time__date__gte=self.week_ago
        )
        
        if not activities.exists():
            return {'status': 'insufficient_data', 'message': self._t('لا توجد أنشطة كافية', 'Insufficient activity data')}
        
        return {'status': 'ok', 'total_activities': activities.count()}
    
    def analyze_sleep_mood(self):
        """تحليل تأثير النوم على المزاج"""
        sleep_records = Sleep.objects.filter(user=self.user, sleep_start__date__gte=self.week_ago)
        
        if not sleep_records.exists():
            return {'status': 'insufficient_data'}
        
        return {'status': 'ok', 'sleep_count': sleep_records.count()}
    
    def analyze_weight_trends(self):
        """تحليل اتجاهات الوزن"""
        health_records = HealthStatus.objects.filter(user=self.user, weight_kg__isnull=False).order_by('recorded_at')
        
        if health_records.count() < 2:
            return {'trend': 'insufficient_data'}
        
        first = health_records.first()
        last = health_records.last()
        
        weight_change = float(last.weight_kg) - float(first.weight_kg)
        days_diff = (last.recorded_at.date() - first.recorded_at.date()).days
        
        return {
            'start_weight': float(first.weight_kg),
            'current_weight': float(last.weight_kg),
            'change': round(weight_change, 1),
            'days_analyzed': days_diff,
            'trend': self._t('زيادة', 'Increasing') if weight_change > 0 else self._t('نقصان', 'Decreasing') if weight_change < 0 else self._t('ثبات', 'Stable')
        }
    
    def analyze_blood_pressure(self):
        """تحليل ضغط الدم"""
        records = HealthStatus.objects.filter(
            user=self.user, systolic_pressure__isnull=False, diastolic_pressure__isnull=False
        ).order_by('-recorded_at')[:10]
        
        if records.count() < 3:
            return {'status': 'insufficient_data'}
        
        avg_sys = records.aggregate(Avg('systolic_pressure'))['systolic_pressure__avg']
        avg_dia = records.aggregate(Avg('diastolic_pressure'))['diastolic_pressure__avg']
        
        return {'average': f"{avg_sys:.0f}/{avg_dia:.0f}", 'status': 'ok'}
    
    def analyze_glucose_risks(self):
        """تحليل مخاطر السكر"""
        records = HealthStatus.objects.filter(user=self.user, blood_glucose__isnull=False).order_by('-recorded_at')[:7]
        
        if records.count() < 2:
            return {'status': 'insufficient_data'}
        
        glucose_values = [float(r.blood_glucose) for r in records if r.blood_glucose]
        
        if not glucose_values:
            return {'status': 'no_data'}
        
        avg_glucose = sum(glucose_values) / len(glucose_values)
        max_glucose = max(glucose_values)
        min_glucose = min(glucose_values)
        
        return {
            'average': round(avg_glucose, 1),
            'range': f"{min_glucose:.0f} - {max_glucose:.0f}",
            'status': 'ok'
        }
    
    def generate_holistic_recommendations(self):
        """توليد توصيات شاملة"""
        return []
    
    def generate_predictive_alerts(self):
        """توليد تنبيهات تنبؤية"""
        return []
# أضف هذا في نهاية ملف main/services/cross_insights_service.py

class CrossInsightsService:
    """
    خدمة التحليلات المتقاطعة الأساسية
    Basic Cross-Insights Service
    """
    
    def __init__(self, user):
        self.user = user
        self.engine = HealthInsightsEngine(user)
    
    def get_all_correlations(self):
        """
        جلب جميع الارتباطات والتحليلات
        Get all correlations and analyses
        """
        try:
            # استخدام المحرك الرئيسي للحصول على التحليلات
            all_analyses = self.engine.analyze_all()
            
            return {
                'success': True,
                'correlations': {
                    'vital_signs': all_analyses.get('vital_signs_analysis', {}),
                    'activity_nutrition': all_analyses.get('activity_nutrition_correlation', {}),
                    'sleep_mood': all_analyses.get('sleep_mood_correlation', {}),
                    'weight_trends': all_analyses.get('weight_trend_analysis', {}),
                    'blood_pressure': all_analyses.get('blood_pressure_insights', {}),
                    'glucose_risk': all_analyses.get('glucose_risk_assessment', {}),
                },
                'insights': {
                    'energy_consumption': all_analyses.get('energy_consumption_alert', {}),
                    'pulse_pressure': all_analyses.get('pulse_pressure_analysis', {}),
                    'pre_exercise': all_analyses.get('pre_exercise_recommendation', {}),
                },
                'recommendations': all_analyses.get('holistic_recommendations', []),
                'alerts': all_analyses.get('predictive_alerts', []),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'correlations': {},
                'insights': {},
                'recommendations': [],
                'alerts': []
            }
    
    def get_vital_correlations(self):
        """الحصول على ارتباطات العلامات الحيوية"""
        analysis = self.engine.analyze_vital_signs()
        return {
            'vital_signs': analysis.get('vital_signs'),
            'insights': analysis.get('insights', []),
            'alerts': analysis.get('alerts', [])
        }
    
    def get_lifestyle_correlations(self):
        """الحصول على ارتباطات نمط الحياة"""
        return {
            'activity_nutrition': self.engine.analyze_activity_nutrition(),
            'sleep_mood': self.engine.analyze_sleep_mood(),
            'energy_balance': self.engine.analyze_energy_consumption()
        }
    
    def get_risk_assessment(self):
        """تقييم المخاطر الصحية"""
        return {
            'pre_exercise_risk': self.engine.analyze_pre_exercise_risk(),
            'blood_pressure_risk': self.engine.analyze_blood_pressure(),
            'glucose_risk': self.engine.analyze_glucose_risks(),
            'pulse_pressure': self.engine.analyze_pulse_pressure()
        }
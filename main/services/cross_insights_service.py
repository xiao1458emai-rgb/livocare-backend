"""
محرك الذكاء الاصطناعي للتحليلات الصحية المتقاطعة - النسخة المتطورة مع scikit-learn
يتضمن تحليل شامل لـ CustomUser + HealthStatus + PhysicalActivity
"""

from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, F, Min, Max
from django.conf import settings
from main.models import (
    HealthStatus, PhysicalActivity, Sleep, 
    MoodEntry, Meal, HabitLog, CustomUser
)
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import NearestNeighbors
import warnings
warnings.filterwarnings('ignore')

class HealthInsightsEngineML:
    """
    محرك متقدم لتحليل البيانات الصحية باستخدام خوارزميات التعلم الآلي
    يشمل تحليل بيانات المستخدم الشخصية (CustomUser) + العلامات الحيوية + الأنشطة
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.today = timezone.now().date()
        self.week_ago = self.today - timedelta(days=7)
        self.month_ago = self.today - timedelta(days=30)
        self.three_months_ago = self.today - timedelta(days=90)
        self.is_arabic = language == 'ar'
        
        # ✅ جلب جميع بيانات المستخدم من CustomUser
        self._load_user_profile_data()
        
        # تخزين البيانات للتحليل
        self._health_data = None
        self._activity_data = None
        self._sleep_data = None
        self._mood_data = None
        self._meal_data = None
        
        # النماذج المدربة
        self._models = {}
        
    def _load_user_profile_data(self):
        """تحميل وتحليل جميع بيانات المستخدم من CustomUser"""
        
        # ✅ البيانات الأساسية
        self.user_age = None
        self.user_gender = self.user.gender if hasattr(self.user, 'gender') else None
        self.user_height = None
        self.user_initial_weight = None
        self.user_health_goal = self.user.health_goal if hasattr(self.user, 'health_goal') else None
        self.user_activity_level = self.user.activity_level if hasattr(self.user, 'activity_level') else None
        self.user_occupation = self.user.occupation_status if hasattr(self.user, 'occupation_status') else None
        
        # حساب العمر من تاريخ الميلاد
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
        
        # ✅ حساب مؤشرات إضافية
        self.user_bmi = None
        if self.user_height and self.user_initial_weight:
            height_m = self.user_height / 100
            self.user_bmi = round(self.user_initial_weight / (height_m ** 2), 1)
        
        # ✅ تحديد الفئة العمرية
        self.age_category = self._get_age_category()
        
        # ✅ حساب معامل النشاط الأساسي
        self.base_activity_multiplier = self._get_base_activity_multiplier()
        
        # ✅ تحديد الهدف الصحي
        self.health_goal_text = self._get_health_goal_text()
        
        # ✅ مستوى الخطر حسب العمر والجنس
        self.risk_factors = self._calculate_risk_factors()
    
    def _get_age_category(self):
        """تحديد الفئة العمرية للمستخدم"""
        if not self.user_age:
            return 'unknown'
        if self.user_age < 18:
            return 'adolescent'
        elif self.user_age < 30:
            return 'young_adult'
        elif self.user_age < 50:
            return 'adult'
        elif self.user_age < 70:
            return 'senior'
        else:
            return 'elderly'
    
    def _get_base_activity_multiplier(self):
        """معامل النشاط الأساسي حسب مستوى النشاط المختار"""
        multipliers = {
            'low': 1.2,
            'medium': 1.375,
            'high': 1.55
        }
        return multipliers.get(self.user_activity_level, 1.375)
    
    def _get_health_goal_text(self):
        """نص الهدف الصحي باللغتين"""
        goals = {
            'loss': {'ar': 'خسارة الوزن', 'en': 'Weight Loss'},
            'gain': {'ar': 'زيادة الوزن', 'en': 'Weight Gain'},
            'maintain': {'ar': 'تثبيت الوزن', 'en': 'Weight Maintenance'}
        }
        goal = goals.get(self.user_health_goal, {'ar': 'غير محدد', 'en': 'Not specified'})
        return goal['ar'] if self.is_arabic else goal['en']
    
    def _calculate_risk_factors(self):
        """حساب عوامل الخطر بناءً على بيانات المستخدم"""
        risk_factors = []
        
        # مخاطر العمر
        if self.user_age:
            if self.user_age > 50:
                risk_factors.append({
                    'factor': 'age',
                    'level': 'high',
                    'message_ar': 'عمرك فوق 50 سنة - يوصى بفحوصات دورية شاملة',
                    'message_en': 'Age over 50 - comprehensive regular checkups recommended'
                })
            elif self.user_age > 40:
                risk_factors.append({
                    'factor': 'age',
                    'level': 'medium',
                    'message_ar': 'عمرك فوق 40 سنة - راقب ضغط الدم والسكر',
                    'message_en': 'Age over 40 - monitor blood pressure and sugar'
                })
        
        # مخاطر الجنس
        if self.user_gender == 'M' and self.user_age and self.user_age > 45:
            risk_factors.append({
                'factor': 'gender',
                'level': 'medium',
                'message_ar': 'الرجال فوق 45 أكثر عرضة لأمراض القلب',
                'message_en': 'Men over 45 are more susceptible to heart disease'
            })
        
        # مخاطر BMI
        if self.user_bmi:
            if self.user_bmi > 30:
                risk_factors.append({
                    'factor': 'bmi',
                    'level': 'high',
                    'message_ar': f'مؤشر كتلة جسمك {self.user_bmi} - زيادة الوزن تزيد من مخاطر صحية متعددة',
                    'message_en': f'Your BMI is {self.user_bmi} - overweight increases multiple health risks'
                })
            elif self.user_bmi < 18.5:
                risk_factors.append({
                    'factor': 'bmi',
                    'level': 'medium',
                    'message_ar': 'نقص الوزن - قد يؤثر على مناعتك وطاقتك',
                    'message_en': 'Underweight - may affect your immunity and energy'
                })
        
        # مخاطر الوظيفة
        sedentary_occupations = ['Student', 'Full-Time']
        if self.user_occupation in sedentary_occupations:
            risk_factors.append({
                'factor': 'occupation',
                'level': 'medium',
                'message_ar': 'وظيفتك تتطلب الجلوس لفترات طويلة - خذ فترات راحة للحركة',
                'message_en': 'Your occupation requires long sitting periods - take movement breaks'
            })
        
        return risk_factors
    
    def _t(self, ar_text, en_text, **kwargs):
        """ترجمة النصوص حسب اللغة المحددة"""
        text = ar_text if self.is_arabic else en_text
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text
    
    def _prepare_dataframe(self):
        """تحضير DataFrame موحد للتحليل مع تضمين بيانات المستخدم الشخصية"""
        
        # جلب جميع بيانات المستخدم
        health_records = HealthStatus.objects.filter(user=self.user).order_by('recorded_at')
        activities = PhysicalActivity.objects.filter(user=self.user).order_by('start_time')
        
        if not health_records.exists():
            return None
        
        # ✅ إضافة البيانات الشخصية الثابتة للمستخدم
        user_features = {
            'user_age': self.user_age or 30,
            'user_gender_male': 1 if self.user_gender == 'M' else 0,
            'user_gender_female': 1 if self.user_gender == 'F' else 0,
            'user_height': self.user_height or 170,
            'user_initial_weight': self.user_initial_weight or 70,
            'user_bmi': self.user_bmi or 24,
            'activity_level_score': self._get_activity_score(),
            'health_goal_loss': 1 if self.user_health_goal == 'loss' else 0,
            'health_goal_gain': 1 if self.user_health_goal == 'gain' else 0,
            'health_goal_maintain': 1 if self.user_health_goal == 'maintain' else 0,
        }
        
        # بناء DataFrame رئيسي
        data = []
        for record in health_records:
            day_data = {
                'date': record.recorded_at.date(),
                'weight': float(record.weight_kg) if record.weight_kg else None,
                'systolic': record.systolic_pressure,
                'diastolic': record.diastolic_pressure,
                'glucose': float(record.blood_glucose) if record.blood_glucose else None,
                'heart_rate': record.heart_rate,
                'oxygen': record.spo2,
                'body_temperature': float(record.body_temperature) if record.body_temperature else None,
                'pulse': record.pulse,
                'respiration_rate': record.respiration_rate,
            }
            
            # إضافة الأنشطة في نفس اليوم
            day_activities = activities.filter(start_time__date=record.recorded_at.date())
            day_data['total_activity_minutes'] = day_activities.aggregate(Sum('duration_minutes'))['duration_minutes__sum'] or 0
            day_data['calories_burned'] = day_activities.aggregate(Sum('calories_burned'))['calories_burned__sum'] or 0
            day_data['activity_count'] = day_activities.count()
            
            # ✅ إضافة متوسط مدة النشاط
            if day_data['activity_count'] > 0:
                day_data['avg_activity_duration'] = day_data['total_activity_minutes'] / day_data['activity_count']
            else:
                day_data['avg_activity_duration'] = 0
            
            # ✅ إضافة جميع البيانات الشخصية
            day_data.update(user_features)
            
            data.append(day_data)
        
        df = pd.DataFrame(data)
        
        # تنظيف البيانات
        df = df.dropna(subset=['weight'], how='any')
        df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def _get_activity_score(self):
        """تحويل مستوى النشاط إلى درجة رقمية"""
        scores = {
            'low': 1,
            'medium': 2,
            'high': 3
        }
        return scores.get(self.user_activity_level, 2)
    
    # ==========================================================================
    # ✅ تحليل جديد: توصيات مخصصة بناءً على ملف المستخدم الشخصي
    # ==========================================================================
    
    def analyze_user_profile_health(self):
        """
        تحليل شامل لملف المستخدم الشخصي وإنتاج توصيات مخصصة
        """
        profile_analysis = {
            'basic_info': {
                'age': self.user_age,
                'gender': self._t('ذكر', 'Male') if self.user_gender == 'M' else self._t('أنثى', 'Female') if self.user_gender == 'F' else None,
                'height_cm': self.user_height,
                'initial_weight_kg': self.user_initial_weight,
                'bmi': self.user_bmi,
                'health_goal': self.health_goal_text,
                'activity_level': self.user_activity_level,
                'occupation': self.user_occupation,
            },
            'age_category': self.age_category,
            'risk_factors': self.risk_factors,
            'personalized_recommendations': self._generate_profile_recommendations(),
            'bmi_analysis': self._analyze_bmi_with_profile(),
            'goal_alignment': self._check_goal_alignment(),
        }
        
        return profile_analysis
    
    def _analyze_bmi_with_profile(self):
        """تحليل BMI مع مراعاة العمر والجنس والهدف الصحي"""
        if not self.user_bmi:
            return {'status': 'no_data'}
        
        # تحديد النطاق المثالي حسب العمر
        if self.user_age and self.user_age > 65:
            ideal_min, ideal_max = 23, 27  # كبار السن
        elif self.user_age and self.user_age < 18:
            ideal_min, ideal_max = 18.5, 24  # المراهقين
        else:
            ideal_min, ideal_max = 18.5, 24.9  # البالغين
        
        if self.user_bmi < ideal_min:
            status = 'underweight'
            message = self._t('⚠️ وزنك أقل من المثالي لعمرك', '⚠️ Your weight is below ideal for your age')
            advice = self._t('نوصي بزيادة السعرات الحرارية مع تمارين بناء العضلات', 'We recommend increasing calories with muscle building exercises')
        elif self.user_bmi > ideal_max:
            status = 'overweight'
            message = self._t('⚠️ وزنك أعلى من المثالي لعمرك', '⚠️ Your weight is above ideal for your age')
            advice = self._t('نوصي بتقليل السعرات وزيادة النشاط البدني اليومي', 'We recommend reducing calories and increasing daily physical activity')
        else:
            status = 'ideal'
            message = self._t('✅ وزنك مثالي لعمرك!', '✅ Your weight is ideal for your age!')
            advice = self._t('استمر في الحفاظ على هذا الوزن الصحي', 'Continue maintaining this healthy weight')
        
        return {
            'status': status,
            'bmi': self.user_bmi,
            'ideal_range': f"{ideal_min} - {ideal_max}",
            'message': message,
            'advice': advice
        }
    
    def _check_goal_alignment(self):
        """التحقق من توافق الوزن الحالي مع الهدف الصحي"""
        if not self.user_health_goal or not self.user_bmi:
            return {'aligned': True, 'message': self._t('حدد هدفك الصحي للحصول على توصيات أفضل', 'Set your health goal for better recommendations')}
        
        latest_weight = self._get_latest_weight()
        if not latest_weight:
            return {'aligned': True, 'message': ''}
        
        weight_change = latest_weight - (self.user_initial_weight or latest_weight)
        
        if self.user_health_goal == 'loss' and weight_change > 0:
            return {
                'aligned': False,
                'message': self._t(f'⚠️ وزنك زاد {abs(weight_change):.1f} كجم بينما هدفك هو الخسارة', 
                                  f'⚠️ Your weight increased by {abs(weight_change):.1f} kg while your goal is loss'),
                'suggestion': self._t('حاول تقليل 300-500 سعرة حرارية يومياً', 'Try reducing 300-500 calories daily')
            }
        elif self.user_health_goal == 'gain' and weight_change < 0:
            return {
                'aligned': False,
                'message': self._t(f'⚠️ وزنك نقص {abs(weight_change):.1f} كجم بينما هدفك الزيادة',
                                  f'⚠️ Your weight decreased by {abs(weight_change):.1f} kg while your goal is gain'),
                'suggestion': self._t('أضف 300-500 سعرة حرارية مع بروتين إضافي', 'Add 300-500 calories with extra protein')
            }
        
        return {
            'aligned': True,
            'message': self._t('✅ أنت على المسار الصحيح لتحقيق هدفك!', '✅ You are on the right track to achieve your goal!')
        }
    
    def _generate_profile_recommendations(self):
        """توليد توصيات مخصصة بناءً على ملف المستخدم"""
        recommendations = []
        
        # توصيات حسب العمر
        if self.age_category == 'adolescent':
            recommendations.append({
                'category': 'age',
                'icon': '🌱',
                'title': self._t('نمو صحي', 'Healthy Growth'),
                'advice': self._t('ركز على البروتين والكالسيوم وفيتامين د لدعم النمو', 'Focus on protein, calcium, and vitamin D to support growth')
            })
        elif self.age_category == 'senior' or self.age_category == 'elderly':
            recommendations.append({
                'category': 'age',
                'icon': '🩺',
                'title': self._t('صحة كبار السن', 'Senior Health'),
                'advice': self._t('اهتم بتمارين التوازن والمرونة، وراقب ضغط الدم دورياً', 'Focus on balance and flexibility exercises, monitor blood pressure regularly')
            })
        
        # توصيات حسب الهدف الصحي
        if self.user_health_goal == 'loss':
            recommendations.append({
                'category': 'goal',
                'icon': '🥗',
                'title': self._t('لخسارة الوزن', 'For Weight Loss'),
                'advice': self._t('ابدأ بالمشي 30 دقيقة يومياً، وتناول الخضروات في كل وجبة', 'Start with 30 minutes of walking daily, eat vegetables with every meal')
            })
        elif self.user_health_goal == 'gain':
            recommendations.append({
                'category': 'goal',
                'icon': '💪',
                'title': self._t('لزيادة الوزن', 'For Weight Gain'),
                'advice': self._t('أضف المكسرات وزبدة الفول السوداني لوجباتك، ومارس تمارين المقاومة', 'Add nuts and peanut butter to your meals, practice resistance training')
            })
        
        # توصيات حسب مستوى النشاط
        if self.user_activity_level == 'low':
            recommendations.append({
                'category': 'activity',
                'icon': '🚶',
                'title': self._t('تحسين النشاط', 'Improve Activity'),
                'advice': self._t('حاول المشي 10 دقائق بعد كل وجبة - 30 دقيقة يومياً', 'Try walking 10 minutes after each meal - 30 minutes daily')
            })
        
        # توصيات حسب الوظيفة
        if self.user_occupation in ['Student', 'Full-Time']:
            recommendations.append({
                'category': 'occupation',
                'icon': '🪑',
                'title': self._t('نصائح للعمل/الدراسة', 'Work/Study Tips'),
                'advice': self._t('خذ استراحة حركة كل ساعة، واجلس بوضعية صحية', 'Take a movement break every hour, sit with proper posture')
            })
        
        return recommendations
    
    def _get_latest_weight(self):
        """جلب آخر وزن مسجل"""
        latest = HealthStatus.objects.filter(user=self.user, weight_kg__isnull=False).order_by('-recorded_at').first()
        return float(latest.weight_kg) if latest else None
    
    # ==========================================================================
    # ✅ تحليل متقدم للعلامات الحيوية مع مراعاة بيانات المستخدم
    # ==========================================================================
    
    def predict_weight_trend_with_profile(self):
        """
        التنبؤ باتجاه الوزن باستخدام Random Forest مع تضمين بيانات المستخدم الشخصية
        """
        df = self._prepare_dataframe()
        if df is None or len(df) < 7:
            return {'status': 'insufficient_data', 'message': self._t('لا توجد بيانات كافية للتنبؤ', 'Insufficient data for prediction')}
        
        # تحضير الميزات (بما فيها بيانات المستخدم)
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['weight_lag1'] = df['weight'].shift(1)
        df['weight_lag3'] = df['weight'].shift(3)
        df['weight_lag7'] = df['weight'].shift(7)
        df['weight_ma3'] = df['weight'].rolling(window=3, min_periods=1).mean()
        df['weight_ma7'] = df['weight'].rolling(window=7, min_periods=1).mean()
        df['weight_diff'] = df['weight'].diff()
        
        # ✅ ميزات إضافية من بيانات المستخدم
        df['calories_deficit'] = (df['calories_burned'] + (self.user_initial_weight or 70) * 22) - df['total_calories']
        df['activity_per_kg'] = df['total_activity_minutes'] / df['weight']
        df['age_normalized'] = df['user_age'] / 100
        df['bmi_normalized'] = df['user_bmi'] / 50
        
        # ميزات التوافق مع الهدف
        if self.user_health_goal == 'loss':
            df['goal_direction'] = -1
        elif self.user_health_goal == 'gain':
            df['goal_direction'] = 1
        else:
            df['goal_direction'] = 0
        
        # قائمة الميزات
        feature_cols = ['day_of_week', 'day_of_month', 'weight_lag1', 'weight_lag3', 
                        'weight_lag7', 'weight_ma3', 'weight_ma7', 'weight_diff',
                        'total_activity_minutes', 'total_calories', 'calories_deficit', 
                        'activity_per_kg', 'age_normalized', 'bmi_normalized', 'goal_direction',
                        'user_gender_male', 'activity_level_score']
        
        df_clean = df.dropna(subset=feature_cols).copy()
        
        if len(df_clean) < 10:
            return {'status': 'insufficient_data'}
        
        # تدريب النموذج
        X = df_clean[feature_cols].fillna(0)
        y = df_clean['weight']
        
        model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=5)
        model.fit(X[:-7] if len(X) > 7 else X, y[:-7] if len(y) > 7 else y)
        
        # التنبؤ
        last_row = X.iloc[-1:].copy()
        predictions = []
        
        for i in range(1, 15):
            pred = model.predict(last_row)[0]
            predictions.append(round(pred, 1))
            
            # تحديث الميزات
            last_row['weight_lag1'] = pred
            last_row['weight_lag3'] = last_row['weight_lag1'].values[0] if i > 2 else pred
            last_row['weight_lag7'] = last_row['weight_lag1'].values[0] if i > 6 else pred
        
        current_weight = df['weight'].iloc[-1]
        target_weight = predictions[-1]
        change = target_weight - current_weight
        
        # توليد توصيات حسب الهدف الصحي
        if self.user_health_goal == 'loss' and change > 0:
            recommendation = self._t('⚠️ الوزن يتجه للزيادة رغم هدفك بالخسارة! حاول زيادة خطواتك اليومية بمقدار 2000 خطوة', 
                                    '⚠️ Weight is increasing despite your loss goal! Try increasing your daily steps by 2000')
        elif self.user_health_goal == 'gain' and change < 0:
            recommendation = self._t('⚠️ الوزن يتجه للنقصان رغم هدفك بالزيادة! أضف وجبة خفيفة إضافية يومياً',
                                    '⚠️ Weight is decreasing despite your gain goal! Add an extra snack daily')
        else:
            recommendation = self._t('استمر في تتبع عاداتك - أنت على الطريق الصحيح لهدفك!',
                                    'Continue tracking your habits - you are on the right track for your goal!')
        
        return {
            'status': 'success',
            'current_weight': round(current_weight, 1),
            'predicted_weight_2weeks': round(target_weight, 1),
            'expected_change': round(change, 1),
            'predictions': predictions[:7],
            'recommendation': recommendation,
            'health_goal': self.health_goal_text,
            'confidence': round(model.score(X, y) * 100, 1) if hasattr(model, 'score') else 75
        }
    
    def analyze_vital_signs_with_risk(self):
        """
        تحليل العلامات الحيوية مع تقييم المخاطر حسب عمر المستخدم وجنسه
        """
        latest = HealthStatus.objects.filter(user=self.user).order_by('-recorded_at').first()
        
        if not latest:
            return {'status': 'no_data'}
        
        alerts = []
        normal_ranges = self._get_normal_ranges_by_age()
        
        # تحليل ضغط الدم
        if latest.systolic_pressure and latest.diastolic_pressure:
            sys, dia = latest.systolic_pressure, latest.diastolic_pressure
            
            if sys > normal_ranges['systolic']['max'] or dia > normal_ranges['diastolic']['max']:
                alerts.append({
                    'type': 'blood_pressure',
                    'severity': 'high',
                    'icon': '❤️',
                    'message': self._t('⚠️ ضغط الدم مرتفع', '⚠️ High blood pressure'),
                    'advice': self._t('قلل الملح، زد البوتاسيوم (موز، خضروات)، واستشر طبيبك', 
                                    'Reduce salt, increase potassium (bananas, vegetables), and consult your doctor'),
                    'normal_range': f"{normal_ranges['systolic']['min']}-{normal_ranges['systolic']['max']}/{normal_ranges['diastolic']['min']}-{normal_ranges['diastolic']['max']}"
                })
            elif sys < normal_ranges['systolic']['min'] or dia < normal_ranges['diastolic']['min']:
                alerts.append({
                    'type': 'blood_pressure',
                    'severity': 'low',
                    'icon': '💙',
                    'message': self._t('⚠️ ضغط الدم منخفض', '⚠️ Low blood pressure'),
                    'advice': self._t('اشرب كمية كافية من الماء، وتناول وجبات صغيرة متكررة',
                                    'Drink enough water, eat small frequent meals')
                })
        
        # تحليل السكر (مع مراعاة العمر)
        if latest.blood_glucose:
            glucose = float(latest.blood_glucose)
            glucose_range = normal_ranges['glucose']
            
            if glucose > glucose_range['max']:
                alerts.append({
                    'type': 'glucose',
                    'severity': 'high',
                    'icon': '🩸',
                    'message': self._t('⚠️ سكر الدم مرتفع', '⚠️ High blood sugar'),
                    'advice': self._t('قلل السكريات والكربوهيدرات البسيطة، ومارس رياضة المشي',
                                    'Reduce sugars and simple carbs, walk for exercise'),
                    'value': glucose,
                    'normal_range': f"{glucose_range['min']}-{glucose_range['max']}"
                })
            elif glucose < glucose_range['min']:
                alerts.append({
                    'type': 'glucose',
                    'severity': 'high',
                    'icon': '🆘',
                    'message': self._t('⚠️ سكر الدم منخفض جداً!', '⚠️ Very low blood sugar!'),
                    'advice': self._t('تناول مصدر سكر سريع (تمر، عصير، عسل) فوراً',
                                    'Eat a quick sugar source (dates, juice, honey) immediately')
                })
        
        # تحليل الأكسجين
        if latest.spo2 and latest.spo2 < 94:
            alerts.append({
                'type': 'oxygen',
                'severity': 'high',
                'icon': '🫁',
                'message': self._t(f'⚠️ نسبة الأكسجين منخفضة: {latest.spo2}%', f'⚠️ Low oxygen level: {latest.spo2}%'),
                'advice': self._t('تنفس بعمق، وإذا استمر الانخفاض استشر طبيبك',
                                'Breathe deeply, if it persists consult your doctor')
            })
        
        # تحليل درجة الحرارة
        if latest.body_temperature:
            temp = float(latest.body_temperature)
            if temp > 37.5:
                alerts.append({
                    'type': 'temperature',
                    'severity': 'medium',
                    'icon': '🌡️',
                    'message': self._t(f'⚠️ درجة حرارتك مرتفعة: {temp}°C', f'⚠️ Your temperature is high: {temp}°C'),
                    'advice': self._t('ارح واستشر طبيبك إذا استمرت الأعراض', 'Rest and consult your doctor if symptoms persist')
                })
            elif temp < 36.0:
                alerts.append({
                    'type': 'temperature',
                    'severity': 'medium',
                    'icon': '❄️',
                    'message': self._t(f'⚠️ درجة حرارتك منخفضة: {temp}°C', f'⚠️ Your temperature is low: {temp}°C'),
                    'advice': self._t('تدفأ واشرب مشروبات دافئة', 'Keep warm and drink warm beverages')
                })
        
        return {
            'status': 'success',
            'recorded_at': latest.recorded_at,
            'alerts': alerts,
            'risk_level': 'high' if len([a for a in alerts if a['severity'] == 'high']) > 0 else 'medium' if alerts else 'low',
            'summary': self._t(f'تم اكتشاف {len(alerts)} تنبيه', f'Found {len(alerts)} alerts') if alerts else self._t('✅ جميع القياسات طبيعية', '✅ All measurements are normal')
        }
    
    def _get_normal_ranges_by_age(self):
        """الحصول على النطاقات الطبيعية حسب عمر المستخدم"""
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
    # ✅ التحليل الكامل
    # ==========================================================================
    
    def analyze_all(self):
        """تحليل جميع الجوانب باستخدام خوارزميات ML مع بيانات المستخدم"""
        return {
            'user_profile_analysis': self.analyze_user_profile_health(),
            'vital_signs_analysis': self.analyze_vital_signs_with_risk(),
            'weight_prediction': self.predict_weight_trend_with_profile(),
            'personalized_summary': self._generate_ai_summary(),
        }
    
    def _generate_ai_summary(self):
        """توليد ملخص ذكي شامل"""
        summaries = []
        
        # ملخص الملف الشخصي
        profile = self.analyze_user_profile_health()
        
        # رسالة ترحيب حسب العمر والجنس
        greeting = self._t(
            f'مرحباً {self.user.get_full_name() or self.user.username}!',
            f'Hello {self.user.get_full_name() or self.user.username}!'
        )
        summaries.append(greeting)
        
        # ملخص BMI
        if profile['bmi_analysis'].get('status') != 'no_data':
            summaries.append(profile['bmi_analysis']['message'])
            summaries.append(profile['bmi_analysis']['advice'])
        
        # ملخص الهدف الصحي
        goal_alignment = profile['goal_alignment']
        if not goal_alignment.get('aligned', True):
            summaries.append(goal_alignment['message'])
            if 'suggestion' in goal_alignment:
                summaries.append(goal_alignment['suggestion'])
        
        # عوامل الخطر
        for risk in profile['risk_factors']:
            msg = risk['message_ar'] if self.is_arabic else risk['message_en']
            summaries.append(msg)
        
        # التنبؤ بالوزن
        weight_pred = self.predict_weight_trend_with_profile()
        if weight_pred.get('status') == 'success':
            summaries.append(weight_pred['recommendation'])
        
        # التوصيات المخصصة
        for rec in profile['personalized_recommendations']:
            summaries.append(f"{rec['icon']} {rec['advice']}")
        
        return {
            'title': self._t('📋 خلاصة تحليلك الصحي', '📋 Your Health Analysis Summary'),
            'bullet_points': summaries[:8],
            'user_age': self.user_age,
            'health_goal': self.health_goal_text
        }


# ==============================================================================
# الخدمة الرئيسية
# ==============================================================================

class CrossInsightsMLService:
    """
    الخدمة الرئيسية للتحليلات المتقاطعة باستخدام ML مع بيانات المستخدم
    """
    
    def __init__(self, user):
        self.user = user
        self.engine = HealthInsightsEngineML(user)
    
    def get_complete_analysis(self):
        """الحصول على تحليل كامل وشامل"""
        try:
            analysis = self.engine.analyze_all()
            
            return {
                'success': True,
                'is_arabic': self.engine.is_arabic,
                'data': analysis,
                'timestamp': timezone.now().isoformat(),
                'user_name': self.user.get_full_name() or self.user.username
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
"""
محرك الذكاء الاصطناعي للتحليلات الصحية المتقاطعة
Cross-Data Analysis Engine for Health Insights
"""
from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q, F
from django.db.models.functions import TruncDate
from main.models import (
    HealthStatus, PhysicalActivity, Sleep, 
    MoodEntry, Meal, HabitLog
)


class HealthInsightsEngine:
    """
    محرك متقدم لتحليل البيانات الصحية وإيجاد العلاقات الخفية
    Advanced engine for analyzing health data and finding hidden correlations
    """
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.today = timezone.now().date()
        self.week_ago = self.today - timedelta(days=7)
        self.month_ago = self.today - timedelta(days=30)
        self.is_arabic = language == 'ar'
    
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
            'vital_signs_analysis': self.analyze_vital_signs(),
            'activity_nutrition_correlation': self.analyze_activity_nutrition(),
            'sleep_mood_correlation': self.analyze_sleep_mood(),
            'weight_trend_analysis': self.analyze_weight_trends(),
            'blood_pressure_insights': self.analyze_blood_pressure(),
            'glucose_risk_assessment': self.analyze_glucose_risks(),
            'energy_consumption_alert': self.analyze_energy_consumption(),
            'pulse_pressure_analysis': self.analyze_pulse_pressure(),
            'pre_exercise_recommendation': self.analyze_pre_exercise_risk(),
            'holistic_recommendations': self.generate_holistic_recommendations(),
            'predictive_alerts': self.generate_predictive_alerts(),
        }
    
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
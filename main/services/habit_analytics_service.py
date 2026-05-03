"""
خدمة تحليلات الأدوية - تركز على التفاعلات والآثار الجانبية
"""

import numpy as np
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
import warnings
warnings.filterwarnings('ignore')

from ..models import (
    HabitDefinition, HabitLog, UserMedication
)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


# ============================================================
# قاعدة بيانات التفاعلات الدوائية والآثار الجانبية
# ============================================================

DRUG_INTERACTIONS = {
    # الأدوية المتفاعلة مع بعضها
    'ibuprofen': {
        'interacts_with': ['warfarin', 'aspirin', 'lisinopril', 'metformin', 'furosemide', 'sertraline', 'fluoxetine'],
        'severity': 'high',
        'description_ar': 'يزيد خطر النزيف ومشاكل الكلى',
        'description_en': 'Increases risk of bleeding and kidney problems'
    },
    'warfarin': {
        'interacts_with': ['ibuprofen', 'aspirin', 'paracetamol', 'amiodarone', 'antibiotics', 'sertraline'],
        'severity': 'high',
        'description_ar': 'يزيد خطر النزيف بشكل كبير',
        'description_en': 'Significantly increases bleeding risk'
    },
    'aspirin': {
        'interacts_with': ['ibuprofen', 'warfarin', 'heparin', 'sertraline', 'fluoxetine'],
        'severity': 'high',
        'description_ar': 'يزيد خطر النزيف',
        'description_en': 'Increases bleeding risk'
    },
    'metformin': {
        'interacts_with': ['furosemide', 'cimetidine', 'ibuprofen'],
        'severity': 'medium',
        'description_ar': 'قد يؤثر على وظائف الكلى',
        'description_en': 'May affect kidney function'
    },
    'lisinopril': {
        'interacts_with': ['ibuprofen', 'potassium_supplements', 'spironolactone'],
        'severity': 'medium',
        'description_ar': 'قد يسبب ارتفاع البوتاسيوم',
        'description_en': 'May cause high potassium levels'
    },
    'sertraline': {
        'interacts_with': ['ibuprofen', 'aspirin', 'warfarin', 'tramadol', 'lithium'],
        'severity': 'high',
        'description_ar': 'يزيد خطر النزيف ومتلازمة السيروتونين',
        'description_en': 'Increases risk of bleeding and serotonin syndrome'
    },
    'fluoxetine': {
        'interacts_with': ['ibuprofen', 'aspirin', 'tramadol', 'lithium'],
        'severity': 'high',
        'description_ar': 'يزيد خطر النزيف ومتلازمة السيروتونين',
        'description_en': 'Increases risk of bleeding and serotonin syndrome'
    },
    'atorvastatin': {
        'interacts_with': ['grapefruit', 'clarithromycin', 'itraconazole', 'cyclosporine'],
        'severity': 'medium',
        'description_ar': 'يزيد خطر الآلام العضلية',
        'description_en': 'Increases risk of muscle pain'
    },
    'simvastatin': {
        'interacts_with': ['grapefruit', 'clarithromycin', 'cyclosporine'],
        'severity': 'medium',
        'description_ar': 'يزيد خطر الآلام العضلية',
        'description_en': 'Increases risk of muscle pain'
    },
    'amlodipine': {
        'interacts_with': ['grapefruit', 'simvastatin', 'clarithromycin'],
        'severity': 'medium',
        'description_ar': 'قد يسبب انخفاض الضغط',
        'description_en': 'May cause low blood pressure'
    },
    'tramadol': {
        'interacts_with': ['antidepressants', 'alcohol', 'benzodiazepines', 'carbamazepine'],
        'severity': 'high',
        'description_ar': 'يزيد خطر التشنجات ومتلازمة السيروتونين',
        'description_en': 'Increases risk of seizures and serotonin syndrome'
    },
    'levothyroxine': {
        'interacts_with': ['calcium', 'iron', 'aluminum_hydroxide', 'amiodarone'],
        'severity': 'medium',
        'description_ar': 'يقلل امتصاص الدواء',
        'description_en': 'Reduces drug absorption'
    },
    'omeprazole': {
        'interacts_with': ['clopidogrel', 'digoxin', 'methotrexate'],
        'severity': 'medium',
        'description_ar': 'يقلل فعالية الأدوية الأخرى',
        'description_en': 'Reduces effectiveness of other medications'
    }
}

# الآثار الجانبية الشائعة
COMMON_SIDE_EFFECTS = {
    'ibuprofen': ['غثيان', 'حرقة المعدة', 'دوخة', 'احتباس السوائل', 'ارتفاع الضغط'],
    'metformin': ['غثيان', 'إسهال', 'انتفاخ', 'طعم معدني', 'فقدان الشهية'],
    'sertraline': ['غثيان', 'أرق', 'جفاف الفم', 'دوخة', 'زيادة الوزن'],
    'fluoxetine': ['غثيان', 'أرق', 'قلق', 'صداع', 'جفاف الفم'],
    'lisinopril': ['سعال جاف', 'دوخة', 'صداع', 'انخفاض الضغط', 'ارتفاع البوتاسيوم'],
    'amlodipine': ['تورم الأطراف', 'صداع', 'دوخة', 'احمرار الوجه', 'خفقان'],
    'atorvastatin': ['آلام عضلية', 'ضعف عام', 'اضطرابات هضمية', 'ارتفاع إنزيمات الكبد'],
    'simvastatin': ['آلام عضلية', 'ضعف عام', 'اضطرابات هضمية'],
    'warfarin': ['نزيف', 'كدمات', 'بول دموي', 'براز أسود'],
    'aspirin': ['تهيج المعدة', 'حرقة', 'غثيان', 'نزيف'],
    'levothyroxine': ['خفقان', 'عصبية', 'أرق', 'رعشة', 'فقدان الوزن'],
    'tramadol': ['غثيان', 'دوخة', 'نعاس', 'إمساك', 'صداع']
}

# أوقات التناول الموصى بها
SUGGESTED_TIMES = {
    'metformin': {'time_ar': 'مع الوجبات', 'time_en': 'With meals', 'reason_ar': 'لتقليل اضطرابات المعدة', 'reason_en': 'To reduce stomach upset'},
    'statin': {'time_ar': 'مساءً', 'time_en': 'Evening', 'reason_ar': 'الكوليسترول يُنتج ليلاً', 'reason_en': 'Cholesterol is produced at night'},
    'pril': {'time_ar': 'صباحاً', 'time_en': 'Morning', 'reason_ar': 'لتجنب انخفاض الضغط ليلاً', 'reason_en': 'To avoid night-time low blood pressure'},
    'dipine': {'time_ar': 'صباحاً', 'time_en': 'Morning', 'reason_ar': 'للحفاظ على ضغط دم منتظم', 'reason_en': 'To maintain regular blood pressure'},
    'ibuprofen': {'time_ar': 'مع الوجبات', 'time_en': 'With meals', 'reason_ar': 'لتقليل تهيج المعدة', 'reason_en': 'To reduce stomach irritation'},
    'sertraline': {'time_ar': 'صباحاً', 'time_en': 'Morning', 'reason_ar': 'لتجنب الأرق', 'reason_en': 'To avoid insomnia'},
    'fluoxetine': {'time_ar': 'صباحاً', 'time_en': 'Morning', 'reason_ar': 'لتجنب الأرق', 'reason_en': 'To avoid insomnia'},
    'levothyroxine': {'time_ar': 'صباحاً على الريق', 'time_en': 'Morning on empty stomach', 'reason_ar': 'للحصول على أفضل امتصاص', 'reason_en': 'For best absorption'}
}


class HabitMedicationAnalyticsService:
    """خدمة تحليلات الأدوية - تركز على التفاعلات والآثار الجانبية"""
    
    def __init__(self, user, language='ar'):
        self.user = user
        self.language = language
        self.is_arabic = language.startswith('ar')
        self.today = timezone.now()
        self.today_date = self.today.date()
        
    def _t(self, ar_text, en_text):
        """ترجمة النصوص"""
        return ar_text if self.is_arabic else en_text
    
    def _is_medication(self, habit):
        """تحديد إذا كانت العادة دواء"""
        text = (habit.name + ' ' + (habit.description or '')).lower()
        medication_keywords = ['ibuprofen', 'metformin', 'lisinopril', 'amlodipine', 'sertraline', 
                               'fluoxetine', 'atorvastatin', 'simvastatin', 'warfarin', 'aspirin',
                               'tramadol', 'levothyroxine', 'omeprazole', 'دواء', 'medication',
                               'mg', 'ملجم', 'pill', 'tablet', 'capsule']
        for keyword in medication_keywords:
            if keyword in text:
                return True
        return False
    
    def get_summary(self):
        """ملخص بسيط للعادات والأدوية"""
        all_habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        medications = [h for h in all_habits if self._is_medication(h)]
        habits = [h for h in all_habits if not self._is_medication(h)]
        
        habit_logs = HabitLog.objects.filter(
            habit__user=self.user,
            log_date__gte=self.today - timedelta(days=7)
        )
        
        total_habits = len(habits)
        completed_today = habit_logs.filter(log_date=self.today_date, is_completed=True).count()
        completion_rate = round((completed_today / total_habits) * 100) if total_habits > 0 else 0
        
        return {
            'total_habits': total_habits,
            'total_medications': len(medications),
            'completion_rate': completion_rate,
            'streak': self._calculate_streak(habit_logs, habits)
        }
    
    def _calculate_streak(self, habit_logs, habits):
        """حساب السلسلة"""
        if not habits:
            return 0
        streak = 0
        current_date = self.today_date
        habit_ids = [h.id for h in habits]
        for _ in range(10):
            day_logs = habit_logs.filter(log_date=current_date, habit_id__in=habit_ids)
            if day_logs.exists() and day_logs.filter(is_completed=True).exists():
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        return streak
    
    def analyze_medications(self):
        """تحليل متعمق للأدوية: التفاعلات، الآثار الجانبية، أوقات التناول"""
        all_habits = HabitDefinition.objects.filter(user=self.user, is_active=True)
        medications = [h for h in all_habits if self._is_medication(h)]
        
        if not medications:
            return {'medications': [], 'interactions': [], 'has_medications': False}
        
        # تحليل كل دواء
        analyzed_meds = []
        for med in medications:
            med_name_lower = med.name.lower()
            
            # البحث عن الآثار الجانبية
            side_effects = []
            for drug_name, effects in COMMON_SIDE_EFFECTS.items():
                if drug_name in med_name_lower:
                    side_effects = effects
                    break
            
            # البحث عن وقت التناول الموصى به
            suggested_time = None
            for drug_name, time_info in SUGGESTED_TIMES.items():
                if drug_name in med_name_lower:
                    suggested_time = {
                        'time': self._t(time_info['time_ar'], time_info['time_en']),
                        'reason': self._t(time_info['reason_ar'], time_info['reason_en'])
                    }
                    break
            
            analyzed_meds.append({
                'id': med.id,
                'name': med.name,
                'description': med.description,
                'side_effects': side_effects,
                'suggested_time': suggested_time
            })
        
        # تحليل التفاعلات بين الأدوية
        interactions = []
        for i in range(len(analyzed_meds)):
            for j in range(i + 1, len(analyzed_meds)):
                med1_name = analyzed_meds[i]['name'].lower()
                med2_name = analyzed_meds[j]['name'].lower()
                
                for drug, info in DRUG_INTERACTIONS.items():
                    if drug in med1_name:
                        for interact in info['interacts_with']:
                            if interact in med2_name:
                                interactions.append({
                                    'medication1': analyzed_meds[i]['name'],
                                    'medication2': analyzed_meds[j]['name'],
                                    'severity': info['severity'],
                                    'description': self._t(info['description_ar'], info['description_en'])
                                })
                    if drug in med2_name:
                        for interact in info['interacts_with']:
                            if interact in med1_name:
                                interactions.append({
                                    'medication1': analyzed_meds[j]['name'],
                                    'medication2': analyzed_meds[i]['name'],
                                    'severity': info['severity'],
                                    'description': self._t(info['description_ar'], info['description_en'])
                                })
        
        # إزالة التكرارات
        unique_interactions = []
        seen = set()
        for inter in interactions:
            key = f"{inter['medication1']}_{inter['medication2']}"
            if key not in seen:
                seen.add(key)
                unique_interactions.append(inter)
        
        return {
            'medications': analyzed_meds,
            'interactions': unique_interactions[:10],
            'has_medications': True,
            'total_medications': len(analyzed_meds),
            'interactions_count': len(unique_interactions)
        }
    
    def get_recommendations(self, summary=None, medications_analysis=None):
        """توليد توصيات عامة"""
        if summary is None:
            summary = self.get_summary()
        if medications_analysis is None:
            medications_analysis = self.analyze_medications()
        
        recommendations = []
        
        # توصيات للعادات
        if summary['completion_rate'] < 70 and summary['completion_rate'] > 0:
            recommendations.append({
                'priority': 'high',
                'icon': '📋',
                'title': self._t('حافظ على عاداتك اليومية', 'Keep Your Daily Habits'),
                'description': self._t(f'التزامك الحالي {summary["completion_rate"]}%', f'Your current adherence is {summary["completion_rate"]}%'),
                'quick_tip': self._t('الاستمرارية أهم من الكمية', 'Consistency is more important than quantity')
            })
        
        # توصيات للأدوية والتفاعلات
        if medications_analysis['has_medications']:
            if medications_analysis['interactions_count'] > 0:
                recommendations.append({
                    'priority': 'high',
                    'icon': '⚠️',
                    'title': self._t('تفاعلات دوائية محتملة', 'Potential Drug Interactions'),
                    'description': self._t(f'تم اكتشاف {medications_analysis["interactions_count"]} تفاعل محتمل بين أدويتك', 
                                           f'Found {medications_analysis["interactions_count"]} potential interactions between your medications'),
                    'quick_tip': self._t('استشر طبيبك حول هذه التفاعلات', 'Consult your doctor about these interactions')
                })
            else:
                recommendations.append({
                    'priority': 'low',
                    'icon': '✅',
                    'title': self._t('لا توجد تفاعلات دوائية خطيرة', 'No Serious Drug Interactions'),
                    'description': self._t('لم نكتشف تفاعلات خطيرة بين أدويتك الحالية', 'No serious interactions detected between your current medications'),
                    'quick_tip': self._t('استمر في متابعة أدويتك', 'Continue monitoring your medications')
                })
        
        # توصية عامة للسلسلة
        if summary['streak'] == 1:
            recommendations.append({
                'priority': 'medium',
                'icon': '🔥',
                'title': self._t('بداية جيدة! استمر', 'Good Start! Keep Going'),
                'description': self._t('لديك سلسلة يوم واحد، حاول الوصول إلى 7 أيام', 'You have a 1-day streak, try to reach 7 days'),
                'quick_tip': self._t('كل يوم مهم في رحلتك', 'Every day matters in your journey')
            })
        
        return recommendations
    
    def get_predictions(self, summary=None):
        """توقعات بسيطة"""
        if summary is None:
            summary = self.get_summary()
        
        predictions = []
        
        if summary['streak'] > 0:
            predicted_streak = min(7, summary['streak'] + 2)
            predictions.append({
                'icon': '🔥',
                'label': self._t('السلسلة المتوقعة', 'Expected Streak'),
                'value': f"{predicted_streak} {self._t('أيام', 'days')}",
                'trend': 'up'
            })
        
        if summary['completion_rate'] < 100:
            future_rate = min(100, summary['completion_rate'] + 15)
            predictions.append({
                'icon': '📈',
                'label': self._t('معدل الإنجاز المتوقع', 'Expected Completion'),
                'value': f"{future_rate}%",
                'trend': 'up'
            })
        
        return predictions
    
    def get_complete_analysis(self):
        """التحليل الكامل"""
        summary = self.get_summary()
        medications_analysis = self.analyze_medications()
        
        return {
            'summary': summary,
            'medications_analysis': medications_analysis,
            'recommendations': self.get_recommendations(summary, medications_analysis),
            'predictions': self.get_predictions(summary)
        }


# ==============================================================================
# دوال API
# ==============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def habit_medication_analytics_api(request):
    """API لتحليلات الأدوية - التفاعلات والآثار الجانبية"""
    language = request.GET.get('lang', 'ar')
    
    try:
        service = HabitMedicationAnalyticsService(request.user, language=language)
        result = service.get_complete_analysis()
        return Response({
            'success': True,
            'data': result,
            'is_arabic': language == 'ar'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'message': 'حدث خطأ في تحليل الأدوية' if language == 'ar' else 'Error analyzing medications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
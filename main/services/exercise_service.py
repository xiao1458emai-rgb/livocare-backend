# main/services/analytics/exercise_service.py
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Avg, Sum, Count
import joblib
import os
from ..models import (
    HealthStatus, Sleep, MoodEntry, Meal, PhysicalActivity, 
    HabitLog, EnvironmentData, FoodItem
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
    
    def _t(self, ar_text, en_text, **kwargs):
        """
        ترجمة النصوص حسب اللغة المحددة
        Translate texts based on selected language
        """
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
    
    def collect_all_health_data(self, days=30):
        """جمع كل البيانات الصحية للمستخدم"""
        
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
        
        # 7. بيانات الطقس (خارجية)
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
            
            # تحقق من وجود الحقل المناسب
            if hasattr(EnvironmentData, 'recorded_at'):
                field_name = 'recorded_at'
            elif hasattr(EnvironmentData, 'date'):
                field_name = 'date'
            else:
                # إذا لم يوجد أي حقل زمني، أرجع قائمة فارغة
                print("⚠️ EnvironmentData model has no date/time field")
                return []
            
            # بناء الفلتر ديناميكياً
            filter_kwargs = {
                'user': self.user,
                f'{field_name}__range': [start_date, end_date]
            }
            
            return EnvironmentData.objects.filter(**filter_kwargs).order_by(field_name)
            
        except Exception as e:
            print(f"⚠️ Error fetching weather data: {e}")
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
        
        # إنشاء DataFrame زمني
        dates = pd.date_range(
            start=raw_data['health'][0].recorded_at.date() if raw_data['health'] else timezone.now().date() - timedelta(days=30),
            end=timezone.now().date(),
            freq='D'
        )
        
        df = pd.DataFrame(index=dates)
        
        # إضافة الميزات
        df['day_of_week'] = df.index.dayofweek
        df['month'] = df.index.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # تجميع البيانات اليومية
        daily_stats = {}
        
        for date in dates:
            date_str = date.strftime('%Y-%m-%d')
            daily_stats[date_str] = self._calculate_daily_stats(raw_data, date)
        
        # إضافة الإحصائيات إلى DataFrame
        for col in ['weight', 'sleep_hours', 'sleep_quality', 'mood_score', 
                   'calories', 'protein', 'activity_minutes', 'habits_completed',
                   'avg_temp', 'humidity']:
            df[col] = [daily_stats[d.strftime('%Y-%m-%d')].get(col, 0) for d in dates]
        
        # إضافة features متقدمة
        df['weight_change'] = df['weight'].diff()
        df['sleep_7d_avg'] = df['sleep_hours'].rolling(window=7, min_periods=1).mean()
        df['calories_7d_avg'] = df['calories'].rolling(window=7, min_periods=1).mean()
        df['mood_3d_avg'] = df['mood_score'].rolling(window=3, min_periods=1).mean()
        
        return df
    
    def _calculate_daily_stats(self, raw_data, date):
        """حساب الإحصائيات اليومية"""
        stats = {}
        
        # الوزن (آخر قياس في اليوم)
        weight_records = [h for h in raw_data['health'] 
                         if h.recorded_at.date() == date and h.weight_kg]
        if weight_records:
            stats['weight'] = weight_records[-1].weight_kg
        
        # النوم
        sleep_records = [s for s in raw_data['sleep'] 
                        if s.sleep_start.date() == date and s.sleep_end]
        if sleep_records:
            total_sleep = 0
            total_quality = 0
            for sleep in sleep_records:
                duration = (sleep.sleep_end - sleep.sleep_start).seconds / 3600
                total_sleep += duration
                if sleep.quality_rating:
                    total_quality += sleep.quality_rating
            stats['sleep_hours'] = total_sleep
            stats['sleep_quality'] = total_quality / len(sleep_records) if sleep_records else 0
        
        # المزاج (تحويل إلى نقاط)
        mood_records = [m for m in raw_data['mood'] if m.entry_time.date() == date]
        if mood_records:
            mood_scores = {
                'excellent': 5,
                'good': 4,
                'neutral': 3,
                'stressed': 2,
                'anxious': 2,
                'sad': 1
            }
            stats['mood_score'] = mood_scores.get(mood_records[-1].mood, 3)
        
        # التغذية
        meal_records = [m for m in raw_data['nutrition'] if m.meal_time.date() == date]
        if meal_records:
            stats['calories'] = sum(m.total_calories or 0 for m in meal_records)
            stats['protein'] = sum(m.total_protein or 0 for m in meal_records)
        
        # النشاط
        activity_records = [a for a in raw_data['activity'] if a.start_time.date() == date]
        if activity_records:
            stats['activity_minutes'] = sum(a.duration_minutes or 0 for a in activity_records)
        
        # العادات
        habit_records = [h for h in raw_data['habits'] if h.log_date == date]
        stats['habits_completed'] = len(habit_records)
        
        # الطقس
        weather_records = [w for w in raw_data['weather'] if w.recorded_at.date() == date]
        if weather_records:
            stats['avg_temp'] = np.mean([w.temperature for w in weather_records])
            stats['humidity'] = np.mean([w.humidity for w in weather_records])
        
        return stats
    
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
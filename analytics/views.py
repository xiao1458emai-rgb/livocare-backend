# analytics/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .services import SleepAnalyticsService, HabitAnalyticsService, MoodAnalyticsService, NutritionAnalyticsService
from .models import SleepInsight, HabitInsight, MoodInsight, NutritionInsight
from .serializers import SleepInsightSerializer, HabitInsightSerializer, MoodInsightSerializer, NutritionInsightSerializer

# ✅ استيراد النماذج من main
from main.models import PhysicalActivity, Sleep, HabitDefinition, HabitLog

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_activity_insights(request):
    """الحصول على تحليلات الأنشطة لآخر 7 أيام"""
    try:
        # جلب آخر 7 أيام من الأنشطة
        week_ago = timezone.now() - timedelta(days=7)
        activities = PhysicalActivity.objects.filter(
            user=request.user,
            start_time__gte=week_ago
        )
        
        # تحليل بسيط
        total_duration = sum(a.duration_minutes or 0 for a in activities)
        total_calories = sum(a.calories_burned or 0 for a in activities)
        
        # توليد توصيات
        recommendations = []
        
        if total_duration == 0:
            recommendations.append("🚶‍♂️ لم تقم بأي نشاط هذا الأسبوع. ابدأ بالمشي لمدة 15 دقيقة!")
        elif total_duration < 150:
            recommendations.append("💪 أنت في الطريق الصحيح! حاول زيادة النشاط إلى 150 دقيقة أسبوعياً")
        else:
            recommendations.append("🌟 ممتاز! أنت تحقق النشاط الموصى به أسبوعياً")
        
        # نصائح إضافية
        if activities.count() < 3:
            recommendations.append("📅 حاول توزيع نشاطك على 3 أيام على الأقل في الأسبوع")
        
        return Response({
            'status': 'success',
            'data': {
                'total_duration': total_duration,
                'total_calories': total_calories,
                'activities_count': activities.count(),
                'average_duration': round(total_duration / activities.count(), 1) if activities.count() > 0 else 0,
                'recommendations': recommendations
            }
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_model_info(request):
    """معرفة النماذج المتاحة في main.models"""
    import inspect
    from main import models
    
    model_classes = []
    for name, obj in inspect.getmembers(models):
        if inspect.isclass(obj) and hasattr(obj, '_meta') and not name.startswith('_'):
            model_classes.append({
                'name': name,
                'table': obj._meta.db_table if hasattr(obj._meta, 'db_table') else 'N/A'
            })
    
    return Response({
        'available_models': model_classes,
        'count': len(model_classes)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sleep_insights(request):
    """الحصول على تحليلات النوم"""
    try:
        print("="*60)
        print(f"👤 جلب تحليلات النوم للمستخدم: {request.user.username}")
        print(f"📅 وقت الطلب: {timezone.now()}")
        
        # جلب جميع سجلات النوم للمستخدم
        all_sleep = Sleep.objects.filter(user=request.user)
        print(f"📊 إجمالي سجلات النوم: {all_sleep.count()}")
        
        # جلب سجلات آخر 7 أيام (باستخدام sleep_end)
        week_ago = timezone.now() - timedelta(days=7)
        recent_sleep = Sleep.objects.filter(
            user=request.user,
            sleep_end__gte=week_ago
        ).order_by('-sleep_start')
        
        print(f"📊 سجلات آخر 7 أيام: {recent_sleep.count()}")
        
        # عرض تفاصيل كل سجل
        total_hours_calculated = 0
        for i, sleep in enumerate(recent_sleep):
            duration = float(sleep.duration_hours) if sleep.duration_hours else 0
            total_hours_calculated += duration
            print(f"\n   📝 سجل {i+1}:")
            print(f"      🆔 ID: {sleep.id}")
            print(f"      🕐 البدء: {sleep.sleep_start}")
            print(f"      🕐 الانتهاء: {sleep.sleep_end}")
            print(f"      ⏱️ المدة: {duration} ساعات")
            print(f"      ⭐ الجودة: {sleep.quality_rating}")
            print(f"      📝 ملاحظات: {sleep.notes}")
        
        print(f"\n📊 المجموع اليدوي: {total_hours_calculated} ساعة")
        
        # إجبار توليد تحليلات جديدة
        print("\n🔄 توليد تحليلات جديدة (إجبارياً)...")
        service = SleepAnalyticsService(request.user)
        latest_insight = service.generate_weekly_insights()
        print("✅ تم توليد التحليلات الجديدة")
        
        serializer = SleepInsightSerializer(latest_insight)
        print(f"\n📤 البيانات المرسلة:")
        print(f"   ⏱️ total_hours: {serializer.data.get('weekly_total_hours')}")
        print(f"   📊 avg_hours: {serializer.data.get('weekly_avg_hours')}")
        print(f"   ⭐ avg_quality: {serializer.data.get('weekly_avg_quality')}")
        print(f"   📈 trend: {serializer.data.get('trend')}")
        print("="*60)
        
        return Response(serializer.data)
        
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_habit_insights(request):
    """الحصول على تحليلات العادات الذكية"""
    try:
        print("="*60)
        print(f"👤 جلب تحليلات العادات للمستخدم: {request.user.username}")
        print(f"📅 وقت الطلب: {timezone.now()}")
        
        # ✅ تشخيص: جلب جميع العادات من قاعدة البيانات
        all_habits = HabitDefinition.objects.filter(user=request.user)
        print(f"\n📋 جميع العادات في DB ({all_habits.count()}):")
        for habit in all_habits:
            print(f"   - ID: {habit.id}, الاسم: '{habit.name}', الوصف: '{habit.description}'")
        
        # ✅ تشخيص: جلب سجلات اليوم
        today = timezone.now().date()
        today_logs = HabitLog.objects.filter(
            habit__user=request.user,
            log_date=today,
            is_completed=True
        )
        print(f"\n✅ سجلات اليوم ({today_logs.count()}):")
        for log in today_logs:
            print(f"   - عادة ID: {log.habit.id}, تم: {log.is_completed}")
        
        # 🔥 إجبار توليد تحليلات جديدة دائماً
        print("\n🔄 توليد تحليلات جديدة للعادات (إجبارياً)...")
        service = HabitAnalyticsService(request.user)
        latest_insight = service.generate_insights()
        print("✅ تم توليد التحليلات الجديدة")
        
        serializer = HabitInsightSerializer(latest_insight)
        print(f"\n📤 البيانات المرسلة:")
        print(f"   📋 total_habits: {serializer.data.get('total_habits')}")
        print(f"   ✅ completed_today: {serializer.data.get('completed_today')}")
        print(f"   📊 completion_rate: {serializer.data.get('completion_rate')}")
        print("="*60)
        
        return Response(serializer.data)
        
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_mood_insights(request):
    """الحصول على تحليلات المزاج الذكية"""
    try:
        print("="*60)
        print(f"👤 جلب تحليلات المزاج للمستخدم: {request.user.username}")
        print(f"📅 وقت الطلب: {timezone.now()}")
        
        # ✅ تشخيص: جلب جميع سجلات المزاج
        from main.models import MoodEntry
        all_entries = MoodEntry.objects.filter(user=request.user)
        print(f"\n📋 جميع سجلات المزاج: {all_entries.count()}")
        for entry in all_entries:
            print(f"   - ID: {entry.id}, المزاج: {entry.mood}, الوقت: {entry.entry_time}")
        
        # 🔥 إجبار توليد تحليلات جديدة دائماً (بدون التحقق من التاريخ)
        print("\n🔄 توليد تحليلات جديدة للمزاج (إجبارياً)...")
        service = MoodAnalyticsService(request.user)
        latest_insight = service.generate_insights()
        print("✅ تم توليد التحليلات الجديدة")
        
        serializer = MoodInsightSerializer(latest_insight)
        print(f"\n📤 البيانات المرسلة:")
        print(f"   📊 total_entries: {serializer.data.get('total_entries')}")
        print(f"   📅 total_days: {serializer.data.get('total_days')}")
        print(f"   😊 most_common_mood: {serializer.data.get('most_common_mood')}")
        print(f"   📈 trend: {serializer.data.get('trend')}")
        print("="*60)
        
        return Response(serializer.data)
        
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nutrition_insights(request):
    """الحصول على تحليلات التغذية الذكية"""
    try:
        print("="*60)
        print(f"👤 جلب تحليلات التغذية للمستخدم: {request.user.username}")
        print(f"📅 وقت الطلب: {timezone.now()}")
        
        # ✅ تشخيص: جلب جميع الوجبات
        from main.models import Meal, FoodItem
        
        meals = Meal.objects.filter(user=request.user)
        print(f"\n🍽️ جميع الوجبات: {meals.count()}")
        
        total_calories = 0
        for meal in meals:
            food_items = FoodItem.objects.filter(meal=meal)
            meal_calories = sum(item.calories or 0 for item in food_items)
            total_calories += meal_calories
            print(f"   - وجبة {meal.id}: {meal.meal_type}, {meal_calories} سعرة")
        
        print(f"\n🔥 إجمالي السعرات: {total_calories}")
        
        # 🔥 إجبار توليد تحليلات جديدة
        print("\n🔄 توليد تحليلات جديدة للتغذية (إجبارياً)...")
        service = NutritionAnalyticsService(request.user)
        latest_insight = service.generate_insights()
        print("✅ تم توليد التحليلات الجديدة")
        
        serializer = NutritionInsightSerializer(latest_insight)
        print(f"\n📤 البيانات المرسلة:")
        print(f"   🍽️ total_meals: {serializer.data.get('total_meals')}")
        print(f"   🔥 avg_calories: {serializer.data.get('avg_calories')}")
        print(f"   🥩 avg_protein: {serializer.data.get('avg_protein')}")
        print(f"   🍚 avg_carbs: {serializer.data.get('avg_carbs')}")
        print(f"   🫒 avg_fat: {serializer.data.get('avg_fat')}")
        print(f"   📊 meal_distribution: {serializer.data.get('meal_distribution')}")
        print("="*60)
        
        return Response(serializer.data)
        
    except Exception as e:
        print(f"❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)
# analytics/views.py - أضف هذا في نهاية الملف
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_advanced_analytics(request):
    """تحليلات صحية متقدمة باستخدام التعلم الآلي"""
    try:
        print("="*60)
        print(f"🔬 جلب التحليلات المتقدمة للمستخدم: {request.user.username}")
        
        # ✅ تشخيص مفصل
        import inspect
        from main.services.exercise_service import AdvancedHealthAnalytics
        
        # 1. المسار الفعلي للملف
        file_path = inspect.getfile(AdvancedHealthAnalytics)
        print(f"📁 الملف المستخدم: {file_path}")
        
        # 2. قراءة الملف والبحث عن الدالة
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'def get_comprehensive_analytics' in content:
                print("✅ الدالة 'get_comprehensive_analytics' موجودة في الملف!")
                # اعرض الأسطر المحيطة بالدالة
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'def get_comprehensive_analytics' in line:
                        print(f"   السطر {i+1}: {line}")
                        print(f"   السطر {i+2}: {lines[i+1] if i+1 < len(lines) else ''}")
                        print(f"   السطر {i+3}: {lines[i+2] if i+2 < len(lines) else ''}")
                        break
            else:
                print("❌ الدالة 'get_comprehensive_analytics' غير موجودة في الملف!")
                print("📄 آخر 500 حرف من الملف:")
                print(content[-500:])
        
        # 3. إنشاء كائن
        analytics_service = AdvancedHealthAnalytics(request.user)
        
        # 4. عرض الدوال المتاحة في الكائن
        methods = dir(analytics_service)
        print(f"📋 الدوال المتاحة في الكائن ({len(methods)}):")
        relevant_methods = [m for m in methods if not m.startswith('_')]
        for method in sorted(relevant_methods):
            print(f"   - {method}")
        
        # 5. محاولة استدعاء الدالة
        if hasattr(analytics_service, 'get_comprehensive_analytics'):
            data = analytics_service.get_comprehensive_analytics()
            print(f"✅ تم استدعاء الدالة بنجاح")
        else:
            print("❌ الدالة غير موجودة في الكائن!")
            # محاولة استدعاء دوال بديلة
            if hasattr(analytics_service, 'generate_smart_recommendations'):
                print("⚠️ محاولة استخدام generate_smart_recommendations بدلاً من ذلك")
                recommendations = analytics_service.generate_smart_recommendations()
                data = {'recommendations': recommendations}
            else:
                return Response({'error': 'لا توجد دوال تحليل متاحة'}, status=500)
        
        return Response({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)
# ==============================================================================
# 🗑️ حذف كل رسائل الدردشة
# ==============================================================================

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_chat_logs(request):
    """حذف كل رسائل الدردشة للمستخدم الحالي"""
    try:
        # ✅ استيراد ChatLog من main.models
        from main.models import ChatLog
        
        deleted_count = ChatLog.objects.filter(user=request.user).delete()[0]
        
        return Response({
            'success': True,
            'message': f'✅ تم حذف {deleted_count} رسالة بنجاح',
            'deleted_count': deleted_count
        }, status=200)
        
    except Exception as e:
        print(f"❌ Error clearing chat logs: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
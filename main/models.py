
# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

# Create your models here.

# ==============================================================================
# 1. نموذج: المستخدم (CustomUser) - أساس كل شيء
# ==============================================================================
# backend/users/models.py

# users/models.py أو main/models.py

class CustomUser(AbstractUser):
    """
    نموذج المستخدم المخصص (يمثل كيان المستخدم)
    """
    # 1. الخصائص الأساسية
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="تاريخ الميلاد")
    gender = models.CharField(max_length=10, choices=[('M', 'ذكر'), ('F', 'أنثى')], null=True, blank=True, verbose_name="النوع")
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True, verbose_name="رقم الهاتف")
    
    # 2. بيانات التقييم الأولي
    initial_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="الوزن الأولي (كجم)")
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="الطول (سم)")
    
    # 3. الوضع الوظيفي/الأكاديمي
    occupation_status = models.CharField(
        max_length=50,
        choices=[('Student', 'طالب'), ('Full-Time', 'موظف بدوام كامل'), ('Freelancer', 'عمل حر'), ('Other', 'أخرى')],
        default='Other',
        verbose_name="الوضع الوظيفي/الأكاديمي"
    )
    
    # ✅ أهداف الصحة
    health_goal = models.CharField(
        max_length=20,
        choices=[('loss', 'خسارة وزن'), ('gain', 'زيادة وزن'), ('maintain', 'تثبيت الوزن')],
        null=True,
        blank=True,
        verbose_name="الهدف الصحي"
    )
    
    # ✅ مستوى النشاط
    activity_level = models.CharField(
        max_length=20,
        choices=[('low', 'منخفض'), ('medium', 'متوسط'), ('high', 'عالي')],
        null=True,
        blank=True,
        verbose_name="مستوى النشاط"
    )
    
    # ✅ قم بإزالة هذين الحقلين من CustomUser لأن لديهما نموذجين منفصلين
    # chronic_conditions = models.TextField(...)  # ❌ أزل هذا السطر
    # current_medications = models.TextField(...) # ❌ أزل هذا السطر
    
    # العلاقات (لتجنب التضارب مع auth)
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=('groups'),
        blank=True,
        related_name="custom_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=('user permissions'),
        blank=True,
        related_name="custom_user_permissions",
        related_query_name="user",
    )

    class Meta:
        verbose_name = "المستخدم"
        verbose_name_plural = "المستخدمون"

    def __str__(self):
        return self.username

# ==============================================================================
# 2. نموذج: النشاط البدني (PhysicalActivity)
# ==============================================================================
class PhysicalActivity(models.Model):
    """
    نموذج النشاط البدني (يمثل كيان النشاط_البدني)
    العلاقة: 1:M مع CustomUser عبر user_id
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities', verbose_name="المستخدم")# المفتاح الأجنبي

    activity_type = models.CharField(max_length=50, verbose_name="نوع النشاط") # مثل: ركض، رفع أثقال
    duration_minutes = models.IntegerField(verbose_name="المدة (دقيقة)")
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="المسافة (كم)")
    calories_burned = models.IntegerField(null=True, blank=True, verbose_name="السعرات المحروقة")
    start_time = models.DateTimeField(verbose_name="وقت البداية")
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "النشاط البدني"
        verbose_name_plural = "الأنشطة البدنية"
        # ترتيب الأنشطة من الأحدث للأقدم
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.user.username} - {self.activity_type} ({self.duration_minutes} min)"

# الملف: main/models.py (تابع)

class Sleep(models.Model):
    """
    نموذج النوم (يمثل كيان النوم)
    العلاقة: 1:M مع CustomUser عبر user_id
    """
    QUALITY_CHOICES = [(i, str(i)) for i in range(1, 6)] # من 1 (سيئ) إلى 5 (ممتاز)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sleep_records', verbose_name="المستخدم") # المفتاح الأجنبي
    
    sleep_start = models.DateTimeField(verbose_name="وقت بداية النوم")
    sleep_end = models.DateTimeField(verbose_name="وقت الاستيقاظ")
    duration_hours = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,  verbose_name="المدة الكلية (بالساعة)")
    quality_rating = models.IntegerField(choices=QUALITY_CHOICES, verbose_name="تقييم الجودة")
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات/أحلام")
    
    class Meta:
        verbose_name = "سجل النوم"
        verbose_name_plural = "سجلات النوم"
        ordering = ['-sleep_start']

    def __str__(self):
        return f"{self.user.username} - Sleep on {self.sleep_start.date()}"
    
# الملف: main/models.py (تابع)

class MoodEntry(models.Model):
    """
    نموذج الحالة المزاجية (يمثل كيان الحالة_المزاجية)
    العلاقة: 1:M مع CustomUser عبر user_id
    """
    MOOD_CHOICES = [
        ('Excellent', 'ممتاز'),
        ('Good', 'جيد'),
        ('Neutral', 'محايد'),
        ('Stressed', 'مرهق/مجهد'),
        ('Anxious', 'قلق'),
        ('Sad', 'حزين')
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mood_entries', verbose_name="المستخدم") # المفتاح الأجنبي
    
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, verbose_name="الحالة المزاجية المسجلة")
    entry_time = models.DateTimeField(auto_now_add=True, verbose_name="وقت التسجيل") # يسجل الوقت تلقائياً
    factors = models.TextField(null=True, blank=True, verbose_name="العوامل المؤثرة (اختياري)")
    # خاصية إضافية: لربطها بتحليل النص إذا كتب المستخدم تفاصيل
    text_entry = models.TextField(null=True, blank=True, verbose_name="إدخال نصي حر")

    class Meta:
        verbose_name = "سجل الحالة المزاجية"
        verbose_name_plural = "سجلات الحالة المزاجية"
        ordering = ['-entry_time']

    def __str__(self):
        return f"{self.user.username} - Mood: {self.mood} at {self.entry_time.date()}"
    
# الملف: main/models.py (تابع)

# في main/models.py - ابحث عن class HealthStatus وأضف هذا السطر
# في main/models.py - ابحث عن class HealthStatus وأضف هذه الحقول

class HealthStatus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='health_records', verbose_name="المستخدم")
    
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ ووقت التسجيل")
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="الوزن (كجم)")
    
    # ✅ معدل ضربات القلب
    heart_rate = models.IntegerField(null=True, blank=True, verbose_name="معدل ضربات القلب (BPM)")
    
    # ✅ ضغط الدم
    systolic_pressure = models.IntegerField(null=True, blank=True, verbose_name="الضغط الانقباضي")
    diastolic_pressure = models.IntegerField(null=True, blank=True, verbose_name="الضغط الانبساطي")
    
    # ✅ نسبة الأكسجين في الدم
    spo2 = models.IntegerField(null=True, blank=True, verbose_name="نسبة الأكسجين في الدم (SpO2%)")
    
    # ✅ مستوى السكر في الدم
    blood_glucose = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="سكر الدم (mg/dL)")
    
    # ✅ درجة حرارة الجسم (جديدة)
    body_temperature = models.DecimalField(
        max_digits=4, 
        decimal_places=1, 
        null=True, 
        blank=True, 
        verbose_name="درجة حرارة الجسم (C°)"
    )
    
    # ✅ نبضات القلب (إضافي)
    pulse = models.IntegerField(null=True, blank=True, verbose_name="النبض (Pulse)")
    
    # ✅ مستوى التنفس
    respiration_rate = models.IntegerField(null=True, blank=True, verbose_name="معدل التنفس ( breaths/min)")
    
    class Meta:
        verbose_name = "القياسات الحيوية"
        verbose_name_plural = "سجلات القياسات الحيوية"
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.user.username} - Status at {self.recorded_at.date()}"

class Meal(models.Model):
    """
    نموذج الوجبة (يمثل كيان الوجبة)
    يسجل متى وماذا تناول المستخدم
    """
    MEAL_TYPE_CHOICES = [
        ('Breakfast', 'فطور'),
        ('Lunch', 'غداء'),
        ('Dinner', 'عشاء'),
        ('Snack', 'وجبة خفيفة'),
        ('Other', 'أخرى'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meals', verbose_name="المستخدم")
    
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, verbose_name="نوع الوجبة")
    meal_time = models.DateTimeField(verbose_name="تاريخ ووقت الوجبة")
    notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات")  # ✅ إضافة notes
    
    # ✅ إضافة ingredients كـ JSONField
    ingredients = models.JSONField(default=list, verbose_name="المكونات")
    
    # ✅ إضافة الإجماليات الغذائية
    total_calories = models.IntegerField(default=0, verbose_name="إجمالي السعرات")
    total_protein = models.FloatField(default=0, verbose_name="إجمالي البروتين")
    total_carbs = models.FloatField(default=0, verbose_name="إجمالي الكربوهيدرات")
    total_fat = models.FloatField(default=0, verbose_name="إجمالي الدهون")
    
    class Meta:
        verbose_name = "الوجبة"
        verbose_name_plural = "الوجبات"
        ordering = ['-meal_time']

    def __str__(self):
        return f"{self.user.username} - {self.get_meal_type_display()} at {self.meal_time.time()}"  
# الملف: main/models.py (تابع)

class FoodItem(models.Model):
    """
    نموذج المكون الغذائي (يمثل كيان العنصر_غذائي)
    يسجل تفاصيل العناصر داخل الوجبة الواحدة
    """
    # العلاقة: يرتبط بـ Meal (النموذج السابق) بعلاقة 1:M
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='food_items', verbose_name="الوجبة التابع لها") # المفتاح الأجنبي

    name = models.CharField(max_length=100, verbose_name="اسم المكون الغذائي")
    quantity = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="الكمية")
    unit = models.CharField(max_length=20, verbose_name="وحدة القياس (جرام، مل، قطعة)")
    calories = models.IntegerField(verbose_name="السعرات الحرارية")
    protein_g = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="البروتين (غ)")
    carbs_g = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="الكربوهيدرات (غ)")
    fat_g = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="الدهون (غ)")

    class Meta:
        verbose_name = "مكون غذائي"
        verbose_name_plural = "المكونات الغذائية"

    def __str__(self):
        return f"{self.name} - {self.quantity} {self.unit}"
# الملف: main/models.py (تابع)

# main/models.py

class HabitDefinition(models.Model):
    """
    نموذج تعريف العادة (يمثل كيان تعريف_العادة)
    يُعرف العادة التي يرغب المستخدم في تتبعها
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='habit_definitions', verbose_name="المستخدم")
    
    name = models.CharField(max_length=100, verbose_name="اسم العادة")
    description = models.TextField(verbose_name="وصف العادة والهدف منها")
    start_date = models.DateField(auto_now_add=True, verbose_name="تاريخ البدء")
    frequency = models.CharField(max_length=20, choices=[('Daily', 'يومي'), ('Weekly', 'أسبوعي'), ('Monthly', 'شهري')], default='Daily', verbose_name="تكرار العادة")
    
    # ✅ أضف هذا الحقل
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    
    target_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="القيمة المستهدفة")
    target_unit = models.CharField(max_length=20, null=True, blank=True, verbose_name="وحدة القياس (مثلاً: لتر، دقيقة)")

    class Meta:
        verbose_name = "تعريف العادة"
        verbose_name_plural = "تعريفات العادات"

    def __str__(self):
        return f"Habit: {self.name} for {self.user.username}"
        return f"Habit: {self.name} for {self.user.username}"
# الملف: main/models.py (تابع)
# main/models.py - أضف في نهاية الملف

class Medication(models.Model):
    """نموذج للأدوية"""
    ndc_code = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="رمز NDC")
    brand_name = models.CharField(max_length=500, verbose_name="الاسم التجاري")
    generic_name = models.CharField(max_length=500, blank=True, verbose_name="الاسم العلمي")
    manufacturer = models.CharField(max_length=500, blank=True, verbose_name="الشركة المصنعة")
    dosage_form = models.CharField(max_length=200, blank=True, verbose_name="شكل الجرعة")
    route = models.CharField(max_length=200, blank=True, verbose_name="طريقة الاستخدام")
    strength = models.CharField(max_length=200, blank=True, verbose_name="التركيز")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "دواء"
        verbose_name_plural = "الأدوية"
    
    def __str__(self):
        return f"{self.brand_name} ({self.generic_name})"


class UserMedication(models.Model):
    """نموذج لأدوية المستخدم"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_medications')
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE, related_name='user_medications')
    dosage = models.CharField(max_length=100, blank=True, verbose_name="الجرعة")
    frequency = models.CharField(max_length=100, blank=True, verbose_name="التكرار")
    start_date = models.DateField(verbose_name="تاريخ البدء")
    end_date = models.DateField(blank=True, null=True, verbose_name="تاريخ الانتهاء")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    reminder_time = models.TimeField(blank=True, null=True, verbose_name="وقت التذكير")
    reminder_days = models.CharField(max_length=50, blank=True, verbose_name="أيام التذكير")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "دواء المستخدم"
        verbose_name_plural = "أدوية المستخدمين"
    
    def __str__(self):
        return f"{self.user.username} - {self.medication.brand_name}"
class HabitLog(models.Model):
    """
    نموذج سجل العادات (يمثل كيان سجل_العادات)
    يسجل إنجاز العادة في يوم معين
    """
    # المفتاح الأجنبي: يرتبط بالـ HabitDefinition (التعريف)
    habit = models.ForeignKey(HabitDefinition, on_delete=models.CASCADE, related_name='logs', verbose_name="التعريف المرتبط") # المفتاح الأجنبي
    
    log_date = models.DateField(verbose_name="تاريخ التسجيل")
    is_completed = models.BooleanField(default=False, verbose_name="هل تم إنجاز العادة؟")
    actual_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="القيمة الفعلية المُنجزة")
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات الإنجاز")

    class Meta:
        verbose_name = "سجل عادة"
        verbose_name_plural = "سجلات العادات"
        # ضمان عدم تكرار سجل العادة لنفس اليوم
        unique_together = ('habit', 'log_date')
        ordering = ['-log_date']

    def __str__(self):
        status = "Completed" if self.is_completed else "Not Completed"
        return f"{self.habit.name} log on {self.log_date}: {status}"
# الملف: main/models.py (تابع)

class HealthGoal(models.Model):
    """
    نموذج الهدف الصحي (يمثل كيان الهدف_الصحي)
    يسجل الأهداف طويلة الأمد للمستخدم
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='health_goals', verbose_name="المستخدم") # المفتاح الأجنبي (1:M)
    
    title = models.CharField(max_length=100, verbose_name="عنوان الهدف")
    target_value = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="القيمة المستهدفة (مثلاً: 65.0)")
    current_value = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="القيمة الحالية (للتتبع)")
    unit = models.CharField(max_length=20, verbose_name="وحدة القياس (كجم، سم، إلخ)")
    start_date = models.DateField(verbose_name="تاريخ البدء")
    target_date = models.DateField(verbose_name="تاريخ الانتهاء المستهدف")
    is_achieved = models.BooleanField(default=False, verbose_name="هل تم تحقيق الهدف؟")

    class Meta:
        verbose_name = "هدف صحي"
        verbose_name_plural = "الأهداف الصحية"

    def __str__(self):
        return f"Goal: {self.title} - Target: {self.target_value} {self.unit}"
# الملف: main/models.py (تابع)

class ChronicCondition(models.Model):
    """
    نموذج الأمراض المزمنة (يمثل كيان الأمراض_المزمنة)
    يسجل الحالات الصحية المزمنة للمستخدم
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chronic_conditions', verbose_name="المستخدم") # المفتاح الأجنبي (1:M)
    
    name = models.CharField(max_length=100, verbose_name="اسم الحالة المزمنة") # مثال: Diabetes Type 2
    diagnosis_date = models.DateField(null=True, blank=True, verbose_name="تاريخ التشخيص")
    is_active = models.BooleanField(default=True, verbose_name="هل الحالة نشطة حالياً؟")
    medications = models.TextField(null=True, blank=True, verbose_name="الأدوية الحالية المتعلقة بالحالة")
    
    class Meta:
        verbose_name = "مرض مزمن"
        verbose_name_plural = "الأمراض المزمنة"
        # ضمان عدم تكرار اسم الحالة لنفس المستخدم
        unique_together = ('user', 'name')

    def __str__(self):
        return f"{self.user.username} - {self.name}"
# الملف: main/models.py (تابع)

class MedicalRecord(models.Model):
    """
    نموذج السجلات الطبية (يمثل كيان السجلات_الطبية)
    يسجل الأحداث الطبية التاريخية الهامة
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='medical_records', verbose_name="المستخدم") # المفتاح الأجنبي (1:M)
    
    event_type = models.CharField(max_length=100, verbose_name="نوع الحدث") # مثال: عملية جراحية، إصابة رياضية
    event_date = models.DateField(verbose_name="تاريخ وقوع الحدث")
    details = models.TextField(verbose_name="وصف تفصيلي للحدث")
    
    class Meta:
        verbose_name = "سجل طبي"
        verbose_name_plural = "السجلات الطبية"
        ordering = ['-event_date']

    def __str__(self):
        return f"{self.user.username} - {self.event_type} on {self.event_date}"
# الملف: main/models.py (تابع)

class Recommendation(models.Model):
    """
    نموذج التوصية (يمثل كيان التوصية)
    يسجل مخرجات الذكاء الاصطناعي الموجهة للمستخدم
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recommendations', verbose_name="المستخدم") # المفتاح الأجنبي (1:M)
    
    recommendation_type = models.CharField(max_length=50, verbose_name="نوع التوصية") # مثال: Nutrition, Sleep, Stress Mgmt
    content = models.TextField(verbose_name="نص التوصية/الإجراء المقترح")
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ ووقت التوليد")
    
    # لتتبع فعالية التوصية (خاصية هامة للتعلم المعزز)
    is_actioned = models.BooleanField(default=False, verbose_name="هل تم اتخاذ إجراء؟")
    
    class Meta:
        verbose_name = "توصية ذكية"
        verbose_name_plural = "التوصيات الذكية"
        ordering = ['-generated_at']

    def __str__(self):
        return f"Rec. for {self.user.username}: {self.recommendation_type} at {self.generated_at.date()}"
# الملف: main/models.py (تابع)

class ChatLog(models.Model):
    """
    نموذج سجل الدردشة (يمثل كيان سجل_الدردشة)
    يسجل تفاعلات المستخدم مع روبوت الدردشة
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_logs', verbose_name="المستخدم") # المفتاح الأجنبي (1:M)
    
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="وقت الرسالة")
    sender = models.CharField(max_length=10, choices=[('User', 'مستخدم'), ('Bot', 'روبوت')], verbose_name="المرسل")
    message_text = models.TextField(verbose_name="نص الرسالة")
    
    # خاصية تحليلية: لتسجيل نتيجة تحليل المشاعر (Sentimental Analysis)
    sentiment_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True, verbose_name="درجة تحليل المشاعر")
    
    class Meta:
        verbose_name = "سجل الدردشة"
        verbose_name_plural = "سجلات الدردشة"
        ordering = ['timestamp']

    def __str__(self):
        return f"Chat from {self.sender} on {self.timestamp.date()}"
# الملف: main/models.py (تابع)

# في ملف main/models.py - تحديث نموذج Notification

class Notification(models.Model):
    """
    نموذج الإشعارات (يمثل كيان الإشعارات)
    يسجل التنبيهات المرسلة من النظام
    """
    NOTIFICATION_TYPES = [
        ('health', 'صحي'),
        ('nutrition', 'تغذوي'),
        ('sleep', 'نوم'),
        ('mood', 'مزاج'),
        ('habit', 'عادة'),
        ('alert', 'تنبيه'),
        ('reminder', 'تذكير'),
        ('achievement', 'إنجاز'),
        ('tip', 'نصيحة'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'منخفضة'),
        ('medium', 'متوسطة'),
        ('high', 'عالية'),
        ('urgent', 'عاجل'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', verbose_name="المستخدم")
    
    # حقول جديدة
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='alert', verbose_name="نوع الإشعار")
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium', verbose_name="الأولوية")
    icon = models.CharField(max_length=10, default='🔔', verbose_name="الأيقونة")
    
    title = models.CharField(max_length=100, verbose_name="عنوان الإشعار")
    message = models.TextField(verbose_name="نص الإشعار")
    
    # بيانات إضافية
    action_url = models.CharField(max_length=500, blank=True, null=True, verbose_name="رابط الإجراء")
    action_text = models.CharField(max_length=100, blank=True, null=True, verbose_name="نص الإجراء")
    suggestions = models.JSONField(default=list, blank=True, verbose_name="اقتراحات")
    
    # الحالة
    is_read = models.BooleanField(default=False, verbose_name="هل تم قراءة الإشعار؟")
    is_archived = models.BooleanField(default=False, verbose_name="مؤرشف؟")
    
    # التواريخ
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت الإرسال")
    expires_at = models.DateTimeField(blank=True, null=True, verbose_name="تاريخ الانتهاء")
    read_at = models.DateTimeField(blank=True, null=True, verbose_name="وقت القراءة")
    
    class Meta:
        verbose_name = "إشعار النظام"
        verbose_name_plural = "إشعارات النظام"
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['user', '-sent_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"Notification to {self.user.username}: {self.title}"
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء"""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
# ==============================================================================
# 16. نموذج: البيانات البيئية (EnvironmentData) - التعديل الجديد
# ==============================================================================
class EnvironmentData(models.Model):
    """
    نموذج لتسجيل العوامل البيئية المحيطة التي قد تؤثر على المستخدم
    """
    # يجب استخدام CustomUser وليس User
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='environment_data', verbose_name="المستخدم") 
    
    date = models.DateField(verbose_name="التاريخ")
    temperature = models.FloatField(verbose_name="درجة الحرارة")
    weather_condition = models.CharField(max_length=100, verbose_name="حالة الطقس")
    mood_at_recording = models.CharField(max_length=50, blank=True, null=True, verbose_name="الحالة المزاجية المسجلة في هذا الوقت")

    class Meta:
        verbose_name = "البيانات البيئية"
        verbose_name_plural = "البيانات البيئية"
        unique_together = ('user', 'date') # لمنع تكرار البيانات البيئية لنفس المستخدم في نفس اليوم
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} - Env Data on {self.date}"
class Achievement(models.Model):
    """نموذج الإنجازات والميداليات"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='achievements')
    title = models.CharField(max_length=100, verbose_name="عنوان الإنجاز")
    description = models.TextField(verbose_name="وصف الإنجاز")
    icon = models.CharField(max_length=10, default='🏆', verbose_name="الأيقونة")
    achieved_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنجاز")
    category = models.CharField(max_length=50, choices=[
        ('streak', 'تتابع'), ('activity', 'نشاط'), ('weight', 'وزن'), 
        ('sleep', 'نوم'), ('habit', 'عادة'), ('special', 'خاص')
    ], default='special')
    
    class Meta:
        verbose_name = "إنجاز"
        verbose_name_plural = "الإنجازات"
        ordering = ['-achieved_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
class Reminder(models.Model):
    """نموذج التذكيرات"""
    REMINDER_TYPES = [
        ('medication', 'دواء'),
        ('habit', 'عادة'),
        ('water', 'ماء'),
        ('meal', 'وجبة'),
        ('sleep', 'نوم'),
        ('general', 'عام'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=100, verbose_name="عنوان التذكير")
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES, default='general')
    reminder_time = models.TimeField(verbose_name="وقت التذكير")
    reminder_days = models.JSONField(default=list, verbose_name="أيام التكرار (0=الأحد, 6=السبت)")
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    related_id = models.IntegerField(null=True, blank=True, verbose_name="معرف العنصر المرتبط")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "تذكير"
        verbose_name_plural = "التذكيرات"
        ordering = ['reminder_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.title} at {self.reminder_time}"

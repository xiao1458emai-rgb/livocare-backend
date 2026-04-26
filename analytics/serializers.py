# analytics/serializers.py
from rest_framework import serializers
from analytics.models import ActivityInsight, SleepInsight, HabitInsight, MoodInsight, NutritionInsight

class ActivityInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityInsight
        fields = '__all__'

class SleepInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = SleepInsight
        fields = '__all__'

class HabitInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitInsight
        fields = '__all__'

class MoodInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodInsight
        fields = '__all__'

class NutritionInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionInsight
        fields = '__all__'
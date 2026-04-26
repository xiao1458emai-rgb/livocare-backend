# services/sentiment_service.py
import os
import requests
import json
import re
from typing import Dict, Any, List, Optional, Tuple

class SentimentAnalyzer:
    """محلل المشاعر باستخدام Groq API - يدعم العربية والإنجليزية"""
    
    def __init__(self, language: str = 'ar', request=None):
        """
        تهيئة محلل المشاعر
        
        Args:
            language: اللغة ('ar' أو 'en')
            request: طلب Django (اختياري، لاستخراج اللغة منه)
        """
        self.api_key = os.environ.get('GROQ_API_KEY')
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"  # مجاني وسريع
        
        # تحديد اللغة من الطلب إذا وجد
        if request:
            language = self._extract_language_from_request(request)
        
        self.language = language
        self.is_arabic = language == 'ar'
        
        if not self.api_key:
            print("⚠️ GROQ_API_KEY not found. Using fallback mode.")
    
    def _extract_language_from_request(self, request) -> str:
        """استخراج اللغة من طلب Django"""
        # من header
        lang_header = request.headers.get('Accept-Language', '')
        if lang_header:
            if lang_header.startswith('en'):
                return 'en'
            elif lang_header.startswith('ar'):
                return 'ar'
        
        # من query params
        lang_param = request.GET.get('lang')
        if lang_param:
            return 'en' if lang_param == 'en' else 'ar'
        
        # من body (POST requests)
        if request.method == 'POST' and request.body:
            try:
                import json
                body = json.loads(request.body)
                if body.get('lang'):
                    return 'en' if body['lang'] == 'en' else 'ar'
            except:
                pass
        
        # افتراضياً العربية
        return 'ar'
    
    def _get_prompt(self, text: str) -> str:
        """بناء الـ prompt حسب اللغة"""
        if self.is_arabic:
            return f"""
            أنت محلل مشاعر متخصص. حلل النص التالي وأعد النتيجة بصيغة JSON فقط.
            
            النص: "{text}"
            
            أجب بهذا التنسيق فقط:
            {{"label": "POSITIVE/NEGATIVE/NEUTRAL", "score": 0.95, "sentiment": "إيجابي 😊/سلبي 😞/محايد 😐"}}
            
            ملاحظات:
            - POSITIVE: المشاعر الإيجابية (سعادة، حب، امتنان، تفاؤل)
            - NEGATIVE: المشاعر السلبية (حزن، غضب، إحباط، قلق)
            - NEUTRAL: المشاعر المحايدة أو الواقعية
            - score: رقم بين 0 و 1 يعبر عن شدة المشاعر
            """
        else:
            return f"""
            You are a specialized sentiment analyzer. Analyze the following text and return the result in JSON format only.
            
            Text: "{text}"
            
            Answer only in this format:
            {{"label": "POSITIVE/NEGATIVE/NEUTRAL", "score": 0.95, "sentiment": "Positive 😊/Negative 😞/Neutral 😐"}}
            
            Notes:
            - POSITIVE: Positive emotions (happiness, love, gratitude, optimism)
            - NEGATIVE: Negative emotions (sadness, anger, frustration, anxiety)
            - NEUTRAL: Neutral or factual emotions
            - score: A number between 0 and 1 indicating emotion intensity
            """
    
    def analyze(self, text: str) -> Dict[str, Any]:
        """
        تحليل المشاعر في النص باستخدام Groq API
        
        Args:
            text: النص المراد تحليله
            
        Returns:
            dict: {
                'label': str ('POSITIVE'/'NEGATIVE'/'NEUTRAL'),
                'score': float,
                'sentiment_text': str,
                'raw_sentiment': str
            }
        """
        if not self.api_key or not text or len(text.strip()) < 3:
            return self._fallback_response()
        
        prompt = self._get_prompt(text)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 150
        }
        
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # استخراج JSON من الرد
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    
                    # الحصول على النص المعبر عن المشاعر حسب اللغة
                    sentiment_text = self._get_sentiment_text(data.get('label', 'NEUTRAL'))
                    
                    return {
                        'label': data.get('label', 'NEUTRAL'),
                        'score': data.get('score', 0.5),
                        'sentiment_text': sentiment_text,
                        'raw_sentiment': data.get('sentiment', sentiment_text)
                    }
            
            return self._fallback_response()
            
        except requests.exceptions.Timeout:
            print(f"Groq API timeout for text: {text[:50]}...")
            return self._fallback_response()
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return self._fallback_response()
        except Exception as e:
            print(f"Groq API error: {e}")
            return self._fallback_response()
    
    def _get_sentiment_text(self, label: str) -> str:
        """الحصول على النص المعبر عن المشاعر حسب اللغة"""
        sentiments = {
            'POSITIVE': {
                'ar': 'إيجابي 😊',
                'en': 'Positive 😊'
            },
            'NEGATIVE': {
                'ar': 'سلبي 😞',
                'en': 'Negative 😞'
            },
            'NEUTRAL': {
                'ar': 'محايد 😐',
                'en': 'Neutral 😐'
            }
        }
        
        lang = 'ar' if self.is_arabic else 'en'
        return sentiments.get(label, sentiments['NEUTRAL']).get(lang, 'Neutral 😐')
    
    def _fallback_response(self) -> Dict[str, Any]:
        """رد بديل في حالة فشل API"""
        sentiment_text = self._get_sentiment_text('NEUTRAL')
        
        return {
            'label': 'NEUTRAL',
            'score': 0.5,
            'sentiment_text': sentiment_text,
            'raw_sentiment': sentiment_text
        }
    
    def map_sentiment(self, label: str) -> str:
        """تحويل نتيجة التحليل إلى مشاعر مفهومة"""
        return self._get_sentiment_text(label)
    
    def get_detailed_analysis(self, text: str) -> Dict[str, Any]:
        """
        تحليل مفصل للمشاعر مع توصيات
        
        Args:
            text: النص المراد تحليله
            
        Returns:
            dict: تحليل مفصل مع توصيات
        """
        basic = self.analyze(text)
        
        # توصيات حسب نوع المشاعر
        recommendations = self._get_recommendations(basic['label'])
        
        intensity = self._get_intensity_text(basic['score'])
        
        return {
            **basic,
            'intensity': intensity,
            'recommendations': recommendations
        }
    
    def _get_recommendations(self, label: str) -> List[str]:
        """الحصول على توصيات حسب نوع المشاعر"""
        if self.is_arabic:
            recommendations_map = {
                'POSITIVE': [
                    '😊 رائع! استمر في نشر الإيجابية',
                    '💪 حافظ على هذا التفاؤل الرائع',
                    '🌟 شارك مشاعرك الإيجابية مع الآخرين',
                    '📝 دوّن هذه المشاعر الجميلة لتتذكرها'
                ],
                'NEGATIVE': [
                    '🤗 خذ نفساً عميقاً وتأمل قليلاً',
                    '💬 تحدث مع شخص تثق به عن مشاعرك',
                    '🚶 قم بنشاط بدني خفيف لتحسين مزاجك',
                    '🎵 استمع لموسيقى هادئة تريح أعصابك',
                    '📝 اكتب مشاعرك على الورق لتفريغها'
                ],
                'NEUTRAL': [
                    '📝 دوّن ما تشعر به للحصول على تحليل أفضل',
                    '🎵 استمع لموسيقى تعجبك',
                    '🌿 جرب نشاطاً جديداً يثير اهتمامك',
                    '💬 تحدث مع شخص تحبه عن يومك'
                ]
            }
        else:
            recommendations_map = {
                'POSITIVE': [
                    '😊 Great! Keep spreading positivity',
                    '💪 Maintain this wonderful optimism',
                    '🌟 Share your positive feelings with others',
                    '📝 Journal these beautiful feelings to remember them'
                ],
                'NEGATIVE': [
                    '🤗 Take a deep breath and meditate for a moment',
                    '💬 Talk to someone you trust about your feelings',
                    '🚶 Do some light physical activity to improve your mood',
                    '🎵 Listen to calming music',
                    '📝 Write down your feelings to release them'
                ],
                'NEUTRAL': [
                    '📝 Journal your feelings for better analysis',
                    '🎵 Listen to music you enjoy',
                    '🌿 Try a new activity that interests you',
                    '💬 Talk to someone you love about your day'
                ]
            }
        
        return recommendations_map.get(label, recommendations_map['NEUTRAL'])
    
    def _get_intensity_text(self, score: float) -> str:
        """الحصول على نص شدة المشاعر"""
        if self.is_arabic:
            if score >= 0.7:
                return "شديدة"
            elif score >= 0.4:
                return "متوسطة"
            else:
                return "خفيفة"
        else:
            if score >= 0.7:
                return "very high"
            elif score >= 0.4:
                return "moderate"
            else:
                return "low"
    
    def get_batch_analysis(self, texts: List[str]) -> List[Dict[str, Any]]:
        """تحليل مجموعة من النصوص"""
        results = []
        for text in texts:
            if text and len(text.strip()) > 0:
                results.append(self.get_detailed_analysis(text))
        return results


class AdvancedSentimentAnalyzer(SentimentAnalyzer):
    """نسخة متقدمة مع تحليل أكثر دقة ودعم المشاعر المتعددة"""
    
    def __init__(self, language: str = 'ar', request=None):
        super().__init__(language, request)
        self.model = "llama-3.1-70b-versatile"  # نموذج أكثر قوة
    
    def analyze_with_context(self, text: str, context: str = "") -> Dict[str, Any]:
        """
        تحليل المشاعر مع سياق إضافي
        
        Args:
            text: النص المراد تحليله
            context: سياق إضافي للمساعدة في التحليل
            
        Returns:
            dict: تحليل مفصل مع المشاعر المتعددة
        """
        if not self.api_key or not text or len(text.strip()) < 3:
            return self._fallback_response()
        
        if self.is_arabic:
            prompt = f"""
            أنت محلل مشاعر متخصص. حلل النص التالي مع مراعاة السياق.
            
            السياق: {context}
            النص: "{text}"
            
            أجب بهذا التنسيق JSON فقط:
            {{
                "label": "POSITIVE/NEGATIVE/NEUTRAL",
                "score": 0.95,
                "sentiment": "إيجابي 😊/سلبي 😞/محايد 😐",
                "emotions": ["سعادة", "حزن", "غضب"],
                "confidence": 0.9
            }}
            """
        else:
            prompt = f"""
            You are a specialized sentiment analyzer. Analyze the following text considering the context.
            
            Context: {context}
            Text: "{text}"
            
            Answer only in JSON format:
            {{
                "label": "POSITIVE/NEGATIVE/NEUTRAL",
                "score": 0.95,
                "sentiment": "Positive 😊/Negative 😞/Neutral 😐",
                "emotions": ["happiness", "sadness", "anger"],
                "confidence": 0.9
            }}
            """
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 200
        }
        
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    
                    sentiment_text = self._get_sentiment_text(data.get('label', 'NEUTRAL'))
                    
                    # ترجمة المشاعر حسب اللغة
                    emotions = self._translate_emotions(data.get('emotions', []))
                    
                    return {
                        'label': data.get('label', 'NEUTRAL'),
                        'score': data.get('score', 0.5),
                        'sentiment_text': sentiment_text,
                        'emotions': emotions[:3],  # أقصى 3 مشاعر
                        'confidence': data.get('confidence', 0.8),
                        'raw_sentiment': data.get('sentiment', sentiment_text)
                    }
            
            return self._fallback_response()
            
        except Exception as e:
            print(f"Advanced analysis error: {e}")
            return self._fallback_response()
    
    def _translate_emotions(self, emotions: List[str]) -> List[str]:
        """ترجمة المشاعر حسب اللغة"""
        if self.is_arabic:
            emotion_map = {
                'happiness': 'سعادة', 'joy': 'فرح', 'excitement': 'حماس',
                'sadness': 'حزن', 'sorrow': 'أسى', 'grief': 'حزن عميق',
                'anger': 'غضب', 'frustration': 'إحباط', 'annoyance': 'انزعاج',
                'fear': 'خوف', 'anxiety': 'قلق', 'worry': 'هم',
                'stress': 'توتر', 'pressure': 'ضغط',
                'calm': 'هدوء', 'peace': 'سلام داخلي', 'relaxed': 'استرخاء',
                'love': 'حب', 'affection': 'مودة', 'care': 'اهتمام',
                'gratitude': 'امتنان', 'thankful': 'شكر',
                'hope': 'أمل', 'optimism': 'تفاؤل',
                'surprise': 'دهشة', 'shock': 'صدمة',
                'disgust': 'اشمئزاز', 'contempt': 'ازدراء',
                'neutral': 'محايد', 'mixed': 'مختلط'
            }
            return [emotion_map.get(e.lower(), e) for e in emotions]
        return emotions
    
    def _fallback_response(self) -> Dict[str, Any]:
        """رد بديل متقدم"""
        sentiment_text = self._get_sentiment_text('NEUTRAL')
        emotions = ['محايد'] if self.is_arabic else ['neutral']
        
        return {
            'label': 'NEUTRAL',
            'score': 0.5,
            'sentiment_text': sentiment_text,
            'emotions': emotions,
            'confidence': 0.6,
            'raw_sentiment': sentiment_text
        }


class SentimentTracker:
    """تتبع المشاعر على مدى الوقت وتوليد تقارير"""
    
    def __init__(self, language: str = 'ar', request=None):
        """
        تهيئة متتبع المشاعر
        
        Args:
            language: اللغة ('ar' أو 'en')
            request: طلب Django (اختياري، لاستخراج اللغة منه)
        """
        self.analyzer = SentimentAnalyzer(language, request)
        self.language = language
        self.is_arabic = language == 'ar'
        self.request = request
    
    def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """تحليل مجموعة من النصوص"""
        results = []
        for text in texts:
            if text and len(text.strip()) > 0:
                results.append(self.analyzer.get_detailed_analysis(text))
        return results
    
    def get_overall_sentiment(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """الحصول على المشاعر العامة من مجموعة من التحليلات"""
        if not results:
            return self._get_empty_response()
        
        positive = sum(1 for r in results if r['label'] == 'POSITIVE')
        negative = sum(1 for r in results if r['label'] == 'NEGATIVE')
        neutral = len(results) - positive - negative
        
        avg_score = sum(r['score'] for r in results) / len(results)
        
        if self.is_arabic:
            if positive > negative and positive > neutral:
                overall = 'إيجابي'
            elif negative > positive and negative > neutral:
                overall = 'سلبي'
            else:
                overall = 'متوازن'
        else:
            if positive > negative and positive > neutral:
                overall = 'Positive'
            elif negative > positive and negative > neutral:
                overall = 'Negative'
            else:
                overall = 'Balanced'
        
        return {
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'total': len(results),
            'avg_score': round(avg_score, 2),
            'overall': overall,
            'positive_rate': round(positive / len(results) * 100, 1) if results else 0
        }
    
    def get_trend_analysis(self, historical_results: List[Dict[str, Any]], window_size: int = 7) -> Dict[str, Any]:
        """تحليل اتجاه المشاعر على مدى الوقت"""
        if len(historical_results) < window_size:
            return {
                'trend': 'insufficient_data',
                'message': self._get_insufficient_message(),
                'recent_positive_rate': 0,
                'period_days': window_size
            }
        
        recent = historical_results[-window_size:]
        older = historical_results[-window_size*2:-window_size] if len(historical_results) >= window_size*2 else []
        
        recent_positive = sum(1 for r in recent if r['label'] == 'POSITIVE')
        older_positive = sum(1 for r in older if r['label'] == 'POSITIVE') if older else 0
        
        recent_rate = round(recent_positive / len(recent) * 100, 1) if recent else 0
        older_rate = round(older_positive / len(older) * 100, 1) if older else 0
        
        if older and recent_positive > older_positive:
            trend = 'improving'
            message = self._get_trend_message('improving')
        elif older and recent_positive < older_positive:
            trend = 'declining'
            message = self._get_trend_message('declining')
        else:
            trend = 'stable'
            message = self._get_trend_message('stable')
        
        return {
            'trend': trend,
            'message': message,
            'recent_positive_rate': recent_rate,
            'older_positive_rate': older_rate,
            'change': round(recent_rate - older_rate, 1),
            'period_days': window_size
        }
    
    def generate_mood_insights(self, mood_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """توليد رؤى وتحليلات متقدمة من سجلات المزاج"""
        if not mood_entries:
            return {
                'has_data': False,
                'message': self._get_no_data_message()
            }
        
        # تحليل المشاعر من النصوص إذا وجدت
        texts = [entry.get('text_entry', '') for entry in mood_entries if entry.get('text_entry')]
        sentiment_results = self.analyze_batch(texts) if texts else []
        
        overall = self.get_overall_sentiment(sentiment_results)
        trend = self.get_trend_analysis(sentiment_results)
        
        # إحصائيات إضافية
        moods_count = {}
        for entry in mood_entries:
            mood = entry.get('mood', 'Neutral')
            moods_count[mood] = moods_count.get(mood, 0) + 1
        
        most_common_mood = max(moods_count.items(), key=lambda x: x[1])[0] if moods_count else 'Neutral'
        
        if self.is_arabic:
            mood_map = {
                'Excellent': 'ممتاز',
                'Good': 'جيد',
                'Neutral': 'محايد',
                'Stressed': 'مرهق',
                'Anxious': 'قلق',
                'Sad': 'حزين'
            }
            most_common_mood_ar = mood_map.get(most_common_mood, most_common_mood)
        else:
            most_common_mood_ar = most_common_mood
        
        return {
            'has_data': True,
            'total_entries': len(mood_entries),
            'overall_sentiment': overall,
            'trend_analysis': trend,
            'most_common_mood': most_common_mood_ar,
            'moods_distribution': moods_count,
            'sentiment_analysis': sentiment_results[:5]  # آخر 5 تحليلات
        }
    
    def _get_empty_response(self) -> Dict[str, Any]:
        """استجابة فارغة"""
        if self.is_arabic:
            return {
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'total': 0,
                'avg_score': 0,
                'overall': 'لا توجد بيانات',
                'positive_rate': 0
            }
        else:
            return {
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'total': 0,
                'avg_score': 0,
                'overall': 'No data',
                'positive_rate': 0
            }
    
    def _get_insufficient_message(self) -> str:
        """رسالة البيانات غير الكافية"""
        return "البيانات غير كافية للتحليل، سجل المزيد من المشاعر" if self.is_arabic else "Insufficient data for analysis, log more sentiments"
    
    def _get_no_data_message(self) -> str:
        """رسالة عدم وجود بيانات"""
        return "لا توجد بيانات مزاج مسجلة بعد" if self.is_arabic else "No mood data recorded yet"
    
    def _get_trend_message(self, trend: str) -> str:
        """رسالة اتجاه المشاعر"""
        messages = {
            'improving': {
                'ar': '📈 ملاحظة تحسن في مشاعرك خلال الفترة الأخيرة، استمر!',
                'en': '📈 Noticeable improvement in your mood recently, keep it up!'
            },
            'declining': {
                'ar': '📉 انخفاض ملحوظ في مشاعرك، اهتم بصحتك النفسية',
                'en': '📉 Noticeable decline in your mood, take care of your mental health'
            },
            'stable': {
                'ar': '➡️ حالة مزاجية مستقرة، يمكنك العمل على تحسينها',
                'en': '➡️ Stable mood, you can work on improving it'
            }
        }
        return messages.get(trend, messages['stable']).get('ar' if self.is_arabic else 'en')


# دوال مساعدة للاستخدام السريع
def quick_analyze(text: str, language: str = 'ar') -> Dict[str, Any]:
    """
    وظيفة سريعة لتحليل مشاعر نص واحد
    
    Args:
        text: النص المراد تحليله
        language: اللغة ('ar' أو 'en')
        
    Returns:
        dict: تحليل مفصل للمشاعر
    """
    analyzer = SentimentAnalyzer(language)
    return analyzer.get_detailed_analysis(text)


def analyze_with_context(text: str, context: str = '', language: str = 'ar') -> Dict[str, Any]:
    """
    تحليل المشاعر مع سياق إضافي
    
    Args:
        text: النص المراد تحليله
        context: سياق إضافي
        language: اللغة ('ar' أو 'en')
        
    Returns:
        dict: تحليل مفصل مع المشاعر المتعددة
    """
    analyzer = AdvancedSentimentAnalyzer(language)
    return analyzer.analyze_with_context(text, context)


def get_sentiment_insights(mood_entries: List[Dict[str, Any]], language: str = 'ar') -> Dict[str, Any]:
    """
    توليد رؤى وتحليلات متقدمة من سجلات المزاج
    
    Args:
        mood_entries: قائمة بسجلات المزاج
        language: اللغة ('ar' أو 'en')
        
    Returns:
        dict: رؤى وتحليلات متقدمة
    """
    tracker = SentimentTracker(language)
    return tracker.generate_mood_insights(mood_entries)


# مثال على الاستخدام
if __name__ == '__main__':
    # اختبار التحليل بالعربية
    analyzer = SentimentAnalyzer('ar')
    
    test_texts = [
        "أنا سعيد جداً اليوم!",
        "شعرت بالتعب والإرهاق الشديد",
        "الطقس جميل اليوم",
        "أنا غاضب جداً من هذا الموقف"
    ]
    
    print("\n" + "="*60)
    print("اختبار تحليل المشاعر بالعربية")
    print("="*60)
    
    for text in test_texts:
        result = analyzer.get_detailed_analysis(text)
        print(f"\n📝 النص: {text}")
        print(f"🎭 المشاعر: {result['sentiment_text']}")
        print(f"📊 الشدة: {result['intensity']}")
        print(f"💡 أول توصية: {result['recommendations'][0]}")
    
    # اختبار التحليل بالإنجليزية
    analyzer_en = SentimentAnalyzer('en')
    
    test_texts_en = [
        "I'm so happy today!",
        "I feel very tired and exhausted",
        "The weather is nice today",
        "I'm very angry about this situation"
    ]
    
    print("\n" + "="*60)
    print("Testing English Sentiment Analysis")
    print("="*60)
    
    for text in test_texts_en:
        result = analyzer_en.get_detailed_analysis(text)
        print(f"\n📝 Text: {text}")
        print(f"🎭 Sentiment: {result['sentiment_text']}")
        print(f"📊 Intensity: {result['intensity']}")
        print(f"💡 First recommendation: {result['recommendations'][0]}")
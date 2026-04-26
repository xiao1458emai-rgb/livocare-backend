"""
Django settings for livocare project.
"""

from pathlib import Path
from datetime import timedelta
import os
import dj_database_url
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# 🔐 الإعدادات الأساسية
# ==============================================================================

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-...')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '192.168.8.187',
    '.onrender.com',
    '.railway.app',
    'livocare.onrender.com',
    'livocare-fronend.onrender.com',
    'livocare-production.up.railway.app',  # ✅ أضف هذا السطر
]

# ==============================================================================
# 🔔 خدمات خارجية مستقلة - الإشعارات
# ==============================================================================

NOTIFICATION_SERVICE_URL = os.environ.get('NOTIFICATION_SERVICE_URL', 'https://notification-service-2xej.onrender.com')
EMAIL_SERVICE_URL = os.environ.get('EMAIL_SERVICE_URL', 'https://email-service-zc0r.onrender.com')

# ==============================================================================
# 📦 التطبيقات المثبتة
# ==============================================================================

INSTALLED_APPS = [
    'django_extensions',
    'sslserver',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'analytics',
    'whitenoise.runserver_nostatic',
]

# ==============================================================================
# 🛡️ Middleware
# ==============================================================================

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'livocare.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'livocare.wsgi.application'

# ==============================================================================
# 🗄️ قاعدة البيانات
# ==============================================================================

if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ==============================================================================
# 🔐 المصادقة
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==============================================================================
# 🌐 اللغة والوقت
# ==============================================================================

LANGUAGE_CODE = 'ar-eg'
TIME_ZONE = 'Asia/Aden'
USE_I18N = True
USE_TZ = True

# ==============================================================================
# 📁 الملفات الثابتة والإعلامية
# ==============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==============================================================================
# 🔑 الإعدادات الأساسية
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'main.CustomUser'

# ==============================================================================
# 🚀 REST Framework و JWT
# ==============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '2000/day',
        'user': '5000/day',
        'notifications': '1000/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "ALGORITHM": "HS256",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ==============================================================================
# 🔗 CORS
# ==============================================================================

CSRF_TRUSTED_ORIGINS = [
    "https://livocare-fronend.onrender.com",
    "https://camera-service-fag3.onrender.com",
    "https://google-auth.onrender.com",
    "https://notification-service-2xej.onrender.com",
    "https://email-service-zc0r.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.8.187:8000",
    "https://*.onrender.com",
    "https://*.railway.app",
    "https://livocare-production.up.railway.app",  # ✅ أضف هذا السطر
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.8.187:8000",
    "https://livocare-fronend.onrender.com",
    "https://livocare-production.up.railway.app",
    "https://livocare-fronend.vercel.app",   # ✅ هذا مفقود!
    "https://camera-service-fag3.onrender.com",
    "https://google-auth.onrender.com",
    "https://notification-service-2xej.onrender.com",
    "https://email-service-zc0r.onrender.com",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = [
    "https://livocare-fronend.onrender.com",
    "https://camera-service-fag3.onrender.com",
    "https://google-auth.onrender.com",
    "https://notification-service-2xej.onrender.com",
    "https://email-service-zc0r.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.8.187:8000",
    "https://*.onrender.com",
    "https://*.railway.app",
    "https://livocare-fronend.vercel.app",
]

CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

# ==============================================================================
# 🌤️ APIs الخارجية
# ==============================================================================

OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
OPENFOODFACTS_ENABLED = True

# Google OAuth2
GOOGLE_OAUTH2_KEY = os.environ.get('GOOGLE_OAUTH2_KEY', '')
GOOGLE_OAUTH2_SECRET = os.environ.get('GOOGLE_OAUTH2_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://google-auth.onrender.com/auth/google/callback')

# Frontend URL
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://livocare-fronend.onrender.com')
DJANGO_API_URL = os.environ.get('DJANGO_API_URL', 'https://livocare.onrender.com')

# ==============================================================================
# 🔔 إعدادات الإشعارات
# ==============================================================================

# VAPID keys لـ Web Push
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = os.environ.get('VAPID_ADMIN_EMAIL', 'admin@livocare.com')

# إعدادات الإشعارات الداخلية
NOTIFICATION_SETTINGS = {
    'ENABLED': True,
    'CHECK_INTERVAL_MINUTES': 30,
    'MAX_NOTIFICATIONS_PER_USER': 50,
    'KEEP_DAYS': 30,
    'PUSH_ENABLED': True,
    'EMAIL_ENABLED': True,
    'DAILY_TIP_ENABLED': True,
    'ACHIEVEMENT_ENABLED': True,
    'BATCH_SIZE': 50,
    'RETRY_ATTEMPTS': 3,
    'RETRY_DELAY': 60,
}

# إعدادات التنبيهات الصحية (مرة واحدة فقط)
HEALTH_ALERTS = {
    'weight': {'min': 50, 'max': 100, 'urgent_min': 40, 'urgent_max': 120},
    'systolic': {'min': 90, 'max': 140, 'urgent_min': 80, 'urgent_max': 160},
    'diastolic': {'min': 60, 'max': 90, 'urgent_min': 50, 'urgent_max': 100},
    'glucose': {'min': 70, 'max': 140, 'urgent_min': 60, 'urgent_max': 180},
}

# إعدادات توقيت الإشعارات (مرة واحدة فقط)
NOTIFICATION_TIMING = {
    'breakfast': {'hour': 8, 'minute': 0},
    'lunch': {'hour': 13, 'minute': 0},
    'dinner': {'hour': 19, 'minute': 0},
    'sleep_reminder': {'hour': 21, 'minute': 0},
    'activity_reminder': {'hour': 17, 'minute': 0},
    'daily_tip': {'hour': 10, 'minute': 0},
}

# ==============================================================================
# 🔒 إعدادات الأمان للإنتاج
# ==============================================================================

# تم تعطيل إعدادات SSL مؤقتاً لتجنب مشكلة إعادة التوجيه
# if not DEBUG:
#     SECURE_SSL_REDIRECT = True
#     SESSION_COOKIE_SECURE = True
#     CSRF_COOKIE_SECURE = True
#     SECURE_BROWSER_XSS_FILTER = True
#     SECURE_CONTENT_TYPE_NOSNIFF = True
#     SECURE_HSTS_SECONDS = 31536000
#     SECURE_HSTS_INCLUDE_SUBDOMAINS = True
#     SECURE_HSTS_PRELOAD = True
# ==============================================================================
# ⏰ Cron Jobs (المهام المجدولة)
# ==============================================================================

INSTALLED_APPS += [
    'django_crontab',
]

CRONJOBS = [
    ('0 20 * * *', 'django.core.management.call_command', ['generate_daily_notifications']),
]

# إذا كنت تريد أيضاً تذكير بالوجبات
# ('0 8 * * *', 'django.core.management.call_command', ['send_meal_reminder', 'breakfast']),
# ('0 13 * * *', 'django.core.management.call_command', ['send_meal_reminder', 'lunch']),
# ('0 19 * * *', 'django.core.management.call_command', ['send_meal_reminder', 'dinner']),

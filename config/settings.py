import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me')
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'karsilastirma',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'karsilastirma.middleware.TekOturumMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'Mesbul$default'),
        'USER': os.getenv('DB_USER', 'Mesbul'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'Mesbul.mysql.pythonanywhere-services.com'),
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
} if os.getenv('DB_PASSWORD') else {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = []
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'

# Auth ayarları
LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Email — Gmail SMTP
EMAIL_BACKEND         = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST            = 'smtp.gmail.com'
EMAIL_PORT            = 587
EMAIL_USE_TLS         = True
EMAIL_HOST_USER       = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD   = os.getenv('EMAIL_HOST_PASSWORD', '')  # Gmail App Password
DEFAULT_FROM_EMAIL    = os.getenv('EMAIL_HOST_USER', '')
ILETISIM_ALICI_EMAIL  = os.getenv('ILETISIM_ALICI_EMAIL', os.getenv('EMAIL_HOST_USER', ''))

# Cache — DB backend (tüm worker'lar aynı tabloyu okur, process restart'tan etkilenmez)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    }
}

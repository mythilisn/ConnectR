"""
Django settings for connectR project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# This BASE_DIR points to the inner 'connectR' folder containing settings.py
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv()


# Quick-start development settings - unsuitable for production
SECRET_KEY = "django-insecure-b+vbvu6+womb0pkdd(!!yj+rfi9ix)bl0=(n^dzdid%-ttxh+f"
DEBUG = True

ALLOWED_HOSTS = ['192.168.114.243', '127.0.0.1', 'localhost']


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    
    'core',
]

SITE_ID = 2

# -------------------------------------------------------------------------
# FIXED MIDDLEWARE (Fixes SystemCheckError)
# -------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Required for Session/Auth/Messages
    "django.contrib.sessions.middleware.SessionMiddleware", 
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # Required for user login/admin
    "django.contrib.auth.middleware.AuthenticationMiddleware", 
    # Required for the messages framework/admin
    "django.contrib.messages.middleware.MessageMiddleware", 
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "connectR.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        'DIRS': [os.path.join(BASE_DIR, 'templates')], 
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "connectR.wsgi.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation (omitted for brevity)
# ...

# Internationalization (omitted for brevity)
# ...

# -------------------------------------------------------------------------
# FIXED STATIC AND MEDIA FILE SETTINGS (Fixes 404 for style.css)
# -------------------------------------------------------------------------

STATIC_URL = "/static/"

# 1. STATIC_ROOT (REQUIRED for collectstatic)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_collected') 

# 2. STATICFILES_DIRS (REQUIRED for development to find project-level static files)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# 3. MEDIA SETTINGS (for uploaded notes)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# -------------------------------------------------------------------------
# EMAIL & LOGIN SETTINGS
# -------------------------------------------------------------------------

LOGIN_REDIRECT_URL = '/dashboard/' 
LOGIN_URL = '/login/'             

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = f"connectR <{EMAIL_HOST_USER}>"
DEFAULT_DOMAIN = "http://192.168.114.243:8000/"

# -------------------------------------------------------------------------
# NEW: AI API KEY CONFIGURATION (Fixes access issues)
# -------------------------------------------------------------------------

# Load AI API keys from environment variables/dotenv file
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_SUMMARY_MODEL = os.getenv("GEMINI_SUMMARY_MODEL", "gemini-1.5-flash") # Use a default if not set

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini") # Use a default if not set


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "$+1*x4=3y8vqq)v=#h0^^r!r96s3tblc4ah&#j37)o&-%ftgaw"
)

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "downloader",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pdf_downloader.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [],
        },
    },
]

WSGI_APPLICATION = "pdf_downloader.wsgi.application"

DATABASES = {}

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/downloads/"
MEDIA_ROOT = BASE_DIR / "downloads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DOWNLOAD_TIMEOUT = 45
DOWNLOAD_RETRIES = 3
MAX_WORKERS = 4

CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
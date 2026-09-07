from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "change-this-secret-key-in-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "downloader",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "pdf_downloader.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "pdf_downloader.wsgi.application"

# No database is used by this project.
DATABASES = {}

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/downloads/"
MEDIA_ROOT = BASE_DIR / "downloads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Downloader settings
DOWNLOAD_TIMEOUT = 45
DOWNLOAD_RETRIES = 3
MAX_WORKERS = 4

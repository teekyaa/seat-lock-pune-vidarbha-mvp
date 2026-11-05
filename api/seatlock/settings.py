"""Django settings for the Seat Lock API.

All environment-specific values come from environment variables. See
`.env.example` for the full list.
"""
import os
import ipaddress
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development convenience: read api/.env if present. Real environment variables win.
_dotenv = BASE_DIR / ".env"
if _dotenv.exists():
    for _line in _dotenv.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _value = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _value.strip())


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY") or ("dev-insecure-secret-key" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY == "change-me"):
    raise RuntimeError("Production requires a strong DJANGO_SECRET_KEY of at least 50 characters.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")
# Legacy Django admin does not enforce the separate operator TOTP policy.
LEGACY_ADMIN_ENABLED = env_bool("DJANGO_LEGACY_ADMIN_ENABLED", DEBUG)
ADMIN_DASHBOARD_ENABLED = env_bool("ADMIN_DASHBOARD_ENABLED", DEBUG)
try:
    ADMIN_IP_ALLOWLIST = [ipaddress.ip_network(item, strict=False) for item in env_list("ADMIN_IP_ALLOWLIST")]
except ValueError as exc:
    raise RuntimeError("ADMIN_IP_ALLOWLIST must contain valid IP addresses or CIDR ranges.") from exc
if LEGACY_ADMIN_ENABLED and not DEBUG and not ADMIN_IP_ALLOWLIST:
    # Route legs are still managed in the legacy admin; in production it must sit behind an allowlist.
    raise RuntimeError("DJANGO_LEGACY_ADMIN_ENABLED in production requires ADMIN_IP_ALLOWLIST.")
if ADMIN_DASHBOARD_ENABLED and not DEBUG:
    from cryptography.fernet import Fernet
    try:
        Fernet(env("ADMIN_TOTP_ENCRYPTION_KEY", "").encode("ascii"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise RuntimeError("ADMIN_TOTP_ENCRYPTION_KEY must be a valid Fernet key when the admin dashboard is enabled.") from exc

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.accounts",
    "apps.core",
    "apps.rides",
    "apps.bookings",
    "apps.trust",
    "apps.notifications",
    "apps.admin_dashboard",
    "apps.routes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.admin_dashboard.legacy_admin.LegacyAdminAllowlistMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "seatlock.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "seatlock.wsgi.application"

# PostgreSQL 16 in production. SQLite is accepted only for quick local runs;
# row locking (SELECT ... FOR UPDATE) is a no-op there.
DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=int(env("DB_CONN_MAX_AGE", "60")),
    )
}
if not DEBUG and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise RuntimeError("Production requires a PostgreSQL DATABASE_URL.")

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "UTC"  # Store UTC. The web app displays IST.
USE_I18N = True
USE_TZ = True
DISPLAY_TIME_ZONE = "Asia/Kolkata"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536

REDIS_URL = env("REDIS_URL")
if not DEBUG and not REDIS_URL:
    raise RuntimeError("Production requires REDIS_URL for shared rate limiting and background jobs.")
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.auth.BearerTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "apps.core.errors.exception_handler",
    "UNAUTHENTICATED_USER": None,
}
SPECTACULAR_SETTINGS = {"TITLE": "Seat Lock Admin API", "VERSION": "0.1.0"}

# Celery: broker is Redis. Beat runs one tick per minute (see apps.notifications.tasks).
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "scheduler-tick": {"task": "apps.notifications.tasks.tick", "schedule": 60.0},
}

# Auth / OTP
AUTH_TOKEN_TTL_DAYS = int(env("AUTH_TOKEN_TTL_DAYS", "30"))
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_VERIFY_ATTEMPTS_PER_IP = 30
OTP_VERIFY_WINDOW_SECONDS = 900
OTP_SENDS_PER_PHONE = 3  # per OTP_SEND_WINDOW_SECONDS
OTP_SENDS_PER_IP = 10
OTP_SEND_WINDOW_SECONDS = 900
OTP_RESEND_COOLDOWN_SECONDS = 60
# Only trust forwarding headers from explicitly configured reverse proxies.
OTP_TRUSTED_PROXY_IPS = env_list("OTP_TRUSTED_PROXY_IPS")

# Messaging
TEXTBEE_API_KEY = env("TEXTBEE_API_KEY", "")
TEXTBEE_DEVICE_ID = env("TEXTBEE_DEVICE_ID", "")
SMS_BACKEND = env("SMS_BACKEND") or (
    "apps.notifications.textbee.TextBeeSMSBackend"
    if TEXTBEE_API_KEY or TEXTBEE_DEVICE_ID
    else "apps.notifications.channels.ConsoleSMSBackend" if DEBUG
    else "apps.notifications.channels.UnconfiguredSMSBackend"
)
# Never return a code when a real SMS gateway is configured, even in DEBUG.
OTP_DEBUG_ECHO = (
    DEBUG and env_bool("OTP_DEBUG_ECHO", False)
    and SMS_BACKEND == "apps.notifications.channels.ConsoleSMSBackend"
    and not (TEXTBEE_API_KEY or TEXTBEE_DEVICE_ID)
)
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_TIMEOUT = 10
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Seat Lock <no-reply@seatlock.local>")
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = env("VAPID_SUBJECT", "mailto:ops@seatlock.local")

# Mappls (MapmyIndia): place search for exact pickup points, and one-time leg measurement in admin.
# The key stays on this server. URLs are configurable in case Mappls moves them; check their console.
MAPPLS_API_KEY = env("MAPPLS_API_KEY", "")
MAPPLS_AUTOSUGGEST_URL = env("MAPPLS_AUTOSUGGEST_URL", "https://search.mappls.com/search/places/autosuggest/json")
MAPPLS_ROUTE_URL = env("MAPPLS_ROUTE_URL", "https://apis.mappls.com/advancedmaps/v1/{key}/route_adv/driving/{coords}")
MAPPLS_TIMEOUT_SECONDS = 8

# Public web origin, used in share links and notification bodies.
WEB_BASE_URL = env("WEB_BASE_URL", "http://localhost:3000")

if not DEBUG:
    if env_bool("DJANGO_TRUST_PROXY_HEADERS", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"admin_json": {"()": "apps.admin_dashboard.logging.AdminJSONFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler"},
                 "admin_console": {"class": "logging.StreamHandler", "formatter": "admin_json"}},
    "loggers": {"seatlock.admin": {"handlers": ["admin_console"], "level": "INFO", "propagate": False}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}

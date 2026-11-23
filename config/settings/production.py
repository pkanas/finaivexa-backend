"""Production settings.

Use together with a MySQL database, e.g.:

    DB_ENGINE=mysql DB_NAME=finance_db DB_USER=finance DB_PASSWORD=... \
    python manage.py runserver --settings=config.settings.production

See .env.example and README.md for the full list of variables.
"""
from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Longer, rotated keys are expected in production.
if SECRET_KEY.startswith("django-insecure"):  # noqa: F405
    raise RuntimeError("Set a strong SECRET_KEY environment variable in production.")

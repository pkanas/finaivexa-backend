"""Fast, isolated settings for the test suite.

Forces SQLite in memory and disables all external AI calls so tests are
deterministic and never spend money or require network access.
"""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-only-secret-key-with-at-least-32-characters-for-jwt"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

OPENAI_API_KEY = ""
OPENAI_MODEL = "test-model"

CELERY_TASK_ALWAYS_EAGER = True

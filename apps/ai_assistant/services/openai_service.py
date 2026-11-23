"""Thin, fail-safe wrapper around the OpenAI SDK.

The API key is read from Django settings (populated from the environment) and
is never returned to clients. All methods return ``None`` when the provider is
unavailable or errors, so callers fall back to deterministic logic.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self._client = None

    @property
    def available(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    @property
    def client(self):
        if not self.available:
            return None
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=getattr(settings, "AI_REQUEST_TIMEOUT", 20),
                max_retries=1,
            )
        return self._client

    def json_completion(self, system_prompt, user_prompt):
        """Return a parsed JSON object from the model, or ``None``."""
        if not self.available:
            return None
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                response_format={"type": "json_object"},
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content
            if not content:
                return None
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            logger.warning("OpenAI JSON completion failed: %s", exc)
            return None

    def text_completion(self, system_prompt, user_prompt):
        """Return a short plain-text answer, or ``None``."""
        if not self.available:
            return None
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                temperature=0.3,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as exc:
            logger.warning("OpenAI text completion failed: %s", exc)
            return None

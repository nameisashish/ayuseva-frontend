"""Groq-only text generation with bounded model fallback and safe errors."""
import logging

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    "configuration": "The AI service is not configured. Please contact the site owner.",
    "authentication": "The AI service could not authenticate. Please contact the site owner.",
    "model_access": "The AI models are unavailable for this account. Please contact the site owner.",
    "rate_limit": "The AI service is busy or has reached its usage limit. Please try again later.",
    "timeout": "The AI service took too long to respond. Please try again.",
    "unavailable": "The AI service is temporarily unavailable. Please try again later.",
    "invalid_response": "The AI service could not complete its response. Please try again.",
}


class GroqError(Exception):
    def __init__(self, code):
        self.code = code
        self.public_message = ERROR_MESSAGES[code]
        super().__init__(self.public_message)


def complete(api_key, messages, max_tokens=4096):
    api_key = (api_key or "").strip()
    if not api_key:
        raise GroqError("configuration")

    for index, model in enumerate(GROQ_MODELS):
        try:
            response = requests.post(
                GROQ_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "reasoning_effort": "low",
                    "include_reasoning": False,
                    # GPT-OSS uses this budget for both reasoning and final text.
                    "max_completion_tokens": max(2048, max_tokens),
                },
                timeout=(5, 25),
                allow_redirects=False,
            )
        except requests.Timeout:
            logger.warning("Groq request timed out: model=%s", model)
            raise GroqError("timeout") from None
        except requests.RequestException:
            logger.warning("Groq connection failed: model=%s", model)
            raise GroqError("unavailable") from None

        if response.status_code != 200:
            status = response.status_code
            code = "unavailable"
            if status == 401:
                code = "authentication"
            elif status in (403, 404):
                code = "model_access"
            elif status == 429:
                code = "rate_limit"
            # Do not log provider bodies: they can echo prompts or credentials.
            logger.warning("Groq failure: status=%s model=%s category=%s", status, model, code)
            if code == "model_access" and index + 1 < len(GROQ_MODELS):
                continue
            raise GroqError(code)

        try:
            choice = response.json()["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
                raise ValueError("Incomplete completion")
        except (ValueError, KeyError, TypeError, IndexError):
            logger.warning("Groq returned an incomplete response: model=%s", model)
            raise GroqError("invalid_response") from None
        return content.strip()

    raise GroqError("model_access")

import logging
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from groq import Groq, RateLimitError

load_dotenv()

logger = logging.getLogger(__name__)

_groq_api_key = os.getenv("GROQ_API_KEY")
_groq_client: Groq | None = Groq(api_key=_groq_api_key) if _groq_api_key else None

_gemini_api_key = os.getenv("GEMINI_API_KEY")
_gemini_client: genai.Client | None = (
    genai.Client(api_key=_gemini_api_key) if _gemini_api_key else None
)
_GEMINI_MODEL = "gemini-2.0-flash"


def _call_gemini(prompt: str, json_mode: bool) -> str | None:
    if _gemini_client is None:
        logger.error("GEMINI_API_KEY not set; cannot fall back to Gemini")
        return None

    config = genai_types.GenerateContentConfig(max_output_tokens=2048)
    if json_mode:
        config = genai_types.GenerateContentConfig(
            max_output_tokens=2048,
            response_mime_type="application/json",
        )

    response = _gemini_client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config=config,
    )
    return response.text


def call_llm(prompt: str, json_mode: bool = True, max_retries: int = 3) -> str | None:
    if _groq_client is None:
        logger.error("GROQ_API_KEY not set")
        return None

    kwargs = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "timeout": 20,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(max_retries):
        logger.info("LLM call attempt %d/%d (Groq)", attempt + 1, max_retries)
        try:
            response = _groq_client.chat.completions.create(**kwargs)
            logger.info("Using Groq")
            return response.choices[0].message.content
        except RateLimitError as exc:
            logger.warning("Groq RateLimitError: %s -- switching to Gemini", exc)
            break
        except Exception as exc:
            # 503 / service unavailable: bail out to Gemini immediately instead of retrying
            if "503" in str(exc) or "service unavailable" in str(exc).lower():
                logger.warning("Groq 503: %s -- switching to Gemini", exc)
                break
            logger.warning("Groq attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    logger.info("Groq failed, switched to Gemini")
    try:
        result = _call_gemini(prompt, json_mode)
        if result is not None:
            return result
    except Exception as exc:
        logger.error("Gemini attempt failed: %s", exc)

    logger.error("All LLM attempts failed (Groq + Gemini)")
    return None

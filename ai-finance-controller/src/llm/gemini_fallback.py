"""Validated Gemini fallback for low-confidence transaction predictions."""

import json
import os
import re
import time
from typing import Any, Dict, Iterable, Optional


GEMINI_MODEL = "gemini-3.5-flash-lite"
MAX_GEMINI_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 8.0
MIN_REQUEST_INTERVAL_SECONDS = 0.25
_last_request_monotonic = 0.0


def _error_result(error_code: str, message: str, **details: Any) -> Dict[str, Any]:
    """Return a stable, non-throwing error result without sensitive details."""
    return {"ok": False, "error_code": error_code, "error": message, **details}


def _sanitized_exception_details(error: Exception) -> Dict[str, Any]:
    """Return bounded diagnostics without retaining credentials or headers."""
    message = str(error)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    message = re.sub(r"AIza[\w-]+", "[REDACTED]", message)
    message = re.sub(r"(?i)(x-goog-api-key|authorization)\s*[:=]\s*[^\s,;]+", r"\1: [REDACTED]", message)
    details: Dict[str, Any] = {
        "gemini_exception_type": type(error).__name__,
        "gemini_provider_message": message[:1000],
    }
    for attribute in ("status_code", "status", "code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            details["gemini_http_status_code"] = value
            break
    return details


def _retry_after_seconds(error: Exception) -> Optional[float]:
    """Read a numeric Retry-After value when the SDK exposes response headers."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) or getattr(error, "headers", None)
    if not headers:
        return None
    value = headers.get("Retry-After") or headers.get("retry-after")
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_transient_provider_error(error: Exception) -> bool:
    """Retry only explicit 429 and 5xx provider responses."""
    details = _sanitized_exception_details(error)
    status_code = details.get("gemini_http_status_code")
    return status_code == 429 or (isinstance(status_code, int) and 500 <= status_code <= 599)


def _pace_request(sleep_fn: Any, monotonic_fn: Any) -> None:
    """Throttle sequential calls conservatively to reduce burst rate limiting."""
    global _last_request_monotonic
    wait = MIN_REQUEST_INTERVAL_SECONDS - (monotonic_fn() - _last_request_monotonic)
    if wait > 0:
        sleep_fn(wait)
    _last_request_monotonic = monotonic_fn()


def validate_gemini_response(payload: Any, allowed_categories: Iterable[str]) -> Dict[str, Any]:
    """Validate the required Gemini JSON fields against the local model classes."""
    allowed = {str(category) for category in allowed_categories}
    if not isinstance(payload, dict):
        return _error_result("malformed_response", "Gemini response must be a JSON object.")
    required = {"category", "confidence", "reason"}
    if not required.issubset(payload):
        return _error_result("missing_fields", "Gemini response is missing required fields.")
    category = payload["category"]
    confidence = payload["confidence"]
    reason = payload["reason"]
    if not isinstance(category, str) or category not in allowed:
        return _error_result("invalid_category", "Gemini returned a category outside the allowed list.")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return _error_result("invalid_confidence", "Gemini confidence must be numeric.")
    if not 0.0 <= float(confidence) <= 1.0:
        return _error_result("invalid_confidence", "Gemini confidence must be between 0 and 1.")
    if not isinstance(reason, str) or not reason.strip():
        return _error_result("invalid_reason", "Gemini reason must be a non-empty string.")
    return {
        "ok": True,
        "category": category,
        "confidence": float(confidence),
        "reason": reason.strip(),
    }


def classify_with_gemini(
    transaction_description: str,
    allowed_categories: Iterable[str],
    client: Optional[Any] = None,
    sleep_fn: Any = time.sleep,
    monotonic_fn: Any = time.monotonic,
) -> Dict[str, Any]:
    """Classify one transaction with Gemini structured output, safely.

    The API key is read only from GEMINI_API_KEY when a client is not injected.
    This function catches provider, authentication, rate-limit, and network
    exceptions so the local categorization flow remains available.
    """
    categories = sorted({str(category) for category in allowed_categories})
    if not categories:
        return _error_result("invalid_allowed_categories", "At least one allowed category is required.")
    if not isinstance(transaction_description, str) or not transaction_description.strip():
        return _error_result("invalid_transaction", "Transaction description must be non-empty.")

    if client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return _error_result("missing_api_key", "GEMINI_API_KEY is not configured for this process.")
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
        except ImportError:
            return _error_result("sdk_unavailable", "google-genai is not installed.")
        except Exception:
            return _error_result("client_initialization_failed", "Gemini client could not be initialized.")

    schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": categories},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["category", "confidence", "reason"],
    }
    prompt = (
        "Classify this financial transaction into exactly one allowed category. "
        "Do not invent categories. Return JSON matching the supplied schema. "
        f"Allowed categories: {', '.join(categories)}.\n"
        f"Transaction description: {transaction_description}"
    )
    for attempt in range(1, MAX_GEMINI_ATTEMPTS + 1):
        try:
            _pace_request(sleep_fn, monotonic_fn)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json", "response_json_schema": schema},
            )
            response_text = getattr(response, "text", None)
            if not isinstance(response_text, str):
                return _error_result("malformed_response", "Gemini did not return JSON text.")
            try:
                payload = json.loads(response_text)
            except json.JSONDecodeError:
                return _error_result("malformed_response", "Gemini returned malformed JSON.")
            return validate_gemini_response(payload, categories)
        except Exception as error:
            diagnostic = _sanitized_exception_details(error)
            if _is_transient_provider_error(error) and attempt < MAX_GEMINI_ATTEMPTS:
                delay = _retry_after_seconds(error)
                if delay is None:
                    delay = min(BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)), MAX_RETRY_DELAY_SECONDS)
                sleep_fn(delay)
                continue
            status_code = diagnostic.get("gemini_http_status_code")
            error_code = "gemini_rate_limited" if status_code == 429 else "gemini_api_error"
            return _error_result(
                error_code,
                "Gemini request failed; local ML result remains available.",
                gemini_request_attempts=attempt,
                **diagnostic,
            )

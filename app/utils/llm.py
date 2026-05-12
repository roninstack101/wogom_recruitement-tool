import os
import time
import threading
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GROQ_MODEL   = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES  = 3
RETRY_DELAY  = 5

COST_PER_M = {
    "groq_input":    0.59,
    "groq_output":   0.79,
    "gemini_input":  0.10,
    "gemini_output": 0.40,
}


class _MultiProviderManager:
    """
    Flat rotation across all available keys from both Groq and Gemini.
    Groq keys are tried first (listed first), Gemini acts as fallback.
    Thread-safe.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Build ordered list: Groq keys first, then Gemini keys
        self._providers = []
        for k, v in sorted(os.environ.items()):
            if k.startswith("GROQ_API_KEY") and v.strip():
                self._providers.append(("groq", v.strip()))
            elif k.startswith("GOOGLE_API_KEY") and v.strip():
                self._providers.append(("gemini", v.strip()))

        if not self._providers:
            raise RuntimeError("No GROQ_API_KEY or GOOGLE_API_KEY found in environment")

        self._index = 0

    @property
    def current(self) -> tuple:
        with self._lock:
            return self._providers[self._index]

    def rotate(self) -> tuple:
        with self._lock:
            self._index = (self._index + 1) % len(self._providers)
            return self._providers[self._index]

    @property
    def count(self) -> int:
        return len(self._providers)


_manager = _MultiProviderManager()

_usage = {"input": 0, "output": 0, "calls": 0, "retries": 0}
_usage_lock = threading.Lock()


def get_usage() -> dict:
    with _usage_lock:
        inp  = _usage["input"]
        out  = _usage["output"]
        # Approximate cost — weighted average across both providers
        cost = (inp * 0.30 + out * 0.55) / 1_000_000
        return {
            "calls":              _usage["calls"],
            "retries":            _usage["retries"],
            "input_tokens":       inp,
            "output_tokens":      out,
            "total_tokens":       inp + out,
            "estimated_cost_usd": round(cost, 6),
        }


def reset_usage() -> None:
    with _usage_lock:
        _usage.update({"input": 0, "output": 0, "calls": 0, "retries": 0})


def get_llm():
    provider, key = _manager.current
    if provider == "groq":
        return ChatGroq(model=GROQ_MODEL, temperature=0.3, api_key=key)
    else:
        return ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0.3, google_api_key=key)


def invoke_llm(prompt: str):
    """
    Single entry point for all LLM calls.
    Rotates through Groq keys first, then falls back to Gemini keys on rate limits.
    Handles truncated responses (finish_reason=length / MAX_TOKENS) the same way.
    """
    last_error = None

    for attempt in range(MAX_RETRIES * _manager.count):
        provider, key = _manager.current
        try:
            llm = get_llm()
            print(f"[LLM] Using {provider} key ...{key[-6:]} (attempt {attempt + 1})")
            response = llm.invoke(prompt)

            # Detect truncated response
            finish_reason = response.response_metadata.get("finish_reason", "")
            if finish_reason in ("length", "MAX_TOKENS"):
                new = _manager.rotate()
                with _usage_lock:
                    _usage["retries"] += 1
                print(f"[LLM] Truncated ({finish_reason}) — switching to {new[0]} key ...{new[1][-6:]} (attempt {attempt + 1})")
                time.sleep(RETRY_DELAY)
                continue

            # Record token usage
            if provider == "groq":
                meta = response.response_metadata.get("token_usage", {})
                inp = meta.get("prompt_tokens", 0)
                out = meta.get("completion_tokens", 0)
            else:
                usage = response.usage_metadata or {}
                inp = usage.get("input_tokens", 0)
                out = usage.get("output_tokens", 0)

            with _usage_lock:
                _usage["input"]  += inp
                _usage["output"] += out
                _usage["calls"]  += 1

            return response

        except Exception as e:
            err = str(e).lower()
            is_rate_limit = any(x in err for x in [
                "rate limit", "429", "too many requests", "tokens per",
                "quota", "resource exhausted", "not_found", "no longer available",
                "model_not_found", "404",
            ])

            if is_rate_limit:
                new = _manager.rotate()
                with _usage_lock:
                    _usage["retries"] += 1
                print(f"[LLM] Rate limit on {provider} — switching to {new[0]} key ...{new[1][-6:]} (attempt {attempt + 1})")
                time.sleep(RETRY_DELAY)
                last_error = e
            else:
                raise

    raise RuntimeError(f"All {_manager.count} keys exhausted after retries. Last error: {last_error}")

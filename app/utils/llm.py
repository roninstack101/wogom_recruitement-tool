import os
import time
import threading
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries on the same key


class _KeyManager:
    """
    Rotates through available GROQ_API_KEY_1/2/3 on rate limit errors.
    Thread-safe — safe to use with ThreadPoolExecutor.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._keys = [
            v for k, v in os.environ.items()
            if k.startswith("GROQ_API_KEY") and v.strip()
        ]
        if not self._keys:
            raise RuntimeError("No GROQ_API_KEY found in environment")
        self._index = 0

    @property
    def current(self) -> str:
        with self._lock:
            return self._keys[self._index]

    def rotate(self) -> str:
        """Move to the next key. Returns the new key."""
        with self._lock:
            self._index = (self._index + 1) % len(self._keys)
            return self._keys[self._index]

    @property
    def count(self) -> int:
        return len(self._keys)


_key_manager = _KeyManager()

# Session-wide token counter — resets on server restart
_usage = {"input": 0, "output": 0, "calls": 0, "retries": 0}
_usage_lock = threading.Lock()

COST_PER_M_INPUT  = 0.59   # USD per 1M input tokens  (Groq LLaMA 3.3-70b)
COST_PER_M_OUTPUT = 0.79   # USD per 1M output tokens


def get_usage() -> dict:
    with _usage_lock:
        inp  = _usage["input"]
        out  = _usage["output"]
        cost = (inp * COST_PER_M_INPUT + out * COST_PER_M_OUTPUT) / 1_000_000
        return {
            "calls":               _usage["calls"],
            "retries":             _usage["retries"],
            "input_tokens":        inp,
            "output_tokens":       out,
            "total_tokens":        inp + out,
            "estimated_cost_usd":  round(cost, 6),
        }


def reset_usage() -> None:
    with _usage_lock:
        _usage.update({"input": 0, "output": 0, "calls": 0, "retries": 0})


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=MODEL,
        temperature=0.3,
        api_key=_key_manager.current,
    )


def invoke_llm(prompt: str):
    """
    Invoke the LLM with automatic retry and key rotation for two failure cases:
      1. Rate limit BEFORE call  — API returns 429, caught in except block
      2. Token limit MID-GENERATION — API returns truncated response with finish_reason="length"
    Rotates to the next key and retries for both cases.
    """
    last_error = None

    for attempt in range(MAX_RETRIES * _key_manager.count):
        try:
            llm = get_llm()
            response = llm.invoke(prompt)

            # Case 2: response came back but was cut off mid-generation
            finish_reason = response.response_metadata.get("finish_reason", "stop")
            if finish_reason == "length":
                new_key = _key_manager.rotate()
                with _usage_lock:
                    _usage["retries"] += 1
                print(f"[LLM] Response truncated (finish_reason=length) — rotated to key ...{new_key[-6:]} (attempt {attempt + 1})")
                time.sleep(RETRY_DELAY)
                continue

            # Record token usage from the successful response
            meta = response.response_metadata.get("token_usage", {})
            with _usage_lock:
                _usage["input"]  += meta.get("prompt_tokens", 0)
                _usage["output"] += meta.get("completion_tokens", 0)
                _usage["calls"]  += 1

            return response

        except Exception as e:
            err = str(e).lower()
            # Case 1: rate limit before the call even started
            is_rate_limit = any(x in err for x in ["rate limit", "429", "too many requests", "tokens per"])

            if is_rate_limit:
                new_key = _key_manager.rotate()
                with _usage_lock:
                    _usage["retries"] += 1
                print(f"[LLM] Rate limit hit — rotated to key ...{new_key[-6:]} (attempt {attempt + 1})")
                time.sleep(RETRY_DELAY)
                last_error = e
            else:
                raise

    raise RuntimeError(f"All {_key_manager.count} API keys exhausted after {MAX_RETRIES} retries. Last error: {last_error}")

"""Real Gemini adapter for the model arms (Phase 8 wiring; NO calls made in this environment).

Mirrors the proven multi-turn function-calling pattern in src/argon_lab/arms.py: build the
client once, call client.interactions.create(...) with tools, read ix.steps for function_call
steps, feed function_result back with previous_interaction_id, accumulate usage. It exposes the
SAME normalised shape agent/loop.py consumes, so the identical loop drives mock and real.

Key handling: the client is created lazily from GEMINI_API_KEY in the environment. This module
NEVER prints, logs, or returns the key, and never accepts a key as an argument. If the SDK or key
is missing, create() raises a clear error BEFORE any network attempt.

This file makes no API call at import time. A call happens only when .create() is invoked by the
runner, which is gated behind the spending guard and explicit confirmation.
"""
from __future__ import annotations

import json
import os
import time

from . import schemas

# Per-turn generation cap (includes thinking). Bounds a single call's output cost.
MAX_OUTPUT_TOKENS = 8_000
TIMEOUT_MS = 120_000          # SDK-level timeout per call
RETRY_ATTEMPTS = 0            # no client-side retries (a failed call is logged, not silently retried)

USAGE_KEYS = ["total_input_tokens", "total_output_tokens", "total_thought_tokens",
              "total_cached_tokens", "total_tool_use_tokens", "total_tokens"]


class GeminiClient:
    """A thin, model-pinned adapter. One instance per (model, level)."""

    def __init__(self, model: str, level: str = "medium"):
        self.model = model
        self.level = level
        self._client = None
        self._prev_id = None          # previous_interaction_id for multi-turn continuity
        self._genai = None
        self._types = None

    # -- lazy client construction (no key touched until here) ----------------------
    def _ensure_client(self):
        if self._client is not None:
            return
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not set in the environment")
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:  # pragma: no cover - environment dependent
            raise RuntimeError("google-genai SDK is not installed (pip install 'google-genai>=2.30.1')") from e
        self._genai, self._types = genai, types
        # the SDK reads GEMINI_API_KEY from the environment itself; we never pass it explicitly
        self._client = genai.Client(http_options=types.HttpOptions(
            timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=RETRY_ATTEMPTS)))

    def reset(self):
        """Start a fresh investigation (clears the interaction chain)."""
        self._prev_id = None

    def _usage_dict(self, ix) -> dict:
        u = getattr(ix, "usage", None)
        return {k: (getattr(u, k, 0) or 0) if u else 0 for k in USAGE_KEYS}

    def create(self, messages, tools, system) -> dict:
        """One model turn, normalised to the loop's shape. `messages` carries the running
        transcript the loop maintains; for the real API we instead thread previous_interaction_id
        and send only the latest input (the first user message, or the tool results)."""
        self._ensure_client()
        # Determine what to send this turn from the last message the loop appended.
        last = messages[-1]
        if last["role"] == "user":
            send_input = last["content"]
            prev = None
            self._prev_id = None
        elif last["role"] == "tool":
            # gather the contiguous trailing tool results into function_result inputs
            send_input = []
            for m in reversed(messages):
                if m["role"] != "tool":
                    break
                send_input.insert(0, {"type": "function_result", "name": m["name"],
                                      "call_id": m.get("call_id"),
                                      "result": [{"type": "text", "text": json.dumps(m["content"])}]})
            prev = self._prev_id
        else:
            send_input = last.get("content", "")
            prev = self._prev_id

        kw = dict(model=self.model, input=send_input, system_instruction=system,
                  tools=tools, generation_config={"thinking_level": self.level,
                                                  "max_output_tokens": MAX_OUTPUT_TOKENS})
        if prev:
            kw["previous_interaction_id"] = prev

        t0 = time.time()
        try:
            ix = self._client.interactions.create(**kw)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            status = ("timeout" if "deadline" in msg or "timeout" in msg or "timed out" in msg
                      else "error")
            return {"function_call": None, "verdict": None,
                    "usage": {}, "status": status, "error": str(e)[:300],
                    "latency_s": round(time.time() - t0, 2)}
        self._prev_id = getattr(ix, "id", None)
        usage = self._usage_dict(ix)
        usage_norm = {"input_tokens": usage["total_input_tokens"],
                      "output_tokens": usage["total_output_tokens"],
                      "thinking_tokens": usage["total_thought_tokens"],
                      "cached_tokens": usage["total_cached_tokens"]}

        steps = getattr(ix, "steps", None) or []
        fcalls = [s for s in steps if getattr(s, "type", "") == "function_call"]
        if fcalls:
            c = fcalls[0]   # the loop executes one call per turn; extra calls re-emerge next turn
            fc = {"name": c.name, "args": dict(getattr(c, "arguments", None) or {}),
                  "call_id": getattr(c, "id", None)}
            return {"function_call": fc, "verdict": None, "usage": usage_norm,
                    "status": "ok", "error": None, "latency_s": round(time.time() - t0, 2),
                    "raw_usage": usage}

        # No function call: either a final text answer, or budget exhausted.
        text = getattr(ix, "output_text", "") or ""
        if usage["total_thought_tokens"] > 1000 and usage["total_output_tokens"] <= 10:
            return {"function_call": None, "verdict": None, "usage": usage_norm,
                    "status": "incomplete", "error": "thinking budget exhausted",
                    "latency_s": round(time.time() - t0, 2), "raw_usage": usage}
        return {"function_call": None, "verdict": None, "usage": usage_norm,
                "status": "ok", "error": None, "text": text,
                "latency_s": round(time.time() - t0, 2), "raw_usage": usage}

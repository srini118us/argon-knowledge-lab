"""Minimal Gemini 4 Argon access test (Interactions API, google-genai >= 2.30.1).

Run:  export GEMINI_API_KEY=...  &&  python argon_access_test.py
Cost: one tiny request, well under one cent.
"""
import os, sys, time
from google import genai
from google.genai import errors

MODEL = "gemini-4-argon"

if not os.getenv("GEMINI_API_KEY"):
    sys.exit("GEMINI_API_KEY is not set. Create a key in a billed project: https://aistudio.google.com/apikey")

client = genai.Client()
t0 = time.time()
try:
    ix = client.interactions.create(
        model=MODEL,
        input="Reply with exactly: ARGON_OK",
        generation_config={"thinking_level": "low"},
    )
except errors.APIError as e:
    print(f"ACCESS FAILED  code={e.code}  status={e.status}\n{e.message}")
    sys.exit(1)

print("ACCESS OK")
print("model:", MODEL)
print("output:", ix.output_text)
print("latency_s:", round(time.time() - t0, 2))
print("usage:", getattr(ix, "usage", None))

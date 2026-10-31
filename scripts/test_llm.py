#!/usr/bin/env python3
"""
test_llm.py — quick check: does the configured LLM backend work?
Run: python scripts/test_llm.py
"""
import config  # loads .env
from llm_backend import get_backend

backend = get_backend()
print(f"Backend: {backend.name()}")
print("Sending a test prompt...")
resp = backend.ask("Say exactly: PONG")
print(f"Response: {resp!r}")
if "PONG" in resp.upper():
    print("✓ Backend is working")
else:
    print("⚠ Backend responded, but not PONG. May be OK, but double-check.")

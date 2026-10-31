#!/usr/bin/env python3
"""
attack.py — feed decompiled code to the LLM, N times.
The LLM backend is selected via LLM_BACKEND in .env (default: openai).
Each response is saved under results/raw/.
"""
import time
import argparse
import config as C
from llm_backend import get_backend

PROMPT_TEMPLATE = (C.ROOT / "scripts" / "prompt.txt").read_text()


def attack(program, technique, n, sleep=2.0):
    code = C.decompiled_path(program, technique).read_text()
    prompt = PROMPT_TEMPLATE.replace("{CODE}", code)
    backend = get_backend()
    print(f"[attack] backend = {backend.name()}")

    responses = []
    for i in range(1, n + 1):
        try:
            text = backend.ask(prompt)
        except Exception as e:
            text = f"ERROR: {e}"
            print(f"[attack] {program}/{technique} run {i}/{n}: {text}")

        from score import response_path
        p = response_path(program, technique, i, backend.name())
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        responses.append(text)
        print(f"[attack] {program}/{technique} run {i}/{n}: {text.strip()[:80]}")

        if i < n:
            time.sleep(sleep)
    return responses


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--technique", required=True)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--sleep", type=float, default=2.0)
    a = ap.parse_args()
    attack(a.program, a.technique, a.n, a.sleep)

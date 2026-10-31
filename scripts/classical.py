#!/usr/bin/env python3
"""
classical.py — classical attack using the `strings` command.
If `strings` finds the secret directly in the binary, a traditional attacker
breaks the technique without needing an LLM.
Used for RQ3: are LLM and classical attacks defeated by the same techniques?
"""
import json
import subprocess
import argparse
import config as C


def classical_attack(program, technique):
    binary = C.binary_path(program, technique)
    if not binary.exists():
        return {"found_direct": None, "error": "binary does not exist"}

    secrets = json.loads(C.SECRETS_FILE.read_text())
    secret = secrets[program]["secret"]

    try:
        result = subprocess.run(
            ["strings", str(binary)],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout
    except FileNotFoundError:
        return {"found_direct": None, "error": "'strings' command missing"}

    if result.returncode != 0:
        return {"found_direct": None, "error": result.stderr.strip()}
    found = secret in output
    return {
        "found_direct": found,
        "total_strings": len(output.splitlines()),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--technique", required=True)
    a = ap.parse_args()
    r = classical_attack(a.program, a.technique)
    print(f"[classical] {a.program}/{a.technique}: {r}")

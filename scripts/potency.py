#!/usr/bin/env python3
"""
potency.py — measure code complexity (Collberg-Thomborson 'potency').
  - cyclomatic complexity (CC) from source C (via 'lizard')
  - instruction count from the binary (via 'objdump -d')

Requires: pip install lizard
"""
import re
import subprocess
import argparse
import config as C


def _cc_from_source(source_path, func_name=None):
    """Return (CC, NLOC) of the function; filter by func_name if given."""
    import lizard
    functions = lizard.analyze_file(str(source_path)).function_list
    if func_name:
        functions = [f for f in functions if f.name == func_name]
    if not functions:
        return None, None
    return sum(f.cyclomatic_complexity for f in functions), sum(f.nloc for f in functions)


def _instr_count_from_binary(binary_path):
    """Count instructions from 'objdump -d <binary>'."""
    try:
        result = subprocess.run(
            ["objdump", "-d", str(binary_path)],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    count = 0
    for line in result.stdout.splitlines():
        # Instruction lines look like:
        #   "100003f98: 94 00 00 02 bl 0x100003fa0 ..." (macOS llvm-objdump)
        #   "  100003f98:  94 00 00 02 bl ..."         (GNU objdump)
        # Accept any leading whitespace, then hex offset, colon, then hex bytes.
        if re.match(r"^\s*[0-9a-f]{4,}:\s+[0-9a-f]{2}", line, re.IGNORECASE):
            count += 1
    return count


def potency(program, technique):
    """Return dict with cc, nloc, instr_count for a program+technique."""
    # Re-load programs.json in case it was updated (e.g. by UI backend)
    import json
    pj = C.ROOT / "targets" / "programs.json"
    if pj.exists():
        try:
            C.PROGRAMS.update(json.loads(pj.read_text()))
        except Exception:
            pass

    if technique == "baseline":
        source = C.source_path(program)
    else:
        source = C.obf_source_path(program, technique)
    binary = C.binary_path(program, technique)

    func = C.PROGRAMS.get(program, {}).get("func", "")
    main_func = func.split(",")[0] if func else None

    cc, nloc = _cc_from_source(source, main_func)
    instr = _instr_count_from_binary(binary)
    return {"cc": cc, "nloc": nloc, "instr_count": instr}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--technique", required=True)
    a = ap.parse_args()
    r = potency(a.program, a.technique)
    print(f"[potency] {a.program}/{a.technique}: {r}")

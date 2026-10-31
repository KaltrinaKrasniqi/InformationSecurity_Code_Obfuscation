#!/usr/bin/env python3
"""
decompile.py — produce pseudo-C from a binary using Ghidra headless.
Writes output under decompiled/c/<baseline|obfuscated>/.
"""
import os
import sys
from pathlib import Path
import tempfile
import subprocess
import argparse
import config as C


def decompile(program, technique):
    if not C.GHIDRA_HOME:
        raise RuntimeError("Set GHIDRA_HOME in .env to the extracted Ghidra folder")
    binary = C.binary_path(program, technique)
    out = C.decompiled_path(program, technique)
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.exists():
        out.unlink()
    with tempfile.TemporaryDirectory(prefix="ghidra_proj_") as tmp:
        cmd = [
            str(Path(C.GHIDRA_HOME) / "support" / ("analyzeHeadless.bat" if os.name == "nt" else "analyzeHeadless")),
            tmp, "tmpproj",
            "-import", str(binary),
            "-scriptPath", str(C.ROOT / "scripts"),
            "-postScript", "ghidra_decompile.java", str(out),
            "-deleteProject",
        ]
        print("[ghidra]", " ".join(cmd))
        env = os.environ.copy()
        state = C.ROOT / "tools" / "ghidra-state"
        for name, variable in [("config", "XDG_CONFIG_HOME"), ("cache", "XDG_CACHE_HOME")]:
            folder = state / name
            folder.mkdir(parents=True, exist_ok=True)
            env[variable] = str(folder)
        local_jdk = next((p for p in (C.ROOT / "tools").glob("jdk*") if (p / "bin" / ("java.exe" if os.name == "nt" else "java")).is_file()), None)
        java_home = os.environ.get("GHIDRA_JAVA_HOME") or (str(local_jdk) if local_jdk else None)
        if java_home:
            env["JAVA_HOME"] = java_home
            env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", "")
        subprocess.run(cmd, check=True, env=env, stdin=subprocess.DEVNULL, timeout=300, stdout=sys.stdout, stderr=sys.stdout)
    if not out.is_file() or not out.read_text(encoding="utf-8").strip():
        raise RuntimeError("Ghidra produced no decompiled code")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--technique", required=True)
    a = ap.parse_args()
    out = decompile(a.program, a.technique)
    print("OK ->", out)

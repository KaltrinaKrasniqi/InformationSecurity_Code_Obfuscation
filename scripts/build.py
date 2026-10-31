#!/usr/bin/env python3
"""
build.py — build the binary for a program + technique.
  baseline              -> compile only (clang)
  individual technique  -> single Tigress pass -> compile
  combo with Virtualize -> two-pass Tigress (also hides the auxiliary
                           functions created by EncodeLiterals) -> compile
Flow: SOURCE -> OBFUSCATION -> (optional 2nd pass) -> COMPILE -> BINARY
"""
import os
import re
import tempfile
import subprocess
import argparse
import json
import sys
import config as C


def _read_tigress_args(technique, func):
    """Read Tigress flags from obfuscation/configs/c/<technique>.tigress."""
    cfg = C.CONFIGS_DIR / f"{technique}.tigress"
    if not cfg.exists():
        raise FileNotFoundError(f"Config not found: {cfg}")
    args = []
    for line in cfg.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.replace("FUNC", func)
        args.extend(line.split())
    return args


def _find_helper_functions(c_text):
    """After EncodeLiterals, Tigress creates helpers like __N_stringEncoder.
    Return their names so pass 2 can virtualize them too."""
    pattern = r'\b([A-Za-z_]\w*(?:string[Ee]ncoder|encodeString)\w*)\s*\('
    found = re.findall(pattern, c_text)
    return list(dict.fromkeys(found))  # unique, preserve order


def _run_tigress_pass2(obf_src, main_func, has_flatten, env, seed):
    """Pass 2: Virtualize (and optionally Flatten) over main_func + stringEncoders.
    If no stringEncoder is found (e.g. secret is numeric, not a string),
    still apply Virtualize over the main function alone."""
    text = obf_src.read_text()
    helpers = _find_helper_functions(text)
    if not helpers:
        print("[pass2] no helper from EncodeLiterals (likely numeric secret), virtualizing main_func only")
    funcs = ",".join([main_func] + helpers)
    print(f"[pass2] will also hide: {helpers}")

    transforms = []
    if has_flatten:
        transforms += ["--Transform=Flatten", f"--Functions={funcs}"]
    transforms += ["--Transform=Virtualize", f"--Functions={funcs}"]

    tmp_out = obf_src.with_suffix(".pass2.c")
    cmd = [
        C.TIGRESS_BIN,
        f"--Environment={C.TIGRESS_ENVIRONMENT}",
        f"--Seed={seed}",
        *transforms,
        f"--out={tmp_out}",
        str(obf_src),
    ]
    print("[tigress2]", " ".join(cmd))
    with tempfile.TemporaryDirectory(prefix="tigress2_") as tmp:
        subprocess.run(cmd, check=True, env=env, cwd=tmp, timeout=120, stdout=sys.stdout, stderr=sys.stdout)
    tmp_out.replace(obf_src)



def build(program, technique, seed=11):
    src = C.source_path(program)
    out_bin = C.binary_path(program, technique)
    out_bin.parent.mkdir(parents=True, exist_ok=True)

    # ---- BASELINE: compile only ----
    if technique == "baseline":
        cmd = [C.CC, *C.CFLAGS, "-I", str(C.TARGETS_DIR), str(src), "-o", str(out_bin)]
        print("[build]", " ".join(cmd))
        subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stdout)
        return out_bin

    func = C.PROGRAMS[program]["func"]
    obf_src = C.obf_source_path(program, technique)
    obf_src.parent.mkdir(parents=True, exist_ok=True)

    tigress_args = _read_tigress_args(technique, func)
    tcmd = [
        C.TIGRESS_BIN,
        f"--Environment={C.TIGRESS_ENVIRONMENT}",
        f"--Seed={seed}",
        *tigress_args,
        f"--out={obf_src}",
        str(src),
    ]
    env = os.environ.copy()
    if C.TIGRESS_HOME:
        env["TIGRESS_HOME"] = C.TIGRESS_HOME
        env["PATH"] = f"{C.TIGRESS_HOME}{os.pathsep}" + env.get("PATH", "")
    print("[tigress]", " ".join(tcmd))
    # Run Tigress in a tmp dir so jitter_template-*.c don't end up at repo root
    with tempfile.TemporaryDirectory(prefix="tigress_") as _tmp:
        subprocess.run(tcmd, check=True, env=env, cwd=_tmp, timeout=120, stdout=sys.stdout, stderr=sys.stdout)

    # ---- 2-PASS: config may request virtualization over stringEncoders ----
    cfg_text = (C.CONFIGS_DIR / f"{technique}.tigress").read_text()
    needs_pass2 = "NEEDS_VIRTUALIZE_PASS2" in cfg_text
    if needs_pass2:
        has_flatten = "WITH_FLATTEN" in cfg_text
        _run_tigress_pass2(obf_src, func, has_flatten, env, seed)

    # ---- COMPILE ----
    cmd = [C.CC, *C.CFLAGS, "-I", str(C.TARGETS_DIR), str(obf_src), "-o", str(out_bin)]
    print("[build]", " ".join(cmd))
    subprocess.run(cmd, check=True, stdout=sys.stdout, stderr=sys.stdout)
    return out_bin


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--program", required=True)
    ap.add_argument("--technique", required=True)
    a = ap.parse_args()
    b = build(a.program, a.technique)
    print("OK ->", b)

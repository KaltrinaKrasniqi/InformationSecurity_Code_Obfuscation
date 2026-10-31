"""Shared configuration loaded from the local .env and environment variables."""
import os
import json
import shutil
import platform
from pathlib import Path

# Project root: parent of scripts/
ROOT = Path(__file__).resolve().parent.parent


def _load_env():
    """Load local settings without overriding explicit environment variables."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    from dotenv import load_dotenv
    load_dotenv(env_path, override=False)


_load_env()

# ---------- Legacy configuration values (current backend uses OpenAI) ----------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ---------- Local tools ----------
CC = os.environ.get("CC", "clang" if shutil.which("clang") else "gcc")            # compiler (Mac: clang, Linux: gcc)
CFLAGS = ["-O0"]                              # no optimization for a fixed, inspectable baseline
TIGRESS_HOME = os.environ.get("TIGRESS_HOME", "")
TIGRESS_BIN = os.environ.get("TIGRESS_BIN", "tigress")
TIGRESS_ENVIRONMENT = os.environ.get("TIGRESS_ENVIRONMENT", "x86_64:Darwin:Clang:9.1")
GHIDRA_HOME = os.environ.get("GHIDRA_HOME", "")
if not GHIDRA_HOME:
    GHIDRA_HOME = next((str(p) for p in (ROOT / "tools").glob("ghidra*_PUBLIC")), "")
if not os.environ.get("JAVA_HOME"):
    local_jdk = next((p for p in (ROOT / "tools").glob("jdk*") if (p / "bin" / ("java.exe" if os.name == "nt" else "java")).is_file()), None)
    if local_jdk:
        os.environ["JAVA_HOME"] = str(local_jdk)
        os.environ["PATH"] = str(local_jdk / "bin") + os.pathsep + os.environ.get("PATH", "")


# ---------- Experiment ----------
LANG = "c"
TECHNIQUES = ["baseline", "flatten", "opaque", "encode", "encode_arith", "virtualize", "combo_flat_enc", "combo_virt_enc", "combo_all"]

# program -> {checker function and source filename}
EXAMPLES = json.loads((ROOT / "targets" / "examples.json").read_text(encoding="utf-8"))
PROGRAMS = {p: {"func": m["func"], "src": m["src"]} for p,m in EXAMPLES.items()}


# ---------- Paths ----------
TARGETS_DIR = ROOT / "targets" / LANG
SECRETS_FILE = ROOT / "targets" / "secrets.json"
CONFIGS_DIR = ROOT / "obfuscation" / "configs" / os.environ.get("TIGRESS_CONFIG_SET", LANG)
BUILD_DIR = ROOT / "build" / LANG
DECOMP_DIR = ROOT / "decompiled" / LANG
RESULTS_DIR = ROOT / "results"
RAW_DIR = RESULTS_DIR / "raw"
RESULTS_CSV = RESULTS_DIR / "results.csv"


# ---------- Path helpers ----------
def source_path(program):
    return TARGETS_DIR / program / PROGRAMS[program]["src"]

def binary_path(program, technique):
    suffix = ".exe" if os.name == "nt" else ""
    if technique == "baseline":
        return BUILD_DIR / "baseline" / (program + suffix)
    return BUILD_DIR / "obfuscated" / f"{program}_{technique}{suffix}"

def obf_source_path(program, technique):
    return BUILD_DIR / "obfuscated" / f"{program}_{technique}.c"

def decompiled_path(program, technique):
    sub = "baseline" if technique == "baseline" else "obfuscated"
    return DECOMP_DIR / sub / f"{program}_{technique}.c"

def raw_path(program, technique, run):
    return RAW_DIR / f"{LANG}_{program}_{technique}_run{run}.txt"

# ---------- Legacy provider values ----------
# The implemented backend is OpenAI; these legacy values are retained for compatibility.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")


# Dynamic programs registered by the UI backend
_dyn_programs_file = ROOT / "targets" / "programs.json"
if _dyn_programs_file.exists():
    try:
        PROGRAMS.update(json.loads(_dyn_programs_file.read_text()))
    except Exception as e:
        print(f"[config] WARN: could not read programs.json: {e}")

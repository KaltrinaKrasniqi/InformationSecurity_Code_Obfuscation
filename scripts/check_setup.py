"""Print tool readiness without printing credentials. Optional --llm sends one PONG request."""
import argparse, os, shutil
from pathlib import Path
import config as C
ap = argparse.ArgumentParser()
ap.add_argument("--llm", action="store_true")
a = ap.parse_args()
checks = {
    "Compiler": bool(shutil.which(C.CC)),
    "Tigress": bool(shutil.which(C.TIGRESS_BIN)),
    "Ghidra": bool(C.GHIDRA_HOME) and (Path(C.GHIDRA_HOME) / "support" / ("analyzeHeadless.bat" if os.name == "nt" else "analyzeHeadless")).is_file(),
    "OpenAI key configured": bool(os.environ.get("OPENAI_API_KEY")),
}
for name, ready in checks.items():
    print(f"{name}: {'OK' if ready else 'MISSING'}")
if a.llm:
    from llm_backend import get_backend
    try:
        text = get_backend().ask("Say exactly: PONG")
        print("LLM connection: " + ("OK" if "PONG" in text.upper() else "unexpected response"))
    except Exception as e:
        print(f"LLM connection: FAILED ({type(e).__name__}; HTTP {getattr(e, 'status_code', 'n/a')})")
        raise SystemExit(1)

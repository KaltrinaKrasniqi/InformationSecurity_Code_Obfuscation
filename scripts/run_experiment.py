"""Shared research protocol. See docs/PROTOCOL.md."""
import argparse
from pathlib import Path
from datetime import datetime
import config as C
from experiment import run_protocol
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--programs",nargs="+",default=list(C.EXAMPLES))
    ap.add_argument("--techniques",nargs="+",default=C.TECHNIQUES)
    ap.add_argument("--seeds",nargs="+",type=int,default=[11,29,47])
    ap.add_argument("--n",type=int,default=1)
    ap.add_argument("--modes",nargs="+",choices=["pseudoc","assisted"],default=["pseudoc","assisted"])
    ap.add_argument("--no-attack",action="store_true")
    ap.add_argument("--no-decompile",action="store_true")
    ap.add_argument("--resume",type=Path)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    if a.no_attack != a.no_decompile:ap.error("Use both --no-attack and --no-decompile for build/measurement validation")
    directory=a.resume or a.output or C.RESULTS_DIR/"experiments"/datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    rows=run_protocol(directory,a.programs,a.techniques,a.seeds,a.n,a.modes,build_only=a.no_attack,resume=bool(a.resume))
    print("RESULT DIRECTORY:",directory)
    raise SystemExit(1 if any(r.get("error") for r in rows) else 0)

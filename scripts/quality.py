"""Conservative warning flags, NOT proof of complete decompilation."""
import re
MARKERS=["could not recover jumptable","treating indirect jump as call","bad instruction","halt_baddata","unimplemented","unable to decompile","decompilation failed"]
def assess(code,functions):
    segments=re.split(r"/\* FUNCTION: (.*?) \*/",code)
    wanted=functions.split(",")
    selected=[segments[i+1] for i in range(1,len(segments)-1,2) if segments[i] in wanted or "stringEncoder" in segments[i]]
    relevant="\n".join(selected) if len(segments)>1 else code
    low=relevant.lower();warnings=[m for m in MARKERS if m in low]
    if any(f"DECOMPILE_FAILED: {f}" in code for f in wanted):warnings.append("target_decompilation_failed")
    missing=[f for f in functions.split(",") if not re.search(r"\b"+re.escape(f)+r"\s*\(",code)]
    return {"status":"flagged" if warnings or missing else "no_warning_detected", "warnings":warnings,"missing_functions":missing,
            "interpretation":"Heuristic only; no_warning_detected does not prove complete recovery."}

def wilson(hits,n,z=1.959963984540054):
    if n==0:return [None,None]
    p=hits/n;d=1+z*z/n;c=(p+z*z/(2*n))/d
    e=z*((p*(1-p)/n+z*z/(4*n*n))**0.5)/d
    return [0.0 if hits==0 else max(0,c-e),1.0 if hits==n else min(1,c+e)]

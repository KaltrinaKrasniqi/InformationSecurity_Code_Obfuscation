"""Read-only explanations and code comparisons; never changes experimental evidence or prompts."""
import difflib,re
from collections import Counter
from pathlib import Path
import lizard

def explain(job):
    rows=job.get("results",[]);cells={}
    for row in rows:cells[(row.get("program"),row.get("technique"),row.get("seed"))]=row
    counts={stage:sum(bool(r.get(stage)) for r in cells.values()) for stage in ("built","verified","decompiled")}
    statuses=Counter(x.get("status","legacy") for r in rows for x in r.get("runs",[]))
    incomplete=sum(statuses[s] for s in ("api_error","input_budget_exceeded"))
    progress=job.get("progress",{})
    terminal=job.get("status") not in ("pending","running")
    total=progress.get("total",len(cells));done=progress.get("done",len(cells))
    pipeline_ok=bool(cells) and terminal and done==total and all(counts[k]==total for k in counts)
    if not terminal:title="The experiment is running"
    elif pipeline_ok and incomplete:title="Build and decompilation completed; some LLM trials were not executed"
    elif pipeline_ok:title="The experiment completed successfully as a technical pipeline"
    elif job.get("status")=="interrupted":title="The experiment was interrupted; saved results are shown"
    else:title="The experiment ended with incomplete technical stages"
    notes=[]
    if statuses["input_budget_exceeded"]:notes.append(f"{statuses['input_budget_exceeded']} trials were not sent to the model: the input exceeded the local size limit. These are not API failures or evidence of protection.")
    if statuses["api_error"]:notes.append(f"{statuses['api_error']} trials encountered transport/API errors; they are not counted as failed attacks.")
    if statuses["invalid_format"]:notes.append(f"{statuses['invalid_format']} answers violated the response format and count as unsuccessful recovery.")
    notes.append("Technical success means the test pipeline worked. Protection is assessed separately through the LLM secret-recovery results.")
    return {"title":title,"pipeline_ok":pipeline_ok,"completed_cells":done,"total_cells":total,"stages":counts,"run_statuses":dict(statuses),"notes":notes,"request":job.get("request",{})}

def function_view(code,names):
    functions=lizard.analyze_file.analyze_source_code("comparison.c",code).function_list
    from quality import symbol
    wanted=[f for f in functions if symbol(f.name) in names]
    if not wanted:return {"code":code[:70000],"scope":"The function was not identified; available output is shown", "truncated":len(code)>70000}
    lines=code.splitlines();parts=[]
    for f in wanted:
        parts.append("\n".join(lines[max(0,f.start_line-1):f.end_line]))
    text="\n\n".join(parts)
    return {"code":text[:70000],"scope":"Checker function; additional helpers are available in the full code", "truncated":len(text)>70000}

def compare(job,program,technique,seed,programs):
    rows=job.get("results",[])
    selected=next((r for r in rows if r.get("program")==program and r.get("technique")==technique and r.get("seed")==seed),None)
    if not selected or not selected.get("artifact_dir"):raise ValueError("Select a saved protocol-v2 build")
    baseline=next((r for r in rows if r.get("program")==program and r.get("technique")=="baseline" and r.get("seed")==seed),None)
    folder=Path(selected["artifact_dir"]);source=folder/"source.c"
    original=source.read_text(encoding="utf-8") if source.exists() else "Original source was not retained in this experiment."
    names=programs.get(program,{}).get("func","").split(",")
    if not any(names):names=re.findall(r"\b(check_\w+)\s*\(",original)[:1]
    def decompiled(row):
        if not row:return None
        files=list((Path(row["artifact_dir"])/"decompiled").rglob("*.c"))
        return files[0].read_text(encoding="utf-8") if files else None
    base=decompiled(baseline);transformed=decompiled(selected)
    views={"original":function_view(original,names),"baseline":function_view(base,names) if base else None,"obfuscated":function_view(transformed,names) if transformed else None}
    obf_sources=list((folder/"build/obfuscated").glob("*.c"))
    if obf_sources:views["tigress"]=function_view(obf_sources[0].read_text(encoding="utf-8"),names)
    for view in views.values():
        if view:view["nonempty_lines"]=sum(bool(l.strip()) for l in view["code"].splitlines())
    difference=None;diff=None
    if views["baseline"] and views["obfuscated"]:
        a=views["baseline"]["code"];b=views["obfuscated"]["code"]
        norm=lambda text:re.sub(r"\s+"," ",text).strip()
        difference=round(100*(1-difflib.SequenceMatcher(None,norm(a),norm(b),autojunk=False).ratio()),1)
        diff="\n".join(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile="Ghidra baseline",tofile="Ghidra "+technique,lineterm=""))[:90000]
    quality=selected.get("decompilation_quality",{})
    return {"program":program,"technique":technique,"seed":seed,"views":views,"textual_difference_pct":difference,"diff":diff,
       "quality":quality,"built":selected.get("built"),"verified":selected.get("verified"),
       "notes":["Original C and Ghidra output differ even without obfuscation because of compilation and decompilation. Compare the Ghidra baseline with the Ghidra variant to assess the transformation.",
                "This percentage measures textual difference after whitespace normalization; it does not measure logical difference, security, or decompiler correctness.",
                "Input-based validation checks binary behavior, not semantic equivalence of pseudo-C. Shorter output can indicate incomplete decompilation.",
                "This comparison is explanatory UI only; original source is not appended to the LLM prompt."]}

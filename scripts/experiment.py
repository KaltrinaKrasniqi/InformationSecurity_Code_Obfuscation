"""One shared, checkpointed protocol for UI and CLI. No source/ground truth enters prompts."""
import contextlib, csv, hashlib, io, json, os, platform, random, re, shutil, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
import config as C
from build import build
from verify import verify_details
from decompile import decompile
from measure import measure_details
from classical import classical_attack
from potency import potency
from quality import assess, wilson

PROTOCOL_VERSION="2.0"
MODES=("pseudoc","assisted")

def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    tmp.replace(path)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def command_version(cmd):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
        return (p.stdout+p.stderr).strip()[:2000]
    except Exception as e:return type(e).__name__

def parse_answer(text,truth):
    match=re.fullmatch(r"SECRET:\s*([^\r\n]+)\s*",text.strip())
    if not match:return {"valid":False,"found":False,"answer":text,"status":"invalid_format"}
    value=match.group(1).strip()
    return {"valid":True,"found":value==truth,"answer":value,"status":"unknown" if value=="UNKNOWN" else "answered"}

def init_session(directory, programs, techniques, seeds, n, modes, no_attack=False):
    if n<1 or not seeds or len(set(seeds))!=len(seeds):raise ValueError("Positive repetitions and distinct seeds required")
    if any(p not in C.PROGRAMS for p in programs):raise ValueError("Unknown program")
    if any(t not in C.TECHNIQUES for t in techniques):raise ValueError("Unknown technique")
    if any(m not in MODES for m in modes):raise ValueError("Unknown attack mode")
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    metadata={"protocol_version":PROTOCOL_VERSION,"implementation_sha256":{p.name:sha(p) for p in (C.ROOT/"scripts").iterdir() if p.suffix in (".py",".java",".txt")},"tigress_environment":C.TIGRESS_ENVIRONMENT,"config_set":str(C.CONFIGS_DIR),"started_utc":datetime.now(timezone.utc).isoformat(),
       "platform":platform.platform(),"python":platform.python_version(),"compiler":command_version([C.CC,"--version"]),
       "tigress":command_version([C.TIGRESS_BIN,"--Version"]),"compiler_flags":C.CFLAGS,
       "ghidra_home":C.GHIDRA_HOME,"ghidra_properties":(Path(C.GHIDRA_HOME)/"Ghidra/application.properties").read_text() if C.GHIDRA_HOME and (Path(C.GHIDRA_HOME)/"Ghidra/application.properties").exists() else None,
       "java":command_version([os.environ.get("GHIDRA_JAVA_HOME","")+"/bin/java","-version"]),
       "programs":programs,"techniques":techniques,"seeds":seeds,"repetitions_per_build":n,"modes":modes,
       "no_attack":no_attack,"model_requested":os.environ.get("OPENAI_MODEL","gpt-4o-mini"),"temperature":0,
       "benchmark":"100000 mixed valid/invalid calls per process; 1000 warmup; 7 independent processes; median and MAD; O0",
       "threat_model":"benign targets; static secret recovery from decompiled compiled binaries; no original source or evaluator ground truth in prompts",
       "arms":{"pseudoc":"Ghidra pseudo-C only","assisted":"Same pseudo-C plus complete objdump disassembly and read-only .rodata bytes"},
       "limitations":["Six small programs; password/license controls are deliberately similar", "Three transformation seeds are a small sample; no universal-security claim", "Repeated requests at temperature 0 are not independent human attackers", "Quality flags are heuristics, not proof of complete decompilation", "strings tests literal visibility only, particularly weak for numeric secrets", "O0 results do not generalize to optimized production builds"]}
    atomic_json(directory/"protocol.json",metadata)
    return directory

def run_cell(directory,program,technique,seed,n,modes,backend,log=print,build_only=False):
    cell=Path(directory)/"cells"/f"{program}__{technique}__seed{seed}"
    checkpoint=cell/"rows.json"
    if checkpoint.exists():
        saved=json.loads(checkpoint.read_text(encoding="utf-8"))
        if any(r.get("source_sha256") != sha(C.source_path(program)) for r in saved):
            raise ValueError("Source changed; start a new experiment instead of mixing versions")
        if technique!="baseline" and any(r.get("recipe_sha256")!=sha(C.CONFIGS_DIR/f"{technique}.tigress") for r in saved):raise ValueError("Recipe changed")
        return saved
    cell.mkdir(parents=True,exist_ok=True)
    old=(C.BUILD_DIR,C.DECOMP_DIR,C.RAW_DIR)
    C.BUILD_DIR=cell/"build";C.DECOMP_DIR=cell/"decompiled";C.RAW_DIR=cell/"raw"
    common={"program":program,"technique":technique,"seed":seed,"built":False,"verified":False,"decompiled":False,"error":None,"artifact_dir":str(cell)}
    rows=[]
    try:
        shutil.copy2(C.source_path(program),cell/"source.c")
        common["source_sha256"]=sha(cell/"source.c")
        if technique!="baseline":
            shutil.copy2(C.CONFIGS_DIR/f"{technique}.tigress",cell/"recipe.tigress")
            common["recipe_sha256"]=sha(cell/"recipe.tigress")
        log(f"{program} / {technique} / seed {seed}: build + verification")
        with (cell/"python.log").open("w",encoding="utf-8") as output, contextlib.redirect_stdout(output):
            build(program,technique,seed=seed);common["built"]=True
            verification=verify_details(program,technique);common["verification"]=verification
            if not verification["passed"]:raise RuntimeError("behavior_verification_failed")
            common["verified"]=True
            common.update(measure_details(program,technique))
            common["classical"]=classical_attack(program,technique)
            common["classical_found"]=common["classical"].get("found_direct")
            common.update(potency(program,technique))
            common["binary_sha256"]=sha(C.binary_path(program,technique))
            if build_only:
                rows=[dict(common,mode="not_run",runs=[],success_rate=None,valid_runs=0,invalid_runs=0)]
                atomic_json(checkpoint,rows);return rows
            decomp=decompile(program,technique);common["decompiled"]=True
        code=decomp.read_text(encoding="utf-8")
        common["decompilation_quality"]=assess(code,C.PROGRAMS[program]["func"])
        common["pseudo_c_sha256"]=sha(decomp)
        binary=C.binary_path(program,technique)
        asm=subprocess.run(["objdump","-d",str(binary)],capture_output=True,text=True,timeout=60,check=True).stdout
        data=subprocess.run(["objdump","-s","-j",".rodata",str(binary)],capture_output=True,text=True,timeout=60)
        if data.returncode not in (0,1):raise RuntimeError("rodata_dump_failed")
        (cell/"disassembly.txt").write_text(asm,encoding="utf-8")
        (cell/"rodata.txt").write_text(data.stdout,encoding="utf-8")
        truth=json.loads(C.SECRETS_FILE.read_text(encoding="utf-8"))[program]["secret"]
        for mode in modes:
            row=dict(common,mode=mode,runs=[])
            material=code if mode=="pseudoc" else code+"\n=== DISASSEMBLY ===\n"+asm+"\n=== READ-ONLY DATA ===\n"+data.stdout
            prompt=(C.ROOT/"scripts/prompt.txt").read_text(encoding="utf-8").replace("{CODE}",material)
            arm=cell/mode;arm.mkdir(exist_ok=True)
            (arm/"prompt.txt").write_text(prompt,encoding="utf-8")
            row["prompt_sha256"]=sha(arm/"prompt.txt")
            for repetition in range(1,n+1):
                started=time.perf_counter()
                if len(prompt)>240000:
                    result={"valid":False,"found":False,"answer":"","status":"input_budget_exceeded"}
                else:
                    try:
                        answer=backend.ask(prompt)
                        result=parse_answer(answer,truth)
                        result["received"]=True
                        result["response_metadata"]=getattr(backend,"last_response",{})
                        (arm/f"response_{repetition}.txt").write_text(answer,encoding="utf-8")
                    except Exception as e:
                        result={"valid":False,"found":False,"answer":"","status":"api_error","error_type":type(e).__name__,"http_status":getattr(e,"status_code",None)}
                result.update(i=repetition,elapsed_s=time.perf_counter()-started)
                row["runs"].append(result)
                atomic_json(arm/f"run_{repetition}.json",result)
                log(f"  {mode} {repetition}/{n}: {result['status']} recovered={result['found']}")
            valid=sum(x.get("received",False) for x in row["runs"]);hits=sum(x["found"] for x in row["runs"])
            row.update(valid_runs=valid,invalid_runs=n-valid,format_errors=sum(x["status"]=="invalid_format" for x in row["runs"]),llm_success=hits,success_rate=hits/valid if valid else None,
                       success_ci95=wilson(hits,valid),backend=backend.name())
            if n-valid:row["error"]=f"{n-valid} invalid/missing responses; see per-run status"
            rows.append(row)
    except Exception as e:
        common["error"]=f"{type(e).__name__}: {str(e)[:1000]}"
        log("CELL ERROR: "+common["error"])
        rows=[dict(common,mode=m,runs=[],success_rate=None,valid_runs=0,invalid_runs=0) for m in (["not_run"] if build_only else modes)]
    finally:
        C.BUILD_DIR,C.DECOMP_DIR,C.RAW_DIR=old
    atomic_json(checkpoint,rows)
    return rows

def summarize(rows):
    groups={}
    for row in rows:groups.setdefault((row["program"],row["technique"],row["mode"]),[]).append(row)
    summary=[]
    import statistics
    for (program,technique,mode),group in groups.items():
        valid=sum(r.get("valid_runs",0) for r in group);hits=sum(r.get("llm_success",0) for r in group)
        checker=[r["checker_ns"] for r in group if r.get("checker_ns") is not None]
        size=[r["size_bytes"] for r in group if r.get("size_bytes") is not None]
        summary.append({"program":program,"technique":technique,"mode":mode,"builds":len(group),"verified_builds":sum(r.get("verified",False) for r in group),
          "valid_runs":valid,"invalid_runs":sum(r.get("invalid_runs",0) for r in group),"format_errors":sum(r.get("format_errors",0) for r in group),"hits":hits,
          "success_rate":hits/valid if valid else None,"ci95":wilson(hits,valid),
          "flagged_builds":sum(r.get("decompilation_quality",{}).get("status")=="flagged" for r in group),
          "strings_found_builds":sum(r.get("classical_found") is True for r in group),
          "checker_ns_median":statistics.median(checker) if checker else None,"size_bytes_median":statistics.median(size) if size else None})
    baselines={(r["program"],r["mode"]):r for r in summary if r["technique"]=="baseline"}
    for r in summary:
        base=baselines.get((r["program"],r["mode"]))
        r["size_overhead_pct"]=((r["size_bytes_median"]/base["size_bytes_median"]-1)*100) if base and base.get("size_bytes_median") and r.get("size_bytes_median") else None
        r["checker_ratio"]=r["checker_ns_median"]/base["checker_ns_median"] if base and base.get("checker_ns_median") and r.get("checker_ns_median") is not None else None
    return summary

def export(directory,rows):
    directory=Path(directory);atomic_json(directory/"results.json",rows)
    summary=summarize(rows);atomic_json(directory/"summary.json",summary)
    if summary:
        with (directory/"summary.csv").open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=summary[0].keys());writer.writeheader();writer.writerows(summary)
    report=["# Experiment results", "", "Descriptive pilot results. Confidence intervals assume independent Bernoulli trials; repeated calls/builds may be correlated. Three seeds are not a broad sample.", "", "| Program | Technique | Input arm | Hits/valid | Invalid | Quality flagged | Size overhead | Checker ratio |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for s in summary:
        report.append(f"| {s['program']} | {s['technique']} | {s['mode']} | {s['hits']}/{s['valid_runs']} | {s['invalid_runs']} | {s['flagged_builds']}/{s['builds']} | {s['size_overhead_pct'] if s['size_overhead_pct'] is not None else 'N/A'} | {s['checker_ratio'] if s['checker_ratio'] is not None else 'N/A'} |")
    report += ["", "Read protocol.json for threat model, versions, fixed seeds and limitations. Pseudoc measures the decompiler+LLM chain; assisted adds assembly and read-only bytes to every build, not just failures. No security claim can be made from UNKNOWN alone. Negative overhead may be measurement noise."]
    (directory/"REPORT.md").write_text("\n".join(report),encoding="utf-8")
    return summary

def run_protocol(directory,programs,techniques,seeds,n,modes,log=print,on_result=None,build_only=False,resume=False):
    directory=Path(directory).resolve()
    if resume:
        saved=json.loads((directory/"protocol.json").read_text(encoding="utf-8"))
        current_hashes={p.name:sha(p) for p in (C.ROOT/"scripts").iterdir() if p.suffix in (".py",".java",".txt")}
        if saved.get("implementation_sha256")!=current_hashes:raise ValueError("Implementation changed; start a new experiment")
        if saved.get("model_requested")!=os.environ.get("OPENAI_MODEL","gpt-4o-mini"):raise ValueError("Model changed")
        for key,value in {"programs":programs,"techniques":techniques,"seeds":seeds,"repetitions_per_build":n,"modes":modes,"no_attack":build_only}.items():
            if saved[key]!=value:raise ValueError("Resume protocol mismatch: "+key)
    else:init_session(directory,programs,techniques,seeds,n,modes,build_only)
    backend=None
    if not build_only:
        from llm_backend import get_backend
        backend=get_backend()
    schedule=[(p,t,s) for p in programs for t in techniques for s in seeds]
    random.Random(20261031).shuffle(schedule)
    atomic_json(directory/"schedule.json",schedule)
    rows=[]
    for index,(p,t,s) in enumerate(schedule,1):
        log(f"CELL {index}/{len(schedule)}")
        current=run_cell(directory,p,t,s,n,modes,backend,log,build_only)
        rows.extend(current);summary=export(directory,rows)
        if on_result:on_result(rows,summary,index,len(schedule))
    atomic_json(directory/"integrity.json",{str(p.relative_to(directory)):sha(p) for p in directory.rglob("*") if p.is_file() and p.name!="integrity.json"})
    return rows

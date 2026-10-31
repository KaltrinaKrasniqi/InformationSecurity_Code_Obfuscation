"""Local UI for the SAME research protocol used by the CLI. Single worker, persistent history."""
import csv, io, json, os, re, shutil, sys, threading, uuid, zipfile
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
import config as C
from experiment import atomic_json, run_protocol, summarize
app=Flask(__name__,static_folder=str(ROOT/"ui/frontend"),static_url_path="")
app.config["MAX_CONTENT_LENGTH"]=8*1024*1024
UPLOADS=ROOT/"ui/uploads";UPLOADS.mkdir(parents=True,exist_ok=True)
JOBS_DIR=ROOT/"results/jobs";JOBS_DIR.mkdir(parents=True,exist_ok=True)
JOBS={};LOCK=threading.Lock()
for path in JOBS_DIR.glob("*.json"):
    try:
        job=json.loads(path.read_text(encoding="utf-8"))
        if job.get("status") in ("running","pending"):
            job.update(status="interrupted",error="Server restarted; evidence retained")
        JOBS[path.stem]=job
    except (ValueError,OSError):pass

def save(job_id):atomic_json(JOBS_DIR/f"{job_id}.json",JOBS[job_id])
@app.get("/")
def index():return send_from_directory(app.static_folder,"index.html")
@app.get("/api/techniques")
def techniques():return jsonify(techniques=C.TECHNIQUES)
@app.get("/api/examples")
def examples():return jsonify(examples=[dict(id=p,**m) for p,m in C.EXAMPLES.items()])
@app.get("/api/examples/<program>/source")
def example_source(program):
    if program not in C.EXAMPLES:return jsonify(error="Unknown example"),404
    return Response(C.source_path(program).read_text(encoding="utf-8"),mimetype="text/plain")
@app.get("/api/jobs")
def history():
    return jsonify(jobs=[{"id":k,"status":j.get("status"),"label":j.get("label",j.get("program",k)),"progress":j.get("progress")} for k,j in reversed(list(JOBS.items()))])
@app.get("/api/jobs/<job_id>")
def get_job(job_id):
    if job_id not in JOBS:return jsonify(error="Unknown job"),404
    from presentation import explain
    return jsonify(dict(JOBS[job_id],explanation=explain(JOBS[job_id])))
@app.post("/api/upload")
def upload():
    files=request.files.getlist("file")
    if not files or not files[0].filename:return jsonify(error="Choose a C file or ZIP"),400
    project_id=uuid.uuid4().hex[:12];dest=UPLOADS/project_id;dest.mkdir()
    try:
        for f in files:
            relative=f.filename.replace("\\","/")
            if Path(relative).is_absolute() or ".." in Path(relative).parts or ":" in relative:raise ValueError("Invalid path")
            path=dest/relative;path.parent.mkdir(parents=True,exist_ok=True);f.save(path)
        for path in list(dest.rglob("*.zip")):
            with zipfile.ZipFile(path) as z:
                if sum(m.file_size for m in z.infolist())>32*1024*1024:raise ValueError("Archive too large")
                for m in z.infolist():
                    if not (path.parent/m.filename).resolve().is_relative_to(dest.resolve()):raise ValueError("Unsafe ZIP path")
                z.extractall(path.parent)
            path.unlink()
        sources=[str(p.relative_to(dest)) for p in dest.rglob("*.c")]
        if not sources:raise ValueError("No C source found")
        return jsonify(project_id=project_id,c_files=sources)
    except Exception as e:return jsonify(error=str(e)),400

def register_upload(data,job_id):
    project_id=data.get("project_id","")
    if not re.fullmatch(r"[a-f0-9]{8,12}",project_id):raise ValueError("Invalid project id")
    folder=UPLOADS/project_id
    choices=[p for p in folder.rglob("*.c") if re.search(r"\bint\s+main\s*\(",p.read_text(errors="replace"))]
    if len(choices)!=1:raise ValueError("Upload needs one main C translation unit")
    main=choices[0];text=main.read_text(errors="replace")
    func=data.get("function","").strip()
    if not re.fullmatch(r"[A-Za-z_]\w*",func):raise ValueError("Enter the checker function name, e.g. check_password")
    if not re.search(r"\b"+re.escape(func)+r"\s*\(",text):raise ValueError("Checker not found")
    secret=data.get("secret_value","")
    if not secret or "\n" in secret or "\r" in secret:raise ValueError("Enter one-line evaluator ground truth")
    prog="ui_"+job_id;dst=C.TARGETS_DIR/prog;shutil.copytree(folder,dst)
    info={"func":func,"src":str(main.relative_to(folder))};C.PROGRAMS[prog]=info
    registry=ROOT/"targets/programs.json";entries=json.loads(registry.read_text()) if registry.exists() else {}
    entries[prog]=info;atomic_json(registry,entries)
    registry=C.SECRETS_FILE;entries=json.loads(registry.read_text(encoding="utf-8"))
    entries[prog]={"secret":secret,"type":data.get("secret_type","password"),"expected_output":data.get("expected_output") or "SUCCESS"}
    atomic_json(registry,entries)
    return prog

@app.post("/api/run")
def start():
    if not LOCK.acquire(blocking=False):return jsonify(error="An experiment is already running"),409
    try:
        data=request.get_json(force=True)
        programs=list(dict.fromkeys(data.get("programs",[])))
        if not programs:programs=[register_upload(data,"custom_"+uuid.uuid4().hex[:12])]
        elif any(p not in C.EXAMPLES for p in programs):raise ValueError("Unknown built-in example")
        techniques=list(dict.fromkeys(["baseline"]+data.get("techniques",[])))
        if any(t not in C.TECHNIQUES for t in techniques):raise ValueError("Unknown technique")
        seeds=[int(s) for s in data.get("seeds",[11,29,47])]
        modes=data.get("modes",["pseudoc","assisted"]);n=int(data.get("n_runs",1))
        if not 1<=n<=10 or not 1<=len(seeds)<=5 or len(set(seeds))!=len(seeds) or any(s<0 or s>2147483647 for s in seeds):raise ValueError("Use 1-5 distinct seeds and 1-10 repetitions")
        if not modes or any(m not in ("pseudoc","assisted") for m in modes):raise ValueError("Invalid input mode")
        job_id=uuid.uuid4().hex[:12]
        JOBS[job_id]={"status":"pending","logs":[],"results":[],"summary":[],"label":", ".join(programs),"progress":{"done":0,"total":len(programs)*len(techniques)*len(seeds)},
                      "request":{"programs":programs,"techniques":techniques,"seeds":seeds,"n_runs":n,"modes":modes}}
        save(job_id)
        threading.Thread(target=worker,args=(job_id,programs,techniques,seeds,n,modes),daemon=True).start()
        return jsonify(job_id=job_id)
    except Exception as e:
        LOCK.release();return jsonify(error=str(e)),400

def worker(job_id,programs,techniques,seeds,n,modes):
    job=JOBS[job_id];job["status"]="running"
    directory=ROOT/"results/experiments"/job_id;job["experiment_dir"]=str(directory)
    def log(message):
        job["logs"].append(str(message));save(job_id)
    def update(rows,summary,done,total):
        job.update(results=rows,summary=summary,progress={"done":done,"total":total});save(job_id)
    try:
        run_protocol(directory,programs,techniques,seeds,n,modes,log=log,on_result=update)
        job["status"]="done_with_errors" if any(r.get("error") for r in job["results"]) else "done"
        log("Finished. All evidence retained. UNKNOWN is not proof of security; inspect quality and assisted arm.")
    except Exception as e:job.update(status="error",error=f"{type(e).__name__}: {e}")
    finally:save(job_id);LOCK.release()

@app.get("/api/jobs/<job_id>/csv")
def csv_export(job_id):
    job=JOBS.get(job_id)
    if job is None:return jsonify(error="Unknown job"),404
    if "summary" not in job:
        rows=[{k:r.get(k) for k in ("technique","built","decompiled","success_rate","classical_found","binary_size_kb","runtime_ms","error")} for r in job.get("results",[])]
    else:
        rows=job["summary"]
    buf=io.StringIO()
    if rows:
        w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return Response(buf.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment; filename=summary_{job_id}.csv"})
@app.get("/api/jobs/<job_id>/report")
def report(job_id):
    job=JOBS.get(job_id,{})
    p=Path(job.get("experiment_dir",str(ROOT/"missing")))/"REPORT.md"
    if not p.is_file():return jsonify(error="Report not yet available"),404
    return Response(p.read_text(encoding="utf-8"),mimetype="text/plain")
@app.get("/api/jobs/<job_id>/code/<int:index>")
def code(job_id,index):
    job=JOBS.get(job_id)
    if not job or not 0<=index<len(job["results"]):return jsonify(error="Unknown row"),404
    row=job["results"][index];folder=Path(row["artifact_dir"])/"decompiled"
    candidates=list(folder.rglob("*.c"))
    if not candidates:return jsonify(error="No pseudo-C"),404
    return Response(candidates[0].read_text(encoding="utf-8"),mimetype="text/plain")
@app.get("/api/jobs/<job_id>/comparison")
def comparison(job_id):
    job=JOBS.get(job_id)
    if not job:return jsonify(error="Unknown job"),404
    from presentation import compare
    try:
        return jsonify(compare(job,request.args.get("program"),request.args.get("technique"),int(request.args.get("seed","11")),C.PROGRAMS))
    except (ValueError,KeyError,OSError) as e:return jsonify(error=str(e)),400

@app.post("/api/jobs/<job_id>/plots")
def plots(job_id):
    job=JOBS.get(job_id)
    if not job:return jsonify(error="Unknown job"),404
    from plot_results import plot_summary
    try:
        folder=ROOT/"analysis/figures"/job_id
        plot_summary(job.get("summary",[]),folder)
        return jsonify(figures=[f"/figures/{job_id}/{p.name}" for p in sorted(folder.glob("*.png"))])
    except Exception as e:return jsonify(error=f"{type(e).__name__}: {e}"),400
@app.get("/figures/<job_id>/<name>")
def figure(job_id,name):return send_from_directory(ROOT/"analysis/figures"/job_id,name)
if __name__=="__main__":app.run(host="127.0.0.1",port=8002,debug=False)

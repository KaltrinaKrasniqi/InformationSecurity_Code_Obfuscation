"""Separate end-to-end wall time from in-process checker latency."""
import argparse, json, re, statistics, subprocess, time
import config as C

def measure_details(program, technique, runs=7, iterations=100000):
    if runs < 3 or iterations < 1: raise ValueError("At least 3 rounds and positive iterations required")
    binary = C.binary_path(program, technique)
    secret = json.loads(C.SECRETS_FILE.read_text(encoding="utf-8"))[program]["secret"]
    wall=[]
    for _ in range(3):
        start=time.perf_counter_ns()
        p=subprocess.run([str(binary)],input=secret+"\n",capture_output=True,text=True,timeout=10,check=True)
        wall.append((time.perf_counter_ns()-start)/1e6)
        if "SUCCESS" not in p.stdout: raise RuntimeError("Correct input rejected during measurement")
    samples=[]
    if program in C.EXAMPLES:
        for _ in range(runs):
            p=subprocess.run([str(binary),"--benchmark",str(iterations)],input=secret+"\n",capture_output=True,text=True,timeout=60,check=True)
            match=re.search(r"^BENCH_NS ([0-9.]+)$",p.stdout,re.M)
            checksum=re.search(r"^CHECKSUM ([0-9]+)$",p.stdout,re.M)
            if not match or not checksum: raise RuntimeError("Benchmark protocol missing")
            if int(checksum.group(1)) != (1000//2 + iterations//2): raise RuntimeError("Benchmark checksum mismatch")
            samples.append(float(match.group(1)))
    median=statistics.median(samples) if samples else None
    return {"size_bytes":binary.stat().st_size,"runtime_ms":statistics.median(wall),
            "checker_ns":median,"checker_samples_ns":samples,
            "checker_mad_ns":statistics.median([abs(x-median) for x in samples]) if samples else None,
            "benchmark_iterations":iterations if samples else None,
            "benchmark_rounds":len(samples),"benchmark_clock":"CLOCK_MONOTONIC (Linux)",
            "runtime_definition":"runtime_ms includes startup+I/O; checker_ns excludes them"}

def measure(program, technique, runs=5):
    data=measure_details(program,technique,runs=max(3,runs))
    return data["size_bytes"], data["runtime_ms"]/1000

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--program",required=True);ap.add_argument("--technique",required=True)
    a=ap.parse_args();print(json.dumps(measure_details(a.program,a.technique),indent=2))

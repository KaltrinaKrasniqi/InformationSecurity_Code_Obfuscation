"""Verify positive, boundary and deterministic negative inputs. Never infer security from a broken binary."""
import argparse, json, random, string, subprocess
import config as C

def verification_inputs(program):
    secret=json.loads(C.SECRETS_FILE.read_text(encoding="utf-8"))[program]["secret"]
    wrong=[]
    if secret:
        for i,c in enumerate(secret):
            wrong.append(secret[:i]+("X" if c!="X" else "Y")+secret[i+1:])
    wrong += ["",secret[:-1],secret+"_WRONG","WRONG", "A"*120]
    if secret.isdigit(): wrong += [str(int(secret)+1), str(int(secret)-1), "-1", "0"]
    rng=random.Random(2026)
    wrong += [''.join(rng.choice(string.ascii_letters+string.digits) for _ in range(rng.randint(1,25))) for _ in range(12)]
    return secret, list(dict.fromkeys(x for x in wrong if x!=secret))

def verify_details(program,technique):
    binary=C.binary_path(program,technique);secret,negative=verification_inputs(program)
    expected=json.loads(C.SECRETS_FILE.read_text(encoding="utf-8"))[program].get("expected_output","SUCCESS")
    def accepts(value):
        p=subprocess.run([str(binary)],input=value+"\n",capture_output=True,text=True,timeout=10)
        return p.returncode==0 and expected in p.stdout
    positive_ok=accepts(secret); failures=[x for x in negative if accepts(x)]
    data={"passed":positive_ok and not failures,"positive_ok":positive_ok,"negative_count":len(negative),"false_acceptances":failures}
    print(f"[verify] {program}/{technique}: passed={data['passed']} negative_cases={len(negative)}")
    return data

def verify(program,technique): return verify_details(program,technique)["passed"]
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--program",required=True);ap.add_argument("--technique",required=True)
    a=ap.parse_args();raise SystemExit(0 if verify(a.program,a.technique) else 1)

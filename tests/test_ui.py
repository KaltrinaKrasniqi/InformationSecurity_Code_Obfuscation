import io,json,runpy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
class UITests(unittest.TestCase):
    def setUp(self):
        self.module=runpy.run_path(str(ROOT/"ui/backend/app.py"));self.app=self.module["app"]
        self.g=self.module["save"].__globals__;self.client=self.app.test_client()
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/"tests");self.g["JOBS_DIR"]=Path(self.tmp.name)
    def tearDown(self):
        if self.g["LOCK"].locked():self.g["LOCK"].release()
        self.tmp.cleanup()
    def test_examples_and_source_available(self):
        r=self.client.get("/api/examples");self.assertEqual(len(r.json["examples"]),6)
        self.assertEqual(self.client.get("/api/examples/p6_staged/source").status_code,200)
        self.assertEqual(self.client.get("/api/examples/not_real/source").status_code,404)
    def test_baseline_inserted_and_request_persisted(self):
        with patch("threading.Thread"):
            r=self.client.post("/api/run",json={"programs":["p1_password"],"techniques":["flatten"],"seeds":[11],"n_runs":1,"modes":["pseudoc"]})
        self.assertEqual(r.status_code,200)
        data=json.loads((Path(self.tmp.name)/(r.json["job_id"]+".json")).read_text())
        self.assertEqual(data["request"]["techniques"],["baseline","flatten"])
    def test_invalid_request_does_not_leave_worker_lock_held(self):
        r=self.client.post("/api/run",json={"programs":["p1_password"],"techniques":["unknown"]})
        self.assertEqual(r.status_code,400);self.assertFalse(self.g["LOCK"].locked())
    def test_same_seed_twice_rejected(self):
        r=self.client.post("/api/run",json={"programs":["p1_password"],"seeds":[11,11]})
        self.assertEqual(r.status_code,400)
    def test_second_concurrent_run_rejected(self):
        self.g["LOCK"].acquire()
        self.assertEqual(self.client.post("/api/run",json={}).status_code,409)
if __name__=="__main__":unittest.main()

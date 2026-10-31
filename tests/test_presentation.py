import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from presentation import explain,function_view
class PresentationTests(unittest.TestCase):
    def test_input_budget_is_not_api_failure_or_security(self):
        job={"status":"done_with_errors","progress":{"done":1,"total":1},"results":[{"program":"p","technique":"flatten","seed":11,"built":True,"verified":True,"decompiled":True,"runs":[{"status":"input_budget_exceeded"}]}]}
        result=explain(job);self.assertTrue(result["pipeline_ok"])
        self.assertIn("local size limit",' '.join(result["notes"]))
        self.assertEqual(result["run_statuses"].get("api_error",0),0)
    def test_checker_view_excludes_main(self):
        view=function_view("int check_x(const char *x){return 1;}\nint main(){return 0;}",["check_x"])
        self.assertIn("check_x",view["code"]);self.assertNotIn("main",view["code"])
    def test_interrupted_job_not_marked_success(self):
        result=explain({"status":"interrupted","progress":{"done":0,"total":2},"results":[]})
        self.assertFalse(result["pipeline_ok"])
if __name__=="__main__":unittest.main()

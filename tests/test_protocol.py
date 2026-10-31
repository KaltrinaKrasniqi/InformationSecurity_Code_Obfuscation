import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from experiment import parse_answer, summarize
from quality import assess,wilson
class ProtocolTests(unittest.TestCase):
    def test_decompiler_failure_is_visible(self):
        q=assess("void check_x(){ /* Could not recover jumptable */ }","check_x")
        self.assertEqual(q["status"],"flagged")
    def test_unrelated_function_warning_not_attributed_to_checker(self):
        q=assess("/* FUNCTION: startup */ /* could not recover jumptable */\n/* FUNCTION: check_x */ int check_x(){return 1;}","check_x")
        self.assertEqual(q["status"],"no_warning_detected")
    def test_missing_function_is_flagged(self):
        self.assertIn("check_x",assess("int main(){}","check_x")["missing_functions"])
    def test_no_warning_is_not_a_completeness_claim(self):
        self.assertEqual(assess("int check_x(){return 1;}","check_x")["status"],"no_warning_detected")
    def test_zero_hits_does_not_imply_zero_uncertainty(self):
        low,high=wilson(0,3);self.assertEqual(low,0);self.assertGreater(high,0.5)
    def test_no_valid_trials_is_na(self):
        self.assertEqual(wilson(0,0),[None,None])
    def test_exact_match_no_case_folding(self):
        self.assertFalse(parse_answer("SECRET: abc","Abc")["found"])
    def test_unknown_is_valid_api_error_is_not(self):
        self.assertTrue(parse_answer("SECRET: UNKNOWN","Abc")["valid"])
        self.assertFalse(parse_answer("ERROR: timeout","Abc")["valid"])
    def test_arms_and_programs_not_pooled(self):
        rows=[]
        for prog,mode,hits in [("a","pseudoc",0),("a","assisted",1),("b","pseudoc",1)]:
            rows.append(dict(program=prog,technique="baseline",mode=mode,valid_runs=1,llm_success=hits,verified=True,checker_ns=10,size_bytes=100))
        summary=summarize(rows);self.assertEqual(len(summary),3)
        self.assertEqual(summary[0]["success_rate"],0)
        self.assertEqual(summary[1]["success_rate"],1)
if __name__=="__main__":unittest.main()

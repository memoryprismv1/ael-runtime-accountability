import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from ael_environment import REPOSITORY_ROOT,prepare_environment,resolve_environment_path,validate_dependencies
from compare_environments import pair
class ExperimentEnvironmentTests(unittest.TestCase):
    def test_baseline_manifest_loads_without_dependencies(self):
        root,manifest,deps=prepare_environment("."); self.assertEqual(root,REPOSITORY_ROOT); self.assertEqual(manifest["experiment_id"],"baseline-v2.8.1"); self.assertEqual(deps,{})
    def test_ct_manifest_resolves_exact_skill_pin(self):
        root,manifest,deps=prepare_environment("ct"); req=manifest["requirements"]["critical-thinking"]
        self.assertEqual(req["version"],"git:"+req["source_commit"]); self.assertTrue(deps["critical-thinking"]["available"]); self.assertEqual(deps["critical-thinking"]["source_blob_sha"],req["source_blob_sha"])
    def test_required_dependency_integrity_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"skill.md").write_text("wrong content",encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"SHA-256 mismatch"): validate_dependencies(root,{"requirements":{"demo":{"version":"1.0","path":"skill.md","required":True,"sha256":"0"*64}}})
    def test_dependency_path_cannot_escape_environment(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"escapes its environment"): validate_dependencies(Path(d),{"requirements":{"demo":{"version":"1.0","path":"../out","required":True,"sha256":"0"*64}}})
    def test_path_context_refuses_to_escape_repository(self):
        with self.assertRaisesRegex(ValueError,"inside the repository"): resolve_environment_path("../")
    def test_comparison_detects_regression(self):
        r=pair("baseline","ct",{"baseline":{"Class.test_same":"ok","Class.test_old":"ok"},"ct":{"Class.test_same":"FAIL","Class.test_new":"ok"}})
        self.assertFalse(r["shared_tests_match"]); self.assertEqual(r["baseline_pass_to_experiment_failure"][0]["test"],"Class.test_same")
        self.assertEqual(r["first_only_tests"],["Class.test_old"]); self.assertEqual(r["second_only_tests"],["Class.test_new"])

    def test_launcher_uses_explicit_ct_path_and_reports_inherited_context(self):
        command=[sys.executable,str(REPOSITORY_ROOT/"run_ael.py"),"--path","ct","runtime","task","--help"]
        cp=subprocess.run(command,cwd=REPOSITORY_ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(cp.returncode,0,cp.stderr)
        self.assertIn("AEL experiment: ct-task-precommitment-v1",cp.stderr)
        self.assertIn(str(REPOSITORY_ROOT/"ct"),cp.stderr)
        self.assertIn("generate-case",cp.stdout)

    def test_launcher_inherits_ael_path_from_parent_environment(self):
        env=os.environ.copy()
        env["AEL_PATH"]=str(REPOSITORY_ROOT/"ct")
        command=[sys.executable,str(REPOSITORY_ROOT/"run_ael.py"),"runtime","task","--help"]
        cp=subprocess.run(command,cwd=REPOSITORY_ROOT,env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(cp.returncode,0,cp.stderr)
        self.assertIn("AEL experiment: ct-task-precommitment-v1",cp.stderr)
        self.assertIn("generate-case",cp.stdout)

if __name__=="__main__": unittest.main()

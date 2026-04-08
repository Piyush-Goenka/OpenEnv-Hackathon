from __future__ import annotations

import unittest

from server.ci_engine import CIEngine, CIEpisodeRuntime
from tasks import get_task


def _make_scenario(
    *,
    files: dict[str, str] | None = None,
    checks: dict | None = None,
    initial_ci_output: str = "FAILED",
) -> dict:
    """Build a minimal CI scenario dict for testing."""
    return {
        "scenario_id": "test_scenario",
        "task_id": "ci_easy",
        "title": "Test",
        "description": "Test scenario",
        "files": files or {"src/main.py": "print('hello')"},
        "relevant_files": list((files or {"src/main.py": ""}).keys()),
        "checks": checks
        or {
            "lint": {
                "failure_output": "FAILED: lint errors",
                "success_output": "All checks passed.",
                "required_tokens_any_of": [["print"]],
                "structural_validators": [],
            }
        },
        "initial_ci_output": initial_ci_output,
    }


def _make_runtime(scenario: dict | None = None) -> CIEpisodeRuntime:
    s = scenario or _make_scenario()
    return CIEpisodeRuntime(
        scenario=s,
        current_files=dict(s.get("files", {})),
        checks_status={name: False for name in s["checks"]},
        last_ci_output=s.get("initial_ci_output"),
    )


class CIEngineReadFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CIEngine()

    def test_read_existing_file(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "read_file", {"path": "src/main.py"}, 1)
        self.assertIn("print('hello')", result.tool_results or "")
        self.assertFalse(result.done)
        self.assertEqual(result.reward, 0.0)

    def test_read_missing_file(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "read_file", {"path": "nope.py"}, 1)
        self.assertIn("Unknown file", result.tool_results or "")
        self.assertIn("src/main.py", result.tool_results or "")

    def test_read_updates_last_tool_results(self) -> None:
        runtime = _make_runtime()
        self.engine.handle_action(runtime, "read_file", {"path": "src/main.py"}, 1)
        self.assertIn("print('hello')", runtime.last_tool_results or "")


class CIEngineRunCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CIEngine()

    def test_run_failing_check(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "run_check", {"check": "lint"}, 1)
        self.assertIn("FAILED", result.ci_output or "")
        self.assertFalse(result.done)

    def test_run_passing_check(self) -> None:
        runtime = _make_runtime()
        runtime.checks_status["lint"] = True
        result = self.engine.handle_action(runtime, "run_check", {"check": "lint"}, 1)
        self.assertIn("All checks passed", result.ci_output or "")
        self.assertTrue(result.done)

    def test_run_unknown_check(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "run_check", {"check": "nonexistent"}, 1)
        self.assertIn("Unknown check", result.ci_output or "")

    def test_done_when_all_checks_pass(self) -> None:
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [["x"]],
                    "structural_validators": [],
                },
                "test": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [["x"]],
                    "structural_validators": [],
                },
            }
        )
        runtime = _make_runtime(scenario)
        # Only one check passing — not done
        runtime.checks_status["lint"] = True
        runtime.checks_status["test"] = False
        result = self.engine.handle_action(runtime, "run_check", {"check": "lint"}, 1)
        self.assertFalse(result.done)

        # Both passing — done
        runtime.checks_status["test"] = True
        result = self.engine.handle_action(runtime, "run_check", {"check": "test"}, 2)
        self.assertTrue(result.done)


class CIEngineSubmitPatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CIEngine()

    def test_valid_patch_gets_reward(self) -> None:
        runtime = _make_runtime()
        patch = "print('hello')\n"
        result = self.engine.handle_action(
            runtime, "submit_patch", {"patch": patch, "file": "src/main.py"}, 1
        )
        self.assertGreater(result.reward, 0.0)
        self.assertIn("Patch evaluated", result.feedback)

    def test_empty_patch_no_reward(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime, "submit_patch", {"patch": "", "file": "src/main.py"}, 1
        )
        self.assertEqual(result.reward, 0.0)

    def test_patch_updates_current_files(self) -> None:
        runtime = _make_runtime()
        new_code = "x = 1\nprint(x)\n"
        self.engine.handle_action(
            runtime, "submit_patch", {"patch": new_code, "file": "src/main.py"}, 1
        )
        # The engine stores the patch string as-is (strip() applied)
        self.assertEqual(runtime.current_files["src/main.py"], new_code.strip())

    def test_repeated_patch_penalty(self) -> None:
        runtime = _make_runtime()
        patch = "print('hello')\n"
        r1 = self.engine.handle_action(
            runtime, "submit_patch", {"patch": patch, "file": "src/main.py"}, 1
        )
        r2 = self.engine.handle_action(
            runtime, "submit_patch", {"patch": patch, "file": "src/main.py"}, 2
        )
        # Second submission has repeated patch penalty
        self.assertIn("repeated identical patch penalty", r2.feedback)

    def test_all_green_marks_done(self) -> None:
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [["import os", "print"]],
                    "structural_validators": [],
                }
            }
        )
        runtime = _make_runtime(scenario)
        patch = "import os\nprint('hello')\n"
        result = self.engine.handle_action(
            runtime, "submit_patch", {"patch": patch, "file": "src/main.py"}, 1
        )
        self.assertTrue(result.done)
        self.assertIn("CI is healthy", result.feedback)

    def test_syntax_error_patch_fails_checks(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime, "submit_patch", {"patch": "def foo(:\n", "file": "src/main.py"}, 1
        )
        # Syntax error means parses=False, so no checks pass
        self.assertFalse(result.done)


class CIEngineUnsupportedActionTest(unittest.TestCase):
    def test_unknown_action_type(self) -> None:
        engine = CIEngine()
        runtime = _make_runtime()
        result = engine.handle_action(runtime, "deploy", {}, 1)
        self.assertIn("Unsupported", result.feedback)
        self.assertEqual(result.reward, 0.0)
        self.assertFalse(result.done)


class CIEngineValidateParsesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CIEngine()

    def test_valid_python(self) -> None:
        self.assertTrue(self.engine._validate_parses("x = 1\nprint(x)\n"))

    def test_invalid_python(self) -> None:
        self.assertFalse(self.engine._validate_parses("def foo(:\n"))

    def test_empty_string(self) -> None:
        self.assertFalse(self.engine._validate_parses(""))

    def test_whitespace_only(self) -> None:
        self.assertFalse(self.engine._validate_parses("   \n\n"))

    def test_diff_with_valid_added_lines(self) -> None:
        diff = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n+x = 1\n+print(x)\n"
        self.assertTrue(self.engine._validate_parses(diff))

    def test_diff_with_invalid_added_lines(self) -> None:
        diff = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n+def foo(:\n"
        self.assertFalse(self.engine._validate_parses(diff))


class CIEngineStructuralValidatorsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CIEngine()

    def test_ast_node_present_found(self) -> None:
        self.assertTrue(self.engine._check_ast_node_present("def foo(): pass", "FunctionDef"))

    def test_ast_node_present_not_found(self) -> None:
        self.assertFalse(self.engine._check_ast_node_present("x = 1", "FunctionDef"))

    def test_imports_before_functions_ok(self) -> None:
        code = "import os\n\ndef foo():\n    pass\n"
        self.assertTrue(self.engine._check_imports_before_functions(code))

    def test_imports_after_functions_fail(self) -> None:
        code = "def foo():\n    pass\n\nimport os\n"
        self.assertFalse(self.engine._check_imports_before_functions(code))

    def test_no_bare_except_ok(self) -> None:
        code = "try:\n    pass\nexcept ValueError:\n    pass\n"
        self.assertTrue(self.engine._check_no_bare_except(code))

    def test_bare_except_fail(self) -> None:
        code = "try:\n    pass\nexcept:\n    pass\n"
        self.assertFalse(self.engine._check_no_bare_except(code))

    def test_function_defined_found(self) -> None:
        self.assertTrue(self.engine._check_function_defined("def greet(): pass", "greet"))

    def test_function_defined_not_found(self) -> None:
        self.assertFalse(self.engine._check_function_defined("def greet(): pass", "hello"))

    def test_unknown_validator_passes(self) -> None:
        result = self.engine._run_structural_validator({"type": "unknown_type"}, "x = 1")
        self.assertTrue(result)


class CIEngineEvaluateChecksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CIEngine()

    def test_token_match_passes(self) -> None:
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [["import os"]],
                    "structural_validators": [],
                }
            }
        )
        result = self.engine._evaluate_checks(scenario, "import os\n")
        self.assertTrue(result["lint"])

    def test_token_no_match_fails(self) -> None:
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [["import sys"]],
                    "structural_validators": [],
                }
            }
        )
        result = self.engine._evaluate_checks(scenario, "import os\n")
        self.assertFalse(result["lint"])

    def test_syntax_error_fails_all(self) -> None:
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [["def"]],
                    "structural_validators": [],
                }
            }
        )
        result = self.engine._evaluate_checks(scenario, "def foo(:\n")
        self.assertFalse(result["lint"])

    def test_structural_validator_blocks(self) -> None:
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [["def foo", "import os"]],
                    "structural_validators": [{"type": "imports_before_functions"}],
                }
            }
        )
        # Tokens match but imports are after function
        bad_code = "def foo():\n    pass\n\nimport os\n"
        result = self.engine._evaluate_checks(scenario, bad_code)
        self.assertFalse(result["lint"])

        # Now fix the order
        good_code = "import os\n\ndef foo():\n    pass\n"
        result = self.engine._evaluate_checks(scenario, good_code)
        self.assertTrue(result["lint"])

    def test_any_of_groups(self) -> None:
        """At least one group of tokens must all be present."""
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "FAIL",
                    "success_output": "OK",
                    "required_tokens_any_of": [
                        ["import sys", "sys.exit"],
                        ["import os"],
                    ],
                    "structural_validators": [],
                }
            }
        )
        # Second group matches
        result = self.engine._evaluate_checks(scenario, "import os\n")
        self.assertTrue(result["lint"])


class CIEngineLoadScenarioTest(unittest.TestCase):
    def test_load_real_scenario(self) -> None:
        engine = CIEngine()
        task = get_task("ci_easy")
        runtime = engine.start_episode(task, seed=42)
        self.assertIn("scenario_id", runtime.scenario)
        self.assertTrue(len(runtime.current_files) > 0)
        self.assertTrue(len(runtime.checks_status) > 0)

    def test_deterministic_with_seed(self) -> None:
        engine = CIEngine()
        task = get_task("ci_easy")
        r1 = engine.start_episode(task, seed=99)
        r2 = engine.start_episode(task, seed=99)
        self.assertEqual(r1.scenario["scenario_id"], r2.scenario["scenario_id"])


class CIEngineFormatChecksTest(unittest.TestCase):
    def test_format_mixed_status(self) -> None:
        engine = CIEngine()
        scenario = _make_scenario(
            checks={
                "lint": {
                    "failure_output": "LINT FAIL",
                    "success_output": "LINT OK",
                    "required_tokens_any_of": [],
                    "structural_validators": [],
                },
                "test": {
                    "failure_output": "TEST FAIL",
                    "success_output": "TEST OK",
                    "required_tokens_any_of": [],
                    "structural_validators": [],
                },
            }
        )
        output = engine._format_all_checks(scenario, {"lint": True, "test": False})
        self.assertIn("[PASSED] lint", output)
        self.assertIn("[FAILED] test", output)
        self.assertIn("LINT OK", output)
        self.assertIn("TEST FAIL", output)

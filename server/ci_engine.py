from __future__ import annotations

import ast
import json
import random
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from server.reward import ci_step_reward, CIRewardConfig
from tasks.base import TaskDefinition


@dataclass
class CIEngineResult:
    reward: float
    feedback: str
    done: bool
    tool_results: Optional[str] = None
    ci_output: Optional[str] = None


@dataclass
class CIEpisodeRuntime:
    scenario: dict[str, Any]
    current_files: dict[str, str]
    patches_applied: list[str] = field(default_factory=list)
    checks_status: dict[str, bool] = field(default_factory=dict)
    last_tool_results: Optional[str] = None
    last_ci_output: Optional[str] = None


class CIEngine:
    def start_episode(self, task: TaskDefinition, seed: Optional[int] = None) -> CIEpisodeRuntime:
        scenario = self._load_scenario(task, seed)
        checks_status = {check_name: False for check_name in scenario["checks"]}
        return CIEpisodeRuntime(
            scenario=scenario,
            current_files=dict(scenario.get("files", {})),
            checks_status=checks_status,
            last_ci_output=scenario.get("initial_ci_output"),
        )

    def handle_action(
        self,
        runtime: CIEpisodeRuntime,
        action_type: str,
        payload: dict[str, Any],
        step_count: int,
    ) -> CIEngineResult:
        if action_type == "read_file":
            return self._read_file(runtime, payload)
        if action_type == "run_check":
            return self._run_check(runtime, payload)
        if action_type == "submit_patch":
            return self._submit_patch(runtime, payload, step_count)
        return CIEngineResult(
            reward=0.0,
            feedback=f"Unsupported CI action_type={action_type!r}.",
            done=False,
            ci_output=runtime.last_ci_output,
        )

    def _read_file(self, runtime: CIEpisodeRuntime, payload: dict[str, Any]) -> CIEngineResult:
        path = payload.get("path", "")
        content = runtime.current_files.get(path)
        if content is None:
            available = ", ".join(sorted(runtime.current_files))
            tool_results = f"Unknown file {path!r}. Available files: {available}"
        else:
            tool_results = f"# {path}\n{content}"
        runtime.last_tool_results = tool_results
        return CIEngineResult(
            reward=0.0,
            feedback="Returned file contents.",
            done=False,
            tool_results=tool_results,
            ci_output=runtime.last_ci_output,
        )

    def _run_check(self, runtime: CIEpisodeRuntime, payload: dict[str, Any]) -> CIEngineResult:
        check_name = payload.get("check", "")
        if check_name not in runtime.scenario["checks"]:
            available = ", ".join(sorted(runtime.scenario["checks"]))
            output = f"Unknown check {check_name!r}. Available checks: {available}"
        else:
            check = runtime.scenario["checks"][check_name]
            passing = runtime.checks_status.get(check_name, False)
            output = check["success_output"] if passing else check["failure_output"]

        runtime.last_ci_output = output
        return CIEngineResult(
            reward=0.0,
            feedback=f"Ran check {check_name!r}.",
            done=all(runtime.checks_status.values()) if runtime.checks_status else False,
            ci_output=output,
        )

    def _submit_patch(
        self,
        runtime: CIEpisodeRuntime,
        payload: dict[str, Any],
        step_count: int,
    ) -> CIEngineResult:
        patch = str(payload.get("patch", "")).strip()
        file_path = str(payload.get("file", "")).strip()
        repeated_patch = patch in runtime.patches_applied if patch else False
        patch_applies = bool(patch)

        # Real structural validation: try to parse as Python via ast
        parses = self._validate_parses(patch)

        previous_status = dict(runtime.checks_status)

        # Evaluate checks with strengthened grading
        runtime.checks_status = self._evaluate_checks(runtime.scenario, patch)

        newly_green_checks = sum(
            1
            for check_name, is_green in runtime.checks_status.items()
            if is_green and not previous_status.get(check_name, False)
        )
        broke_green_checks = any(
            previous_status.get(check_name, False) and not is_green
            for check_name, is_green in runtime.checks_status.items()
        )
        scenario_config = runtime.scenario.get("reward_config", {})
        config_obj = CIRewardConfig(**scenario_config) if scenario_config else CIRewardConfig()

        all_green = all(runtime.checks_status.values()) if runtime.checks_status else False
        reward, notes = ci_step_reward(
            patch_applies=patch_applies,
            parses=parses,
            newly_green_checks=newly_green_checks,
            all_green=all_green,
            repeated_patch=repeated_patch,
            broke_green_checks=broke_green_checks,
            step_count=step_count,
            config=config_obj,
        )

        if patch:
            runtime.patches_applied.append(patch)
        if file_path and file_path in runtime.current_files and patch:
            runtime.current_files[file_path] = patch

        ci_output = self._format_all_checks(runtime.scenario, runtime.checks_status)
        runtime.last_ci_output = ci_output
        runtime.last_tool_results = (
            f"Recorded patch for {file_path or 'multiple files'}."
            if patch
            else "Empty patch submitted."
        )

        feedback = "Patch evaluated."
        if notes:
            feedback = f"{feedback} {'; '.join(notes)}."
        if all_green:
            feedback = f"{feedback} CI is healthy."

        return CIEngineResult(
            reward=reward,
            feedback=feedback,
            done=all_green,
            tool_results=runtime.last_tool_results,
            ci_output=ci_output,
        )

    def _validate_parses(self, patch: str) -> bool:
        """Validate that the patch is syntactically valid Python using ast.parse.

        Falls back to token-based heuristic only if the patch is clearly
        not a standalone Python file (e.g., a diff or multi-file patch).
        """
        if not patch.strip():
            return False
        try:
            ast.parse(patch)
            return True
        except SyntaxError:
            pass

        # Fallback: if the patch contains diff-like markers, it's not meant
        # to be standalone Python.  Accept it if it contains code-like tokens.
        diff_markers = ("---", "+++", "@@", "diff --git")
        if any(marker in patch for marker in diff_markers):
            # It's a unified-diff style patch.  Check that the added lines parse.
            added_lines = [
                line[1:] for line in patch.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            ]
            if added_lines:
                try:
                    ast.parse("\n".join(added_lines))
                    return True
                except SyntaxError:
                    return False
        return False

    def _evaluate_checks(self, scenario: dict[str, Any], patch: str) -> dict[str, bool]:
        """Evaluate whether each defined check passes for the submitted patch.

        Uses a layered approach:
        1. The patch must parse as valid Python (via ast).
        2. Token matching checks that required code constructs are present.
        3. Optional structural validators for deeper analysis.
        """
        results: dict[str, bool] = {}

        # Gate: if the patch doesn't parse at all, no checks pass
        if not self._validate_parses(patch):
            for check_name in scenario["checks"]:
                results[check_name] = False
            return results

        patch_lower = patch.lower()

        for check_name, check_config in scenario["checks"].items():
            results[check_name] = False

            # Primary: token group matching — all tokens in at least one group must be present
            for token_group in check_config.get("required_tokens_any_of", []):
                if all(token.lower() in patch_lower for token in token_group):
                    results[check_name] = True
                    break

            # If token matching passed, apply structural validators if defined
            if results[check_name]:
                structural = check_config.get("structural_validators", [])
                for validator in structural:
                    if not self._run_structural_validator(validator, patch):
                        results[check_name] = False
                        break

        return results

    def _run_structural_validator(self, validator: dict[str, Any], patch: str) -> bool:
        """Run a named structural validator on the patch.

        Validators are defined in scenario JSON under checks[name].structural_validators.
        Supported validators:
        - "ast_node_present": checks that a specific AST node type exists
        - "imports_before_functions": checks E402-style import ordering
        - "no_bare_except": checks that there are no bare except clauses
        - "function_defined": checks that a named function exists
        - "ruff_check": runs real ruff linter (if available)
        """
        vtype = validator.get("type", "")

        if vtype == "ast_node_present":
            return self._check_ast_node_present(patch, validator.get("node_type", ""))

        if vtype == "imports_before_functions":
            return self._check_imports_before_functions(patch)

        if vtype == "no_bare_except":
            return self._check_no_bare_except(patch)

        if vtype == "function_defined":
            return self._check_function_defined(patch, validator.get("name", ""))

        if vtype == "ruff_check":
            return self._run_ruff_check(patch, validator.get("select", "E,F,I"))

        return True  # Unknown validator type — don't block

    def _check_ast_node_present(self, patch: str, node_type: str) -> bool:
        """Check that at least one AST node of the given type exists in the patch."""
        try:
            tree = ast.parse(patch)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if type(node).__name__ == node_type:
                return True
        return False

    def _check_imports_before_functions(self, patch: str) -> bool:
        """Check that all module-level imports appear before function definitions."""
        try:
            tree = ast.parse(patch)
        except SyntaxError:
            return False
        last_import_line = 0
        first_func_line = float("inf")
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                last_import_line = max(last_import_line, node.lineno)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                first_func_line = min(first_func_line, node.lineno)
        if last_import_line == 0:
            return True  # No imports — nothing to check
        return last_import_line < first_func_line

    def _check_no_bare_except(self, patch: str) -> bool:
        """Check that there are no bare `except:` clauses."""
        try:
            tree = ast.parse(patch)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                return False
        return True

    def _check_function_defined(self, patch: str, name: str) -> bool:
        """Check that a function with the given name is defined."""
        try:
            tree = ast.parse(patch)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    return True
        return False

    def _run_ruff_check(self, patch: str, select: str = "E,F,I") -> bool:
        """Run the ruff linter on the patch. Returns True if no violations found.

        Falls back gracefully if ruff is not installed.
        """
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(patch)
                tmp.flush()
                tmp_path = tmp.name

            result = subprocess.run(
                ["ruff", "check", tmp_path, "--select", select, "--no-fix"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # ruff not installed or timed out — fall back to passing
            return True
        finally:
            try:
                os.unlink(tmp_path)
            except (OSError, UnboundLocalError):
                pass

    def _format_all_checks(self, scenario: dict[str, Any], checks_status: dict[str, bool]) -> str:
        blocks: list[str] = []
        for check_name, check_config in scenario["checks"].items():
            passed = checks_status.get(check_name, False)
            state = "PASSED" if passed else "FAILED"
            body = check_config["success_output"] if passed else check_config["failure_output"]
            blocks.append(f"[{state}] {check_name}\n{body}")
        return "\n\n".join(blocks)

    def _load_scenario(self, task: TaskDefinition, seed: Optional[int]) -> dict[str, Any]:
        candidates = sorted(Path(task.scenario_dir).glob(task.scenario_glob))
        if not candidates:
            raise FileNotFoundError(f"No CI scenarios found for {task.id} in {task.scenario_dir}")
        chooser = random.Random(seed)
        selected = chooser.choice(candidates)
        with selected.open("r", encoding="utf-8") as handle:
            return json.load(handle)

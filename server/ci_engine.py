from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from server.reward import ci_step_reward
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
        parses = any(
            token.lower() in patch.lower() for token in runtime.scenario.get("parse_tokens_any", [])
        )
        previous_status = dict(runtime.checks_status)
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
        all_green = all(runtime.checks_status.values()) if runtime.checks_status else False
        reward, notes = ci_step_reward(
            patch_applies=patch_applies,
            parses=parses,
            newly_green_checks=newly_green_checks,
            all_green=all_green,
            repeated_patch=repeated_patch,
            broke_green_checks=broke_green_checks,
            step_count=step_count,
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

    def _evaluate_checks(self, scenario: dict[str, Any], patch: str) -> dict[str, bool]:
        patch_lower = patch.lower()
        results: dict[str, bool] = {}
        for check_name, check_config in scenario["checks"].items():
            results[check_name] = False
            for token_group in check_config.get("required_tokens_any_of", []):
                if all(token.lower() in patch_lower for token in token_group):
                    results[check_name] = True
                    break
        return results

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

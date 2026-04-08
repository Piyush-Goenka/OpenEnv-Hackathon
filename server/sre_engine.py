from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from server.reward import clamp_reward, sre_diagnosis_reward, sre_query_reward, sre_remediation_reward, SRERewardConfig
from tasks.base import TaskDefinition


@dataclass
class SREEngineResult:
    reward: float
    feedback: str
    done: bool
    tool_results: Optional[str] = None


@dataclass
class SREEpisodeRuntime:
    scenario: dict[str, Any]
    queries_made: list[str] = field(default_factory=list)
    services_investigated: list[str] = field(default_factory=list)
    # Tracks one-time reward signals already claimed to prevent farming
    one_time_rewards_claimed: set[str] = field(default_factory=set)
    # Best undecayed diagnosis score achieved so far — only improvements earn reward
    best_diagnosis_score: float = 0.0
    diagnosis_submitted: bool = False
    remediation_submitted: bool = False
    diagnosis_correct: bool = False
    remediation_correct: bool = False
    last_tool_results: Optional[str] = None


class SREEngine:
    def start_episode(self, task: TaskDefinition, seed: Optional[int] = None) -> SREEpisodeRuntime:
        scenario = self._load_scenario(task, seed)
        return SREEpisodeRuntime(scenario=scenario)

    def handle_action(
        self,
        runtime: SREEpisodeRuntime,
        action_type: str,
        payload: dict[str, Any],
        step_count: int,
    ) -> SREEngineResult:
        if action_type in {
            "get_logs",
            "get_metrics",
            "get_diff",
            "get_heap_summary",
            "get_deployment_history",
        }:
            return self._handle_query(runtime, action_type, payload, step_count)
        if action_type == "submit_diagnosis":
            return self._submit_diagnosis(runtime, payload, step_count)
        if action_type == "submit_remediation":
            return self._submit_remediation(runtime, payload, step_count)
        return SREEngineResult(
            reward=0.0,
            feedback=f"Unsupported SRE action_type={action_type!r}.",
            done=False,
        )

    def _handle_query(
        self,
        runtime: SREEpisodeRuntime,
        action_type: str,
        payload: dict[str, Any],
        step_count: int,
    ) -> SREEngineResult:
        fingerprint = json.dumps({"action_type": action_type, "payload": payload}, sort_keys=True)
        repeated_query = fingerprint in runtime.queries_made
        runtime.queries_made.append(fingerprint)

        service = str(payload.get("service", "")).strip()
        query_rewards = runtime.scenario.get("query_rewards", {})
        root_cause_service = query_rewards.get("root_cause_service", "")
        relevant_services = set(runtime.scenario.get("relevant_services", []))
        claimed = runtime.one_time_rewards_claimed

        # One-time signals: only fire the first time each condition is met
        new_relevant_service = False
        queried_root_cause_service = False

        if service and service not in runtime.services_investigated:
            runtime.services_investigated.append(service)
            if service in relevant_services and service not in claimed:
                new_relevant_service = True
                claimed.add(f"relevant:{service}")
            # Root-cause bonus only on the FIRST query to that service
            if service == root_cause_service and "root_cause_service" not in claimed:
                queried_root_cause_service = True
                claimed.add("root_cause_service")

        # Deployment history: one-time reward
        queried_deployment_history = (
            action_type == "get_deployment_history"
            and "deployment_history" not in claimed
        )
        if queried_deployment_history:
            claimed.add("deployment_history")

        # Correct diff: one-time reward
        queried_correct_diff = False
        queried_heap_summary = False

        if action_type == "get_logs":
            tool_results = self._format_logs(runtime.scenario, payload)
        elif action_type == "get_metrics":
            tool_results = self._format_metrics(runtime.scenario, payload)
        elif action_type == "get_diff":
            tool_results = self._format_diff(runtime.scenario, payload)
            correct_diff_id = query_rewards.get("correct_diff_id")
            if (
                payload.get("deploy_id") == correct_diff_id
                and "correct_diff" not in claimed
            ):
                queried_correct_diff = True
                claimed.add("correct_diff")
        elif action_type == "get_heap_summary":
            tool_results = self._format_heap_summary(runtime.scenario, payload)
            correct_ts = query_rewards.get("heap_summary_timestamp")
            if (
                payload.get("timestamp") == correct_ts
                and "heap_summary" not in claimed
            ):
                queried_heap_summary = True
                claimed.add("heap_summary")
        else:
            tool_results = self._format_deployment_history(runtime.scenario)

        scenario_config = runtime.scenario.get("reward_config", {})
        config_obj = SRERewardConfig(**scenario_config) if scenario_config else SRERewardConfig()

        reward, notes = sre_query_reward(
            repeated_query=repeated_query,
            new_relevant_service=new_relevant_service,
            queried_root_cause_service=queried_root_cause_service,
            queried_deployment_history=queried_deployment_history,
            queried_correct_diff=queried_correct_diff,
            queried_heap_summary=queried_heap_summary,
            step_count=step_count,
            config=config_obj,
        )
        runtime.last_tool_results = tool_results
        feedback = "Investigation data returned."
        if notes:
            feedback = f"{feedback} {'; '.join(notes)}."

        return SREEngineResult(
            reward=reward,
            feedback=feedback,
            done=runtime.diagnosis_correct and self._task_complete(runtime),
            tool_results=tool_results,
        )

    def _submit_diagnosis(
        self,
        runtime: SREEpisodeRuntime,
        payload: dict[str, Any],
        step_count: int,
    ) -> SREEngineResult:
        runtime.diagnosis_submitted = True
        field_results: list[tuple[str, bool, float]] = []
        diagnosis_fields = runtime.scenario.get("diagnosis_fields", {})

        for field_name, config in diagnosis_fields.items():
            expected = str(config["value"]).strip().lower()
            submitted = str(payload.get(field_name, "")).strip().lower()
            match_mode = config.get("match_mode", "equals")
            matched = expected == submitted if match_mode == "equals" else expected in submitted
            field_results.append((field_name, matched, float(config["weight"])))

        runtime.diagnosis_correct = all(match for _, match, _ in field_results) and bool(field_results)

        scenario_config = runtime.scenario.get("reward_config", {})
        config_obj = SRERewardConfig(**scenario_config) if scenario_config else SRERewardConfig()

        # Delta-reward: only genuine improvements over best previous submission earn reward.
        # Prevents farming (agent repeatedly submitting correct diagnosis before remediation).
        undecayed = sum(
            weight * config_obj.diagnosis_weight_scale
            for _, matched, weight in field_results
            if matched
        )
        delta = undecayed - runtime.best_diagnosis_score

        if delta > 0:
            runtime.best_diagnosis_score = undecayed
            reward = clamp_reward(delta * (config_obj.step_decay_factor ** step_count))
            notes = [f"correct {name}" for name, matched, _ in field_results if matched]
            feedback = "Diagnosis submitted."
            if notes:
                feedback = f"{feedback} {'; '.join(notes)}."
        elif not any(matched for _, matched, _ in field_results) and runtime.best_diagnosis_score == 0.0:
            # First attempt was entirely wrong — apply negative penalty (clamped to 0 by environment)
            reward = clamp_reward(-config_obj.wrong_diagnosis_penalty)
            feedback = "Diagnosis submitted. wrong diagnosis penalty."
        else:
            # No improvement over best — silent zero reward
            reward = 0.0
            feedback = "Diagnosis submitted. No improvement over previous submission."

        return SREEngineResult(
            reward=reward,
            feedback=feedback,
            done=self._task_complete(runtime),
        )

    def _submit_remediation(
        self,
        runtime: SREEpisodeRuntime,
        payload: dict[str, Any],
        step_count: int,
    ) -> SREEngineResult:
        submitted = " ".join(str(value) for value in payload.values()).strip().lower()
        accepted = [
            remediation.strip().lower()
            for remediation in runtime.scenario.get("accepted_remediations", [])
        ]
        is_correct = any(candidate in submitted for candidate in accepted)
        runtime.remediation_correct = is_correct

        already_rewarded = "remediation_rewarded" in runtime.one_time_rewards_claimed
        runtime.remediation_submitted = True

        scenario_config = runtime.scenario.get("reward_config", {})
        config_obj = SRERewardConfig(**scenario_config) if scenario_config else SRERewardConfig()

        if is_correct and not already_rewarded:
            # First correct submission — full reward
            runtime.one_time_rewards_claimed.add("remediation_rewarded")
            reward, notes = sre_remediation_reward(True, step_count, config_obj)
            feedback = f"Remediation submitted. {'; '.join(notes)}."
        elif already_rewarded:
            # Already got the reward — no additional reward (farming prevention)
            reward = 0.0
            feedback = "Remediation submitted. No improvement over previous submission."
        else:
            # Wrong submission, never been rewarded — zero reward (can retry)
            reward = 0.0
            feedback = "Remediation submitted. incorrect remediation."

        return SREEngineResult(
            reward=reward,
            feedback=feedback,
            done=self._task_complete(runtime),
        )

    def _task_complete(self, runtime: SREEpisodeRuntime) -> bool:
        if runtime.scenario.get("accepted_remediations"):
            return runtime.diagnosis_correct and runtime.remediation_correct
        return runtime.diagnosis_correct

    def _format_logs(self, scenario: dict[str, Any], payload: dict[str, Any]) -> str:
        service = str(payload.get("service", "")).strip()
        logs = scenario.get("logs", {}).get(service)
        if logs is None:
            available = ", ".join(sorted(scenario.get("logs", {})))
            return f"Unknown service {service!r}. Available services: {available}"
        return "\n".join(logs)

    def _format_metrics(self, scenario: dict[str, Any], payload: dict[str, Any]) -> str:
        service = str(payload.get("service", "")).strip()
        metric = str(payload.get("metric", "")).strip()
        metric_data = scenario.get("metrics", {}).get(service, {}).get(metric)
        if metric_data is None:
            available = scenario.get("metrics", {}).get(service, {})
            return f"No metric {metric!r} for {service!r}. Available: {list(available)}"
        return json.dumps(metric_data, indent=2)

    def _format_diff(self, scenario: dict[str, Any], payload: dict[str, Any]) -> str:
        deploy_id = str(payload.get("deploy_id", "")).strip()
        diff = scenario.get("diffs", {}).get(deploy_id)
        if diff is None:
            available = ", ".join(sorted(scenario.get("diffs", {})))
            return f"Unknown deploy_id {deploy_id!r}. Available: {available}"
        return diff

    def _format_heap_summary(self, scenario: dict[str, Any], payload: dict[str, Any]) -> str:
        timestamp = str(payload.get("timestamp", "")).strip()
        summary = scenario.get("heap_summaries", {}).get(timestamp)
        if summary is None:
            available = ", ".join(sorted(scenario.get("heap_summaries", {})))
            return f"Unknown heap summary timestamp {timestamp!r}. Available: {available}"
        return json.dumps(summary, indent=2)

    def _format_deployment_history(self, scenario: dict[str, Any]) -> str:
        history = scenario.get("deployment_history", [])
        if not history:
            return "No deployment history available for this scenario."
        return json.dumps(history, indent=2)

    def _load_scenario(self, task: TaskDefinition, seed: Optional[int]) -> dict[str, Any]:
        candidates = sorted(Path(task.scenario_dir).glob(task.scenario_glob))
        if not candidates:
            raise FileNotFoundError(f"No SRE scenarios found for {task.id} in {task.scenario_dir}")
        chooser = random.Random(seed)
        selected = chooser.choice(candidates)
        with selected.open("r", encoding="utf-8") as handle:
            return json.load(handle)

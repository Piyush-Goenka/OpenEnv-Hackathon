from __future__ import annotations

import uuid
from typing import Any, Optional

from openenv.core.env_server import Environment

from models import DevReliabilityAction, DevReliabilityObservation, DevReliabilityState
from server.ci_engine import CIEngine, CIEpisodeRuntime
from server.sre_engine import SREEngine, SREEpisodeRuntime
from tasks import DEFAULT_TASK_ID, TaskDefinition, get_task


class DevReliabilityEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self) -> None:
        self._ci_engine = CIEngine()
        self._sre_engine = SREEngine()
        self._task: Optional[TaskDefinition] = None
        self._runtime: Optional[CIEpisodeRuntime | SREEpisodeRuntime] = None
        self._state = DevReliabilityState()
        self._last_tool_results: Optional[str] = None
        self._last_ci_output: Optional[str] = None

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: str = DEFAULT_TASK_ID,
        **_: Any,
    ) -> DevReliabilityObservation:
        task = get_task(task_id)
        self._task = task
        self._runtime = (
            self._ci_engine.start_episode(task, seed)
            if task.track == "ci"
            else self._sre_engine.start_episode(task, seed)
        )
        self._last_tool_results = None
        self._last_ci_output = (
            self._runtime.last_ci_output if isinstance(self._runtime, CIEpisodeRuntime) else None
        )
        self._state = DevReliabilityState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            track=task.track,
            task_id=task.id,
            difficulty=task.difficulty,
            current_files=(
                dict(self._runtime.current_files)
                if isinstance(self._runtime, CIEpisodeRuntime)
                else {}
            ),
            patches_applied=(
                list(self._runtime.patches_applied)
                if isinstance(self._runtime, CIEpisodeRuntime)
                else []
            ),
            checks_status=(
                dict(self._runtime.checks_status)
                if isinstance(self._runtime, CIEpisodeRuntime)
                else {}
            ),
            queries_made=(
                list(self._runtime.queries_made)
                if isinstance(self._runtime, SREEpisodeRuntime)
                else []
            ),
            services_investigated=(
                list(self._runtime.services_investigated)
                if isinstance(self._runtime, SREEpisodeRuntime)
                else []
            ),
            diagnosis_submitted=(
                self._runtime.diagnosis_submitted
                if isinstance(self._runtime, SREEpisodeRuntime)
                else False
            ),
            remediation_submitted=(
                self._runtime.remediation_submitted
                if isinstance(self._runtime, SREEpisodeRuntime)
                else False
            ),
            max_steps=task.max_steps,
            done=False,
            final_score=0.0,
        )
        return self._build_observation(
            reward=None,
            done=False,
            feedback="Episode started.",
            tool_results=None,
            ci_output=self._last_ci_output,
        )

    def step(
        self,
        action: DevReliabilityAction,
        timeout_s: Optional[float] = None,
        **_: Any,
    ) -> DevReliabilityObservation:
        del timeout_s
        if self._task is None or self._runtime is None:
            raise RuntimeError("reset() must be called before step().")

        self._state.step_count += 1
        if self._task.track == "ci":
            if not isinstance(self._runtime, CIEpisodeRuntime):
                raise RuntimeError("CI task has invalid runtime state.")
            result = self._ci_engine.handle_action(
                self._runtime,
                action.action_type,
                action.payload,
                self._state.step_count,
            )
            self._state.current_files = dict(self._runtime.current_files)
            self._state.patches_applied = list(self._runtime.patches_applied)
            self._state.checks_status = dict(self._runtime.checks_status)
            self._last_ci_output = result.ci_output
            self._last_tool_results = result.tool_results
        else:
            if not isinstance(self._runtime, SREEpisodeRuntime):
                raise RuntimeError("SRE task has invalid runtime state.")
            result = self._sre_engine.handle_action(
                self._runtime,
                action.action_type,
                action.payload,
                self._state.step_count,
            )
            self._state.queries_made = list(self._runtime.queries_made)
            self._state.services_investigated = list(self._runtime.services_investigated)
            self._state.diagnosis_submitted = self._runtime.diagnosis_submitted
            self._state.remediation_submitted = self._runtime.remediation_submitted
            self._last_tool_results = result.tool_results
            self._last_ci_output = None

        self._state.final_score = round(self._state.final_score + (result.reward or 0.0), 3)
        done = result.done or self._state.step_count >= self._state.max_steps
        feedback = result.feedback
        if done and not result.done and self._state.step_count >= self._state.max_steps:
            feedback = f"{feedback} Maximum steps reached."
        self._state.done = done

        return self._build_observation(
            reward=result.reward,
            done=done,
            feedback=feedback,
            tool_results=self._last_tool_results,
            ci_output=self._last_ci_output,
        )

    @property
    def state(self) -> DevReliabilityState:
        return self._state

    def _build_observation(
        self,
        *,
        reward: Optional[float],
        done: bool,
        feedback: str,
        tool_results: Optional[str],
        ci_output: Optional[str],
    ) -> DevReliabilityObservation:
        if self._task is None or self._runtime is None:
            raise RuntimeError("No active episode. Call reset() first.")

        scenario = self._runtime.scenario
        checks_status = self._state.checks_status

        return DevReliabilityObservation(
            done=done,
            reward=reward,
            task_id=self._task.id,
            track=self._task.track,
            difficulty=self._task.difficulty,
            description=self._task.description,
            context=self._build_context(scenario),
            available_actions=list(self._task.available_actions),
            tool_results=tool_results,
            ci_output=ci_output,
            checks_passing=sum(1 for is_green in checks_status.values() if is_green)
            if checks_status
            else None,
            checks_total=len(checks_status) if checks_status else None,
            step_count=self._state.step_count,
            max_steps=self._task.max_steps,
            feedback=feedback,
        )

    def _build_context(self, scenario: dict[str, Any]) -> dict[str, Any]:
        if self._task is None:
            return {}
        if self._task.track == "ci":
            return {
                "scenario_id": scenario.get("scenario_id"),
                "title": scenario.get("title"),
                "pr_diff": scenario.get("pr_diff"),
                "relevant_files": scenario.get("relevant_files", []),
                "initial_ci_output": scenario.get("initial_ci_output"),
            }
        return {
            "scenario_id": scenario.get("scenario_id"),
            "title": scenario.get("title"),
            "alert": scenario.get("alert"),
            "service_catalog": scenario.get("service_catalog", []),
            "deployment_ids": [item.get("deploy_id") for item in scenario.get("deployment_history", [])],
            "initial_log_excerpt": scenario.get("initial_log_excerpt"),
        }

from __future__ import annotations

try:
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient
except ImportError:  # pragma: no cover - compatibility fallback
    from openenv.core.http_env_client import HTTPEnvClient as EnvClient
    from openenv.core.types import StepResult

from models import DevReliabilityAction, DevReliabilityObservation, DevReliabilityState


class DevReliabilityEnv(
    EnvClient[DevReliabilityAction, DevReliabilityObservation, DevReliabilityState]
):
    def _step_payload(self, action: DevReliabilityAction) -> dict:
        return {"action_type": action.action_type, "payload": action.payload}

    def _parse_result(self, payload: dict) -> StepResult:
        observation_payload = payload.get("observation", payload)
        observation = DevReliabilityObservation(
            done=observation_payload.get("done", payload.get("done", False)),
            reward=observation_payload.get("reward", payload.get("reward")),
            task_id=observation_payload.get("task_id", ""),
            track=observation_payload.get("track", ""),
            difficulty=observation_payload.get("difficulty", ""),
            description=observation_payload.get("description", ""),
            context=observation_payload.get("context", {}),
            available_actions=observation_payload.get("available_actions", []),
            tool_results=observation_payload.get("tool_results"),
            ci_output=observation_payload.get("ci_output"),
            checks_passing=observation_payload.get("checks_passing"),
            checks_total=observation_payload.get("checks_total"),
            feedback=observation_payload.get("feedback", ""),
            step_count=observation_payload.get("step_count", 0),
            max_steps=observation_payload.get("max_steps", 0),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
        )

    def _parse_state(self, payload: dict) -> DevReliabilityState:
        return DevReliabilityState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id", ""),
            track=payload.get("track", ""),
            difficulty=payload.get("difficulty", ""),
            current_files=payload.get("current_files", {}),
            patches_applied=payload.get("patches_applied", []),
            checks_status=payload.get("checks_status", {}),
            queries_made=payload.get("queries_made", []),
            services_investigated=payload.get("services_investigated", []),
            diagnosis_submitted=payload.get("diagnosis_submitted", False),
            remediation_submitted=payload.get("remediation_submitted", False),
            max_steps=payload.get("max_steps", 0),
            done=payload.get("done", False),
            final_score=payload.get("final_score", 0.0),
        )

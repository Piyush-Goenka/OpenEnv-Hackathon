from __future__ import annotations

try:
    from openenv.core.client_types import StepResult
    from openenv.core.env_client import EnvClient
except ImportError:  # pragma: no cover - compatibility fallback
    from openenv.core.http_env_client import HTTPEnvClient as EnvClient
    from openenv.core.types import StepResult

from models import HackathonAction, HackathonObservation, HackathonState


class HackathonEnv(EnvClient[HackathonAction, HackathonObservation, HackathonState]):
    def _step_payload(self, action: HackathonAction) -> dict:
        return {"response": action.response}

    def _parse_result(self, payload: dict) -> StepResult:
        observation_payload = payload.get("observation", payload)
        observation = HackathonObservation(
            done=observation_payload.get("done", payload.get("done", False)),
            reward=observation_payload.get("reward", payload.get("reward")),
            task_id=observation_payload.get("task_id", ""),
            difficulty=observation_payload.get("difficulty", ""),
            task_description=observation_payload.get("task_description", ""),
            current_state=observation_payload.get("current_state", ""),
            feedback=observation_payload.get("feedback", ""),
            step_count=observation_payload.get("step_count", 0),
            max_steps=observation_payload.get("max_steps", 0),
            history=observation_payload.get("history", []),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
        )

    def _parse_state(self, payload: dict) -> HackathonState:
        return HackathonState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id", ""),
            difficulty=payload.get("difficulty", ""),
            max_steps=payload.get("max_steps", 0),
            last_reward=payload.get("last_reward"),
        )

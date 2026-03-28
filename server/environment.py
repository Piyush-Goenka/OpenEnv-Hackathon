from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from openenv.core.env_server import Environment

from models import HackathonAction, HackathonObservation, HackathonState
from tasks import DEFAULT_TASK_ID, TaskDefinition, get_task


class HackathonEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self) -> None:
        self._state = HackathonState()
        self._current_task: Optional[TaskDefinition] = None
        self._history: List[Dict[str, Any]] = []

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: str = DEFAULT_TASK_ID,
        **_: Any,
    ) -> HackathonObservation:
        del seed
        task = get_task(task_id)
        self._current_task = task
        self._history = []
        self._state = HackathonState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            task_id=task.id,
            difficulty=task.difficulty,
            max_steps=task.max_steps,
            last_reward=None,
        )
        return self._build_observation(
            feedback=(
                "Episode started. This scaffold uses placeholder tasks and should be "
                "replaced with the final domain-specific environment logic."
            ),
            reward=None,
            done=False,
        )

    def step(
        self,
        action: HackathonAction,
        timeout_s: Optional[float] = None,
        **_: Any,
    ) -> HackathonObservation:
        del timeout_s
        if self._current_task is None:
            raise RuntimeError("reset() must be called before step().")

        self._state.step_count += 1
        submission = action.response.strip()
        reward, feedback = self._current_task.grader(submission)
        self._state.last_reward = reward
        self._history.append(
            {
                "step": self._state.step_count,
                "submission": submission,
                "reward": reward,
            }
        )
        done = reward >= 1.0 or self._state.step_count >= self._current_task.max_steps
        if done and reward < 1.0 and self._state.step_count >= self._current_task.max_steps:
            feedback = f"{feedback} Maximum steps reached for this episode."
        return self._build_observation(feedback=feedback, reward=reward, done=done)

    @property
    def state(self) -> HackathonState:
        return self._state

    def _build_observation(
        self,
        *,
        feedback: str,
        reward: Optional[float],
        done: bool,
    ) -> HackathonObservation:
        if self._current_task is None:
            raise RuntimeError("No task has been selected. Call reset() first.")
        return HackathonObservation(
            done=done,
            reward=reward,
            task_id=self._current_task.id,
            difficulty=self._current_task.difficulty,
            task_description=self._current_task.description,
            current_state=self._render_state(),
            feedback=feedback,
            step_count=self._state.step_count,
            max_steps=self._current_task.max_steps,
            history=list(self._history),
        )

    def _render_state(self) -> str:
        if self._current_task is None:
            return "Environment not initialized."
        if not self._history:
            return self._current_task.initial_state

        lines = [self._current_task.initial_state, "", "Recent attempts:"]
        for entry in self._history[-3:]:
            lines.append(
                f"- step={entry['step']} reward={entry['reward']:.2f} submission={entry['submission']!r}"
            )
        return "\n".join(lines)

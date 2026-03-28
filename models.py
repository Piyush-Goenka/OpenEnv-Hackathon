from __future__ import annotations

from typing import Any, Dict, List, Optional

from openenv.core.env_server import Action, Observation, State
from pydantic import Field


class HackathonAction(Action):
    response: str


class HackathonObservation(Observation):
    done: bool = False
    reward: Optional[float] = None
    task_id: str = ""
    difficulty: str = ""
    task_description: str = ""
    current_state: str = ""
    feedback: str = ""
    step_count: int = 0
    max_steps: int = 0
    history: List[Dict[str, Any]] = Field(default_factory=list)


class HackathonState(State):
    episode_id: Optional[str] = None
    step_count: int = 0
    task_id: str = ""
    difficulty: str = ""
    max_steps: int = 0
    last_reward: Optional[float] = None

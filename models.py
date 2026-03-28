from __future__ import annotations

from typing import Any, Dict, List, Optional

from openenv.core.env_server import Action, Observation, State
from pydantic import Field


class DevReliabilityAction(Action):
    action_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class DevReliabilityObservation(Observation):
    done: bool = False
    reward: Optional[float] = None
    task_id: str = ""
    track: str = ""
    difficulty: str = ""
    description: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)
    available_actions: List[str] = Field(default_factory=list)
    tool_results: Optional[str] = None
    ci_output: Optional[str] = None
    checks_passing: Optional[int] = None
    checks_total: Optional[int] = None
    feedback: str = ""
    step_count: int = 0
    max_steps: int = 0


class DevReliabilityState(State):
    episode_id: Optional[str] = None
    step_count: int = 0
    track: str = ""
    task_id: str = ""
    difficulty: str = ""
    current_files: Dict[str, str] = Field(default_factory=dict)
    patches_applied: List[str] = Field(default_factory=list)
    checks_status: Dict[str, bool] = Field(default_factory=dict)
    queries_made: List[str] = Field(default_factory=list)
    services_investigated: List[str] = Field(default_factory=list)
    diagnosis_submitted: bool = False
    remediation_submitted: bool = False
    max_steps: int = 0
    done: bool = False
    final_score: float = 0.0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Track = Literal["ci", "sre"]


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    id: str
    track: Track
    difficulty: str
    title: str
    description: str
    max_steps: int
    available_actions: tuple[str, ...]
    scenario_glob: str

    @property
    def scenario_dir(self) -> Path:
        data_root = Path(__file__).resolve().parent.parent / "data"
        return data_root / ("ci_scenarios" if self.track == "ci" else "sre_scenarios")

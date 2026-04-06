from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class CIRewardConfig:
    patch_applied: float = 0.10
    parses: float = 0.10
    newly_green_check: float = 0.20
    all_green_base: float = 0.40
    repeated_patch_penalty: float = 0.10
    broke_green_check_penalty: float = 0.15
    efficiency_bonus_step1: float = 0.10
    efficiency_bonus_step2: float = 0.05
    step_decay_factor: float = 0.95


@dataclass
class SRERewardConfig:
    new_relevant_service: float = 0.05
    queried_root_cause: float = 0.15
    queried_deployment_history: float = 0.10
    queried_correct_diff: float = 0.10
    queried_heap_summary: float = 0.20
    repeated_query_penalty: float = 0.05
    wrong_diagnosis_penalty: float = 0.10
    correct_remediation: float = 0.35
    step_decay_factor: float = 0.95


def clamp_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def ci_efficiency_bonus(step_count: int, config: CIRewardConfig) -> float:
    if step_count <= 1:
        return config.efficiency_bonus_step1
    if step_count == 2:
        return config.efficiency_bonus_step2
    return 0.0


def ci_step_reward(
    *,
    patch_applies: bool,
    parses: bool,
    newly_green_checks: int,
    all_green: bool,
    repeated_patch: bool,
    broke_green_checks: bool,
    step_count: int,
    config: CIRewardConfig | None = None,
) -> tuple[float, list[str]]:
    if config is None:
        config = CIRewardConfig()

    reward = 0.0
    notes: list[str] = []

    if patch_applies:
        reward += config.patch_applied
        notes.append("patch applied cleanly")
    if parses:
        reward += config.parses
        notes.append("code still parses structurally")
    if newly_green_checks:
        reward += config.newly_green_check * newly_green_checks
        notes.append(f"{newly_green_checks} new check(s) went green")
    if all_green:
        reward += config.all_green_base + ci_efficiency_bonus(step_count, config)
        notes.append("all checks green")
    if repeated_patch:
        reward -= config.repeated_patch_penalty
        notes.append("repeated identical patch penalty")
    if broke_green_checks:
        reward -= config.broke_green_check_penalty
        notes.append("patch regressed a previously green check")

    decayed_reward = reward * (config.step_decay_factor ** step_count)
    return clamp_score(decayed_reward), notes


def sre_query_reward(
    *,
    repeated_query: bool,
    new_relevant_service: bool,
    queried_root_cause_service: bool,
    queried_deployment_history: bool,
    queried_correct_diff: bool,
    queried_heap_summary: bool,
    step_count: int,
    config: SRERewardConfig | None = None,
) -> tuple[float, list[str]]:
    if config is None:
        config = SRERewardConfig()

    reward = 0.0
    notes: list[str] = []

    if new_relevant_service:
        reward += config.new_relevant_service
        notes.append("queried a new relevant service")
    if queried_root_cause_service:
        reward += config.queried_root_cause
        notes.append("queried the root-cause service")
    if queried_deployment_history:
        reward += config.queried_deployment_history
        notes.append("checked deployment history")
    if queried_correct_diff:
        reward += config.queried_correct_diff
        notes.append("inspected the most relevant diff")
    if queried_heap_summary:
        reward += config.queried_heap_summary
        notes.append("confirmed heap growth evidence")
    if repeated_query:
        reward -= config.repeated_query_penalty
        notes.append("repeated identical query penalty")

    decayed_reward = reward * (config.step_decay_factor ** step_count)
    return clamp_score(decayed_reward), notes


def sre_diagnosis_reward(
    field_results: Iterable[tuple[str, bool, float]],
    step_count: int,
    config: SRERewardConfig | None = None,
) -> tuple[float, list[str]]:
    if config is None:
        config = SRERewardConfig()

    reward = 0.0
    notes: list[str] = []
    matched_any = False

    for field_name, matched, weight in field_results:
        if matched:
            reward += weight
            matched_any = True
            notes.append(f"correct {field_name}")

    if not matched_any:
        reward -= config.wrong_diagnosis_penalty
        notes.append("wrong diagnosis penalty")

    decayed_reward = reward * (config.step_decay_factor ** step_count)
    return clamp_score(decayed_reward), notes


def sre_remediation_reward(
    correct: bool,
    step_count: int,
    config: SRERewardConfig | None = None,
) -> tuple[float, list[str]]:
    if config is None:
        config = SRERewardConfig()

    if correct:
        decayed_reward = config.correct_remediation * (config.step_decay_factor ** step_count)
        return clamp_score(decayed_reward), ["correct remediation submitted"]

    return 0.0, ["remediation did not match an accepted fix"]

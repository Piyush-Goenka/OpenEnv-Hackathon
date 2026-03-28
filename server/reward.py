from __future__ import annotations

from typing import Iterable


def clamp_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def ci_efficiency_bonus(step_count: int) -> float:
    if step_count <= 1:
        return 0.10
    if step_count == 2:
        return 0.05
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
) -> tuple[float, list[str]]:
    reward = 0.0
    notes: list[str] = []

    if patch_applies:
        reward += 0.10
        notes.append("patch applied cleanly")
    if parses:
        reward += 0.10
        notes.append("code still parses structurally")
    if newly_green_checks:
        reward += 0.20 * newly_green_checks
        notes.append(f"{newly_green_checks} new check(s) went green")
    if all_green:
        reward += 0.40 + ci_efficiency_bonus(step_count)
        notes.append("all checks green")
    if repeated_patch:
        reward -= 0.10
        notes.append("repeated identical patch penalty")
    if broke_green_checks:
        reward -= 0.15
        notes.append("patch regressed a previously green check")

    return clamp_score(reward), notes


def sre_query_reward(
    *,
    repeated_query: bool,
    new_relevant_service: bool,
    queried_root_cause_service: bool,
    queried_deployment_history: bool,
    queried_correct_diff: bool,
    queried_heap_summary: bool,
) -> tuple[float, list[str]]:
    reward = 0.0
    notes: list[str] = []

    if new_relevant_service:
        reward += 0.05
        notes.append("queried a new relevant service")
    if queried_root_cause_service:
        reward += 0.15
        notes.append("queried the root-cause service")
    if queried_deployment_history:
        reward += 0.10
        notes.append("checked deployment history")
    if queried_correct_diff:
        reward += 0.10
        notes.append("inspected the most relevant diff")
    if queried_heap_summary:
        reward += 0.20
        notes.append("confirmed heap growth evidence")
    if repeated_query:
        reward -= 0.05
        notes.append("repeated identical query penalty")

    return clamp_score(reward), notes


def sre_diagnosis_reward(field_results: Iterable[tuple[str, bool, float]]) -> tuple[float, list[str]]:
    reward = 0.0
    notes: list[str] = []
    matched_any = False

    for field_name, matched, weight in field_results:
        if matched:
            reward += weight
            matched_any = True
            notes.append(f"correct {field_name}")

    if not matched_any:
        reward -= 0.10
        notes.append("wrong diagnosis penalty")

    return clamp_score(reward), notes


def sre_remediation_reward(correct: bool) -> tuple[float, list[str]]:
    if correct:
        return 0.35, ["correct remediation submitted"]
    return 0.0, ["remediation did not match an accepted fix"]

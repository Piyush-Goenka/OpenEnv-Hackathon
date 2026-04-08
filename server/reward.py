"""Reward shaping for DevReliability-Env.

Design principles (budget-based, industry-standard RL reward shaping):

1. Episode total is always in [0.0, 1.0] — capped at environment level.
2. Per-step rewards allow negatives [-1.0, 1.0] so penalties have real effect.
3. The bulk of reward (≥60%) comes from TASK COMPLETION, not intermediate steps.
4. Small shaping rewards guide exploration but cannot dominate.
5. Penalties are proportional and prevent reward hacking.
6. Step decay (γ=0.98) naturally rewards efficiency — faster solutions score higher.
7. Smooth efficiency bonus (exponential decay, not step function).
8. Anti-farming: delta-reward (diagnosis), one-shot (remediation), progress-gate
   (CI code quality), claimed-set (SRE queries).

References:
  - Ng et al. 1999 — potential-based reward shaping
  - Eschmann 2021 — reward function design in RL (completion >> shaping)
  - SWE-bench, WebArena, InterCode — comparable LLM-agent benchmarks

Budget allocation:
  CI track (optimal ≈ 0.93, per-step ∈ [-1, 1], episode ∈ [0, 1]):
    Completion (all checks green)     0.55
    Per-check progress                0.05 each (max ~0.20 for 4 checks)
    Code quality (applies + parses)   0.05 + 0.05 = 0.10 (gated on check progress)
    Efficiency bonus (smooth decay)   0.10 × 0.5^(step-1)
    Penalties: repeated patch -0.10, regression -0.15

  SRE track (optimal ≈ 0.86, per-step ∈ [-1, 1], episode ∈ [0, 1]):
    Diagnosis accuracy                up to 0.45 (delta-reward, JSON weights scaled)
    Remediation correctness           0.30 (one-shot, allows wrong→correct upgrade)
    Investigation quality             up to 0.15 (one-time signals)
    Penalties: repeated query -0.03, wrong diagnosis -0.05
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# Configs
# ---------------------------------------------------------------------------

@dataclass
class CIRewardConfig:
    # Code quality signals (small, per-submission)
    patch_applied: float = 0.05
    parses: float = 0.05
    # Progress: per newly-green check
    newly_green_check: float = 0.05
    # Completion: bulk reward for solving the task
    all_green_base: float = 0.55
    # Penalties
    repeated_patch_penalty: float = 0.10
    broke_green_check_penalty: float = 0.15
    # Efficiency: smooth bonus for fast completion (0.10 × 0.5^(step-1))
    efficiency_bonus_step1: float = 0.10
    # Decay: naturally penalizes slow solving
    step_decay_factor: float = 0.98


@dataclass
class SRERewardConfig:
    # Investigation signals (small, capped at ~0.15 total)
    new_relevant_service: float = 0.03
    queried_root_cause: float = 0.05
    queried_deployment_history: float = 0.02
    queried_correct_diff: float = 0.03
    queried_heap_summary: float = 0.02
    # Diagnosis: JSON field weights (sum to 1.0) are scaled by this factor
    diagnosis_weight_scale: float = 0.45
    # Remediation
    correct_remediation: float = 0.30
    # Penalties
    repeated_query_penalty: float = 0.03
    wrong_diagnosis_penalty: float = 0.05
    # Decay
    step_decay_factor: float = 0.98


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp_score(value: float) -> float:
    """Clamp a score to [0.0, 1.0], rounded to 3 decimal places."""
    return round(max(0.0, min(1.0, value)), 3)


def clamp_reward(value: float) -> float:
    """Clamp a per-step reward to [-1.0, 1.0], rounded to 3 decimal places.

    Unlike clamp_score, allows negative values so penalties have real effect.
    The episode-level accumulator in environment.py floors at 0.0.
    """
    return round(max(-1.0, min(1.0, value)), 3)


def ci_efficiency_bonus(step_count: int, config: CIRewardConfig) -> float:
    """Reward agents that solve the task in fewer steps.

    Uses smooth exponential decay so every additional step costs something,
    rather than a hard step-function cutoff.
    """
    if step_count <= 0:
        return config.efficiency_bonus_step1
    return round(config.efficiency_bonus_step1 * (0.5 ** (step_count - 1)), 4)


# ---------------------------------------------------------------------------
# CI Rewards
# ---------------------------------------------------------------------------

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
    """Compute reward for a single CI step (submit_patch action).

    Returns (clamped_reward, explanation_notes).
    """
    if config is None:
        config = CIRewardConfig()

    reward = 0.0
    notes: list[str] = []

    # Positive signals
    if patch_applies:
        reward += config.patch_applied
        notes.append("patch applied")
    if parses:
        reward += config.parses
        notes.append("code parses")
    if newly_green_checks:
        reward += config.newly_green_check * newly_green_checks
        notes.append(f"{newly_green_checks} new check(s) green")
    if all_green:
        reward += config.all_green_base + ci_efficiency_bonus(step_count, config)
        notes.append("all checks green — task complete")

    # Penalties
    if repeated_patch:
        reward -= config.repeated_patch_penalty
        notes.append("repeated patch penalty")
    if broke_green_checks:
        reward -= config.broke_green_check_penalty
        notes.append("regression penalty")

    decayed = reward * (config.step_decay_factor ** step_count)
    return clamp_reward(decayed), notes


# ---------------------------------------------------------------------------
# SRE Rewards
# ---------------------------------------------------------------------------

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
    """Reward for an investigation query.

    Small shaping rewards to guide exploration. Total investigation
    budget is ~0.15 across an episode.
    """
    if config is None:
        config = SRERewardConfig()

    reward = 0.0
    notes: list[str] = []

    if new_relevant_service:
        reward += config.new_relevant_service
        notes.append("queried relevant service")
    if queried_root_cause_service:
        reward += config.queried_root_cause
        notes.append("queried root-cause service")
    if queried_deployment_history:
        reward += config.queried_deployment_history
        notes.append("checked deployment history")
    if queried_correct_diff:
        reward += config.queried_correct_diff
        notes.append("inspected relevant diff")
    if queried_heap_summary:
        reward += config.queried_heap_summary
        notes.append("checked heap evidence")

    # Penalty
    if repeated_query:
        reward -= config.repeated_query_penalty
        notes.append("repeated query penalty")

    decayed = reward * (config.step_decay_factor ** step_count)
    return clamp_reward(decayed), notes


def sre_diagnosis_reward(
    field_results: Iterable[tuple[str, bool, float]],
    step_count: int,
    config: SRERewardConfig | None = None,
) -> tuple[float, list[str]]:
    """Reward for a diagnosis submission.

    Field weights from the scenario JSON (summing to 1.0) are scaled
    by ``config.diagnosis_weight_scale`` so diagnosis reward stays
    within its budget (~0.45).
    """
    if config is None:
        config = SRERewardConfig()

    reward = 0.0
    notes: list[str] = []
    matched_any = False

    for field_name, matched, weight in field_results:
        if matched:
            reward += weight * config.diagnosis_weight_scale
            matched_any = True
            notes.append(f"correct {field_name}")

    if not matched_any:
        reward -= config.wrong_diagnosis_penalty
        notes.append("wrong diagnosis penalty")

    decayed = reward * (config.step_decay_factor ** step_count)
    return clamp_reward(decayed), notes


def sre_remediation_reward(
    correct: bool,
    step_count: int,
    config: SRERewardConfig | None = None,
) -> tuple[float, list[str]]:
    """Reward for a remediation submission."""
    if config is None:
        config = SRERewardConfig()

    if correct:
        decayed = config.correct_remediation * (config.step_decay_factor ** step_count)
        return clamp_score(decayed), ["correct remediation"]

    return 0.0, ["incorrect remediation"]

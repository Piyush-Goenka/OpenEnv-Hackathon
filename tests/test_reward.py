from __future__ import annotations

import unittest

from server.reward import (
    CIRewardConfig,
    SRERewardConfig,
    ci_efficiency_bonus,
    ci_step_reward,
    clamp_reward,
    clamp_score,
    sre_diagnosis_reward,
    sre_query_reward,
    sre_remediation_reward,
)


class ClampScoreTest(unittest.TestCase):
    def test_clamp_within_range(self) -> None:
        self.assertEqual(clamp_score(0.5), 0.5)

    def test_clamp_negative(self) -> None:
        self.assertEqual(clamp_score(-0.3), 0.0)

    def test_clamp_above_one(self) -> None:
        self.assertEqual(clamp_score(1.5), 1.0)

    def test_clamp_zero(self) -> None:
        self.assertEqual(clamp_score(0.0), 0.0)

    def test_clamp_one(self) -> None:
        self.assertEqual(clamp_score(1.0), 1.0)


class ClampRewardTest(unittest.TestCase):
    def test_clamp_reward_positive(self) -> None:
        self.assertEqual(clamp_reward(0.5), 0.5)

    def test_clamp_reward_negative(self) -> None:
        self.assertEqual(clamp_reward(-0.3), -0.3)

    def test_clamp_reward_below_minus_one(self) -> None:
        self.assertEqual(clamp_reward(-2.0), -1.0)

    def test_clamp_reward_above_one(self) -> None:
        self.assertEqual(clamp_reward(1.5), 1.0)


class CIEfficiencyBonusTest(unittest.TestCase):
    def test_step1_bonus(self) -> None:
        self.assertEqual(ci_efficiency_bonus(1, CIRewardConfig()), 0.10)

    def test_step2_bonus(self) -> None:
        # Smooth decay: 0.10 * 0.5^1 = 0.05
        self.assertEqual(ci_efficiency_bonus(2, CIRewardConfig()), 0.05)

    def test_step3_decayed(self) -> None:
        # 0.10 * 0.5^2 = 0.025
        self.assertEqual(ci_efficiency_bonus(3, CIRewardConfig()), 0.025)

    def test_step5_small(self) -> None:
        # 0.10 * 0.5^4 = 0.00625 → rounded to 0.0063
        bonus = ci_efficiency_bonus(5, CIRewardConfig())
        self.assertGreater(bonus, 0.0)
        self.assertLess(bonus, 0.01)

    def test_step0_bonus(self) -> None:
        self.assertEqual(ci_efficiency_bonus(0, CIRewardConfig()), 0.10)


class CIStepRewardTest(unittest.TestCase):
    """Tests that CI rewards follow budget-based design.

    Budget: apply(0.05) + parse(0.05) + checks(0.05 each) + all_green(0.55) + efficiency(0.10)
    Optimal single-step solve (1 check, step 1) ≈ 0.80 * 0.98 = 0.784
    """

    def test_no_action_no_reward(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=False, parses=False, newly_green_checks=0,
            all_green=False, repeated_patch=False, broke_green_checks=False,
            step_count=1,
        )
        self.assertEqual(score, 0.0)
        self.assertEqual(notes, [])

    def test_patch_applies_and_parses(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=0,
            all_green=False, repeated_patch=False, broke_green_checks=False,
            step_count=0,
        )
        # 0.05 + 0.05 = 0.10, decay 0.98^0 = 1.0
        self.assertEqual(score, 0.1)
        self.assertIn("patch applied", notes)
        self.assertIn("code parses", notes)

    def test_single_check_all_green_step1(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=1,
            all_green=True, repeated_patch=False, broke_green_checks=False,
            step_count=1,
        )
        # (0.05 + 0.05 + 0.05 + 0.55 + 0.10) * 0.98 = 0.80 * 0.98 = 0.784
        self.assertEqual(score, 0.784)
        self.assertIn("all checks green — task complete", notes)

    def test_four_checks_all_green_step1(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=4,
            all_green=True, repeated_patch=False, broke_green_checks=False,
            step_count=1,
        )
        # (0.05 + 0.05 + 0.20 + 0.55 + 0.10) * 0.98 = 0.95 * 0.98 = 0.931
        self.assertEqual(score, 0.931)
        self.assertLessEqual(score, 1.0)

    def test_repeated_patch_penalty(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=0,
            all_green=False, repeated_patch=True, broke_green_checks=False,
            step_count=0,
        )
        # (0.05 + 0.05 - 0.10) = 0.0
        self.assertEqual(score, 0.0)
        self.assertIn("repeated patch penalty", notes)

    def test_regression_penalty(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=0,
            all_green=False, repeated_patch=False, broke_green_checks=True,
            step_count=0,
        )
        # (0.05 + 0.05 - 0.15) = -0.05 → allowed negative (clamp_reward)
        self.assertEqual(score, -0.05)
        self.assertIn("regression penalty", notes)

    def test_step_decay_reduces_reward(self) -> None:
        score_s0, _ = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=0,
            all_green=False, repeated_patch=False, broke_green_checks=False,
            step_count=0,
        )
        score_s5, _ = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=0,
            all_green=False, repeated_patch=False, broke_green_checks=False,
            step_count=5,
        )
        self.assertGreater(score_s0, score_s5)

    def test_multiple_newly_green_checks(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=3,
            all_green=False, repeated_patch=False, broke_green_checks=False,
            step_count=0,
        )
        # (0.05 + 0.05 + 0.15) = 0.25
        self.assertEqual(score, 0.25)

    def test_score_never_exceeds_one(self) -> None:
        score, _ = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=10,
            all_green=True, repeated_patch=False, broke_green_checks=False,
            step_count=0,
        )
        self.assertLessEqual(score, 1.0)

    def test_heavy_penalties_clamp_at_minus_one(self) -> None:
        config = CIRewardConfig(
            repeated_patch_penalty=2.0,
            broke_green_check_penalty=2.0,
        )
        score, _ = ci_step_reward(
            patch_applies=False, parses=False, newly_green_checks=0,
            all_green=False, repeated_patch=True, broke_green_checks=True,
            step_count=0, config=config,
        )
        # -4.0 clamped to -1.0
        self.assertEqual(score, -1.0)

    def test_optimal_episode_budget(self) -> None:
        """Verify optimal play scores under 1.0 per step."""
        score, _ = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=4,
            all_green=True, repeated_patch=False, broke_green_checks=False,
            step_count=1,
        )
        self.assertLessEqual(score, 1.0)
        self.assertGreater(score, 0.8)


class SREQueryRewardTest(unittest.TestCase):
    """Tests that SRE query rewards stay within investigation budget (~0.15)."""

    def test_no_signals(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=False, new_relevant_service=False,
            queried_root_cause_service=False, queried_deployment_history=False,
            queried_correct_diff=False, queried_heap_summary=False,
            step_count=0,
        )
        self.assertEqual(score, 0.0)
        self.assertEqual(notes, [])

    def test_new_relevant_service(self) -> None:
        score, _ = sre_query_reward(
            repeated_query=False, new_relevant_service=True,
            queried_root_cause_service=False, queried_deployment_history=False,
            queried_correct_diff=False, queried_heap_summary=False,
            step_count=0,
        )
        self.assertEqual(score, 0.03)

    def test_root_cause_service(self) -> None:
        score, _ = sre_query_reward(
            repeated_query=False, new_relevant_service=True,
            queried_root_cause_service=True, queried_deployment_history=False,
            queried_correct_diff=False, queried_heap_summary=False,
            step_count=0,
        )
        # 0.03 + 0.05 = 0.08
        self.assertEqual(score, 0.08)

    def test_all_investigation_signals(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=False, new_relevant_service=True,
            queried_root_cause_service=True, queried_deployment_history=True,
            queried_correct_diff=True, queried_heap_summary=True,
            step_count=0,
        )
        # 0.03 + 0.05 + 0.02 + 0.03 + 0.02 = 0.15
        self.assertEqual(score, 0.15)
        self.assertEqual(len(notes), 5)

    def test_investigation_budget_capped(self) -> None:
        """Maximum investigation reward should be ~0.15."""
        score, _ = sre_query_reward(
            repeated_query=False, new_relevant_service=True,
            queried_root_cause_service=True, queried_deployment_history=True,
            queried_correct_diff=True, queried_heap_summary=True,
            step_count=0,
        )
        self.assertLessEqual(score, 0.20)

    def test_repeated_query_penalty(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=True, new_relevant_service=False,
            queried_root_cause_service=False, queried_deployment_history=False,
            queried_correct_diff=False, queried_heap_summary=False,
            step_count=0,
        )
        self.assertEqual(score, -0.03)  # real negative penalty
        self.assertIn("repeated query penalty", notes)

    def test_step_decay(self) -> None:
        kwargs = dict(
            repeated_query=False, new_relevant_service=True,
            queried_root_cause_service=True, queried_deployment_history=False,
            queried_correct_diff=False, queried_heap_summary=False,
        )
        s0, _ = sre_query_reward(**kwargs, step_count=0)
        s5, _ = sre_query_reward(**kwargs, step_count=5)
        self.assertGreater(s0, s5)


class SREDiagnosisRewardTest(unittest.TestCase):
    """Tests that diagnosis rewards are scaled by diagnosis_weight_scale (0.45).

    JSON field weights sum to 1.0; after scaling, max diagnosis reward = 0.45.
    """

    def test_all_correct(self) -> None:
        fields = [
            ("root_cause_service", True, 0.4),
            ("error_type", True, 0.3),
            ("affected_line", True, 0.3),
        ]
        score, notes = sre_diagnosis_reward(fields, step_count=0)
        # 1.0 * 0.45 = 0.45
        self.assertEqual(score, 0.45)
        self.assertEqual(len(notes), 3)

    def test_partial_match(self) -> None:
        fields = [
            ("root_cause_service", True, 0.4),
            ("error_type", False, 0.3),
            ("affected_line", True, 0.3),
        ]
        score, _ = sre_diagnosis_reward(fields, step_count=0)
        # (0.4 + 0.3) * 0.45 = 0.7 * 0.45 = 0.315
        self.assertEqual(score, 0.315)

    def test_no_match(self) -> None:
        fields = [
            ("root_cause_service", False, 0.4),
            ("error_type", False, 0.3),
        ]
        score, notes = sre_diagnosis_reward(fields, step_count=0)
        self.assertEqual(score, -0.05)  # real negative penalty
        self.assertIn("wrong diagnosis penalty", notes)

    def test_empty_fields(self) -> None:
        score, notes = sre_diagnosis_reward([], step_count=0)
        self.assertEqual(score, -0.05)  # real negative penalty
        self.assertIn("wrong diagnosis penalty", notes)

    def test_max_diagnosis_within_budget(self) -> None:
        """Perfect diagnosis should give exactly 0.45, not 1.0."""
        fields = [("a", True, 0.5), ("b", True, 0.5)]
        score, _ = sre_diagnosis_reward(fields, step_count=0)
        self.assertEqual(score, 0.45)
        self.assertLessEqual(score, 0.50)

    def test_decay_applied(self) -> None:
        fields = [("root_cause_service", True, 0.5)]
        s0, _ = sre_diagnosis_reward(fields, step_count=0)
        s3, _ = sre_diagnosis_reward(fields, step_count=3)
        self.assertGreater(s0, s3)


class SRERemediationRewardTest(unittest.TestCase):
    def test_correct(self) -> None:
        score, notes = sre_remediation_reward(True, step_count=0)
        self.assertEqual(score, 0.30)
        self.assertIn("correct remediation", notes)

    def test_incorrect(self) -> None:
        score, notes = sre_remediation_reward(False, step_count=0)
        self.assertEqual(score, 0.0)
        self.assertIn("incorrect remediation", notes)

    def test_decay(self) -> None:
        s0, _ = sre_remediation_reward(True, step_count=0)
        s5, _ = sre_remediation_reward(True, step_count=5)
        self.assertGreater(s0, s5)


class SREEpisodeBudgetTest(unittest.TestCase):
    """End-to-end budget verification for SRE optimal episode."""

    def test_optimal_sre_episode_under_one(self) -> None:
        """Simulate optimal play: investigate → diagnose → remediate.

        Investigation (step 0):  0.15
        Diagnosis (step 1):      0.45 * 0.98 = 0.441
        Remediation (step 2):    0.30 * 0.98^2 = 0.288
        Total: ~0.879 — well under 1.0
        """
        inv, _ = sre_query_reward(
            repeated_query=False, new_relevant_service=True,
            queried_root_cause_service=True, queried_deployment_history=True,
            queried_correct_diff=True, queried_heap_summary=True,
            step_count=0,
        )
        diag, _ = sre_diagnosis_reward(
            [("a", True, 0.5), ("b", True, 0.5)], step_count=1,
        )
        rem, _ = sre_remediation_reward(True, step_count=2)

        total = inv + diag + rem
        self.assertLessEqual(total, 1.0)
        self.assertGreater(total, 0.7)


class CIEpisodeBudgetTest(unittest.TestCase):
    """End-to-end budget verification for CI optimal episode."""

    def test_optimal_ci_single_step_under_one(self) -> None:
        score, _ = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=4,
            all_green=True, repeated_patch=False, broke_green_checks=False,
            step_count=1,
        )
        self.assertLessEqual(score, 1.0)

    def test_two_step_ci_accumulated_under_one(self) -> None:
        """Step 1: partial fix (2 checks). Step 2: complete fix (2 more + all green)."""
        s1, _ = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=2,
            all_green=False, repeated_patch=False, broke_green_checks=False,
            step_count=1,
        )
        s2, _ = ci_step_reward(
            patch_applies=True, parses=True, newly_green_checks=2,
            all_green=True, repeated_patch=False, broke_green_checks=False,
            step_count=2,
        )
        total = s1 + s2
        self.assertLessEqual(total, 1.0)

    def test_five_garbage_patches_low_score(self) -> None:
        """Submitting patches that parse but never fix anything should score low.

        In the real engine, patch_applies and parses are gated on has_progress,
        so we simulate that here with False for no-progress steps.
        """
        total = 0.0
        for step in range(1, 6):
            s, _ = ci_step_reward(
                patch_applies=False, parses=False, newly_green_checks=0,
                all_green=False, repeated_patch=(step > 1), broke_green_checks=False,
                step_count=step,
            )
            total += s
        # All steps: 0 positive signals. Steps 2-5: repeated_patch penalty (-0.10 each)
        self.assertLess(total, 0.0)
        # Environment would floor this at 0.0


class RewardConfigDefaultsTest(unittest.TestCase):
    def test_ci_config_defaults(self) -> None:
        c = CIRewardConfig()
        self.assertEqual(c.patch_applied, 0.05)
        self.assertEqual(c.parses, 0.05)
        self.assertEqual(c.newly_green_check, 0.05)
        self.assertEqual(c.all_green_base, 0.55)
        self.assertEqual(c.step_decay_factor, 0.98)

    def test_sre_config_defaults(self) -> None:
        c = SRERewardConfig()
        self.assertEqual(c.new_relevant_service, 0.03)
        self.assertEqual(c.queried_root_cause, 0.05)
        self.assertEqual(c.diagnosis_weight_scale, 0.45)
        self.assertEqual(c.correct_remediation, 0.30)
        self.assertEqual(c.step_decay_factor, 0.98)

    def test_ci_config_override(self) -> None:
        c = CIRewardConfig(patch_applied=0.5, step_decay_factor=0.9)
        self.assertEqual(c.patch_applied, 0.5)
        self.assertEqual(c.step_decay_factor, 0.9)

    def test_sre_config_override(self) -> None:
        c = SRERewardConfig(correct_remediation=0.5)
        self.assertEqual(c.correct_remediation, 0.5)

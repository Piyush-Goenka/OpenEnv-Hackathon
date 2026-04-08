from __future__ import annotations

import unittest

from server.reward import (
    CIRewardConfig,
    SRERewardConfig,
    ci_efficiency_bonus,
    ci_step_reward,
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


class CIEfficiencyBonusTest(unittest.TestCase):
    def test_step1_bonus(self) -> None:
        config = CIRewardConfig()
        self.assertEqual(ci_efficiency_bonus(1, config), 0.10)

    def test_step2_bonus(self) -> None:
        config = CIRewardConfig()
        self.assertEqual(ci_efficiency_bonus(2, config), 0.05)

    def test_step3_no_bonus(self) -> None:
        config = CIRewardConfig()
        self.assertEqual(ci_efficiency_bonus(3, config), 0.0)

    def test_step0_bonus(self) -> None:
        config = CIRewardConfig()
        self.assertEqual(ci_efficiency_bonus(0, config), 0.10)


class CIStepRewardTest(unittest.TestCase):
    def test_empty_patch_no_reward(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=False,
            parses=False,
            newly_green_checks=0,
            all_green=False,
            repeated_patch=False,
            broke_green_checks=False,
            step_count=1,
        )
        self.assertEqual(score, 0.0)
        self.assertEqual(notes, [])

    def test_patch_applies_and_parses(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=0,
            all_green=False,
            repeated_patch=False,
            broke_green_checks=False,
            step_count=0,
        )
        # 0.10 + 0.10 = 0.20, decay 0.95^0 = 1.0
        self.assertEqual(score, 0.2)
        self.assertIn("patch applied cleanly", notes)
        self.assertIn("code still parses structurally", notes)

    def test_all_green_at_step1(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=1,
            all_green=True,
            repeated_patch=False,
            broke_green_checks=False,
            step_count=1,
        )
        # (0.10 + 0.10 + 0.20 + 0.40 + 0.10) * 0.95 = 0.90 * 0.95 = 0.855
        self.assertEqual(score, 0.855)
        self.assertIn("all checks green", notes)

    def test_repeated_patch_penalty(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=0,
            all_green=False,
            repeated_patch=True,
            broke_green_checks=False,
            step_count=0,
        )
        # (0.10 + 0.10 - 0.10) * 1.0 = 0.10
        self.assertEqual(score, 0.1)
        self.assertIn("repeated identical patch penalty", notes)

    def test_broke_green_penalty(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=0,
            all_green=False,
            repeated_patch=False,
            broke_green_checks=True,
            step_count=0,
        )
        # (0.10 + 0.10 - 0.15) * 1.0 = 0.05
        self.assertEqual(score, 0.05)
        self.assertIn("patch regressed a previously green check", notes)

    def test_step_decay(self) -> None:
        score_step0, _ = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=0,
            all_green=False,
            repeated_patch=False,
            broke_green_checks=False,
            step_count=0,
        )
        score_step5, _ = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=0,
            all_green=False,
            repeated_patch=False,
            broke_green_checks=False,
            step_count=5,
        )
        self.assertGreater(score_step0, score_step5)

    def test_multiple_newly_green_checks(self) -> None:
        score, notes = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=3,
            all_green=False,
            repeated_patch=False,
            broke_green_checks=False,
            step_count=0,
        )
        # (0.10 + 0.10 + 0.60) * 1.0 = 0.80
        self.assertEqual(score, 0.8)
        self.assertIn("3 new check(s) went green", notes)

    def test_score_clamped_at_one(self) -> None:
        score, _ = ci_step_reward(
            patch_applies=True,
            parses=True,
            newly_green_checks=5,
            all_green=True,
            repeated_patch=False,
            broke_green_checks=False,
            step_count=0,
        )
        self.assertLessEqual(score, 1.0)

    def test_heavy_penalty_clamped_at_zero(self) -> None:
        config = CIRewardConfig(
            repeated_patch_penalty=2.0,
            broke_green_check_penalty=2.0,
        )
        score, _ = ci_step_reward(
            patch_applies=False,
            parses=False,
            newly_green_checks=0,
            all_green=False,
            repeated_patch=True,
            broke_green_checks=True,
            step_count=0,
            config=config,
        )
        self.assertEqual(score, 0.0)


class SREQueryRewardTest(unittest.TestCase):
    def test_no_signals(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=False,
            new_relevant_service=False,
            queried_root_cause_service=False,
            queried_deployment_history=False,
            queried_correct_diff=False,
            queried_heap_summary=False,
            step_count=0,
        )
        self.assertEqual(score, 0.0)
        self.assertEqual(notes, [])

    def test_new_relevant_service(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=False,
            new_relevant_service=True,
            queried_root_cause_service=False,
            queried_deployment_history=False,
            queried_correct_diff=False,
            queried_heap_summary=False,
            step_count=0,
        )
        self.assertEqual(score, 0.05)
        self.assertIn("queried a new relevant service", notes)

    def test_root_cause_service(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=False,
            new_relevant_service=True,
            queried_root_cause_service=True,
            queried_deployment_history=False,
            queried_correct_diff=False,
            queried_heap_summary=False,
            step_count=0,
        )
        # 0.05 + 0.15 = 0.20
        self.assertEqual(score, 0.2)

    def test_repeated_query_penalty(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=True,
            new_relevant_service=False,
            queried_root_cause_service=False,
            queried_deployment_history=False,
            queried_correct_diff=False,
            queried_heap_summary=False,
            step_count=0,
        )
        # -0.05 clamped to 0.0
        self.assertEqual(score, 0.0)
        self.assertIn("repeated identical query penalty", notes)

    def test_all_signals(self) -> None:
        score, notes = sre_query_reward(
            repeated_query=False,
            new_relevant_service=True,
            queried_root_cause_service=True,
            queried_deployment_history=True,
            queried_correct_diff=True,
            queried_heap_summary=True,
            step_count=0,
        )
        # 0.05 + 0.15 + 0.10 + 0.10 + 0.20 = 0.60
        self.assertEqual(score, 0.6)
        self.assertEqual(len(notes), 5)

    def test_step_decay(self) -> None:
        score_s0, _ = sre_query_reward(
            repeated_query=False,
            new_relevant_service=True,
            queried_root_cause_service=True,
            queried_deployment_history=False,
            queried_correct_diff=False,
            queried_heap_summary=False,
            step_count=0,
        )
        score_s5, _ = sre_query_reward(
            repeated_query=False,
            new_relevant_service=True,
            queried_root_cause_service=True,
            queried_deployment_history=False,
            queried_correct_diff=False,
            queried_heap_summary=False,
            step_count=5,
        )
        self.assertGreater(score_s0, score_s5)


class SREDiagnosisRewardTest(unittest.TestCase):
    def test_all_correct(self) -> None:
        fields = [
            ("root_cause_service", True, 0.4),
            ("error_type", True, 0.3),
            ("affected_line", True, 0.3),
        ]
        score, notes = sre_diagnosis_reward(fields, step_count=0)
        self.assertEqual(score, 1.0)
        self.assertEqual(len(notes), 3)

    def test_partial_match(self) -> None:
        fields = [
            ("root_cause_service", True, 0.4),
            ("error_type", False, 0.3),
            ("affected_line", True, 0.3),
        ]
        score, notes = sre_diagnosis_reward(fields, step_count=0)
        self.assertEqual(score, 0.7)

    def test_no_match(self) -> None:
        fields = [
            ("root_cause_service", False, 0.4),
            ("error_type", False, 0.3),
        ]
        score, notes = sre_diagnosis_reward(fields, step_count=0)
        # -0.10 clamped to 0.0
        self.assertEqual(score, 0.0)
        self.assertIn("wrong diagnosis penalty", notes)

    def test_empty_fields(self) -> None:
        score, notes = sre_diagnosis_reward([], step_count=0)
        self.assertEqual(score, 0.0)
        self.assertIn("wrong diagnosis penalty", notes)

    def test_decay_applied(self) -> None:
        fields = [("root_cause_service", True, 0.5)]
        score_s0, _ = sre_diagnosis_reward(fields, step_count=0)
        score_s3, _ = sre_diagnosis_reward(fields, step_count=3)
        self.assertGreater(score_s0, score_s3)


class SRERemediationRewardTest(unittest.TestCase):
    def test_correct(self) -> None:
        score, notes = sre_remediation_reward(True, step_count=0)
        self.assertEqual(score, 0.35)
        self.assertIn("correct remediation submitted", notes)

    def test_incorrect(self) -> None:
        score, notes = sre_remediation_reward(False, step_count=0)
        self.assertEqual(score, 0.0)
        self.assertIn("remediation did not match an accepted fix", notes)

    def test_decay(self) -> None:
        score_s0, _ = sre_remediation_reward(True, step_count=0)
        score_s5, _ = sre_remediation_reward(True, step_count=5)
        self.assertGreater(score_s0, score_s5)


class RewardConfigDefaultsTest(unittest.TestCase):
    def test_ci_config_defaults(self) -> None:
        config = CIRewardConfig()
        self.assertEqual(config.patch_applied, 0.10)
        self.assertEqual(config.parses, 0.10)
        self.assertEqual(config.newly_green_check, 0.20)
        self.assertEqual(config.all_green_base, 0.40)
        self.assertEqual(config.step_decay_factor, 0.95)

    def test_sre_config_defaults(self) -> None:
        config = SRERewardConfig()
        self.assertEqual(config.new_relevant_service, 0.05)
        self.assertEqual(config.queried_root_cause, 0.15)
        self.assertEqual(config.correct_remediation, 0.35)
        self.assertEqual(config.step_decay_factor, 0.95)

    def test_ci_config_override(self) -> None:
        config = CIRewardConfig(patch_applied=0.5, step_decay_factor=0.9)
        self.assertEqual(config.patch_applied, 0.5)
        self.assertEqual(config.step_decay_factor, 0.9)

    def test_sre_config_override(self) -> None:
        config = SRERewardConfig(correct_remediation=0.5)
        self.assertEqual(config.correct_remediation, 0.5)

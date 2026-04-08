from __future__ import annotations

import unittest

from models import DevReliabilityAction, DevReliabilityObservation, DevReliabilityState
from server.environment import DevReliabilityEnvironment


class EnvironmentResetCITest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = DevReliabilityEnvironment()

    def test_reset_returns_observation(self) -> None:
        obs = self.env.reset(seed=42, task_id="ci_easy")
        self.assertIsInstance(obs, DevReliabilityObservation)
        self.assertFalse(obs.done)
        self.assertEqual(obs.task_id, "ci_easy")
        self.assertEqual(obs.track, "ci")
        self.assertEqual(obs.difficulty, "easy")

    def test_reset_sets_state(self) -> None:
        self.env.reset(seed=42, task_id="ci_easy")
        state = self.env.state
        self.assertIsInstance(state, DevReliabilityState)
        self.assertEqual(state.step_count, 0)
        self.assertEqual(state.track, "ci")
        self.assertEqual(state.task_id, "ci_easy")
        self.assertFalse(state.done)
        self.assertEqual(state.final_score, 0.0)
        self.assertTrue(len(state.current_files) > 0)

    def test_reset_provides_ci_output(self) -> None:
        obs = self.env.reset(seed=42, task_id="ci_easy")
        self.assertIsNotNone(obs.ci_output)

    def test_reset_provides_available_actions(self) -> None:
        obs = self.env.reset(seed=42, task_id="ci_easy")
        self.assertIn("read_file", obs.available_actions)
        self.assertIn("submit_patch", obs.available_actions)

    def test_reset_provides_context(self) -> None:
        obs = self.env.reset(seed=42, task_id="ci_easy")
        self.assertIn("scenario_id", obs.context)
        self.assertIn("relevant_files", obs.context)

    def test_reset_with_episode_id(self) -> None:
        self.env.reset(seed=42, task_id="ci_easy", episode_id="my-ep-1")
        self.assertEqual(self.env.state.episode_id, "my-ep-1")

    def test_reset_generates_episode_id(self) -> None:
        self.env.reset(seed=42, task_id="ci_easy")
        self.assertIsNotNone(self.env.state.episode_id)
        self.assertTrue(len(self.env.state.episode_id) > 0)


class EnvironmentResetSRETest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = DevReliabilityEnvironment()

    def test_reset_sre_easy(self) -> None:
        obs = self.env.reset(seed=42, task_id="sre_easy")
        self.assertEqual(obs.track, "sre")
        self.assertEqual(obs.difficulty, "easy")
        self.assertIn("submit_diagnosis", obs.available_actions)

    def test_reset_sre_state(self) -> None:
        self.env.reset(seed=42, task_id="sre_easy")
        state = self.env.state
        self.assertEqual(state.track, "sre")
        self.assertEqual(state.queries_made, [])
        self.assertEqual(state.services_investigated, [])
        self.assertFalse(state.diagnosis_submitted)

    def test_reset_sre_context(self) -> None:
        obs = self.env.reset(seed=42, task_id="sre_easy")
        self.assertIn("alert", obs.context)
        self.assertIn("service_catalog", obs.context)


class EnvironmentStepCITest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = DevReliabilityEnvironment()
        self.env.reset(seed=42, task_id="ci_easy")

    def test_step_increments_count(self) -> None:
        action = DevReliabilityAction(action_type="read_file", payload={"path": "src/utils.py"})
        self.env.step(action)
        self.assertEqual(self.env.state.step_count, 1)

    def test_step_read_file(self) -> None:
        files = list(self.env.state.current_files.keys())
        action = DevReliabilityAction(action_type="read_file", payload={"path": files[0]})
        obs = self.env.step(action)
        self.assertIsNotNone(obs.tool_results)
        self.assertFalse(obs.done)

    def test_step_run_check(self) -> None:
        action = DevReliabilityAction(action_type="run_check", payload={"check": "lint"})
        obs = self.env.step(action)
        self.assertIsNotNone(obs.ci_output)

    def test_step_submit_patch_accumulates_score(self) -> None:
        files = list(self.env.state.current_files.keys())
        code = self.env.state.current_files[files[0]]
        action = DevReliabilityAction(
            action_type="submit_patch", payload={"patch": code, "file": files[0]}
        )
        obs = self.env.step(action)
        self.assertGreaterEqual(self.env.state.final_score, 0.0)

    def test_multiple_steps(self) -> None:
        files = list(self.env.state.current_files.keys())
        a1 = DevReliabilityAction(action_type="read_file", payload={"path": files[0]})
        a2 = DevReliabilityAction(action_type="run_check", payload={"check": "lint"})
        self.env.step(a1)
        self.env.step(a2)
        self.assertEqual(self.env.state.step_count, 2)


class EnvironmentStepSRETest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = DevReliabilityEnvironment()
        self.env.reset(seed=42, task_id="sre_easy")

    def test_step_get_logs(self) -> None:
        services = self.env.state  # state has empty queries initially
        catalog = self.env._runtime.scenario.get("service_catalog", [])
        action = DevReliabilityAction(
            action_type="get_logs", payload={"service": catalog[0]}
        )
        obs = self.env.step(action)
        self.assertIsNotNone(obs.tool_results)
        self.assertEqual(self.env.state.step_count, 1)
        self.assertTrue(len(self.env.state.queries_made) > 0)

    def test_step_tracks_services(self) -> None:
        catalog = self.env._runtime.scenario.get("service_catalog", [])
        action = DevReliabilityAction(
            action_type="get_logs", payload={"service": catalog[0]}
        )
        self.env.step(action)
        self.assertIn(catalog[0], self.env.state.services_investigated)

    def test_step_diagnosis(self) -> None:
        action = DevReliabilityAction(
            action_type="submit_diagnosis",
            payload={"root_cause_service": "fake", "error_type": "fake"},
        )
        obs = self.env.step(action)
        self.assertTrue(self.env.state.diagnosis_submitted)


class EnvironmentStepBeforeResetTest(unittest.TestCase):
    def test_step_before_reset_raises(self) -> None:
        env = DevReliabilityEnvironment()
        action = DevReliabilityAction(action_type="read_file", payload={"path": "x.py"})
        with self.assertRaises(RuntimeError):
            env.step(action)


class EnvironmentMaxStepsTest(unittest.TestCase):
    def test_done_at_max_steps(self) -> None:
        env = DevReliabilityEnvironment()
        env.reset(seed=42, task_id="ci_easy")
        max_steps = env.state.max_steps
        action = DevReliabilityAction(action_type="read_file", payload={"path": "src/utils.py"})
        obs = None
        for _ in range(max_steps):
            obs = env.step(action)
        self.assertTrue(obs.done)
        self.assertIn("Maximum steps reached", obs.feedback)


class EnvironmentScoreAccumulationTest(unittest.TestCase):
    def test_score_accumulates_across_steps(self) -> None:
        env = DevReliabilityEnvironment()
        env.reset(seed=42, task_id="ci_easy")
        files = list(env.state.current_files.keys())
        code = env.state.current_files[files[0]]
        # Submit a valid patch
        a1 = DevReliabilityAction(
            action_type="submit_patch", payload={"patch": code, "file": files[0]}
        )
        env.step(a1)
        score1 = env.state.final_score

        # Submit again (different code)
        a2 = DevReliabilityAction(
            action_type="submit_patch", payload={"patch": "x = 1\n", "file": files[0]}
        )
        env.step(a2)
        score2 = env.state.final_score
        # Score should have changed (accumulated)
        self.assertNotEqual(score1, 0.0)
        self.assertGreaterEqual(score2, 0.0)


class EnvironmentResetClearsStateTest(unittest.TestCase):
    def test_reset_clears_previous_episode(self) -> None:
        env = DevReliabilityEnvironment()
        env.reset(seed=42, task_id="ci_easy")
        files = list(env.state.current_files.keys())
        action = DevReliabilityAction(
            action_type="submit_patch",
            payload={"patch": env.state.current_files[files[0]], "file": files[0]},
        )
        env.step(action)
        old_score = env.state.final_score

        # Reset should clear everything
        env.reset(seed=42, task_id="ci_easy")
        self.assertEqual(env.state.step_count, 0)
        self.assertEqual(env.state.final_score, 0.0)
        self.assertFalse(env.state.done)


class EnvironmentAllTasksTest(unittest.TestCase):
    """Smoke test: reset works for every registered task."""

    def test_reset_ci_easy(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=1, task_id="ci_easy")
        self.assertEqual(obs.track, "ci")

    def test_reset_ci_medium(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=1, task_id="ci_medium")
        self.assertEqual(obs.track, "ci")

    def test_reset_ci_hard(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=1, task_id="ci_hard")
        self.assertEqual(obs.track, "ci")

    def test_reset_sre_easy(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=1, task_id="sre_easy")
        self.assertEqual(obs.track, "sre")

    def test_reset_sre_medium(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=1, task_id="sre_medium")
        self.assertEqual(obs.track, "sre")

    def test_reset_sre_hard(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=1, task_id="sre_hard")
        self.assertEqual(obs.track, "sre")


class EnvironmentBuildContextTest(unittest.TestCase):
    def test_ci_context_has_pr_diff(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=42, task_id="ci_easy")
        self.assertIn("pr_diff", obs.context)

    def test_sre_context_has_alert(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=42, task_id="sre_easy")
        self.assertIn("alert", obs.context)
        self.assertIn("service_catalog", obs.context)

    def test_sre_medium_context_has_deployment_ids(self) -> None:
        env = DevReliabilityEnvironment()
        obs = env.reset(seed=42, task_id="sre_medium")
        self.assertIn("deployment_ids", obs.context)

from __future__ import annotations

import unittest

from server.sre_engine import SREEngine, SREEpisodeRuntime
from tasks import get_task


def _make_scenario(
    *,
    logs: dict | None = None,
    metrics: dict | None = None,
    deployment_history: list | None = None,
    diffs: dict | None = None,
    heap_summaries: dict | None = None,
    relevant_services: list | None = None,
    query_rewards: dict | None = None,
    diagnosis_fields: dict | None = None,
    accepted_remediations: list | None = None,
) -> dict:
    return {
        "scenario_id": "test_sre_scenario",
        "task_id": "sre_easy",
        "title": "Test SRE",
        "description": "Test scenario",
        "alert": "Error rate alert",
        "initial_log_excerpt": "excerpt",
        "service_catalog": ["svc-a", "svc-b", "svc-c"],
        "logs": logs if logs is not None else {
            "svc-a": ["[svc-a] ERROR something broke"],
            "svc-b": ["[svc-b] INFO all ok"],
        },
        "metrics": metrics if metrics is not None else {
            "svc-a": {
                "latency_p99": {"timestamps": ["14:00"], "values": [500]}
            }
        },
        "deployment_history": deployment_history if deployment_history is not None else [
            {"deploy_id": "deploy-001", "timestamp": "2026-04-01T10:00:00Z", "summary": "deploy one"}
        ],
        "diffs": diffs if diffs is not None else {"deploy-001": "diff --git a/f.py\n+x = 1"},
        "heap_summaries": heap_summaries if heap_summaries is not None else {"14:30": {"top_allocators": ["Foo"]}},
        "relevant_services": relevant_services if relevant_services is not None else ["svc-a"],
        "query_rewards": query_rewards if query_rewards is not None else {
            "root_cause_service": "svc-a",
            "correct_diff_id": "deploy-001",
            "heap_summary_timestamp": "14:30",
        },
        "diagnosis_fields": diagnosis_fields if diagnosis_fields is not None else {
            "root_cause_service": {"value": "svc-a", "weight": 0.5, "match_mode": "equals"},
            "error_type": {"value": "something broke", "weight": 0.5, "match_mode": "contains"},
        },
        "accepted_remediations": accepted_remediations if accepted_remediations is not None else ["restart svc-a", "rollback deploy-001"],
    }


def _make_runtime(scenario: dict | None = None) -> SREEpisodeRuntime:
    return SREEpisodeRuntime(scenario=scenario or _make_scenario())


class SREEngineQueryLogsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SREEngine()

    def test_get_logs_existing_service(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_logs", {"service": "svc-a"}, 1)
        self.assertIn("ERROR something broke", result.tool_results or "")
        self.assertFalse(result.done)

    def test_get_logs_unknown_service(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_logs", {"service": "unknown"}, 1)
        self.assertIn("Unknown service", result.tool_results or "")

    def test_get_logs_tracks_service(self) -> None:
        runtime = _make_runtime()
        self.engine.handle_action(runtime, "get_logs", {"service": "svc-a"}, 1)
        self.assertIn("svc-a", runtime.services_investigated)


class SREEngineQueryMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SREEngine()

    def test_get_metrics_existing(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime, "get_metrics", {"service": "svc-a", "metric": "latency_p99"}, 1
        )
        self.assertIn("500", result.tool_results or "")

    def test_get_metrics_missing_metric(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime, "get_metrics", {"service": "svc-a", "metric": "cpu"}, 1
        )
        self.assertIn("No metric", result.tool_results or "")


class SREEngineQueryDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SREEngine()

    def test_get_diff_existing(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_diff", {"deploy_id": "deploy-001"}, 1)
        self.assertIn("x = 1", result.tool_results or "")

    def test_get_diff_unknown(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_diff", {"deploy_id": "nope"}, 1)
        self.assertIn("Unknown deploy_id", result.tool_results or "")

    def test_correct_diff_gives_reward(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_diff", {"deploy_id": "deploy-001"}, 1)
        self.assertGreater(result.reward, 0.0)


class SREEngineQueryHeapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SREEngine()

    def test_get_heap_summary_existing(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_heap_summary", {"timestamp": "14:30"}, 1)
        self.assertIn("Foo", result.tool_results or "")

    def test_get_heap_summary_unknown(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_heap_summary", {"timestamp": "99:99"}, 1)
        self.assertIn("Unknown heap summary", result.tool_results or "")

    def test_correct_heap_gives_reward(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(runtime, "get_heap_summary", {"timestamp": "14:30"}, 1)
        self.assertGreater(result.reward, 0.0)


class SREEngineDeploymentHistoryTest(unittest.TestCase):
    def test_get_deployment_history(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        result = engine.handle_action(runtime, "get_deployment_history", {}, 1)
        self.assertIn("deploy-001", result.tool_results or "")
        self.assertGreater(result.reward, 0.0)

    def test_empty_deployment_history(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime(_make_scenario(deployment_history=[]))
        result = engine.handle_action(runtime, "get_deployment_history", {}, 1)
        self.assertIn("No deployment history", result.tool_results or "")


class SREEngineRepeatedQueryTest(unittest.TestCase):
    def test_repeated_query_penalty(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        engine.handle_action(runtime, "get_logs", {"service": "svc-b"}, 1)
        r2 = engine.handle_action(runtime, "get_logs", {"service": "svc-b"}, 2)
        self.assertIn("repeated query penalty", r2.feedback)

    def test_different_queries_no_penalty(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        engine.handle_action(runtime, "get_logs", {"service": "svc-a"}, 1)
        r2 = engine.handle_action(runtime, "get_logs", {"service": "svc-b"}, 2)
        self.assertNotIn("repeated", r2.feedback)


class SREEngineRelevantServiceRewardTest(unittest.TestCase):
    def test_new_relevant_service_reward(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        result = engine.handle_action(runtime, "get_logs", {"service": "svc-a"}, 1)
        self.assertIn("queried relevant service", result.feedback)

    def test_irrelevant_service_no_bonus(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        result = engine.handle_action(runtime, "get_logs", {"service": "svc-b"}, 1)
        self.assertNotIn("queried relevant service", result.feedback)

    def test_root_cause_service_reward(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        result = engine.handle_action(runtime, "get_logs", {"service": "svc-a"}, 1)
        self.assertIn("queried root-cause service", result.feedback)


class SREEngineDiagnosisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SREEngine()

    def test_correct_diagnosis(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime,
            "submit_diagnosis",
            {"root_cause_service": "svc-a", "error_type": "something broke"},
            1,
        )
        self.assertTrue(runtime.diagnosis_correct)
        self.assertGreater(result.reward, 0.0)

    def test_partial_diagnosis(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime,
            "submit_diagnosis",
            {"root_cause_service": "svc-a", "error_type": "wrong"},
            1,
        )
        self.assertFalse(runtime.diagnosis_correct)
        self.assertGreater(result.reward, 0.0)  # partial match still gets weight

    def test_wrong_diagnosis(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime,
            "submit_diagnosis",
            {"root_cause_service": "wrong", "error_type": "wrong"},
            1,
        )
        self.assertFalse(runtime.diagnosis_correct)
        self.assertEqual(result.reward, -0.05)  # real negative penalty

    def test_contains_match_mode(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime,
            "submit_diagnosis",
            {"root_cause_service": "svc-a", "error_type": "it was something broke in prod"},
            1,
        )
        self.assertTrue(runtime.diagnosis_correct)

    def test_diagnosis_without_remediation_completes_easy_task(self) -> None:
        scenario = _make_scenario(accepted_remediations=[])
        runtime = _make_runtime(scenario)
        result = self.engine.handle_action(
            runtime,
            "submit_diagnosis",
            {"root_cause_service": "svc-a", "error_type": "something broke"},
            1,
        )
        self.assertTrue(result.done)

    def test_correct_diagnosis_repeated_gives_no_reward(self) -> None:
        """Delta-reward: identical re-submission must not earn reward (farming prevention)."""
        runtime = _make_runtime()
        payload = {"root_cause_service": "svc-a", "error_type": "something broke"}
        r1 = self.engine.handle_action(runtime, "submit_diagnosis", payload, 1)
        r2 = self.engine.handle_action(runtime, "submit_diagnosis", payload, 2)
        self.assertGreater(r1.reward, 0.0)
        self.assertEqual(r2.reward, 0.0)

    def test_partial_then_correct_rewards_delta_only(self) -> None:
        """Upgrading from partial to correct earns only the marginal improvement."""
        runtime = _make_runtime()
        r1 = self.engine.handle_action(
            runtime, "submit_diagnosis",
            {"root_cause_service": "svc-a", "error_type": "wrong"},  # 0.5 weight correct
            1,
        )
        r2 = self.engine.handle_action(
            runtime, "submit_diagnosis",
            {"root_cause_service": "svc-a", "error_type": "something broke"},  # 1.0 correct
            2,
        )
        # Both steps give reward; second is smaller (delta only, later step)
        self.assertGreater(r1.reward, 0.0)
        self.assertGreater(r2.reward, 0.0)
        self.assertLess(r2.reward, r1.reward)

    def test_diagnosis_farming_capped(self) -> None:
        """Repeated correct diagnosis submissions cannot push score above first reward."""
        runtime = _make_runtime()
        payload = {"root_cause_service": "svc-a", "error_type": "something broke"}
        rewards = [
            self.engine.handle_action(runtime, "submit_diagnosis", payload, s).reward
            for s in range(1, 6)
        ]
        self.assertGreater(rewards[0], 0.0)
        self.assertEqual(sum(rewards[1:]), 0.0)


class SREEngineRemediationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = SREEngine()

    def test_correct_remediation(self) -> None:
        runtime = _make_runtime()
        runtime.diagnosis_correct = True
        result = self.engine.handle_action(
            runtime, "submit_remediation", {"action": "restart svc-a"}, 1
        )
        self.assertTrue(runtime.remediation_correct)
        self.assertTrue(result.done)
        self.assertGreater(result.reward, 0.0)

    def test_wrong_remediation(self) -> None:
        runtime = _make_runtime()
        runtime.diagnosis_correct = True
        result = self.engine.handle_action(
            runtime, "submit_remediation", {"action": "do nothing"}, 1
        )
        self.assertFalse(runtime.remediation_correct)
        self.assertFalse(result.done)
        self.assertEqual(result.reward, 0.0)

    def test_remediation_without_diagnosis_not_done(self) -> None:
        runtime = _make_runtime()
        result = self.engine.handle_action(
            runtime, "submit_remediation", {"action": "restart svc-a"}, 1
        )
        self.assertFalse(result.done)

    def test_remediation_substring_match(self) -> None:
        runtime = _make_runtime()
        runtime.diagnosis_correct = True
        result = self.engine.handle_action(
            runtime,
            "submit_remediation",
            {"action": "we should rollback deploy-001 immediately"},
            1,
        )
        self.assertTrue(runtime.remediation_correct)

    def test_remediation_farming_blocked(self) -> None:
        """Repeated correct remediation must yield 0 reward after first submission."""
        runtime = _make_runtime()
        runtime.diagnosis_correct = True
        r1 = self.engine.handle_action(runtime, "submit_remediation", {"action": "restart svc-a"}, 1)
        r2 = self.engine.handle_action(runtime, "submit_remediation", {"action": "restart svc-a"}, 2)
        r3 = self.engine.handle_action(runtime, "submit_remediation", {"action": "rollback deploy-001"}, 3)
        self.assertGreater(r1.reward, 0.0)
        self.assertEqual(r2.reward, 0.0)
        self.assertEqual(r3.reward, 0.0)

    def test_wrong_then_correct_remediation_earns_reward(self) -> None:
        """First wrong, then correct — agent can upgrade (delta-reward)."""
        runtime = _make_runtime()
        runtime.diagnosis_correct = True
        r1 = self.engine.handle_action(runtime, "submit_remediation", {"action": "do nothing"}, 1)
        r2 = self.engine.handle_action(runtime, "submit_remediation", {"action": "restart svc-a"}, 2)
        self.assertEqual(r1.reward, 0.0)
        self.assertGreater(r2.reward, 0.0)  # upgrade earns reward
        # But no further farming
        r3 = self.engine.handle_action(runtime, "submit_remediation", {"action": "restart svc-a"}, 3)
        self.assertEqual(r3.reward, 0.0)


class SREEngineUnsupportedActionTest(unittest.TestCase):
    def test_unknown_action(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        result = engine.handle_action(runtime, "reboot_server", {}, 1)
        self.assertIn("Unsupported", result.feedback)
        self.assertEqual(result.reward, 0.0)
        self.assertFalse(result.done)


class SREEngineLoadScenarioTest(unittest.TestCase):
    def test_load_real_scenario(self) -> None:
        engine = SREEngine()
        task = get_task("sre_easy")
        runtime = engine.start_episode(task, seed=42)
        self.assertIn("scenario_id", runtime.scenario)
        self.assertIn("logs", runtime.scenario)

    def test_deterministic_with_seed(self) -> None:
        engine = SREEngine()
        task = get_task("sre_easy")
        r1 = engine.start_episode(task, seed=99)
        r2 = engine.start_episode(task, seed=99)
        self.assertEqual(r1.scenario["scenario_id"], r2.scenario["scenario_id"])


class SREEngineTaskCompleteTest(unittest.TestCase):
    def test_complete_when_no_remediations_required(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime(_make_scenario(accepted_remediations=[]))
        runtime.diagnosis_correct = True
        self.assertTrue(engine._task_complete(runtime))

    def test_not_complete_without_remediation(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        runtime.diagnosis_correct = True
        runtime.remediation_correct = False
        self.assertFalse(engine._task_complete(runtime))

    def test_complete_with_both(self) -> None:
        engine = SREEngine()
        runtime = _make_runtime()
        runtime.diagnosis_correct = True
        runtime.remediation_correct = True
        self.assertTrue(engine._task_complete(runtime))

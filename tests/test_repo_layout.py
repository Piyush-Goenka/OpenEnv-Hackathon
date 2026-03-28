from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class RepoLayoutTest(unittest.TestCase):
    def test_expected_paths_exist(self) -> None:
        expected_paths = [
            ROOT / "Dockerfile",
            ROOT / "client.py",
            ROOT / "inference.py",
            ROOT / "models.py",
            ROOT / "openenv.yaml",
            ROOT / "server" / "app.py",
            ROOT / "server" / "ci_engine.py",
            ROOT / "server" / "environment.py",
            ROOT / "server" / "reward.py",
            ROOT / "server" / "sre_engine.py",
            ROOT / "tasks" / "ci" / "easy_lint_failure.py",
            ROOT / "tasks" / "ci" / "medium_test_failure.py",
            ROOT / "tasks" / "ci" / "hard_cascading_failure.py",
            ROOT / "tasks" / "sre" / "easy_noisy_service.py",
            ROOT / "tasks" / "sre" / "medium_latency_trace.py",
            ROOT / "tasks" / "sre" / "hard_memory_leak.py",
            ROOT / "data" / "ci_scenarios" / "scenario_lint_001.json",
            ROOT / "data" / "ci_scenarios" / "scenario_test_001.json",
            ROOT / "data" / "ci_scenarios" / "scenario_cascade_001.json",
            ROOT / "data" / "sre_scenarios" / "scenario_noisy_001.json",
            ROOT / "data" / "sre_scenarios" / "scenario_latency_001.json",
            ROOT / "data" / "sre_scenarios" / "scenario_memleak_001.json",
        ]
        for path in expected_paths:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"Missing required path: {path}")

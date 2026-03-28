from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class RepoScaffoldTest(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        expected_paths = [
            ROOT / "client.py",
            ROOT / "inference.py",
            ROOT / "models.py",
            ROOT / "openenv.yaml",
            ROOT / "pyproject.toml",
            ROOT / "requirements.txt",
            ROOT / "server" / "app.py",
            ROOT / "server" / "environment.py",
            ROOT / "server" / "Dockerfile",
            ROOT / "tasks" / "task_easy.py",
            ROOT / "tasks" / "task_medium.py",
            ROOT / "tasks" / "task_hard.py",
        ]
        for path in expected_paths:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"Missing scaffold file: {path}")

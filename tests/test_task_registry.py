from __future__ import annotations

import unittest

from tasks import DEFAULT_TASK_ID, get_task, list_tasks


class TaskRegistryTest(unittest.TestCase):
    def test_registry_contains_all_six_tasks(self) -> None:
        tasks = list_tasks()
        self.assertEqual(len(tasks), 6)
        self.assertEqual(
            [task.id for task in tasks],
            ["ci_easy", "ci_hard", "ci_medium", "sre_easy", "sre_hard", "sre_medium"],
        )

    def test_track_filtering_works(self) -> None:
        self.assertEqual([task.id for task in list_tasks("ci")], ["ci_easy", "ci_hard", "ci_medium"])
        self.assertEqual(
            [task.id for task in list_tasks("sre")],
            ["sre_easy", "sre_hard", "sre_medium"],
        )

    def test_default_task_exists(self) -> None:
        task = get_task(DEFAULT_TASK_ID)
        self.assertEqual(task.id, "ci_easy")
        self.assertEqual(task.track, "ci")

    def test_all_tasks_have_scenario_directories(self) -> None:
        for task in list_tasks():
            with self.subTest(task=task.id):
                self.assertTrue(task.scenario_dir.exists())

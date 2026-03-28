from __future__ import annotations

import unittest

from tasks import DEFAULT_TASK_ID, get_task, list_tasks


class TaskRegistryTest(unittest.TestCase):
    def test_registry_contains_three_tasks(self) -> None:
        tasks = list_tasks()
        self.assertEqual(len(tasks), 3)
        self.assertEqual([task.id for task in tasks], ["task_easy", "task_hard", "task_medium"])

    def test_default_task_exists(self) -> None:
        task = get_task(DEFAULT_TASK_ID)
        self.assertEqual(task.id, "task_easy")
        self.assertEqual(task.difficulty, "easy")

    def test_all_tasks_have_positive_step_limits(self) -> None:
        for task in list_tasks():
            with self.subTest(task=task.id):
                self.assertGreater(task.max_steps, 0)

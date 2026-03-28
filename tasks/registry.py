from tasks.base import TaskDefinition
from tasks.ci.easy_lint_failure import TASK as CI_EASY
from tasks.ci.hard_cascading_failure import TASK as CI_HARD
from tasks.ci.medium_test_failure import TASK as CI_MEDIUM
from tasks.sre.easy_noisy_service import TASK as SRE_EASY
from tasks.sre.hard_memory_leak import TASK as SRE_HARD
from tasks.sre.medium_latency_trace import TASK as SRE_MEDIUM

TASKS = {
    CI_EASY.id: CI_EASY,
    CI_MEDIUM.id: CI_MEDIUM,
    CI_HARD.id: CI_HARD,
    SRE_EASY.id: SRE_EASY,
    SRE_MEDIUM.id: SRE_MEDIUM,
    SRE_HARD.id: SRE_HARD,
}

DEFAULT_TASK_ID = CI_EASY.id


def get_task(task_id: str) -> TaskDefinition:
    try:
        return TASKS[task_id]
    except KeyError as exc:
        available = ", ".join(sorted(TASKS))
        raise ValueError(f"Unknown task_id={task_id!r}. Available tasks: {available}") from exc


def list_tasks(track: str | None = None) -> list[TaskDefinition]:
    ordered = [TASKS[key] for key in sorted(TASKS)]
    if track is None:
        return ordered
    return [task for task in ordered if task.track == track]

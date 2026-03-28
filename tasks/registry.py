from tasks.base import TaskDefinition
from tasks.task_easy import TASK as TASK_EASY
from tasks.task_hard import TASK as TASK_HARD
from tasks.task_medium import TASK as TASK_MEDIUM

TASKS = {
    TASK_EASY.id: TASK_EASY,
    TASK_MEDIUM.id: TASK_MEDIUM,
    TASK_HARD.id: TASK_HARD,
}

DEFAULT_TASK_ID = TASK_EASY.id


def get_task(task_id: str) -> TaskDefinition:
    try:
        return TASKS[task_id]
    except KeyError as exc:
        available = ", ".join(sorted(TASKS))
        raise ValueError(f"Unknown task_id={task_id!r}. Available tasks: {available}") from exc


def list_tasks() -> list[TaskDefinition]:
    return [TASKS[key] for key in sorted(TASKS)]

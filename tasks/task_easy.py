from tasks.base import TaskDefinition, exact_match_grader

TASK = TaskDefinition(
    id="task_easy",
    difficulty="easy",
    title="Placeholder Exact Match",
    description=(
        "This is a scaffold-only task. Reply with exactly `ACK EASY` and nothing else. "
        "Replace this task with the real easy task once the final idea is chosen."
    ),
    initial_state="No attempts made yet. The current scaffold validates exact-match grading.",
    max_steps=2,
    grader=exact_match_grader("ACK EASY"),
)

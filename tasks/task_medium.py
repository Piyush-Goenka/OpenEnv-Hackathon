from tasks.base import TaskDefinition, required_tokens_grader

TASK = TaskDefinition(
    id="task_medium",
    difficulty="medium",
    title="Placeholder Token Match",
    description=(
        "This scaffold task expects a response that contains the tokens `deterministic`, "
        "`medium`, and `grader`. Order does not matter. Replace this task with the final "
        "medium-difficulty task later."
    ),
    initial_state="No attempts made yet. Partial credit is based on how many required tokens appear.",
    max_steps=3,
    grader=required_tokens_grader(["deterministic", "medium", "grader"]),
)

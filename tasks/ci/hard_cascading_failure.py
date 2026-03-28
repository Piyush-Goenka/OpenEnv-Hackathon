from tasks.base import TaskDefinition

TASK = TaskDefinition(
    id="ci_hard",
    track="ci",
    difficulty="hard",
    title="Fix the Cascading Multi-File Failure",
    description=(
        "Trace a core signature change through mypy, unit, and integration failures, "
        "then submit a coherent multi-file patch that stabilizes the whole suite."
    ),
    max_steps=10,
    available_actions=("read_file", "run_check", "submit_patch"),
    scenario_glob="scenario_cascade_*.json",
)

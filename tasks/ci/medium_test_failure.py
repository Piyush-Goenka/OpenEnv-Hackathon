from tasks.base import TaskDefinition

TASK = TaskDefinition(
    id="ci_medium",
    track="ci",
    difficulty="medium",
    title="Fix the Broken Unit Test",
    description=(
        "Read the refactor diff and failing unit test output, then patch either the "
        "implementation or the test so the target test and regression check go green."
    ),
    max_steps=8,
    available_actions=("read_file", "run_check", "submit_patch"),
    scenario_glob="scenario_test_*.json",
)

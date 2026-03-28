from tasks.base import TaskDefinition

TASK = TaskDefinition(
    id="ci_easy",
    track="ci",
    difficulty="easy",
    title="Fix the Linting Failure",
    description="Read the failing CI output, inspect the file, and submit a patch that fixes lint.",
    max_steps=5,
    available_actions=("read_file", "run_check", "submit_patch"),
    scenario_glob="scenario_lint_*.json",
)

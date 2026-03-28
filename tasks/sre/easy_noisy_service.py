from tasks.base import TaskDefinition

TASK = TaskDefinition(
    id="sre_easy",
    track="sre",
    difficulty="easy",
    title="Identify the Noisy Service",
    description=(
        "Inspect the alert context and logs, then submit the root-cause service, "
        "error type, and affected line."
    ),
    max_steps=5,
    available_actions=("get_logs", "submit_diagnosis"),
    scenario_glob="scenario_noisy_*.json",
)

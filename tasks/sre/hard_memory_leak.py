from tasks.base import TaskDefinition

TASK = TaskDefinition(
    id="sre_hard",
    track="sre",
    difficulty="hard",
    title="Diagnose a Memory Leak Under Load",
    description=(
        "Correlate deployment history, diffs, metrics, and heap summaries to diagnose "
        "a memory leak and recommend the correct fix."
    ),
    max_steps=12,
    available_actions=(
        "get_metrics",
        "get_deployment_history",
        "get_diff",
        "get_heap_summary",
        "get_logs",
        "submit_diagnosis",
        "submit_remediation",
    ),
    scenario_glob="scenario_memleak_*.json",
)

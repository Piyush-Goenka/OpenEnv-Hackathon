from tasks.base import TaskDefinition

TASK = TaskDefinition(
    id="sre_medium",
    track="sre",
    difficulty="medium",
    title="Trace a Latency Spike",
    description=(
        "Use logs and metrics across multiple services to find the root cause of a "
        "checkout latency regression and submit the right remediation."
    ),
    max_steps=10,
    available_actions=("get_logs", "get_metrics", "submit_diagnosis", "submit_remediation"),
    scenario_glob="scenario_latency_*.json",
)

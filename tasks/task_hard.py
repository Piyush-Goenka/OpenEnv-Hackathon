from tasks.base import TaskDefinition, json_object_grader

TASK = TaskDefinition(
    id="task_hard",
    difficulty="hard",
    title="Placeholder Structured Output",
    description=(
        "This scaffold task expects a JSON object with exact values for three fields: "
        '`{"status":"ready","difficulty":"hard","type":"scaffold"}`. Replace this '
        "task with the final hard task and grader later."
    ),
    initial_state="No attempts made yet. Partial credit is based on JSON validity, keys, and exact values.",
    max_steps=4,
    grader=json_object_grader(
        {
            "status": "ready",
            "difficulty": "hard",
            "type": "scaffold",
        }
    ),
)

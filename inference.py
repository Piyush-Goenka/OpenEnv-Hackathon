from __future__ import annotations

import json
import os
from typing import Iterable

from openai import OpenAI

from client import DevReliabilityEnv
from models import DevReliabilityAction

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860")
MODEL_NAME = os.getenv("MODEL_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
TASK_IDS = tuple(
    task_id.strip()
    for task_id in os.getenv(
        "TASK_IDS",
        "ci_easy,ci_medium,ci_hard,sre_easy,sre_medium,sre_hard",
    ).split(",")
    if task_id.strip()
)


def require_config() -> None:
    missing = []
    if not MODEL_NAME:
        missing.append("MODEL_NAME")
    if not API_KEY:
        missing.append("HF_TOKEN or API_KEY")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def build_prompt(task_id: str, observation) -> str:
    if observation.track == "ci":
        examples = """Examples:
{"action_type":"read_file","payload":{"path":"src/utils.py"}}
{"action_type":"run_check","payload":{"check":"lint"}}
{"action_type":"submit_patch","payload":{"file":"src/utils.py","patch":"import time\\n\\ndef calculate_retry_delay(attempt: int):\\n    return 2 ** attempt\\n"}}"""
    else:
        examples = """Examples:
{"action_type":"get_logs","payload":{"service":"payment-service","level":"ERROR"}}
{"action_type":"get_metrics","payload":{"service":"db-proxy","metric":"query_latency_p99_ms"}}
{"action_type":"submit_diagnosis","payload":{"root_cause_service":"payment-service","error_type":"NullPointerException"}}"""

    return f"""You are solving a DevReliability-Env task.

Task ID: {task_id}
Track: {observation.track}
Difficulty: {observation.difficulty}
Description:
{observation.description}

Context:
{json.dumps(observation.context, indent=2)}

Available actions:
{observation.available_actions}

Latest tool results:
{observation.tool_results}

Current CI output:
{observation.ci_output}

Latest feedback:
{observation.feedback}

Return exactly one JSON object with keys "action_type" and "payload".
Do not wrap it in markdown.

{examples}
"""


def parse_action(response_text: str, observation) -> DevReliabilityAction:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        payload = {}

    if isinstance(payload, dict) and isinstance(payload.get("action_type"), str):
        action_payload = payload.get("payload", {})
        if isinstance(action_payload, dict):
            return DevReliabilityAction(
                action_type=payload["action_type"],
                payload=action_payload,
            )

    if observation.track == "ci":
        default_file = observation.context.get("relevant_files", [""])[0]
        return DevReliabilityAction(
            action_type="submit_patch",
            payload={"file": default_file, "patch": response_text.strip()},
        )

    return DevReliabilityAction(
        action_type="submit_diagnosis",
        payload={"summary": response_text.strip()},
    )


def run_task(task_id: str, llm_client: OpenAI) -> float:
    total_reward = 0.0
    with DevReliabilityEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(task_id=task_id)
        for _ in range(result.observation.max_steps or 1):
            if result.done:
                break

            prompt = build_prompt(task_id, result.observation)
            completion = llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.0,
            )
            response_text = (completion.choices[0].message.content or "").strip()
            result = env.step(parse_action(response_text, result.observation))
            total_reward += result.reward or 0.0
    return total_reward


def run_all_tasks(task_ids: Iterable[str]) -> dict[str, float]:
    require_config()
    llm_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    return {task_id: run_task(task_id, llm_client) for task_id in task_ids}


def main() -> None:
    scores = run_all_tasks(TASK_IDS)
    for task_id, score in scores.items():
        print(f"{task_id}: {score:.3f}")
    average = sum(scores.values()) / len(scores)
    print(f"\nOverall: {average:.3f}")


if __name__ == "__main__":
    main()

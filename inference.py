from __future__ import annotations

import os
from typing import Iterable

from openai import OpenAI

from client import HackathonEnv
from models import HackathonAction

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860")
MODEL_NAME = os.getenv("MODEL_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MAX_STEPS = int(os.getenv("MAX_STEPS", "6"))
TASK_IDS = ("task_easy", "task_medium", "task_hard")


def require_config() -> None:
    missing = []
    if not MODEL_NAME:
        missing.append("MODEL_NAME")
    if not API_KEY:
        missing.append("HF_TOKEN or API_KEY")
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def build_prompt(task_id: str, observation) -> str:
    return f"""You are interacting with an OpenEnv task.

Task ID: {task_id}
Difficulty: {observation.difficulty}
Task description:
{observation.task_description}

Current state:
{observation.current_state}

Latest feedback:
{observation.feedback}

Return only the action text you want to send back to the environment.
Do not add explanations unless the task explicitly requires them.
"""


def run_task(task_id: str, llm_client: OpenAI) -> float:
    total_reward = 0.0
    with HackathonEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(task_id=task_id)
        for _ in range(MAX_STEPS):
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
            result = env.step(HackathonAction(response=response_text))
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

from __future__ import annotations

import json
import os
import re
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


SYSTEM_PROMPT_CI = """You are an expert CI/CD engineer debugging failing CI pipelines.

STRATEGY — follow this EXACT sequence:
1. Step 1: read_file the FIRST src/ file (the source code, NOT test files).
2. Step 2: run_check to see the FIRST failing check's error message.
3. Step 3+: submit_patch with the COMPLETE fixed file. You MUST submit a patch by step 3.
4. If the patch fails, read the CI error and submit a DIFFERENT improved patch immediately.

CRITICAL: Fix the src/ source files, NOT the test files. Tests define what's expected — fix the code to pass them.
CRITICAL: Do NOT spend more than 2 steps reading files. You MUST submit_patch early.
CRITICAL: Do NOT submit the same patch twice. If it didn't work, change your approach.
CRITICAL: Each submit_patch must be for ONE file. If multiple src/ files need fixing, submit patches for each one in separate steps.

EXACT PAYLOAD SCHEMAS (use these key names exactly):
- read_file:     {"path": "src/utils.py"}
- run_check:     {"check": "lint"}
- submit_patch:  {"file": "src/utils.py", "patch": "COMPLETE file content here"}

IMPORTANT: The key for read_file is "path", NOT "filename".
IMPORTANT: For submit_patch, the "patch" must be the COMPLETE fixed file content (not a diff).
IMPORTANT: Ensure all imports are before function definitions, no bare except clauses, and all required functions are defined.

RULES:
- Return exactly ONE JSON object per turn: {"action_type": "...", "payload": {...}}
- NO markdown fences, NO explanation — just the raw JSON.
"""

SYSTEM_PROMPT_SRE = """You are an expert SRE investigating a production incident.

STRATEGY:
1. First, get_logs for services mentioned in the alert to find errors.
2. Use get_metrics, get_deployment_history, get_diff, get_heap_summary to gather evidence.
3. Once you have enough evidence, submit_diagnosis with the EXACT field names from the scenario.
4. Then submit_remediation with a SHORT, concrete action.

CRITICAL: Do NOT repeat the same query. Each step should gather NEW information.

EXACT PAYLOAD SCHEMAS (use these key names, not alternatives):
- get_logs:               {"service": "service-name"}
- get_metrics:            {"service": "service-name", "metric": "metric_name"}
- get_deployment_history: {}
- get_diff:               {"deploy_id": "deploy-123"}
- get_heap_summary:       {"timestamp": "2026-04-05T14:18:00Z"}
- submit_diagnosis:       use field names like root_cause_service, error_type, trigger_event, affected_table, impact
- submit_remediation:     {"action": "rollback deploy-123"} — keep it SHORT (e.g. "rollback deploy-X", "restart service-Y", "revert config change")

IMPORTANT: The key for service is "service", NOT "service_name".
IMPORTANT: For remediation, use a short phrase like "rollback deploy-204" not a paragraph.

RULES:
- Return exactly ONE JSON object per turn: {"action_type": "...", "payload": {...}}
- NO markdown fences, NO explanation — just the raw JSON.
"""


def build_system_prompt(observation) -> str:
    if observation.track == "ci":
        return SYSTEM_PROMPT_CI
    return SYSTEM_PROMPT_SRE


def build_user_message(task_id: str, observation, step_num: int) -> str:
    parts = [
        f"Task: {task_id} | Track: {observation.track} | Difficulty: {observation.difficulty}",
        f"Step: {step_num}/{observation.max_steps}",
        f"\nDescription:\n{observation.description}",
        f"\nContext:\n{json.dumps(observation.context, indent=2)}",
        f"\nAvailable actions: {observation.available_actions}",
    ]

    if observation.tool_results:
        parts.append(f"\nTool results from last action:\n{observation.tool_results}")
    if observation.ci_output:
        parts.append(f"\nCI output:\n{observation.ci_output}")
    if observation.feedback:
        parts.append(f"\nFeedback: {observation.feedback}")

    remaining = (observation.max_steps or 1) - step_num
    if observation.track == "ci":
        urgency = f" You have {remaining} step(s) left — submit_patch NOW if you haven't already!" if remaining <= 3 else ""
        parts.append(
            f"\nReturn one JSON action. For submit_patch, include the COMPLETE fixed file as the 'patch' value.{urgency}"
        )
    else:
        urgency = f" You have {remaining} step(s) left — submit_diagnosis NOW if you haven't already!" if remaining <= 3 else ""
        parts.append(
            f"\nReturn one JSON action. For submit_diagnosis, use field names that match the scenario "
            f"(e.g. root_cause_service, error_type, trigger_event, affected_table, impact).{urgency}"
        )

    return "\n".join(parts)


def parse_action(response_text: str, observation) -> DevReliabilityAction:
    # Strip markdown fences if present
    cleaned = response_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        match = re.search(r'\{[^{}]*"action_type"\s*:\s*"[^"]+?"[^{}]*\}', cleaned, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group())
            except json.JSONDecodeError:
                payload = {}
        else:
            payload = {}

    if isinstance(payload, dict) and isinstance(payload.get("action_type"), str):
        action_payload = payload.get("payload", {})
        if isinstance(action_payload, dict):
            return DevReliabilityAction(
                action_type=payload["action_type"],
                payload=action_payload,
            )

    # Fallback: for CI, try submitting the raw text as a patch
    if observation.track == "ci":
        default_file = observation.context.get("relevant_files", [""])[0]
        return DevReliabilityAction(
            action_type="read_file",
            payload={"path": default_file},
        )

    # Fallback for SRE: get logs for the first service in catalog
    services = observation.context.get("service_catalog", [])
    if services:
        return DevReliabilityAction(
            action_type="get_logs",
            payload={"service": services[0]},
        )
    return DevReliabilityAction(action_type="get_logs", payload={"service": "unknown"})


def run_task(task_id: str, llm_client: OpenAI) -> float:
    with DevReliabilityEnv(base_url=ENV_BASE_URL).sync() as env:
        result = env.reset(task_id=task_id)
        # print(f"\n--- {task_id} (max_steps={result.observation.max_steps}) ---")

        messages = [{"role": "system", "content": build_system_prompt(result.observation)}]

        for step in range(result.observation.max_steps or 1):
            if result.done:
                break

            user_msg = build_user_message(task_id, result.observation, step + 1)
            messages.append({"role": "user", "content": user_msg})
            # Keep conversation short: system + last 4 turns to save tokens
            if len(messages) > 9:
                messages = [messages[0]] + messages[-8:]

            try:
                completion = llm_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    max_tokens=512,
                    temperature=0.0,
                )
                response_text = (completion.choices[0].message.content or "").strip()
            except Exception as e:
                print(f"           LLM error: {e}")
                break
            messages.append({"role": "assistant", "content": response_text})

            action = parse_action(response_text, result.observation)
            # print(f"  step {step+1}: action={action.action_type} payload={json.dumps(action.payload)[:150]}")
            result = env.step(action)
            # print(f"           reward={result.reward}  feedback={result.observation.feedback}")

        # Use the environment's final_score which is always in [0, 1]
        state = env.state()
        return state.final_score if state else 0.0


def run_all_tasks(task_ids: Iterable[str]) -> dict[str, float]:
    require_config()
    llm_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    return {task_id: run_task(task_id, llm_client) for task_id in task_ids}


def main() -> None:
    scores = run_all_tasks(TASK_IDS)
    print("\n" + "=" * 40)
    for task_id, score in scores.items():
        print(f"{task_id}: {score:.3f}")
    average = sum(scores.values()) / len(scores)
    print(f"\nOverall: {average:.3f}")


if __name__ == "__main__":
    main()

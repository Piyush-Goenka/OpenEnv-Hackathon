from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

Grader = Callable[[str], tuple[float, str]]


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    id: str
    difficulty: str
    title: str
    description: str
    initial_state: str
    max_steps: int
    grader: Grader


def exact_match_grader(expected_response: str) -> Grader:
    expected = expected_response.strip()
    expected_lower = expected.lower()

    def grade(submission: str) -> tuple[float, str]:
        candidate = submission.strip()
        if not candidate:
            return 0.0, "No response received."
        if candidate == expected:
            return 1.0, "Exact match."
        if candidate.lower() == expected_lower:
            return 0.4, "Case-insensitive match only. Exact formatting still matters."
        return 0.0, f"Expected the exact response {expected!r}."

    return grade


def required_tokens_grader(required_tokens: Sequence[str]) -> Grader:
    tokens = tuple(token.lower() for token in required_tokens)

    def grade(submission: str) -> tuple[float, str]:
        candidate = submission.strip().lower()
        if not candidate:
            return 0.0, "No response received."
        matched = [token for token in tokens if token in candidate]
        score = len(matched) / len(tokens) if tokens else 1.0
        feedback = f"Matched {len(matched)}/{len(tokens)} required tokens: {matched}."
        return round(score, 3), feedback

    return grade


def json_object_grader(expected_fields: Mapping[str, str]) -> Grader:
    required_items = dict(expected_fields)

    def grade(submission: str) -> tuple[float, str]:
        candidate = submission.strip()
        if not candidate:
            return 0.0, "No response received."
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return 0.0, "Response is not valid JSON."

        if not isinstance(payload, dict):
            return 0.2, "JSON parsed successfully but was not an object."

        score = 0.2
        missing_keys = [key for key in required_items if key not in payload]
        matched_values = [
            key for key, value in required_items.items() if payload.get(key) == value
        ]
        key_score = (len(required_items) - len(missing_keys)) / len(required_items)
        value_score = len(matched_values) / len(required_items)
        score += 0.3 * key_score
        score += 0.5 * value_score
        feedback = (
            f"Present keys: {len(required_items) - len(missing_keys)}/{len(required_items)}. "
            f"Exact values: {len(matched_values)}/{len(required_items)}."
        )
        return round(min(score, 1.0), 3), feedback

    return grade

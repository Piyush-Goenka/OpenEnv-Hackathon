---
title: dev-reliability-env
emoji: wrench
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
tags:
  - openenv
---

# DevReliability-Env

An OpenEnv environment that simulates two core software reliability workflows: **CI pipeline debugging** and **SRE incident response**. Agents fix failing builds by patching code and investigate production outages by querying logs, metrics, diffs, and heap dumps.

2 tracks, 6 tasks, 18 scenario variants, 16 distinct reward signals, 160 tests.

---

## Tasks

### CI Track

The agent receives a failing CI pipeline and must submit patches to make all checks green.

| Task ID | Difficulty | Description | Max Steps |
|---|---|---|---|
| `ci_easy` | Easy | Fix a lint failure in a single file | 5 |
| `ci_medium` | Medium | Fix a broken unit test caused by a refactor | 8 |
| `ci_hard` | Hard | Fix a cascading multi-file failure from a signature change | 10 |

**Actions:** `read_file`, `run_check`, `submit_patch`

### SRE Track

The agent receives a production alert and must investigate, diagnose, and remediate.

| Task ID | Difficulty | Description | Max Steps |
|---|---|---|---|
| `sre_easy` | Easy | Identify the noisy service from a log stream | 5 |
| `sre_medium` | Medium | Trace a latency spike across 6 services | 10 |
| `sre_hard` | Hard | Diagnose a memory leak from metrics, diffs, and heap data | 12 |

**Actions:** `get_logs`, `get_metrics`, `get_deployment_history`, `get_diff`, `get_heap_summary`, `submit_diagnosis`, `submit_remediation`

---

## Baseline Scores

Model: **GPT-OSS-120B** (`openai/gpt-oss-120b:free`, temperature=0)

| Task | Score | Notes |
|---|---|---|
| `ci_easy` | **0.720** | Solved in 2 steps |
| `ci_medium` | **0.768** | Solved in 2 steps |
| `ci_hard` | **0.000** | Failed to submit patch |
| `sre_easy` | **0.381** | Partial diagnosis (2/3 fields correct) |
| `sre_medium` | **0.215** | Partial diagnosis, wrong remediation |
| `sre_hard` | **0.200** | Partial diagnosis, wrong remediation |
| **Average** | **0.381** | |

---

## Reward System

Industry-standard budget-based reward shaping following established RL principles:

- **Ng et al. 1999** — potential-based reward shaping theory
- **Eschmann 2021** — reward function design survey (completion >> shaping)
- **Comparable to** SWE-bench (0-1 scoring), WebArena (task completion), InterCode (partial credit)

### Core Design

| Principle | Implementation |
|---|---|
| Bounded episode returns | Episode score in `[0.0, 1.0]`, per-step rewards in `[-1.0, 1.0]` |
| Completion >> Shaping | CI: 68% from completion, SRE: 81% from completion (standard: >=60%) |
| Step discount factor | gamma = 0.98 per step (appropriate for 5-12 step episodes) |
| Real penalties | Negative per-step rewards, episode floor at 0.0 via `max(0, min(1, acc + r))` |
| Dense learning signal | 16 distinct reward signals across 2 tracks |
| Monotonic skill gradient | Optimal agent > Lazy agent > Random agent (verified) |

### Score Profiles (Verified)

| Agent Behavior | CI Score | SRE Score |
|---|---|---|
| Optimal (investigate + solve) | ~0.93 | ~0.83 |
| Lazy (skip investigation, correct answer) | — | ~0.73 |
| Farming attempt (spam same action) | 0.00 | ~0.44 (capped at first submission) |
| Random / wrong answers | 0.00 | 0.00 |

### CI Track Budget (optimal ~0.93, always in [0, 1])

| Signal | Reward | Type | Notes |
|---|---|---|---|
| Patch applies cleanly | +0.05 | Quality | Gated on `newly_green_checks > 0` to prevent farming |
| Code parses (valid Python) | +0.05 | Quality | Gated on `newly_green_checks > 0` to prevent farming |
| New check turns green | +0.05/check | Progress | Per-check, up to ~0.20 for 4 checks |
| All checks green | +0.55 | Completion | Bulk reward, dominates episode score |
| Efficiency bonus | 0.10 * 0.5^(step-1) | Efficiency | Smooth exponential decay, not step function |
| Repeated identical patch | -0.10 | Penalty | Real negative, deducted from episode score |
| Regression (broke green check) | -0.15 | Penalty | Real negative, deducted from episode score |

All rewards are decayed by `0.98^step_count` before clamping.

### SRE Track Budget (optimal ~0.83, always in [0, 1])

**Investigation signals** (capped at ~0.15 total, one-time each):

| Signal | Reward | Notes |
|---|---|---|
| Query relevant service | +0.03 | One-time per service, tracked via `one_time_rewards_claimed` |
| Query root-cause service | +0.05 | One-time, tracked via claimed set |
| Check deployment history | +0.02 | One-time |
| Inspect correct diff | +0.03 | One-time |
| Check heap evidence | +0.02 | One-time |

**Diagnosis** (up to 0.45, delta-reward):

| Signal | Reward | Notes |
|---|---|---|
| Correct diagnosis fields | up to 0.45 | Scenario JSON weights (sum to 1.0) scaled by 0.45 |
| Improved diagnosis | delta only | Only the improvement over best previous submission earns reward |
| Repeated same diagnosis | 0.00 | "No improvement over previous submission" |
| All fields wrong | -0.05 | Real negative penalty |

**Remediation** (up to 0.30, one-shot with upgrade):

| Signal | Reward | Notes |
|---|---|---|
| Correct remediation | +0.30 | First correct submission earns full reward |
| Wrong then correct | +0.30 | Upgrade path allowed (wrong attempt costs 0, not locked out) |
| Correct then correct again | 0.00 | Already rewarded, farming blocked |
| Wrong remediation | 0.00 | No penalty, can retry |

**Penalties:**

| Signal | Reward | Notes |
|---|---|---|
| Repeated query (exact same payload) | -0.03 | Real negative |
| Wrong diagnosis (all fields wrong) | -0.05 | Real negative, only on first wrong attempt |

All rewards are decayed by `0.98^step_count` before clamping.

### Anti-Farming Mechanisms

| Attack Vector | Prevention Mechanism |
|---|---|
| Submit valid-but-useless Python patches | Code quality rewards gated on `newly_green_checks > 0` |
| Re-query same investigation signals | `one_time_rewards_claimed` tracking set with unique keys |
| Spam correct diagnosis before remediation | Delta-reward: tracks `best_diagnosis_score`, only improvements earn reward |
| Spam correct remediation | One-shot: `"remediation_rewarded"` flag in claimed set |
| Toggle checks on/off to farm | Deterministic `_evaluate_checks()` — same patch always gives same result |
| Accumulate score above 1.0 | Double-clamped: `clamp_reward` per-step [-1,1], `max(0, min(1, acc))` at episode level |

---

## Observation Space

```python
@dataclass
class DevReliabilityObservation(Observation):
    done: bool
    reward: Optional[float]
    task_id: str
    track: str                          # "ci" or "sre"
    difficulty: str                     # "easy", "medium", "hard"
    description: str
    context: Dict[str, Any]
    available_actions: List[str]
    tool_results: Optional[str]         # SRE query results
    ci_output: Optional[str]            # CI check output
    checks_passing: Optional[int]
    checks_total: Optional[int]
    step_count: int
    max_steps: int
    feedback: str
```

## Action Space

```python
@dataclass
class DevReliabilityAction(Action):
    action_type: str
    payload: Dict[str, Any]
```

**CI examples:**
```json
{"action_type": "read_file",    "payload": {"path": "src/utils.py"}}
{"action_type": "run_check",    "payload": {"check": "lint"}}
{"action_type": "submit_patch", "payload": {"file": "src/utils.py", "patch": "import os\n\ndef main():\n    pass\n"}}
```

**SRE examples:**
```json
{"action_type": "get_logs",              "payload": {"service": "payment-service"}}
{"action_type": "get_metrics",           "payload": {"service": "db-proxy", "metric": "latency_p99"}}
{"action_type": "get_deployment_history", "payload": {}}
{"action_type": "get_diff",              "payload": {"deploy_id": "deploy-042"}}
{"action_type": "get_heap_summary",      "payload": {"timestamp": "2026-04-05T14:18:00Z"}}
{"action_type": "submit_diagnosis",      "payload": {"root_cause_service": "db-proxy", "error_type": "missing_index"}}
{"action_type": "submit_remediation",    "payload": {"action": "rollback deploy-042"}}
```

---

## Scenarios

Each task has 3 scenario variants (18 total), randomly selected on `reset()`.

**CI scenarios** contain Python source files, AST-based structural validators (`imports_before_functions`, `no_bare_except`, `function_defined`, `ruff_check`), and token-group matching.

**SRE scenarios** contain multi-service logs, metric timeseries, deployment histories, diffs, heap summaries, weighted diagnosis fields (sum to 1.0), and accepted remediation strings.

---

## Architecture

```
inference.py  <--HTTP-->  FastAPI (port 7860)
                               |
                         environment.py
                          /          \
                   ci_engine.py    sre_engine.py
                          \          /
                          reward.py
                               |
                         data/*.json (18 scenarios)
```

| Module | Responsibility |
|---|---|
| `server/environment.py` | OpenEnv `Environment`: `reset()`, `step()`, `state()` |
| `server/ci_engine.py` | AST parsing, token matching, structural validators |
| `server/sre_engine.py` | Log/metric/diff/heap queries, diagnosis/remediation grading |
| `server/reward.py` | Budget-based shaping, `clamp_reward` [-1,1], `clamp_score` [0,1] |
| `tasks/` | 6 task definitions with scenario dirs and action spaces |
| `data/` | 18 scenario JSON files |

---

## Setup

### Local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload
```

### Docker

```bash
docker build -t dev-reliability-env .
docker run --rm -p 7860:7860 dev-reliability-env
```

### Run Tests

```bash
python -m pytest tests/ -q
# 160 passed, 28 subtests passed
```

### Run Inference

```bash
API_BASE_URL="https://openrouter.ai/api/v1" \
API_KEY="your-key" \
MODEL_NAME="openai/gpt-oss-120b:free" \
ENV_BASE_URL="http://localhost:7860" \
python inference.py
```

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `API_BASE_URL` | LLM endpoint | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | Model identifier | (required) |
| `HF_TOKEN` / `API_KEY` | API key | (required) |
| `ENV_BASE_URL` | Environment server | `http://localhost:7860` |
| `TASK_IDS` | Comma-separated tasks | all 6 tasks |

---

## License

MIT

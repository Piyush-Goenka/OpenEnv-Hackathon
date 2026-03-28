# OpenEnv Hackathon — Complete Reference Guide
*Last updated: March 29, 2026*

---

## 1. What Is This Hackathon?

You are building an **AI training/evaluation environment** using the **OpenEnv framework**. The environment simulates a real-world task that an AI agent can practice, get scored on, and learn from.

Think of it like a gym for AI agents — your job is to build one room of that gym, with clear exercises (tasks), a scoring system (graders), and feedback signals (rewards).

---

## 2. Timeline

| Date | Event |
|---|---|
| **March 29, 2026** | Problem statement released ✅ |
| **April 1, 2026** | Round 1 officially opens |
| **April 8, 2026, 11:59 PM IST** | **Submission deadline** |

You have **7 days** from April 1st. Start building the scaffold now.

---

## 3. What OpenEnv Actually Is

OpenEnv treats RL environments as **microservices** — your environment runs in a Docker container and exposes a WebSocket/HTTP API. Your training code talks to it over the network.

```
┌──────────────────────────────────────┐
│  YOUR INFERENCE / TRAINING CODE      │
│                                      │
│  env = MyEnv(base_url="https://...") │
│  result = env.reset()                │
│  result = env.step(action)           │
└────────────────┬─────────────────────┘
                 │  WebSocket / HTTP
┌────────────────▼─────────────────────┐
│  DOCKER CONTAINER (HF Space)         │
│  FastAPI Server                      │
│  └─ Environment (reset, step, state) │
│     └─ Your task logic               │
└──────────────────────────────────────┘
```

Every OpenEnv environment exposes exactly **3 methods**:

| Method | What it does | Returns |
|---|---|---|
| `reset()` | Start a new episode | `StepResult` (observation, reward, done) |
| `step(action)` | Agent takes an action | `StepResult` (observation, reward, done) |
| `state()` | Get episode metadata | `State` (episode_id, step_count, etc.) |

---

## 4. Exact Project Structure (From the Course)

```
my_env/
├── models.py              ← Type contracts: Action, Observation, State
├── client.py              ← HTTP/WebSocket client (what users import)
├── server/
│   ├── environment.py     ← Core logic: reset(), step(), state
│   ├── app.py             ← FastAPI server (literally 1 line)
│   └── Dockerfile         ← Container definition
├── openenv.yaml           ← Manifest / metadata
├── pyproject.toml         ← Package metadata
├── requirements.txt       ← Python dependencies
├── inference.py           ← MUST be in root (hackathon requirement)
└── README.md              ← Documentation

# Additional for hackathon:
├── tasks/
│   ├── task_easy.py
│   ├── task_medium.py
│   └── task_hard.py
```

---

## 5. Exact Code Patterns (From Module 4)

### 5.1 models.py — Define Your Types

```python
from dataclasses import dataclass, field
from typing import List, Optional
from openenv.core.env_server import Action, Observation, State

@dataclass
class MyAction(Action):
    # What the agent submits
    value: str

@dataclass
class MyObservation(Observation):
    done: bool
    reward: Optional[float]
    task_description: str
    current_state: str
    feedback: str
    step_count: int

@dataclass
class MyState(State):
    episode_id: Optional[str] = None
    step_count: int = 0
    task_id: str = ""
    difficulty: str = ""
```

### 5.2 server/environment.py — Core Logic

```python
import uuid
from openenv.core.env_server import Environment
from models import MyAction, MyObservation, MyState

class MyEnvironment(Environment):
    def __init__(self):
        self._state = MyState()

    def reset(self) -> MyObservation:
        self._state = MyState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            task_id="task_easy",
        )
        return MyObservation(
            done=False,
            reward=None,
            task_description="...",
            current_state="...",
            feedback="Episode started.",
            step_count=0,
        )

    def step(self, action: MyAction) -> MyObservation:
        self._state.step_count += 1
        score = self._grade(action)
        done = score >= 1.0 or self._state.step_count >= 10
        return MyObservation(
            done=done,
            reward=score,
            task_description="...",
            current_state="...",
            feedback=f"Score: {score:.2f}",
            step_count=self._state.step_count,
        )

    @property
    def state(self) -> MyState:
        return self._state

    def _grade(self, action: MyAction) -> float:
        # Deterministic grading logic here
        return 0.0
```

### 5.3 server/app.py — FastAPI Wiring (1 line)

```python
from openenv.core.env_server import create_fastapi_app
from environment import MyEnvironment

app = create_fastapi_app(MyEnvironment)
```

`create_fastapi_app()` auto-generates all endpoints:
`/ws`, `/reset`, `/step`, `/state`, `/health`, `/web`, `/docs`

### 5.4 client.py — Client Side

```python
from openenv.core.http_env_client import HTTPEnvClient
from openenv.core.types import StepResult
from models import MyAction, MyObservation, MyState

class MyEnv(HTTPEnvClient[MyAction, MyObservation]):
    def _step_payload(self, action: MyAction) -> dict:
        return {"value": action.value}

    def _parse_result(self, payload: dict) -> StepResult:
        return StepResult(
            observation=MyObservation(
                done=payload["done"],
                reward=payload.get("reward"),
                task_description=payload["task_description"],
                current_state=payload["current_state"],
                feedback=payload["feedback"],
                step_count=payload["step_count"],
            ),
            reward=payload.get("reward", 0),
            done=payload["done"],
        )

    def _parse_state(self, payload: dict) -> MyState:
        return MyState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
```

### 5.5 server/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
```

> **Important:** HF Spaces uses port **7860** by default, not 8000.

### 5.6 openenv.yaml

```yaml
name: my-environment-name
version: "1.0.0"
description: "One-line description of the real-world task"
tags:
  - openenv
tasks:
  - id: task_easy
    difficulty: easy
    description: "Simple single-step objective"
  - id: task_medium
    difficulty: medium
    description: "Multi-step nuanced objective"
  - id: task_hard
    difficulty: hard
    description: "Complex objective that challenges frontier models"
```

### 5.7 inference.py (Hackathon Baseline Script)

```python
import os
from openai import OpenAI
from client import MyEnv, MyAction

# MANDATORY — read from env vars
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

TASKS = ["task_easy", "task_medium", "task_hard"]

def run_task(task_id: str) -> float:
    env = MyEnv(base_url="http://localhost:7860")
    result = env.reset()
    total_reward = 0.0

    for step in range(10):
        if result.done:
            break

        prompt = f"""
Task: {result.observation.task_description}
Current state: {result.observation.current_state}
Feedback: {result.observation.feedback}

Respond with your action value only.
"""
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.0,
        )
        action_value = completion.choices[0].message.content.strip()
        result = env.step(MyAction(value=action_value))
        total_reward += result.reward or 0.0

    return total_reward

if __name__ == "__main__":
    scores = {}
    for task_id in TASKS:
        score = run_task(task_id)
        scores[task_id] = score
        print(f"{task_id}: {score:.3f}")
    print(f"\nOverall: {sum(scores.values()) / len(scores):.3f}")
```

---

## 6. The 3 Tasks — Design Pattern

### Grader Rules
- Must be **deterministic** — same input always gives same score
- Scores must be **0.0–1.0**
- **Partial credit required** at intermediate steps

### Reward Shaping Pattern (Layered)

```python
def grade(submission: str, expected: str) -> float:
    score = 0.0

    # Layer 1: Is it valid / does it parse? (+0.2)
    if is_valid(submission):
        score += 0.2

    # Layer 2: Is the structure correct? (+0.3)
    if structure_matches(submission, expected):
        score += 0.3

    # Layer 3: Is the output correct? (+0.5)
    similarity = compute_similarity(submission, expected)
    score += 0.5 * similarity

    return min(score, 1.0)
```

### Difficulty Calibration

| Level | Frontier Model Score | Characteristics |
|---|---|---|
| Easy | 0.7–1.0 | Single clear objective, 1–2 steps |
| Medium | 0.4–0.7 | Requires reasoning, multi-step |
| Hard | 0.1–0.4 | Ambiguous constraints, multi-objective |

---

## 7. Judging Criteria

| Criterion | Weight | Key Questions |
|---|---|---|
| **Real-world utility** | 30% | Task humans actually do? Immediate value for RL community? |
| **Task & grader quality** | 25% | Clear objectives? Deterministic graders? Hard = actually hard? |
| **Environment design** | 20% | Clean state? Good reward shaping? Sensible episodes? |
| **Code quality & spec** | 15% | `openenv validate` passes? Docker works? Baseline runs? |
| **Creativity & novelty** | 10% | Novel domain? Clever mechanics? |

### Automated Disqualification Gate (All must pass)
- [ ] HF Space deploys and returns HTTP 200 on `reset()`
- [ ] `openenv validate` passes
- [ ] `docker build && docker run` succeeds
- [ ] `inference.py` runs without error and produces scores
- [ ] 3+ tasks with graders scoring 0.0–1.0
- [ ] Graders are not constant (not always same score)

---

## 8. Domain Options

| Domain | Grader Determinism | Build Complexity | Novelty |
|---|---|---|---|
| **SQL Query Debugging** | ✅ Very high | Low–Medium | High |
| **Data Cleaning Pipeline** | ✅ High | Medium | Medium |
| **CI/CD Log Diagnosis** | ✅ High | Medium | High |
| **Code Review Triage** | ⚠️ Medium | Medium | Medium |
| **Email / Ticket Triage** | ⚠️ Medium | Low | Low |

**Why SQL Query Debugging is the best pick:**
- Graders are 100% deterministic — run query against SQLite, compare results
- Natural difficulty curve: syntax errors → logic errors → optimization constraints
- High real-world utility (every dev team does this daily)
- SQLite is in-process — no external deps, fits 2vCPU/8GB easily
- Not yet a common OpenEnv domain

---

## 9. Infrastructure Constraints

| Constraint | Value |
|---|---|
| Max inference runtime | 20 minutes |
| Machine spec | 2 vCPU, 8 GB RAM |
| LLM client | OpenAI client **only** |
| Inference script name | `inference.py` in **root directory** |
| Required env vars | `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN` |
| HF Spaces port | **7860** |

---

## 10. Quick Start Commands

```bash
# Install
pip install openenv-core

# Scaffold
openenv init my_env_name
cd my_env_name

# Test locally
uvicorn server.app:app --host 0.0.0.0 --port 7860

# Validate
openenv validate

# Docker test
docker build -t my-env .
docker run -p 7860:7860 my-env

# Deploy to HF Spaces
openenv push --repo-id your-hf-username/my-env

# Run baseline
HF_TOKEN=xxx MODEL_NAME=yyy API_BASE_URL=zzz python inference.py
```

---

## 11. Pre-Submission Checklist

- [ ] `openenv validate` passes locally
- [ ] `docker build` succeeds
- [ ] `docker run` starts and responds to `reset()`
- [ ] `inference.py` runs end-to-end without errors
- [ ] All 3 tasks produce scores in 0.0–1.0
- [ ] Graders are deterministic
- [ ] HF Space is public, responds HTTP 200
- [ ] `openenv.yaml` present and valid
- [ ] README includes baseline scores
- [ ] Env vars read from `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
- [ ] `inference.py` is in the **root directory**
- [ ] Inference runs in under 20 minutes on 2vCPU/8GB

---

## 12. Preparatory Course Modules

https://github.com/raun/openenv-course

| Module | Topic | Priority |
|---|---|---|
| Module 1 | Why OpenEnv? Architecture, the RL loop | Read first |
| Module 2 | Using existing environments | Skim |
| Module 3 | Deploying to Docker + HF Spaces | Read carefully |
| **Module 4** | **Building your own environment** | **Most important** |
| Module 5 | Training with TRL + GRPO | Optional |

---

## 13. Submission

1. `openenv push --repo-id your-username/your-env`
2. Paste HF Spaces URL on the hackathon platform
3. Deadline: **April 8, 2026, 11:59 PM IST**
# DevReliability-Env: CI Debugging + SRE Incident Response
### OpenEnv Hackathon — Full Environment Design Document
*Author: Piyush | Deadline: April 8, 2026, 11:59 PM IST*

---

## 1. The Idea in One Paragraph

**DevReliability-Env** is an OpenEnv environment that simulates the two most common reliability loops in real software teams: (1) a developer whose PR has failing GitHub Actions CI and must patch the code to make it green, and (2) an SRE who receives a production alert and must read logs, identify root cause, and apply the correct fix or runbook action. Both loops share the same core mechanic — the agent observes a broken system, takes targeted actions, and gets rewarded for restoring it to a healthy state. The environment is grounded in real failure modes: lint errors, broken tests, cascading type failures, high error rates, DB timeouts, memory leaks, and misconfigured deployments.

---

## 2. Why This Environment

### 2.1 Personal Motivation
This environment was designed from lived experience. As a contributor and maintainer at the Palisadoes Foundation (Talawa project) and an active open source contributor (rage-rb/rage), the author has spent significant time in the exact loop this environment simulates:

- PR gets opened
- CI fails (lint, tests, type checks, build)
- Read the GitHub Actions log
- Find the broken line
- Push a fix
- Wait for CI to re-run
- Repeat

The SRE extension models the production-side equivalent: alert fires, logs spike, something is down, find the root cause before it pages the whole team.

No AI assistant suggested this. It came from frustration.

### 2.2 Gap in the Existing OpenEnv Ecosystem
Current OpenEnv environments (as of March 2026):

| Environment | Type |
|---|---|
| Wordle | Word game |
| Sudoku | Puzzle |
| BrowserGym | Web browser control |
| REPL | Code execution sandbox |
| SUMO RL | Traffic simulation |
| Calendar Gym | Scheduling |
| Football Play-Caller | Sports strategy |

**Missing:** Any environment that simulates the software development/operations reliability loop. DevReliability-Env fills this gap entirely.

### 2.3 Scoring Argument
- **Real-world utility (30%):** Every software team — from a 2-person startup to Meta — runs CI and has SREs. This is not a niche domain.
- **Task & grader quality (25%):** Graders are fully deterministic — run the patched code through the test suite/linter. Either it passes or it doesn't.
- **Creativity & novelty (10%):** First CI+SRE environment in OpenEnv. Judges are HF/Meta engineers who personally live this loop.

---

## 3. Environment Overview

### 3.1 Name
`dev-reliability-env`

### 3.2 Two Tracks, One Environment

The environment has two tracks, selectable via `reset(task_id=...)`:

**Track A — CI Debugger**
Agent plays the role of a developer. Receives a PR diff + failing CI log. Must patch the code to make CI pass.

**Track B — SRE Incident Responder**
Agent plays the role of an SRE. Receives a production alert + log stream. Must query logs, identify root cause, and apply the correct remediation action.

Both tracks use the same `step()` / `reset()` / `state()` interface. The action space is slightly different per track but the observation structure is unified.

---

## 4. Task Definitions

### 4.1 Track A — CI Debugger Tasks

---

#### Task A1: Fix the Linting Failure *(Easy)*

**Scenario:**
A contributor opened a PR that adds a new utility function. CI fails at the lint step. The agent receives the full CI log showing exactly which file and line caused the failure.

**What the agent sees:**
```
PR Diff:
  + def calculate_retry_delay(attempt: int):
  +     return 2 ** attempt
  +
  + import time   # ← wrong position, import not at top of file

CI Log:
  ruff check src/utils.py
  src/utils.py:47:1: E402 Module level import not at top of file
  Found 1 error.
  FAILED
```

**What the agent must do:**
Submit a patch that moves the import to the top of the file.

**Grader:**
```
+0.3  patch applies cleanly (no patch syntax error)
+0.3  file parses as valid Python after patch
+0.4  ruff check passes on the patched file
────
1.0   total
```

**Expected frontier model score:** 0.85–1.0
**Why it's easy:** Single file, single error, exact line number given in the log.

---

#### Task A2: Fix the Broken Unit Test *(Medium)*

**Scenario:**
A refactor changed the return type of a function from a list to a generator. An existing unit test breaks because it calls `len()` on the result, which doesn't work on generators.

**What the agent sees:**
```
PR Diff:
  - def get_pending_jobs(queue):
  -     return [job for job in queue if job.status == "pending"]
  + def get_pending_jobs(queue):
  +     return (job for job in queue if job.status == "pending")

CI Log:
  FAILED tests/test_queue.py::test_pending_count
  TypeError: object of type 'generator' has no len()
  
  test_queue.py:34: in test_pending_count
      assert len(get_pending_jobs(mock_queue)) == 3
```

**What the agent must do:**
Decide whether to fix the implementation (wrap in list) or fix the test (use `sum(1 for _ in ...)`). Either valid approach passes the grader.

**Grader:**
```
+0.2  patch applies cleanly
+0.2  file parses as valid Python
+0.2  no new test failures introduced
+0.4  target test passes
────
1.0   total
```

**Expected frontier model score:** 0.55–0.75
**Why it's medium:** Agent must understand the semantic relationship between the diff and the test failure. The fix is not spelled out in the log.

---

#### Task A3: Fix the Cascading Multi-File Failure *(Hard)*

**Scenario:**
A PR changes the signature of a core function — adds a required parameter. This causes: (1) a type check failure in the module itself, (2) three call sites in other files that now pass wrong args, (3) two tests that mock the old signature. All of these show up as separate CI failures. The agent must identify the root cause (signature change) and apply a coherent fix across all affected files, not patch each symptom individually.

**What the agent sees:**
```
PR Diff:
  - def process_event(event: Event) -> Result:
  + def process_event(event: Event, dry_run: bool = False) -> Result:
  +     if dry_run:
  +         return Result(success=True, changes=[])

CI Log:
  mypy src/processor.py ... FAILED
    error: Argument missing for parameter "dry_run" [call-arg] (×3 occurrences)
  
  pytest tests/test_processor.py ... FAILED
    TypeError: process_event() got unexpected keyword argument 'dry_run' (×2 tests)
    (tests are patching the old signature)
  
  pytest tests/test_integration.py ... FAILED  
    AssertionError: expected Result with changes, got empty Result
    (integration test not updated for dry_run behaviour)
```

**What the agent must do:**
Understand that the root cause is the signature change propagating outward. Fix the 3 call sites to pass `dry_run=False` explicitly, update the 2 test mocks, and fix the integration test assertion.

**Grader:**
```
+0.1  patch applies cleanly
+0.1  all files parse
+0.2  mypy passes
+0.2  unit tests pass (both)
+0.2  integration test passes
+0.2  no regressions (full test suite green)
────
1.0   total
```

**Expected frontier model score:** 0.15–0.40
**Why it's hard:** Multi-file, multi-symptom, one root cause. Agent must resist patching symptoms and instead reason about the source of the cascade. Mirrors exactly the kind of PR failure an experienced open source maintainer has seen many times.

---

### 4.2 Track B — SRE Incident Response Tasks

---

#### Task B1: Identify the Noisy Service *(Easy)*

**Scenario:**
PagerDuty fires: "Error rate > 5% on api-gateway." Agent receives a 50-line log stream from 4 services. One service is clearly emitting repeated 500 errors with a stack trace. Agent must identify the correct service name and the error type.

**What the agent sees:**
```
Alert: Error rate threshold exceeded (api-gateway, 5.2%)
Timestamp: 2026-04-05T14:32:11Z

Log Stream (last 2 min):
  [auth-service]     INFO  token validated user_id=8821
  [auth-service]     INFO  token validated user_id=9034
  [api-gateway]      ERROR downstream call failed: timeout after 30s
  [api-gateway]      ERROR downstream call failed: timeout after 30s
  [payment-service]  ERROR NullPointerException at PaymentProcessor.java:87
  [payment-service]  ERROR NullPointerException at PaymentProcessor.java:87
  [payment-service]  ERROR NullPointerException at PaymentProcessor.java:87
  [notification-svc] INFO  email queued for user 9034
  [payment-service]  ERROR NullPointerException at PaymentProcessor.java:87
  ... (40 more lines, same pattern)
```

**What the agent must do:**
Submit action: `{ "root_cause_service": "payment-service", "error_type": "NullPointerException", "affected_line": "PaymentProcessor.java:87" }`

**Grader:**
```
+0.4  correct service identified
+0.3  correct error type
+0.3  correct file/line
────
1.0   total
```

**Expected frontier model score:** 0.80–1.0
**Why it's easy:** The signal is obvious in the logs. Single error type, single file, high repetition.

---

#### Task B2: Trace a Latency Spike Across Services *(Medium)*

**Scenario:**
Alert: "P99 latency on checkout-api > 8s (baseline: 400ms)." Agent receives structured logs from 6 services over a 5-minute window. The root cause is a slow DB query caused by a missing index on a table that was recently migrated. The symptom appears in checkout-api but the cause is in db-proxy.

**What the agent sees:**
```
Alert: checkout-api P99 latency = 8.4s (SLO breach)

Logs available for: [checkout-api, cart-service, db-proxy, 
                     inventory-api, auth-service, cache-layer]

Agent can query: get_logs(service, time_range, filter_keyword)
                 get_metrics(service, metric_name, time_range)
```

The agent must issue multiple `get_logs` / `get_metrics` queries across services to trace the call chain, find that `db-proxy` shows query times of 7–8s on `SELECT * FROM order_items WHERE user_id=?`, and conclude the missing index is the root cause.

**Grader:**
```
+0.1  queries at least 3 different services
+0.2  queries db-proxy specifically
+0.2  identifies db-proxy as root cause service
+0.2  identifies the slow query
+0.3  correct remediation action submitted
       (acceptable: "add index on order_items.user_id" or "run ANALYZE on order_items")
────
1.0   total
```

**Expected frontier model score:** 0.40–0.65
**Why it's medium:** Multi-service, multi-step investigation. Agent must query iteratively — can't get the answer from a single log read.

---

#### Task B3: Diagnose a Memory Leak Under Load *(Hard)*

**Scenario:**
Alert: "worker-pool OOMKilled 3 times in 20 minutes." Agent has access to: application logs, container metrics (memory over time), heap dump summary, recent deployment history, and the diff of the last 2 deployments. Root cause: a new background job introduced in the last deploy holds references to processed objects indefinitely (a classic Python/Ruby object retention bug). There is no error in the logs — the service just silently grows until it's killed.

**What the agent sees:**
```
Alert: worker-pool OOMKilled (3 occurrences, last 20 min)
       Container memory: grew from 200MB → 1.8GB over 18 minutes
       No error logs. Pod restarts cleanly each time.

Available tools:
  get_metrics(service, metric, time_range)
  get_deployment_history(service, n_recent)
  get_diff(deploy_id)
  get_heap_summary(service, timestamp)
  get_logs(service, time_range, level)
```

The agent must: (1) check deployment history and find the suspicious deploy, (2) read the diff and identify the background job, (3) read the heap summary to confirm object retention, (4) submit the correct diagnosis and fix recommendation.

**Grader:**
```
+0.1  queries deployment history
+0.1  fetches the correct diff
+0.2  identifies the background job as the source
+0.2  confirms via heap summary (object count growing)
+0.2  correct root cause diagnosis submitted
+0.2  correct fix recommendation
       (acceptable: "clear processed_items list in job teardown"
        or "use weakref" or "explicitly del references after processing")
────
1.0   total
```

**Expected frontier model score:** 0.10–0.30
**Why it's hard:** No error in the logs — agent can't just grep for ERROR. Must reason across multiple data sources (metrics + diff + heap). The bug is subtle. This is the kind of incident that takes a senior SRE 45 minutes to diagnose in real life.

---

## 5. Observation & Action Spaces

### 5.1 Unified Observation (Both Tracks)

```python
@dataclass
class DevReliabilityObservation(Observation):
    done: bool
    reward: Optional[float]

    # Task context
    task_id: str                        # e.g. "ci_easy", "sre_hard"
    track: str                          # "ci" or "sre"
    difficulty: str                     # "easy", "medium", "hard"

    # The broken system
    description: str                    # Human-readable task description
    context: Dict[str, Any]            # PR diff / alert details / deployment info

    # Current state of the episode
    available_actions: List[str]        # What the agent can do right now
    tool_results: Optional[str]         # Results of last tool call (SRE track)
    ci_output: Optional[str]           # Current CI run output (CI track)
    checks_passing: Optional[int]      # How many checks are currently green
    checks_total: Optional[int]        # Total CI checks

    # Episode metadata
    step_count: int
    max_steps: int
    feedback: str                       # Feedback from last action
```

### 5.2 Action Space

**CI Track Actions:**
```python
@dataclass
class CIAction(Action):
    action_type: str    # "submit_patch" | "read_file" | "run_check"
    payload: Dict[str, Any]

# Examples:
CIAction(action_type="read_file",    payload={"path": "src/utils.py"})
CIAction(action_type="submit_patch", payload={"file": "src/utils.py", "patch": "..."})
CIAction(action_type="run_check",    payload={"check": "lint"})
```

**SRE Track Actions:**
```python
@dataclass
class SREAction(Action):
    action_type: str    # "get_logs" | "get_metrics" | "get_diff" |
                        # "get_heap_summary" | "get_deployment_history" |
                        # "submit_diagnosis" | "submit_remediation"
    payload: Dict[str, Any]

# Examples:
SREAction(action_type="get_logs",    payload={"service": "payment-service", "level": "ERROR"})
SREAction(action_type="get_metrics", payload={"service": "worker-pool", "metric": "memory"})
SREAction(action_type="submit_diagnosis", payload={"root_cause": "...", "fix": "..."})
```

---

## 6. Reward Function

### 6.1 Principles
- **Never binary.** Every step provides signal.
- **Reward investigation.** Taking the right exploratory actions earns partial credit.
- **Reward efficiency.** Fewer steps to the same result = higher total reward.
- **Penalize thrashing.** Submitting the same wrong patch twice = penalty.

### 6.2 Reward Shaping (CI Track)

```
Per step:
  patch applies cleanly           +0.10
  code parses after patch         +0.10
  new check goes green            +0.20 each
  all checks green (done)         +0.40 bonus
  repeated identical patch        -0.10 penalty
  patch breaks previously green   -0.15 penalty

Step efficiency bonus:
  solved in 1 step                +0.10
  solved in 2 steps               +0.05
  solved in 3+ steps              +0.00
```

### 6.3 Reward Shaping (SRE Track)

```
Per step:
  queries a new relevant service  +0.05
  queries the root cause service  +0.15
  correct error type identified   +0.15
  correct root cause submitted    +0.30
  correct fix/remediation         +0.35
  querying irrelevant services    +0.00 (no penalty, but no reward)
  wrong root cause submitted      -0.10 penalty
  repeated identical query        -0.05 penalty
```

---

## 7. State Management

```python
@dataclass
class DevReliabilityState(State):
    episode_id: Optional[str] = None
    step_count: int = 0
    track: str = ""                     # "ci" or "sre"
    task_id: str = ""
    difficulty: str = ""

    # CI track state
    current_files: Dict[str, str] = field(default_factory=dict)   # filename → content
    patches_applied: List[str] = field(default_factory=list)
    checks_status: Dict[str, bool] = field(default_factory=dict)  # check → passing

    # SRE track state
    queries_made: List[str] = field(default_factory=list)
    services_investigated: List[str] = field(default_factory=list)
    diagnosis_submitted: bool = False
    remediation_submitted: bool = False

    # Episode control
    max_steps: int = 10
    done: bool = False
    final_score: float = 0.0
```

---

## 8. Project Structure

```
dev-reliability-env/
├── inference.py                        ← HACKATHON: baseline script (root)
├── openenv.yaml                        ← Manifest
├── Dockerfile                          ← Container
├── requirements.txt
├── README.md
│
├── models.py                           ← Pydantic/dataclass types
├── client.py                           ← HTTPEnvClient subclass
│
├── server/
│   ├── app.py                          ← create_fastapi_app(DevReliabilityEnvironment)
│   ├── environment.py                  ← Main environment: reset/step/state
│   ├── ci_engine.py                    ← Simulated CI runner (lint, test, type check)
│   ├── sre_engine.py                   ← Simulated log/metrics/heap query system
│   └── reward.py                       ← Reward computation
│
├── tasks/
│   ├── ci/
│   │   ├── easy_lint_failure.py        ← Task A1 definition + grader
│   │   ├── medium_test_failure.py      ← Task A2 definition + grader
│   │   └── hard_cascading_failure.py   ← Task A3 definition + grader
│   └── sre/
│       ├── easy_noisy_service.py       ← Task B1 definition + grader
│       ├── medium_latency_trace.py     ← Task B2 definition + grader
│       └── hard_memory_leak.py        ← Task B3 definition + grader
│
└── data/
    ├── ci_scenarios/                   ← Pre-written broken codebases (JSON)
    │   ├── scenario_lint_001.json
    │   ├── scenario_test_001.json
    │   └── scenario_cascade_001.json
    └── sre_scenarios/                  ← Pre-written incident scenarios (JSON)
        ├── scenario_noisy_001.json
        ├── scenario_latency_001.json
        └── scenario_memleak_001.json
```

---

## 9. Technical Implementation Notes

### 9.1 CI Simulation (No Real Execution Needed)
The CI engine does **not** actually run Python/lint tools. Instead:
- Each scenario has a pre-defined set of "checks" and their pass/fail conditions
- A patch is evaluated by string matching / AST parsing against the expected fix
- The grader checks structural correctness, not live execution

This keeps the environment deterministic, fast, and within the 2vCPU/8GB constraint.

```python
class CIEngine:
    def apply_patch(self, scenario, patch) -> CIResult:
        # Apply patch to in-memory file content
        # Run pre-defined check functions
        # Return which checks pass/fail + output strings
        ...
```

### 9.2 Log/Metrics Simulation (SRE Track)
Logs and metrics are pre-generated JSON datasets, not live systems:
```python
class SREEngine:
    def get_logs(self, service, time_range, level=None) -> str:
        # Return slice of pre-generated log dataset
        # Filtered by service, time, level
        ...

    def get_metrics(self, service, metric, time_range) -> Dict:
        # Return pre-generated metric timeseries
        ...
```

### 9.3 Episode Isolation
Each `reset()` call:
- Generates a fresh `episode_id`
- Selects a scenario from the task's scenario pool
- Resets all state (files, patches, queries made)
- Returns a clean initial observation

No state leaks between episodes.

### 9.4 Scenario Variety
Each task has **multiple scenario variants** (at least 3 per task). The environment randomly selects one on `reset()`. This prevents agents from memorizing answers and ensures the grader evaluation is meaningful.

---

## 10. openenv.yaml

```yaml
name: dev-reliability-env
version: "1.0.0"
description: >
  CI debugging and SRE incident response environment.
  Agents fix failing GitHub Actions builds and diagnose
  production incidents from logs and metrics.
author: piyush
tags:
  - openenv
  - real-world
  - software-engineering
  - devops
  - sre
  - ci-cd

tasks:
  - id: ci_easy
    track: ci
    difficulty: easy
    description: "Fix a failing lint check in a single file"
    max_steps: 5

  - id: ci_medium
    track: ci
    difficulty: medium
    description: "Fix a broken unit test caused by a refactor"
    max_steps: 8

  - id: ci_hard
    track: ci
    difficulty: hard
    description: "Fix a cascading multi-file failure from a signature change"
    max_steps: 10

  - id: sre_easy
    track: sre
    difficulty: easy
    description: "Identify the noisy service from a log stream"
    max_steps: 5

  - id: sre_medium
    track: sre
    difficulty: medium
    description: "Trace a latency spike across 6 services"
    max_steps: 10

  - id: sre_hard
    track: sre
    difficulty: hard
    description: "Diagnose a memory leak from metrics, diff, and heap data"
    max_steps: 12
```

---

## 11. README Outline (For Submission)

```
# DevReliability-Env

## What This Is
## Motivation
## Observation Space
## Action Space
## Tasks
  ### CI Track
  ### SRE Track
## Reward Function
## Setup & Usage
  ### Local
  ### Docker
  ### HF Space
## Baseline Scores
## Environment Design Notes
```

---

## 12. Build Plan (April 1–8)

| Day | Date | Goal |
|---|---|---|
| 0 | Mar 29–31 | Finalize design, scaffold project, write models.py + environment.py skeleton |
| 1 | Apr 1 | Implement CI engine + 3 CI scenarios (JSON data) |
| 2 | Apr 2 | Implement CI graders (A1, A2, A3) + test them |
| 3 | Apr 3 | Implement SRE engine + 3 SRE scenarios (JSON data) |
| 4 | Apr 4 | Implement SRE graders (B1, B2, B3) + test them |
| 5 | Apr 5 | Wire FastAPI app, client.py, full reset/step/state loop |
| 6 | Apr 6 | Write inference.py, run baseline, openenv validate |
| 7 | Apr 7 | Dockerfile, HF Space deploy, README with baseline scores |
| 8 | Apr 8 | Buffer — fix issues, submit URL before 11:59 PM IST |

---

## 13. Baseline Score Targets

| Task | Expected Baseline Score | Notes |
|---|---|---|
| ci_easy | 0.85 | Frontier model should almost always solve lint |
| ci_medium | 0.55 | Requires semantic reasoning about test↔impl |
| ci_hard | 0.25 | Multi-file cascade, most models partially fix |
| sre_easy | 0.80 | Signal is obvious in logs |
| sre_medium | 0.50 | Multi-step investigation needed |
| sre_hard | 0.20 | No error in logs, requires cross-source reasoning |
| **Overall** | **~0.52** | Healthy spread, not too easy, not unsolvable |

---

## 14. What Makes This Hard to Copy

1. **Domain specificity** — the CI failure scenarios are modeled on real failure modes from actual open source PRs (Rage, Talawa). They're not generic textbook examples.

2. **Two-track design** — combining CI + SRE in one environment is not obvious. It requires understanding that these are the same underlying loop at different layers of the stack.

3. **Grader design** — the layered partial-credit graders (especially for SRE) require careful thought about what "partial progress" means in an investigation task. This is non-trivial to get right.

4. **Scenario data** — the pre-written scenarios (JSON) are the real moat. Anyone can copy the architecture. No one can easily replicate realistic CI failure logs and production incident data without the experience to know what real ones look like.
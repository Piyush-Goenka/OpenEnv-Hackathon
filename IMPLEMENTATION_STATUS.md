# DevReliability-Env Implementation Status

This document is the working execution tracker for the project.
It is based on:

- [deliverable.md](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/deliverable.md)
- [guide.md](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/guide.md)
- [README.md](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/README.md)
- the current codebase under `server/`, `tasks/`, `data/`, and `tests/`

It separates:

- what the project is supposed to be
- what has already been implemented
- what is still missing before the environment is truly submission-ready
- what workflows and test cases are required

## 1. Problem Statement

The hackathon requires building an **OpenEnv environment** that an agent can interact with through:

- `reset()`
- `step(action)`
- `state()`

The environment must simulate a real-world task, assign deterministic rewards, provide partial credit, and be deployable as a Dockerized service for local use and Hugging Face Spaces deployment.

For this project, the environment is:

- **Name:** `dev-reliability-env`
- **Domain:** software reliability workflows
- **Tracks:** CI debugging and SRE incident response

The environment is meant to train or evaluate an agent on two real operational loops:

1. A developer receives a broken PR and failing CI logs, then must fix the code.
2. An SRE receives a production alert and must investigate logs, metrics, deployment history, and other debugging signals to diagnose and remediate the issue.

## 2. Source-of-Truth Expectations

### From `guide.md`

- The environment must expose exactly `reset()`, `step()`, and `state()`.
- A root-level `inference.py` is mandatory.
- `inference.py` must use the OpenAI client and read:
  - `API_BASE_URL`
  - `MODEL_NAME`
  - `HF_TOKEN`
- Graders must be deterministic.
- Scores must stay in the `0.0` to `1.0` range.
- Partial credit is required.
- Docker build/run must work.
- `openenv validate` must pass.
- HF Space must respond successfully.
- The environment should run within the hackathon runtime and resource constraints.
- The guide only mandates `API_BASE_URL`, `MODEL_NAME`, and `HF_TOKEN`, but the current implementation also reads:
  - `ENV_BASE_URL`
  - `TASK_IDS`
  These are convenience variables with defaults, not extra submission requirements.

### From `deliverable.md`

- The environment has **two tracks**:
  - `ci`
  - `sre`
- The environment has **six tasks**:
  - `ci_easy`
  - `ci_medium`
  - `ci_hard`
  - `sre_easy`
  - `sre_medium`
  - `sre_hard`
- CI is simulated, not executed against real tools.
- SRE investigation is simulated from pre-generated data, not live infra.
- Each task should have **multiple scenario variants**.
- Reward shaping should reflect investigation progress, not only final success.
- The final README should include usage, environment design, and baseline scores.

### From `README.md`

- The intended repo structure is already aligned to the `deliverable.md` architecture.
- The current implementation is a starter version and still needs deeper scenario pools and grader tuning.

## 3. High-Level Architecture

The current intended architecture is:

1. `models.py`
   - defines action, observation, and state objects

2. `client.py`
   - defines the typed environment client

3. `server/environment.py`
   - orchestrates `reset()`, `step()`, and state updates
   - routes by track to the correct engine

4. `server/ci_engine.py`
   - simulates CI workflows

5. `server/sre_engine.py`
   - simulates SRE workflows

6. `server/reward.py`
   - central reward shaping logic

7. `tasks/`
   - declares task metadata and scenario selection

8. `data/`
   - holds the scenario fixtures

9. `inference.py`
   - baseline model runner for hackathon evaluation

## 4. What Has Been Done

### Repository Structure

- [x] Root-level [Dockerfile](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/Dockerfile) added.
- [x] Root-level [inference.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/inference.py) added.
- [x] Root-level [openenv.yaml](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/openenv.yaml) added and aligned with 6 tasks.
- [x] Root-level [README.md](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/README.md) updated to reflect the DevReliability environment.
- [x] Root-level [Makefile](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/Makefile) added for common workflows.
- [x] Root-level [.env.example](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/.env.example) added.

### Runtime Code

- [x] [models.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/models.py) defines:
  - `DevReliabilityAction`
  - `DevReliabilityObservation`
  - `DevReliabilityState`
- [x] [client.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/client.py) defines `DevReliabilityEnv`.
- [x] [server/app.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/server/app.py) wires the environment into FastAPI/OpenEnv.
- [x] [server/environment.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/server/environment.py) implements:
  - task selection
  - track routing
  - episode reset
  - step handling
  - observation building
  - state accumulation
- [x] [inference.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/inference.py) currently reads:
  - required hackathon variables:
    - `API_BASE_URL`
    - `MODEL_NAME`
    - `HF_TOKEN`
  - convenience variables with defaults:
    - `ENV_BASE_URL`
    - `TASK_IDS`

### CI Track Scaffolding

- [x] [server/ci_engine.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/server/ci_engine.py) exists.
- [x] CI actions currently supported:
  - `read_file`
  - `run_check`
  - `submit_patch`
- [x] CI patch handling currently supports:
  - patch submission tracking
  - repeated patch detection
  - reward calculation for newly passing checks
  - per-check output aggregation
- [x] CI tasks are declared:
  - [tasks/ci/easy_lint_failure.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tasks/ci/easy_lint_failure.py)
  - [tasks/ci/medium_test_failure.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tasks/ci/medium_test_failure.py)
  - [tasks/ci/hard_cascading_failure.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tasks/ci/hard_cascading_failure.py)
- [x] One starter CI scenario exists for each task:
  - [data/ci_scenarios/scenario_lint_001.json](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/data/ci_scenarios/scenario_lint_001.json)
  - [data/ci_scenarios/scenario_test_001.json](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/data/ci_scenarios/scenario_test_001.json)
  - [data/ci_scenarios/scenario_cascade_001.json](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/data/ci_scenarios/scenario_cascade_001.json)

### SRE Track Scaffolding

- [x] [server/sre_engine.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/server/sre_engine.py) exists.
- [x] SRE actions currently supported:
  - `get_logs`
  - `get_metrics`
  - `get_diff`
  - `get_heap_summary`
  - `get_deployment_history`
  - `submit_diagnosis`
  - `submit_remediation`
- [x] SRE query reward hooks exist for:
  - repeated query penalty
  - relevant-service reward
  - root-cause-service reward
  - deployment history reward
  - diff reward
  - heap summary reward
- [x] SRE tasks are declared:
  - [tasks/sre/easy_noisy_service.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tasks/sre/easy_noisy_service.py)
  - [tasks/sre/medium_latency_trace.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tasks/sre/medium_latency_trace.py)
  - [tasks/sre/hard_memory_leak.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tasks/sre/hard_memory_leak.py)
- [x] One starter SRE scenario exists for each task:
  - [data/sre_scenarios/scenario_noisy_001.json](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/data/sre_scenarios/scenario_noisy_001.json)
  - [data/sre_scenarios/scenario_latency_001.json](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/data/sre_scenarios/scenario_latency_001.json)
  - [data/sre_scenarios/scenario_memleak_001.json](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/data/sre_scenarios/scenario_memleak_001.json)
- [x] `sre_hard` is currently the strongest starter scenario.
  - It already includes deployment history, multiple diffs, heap evidence, distractors, and a diagnosis-plus-remediation requirement.
  - It should be treated as the quality bar for future scenario additions.

### Reward Layer

- [x] [server/reward.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/server/reward.py) exists.
- [x] CI reward helpers exist.
- [x] SRE reward helpers exist.
- [x] Scores are clamped into `0.0` to `1.0`.

### Registry and Metadata

- [x] [tasks/registry.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tasks/registry.py) registers all 6 tasks.
- [x] Task filtering by track exists.
- [x] Default task exists.

### Tests and Verification Already Added

- [x] [tests/test_repo_layout.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tests/test_repo_layout.py) verifies expected file layout.
- [x] [tests/test_task_registry.py](/Users/piyushgoenka/Desktop/Agents/OpenEnv-Hackathon/tests/test_task_registry.py) verifies task registration basics.
- [x] Python compile check has already passed.
- [x] Current unit tests have already passed.
- [x] Scenario JSON files have already passed JSON validation.

## 5. What Is Not Done Yet

This section is the real gap analysis.

### Critical Gaps Against `deliverable.md`

- [x] Each task needs at least **3 scenario variants**.
  - Status: 001, 002, and 003 exist for all 6 tasks (18 total scenarios).
- [x] The CI graders are still relatively shallow.
  - Status: Fixed. `ci_engine.py` now gates all checks using real `ast.parse()` and uses structural validators (e.g., real `ruff` linting).
- [ ] The SRE investigation logic is still relatively shallow.
  - Current implementation checks direct query/diagnosis/remediation conditions.
  - Missing deeper workflow validation for multi-step reasoning quality.
- [ ] The current README is still not a true submission README.
- [ ] The baseline score targets in `deliverable.md` have not been validated.
- [ ] `openenv validate` has not been run yet.
- [ ] Docker build/run has not been tested yet after the refactor.
- [ ] HF Space deployment has not been done yet.
- [ ] End-to-end inference baseline has not been run against the environment server yet.

### CI-Track Specific Gaps

- [x] Support richer patch validation beyond string-token heuristics. (Done via structural validators and AST parsing)
- [ ] Support multi-file patch semantics more explicitly for `ci_hard`.
- [x] Verify that both valid fix paths for `ci_medium` work:
  - implementation fix
  - test fix
- [x] Fix the `ci_medium` regression-guard duplication first.
  - Status: Fixed. Regression guard now strictly requires list-returning implementation, differentiating partial-credit test fixes.
- [x] Add regression scenarios where partial fixes should not accidentally pass the full suite.
- [x] Add more realistic CI output variations to reduce memorization. (Done via 3 variants per task)

### SRE-Track Specific Gaps

- [ ] Reward “good investigation path” more explicitly for `sre_medium`.
- [x] Ensure `sre_medium` requires cross-service investigation, not one lucky guess.
- [x] Deepen `sre_medium` scenario data.
  - Status: Fixed. `scenario_latency_001.json` now includes deployment history, diffs, distractor logs, and timestamped metrics.
- [ ] Ensure `sre_hard` requires deployment history + diff + heap confirmation.
- [x] Add more scenario diversity for:
  - different services
  - different queries
  - different accepted remediations
  (Done via 3 variants per task)
- [x] Add “irrelevant but plausible” data so the tasks are not trivially pattern-matched. (Added to new scenarios)

### Testing Gaps

- [ ] No direct unit tests for `server/ci_engine.py`.
- [ ] No direct unit tests for `server/sre_engine.py`.
- [ ] No direct unit tests for `server/environment.py`.
- [ ] No tests for reward helper behavior in `server/reward.py`.
- [ ] No tests for `inference.py` prompt generation or action parsing.
- [ ] No end-to-end tests covering `reset -> step -> state`.
- [ ] No tests for scenario randomization with stable seeds.
- [ ] No tests for max-step termination behavior.
- [ ] No tests for state isolation between episodes.

## 6. Required Workflows

### CI Episode Workflow

This is the expected agent flow for CI tasks:

1. `reset(task_id="ci_*")`
2. Receive:
   - task description
   - PR diff
   - failing CI output
   - relevant files
3. Optional investigation:
   - `read_file`
   - `run_check`
4. Submit patch:
   - `submit_patch`
5. Environment evaluates:
   - whether patch applied
   - whether structure still looks valid
   - which checks passed
   - whether previous green checks regressed
6. Environment returns:
   - reward
   - feedback
   - updated CI output
   - check counts
7. Loop until:
   - all checks green
   - or max steps reached

### SRE Episode Workflow

This is the expected agent flow for SRE tasks:

1. `reset(task_id="sre_*")`
2. Receive:
   - alert summary
   - service catalog
   - initial log excerpt
3. Investigate with tools:
   - `get_logs`
   - `get_metrics`
   - `get_deployment_history`
   - `get_diff`
   - `get_heap_summary`
4. Submit:
   - `submit_diagnosis`
   - optionally `submit_remediation`
5. Environment evaluates:
   - relevance of investigation
   - whether root cause fields are correct
   - whether remediation matches accepted actions
6. Loop until:
   - diagnosis/remediation is sufficient
   - or max steps reached

### Local Development Workflow

1. Create a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Run `make test`.
4. Run `make run`.
5. Manually call:
   - `/health`
   - `/reset`
   - `/step`
   - `/state`
6. Run `make infer`.
7. Iterate on scenarios and rewards.

### Submission Workflow

1. Complete task logic and tests.
2. Run `openenv validate`.
3. Build Docker image.
4. Run container locally on port `7860`.
5. Run `inference.py` end to end.
6. Capture baseline scores.
7. Finalize README.
8. Deploy to Hugging Face Spaces.
9. Re-run health checks and inference against the deployed Space.
10. Submit the Space URL before the deadline.

## 7. Required Test Cases

This is the test matrix the project still needs.

### Repo and Metadata Tests

- [x] Required files exist.
- [x] Task registry contains all tasks.
- [ ] `openenv.yaml` fields match task registry exactly.
- [ ] Root `inference.py` imports and configuration handling are stable.
- [ ] `inference.py` handles both mandatory hackathon env vars and convenience env vars correctly.

### CI Engine Tests

#### `ci_easy`

- [ ] `read_file` returns the target file content.
- [ ] `run_check("lint")` returns the failing output before fix.
- [ ] Correct patch makes `lint` pass.
- [ ] Empty patch gives no positive reward.
- [ ] Repeating the same wrong patch applies penalty.
- [ ] Incorrect file path returns a useful error.

#### `ci_medium`

- [ ] Implementation-based fix is accepted.
- [ ] Test-based fix is accepted.
- [ ] Redesign the current regression guard so it is meaningfully different from the target-test success condition.
- [ ] Partial fix passes target test but not regression guard when appropriate.
- [ ] Correct fix turns all required checks green.
- [ ] Previously green checks regressing triggers penalty.

#### `ci_hard`

- [ ] Fixing only call sites gives partial credit, not full success.
- [ ] Fixing only mocks gives partial credit, not full success.
- [ ] Fixing only integration assertion gives partial credit, not full success.
- [ ] Correct multi-file patch gives full success.
- [ ] Full suite remains red until all required dimensions are addressed.

### SRE Engine Tests

#### `sre_easy`

- [ ] `get_logs("payment-service")` returns the relevant repeated errors.
- [ ] Correct service gets partial credit.
- [ ] Correct error type gets partial credit.
- [ ] Correct affected line gets partial credit.
- [ ] Full diagnosis yields completion.

#### `sre_medium`

- [ ] Querying a new relevant service gets reward.
- [ ] Querying `db-proxy` gets root-cause-service reward.
- [ ] Repeated identical query gets penalty.
- [ ] Wrong diagnosis gets penalty.
- [ ] Correct remediation closes the task.

#### `sre_hard`

- [ ] `get_deployment_history` exposes the suspicious deploy.
- [ ] `get_diff` for the correct deploy gets rewarded.
- [ ] `get_heap_summary` for the right timestamp gets rewarded.
- [ ] Diagnosis without remediation does not finish the task when remediation is required.
- [ ] Accepted remediation variants are recognized.

### Environment Integration Tests

- [ ] `reset(task_id="ci_easy")` returns a CI observation with correct available actions.
- [ ] `reset(task_id="sre_easy")` returns an SRE observation with correct available actions.
- [ ] `step()` before `reset()` raises the intended error.
- [ ] State updates after each step.
- [ ] `final_score` accumulates rewards correctly.
- [ ] Episode ends correctly at max steps.
- [ ] Episode state does not leak across resets.
- [ ] Seeded reset gives deterministic scenario selection.

### Inference and Client Tests

- [ ] `client.py` parses server payloads correctly.
- [ ] `inference.py` builds CI prompts correctly.
- [ ] `inference.py` builds SRE prompts correctly.
- [ ] `inference.py` parses valid JSON actions correctly.
- [ ] `inference.py` fallback behavior is safe for malformed model output.

### Manual / End-to-End Checks

- [ ] `make run` starts the app without import/runtime errors.
- [ ] `/health` responds successfully.
- [ ] `/reset` works for all 6 tasks.
- [ ] `/step` works for representative CI and SRE actions.
- [ ] `/state` returns valid episode metadata.
- [ ] `make infer` completes end to end.
- [ ] `docker build` succeeds.
- [ ] `docker run` succeeds.
- [ ] `openenv validate` succeeds.

## 8. Recommended Execution Order From Here

### Phase 1: Strengthen CI Track

- [x] Fix the `ci_medium` regression-guard duplication before adding more CI variants.
- [x] Add `002` and `003` variants for:
  - `ci_easy`
  - `ci_medium`
  - `ci_hard`
- [ ] Add CI engine unit tests.
- [x] Tighten token-matching logic so medium/hard tasks need coherent fixes.
- [ ] Validate CI partial-credit behavior against expected score ranges.

### Phase 2: Strengthen SRE Track

- [x] Add `002` and `003` variants for:
  - `sre_easy`
  - `sre_medium`
  - `sre_hard`
- [ ] Add SRE engine unit tests.
- [ ] Strengthen query-path logic for medium and hard investigations.
- [ ] Validate SRE partial-credit behavior against expected score ranges.

### Phase 3: End-to-End Hardening

- [ ] Add environment integration tests.
- [ ] Add inference tests.
- [ ] Run local server manually.
- [ ] Run full baseline inference.
- [ ] Tune rewards to match target score spread.

### Phase 4: Submission Hardening

- [ ] Expand README into a proper submission document.
- [ ] Run `openenv validate`.
- [ ] Run Docker locally.
- [ ] Deploy to HF Spaces.
- [ ] Capture baseline scores and document them.

## 9. Current Honest Status

The project is **structurally well-scaffolded** and already aligned to the intended architecture.
The repo now has:

- the right file layout
- the right task inventory
- the right engines
- the right scenario categories
- the right top-level manifest and baseline runner

But it is **not yet finished as a hackathon submission**.

While the **behavioral depth, scenarios, and graders** have been significantly improved (with real AST/ruff validation, 18 scenarios, and deepened SRE content), the remaining gaps are primarily around **testing and deployment**:

- deeper engine tests
- actual end-to-end validation
- deployment and baseline score evidence
- rewriting the README for submission

The grading quality risk has been mitigated by the new structural validator framework in the CI engine and the deeper, evidence-based scenario requirements in the SRE engine.

That is the remaining project: testing, documentation, and deployment.

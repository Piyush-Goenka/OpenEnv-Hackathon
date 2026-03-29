# Hackathon Requirements & Deliverables Checklist

> **Deadline:** April 8, 2026, 11:59 PM IST
> **This file tracks every requirement from the problem statement. Nothing can be missed.**

---

## Disqualification Gate (ALL must pass — Phase 1 Automated Validation)

- [ ] HF Space deploys and returns HTTP 200
- [ ] HF Space responds successfully to `reset()`
- [ ] `openenv validate` passes (validates openenv.yaml, typed models, endpoints)
- [ ] `docker build` succeeds on the submitted repo
- [ ] `docker run` starts and serves the environment
- [ ] `inference.py` runs end-to-end without error
- [ ] `inference.py` produces scores for all tasks
- [ ] 3+ tasks with graders (we have 6)
- [ ] Grader scores are in 0.0–1.0 range
- [ ] Graders are NOT constant (different inputs → different scores)
- [ ] Environment is NOT plagiarized or trivially modified from existing envs

---

## Functional Requirements

### OpenEnv Spec Compliance

- [ ] Typed `Action` Pydantic model (`DevReliabilityAction`)
- [ ] Typed `Observation` Pydantic model (`DevReliabilityObservation`)
- [ ] Typed `State` Pydantic model (`DevReliabilityState`)
- [ ] `step(action)` → returns observation, reward, done
- [ ] `reset()` → returns initial observation
- [ ] `state()` → returns current state
- [ ] `openenv.yaml` present with metadata and task list
- [ ] `openenv validate` passes

### Tasks & Graders

- [ ] Minimum 3 tasks (we have 6 — exceeds requirement)
- [ ] Tasks range from easy → medium → hard
- [ ] Each task has a programmatic grader
- [ ] Graders produce deterministic scores (0.0–1.0)
- [ ] Graders have clear success/failure criteria
- [ ] Hard task genuinely challenges frontier models

#### CI Track Tasks
- [ ] `ci_easy` — Fix lint failure (expected baseline: 0.85–1.0)
- [ ] `ci_medium` — Fix broken unit test (expected baseline: 0.55–0.75)
- [ ] `ci_hard` — Fix cascading multi-file failure (expected baseline: 0.15–0.40)

#### SRE Track Tasks
- [ ] `sre_easy` — Identify noisy service (expected baseline: 0.80–1.0)
- [ ] `sre_medium` — Trace latency spike (expected baseline: 0.40–0.65)
- [ ] `sre_hard` — Diagnose memory leak (expected baseline: 0.10–0.30)

### Reward Function

- [ ] Provides signal over full trajectory (not just binary end-of-episode)
- [ ] Rewards partial progress toward task completion
- [ ] Penalizes undesirable behavior (repeated actions, regressions)
- [ ] CI: patch applies (+0.10), parses (+0.10), checks green (+0.20 each), all green (+0.40), efficiency bonus
- [ ] CI: repeated patch penalty (-0.10), regression penalty (-0.15)
- [ ] SRE: new relevant service (+0.05), root cause service (+0.15), deployment history (+0.10)
- [ ] SRE: correct diff (+0.10), heap summary (+0.20), repeated query penalty (-0.05)
- [ ] SRE: diagnosis weighted per-field, wrong diagnosis penalty (-0.10)
- [ ] SRE: correct remediation (+0.35)
- [ ] Scores always clamped to 0.0–1.0

### Baseline Inference Script

- [ ] Named `inference.py` in root directory
- [ ] Uses OpenAI API client for all LLM calls
- [ ] Reads `API_BASE_URL` from env (default: `https://router.huggingface.co/v1`)
- [ ] Reads `MODEL_NAME` from env
- [ ] Reads `HF_TOKEN` from env (or `API_KEY`)
- [ ] Produces reproducible baseline scores on all tasks
- [ ] Runtime < 20 minutes on 2vCPU / 8GB RAM

### Scenario Variety

- [ ] Each task has at least 3 scenario variants
- [ ] `data/ci_scenarios/scenario_lint_001.json` ✅
- [ ] `data/ci_scenarios/scenario_lint_002.json`
- [ ] `data/ci_scenarios/scenario_lint_003.json`
- [ ] `data/ci_scenarios/scenario_test_001.json` ✅
- [ ] `data/ci_scenarios/scenario_test_002.json`
- [ ] `data/ci_scenarios/scenario_test_003.json`
- [ ] `data/ci_scenarios/scenario_cascade_001.json` ✅
- [ ] `data/ci_scenarios/scenario_cascade_002.json`
- [ ] `data/ci_scenarios/scenario_cascade_003.json`
- [ ] `data/sre_scenarios/scenario_noisy_001.json` ✅
- [ ] `data/sre_scenarios/scenario_noisy_002.json`
- [ ] `data/sre_scenarios/scenario_noisy_003.json`
- [ ] `data/sre_scenarios/scenario_latency_001.json` ✅
- [ ] `data/sre_scenarios/scenario_latency_002.json`
- [ ] `data/sre_scenarios/scenario_latency_003.json`
- [ ] `data/sre_scenarios/scenario_memleak_001.json` ✅
- [ ] `data/sre_scenarios/scenario_memleak_002.json`
- [ ] `data/sre_scenarios/scenario_memleak_003.json`

---

## Non-Functional Requirements

### Deployment

- [ ] Working `Dockerfile` in repo
- [ ] `docker build` succeeds cleanly
- [ ] `docker run` starts server on port 7860
- [ ] `/health` endpoint responds
- [ ] `/reset` endpoint responds
- [ ] `/step` endpoint responds
- [ ] `/state` endpoint responds
- [ ] Deployed to HF Space tagged with `openenv`
- [ ] HF Space is public

### Infrastructure Constraints

- [ ] Runs on 2 vCPU / 8 GB RAM
- [ ] Inference runtime < 20 minutes
- [ ] Port: 7860 (HF Spaces default)

### Documentation (README.md)

- [ ] Environment description and motivation
- [ ] Action space definition (table/description)
- [ ] Observation space definition (table/description)
- [ ] Task descriptions with expected difficulty levels
- [ ] Setup and usage instructions (local + Docker + HF Space)
- [ ] Baseline scores for all tasks
- [ ] Reward function description

---

## Scoring Criteria Checklist

### Real-World Utility (30%)
- [ ] Environment models a genuine task humans do daily
- [ ] Would be useful for training/evaluating agents
- [ ] Not a game or toy problem
- [ ] README clearly articulates the real-world value
- [ ] Fills a gap in the OpenEnv ecosystem

### Task & Grader Quality (25%)
- [ ] 3+ tasks with difficulty range
- [ ] Graders produce 0.0–1.0 scores
- [ ] Graders are deterministic and reproducible
- [ ] Hard task genuinely challenges frontier models
- [ ] Multiple valid solutions accepted where appropriate
- [ ] Partial credit at intermediate steps

### Environment Design (20%)
- [ ] `reset()` produces clean state (no episode leakage)
- [ ] Action/observation types are well-designed
- [ ] Reward function provides useful varying signal
- [ ] Episode boundaries are sensible
- [ ] State management is clean

### Code Quality & Spec Compliance (15%)
- [ ] `openenv validate` passes
- [ ] `docker build && docker run` works
- [ ] HF Space deploys and responds
- [ ] Baseline script runs and reproduces scores
- [ ] Clean project structure
- [ ] Typed Pydantic models
- [ ] Tests exist and pass

### Creativity & Novelty (10%)
- [ ] Novel domain (not seen in OpenEnv before)
- [ ] Interesting reward design properties
- [ ] Clever mechanics (two-track, investigation rewarding)
- [ ] README highlights novel aspects

---

## Phase 2: Agentic Evaluation (What Judges Do)

- [ ] Baseline agent is re-run by judges
- [ ] Standard Open LLM agent (e.g., Nemotron 3 Super) is run against environment
- [ ] Score variance is checked (scores should NOT be constant)
- [ ] Environment stability is verified (no crashes during multi-episode runs)

## Phase 3: Human Review (What Meta/HF Engineers Look For)

- [ ] Real-world utility is genuine
- [ ] Creativity stands out
- [ ] No exploits in grading (can't get 1.0 trivially)
- [ ] Code quality is professional
- [ ] Environment design shows thought

---

## Environment Variables (Must Be Configured)

| Variable | Purpose | Default |
|---|---|---|
| `API_BASE_URL` | LLM API endpoint | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | Model identifier | (required, no default) |
| `HF_TOKEN` | Hugging Face / API key | (required, no default) |
| `API_KEY` | Alternative to `HF_TOKEN` | (empty) |
| `ENV_BASE_URL` | Environment server URL | `http://localhost:7860` |
| `TASK_IDS` | Comma-separated task list | `ci_easy,ci_medium,ci_hard,sre_easy,sre_medium,sre_hard` |

---

## Files That Must Exist at Submission

| File | Status |
|---|---|
| `inference.py` (root) | ✅ Exists |
| `openenv.yaml` (root) | ✅ Exists |
| `Dockerfile` (root) | ✅ Exists |
| `requirements.txt` | ✅ Exists |
| `README.md` | ⚠️ Exists but needs rewrite for submission |
| `models.py` | ✅ Exists |
| `client.py` | ✅ Exists |
| `server/app.py` | ✅ Exists |
| `server/environment.py` | ✅ Exists |
| `server/ci_engine.py` | ✅ Exists |
| `server/sre_engine.py` | ✅ Exists |
| `server/reward.py` | ✅ Exists |
| `tasks/` (6 task defs) | ✅ Exists |
| `data/` (scenario JSONs) | ⚠️ Exists but needs 12 more variants |
| `tests/` | ⚠️ Exists but needs more coverage |

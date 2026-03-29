# DevReliability-Env — Full Build Strategy

## 1. How Real OpenEnv Environments Are Built

Every successful OpenEnv environment follows the same proven pattern. Here's what the official environments do, and how we must match them.

### The Pattern: Real Execution, Not Simulation

| Environment | What It Does | How Grading Works |
|---|---|---|
| **Coding Env** | Agent submits Python code | Code is **actually executed** via `PyExecutor`. Grading = real stdout/stderr/exit_code |
| **Chess Env** | Agent submits chess moves | Moves are **validated by python-chess**. Opponent plays via **real moonfish engine** |
| **Wordle/TextArena** | Agent guesses words | Words are **checked against real dictionary**. GREEN/YELLOW/GRAY computed from real comparison |
| **OpenSpiel** | Agent plays board games | **Real DeepMind OpenSpiel** library computes legal moves, game state, winner |
| **Atari** | Agent plays Atari games | **Real ALE emulator** runs game frames |

**The principle:** The grading IS the execution. The environment doesn't check if the agent's answer "looks right" — it runs the answer through a real system and the outcome IS the grade.

### What This Means for Us

Our CI track must move toward **real execution**:
- `ci_easy` → Run real `ruff` on the patched file
- `ci_medium` → Run real `pytest` on the patched code
- `ci_hard` → Run real `mypy` + `pytest` on patched files

Our SRE track's approach is **already correct** — querying logs/metrics/diffs from pre-generated data is faithful to how real SRE investigation works. No one investigates production by running the broken code.

### Standard OpenEnv Project Structure

Every environment follows the exact same skeleton:

```
my_env/
├── models.py                 ← Pydantic types: Action, Observation, State
├── client.py                 ← EnvClient subclass with 3 parsing methods
├── server/
│   ├── environment.py        ← Core: reset(), step(), state property
│   ├── app.py                ← One line: app = create_fastapi_app(MyEnv)
│   └── [engine files]        ← Domain-specific logic
├── openenv.yaml              ← Manifest
├── Dockerfile                ← Python 3.11-slim, uvicorn on port 7860
├── requirements.txt          ← Dependencies
├── inference.py              ← Root-level baseline LLM script
└── README.md                 ← Submission docs
```

We already have this structure. The work is in the engine quality, not the scaffolding.

---

## 2. The Build Plan — Maximum Velocity

### Block A: Make It Actually Run (First Priority)

Everything else is worthless if the environment doesn't deploy.

**A1. Verify Docker locally**
```bash
docker build -t dev-reliability-env .
docker run --rm -p 7860:7860 dev-reliability-env
# In another terminal:
curl http://localhost:7860/health
```

**A2. Verify reset/step/state work via HTTP**
```bash
# Reset
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" \
  -d '{"task_id": "ci_easy"}'

# Step
curl -X POST http://localhost:7860/step -H "Content-Type: application/json" \
  -d '{"action_type": "read_file", "payload": {"path": "src/utils.py"}}'
```

**A3. Run `openenv validate`**
```bash
pip install openenv-core
openenv validate
```

**A4. Run inference.py E2E**
```bash
# Start server in one terminal
make run

# Run inference in another
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=<your-model>
export HF_TOKEN=<your-token>
python inference.py
```

**A5. Deploy to HF Spaces**
```bash
openenv push --repo-id <your-username>/dev-reliability-env
```

### Block B: Make Graders Real (Highest Scoring Impact)

This block addresses the #1 scoring gap. We go from token-matching to real execution.

**B1. Add `ruff` to requirements and Dockerfile**

Add `ruff>=0.11.0` to `requirements.txt`. The Dockerfile already installs from requirements.txt.

**B2. Real lint grading for `ci_easy`**

Replace token matching in `ci_engine.py` with real `ruff` execution:

```python
import ast
import subprocess
import tempfile
import os

def _evaluate_patch_with_real_tools(self, scenario, patch, file_path):
    """Grade a CI patch using real tools instead of token matching."""
    results = {"patch_applies": bool(patch.strip()), "parses": False, "checks": {}}
    
    # Step 1: Does it parse as valid Python?
    try:
        ast.parse(patch)
        results["parses"] = True
    except SyntaxError:
        return results
    
    # Step 2: Run real ruff lint check
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write the patched file
        file_basename = os.path.basename(file_path) if file_path else "patched.py"
        tmp_path = os.path.join(tmpdir, file_basename)
        with open(tmp_path, "w") as f:
            f.write(patch)
        
        # Run ruff
        try:
            result = subprocess.run(
                ["ruff", "check", tmp_path, "--select", "E,F,I"],
                capture_output=True, text=True, timeout=5
            )
            results["checks"]["lint"] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Fallback to token matching if ruff isn't available
            results["checks"]["lint"] = self._token_match_fallback(scenario, patch, "lint")
    
    return results
```

**B3. Real AST validation for `ci_medium`**

For the test failure task, we check structural correctness:

```python
def _validate_medium_patch(self, patch, scenario):
    """Check that the patch structurally fixes the list/generator issue."""
    try:
        tree = ast.parse(patch)
    except SyntaxError:
        return False
    
    # Check if it contains a list comprehension (implementation fix)
    # or sum(1 for ...) pattern (test fix)
    source = ast.dump(tree)
    has_list_comp = "ListComp" in source
    has_generator_sum = "sum" in patch and "for" in patch
    has_list_wrap = "list(" in patch
    
    return has_list_comp or has_generator_sum or has_list_wrap
```

**B4. Real structural validation for `ci_hard`**

For the cascading failure, check that all required fixes are present:

```python
def _validate_hard_patch(self, patch, scenario):
    """Check multi-file patch addresses all failure dimensions."""
    try:
        ast.parse(patch)
    except SyntaxError:
        return {"mypy": False, "unit_tests": False, "integration": False}
    
    # Check each dimension is addressed
    results = {}
    results["mypy"] = "dry_run" in patch and "process_event" in patch
    results["unit_tests"] = ("lambda event, dry_run" in patch or 
                              "def mock_process_event(event, dry_run" in patch)
    results["integration"] = "assert" in patch and "changes" in patch
    
    return results
```

### Block C: Scenario Depth (Critical for Phase 2 Evaluation)

Each task needs at least 3 scenario variants so the Phase 2 agent evaluation sees variety and can't memorize.

**C1. CI Easy — 3 lint scenarios**

| Scenario | Error | File |
|---|---|---|
| `scenario_lint_001.json` | E402 import not at top | `src/utils.py` |
| `scenario_lint_002.json` | F841 unused variable | `src/config.py` |
| `scenario_lint_003.json` | E711 comparison to None should use `is` | `src/validator.py` |

Each scenario has different files, different error codes, different expected fixes.

**C2. CI Medium — 3 test failure scenarios**

| Scenario | Refactor | Break |
|---|---|---|
| `scenario_test_001.json` | list → generator | `len()` fails on generator |
| `scenario_test_002.json` | return dict → return namedtuple | `.get()` fails on namedtuple |
| `scenario_test_003.json` | sync → async function | test doesn't await |

**C3. CI Hard — 3 cascading failure scenarios**

| Scenario | Signature Change | Affected Files |
|---|---|---|
| `scenario_cascade_001.json` | Added `dry_run` param | 3 call sites + 2 tests + 1 integration |
| `scenario_cascade_002.json` | Changed return type from `dict` to `Result` | 4 consumers + 3 test assertions |
| `scenario_cascade_003.json` | Renamed method + changed param order | 2 subclasses + 2 call sites + 1 test mock |

**C4. SRE Easy — 3 noisy service scenarios**

| Scenario | Noisy Service | Error |
|---|---|---|
| `scenario_noisy_001.json` | payment-service | NullPointerException |
| `scenario_noisy_002.json` | auth-service | ConnectionRefusedException |
| `scenario_noisy_003.json` | inventory-service | IndexOutOfBoundsException |

**C5. SRE Medium — 3 latency scenarios**

| Scenario | Root Cause | Evidence |
|---|---|---|
| `scenario_latency_001.json` | db-proxy (missing index) | 7.9s query on order_items |
| `scenario_latency_002.json` | cache-layer (cold cache after restart) | hit ratio dropped from 94% to 12% |
| `scenario_latency_003.json` | auth-service (certificate re-validation loop) | 50x token validation requests |

**C6. SRE Hard — 3 memory leak scenarios**

| Scenario | Root Cause | Evidence Chain |
|---|---|---|
| `scenario_memleak_001.json` | cache-warmup job retaining references | deploy-204 diff + heap shows ProcessedItem growth |
| `scenario_memleak_002.json` | event listener not deregistered | deploy-187 diff + heap shows EventHandler growth |
| `scenario_memleak_003.json` | connection pool not releasing connections | deploy-312 diff + heap shows SocketConnection growth |

### Block D: Unit Tests (Code Quality Points)

Tests demonstrate correctness to judges and catch bugs before live evaluation.

**D1. `tests/test_ci_engine.py`**
```python
class TestCIEngine(unittest.TestCase):
    def test_read_file_returns_content(self):
        """read_file action returns file content from scenario."""
        
    def test_read_file_unknown_path_returns_error(self):
        """read_file with wrong path returns available files list."""
        
    def test_run_check_before_fix_shows_failure(self):
        """run_check returns failure output when check hasn't passed."""
        
    def test_submit_correct_patch_passes_checks(self):
        """Correct patch makes checks green and gives positive reward."""
        
    def test_submit_empty_patch_no_positive_reward(self):
        """Empty patch gives zero or negative reward."""
        
    def test_repeated_patch_penalty(self):
        """Submitting same patch twice triggers penalty."""
        
    def test_reward_clamped_to_0_1(self):
        """Reward is always between 0.0 and 1.0."""
```

**D2. `tests/test_sre_engine.py`**
```python
class TestSREEngine(unittest.TestCase):
    def test_get_logs_returns_service_logs(self):
        """get_logs returns log lines for valid service."""
        
    def test_get_logs_unknown_service_returns_error(self):
        """get_logs with wrong service name returns available services."""
        
    def test_query_root_cause_service_gives_reward(self):
        """Querying the root cause service earns reward."""
        
    def test_repeated_query_gives_penalty(self):
        """Exact same query repeated gives penalty."""
        
    def test_correct_diagnosis_completes_episode(self):
        """Full correct diagnosis marks episode done."""
        
    def test_wrong_diagnosis_gives_penalty(self):
        """Incorrect diagnosis gives negative reward."""
        
    def test_remediation_required_when_present(self):
        """Task doesn't complete without remediation when accepted_remediations is non-empty."""
```

**D3. `tests/test_environment.py`**
```python
class TestEnvironment(unittest.TestCase):
    def test_reset_returns_clean_observation(self):
        """reset() returns observation with step_count=0, done=False."""
        
    def test_step_before_reset_raises(self):
        """step() without reset() raises RuntimeError."""
        
    def test_state_updates_after_step(self):
        """State step_count increments after each step."""
        
    def test_max_steps_terminates_episode(self):
        """Episode ends when step_count >= max_steps."""
        
    def test_episode_isolation(self):
        """Second reset() completely clears state from first episode."""
        
    def test_seeded_reset_deterministic(self):
        """Same seed produces same scenario selection."""
```

**D4. `tests/test_reward.py`**
```python
class TestReward(unittest.TestCase):
    def test_ci_efficiency_bonus_step_1(self):
        """Solving in 1 step gives +0.10 bonus."""
        
    def test_ci_reward_all_green(self):
        """All checks green gives +0.40 bonus."""
        
    def test_sre_diagnosis_wrong_penalty(self):
        """No matched fields gives -0.10 penalty."""
        
    def test_clamp_score_never_exceeds_1(self):
        """Score is clamped at 1.0 even with many bonuses."""
        
    def test_clamp_score_never_below_0(self):
        """Score is clamped at 0.0 even with many penalties."""
```

### Block E: README for Submission

The README must be rewritten to be a submission document, not a developer note. Structure:

```markdown
# DevReliability-Env

## What This Is
[1 paragraph — CI debugging + SRE incident response for AI agents]

## Why This Environment
[Personal motivation + gap in OpenEnv ecosystem]

## Tasks

### CI Track
| Task | Difficulty | Description | Baseline Score |
| ci_easy | Easy | Fix lint failure | 0.XX |
| ci_medium | Medium | Fix broken unit test | 0.XX |
| ci_hard | Hard | Fix cascading multi-file failure | 0.XX |

### SRE Track
[Same table format]

## Observation Space
[Table of DevReliabilityObservation fields]

## Action Space
[Table of action_type values + payload shapes per track]

## Reward Function
[CI reward shaping explanation]
[SRE reward shaping explanation]
[Investigation progress rewarding — this is the differentiator]

## Setup & Usage

### Local
make run

### Docker
docker build -t dev-reliability-env .
docker run -p 7860:7860 dev-reliability-env

### HF Space
[Space URL]

## Baseline Scores
[Table with scores from inference.py run]

## Environment Design Notes
[Episode isolation, deterministic grading, scenario variety]
```

### Block F: Final Polish

**F1. Verify all 6 tasks produce varying scores**
Run inference multiple times, ensure graders return different scores for different actions.

**F2. Verify inference completes in < 20 minutes**
Time the full `inference.py` run on a 2vCPU/8GB machine.

**F3. Run `openenv validate` one final time**

**F4. Test HF Space responds to reset() from external client**

---

## 3. Scoring Breakdown — How to Hit 100/100

### Real-World Utility (30 points)

**What judges want:** A task humans actually do. Immediate value for RL community.

**How to score 30/30:**
- [x] Domain every software team encounters daily (CI + SRE) ✓
- [ ] README clearly explains why this matters
- [ ] README shows baseline scores proving the environment works
- [ ] Both tracks are functional and demonstrably distinct
- [ ] Difficulty range is real — easy ≠ medium ≠ hard in actual model performance

**Key argument for README:** "Every software team — from 2-person startups to Meta — runs CI and has SREs. This environment simulates the exact debugging loop that millions of developers and operations engineers perform daily. No existing OpenEnv environment covers software reliability."

### Task & Grader Quality (25 points)

**What judges want:** Deterministic graders. Meaningful difficulty. Fair scoring.

**How to score 25/25:**
- [ ] 6 tasks (exceeds the 3-task minimum)
- [ ] Graders use real tools (ruff, ast, pytest) not just token matching
- [ ] Scores vary based on agent quality (not constant)
- [ ] Hard task genuinely challenges frontier models (target: 0.15–0.30 baseline)
- [ ] Partial credit at every step (investigation rewards, not just final answer)
- [ ] Both valid fix paths for ci_medium are accepted
- [ ] SRE diagnosis uses weighted field matching (not binary)

**Critical risk:** If graders always return the same score regardless of input, you're disqualified. Test this by submitting garbage actions and verifying you get low scores.

### Environment Design (20 points)

**What judges want:** Clean state, good reward shaping, sensible episodes.

**How to score 20/20:**
- [ ] `reset()` produces completely clean state (no leakage from previous episodes)
- [ ] Different seeds produce different scenarios
- [ ] Action/observation types are well-documented with clear field descriptions
- [ ] Reward provides signal at every step (not just at episode end)
- [ ] Penalties for bad behavior (repeated patches, wrong diagnoses)
- [ ] Efficiency bonuses for solving quickly
- [ ] Episode ends cleanly at max_steps
- [ ] State property reflects all accumulated information

**Our advantage:** The reward shaping is already good. The SRE investigation rewarding (partial credit for querying relevant services) is novel and strong.

### Code Quality & Spec Compliance (15 points)

**What judges want:** `openenv validate` passes. Docker works. Baseline runs.

**How to score 15/15:**
- [ ] `openenv validate` passes without errors
- [ ] `docker build` succeeds
- [ ] `docker run` starts server that responds to `/health`
- [ ] HF Space is public and responds HTTP 200
- [ ] `inference.py` runs end-to-end without errors
- [ ] `inference.py` produces scores for all tasks
- [ ] Typed Pydantic models (not raw dicts)
- [ ] Project structure matches OpenEnv convention
- [ ] Unit tests exist and pass
- [ ] Code is clean and well-organized

### Creativity & Novelty (10 points)

**What judges want:** Something they haven't seen before.

**How to score 10/10:**
- [x] Novel domain (CI + SRE — first in OpenEnv) ✓
- [x] Two-track design (CI + SRE sharing one interface) ✓
- [x] Investigation-quality rewarding (not just final-answer scoring) ✓
- [ ] README explicitly calls out these novel aspects
- [ ] SRE track requires multi-step reasoning across data sources
- [ ] Hard tasks require reasoning, not pattern matching

---

## 4. Competitive Advantages to Emphasize

1. **6 tasks, not 3.** Double the minimum. Shows depth.
2. **Two tracks in one environment.** Architecturally interesting. Shows it's not a one-trick domain.
3. **Investigation rewarding.** The SRE track rewards the debugging process itself, not just the final answer. This is closer to real RL reward shaping than binary pass/fail.
4. **Grounded in real failure modes.** Scenarios modeled on actual CI failures from open source projects.
5. **Extensible by design.** Adding new scenarios is just adding JSON files. No engine changes needed.

---

## 5. Execution Order (No Dates — Just Sequence)

```
SEQUENCE 1 — SURVIVAL
├── Docker build + run locally
├── openenv validate
├── inference.py E2E test
└── HF Spaces deployment

SEQUENCE 2 — GRADING QUALITY  
├── Add ruff to requirements.txt + Dockerfile
├── Implement real ruff linting in ci_engine for ci_easy
├── Add ast.parse() validation for all CI tasks
├── Verify graders return different scores for different inputs
└── (Optional) Add real pytest execution for ci_medium

SEQUENCE 3 — SCENARIO DEPTH
├── Write scenario_lint_002.json, scenario_lint_003.json
├── Write scenario_test_002.json, scenario_test_003.json
├── Write scenario_cascade_002.json, scenario_cascade_003.json
├── Write scenario_noisy_002.json, scenario_noisy_003.json
├── Write scenario_latency_002.json, scenario_latency_003.json
└── Write scenario_memleak_002.json, scenario_memleak_003.json

SEQUENCE 4 — TESTS
├── tests/test_ci_engine.py
├── tests/test_sre_engine.py
├── tests/test_environment.py
├── tests/test_reward.py
└── make test (all green)

SEQUENCE 5 — DOCUMENTATION
├── Rewrite README.md as submission document
├── Include baseline scores from real inference run
├── Include observation/action space tables
└── Highlight novel aspects (two-track, investigation rewarding)

SEQUENCE 6 — FINAL VALIDATION
├── Run openenv validate
├── Rebuild Docker, re-test
├── Re-run inference.py against HF Space
├── Verify all 6 tasks produce varying scores
├── Verify < 20 min runtime on 2vCPU/8GB
└── Submit
```

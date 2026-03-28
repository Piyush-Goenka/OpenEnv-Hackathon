# DevReliability-Env

CI debugging and SRE incident response environment for the OpenEnv hackathon.
The environment simulates two reliability workflows:

- developers fixing failing CI
- SREs investigating production incidents

The implementation is deterministic and data-driven. CI checks are simulated
from scenario rules instead of executing real tools, and SRE investigations
query pre-generated logs, metrics, deployment history, and heap summaries.

## Repository Layout

```text
.
├── Dockerfile
├── client.py
├── inference.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── requirements.txt
├── server/
│   ├── __init__.py
│   ├── app.py
│   ├── ci_engine.py
│   ├── environment.py
│   ├── reward.py
│   └── sre_engine.py
├── tasks/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── ci/
│   │   ├── __init__.py
│   │   ├── easy_lint_failure.py
│   │   ├── medium_test_failure.py
│   │   └── hard_cascading_failure.py
│   └── sre/
│       ├── __init__.py
│       ├── easy_noisy_service.py
│       ├── medium_latency_trace.py
│       └── hard_memory_leak.py
├── data/
│   ├── ci_scenarios/
│   └── sre_scenarios/
├── tests/
│   ├── __init__.py
│   ├── test_repo_layout.py
│   └── test_task_registry.py
├── deliverable.md
├── guide.md
└── Makefile
```

## Tasks

### CI Track
- `ci_easy`: fix a failing lint check in a single file
- `ci_medium`: fix a broken unit test caused by a refactor
- `ci_hard`: fix a cascading multi-file failure from a signature change

### SRE Track
- `sre_easy`: identify the noisy service from a log stream
- `sre_medium`: trace a latency spike across services
- `sre_hard`: diagnose a memory leak from metrics, diffs, and heap data

## Implementation Notes

- `server/ci_engine.py` handles read-file, run-check, and patch-submission actions.
- `server/sre_engine.py` handles log, metric, diff, heap, and deployment-history queries.
- `server/reward.py` centralizes deterministic reward shaping.
- `data/` contains scenario fixtures. Adding more variants does not require changing the engines.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make run
```

Run tests:

```bash
make test
```

Run the baseline inference script:

```bash
make infer
```

Build the container:

```bash
make docker-build
```

## Current Scope

This repo now matches the `deliverable.md` architecture and includes starter
scenario data for all 6 tasks. The next layer of work is to deepen the scenario
pools and tune the graders against real baseline runs.

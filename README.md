# OpenEnv Hackathon Scaffold

This repository is structured as a clean starting point for the OpenEnv hackathon.
It already includes the expected top-level files, a generic environment scaffold,
placeholder tasks, Docker wiring, and basic repository hygiene.

The current implementation is intentionally domain-neutral. It is useful for
local iteration and for locking in the repo structure, but it is not the final
submission. The remaining work is to replace the placeholder tasks and grading
logic with the real environment idea.

## Repository Layout

```text
.
├── client.py
├── inference.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── requirements.txt
├── server/
│   ├── __init__.py
│   ├── app.py
│   ├── Dockerfile
│   └── environment.py
├── tasks/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── task_easy.py
│   ├── task_medium.py
│   └── task_hard.py
├── tests/
│   ├── __init__.py
│   ├── test_repo_scaffold.py
│   └── test_task_registry.py
├── .env.example
└── Makefile
```

## What Is Ready

- Hackathon-aligned file structure
- Generic `Action`, `Observation`, and `State` models
- A starter environment with task selection and deterministic placeholder grading
- Root-level `inference.py` using the OpenAI client and required env vars
- Docker entrypoint on port `7860`
- Basic unit tests for scaffold integrity
- `Makefile` commands for common local workflows

## What Still Needs Customization

- Choose the actual domain
- Rewrite the 3 task modules with real task descriptions and graders
- Replace placeholder reward logic with domain-specific evaluation
- Refine the inference prompt for the chosen environment
- Validate with the final `openenv-core` version and Hugging Face Space

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run the server locally:

```bash
make run
```

Run the baseline inference script:

```bash
make infer
```

Run the lightweight tests:

```bash
make test
```

Build the Docker image:

```bash
make docker-build
```

## Hackathon Notes

- Follow the hackathon-specific rules in `guide.md`
- Use the course materials under `openenv-course/` as implementation reference
- Treat the final OpenEnv API installed in your environment as the source of truth
  if the guide and course examples differ in minor details

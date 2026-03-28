PYTHON ?= python3
IMAGE_NAME ?= dev-reliability-env

.PHONY: run test compile docker-build docker-run infer validate

run:
	uvicorn server.app:app --host 0.0.0.0 --port 7860 --reload

test:
	$(PYTHON) -m unittest discover -s tests

compile:
	$(PYTHON) -m compileall client.py inference.py models.py server tasks tests

docker-build:
	docker build -f Dockerfile -t $(IMAGE_NAME) .

docker-run:
	docker run --rm -p 7860:7860 $(IMAGE_NAME)

infer:
	$(PYTHON) inference.py

validate:
	openenv validate

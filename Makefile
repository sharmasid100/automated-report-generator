PYTHON ?= python3
IMAGE ?= pader-automated-report-generator:local
export MOCK_LLM ?= true

.PHONY: help install install-dev sample-data test lint format pipeline docker-build docker-test docker-run compose-run

help:
	@echo "Available targets: install install-dev sample-data test lint format pipeline docker-build docker-test docker-run"

install:
	$(PYTHON) -m pip install -r requirements-ci.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-ci.txt -r requirements-dev.txt

sample-data:
	$(PYTHON) scripts/generate_sample_icsr.py

lint:
	ruff check src tests scripts
	ruff format --check src tests scripts

format:
	ruff check --fix src tests scripts
	ruff format src tests scripts

test: sample-data
	MOCK_LLM=true pytest

pipeline: sample-data
	MOCK_LLM=true $(PYTHON) src/main.py

docker-build:
	docker build -t $(IMAGE) .

docker-test:
	docker compose --profile test run --rm test

docker-run:
	docker compose run --rm report-generator

compose-run: docker-run

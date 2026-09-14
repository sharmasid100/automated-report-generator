# Contributing

## Getting Started

### Development Environment Setup

1. Clone the repository and create a virtual environment.
2. Install test and lint dependencies:

```bash
pip install -r requirements-ci.txt -r requirements-dev.txt
```

3. Generate the synthetic ICSR sample and run the pipeline:

```bash
python scripts/generate_sample_icsr.py
MOCK_LLM=true python src/main.py
```

Optional:

```bash
pre-commit install
```

## Testing

```bash
MOCK_LLM=true pytest
MOCK_LLM=true pytest --cov=src --cov-report=term-missing
```

Docker:

```bash
docker compose --profile test run --rm test
```

### Writing Tests

- Keep tests under `tests/`.
- Use the synthetic generator in `scripts/generate_sample_icsr.py`.
- Do not commit identifiable ICSR extracts.
- Prefer assertions on evidence JSON and validation helpers over model fluency.

## Code Standards

- Python 3.9+.
- Ruff for lint and format (`src/analysis.py` is excluded from format because it preserves the original analysis layout).
- Keep calculations in `preprocess.py` and `analysis.py`.
- Keep prompts in `prompts.py` and document contract changes in `prompts/report_prompts.md`.
- Do not log patient narratives, names, or other personal data.

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes

**All changes** must be documented in [CHANGELOG.md](CHANGELOG.md).

## Pull Request Process

1. Open a branch from `main`.
2. Include tests for analysis, validation, or packaging changes.
3. Keep CI green: `.github/workflows/ci.yaml` and `.github/workflows/docker.yaml`.
4. Describe why the change is needed and confirm the LLM still cannot own numerical truth.

## Support

Report bugs and request features through GitHub issues. Do not upload regulatory source files that contain personal data.

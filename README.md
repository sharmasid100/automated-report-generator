# PADER Automated Report Generator

CPU-friendly pipeline that turns an Individual Case Safety Report (ICSR) Excel dataset into a Periodic Adverse Drug Experience Report (PADER) style Markdown draft.

Python calculates the facts. The language model verbalizes those facts. Validation decides whether generated text can be accepted. A qualified human reviewer remains the final control.

## Features

- Preprocesses ICSR Excel data, keeps the latest case version, and filters to Bisoprolol unless you override that setting.
- Runs deterministic case, seriousness, demographic, reaction, outcome, alert, and trend analysis.
- Writes `output/evidence.json` as the factual source of truth.
- Generates five narrative sections with Qwen2.5-0.5B-Instruct, or a deterministic fallback when `MOCK_LLM=true`.
- Flags unsupported numbers and high-risk causal or regulatory phrases.
- Assembles a PADER-style Markdown report marked pending human review.

## Prerequisites

- Python 3.9 or later
- pip
- Optional: Docker and Docker Compose for containerized runs
- Optional: Hugging Face access if you disable mock mode and load `Qwen/Qwen2.5-0.5B-Instruct`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-ci.txt -r requirements-dev.txt
python scripts/generate_sample_icsr.py
```

Install `requirements.txt` only when you want local Hugging Face generation.

## Usage

```bash
export MOCK_LLM=true
python src/main.py
```

The pipeline writes:

- `output/evidence.json`
- `output/generation_audit.json`
- `output/pader_report.md`

Docker:

```bash
python scripts/generate_sample_icsr.py
docker compose run --rm report-generator
```

Set `MOCK_LLM=false` and install `requirements.txt` (or a GPU/CPU torch wheel that matches your host) before running the real model.

## Technologies Used

- Python 3.10+
- pandas, NumPy, and openpyxl for ICSR processing
- Hugging Face Transformers and Qwen2.5-0.5B-Instruct for optional narrative generation
- pytest and Ruff for tests and lint
- Docker, Docker Compose, and GitHub Actions for packaging and CI/CD

## FAQ

### Why is the report still pending human review after validation passes?

Numerical membership checks do not prove that a number is attached to the correct evidence field. Phrase filters also miss some unsupported inferences. The draft is never a finished regulatory submission.

### How do I use my own ICSR workbook?

Place the Excel file under `data/` and set `ICSR_INPUT_FILE` to that path. Column names should match the FAERS-style fields listed in `src/preprocess.py`.

### How do I skip the language-model download in CI?

Leave `MOCK_LLM=true`. GitHub Actions and the default Docker image use that mode.

### Can the model calculate case counts?

No. `src/analysis.py` owns counts, percentages, and trends. The model only receives compact evidence JSON.

## Documentation

- [Architecture](architecture_diagram.md)
- [Prompt contract](prompts/report_prompts.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and pull request expectations.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Support

- **Issues**: Use the GitHub issue templates in this repository.
- **Security**: Follow [SECURITY.md](SECURITY.md). Do not attach identifiable patient data to issues.

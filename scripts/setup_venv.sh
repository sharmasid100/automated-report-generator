.\.venv\Scripts\Activate.ps1#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-ci.txt -r requirements-dev.txt
python scripts/generate_sample_icsr.py
echo "Environment ready. Activate with: source .venv/bin/activate"

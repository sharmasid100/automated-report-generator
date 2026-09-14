"""Shared project paths. All modules resolve files from the repository root."""

from __future__ import annotations

import os
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
PROCESSED_DATA_DIR = PROJECT_ROOT / "processed_data"

DEFAULT_INPUT_FILE = DATA_DIR / "Bisoprolol_icsr_sample.xlsx"
INPUT_FILE = Path(os.environ.get("ICSR_INPUT_FILE", str(DEFAULT_INPUT_FILE)))

CASES_FILE = PROCESSED_DATA_DIR / "cases.csv"
REACTIONS_FILE = PROCESSED_DATA_DIR / "reactions.csv"
DRUGS_FILE = PROCESSED_DATA_DIR / "target_drugs.csv"

EVIDENCE_FILE = OUTPUT_DIR / "evidence.json"
REPORT_FILE = OUTPUT_DIR / "pader_report.md"
AUDIT_FILE = OUTPUT_DIR / "generation_audit.json"

FILTER_TO_TARGET_DRUG = os.environ.get("FILTER_TO_TARGET_DRUG", "true").lower() in {
    "1",
    "true",
    "yes",
}
TARGET_DRUG_PATTERN = os.environ.get(
    "TARGET_DRUG_PATTERN",
    r"\bBISOPROLOL(?:\s+FUMARATE)?\b",
)
MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
MOCK_LLM = os.environ.get("MOCK_LLM", "false").lower() in {"1", "true", "yes"}


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

"""Unit tests for validation, prompts, and the end-to-end mock pipeline."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPTS))

os.environ.setdefault("MOCK_LLM", "true")
os.environ.setdefault("ICSR_INPUT_FILE", str(ROOT / "data" / "Bisoprolol_icsr_sample.xlsx"))


def test_extract_and_validate_numbers():
    from llm_pipeline import extract_numbers, validate_numbers

    text = "There were 3 unique cases and 2 serious cases (66.67%)."
    evidence = {"total_unique_cases": 3, "serious_cases": 2, "serious_percentage": 66.67}
    assert "3" in extract_numbers(text)
    valid, unsupported = validate_numbers(text, evidence)
    assert valid
    assert unsupported == []


def test_unsupported_number_is_flagged():
    from llm_pipeline import validate_numbers

    valid, unsupported = validate_numbers("There were 99 cases.", {"total_unique_cases": 3})
    assert not valid
    assert unsupported


def test_unsupported_claims_are_flagged():
    from llm_pipeline import detect_unsupported_claims

    findings = detect_unsupported_claims("This proves that a confirmed safety signal exists.")
    assert findings


def test_prompt_compaction_keeps_supplied_counts():
    from prompts import get_prompt

    evidence = {
        "case_summary": {
            "total_unique_cases": 3,
            "serious_cases": 2,
            "non_serious_cases": 1,
            "serious_percentage": 66.67,
            "expedite_alert_cases": 2,
            "expedite_alert_percentage": 66.67,
        },
        "reporting_period": {"start_date": "2025-01-15", "end_date": "2025-06-10"},
        "seriousness": {},
        "demographics": {},
        "reactions": {
            "total_reaction_occurrences": 6,
            "most_frequent_reactions": {"Hypotension": 1},
        },
        "outcomes": {},
        "alerts": {},
    }
    prompt = get_prompt("narrative_summary", evidence)
    assert "3" in prompt
    assert "Hypotension" in prompt


def test_full_pipeline_with_mock_llm(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("ICSR_INPUT_FILE", str(ROOT / "data" / "Bisoprolol_icsr_sample.xlsx"))

    from generate_sample_icsr import write_sample

    from main import main

    write_sample(ROOT / "data" / "Bisoprolol_icsr_sample.xlsx")
    report = main()
    assert "PADER-Style Safety Report" in report
    evidence = json.loads((ROOT / "output" / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["case_summary"]["total_unique_cases"] == 3
    assert (ROOT / "output" / "pader_report.md").exists()
    assert (ROOT / "output" / "generation_audit.json").exists()

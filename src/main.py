"""Orchestration layer for the PADER-style safety reporting pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analysis import run_analysis
from llm_pipeline import generate_report
from paths import (
    AUDIT_FILE,
    DATA_DIR,
    EVIDENCE_FILE,
    OUTPUT_DIR,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    REPORT_FILE,
    ensure_directories,
)
from preprocess import preprocess_data


def print_stage(stage_number: int, total_stages: int, message: str) -> None:
    print()
    print("=" * 70)
    print(f"[{stage_number}/{total_stages}] {message}")
    print("=" * 70)


def main() -> str:
    total_stages = 4
    try:
        ensure_directories()

        print()
        print("=" * 70)
        print("PADER-STYLE SAFETY REPORTING PIPELINE")
        print("=" * 70)
        print(f"Project root     : {PROJECT_ROOT}")
        print(f"Data directory   : {DATA_DIR}")
        print(f"Processed data   : {PROCESSED_DATA_DIR}")
        print(f"Output directory : {OUTPUT_DIR}")

        print_stage(1, total_stages, "Preprocessing and validating the ICSR dataset")
        preprocess_data()
        print("Preprocessing completed successfully.")

        print_stage(2, total_stages, "Running deterministic safety analysis")
        evidence = run_analysis()
        if evidence is None:
            raise RuntimeError("analysis.py did not return an Evidence JSON object.")
        if not isinstance(evidence, dict):
            raise TypeError("run_analysis() must return the Evidence JSON as a Python dictionary.")

        print("Deterministic analysis completed successfully.")
        print()
        print("Evidence summary:")
        case_summary = evidence.get("case_summary", {})
        if isinstance(case_summary, dict):
            for key in ("total_unique_cases", "serious_cases", "non_serious_cases"):
                value = case_summary.get(key)
                if value is not None:
                    print(f"  {key}: {value}")
        print(f"Evidence saved to: {EVIDENCE_FILE}")

        print_stage(3, total_stages, "Generating PADER-style report")
        report = generate_report()
        if report is None:
            raise RuntimeError("llm_pipeline.py did not return the generated report.")
        if not isinstance(report, str):
            raise TypeError("generate_report() must return the generated report as a string.")
        print("Report generation completed successfully.")

        print_stage(4, total_stages, "Verifying generated output")
        for path, label in (
            (REPORT_FILE, "Report"),
            (EVIDENCE_FILE, "Evidence file"),
            (AUDIT_FILE, "Audit file"),
        ):
            if path.exists():
                print(f"{label} saved to: {path}")
            else:
                print(f"WARNING: Expected {label.lower()} was not found.")

        print()
        print("=" * 70)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("IMPORTANT:")
        print("The generated report is PENDING HUMAN REVIEW.")
        print("=" * 70)
        return report
    except FileNotFoundError as error:
        print()
        print("PIPELINE FAILED")
        print(f"Required file was not found: {error}")
        print(f"Check that the required dataset exists inside: {DATA_DIR}")
        raise
    except Exception as error:
        print()
        print("PIPELINE FAILED")
        print(f"Error type    : {type(error).__name__}")
        print(f"Error message : {error}")
        raise


if __name__ == "__main__":
    main()

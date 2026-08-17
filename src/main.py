"""
main.py

Entry point for the CPU-friendly PADER-style safety reporting pipeline.

Pipeline:

    ICSR Excel Dataset
            |
            v
    preprocess.py
            |
            v
    Cleaned / Validated Data
            |
            v
    analysis.py
            |
            v
    Evidence JSON
            |
            v
    llm_pipeline.py
            |
            v
    Qwen2.5-0.5B-Instruct
            |
            v
    Claim Validation
            |
            v
    PADER Markdown Report


This file is intentionally kept as an orchestration layer.

It does NOT:
    - Perform data preprocessing.
    - Calculate statistics.
    - Build LLM prompts.
    - Load the Hugging Face model.
    - Generate individual report sections.
    - Perform detailed claim validation.

Those responsibilities belong to the respective modules.
"""


import sys
from pathlib import Path


# ---------------------------------------------------------------------
# Make sure imports work when running:
#
#     python src/main.py
#
# ---------------------------------------------------------------------

SRC_DIR = Path(__file__).resolve().parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------
# Project modules
# ---------------------------------------------------------------------

from preprocess import preprocess_data
from analysis import run_analysis
from llm_pipeline import generate_report


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJECT_ROOT = SRC_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
PROCESSED_DATA_DIR = PROJECT_ROOT / "processed_data"

REPORT_PATH = OUTPUT_DIR / "pader_report.md"
EVIDENCE_PATH = OUTPUT_DIR / "evidence.json"
AUDIT_PATH = OUTPUT_DIR / "generation_audit.json"


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def create_required_directories():
    """
    Create directories required by the pipeline.

    Existing directories are not modified.
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)


def print_stage(stage_number, total_stages, message):
    """
    Print a simple pipeline progress message.
    """

    print()
    print("=" * 70)
    print(f"[{stage_number}/{total_stages}] {message}")
    print("=" * 70)


# ---------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------

def main():
    """
    Execute the complete PADER safety reporting pipeline.

    Returns
    -------
    str
        Generated PADER-style Markdown report.

    Raises
    ------
    Exception
        Any unexpected pipeline error is re-raised after displaying
        a useful error message.
    """

    total_stages = 4

    try:
        # -------------------------------------------------------------
        # Stage 1: Prepare directories
        # -------------------------------------------------------------

        create_required_directories()

        print()
        print("=" * 70)
        print("PADER-STYLE SAFETY REPORTING PIPELINE")
        print("=" * 70)

        print(f"Project root     : {PROJECT_ROOT}")
        print(f"Data directory   : {DATA_DIR}")
        print(f"Processed data   : {PROCESSED_DATA_DIR}")
        print(f"Output directory : {OUTPUT_DIR}")

        # -------------------------------------------------------------
        # Stage 2: Preprocessing
        # -------------------------------------------------------------

        print_stage(
            1,
            total_stages,
            "Preprocessing and validating the ICSR dataset"
        )

        preprocess_data()

        print("Preprocessing completed successfully.")

        # -------------------------------------------------------------
        # Stage 3: Deterministic analysis
        # -------------------------------------------------------------

        print_stage(
            2,
            total_stages,
            "Running deterministic safety analysis"
        )

        evidence = run_analysis()

        if evidence is None:
            raise RuntimeError(
                "analysis.py did not return an Evidence JSON object."
            )

        if not isinstance(evidence, dict):
            raise TypeError(
                "run_analysis() must return the Evidence JSON as a "
                "Python dictionary."
            )

        print("Deterministic analysis completed successfully.")

        # -------------------------------------------------------------
        # Display basic evidence information
        # -------------------------------------------------------------

        print()
        print("Evidence summary:")

        case_summary = evidence.get("case_summary", {})

        if isinstance(case_summary, dict):

            total_cases = case_summary.get("total_unique_cases")

            serious_cases = case_summary.get("serious_cases")

            non_serious_cases = case_summary.get("non_serious_cases")

            if total_cases is not None:
                print(f"  Total unique cases : {total_cases}")

            if serious_cases is not None:
                print(f"  Serious cases      : {serious_cases}")

            if non_serious_cases is not None:
                print(f"  Non-serious cases  : {non_serious_cases}")

        print(f"Evidence saved to: {EVIDENCE_PATH}")

        # -------------------------------------------------------------
        # Stage 4: LLM generation and validation
        # -------------------------------------------------------------

        print_stage(
            3,
            total_stages,
            "Generating PADER-style report using Qwen2.5-0.5B-Instruct"
        )

        report = generate_report()

        if report is None:
            raise RuntimeError(
                "llm_pipeline.py did not return the generated report."
            )

        if not isinstance(report, str):
            raise TypeError(
                "generate_report() must return the generated report "
                "as a string."
            )

        print("Report generation completed successfully.")

        # -------------------------------------------------------------
        # Final output verification
        # -------------------------------------------------------------

        print_stage(
            4,
            total_stages,
            "Verifying generated output"
        )

        if REPORT_PATH.exists():
            print(f"Report saved to : {REPORT_PATH}")
        else:
            print(
                "WARNING: The report was returned by generate_report(), "
                "but the expected report file was not found."
            )

        if EVIDENCE_PATH.exists():
            print(f"Evidence file   : {EVIDENCE_PATH}")
        else:
            print(
                "WARNING: Expected Evidence JSON was not found."
            )

        if AUDIT_PATH.exists():
            print(f"Audit file      : {AUDIT_PATH}")
        else:
            print(
                "WARNING: Generation audit file was not found."
            )

        # -------------------------------------------------------------
        # Completion message
        # -------------------------------------------------------------

        print()
        print("=" * 70)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 70)

        print()
        print("Generated files:")

        print(f"  - {REPORT_PATH}")
        print(f"  - {EVIDENCE_PATH}")
        print(f"  - {AUDIT_PATH}")

        print()
        print("IMPORTANT:")
        print("The generated report is PENDING HUMAN REVIEW.")
        print(
            "AI-generated content must be reviewed against the "
            "validated evidence before final approval."
        )

        print("=" * 70)

        return report

    except FileNotFoundError as error:

        print()
        print("=" * 70)
        print("PIPELINE FAILED")
        print("=" * 70)

        print(f"Required file was not found:")
        print(f"  {error}")

        print()
        print("Check that the required dataset exists inside:")
        print(f"  {DATA_DIR}")

        raise

    except ImportError as error:

        print()
        print("=" * 70)
        print("PIPELINE FAILED - IMPORT ERROR")
        print("=" * 70)

        print(error)

        print()
        print(
            "Check that all required dependencies are installed "
            "inside the active Python environment."
        )

        raise

    except Exception as error:

        print()
        print("=" * 70)
        print("PIPELINE FAILED")
        print("=" * 70)

        print(f"Error type    : {type(error).__name__}")
        print(f"Error message : {error}")

        print()
        print(
            "The error above should be investigated before using "
            "the generated report."
        )

        raise


# ---------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    main()
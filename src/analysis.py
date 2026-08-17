"""
analysis.py

Deterministic safety analysis for the Bisoprolol ICSR dataset.

Responsibilities:
    1. Load preprocessed case/reaction/drug data
    2. Perform case-level analysis
    3. Perform reaction-level analysis
    4. Perform demographic analysis
    5. Perform seriousness analysis
    6. Perform outcome analysis
    7. Perform monthly trend analysis
    8. Identify alerts / concentrations
    9. Build Evidence JSON
    10. Save Evidence JSON for the LLM layer

IMPORTANT:
    Python is the source of truth.

    This module does NOT use an LLM.
    This module does NOT make causal or regulatory conclusions.
"""


from pathlib import Path
import json
import re

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROCESSED_DIR = Path("processed_data")
OUTPUT_DIR = Path("output")

CASES_FILE = PROCESSED_DIR / "cases.csv"
REACTIONS_FILE = PROCESSED_DIR / "reactions.csv"
DRUGS_FILE = PROCESSED_DIR / "target_drugs.csv"

EVIDENCE_FILE = OUTPUT_DIR / "evidence.json"


# Number of top reactions/countries/etc. retained
TOP_N = 10


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_value(value):
    """Convert pandas/NumPy values into JSON-safe values."""

    if pd.isna(value):
        return None

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None

        return float(value)

    return value


def clean_dict(data):
    """
    Recursively convert NumPy/Pandas values
    into JSON-serializable Python values.
    """

    if isinstance(data, dict):

        return {
            key: clean_dict(value)
            for key, value in data.items()
        }

    if isinstance(data, list):

        return [
            clean_dict(value)
            for value in data
        ]

    return clean_value(data)


def normalize_string(series):
    """Normalize categorical pandas Series."""

    return (
        series
        .astype("string")
        .str.strip()
        .str.lower()
    )


def value_counts_dict(series, top_n=None):
    """
    Return frequency distribution as a dictionary.
    Missing values are explicitly represented as 'unknown'.
    """

    series = series.copy()

    series = series.fillna("unknown")

    series = (
        series
        .astype(str)
        .str.strip()
        .replace("", "unknown")
    )

    counts = series.value_counts()

    if top_n is not None:
        counts = counts.head(top_n)

    return {
        str(index): int(value)
        for index, value in counts.items()
    }


def percentage(part, total):
    """Calculate percentage safely."""

    if total == 0:
        return 0.0

    return round(
        (part / total) * 100,
        2
    )


# ============================================================
# DATA LOADING
# ============================================================

def load_processed_data():
    """
    Load preprocessed datasets.
    """

    print("Loading processed data...")

    if not CASES_FILE.exists():
        raise FileNotFoundError(
            f"Cases file not found: {CASES_FILE}"
        )

    if not REACTIONS_FILE.exists():
        raise FileNotFoundError(
            f"Reactions file not found: {REACTIONS_FILE}"
        )

    if not DRUGS_FILE.exists():
        raise FileNotFoundError(
            f"Drugs file not found: {DRUGS_FILE}"
        )

    cases = pd.read_csv(
        CASES_FILE
    )

    reactions = pd.read_csv(
        REACTIONS_FILE
    )

    drugs = pd.read_csv(
        DRUGS_FILE
    )

    return cases, reactions, drugs


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_data(cases, reactions, drugs):
    """
    Perform basic validation before analysis.
    """

    print("Validating processed data...")

    required_case_columns = [
        "safetyreportid",
        "serious",
        "fulfillexpeditecriteria",
        "patient_patientsex",
        "age_group",
    ]

    required_reaction_columns = [
        "safetyreportid",
        "reaction_pt",
    ]

    required_drug_columns = [
        "safetyreportid",
        "active_substance",
    ]

    missing_cases = [
        column
        for column in required_case_columns
        if column not in cases.columns
    ]

    missing_reactions = [
        column
        for column in required_reaction_columns
        if column not in reactions.columns
    ]

    missing_drugs = [
        column
        for column in required_drug_columns
        if column not in drugs.columns
    ]

    if missing_cases:
        raise ValueError(
            "Missing case columns: "
            + ", ".join(missing_cases)
        )

    if missing_reactions:
        raise ValueError(
            "Missing reaction columns: "
            + ", ".join(missing_reactions)
        )

    if missing_drugs:
        raise ValueError(
            "Missing drug columns: "
            + ", ".join(missing_drugs)
        )

    # Case IDs must be unique at case level
    duplicate_cases = cases[
        cases["safetyreportid"].duplicated()
    ]

    if not duplicate_cases.empty:

        raise ValueError(
            "cases.csv contains duplicate safetyreportid values."
        )

    print("Validation passed.")


# ============================================================
# CASE-LEVEL ANALYSIS
# ============================================================

def analyze_cases(cases):
    """
    Calculate case-level statistics.

    One row = one unique ICSR case.
    """

    total_cases = len(cases)
    	


    seriousness_columns = [
    "serious",
    "seriousnessdeath",
    "seriousnesslifethreatening",
    "seriousnesshospitalization",
    "seriousnessdisabling",
    "seriousnesscongenitalanomali",
    "seriousnessother"
    ]

    serious = (
    cases[seriousness_columns]
    .apply(
        lambda col: normalize_string(col).isin(["1", "yes", "y"])
    )
    .any(axis=1)
    )

    non_serious = (
        normalize_string(
            cases["serious"]
        )
        .isin(["0", "false", "no"])
    )

    unknown_serious = ~(
        serious | non_serious
    )

    expedite = (
        normalize_string(
            cases["fulfillexpeditecriteria"]
        )
        .isin(["1", "true", "yes"])
    )

    result = {

        "total_unique_cases": total_cases,

        "serious_cases": int(
            serious.sum()
        ),

        "non_serious_cases": int(
            non_serious.sum()
        ),

        "unknown_seriousness": int(
            unknown_serious.sum()
        ),

        "serious_percentage": percentage(
            serious.sum(),
            total_cases
        ),

        "non_serious_percentage": percentage(
            non_serious.sum(),
            total_cases
        ),

        "expedite_alert_cases": int(
            expedite.sum()
        ),

        "expedite_alert_percentage": percentage(
            expedite.sum(),
            total_cases
        ),
    }

    return result


# ============================================================
# SERIOUSNESS ANALYSIS
# ============================================================

def analyze_seriousness(cases):
    """
    Analyze seriousness indicators independently.

    Important:
        These categories are NOT treated as mutually exclusive.
    """

    seriousness_columns = {

        "death": "seriousnessdeath",

        "life_threatening":
            "seriousnesslifethreatening",

        "hospitalization":
            "seriousnesshospitalization",

        "disability":
            "seriousnessdisabling",

        "congenital_anomaly":
            "seriousnesscongenitalanomali",

        "other_serious":
            "seriousnessother",
    }

    result = {}

    total_cases = len(cases)

    for name, column in seriousness_columns.items():

        if column not in cases.columns:

            result[name] = {
                "available": False,
                "count": None,
                "percentage": None,
            }

            continue

        values = normalize_string(
            cases[column]
        )

        positive = values.isin(
            ["1", "true", "yes"]
        )

        count = int(
            positive.sum()
        )

        result[name] = {

            "available": True,

            "count": count,

            "percentage": percentage(
                count,
                total_cases
            ),
        }

    return result


# ============================================================
# DEMOGRAPHIC ANALYSIS
# ============================================================

def analyze_demographics(cases):
    """
    Analyze age, sex and country distributions.
    """

    result = {}

    # --------------------------------------------------------
    # AGE
    # --------------------------------------------------------

    if "age_years" in cases.columns:

        age = pd.to_numeric(
            cases["age_years"],
            errors="coerce"
        )

        valid_age = age.dropna()

        age_summary = {

            "available_cases": int(
                valid_age.count()
            ),

            "missing_cases": int(
                age.isna().sum()
            ),
        }

        if not valid_age.empty:

            age_summary.update({

                "minimum_years":
                    round(
                        float(valid_age.min()),
                        2
                    ),

                "maximum_years":
                    round(
                        float(valid_age.max()),
                        2
                    ),

                "mean_years":
                    round(
                        float(valid_age.mean()),
                        2
                    ),

                "median_years":
                    round(
                        float(valid_age.median()),
                        2
                    ),
            })

    else:

        age_summary = {
            "available_cases": 0,
            "missing_cases": len(cases),
        }

    result["age"] = age_summary

    # --------------------------------------------------------
    # AGE GROUP
    # --------------------------------------------------------

    if "age_group" in cases.columns:

        result["age_group_distribution"] = (
            value_counts_dict(
                cases["age_group"]
            )
        )

    # --------------------------------------------------------
    # SEX
    # --------------------------------------------------------

    result["sex_distribution"] = (
        value_counts_dict(
            cases["patient_patientsex"]
        )
    )

    # --------------------------------------------------------
    # PRIMARY SOURCE COUNTRY
    # --------------------------------------------------------

    if "primarysourcecountry" in cases.columns:

        result["primary_source_country"] = (
            value_counts_dict(
                cases["primarysourcecountry"],
                TOP_N
            )
        )

    else:

        result["primary_source_country"] = {}

    # --------------------------------------------------------
    # OCCURRENCE COUNTRY
    # --------------------------------------------------------

    if "occurcountry" in cases.columns:

        result["occurrence_country"] = (
            value_counts_dict(
                cases["occurcountry"],
                TOP_N
            )
        )

    else:

        result["occurrence_country"] = {}

    return result


# ============================================================
# REACTION-LEVEL ANALYSIS
# ============================================================

def analyze_reactions(reactions):
    """
    Analyze reactions independently from cases.

    One case may have multiple reactions.
    Therefore reaction counts must NOT be interpreted
    as case counts.
    """

    if reactions.empty:

        return {

            "total_reaction_occurrences": 0,

            "unique_reaction_terms": 0,

            "most_frequent_reactions": {},

            "most_frequent_serious_reactions": {},
        }

    reactions = reactions.copy()

    reactions["reaction_pt"] = (
        reactions["reaction_pt"]
        .astype("string")
        .str.strip()
    )

    reactions = reactions[
        reactions["reaction_pt"].notna()
    ]

    reactions = reactions[
        reactions["reaction_pt"] != ""
    ]

    total_reactions = len(reactions)

    unique_reactions = (
        reactions["reaction_pt"]
        .nunique()
    )

    most_frequent = (
        reactions["reaction_pt"]
        .value_counts()
        .head(TOP_N)
        .to_dict()
    )

    # --------------------------------------------------------
    # SERIOUS REACTIONS
    # --------------------------------------------------------

    serious_reactions = pd.DataFrame()

    if "case_serious" in reactions.columns:

        serious_mask = (
            normalize_string(
                reactions["case_serious"]
            )
            .isin(["1", "true", "yes", "serious"])
        )

        serious_reactions = reactions[
            serious_mask
        ]

    serious_counts = {}

    if not serious_reactions.empty:

        serious_counts = (
            serious_reactions["reaction_pt"]
            .value_counts()
            .head(TOP_N)
            .to_dict()
        )

    return {

        "total_reaction_occurrences":
            int(total_reactions),

        "unique_reaction_terms":
            int(unique_reactions),

        "most_frequent_reactions":
            {
                str(key): int(value)
                for key, value
                in most_frequent.items()
            },

        "most_frequent_serious_reactions":
            {
                str(key): int(value)
                for key, value
                in serious_counts.items()
            },
    }


# ============================================================
# REACTION FREQUENCY BY MONTH
# ============================================================

def analyze_reaction_trends(reactions, cases):
    """
    Calculate monthly reaction frequencies.

    Reactions are joined to their case's report date.
    """

    if reactions.empty:
        return {}

    if "report_date" not in cases.columns:
        return {}

    case_dates = cases[
        [
            "safetyreportid",
            "report_date"
        ]
    ].copy()

    case_dates["report_date"] = pd.to_datetime(
        case_dates["report_date"],
        errors="coerce"
    )

    merged = reactions.merge(
        case_dates,
        on="safetyreportid",
        how="left"
    )

    merged = merged[
        merged["report_date"].notna()
    ]

    if merged.empty:
        return {}

    merged["month"] = (
        merged["report_date"]
        .dt.to_period("M")
        .astype(str)
    )

    monthly_counts = (
        merged
        .groupby("month")
        .size()
        .sort_index()
    )

    return {
        month: int(count)
        for month, count
        in monthly_counts.items()
    }


# ============================================================
# CASE TREND ANALYSIS
# ============================================================

def analyze_case_trends(cases):
    """
    Calculate monthly case counts and identify
    observed increases/decreases.

    This does NOT make a safety signal conclusion.
    """

    if "report_date" not in cases.columns:

        return {
            "monthly_case_counts": {},
            "trend_observation": "Reporting dates unavailable."
        }

    dates = pd.to_datetime(
        cases["report_date"],
        errors="coerce"
    )

    valid_dates = dates.dropna()

    if valid_dates.empty:

        return {
            "monthly_case_counts": {},
            "trend_observation":
                "No valid reporting dates available."
        }

    months = (
        valid_dates
        .dt.to_period("M")
        .astype(str)
    )

    monthly = (
        months
        .value_counts()
        .sort_index()
    )

    monthly_dict = {
        str(month): int(count)
        for month, count
        in monthly.items()
    }

    # --------------------------------------------------------
    # OBSERVED TREND
    # --------------------------------------------------------

    trend_observation = (
        "Insufficient monthly observations "
        "to describe a trend."
    )

    if len(monthly) >= 2:

        first_count = int(
            monthly.iloc[0]
        )

        last_count = int(
            monthly.iloc[-1]
        )

        if first_count == 0:

            trend_observation = (
                "The first observed month "
                "contains zero cases; "
                "a percentage change cannot "
                "be calculated."
            )

        else:

            change = (
                (last_count - first_count)
                / first_count
                * 100
            )

            if change > 0:

                trend_observation = (
                    f"Observed case reporting "
                    f"increased by "
                    f"{round(change, 2)}% "
                    f"between the first and "
                    f"last observed months."
                )

            elif change < 0:

                trend_observation = (
                    f"Observed case reporting "
                    f"decreased by "
                    f"{round(abs(change), 2)}% "
                    f"between the first and "
                    f"last observed months."
                )

            else:

                trend_observation = (
                    "Observed case reporting "
                    "was unchanged between "
                    "the first and last "
                    "observed months."
                )

    return {

        "monthly_case_counts":
            monthly_dict,

        "trend_observation":
            trend_observation,
    }


# ============================================================
# COMBINED MONTHLY TREND ANALYSIS
# ============================================================

def analyze_trends(cases, reactions):
    """
    Combine case and reaction trends.
    """

    case_trends = analyze_case_trends(
        cases
    )

    reaction_trends = analyze_reaction_trends(
        reactions,
        cases
    )

    return {

        "case_trends":
            case_trends,

        "reaction_trends":
            reaction_trends,
    }


# ============================================================
# OUTCOME ANALYSIS
# ============================================================

def analyze_outcomes(cases, reactions):
    """
    Analyze patient outcomes when outcome information
    is available in the preprocessed data.

    The preprocessing layer may not have an outcome
    column if the source dataset does not provide one.

    We therefore detect available outcome columns
    instead of fabricating outcome information.
    """

    # Possible outcome columns
    candidate_columns = [
        "patient_patientoutcome",
        "patient_outcome",
        "outcome",
        "patient_outcome_code",
    ]

    outcome_column = None

    for column in candidate_columns:

        if column in cases.columns:

            outcome_column = column
            break

    if outcome_column is None:

        # Fatal outcome can still be represented
        # from seriousnessdeath if available.

        if "seriousnessdeath" in cases.columns:

            death_values = normalize_string(
                cases["seriousnessdeath"]
            )

            fatal_count = int(
                death_values
                .isin(["1", "true", "yes"])
                .sum()
            )

            return {

                "available": True,

                "source": "seriousnessdeath",

                "outcome_distribution": {

                    "fatal_or_death_reported":
                        fatal_count,

                    "other_outcomes":
                        "Not available in supplied "
                        "preprocessed data."
                },

                "limitation":
                    "Detailed patient outcome "
                    "categories were not available "
                    "in the preprocessed dataset."
            }

        return {

            "available": False,

            "outcome_distribution": {},

            "limitation":
                "Patient outcome information "
                "was not available in the "
                "supplied dataset."
        }

    return {

        "available": True,

        "source": outcome_column,

        "outcome_distribution":
            value_counts_dict(
                cases[outcome_column]
            )
    }


# ============================================================
# ALERT ANALYSIS
# ============================================================

def analyze_alerts(cases):
    """
    Identify deterministic alert/priority categories.

    These are observations only.
    They are NOT interpreted as confirmed safety signals.
    """

    total_cases = len(cases)

    alerts = {}

    # --------------------------------------------------------
    # EXPEDITED CASES
    # --------------------------------------------------------

    if "fulfillexpeditecriteria" in cases.columns:

        expedite = (
            normalize_string(
                cases["fulfillexpeditecriteria"]
            )
            .isin(["1", "true", "yes"])
        )

        count = int(
            expedite.sum()
        )

        alerts["expedite_cases"] = {

            "count": count,

            "percentage": percentage(
                count,
                total_cases
            ),

            "interpretation":
                "Cases meeting the supplied "
                "expedite criterion."
        }

    # --------------------------------------------------------
    # DEATH CASES
    # --------------------------------------------------------

    if "seriousnessdeath" in cases.columns:

        death = (
            normalize_string(
                cases["seriousnessdeath"]
            )
            .isin(["1", "true", "yes"])
        )

        count = int(
            death.sum()
        )

        alerts["death_cases"] = {

            "count": count,

            "percentage": percentage(
                count,
                total_cases
            ),

            "interpretation":
                "Cases containing a supplied "
                "death seriousness indicator."
        }

    # --------------------------------------------------------
    # LIFE-THREATENING CASES
    # --------------------------------------------------------

    if "seriousnesslifethreatening" in cases.columns:

        life_threatening = (
            normalize_string(
                cases[
                    "seriousnesslifethreatening"
                ]
            )
            .isin(["1", "true", "yes"])
        )

        count = int(
            life_threatening.sum()
        )

        alerts["life_threatening_cases"] = {

            "count": count,

            "percentage": percentage(
                count,
                total_cases
            ),

            "interpretation":
                "Cases containing a supplied "
                "life-threatening seriousness "
                "indicator."
        }

    return alerts


# ============================================================
# REACTION CONCENTRATION ANALYSIS
# ============================================================

def analyze_reaction_concentrations(
    reactions,
    cases
):
    """
    Identify reactions concentrated in a subset
    of the reporting period.

    This is descriptive only.
    """

    if reactions.empty:

        return {}

    if "report_date" not in cases.columns:

        return {}

    dates = cases[
        [
            "safetyreportid",
            "report_date"
        ]
    ].copy()

    dates["report_date"] = pd.to_datetime(
        dates["report_date"],
        errors="coerce"
    )

    merged = reactions.merge(
        dates,
        on="safetyreportid",
        how="left"
    )

    merged = merged[
        merged["report_date"].notna()
    ]

    if merged.empty:
        return {}

    merged["month"] = (
        merged["report_date"]
        .dt.to_period("M")
        .astype(str)
    )

    top_reactions = (
        merged["reaction_pt"]
        .value_counts()
        .head(5)
        .index
    )

    concentrations = {}

    for reaction in top_reactions:

        subset = merged[
            merged["reaction_pt"] == reaction
        ]

        monthly = (
            subset["month"]
            .value_counts()
            .sort_index()
        )

        concentrations[str(reaction)] = {
            str(month): int(count)
            for month, count
            in monthly.items()
        }

    return concentrations


# ============================================================
# DATA QUALITY / LIMITATIONS
# ============================================================

def analyze_data_quality(
    cases,
    reactions,
    drugs
):
    """
    Identify missing or unavailable information
    that should be disclosed in the Evidence JSON.
    """

    limitations = []

    # --------------------------------------------------------
    # AGE
    # --------------------------------------------------------

    if "age_years" in cases.columns:

        missing_age = int(
            cases["age_years"]
            .isna()
            .sum()
        )

        if missing_age > 0:

            limitations.append(
                f"Age was unavailable or "
                f"could not be normalized for "
                f"{missing_age} cases."
            )

    # --------------------------------------------------------
    # SEX
    # --------------------------------------------------------

    if "patient_patientsex" in cases.columns:

        missing_sex = int(
            cases["patient_patientsex"]
            .isna()
            .sum()
        )

        if missing_sex > 0:

            limitations.append(
                f"Sex was missing for "
                f"{missing_sex} cases."
            )

    # --------------------------------------------------------
    # REPORT DATE
    # --------------------------------------------------------

    if "report_date" in cases.columns:

        dates = pd.to_datetime(
            cases["report_date"],
            errors="coerce"
        )

        missing_dates = int(
            dates.isna().sum()
        )

        if missing_dates > 0:

            limitations.append(
                f"Reporting date was unavailable "
                f"for {missing_dates} cases."
            )

    # --------------------------------------------------------
    # SOC
    # --------------------------------------------------------

    limitations.append(
        "System Organ Class (SOC) analysis was "
        "not performed unless SOC information "
        "was explicitly supplied in the dataset."
    )

    # --------------------------------------------------------
    # EXPECTEDNESS
    # --------------------------------------------------------

    limitations.append(
        "Expectedness analysis was not performed "
        "because label/CCDS/reference safety "
        "information was not supplied."
    )

    # --------------------------------------------------------
    # CAUSALITY
    # --------------------------------------------------------

    limitations.append(
        "No causality inference was performed "
        "beyond information explicitly present "
        "in the supplied dataset."
    )

    # --------------------------------------------------------
    # REGULATORY ACTION
    # --------------------------------------------------------

    limitations.append(
        "No regulatory or safety action conclusion "
        "was generated unless explicit action "
        "information was supplied."
    )

    return limitations


# ============================================================
# REPORTING PERIOD
# ============================================================

def determine_reporting_period(cases):
    """
    Determine the available reporting period
    from report_date.
    """

    if "report_date" not in cases.columns:

        return {

            "available": False,

            "start_date": None,

            "end_date": None
        }

    dates = pd.to_datetime(
        cases["report_date"],
        errors="coerce"
    ).dropna()

    if dates.empty:

        return {

            "available": False,

            "start_date": None,

            "end_date": None
        }

    return {

        "available": True,

        "start_date":
            dates.min().strftime(
                "%Y-%m-%d"
            ),

        "end_date":
            dates.max().strftime(
                "%Y-%m-%d"
            ),

        "number_of_months":
            int(
                dates.dt.to_period("M")
                .nunique()
            )
    }


# ============================================================
# CASE COUNTS BY MONTH
# ============================================================

def case_counts_by_month(cases):
    """
    Return deterministic monthly case counts.
    """

    if "report_date" not in cases.columns:
        return {}

    dates = pd.to_datetime(
        cases["report_date"],
        errors="coerce"
    )

    valid = dates.dropna()

    if valid.empty:
        return {}

    months = (
        valid
        .dt.to_period("M")
        .astype(str)
    )

    counts = (
        months
        .value_counts()
        .sort_index()
    )

    return {
        str(month): int(count)
        for month, count
        in counts.items()
    }

def analyze_case_trends(cases):
    """
    Calculate deterministic case-volume trend statistics.

    Returns:
        dict: Monthly case counts and derived trend statistics.
    """

    monthly_counts = case_counts_by_month(
        cases
    )

    if not monthly_counts:
        return {
            "monthly_case_counts": {},
            "highest_month": None,
            "lowest_month": None,
            "first_month": None,
            "last_month": None,
            "absolute_change": None,
            "percentage_change": None
        }

    # ---------------------------------------------------------
    # First and last observed months
    # ---------------------------------------------------------

    months = list(
        monthly_counts.keys()
    )

    first_month = months[0]
    last_month = months[-1]

    first_count = monthly_counts[
        first_month
    ]

    last_count = monthly_counts[
        last_month
    ]

    # ---------------------------------------------------------
    # Highest and lowest months
    # ---------------------------------------------------------

    highest_month = max(
        monthly_counts,
        key=monthly_counts.get
    )

    lowest_month = min(
        monthly_counts,
        key=monthly_counts.get
    )

    highest_count = monthly_counts[
        highest_month
    ]

    lowest_count = monthly_counts[
        lowest_month
    ]

    # ---------------------------------------------------------
    # Absolute change
    # ---------------------------------------------------------

    absolute_change = (
        last_count -
        first_count
    )

    # ---------------------------------------------------------
    # Percentage change
    # ---------------------------------------------------------

    if first_count == 0:
        percentage_change = None

    else:
        percentage_change = round(
            (
                absolute_change /
                first_count
            ) * 100,
            2
        )

    # ---------------------------------------------------------
    # Return deterministic result
    # ---------------------------------------------------------

    return {
        "monthly_case_counts": monthly_counts,

        "highest_month": {
            "month": highest_month,
            "count": int(highest_count)
        },

        "lowest_month": {
            "month": lowest_month,
            "count": int(lowest_count)
        },

        "first_month": {
            "month": first_month,
            "count": int(first_count)
        },

        "last_month": {
            "month": last_month,
            "count": int(last_count)
        },

        "absolute_change": int(
            absolute_change
        ),

        "percentage_change": percentage_change
    }


# ============================================================
# BUILD EVIDENCE JSON
# ============================================================

def build_evidence(
    cases,
    reactions,
    drugs
):
    """
    Build the complete Evidence JSON.

    Every downstream LLM section should use
    this object rather than the raw Excel data.
    """

    reporting_period = (
        determine_reporting_period(cases)
    )

    case_summary = analyze_cases(
        cases
    )

    seriousness = analyze_seriousness(
        cases
    )

    demographics = analyze_demographics(
        cases
    )

    reaction_analysis = analyze_reactions(
        reactions
    )

    outcome_analysis = analyze_outcomes(
        cases,
        reactions
    )

    trend_analysis = analyze_trends(
        cases,
        reactions
    )

    alerts = analyze_alerts(
        cases
    )

    reaction_concentrations = (
        analyze_reaction_concentrations(
            reactions,
            cases
        )
    )

    limitations = analyze_data_quality(
        cases,
        reactions,
        drugs
    )

    case_trends = analyze_case_trends(
    cases
    )

    # --------------------------------------------------------
    # FINAL EVIDENCE OBJECT
    # --------------------------------------------------------

    evidence = {

    "metadata": {

        "analysis_type":
            "Deterministic ICSR safety analysis",

        "target_product":
            "Bisoprolol",

        "source":
            "Bisoprolol ICSR dataset",

        "analysis_principle":
            "Python-calculated facts are the "
            "source of truth."
    },

    "reporting_period":
        reporting_period,

    "case_summary": {

        **case_summary,

        "cases_by_month":
            case_counts_by_month(cases)
    },

    "seriousness":
        seriousness,

    "demographics":
        demographics,

    "reactions": {

        **reaction_analysis,

        "frequency_by_month":
            analyze_reaction_trends(
                reactions,
                cases
            ),

        "reaction_concentrations":
            reaction_concentrations
    },

    "outcomes":
        outcome_analysis,

    "trends": {

        "case_trends":
            analyze_case_trends(
                cases
            ),

        "reaction_trends":
            analyze_reaction_trends(
                reactions,
                cases
            )
    },

    "alerts":
        alerts,

    "data_quality": {

        "cases":
            len(cases),

        "reaction_records":
            len(reactions),

        "drug_records":
            len(drugs),

        "missingness_notes":
            limitations
    },

    "limitations":
        limitations
}

    return clean_dict(
        evidence
    )


# ============================================================
# SAVE EVIDENCE JSON
# ============================================================

def save_evidence(evidence):
    """
    Save Evidence JSON to output directory.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        EVIDENCE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            evidence,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"Evidence JSON saved to: "
        f"{EVIDENCE_FILE}"
    )


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

def run_analysis():
    """
    Main entry point used by main.py.

    Returns:
        dict: Evidence JSON object
    """

    print("\n")
    print("=" * 60)
    print("DETERMINISTIC SAFETY ANALYSIS")
    print("=" * 60)

    # 1. Load
    cases, reactions, drugs = (
        load_processed_data()
    )

    # 2. Validate
    validate_data(
        cases,
        reactions,
        drugs
    )

    # 3. Build evidence
    evidence = build_evidence(
        cases,
        reactions,
        drugs
    )

    # 4. Save evidence
    save_evidence(
        evidence
    )

    # 5. Print summary
    print("\nAnalysis Summary")
    print("-" * 40)

    print(
        "Unique cases:",
        evidence[
            "case_summary"
        ][
            "total_unique_cases"
        ]
    )

    print(
        "Serious cases:",
        evidence[
            "case_summary"
        ][
            "serious_cases"
        ]
    )

    print(
        "Non-serious cases:",
        evidence[
            "case_summary"
        ][
            "non_serious_cases"
        ]
    )

    print(
        "Expedite/alert cases:",
        evidence[
            "case_summary"
        ][
            "expedite_alert_cases"
        ]
    )

    print(
        "Reaction occurrences:",
        evidence[
            "reactions"
        ][
            "total_reaction_occurrences"
        ]
    )

    print(
        "Unique reaction terms:",
        evidence[
            "reactions"
        ][
            "unique_reaction_terms"
        ]
    )

    print("\nTop reactions:")

    for reaction, count in (
        evidence[
            "reactions"
        ][
            "most_frequent_reactions"
        ].items()
    ):

        print(
            f"  {reaction}: {count}"
        )

    print("\nAnalysis complete.")

    return evidence


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    run_analysis()
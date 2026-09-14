"""Deterministic safety analysis. Python is the source of truth."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paths import CASES_FILE, DRUGS_FILE, EVIDENCE_FILE, OUTPUT_DIR, REACTIONS_FILE

TOP_N = 10


def clean_value(value):
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
    if isinstance(data, dict):
        return {key: clean_dict(value) for key, value in data.items()}
    if isinstance(data, list):
        return [clean_dict(value) for value in data]
    return clean_value(data)


def normalize_string(series):
    return series.astype("string").str.strip().str.lower()


def value_counts_dict(series, top_n=None):
    series = series.copy().fillna("unknown")
    series = series.astype(str).str.strip().replace("", "unknown")
    counts = series.value_counts()
    if top_n is not None:
        counts = counts.head(top_n)
    return {str(index): int(value) for index, value in counts.items()}


def percentage(part, total):
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)


def load_processed_data():
    print("Loading processed data...")
    if not CASES_FILE.exists():
        raise FileNotFoundError(f"Cases file not found: {CASES_FILE}")
    if not REACTIONS_FILE.exists():
        raise FileNotFoundError(f"Reactions file not found: {REACTIONS_FILE}")
    if not DRUGS_FILE.exists():
        raise FileNotFoundError(f"Drugs file not found: {DRUGS_FILE}")
    return pd.read_csv(CASES_FILE), pd.read_csv(REACTIONS_FILE), pd.read_csv(DRUGS_FILE)


def validate_data(cases, reactions, drugs):
    print("Validating processed data...")
    required_case_columns = [
        "safetyreportid",
        "serious",
        "fulfillexpeditecriteria",
        "patient_patientsex",
        "age_group",
    ]
    required_reaction_columns = ["safetyreportid", "reaction_pt"]
    required_drug_columns = ["safetyreportid", "active_substance"]
    missing_cases = [column for column in required_case_columns if column not in cases.columns]
    missing_reactions = [
        column for column in required_reaction_columns if column not in reactions.columns
    ]
    missing_drugs = [column for column in required_drug_columns if column not in drugs.columns]
    if missing_cases:
        raise ValueError("Missing case columns: " + ", ".join(missing_cases))
    if missing_reactions:
        raise ValueError("Missing reaction columns: " + ", ".join(missing_reactions))
    if missing_drugs:
        raise ValueError("Missing drug columns: " + ", ".join(missing_drugs))
    if cases["safetyreportid"].duplicated().any():
        raise ValueError("cases.csv contains duplicate safetyreportid values.")
    print("Validation passed.")


def analyze_cases(cases):
    total_cases = len(cases)
    seriousness_columns = [
        "serious",
        "seriousnessdeath",
        "seriousnesslifethreatening",
        "seriousnesshospitalization",
        "seriousnessdisabling",
        "seriousnesscongenitalanomali",
        "seriousnessother",
    ]
    present = [column for column in seriousness_columns if column in cases.columns]
    serious = (
        cases[present].apply(lambda col: normalize_string(col).isin(["1", "yes", "y"])).any(axis=1)
    )
    non_serious = normalize_string(cases["serious"]).isin(["0", "false", "no"])
    unknown_serious = ~(serious | non_serious)
    expedite = normalize_string(cases["fulfillexpeditecriteria"]).isin(["1", "true", "yes"])
    return {
        "total_unique_cases": total_cases,
        "serious_cases": int(serious.sum()),
        "non_serious_cases": int(non_serious.sum()),
        "unknown_seriousness": int(unknown_serious.sum()),
        "serious_percentage": percentage(serious.sum(), total_cases),
        "non_serious_percentage": percentage(non_serious.sum(), total_cases),
        "expedite_alert_cases": int(expedite.sum()),
        "expedite_alert_percentage": percentage(expedite.sum(), total_cases),
    }


def analyze_seriousness(cases):
    seriousness_columns = {
        "death": "seriousnessdeath",
        "life_threatening": "seriousnesslifethreatening",
        "hospitalization": "seriousnesshospitalization",
        "disability": "seriousnessdisabling",
        "congenital_anomaly": "seriousnesscongenitalanomali",
        "other_serious": "seriousnessother",
    }
    result = {}
    total_cases = len(cases)
    for name, column in seriousness_columns.items():
        if column not in cases.columns:
            result[name] = {"available": False, "count": None, "percentage": None}
            continue
        positive = normalize_string(cases[column]).isin(["1", "true", "yes"])
        count = int(positive.sum())
        result[name] = {
            "available": True,
            "count": count,
            "percentage": percentage(count, total_cases),
        }
    return result


def analyze_demographics(cases):
    result = {}
    if "age_years" in cases.columns:
        age = pd.to_numeric(cases["age_years"], errors="coerce")
        valid_age = age.dropna()
        age_summary = {
            "available_cases": int(valid_age.count()),
            "missing_cases": int(age.isna().sum()),
        }
        if not valid_age.empty:
            age_summary.update(
                {
                    "minimum_years": round(float(valid_age.min()), 2),
                    "maximum_years": round(float(valid_age.max()), 2),
                    "mean_years": round(float(valid_age.mean()), 2),
                    "median_years": round(float(valid_age.median()), 2),
                }
            )
        result["age"] = age_summary
    else:
        result["age"] = {"available_cases": 0, "missing_cases": len(cases)}
    if "age_group" in cases.columns:
        result["age_group_distribution"] = value_counts_dict(cases["age_group"])
    result["sex_distribution"] = value_counts_dict(cases["patient_patientsex"])
    if "primarysourcecountry" in cases.columns:
        result["primary_source_country"] = value_counts_dict(cases["primarysourcecountry"], TOP_N)
    else:
        result["primary_source_country"] = {}
    if "occurcountry" in cases.columns:
        result["occurrence_country"] = value_counts_dict(cases["occurcountry"], TOP_N)
    else:
        result["occurrence_country"] = {}
    return result


def analyze_reactions(reactions):
    if reactions.empty:
        return {
            "total_reaction_occurrences": 0,
            "unique_reaction_terms": 0,
            "most_frequent_reactions": {},
            "most_frequent_serious_reactions": {},
        }
    reactions = reactions.copy()
    reactions["reaction_pt"] = reactions["reaction_pt"].astype("string").str.strip()
    reactions = reactions[reactions["reaction_pt"].notna()]
    reactions = reactions[reactions["reaction_pt"] != ""]
    most_frequent = reactions["reaction_pt"].value_counts().head(TOP_N).to_dict()
    serious_counts = {}
    if "case_serious" in reactions.columns:
        serious_mask = normalize_string(reactions["case_serious"]).isin(
            ["1", "true", "yes", "serious"]
        )
        serious_reactions = reactions[serious_mask]
        if not serious_reactions.empty:
            serious_counts = serious_reactions["reaction_pt"].value_counts().head(TOP_N).to_dict()
    return {
        "total_reaction_occurrences": int(len(reactions)),
        "unique_reaction_terms": int(reactions["reaction_pt"].nunique()),
        "most_frequent_reactions": {str(key): int(value) for key, value in most_frequent.items()},
        "most_frequent_serious_reactions": {
            str(key): int(value) for key, value in serious_counts.items()
        },
    }


def analyze_reaction_trends(reactions, cases):
    if reactions.empty or "report_date" not in cases.columns:
        return {}
    case_dates = cases[["safetyreportid", "report_date"]].copy()
    case_dates["report_date"] = pd.to_datetime(case_dates["report_date"], errors="coerce")
    merged = reactions.merge(case_dates, on="safetyreportid", how="left")
    merged = merged[merged["report_date"].notna()]
    if merged.empty:
        return {}
    merged["month"] = merged["report_date"].dt.to_period("M").astype(str)
    monthly_counts = merged.groupby("month").size().sort_index()
    return {month: int(count) for month, count in monthly_counts.items()}


def case_counts_by_month(cases):
    if "report_date" not in cases.columns:
        return {}
    dates = pd.to_datetime(cases["report_date"], errors="coerce")
    valid = cases.loc[dates.notna()].copy()
    if valid.empty:
        return {}
    valid["month"] = (
        pd.to_datetime(valid["report_date"], errors="coerce").dt.to_period("M").astype(str)
    )
    monthly_counts = valid.groupby("month").size().sort_index()
    return {month: int(count) for month, count in monthly_counts.items()}


def analyze_case_trends(cases):
    monthly_counts = case_counts_by_month(cases)
    if not monthly_counts:
        return {
            "monthly_case_counts": {},
            "highest_month": None,
            "lowest_month": None,
            "first_month": None,
            "last_month": None,
            "absolute_change": None,
            "percentage_change": None,
        }
    months = list(monthly_counts.keys())
    first_month = months[0]
    last_month = months[-1]
    first_count = monthly_counts[first_month]
    last_count = monthly_counts[last_month]
    highest_month = max(monthly_counts, key=monthly_counts.get)
    lowest_month = min(monthly_counts, key=monthly_counts.get)
    absolute_change = last_count - first_count
    percentage_change = (
        None if first_count == 0 else round((absolute_change / first_count) * 100, 2)
    )
    return {
        "monthly_case_counts": monthly_counts,
        "highest_month": {"month": highest_month, "count": int(monthly_counts[highest_month])},
        "lowest_month": {"month": lowest_month, "count": int(monthly_counts[lowest_month])},
        "first_month": {"month": first_month, "count": int(first_count)},
        "last_month": {"month": last_month, "count": int(last_count)},
        "absolute_change": int(absolute_change),
        "percentage_change": percentage_change,
    }


def analyze_trends(cases, reactions):
    return {
        "case_trends": analyze_case_trends(cases),
        "reaction_trends": analyze_reaction_trends(reactions, cases),
    }


def analyze_outcomes(cases, reactions):
    result = {"available": False}
    if "reaction_outcome" in reactions.columns and not reactions.empty:
        result = {
            "available": True,
            "reaction_outcome_distribution": value_counts_dict(reactions["reaction_outcome"]),
        }
    return result


def analyze_alerts(cases):
    total_cases = len(cases)
    alerts = {}
    if "fulfillexpeditecriteria" in cases.columns:
        expedite = normalize_string(cases["fulfillexpeditecriteria"]).isin(["1", "true", "yes"])
        count = int(expedite.sum())
        alerts["expedite_cases"] = {
            "count": count,
            "percentage": percentage(count, total_cases),
            "interpretation": "Cases meeting the supplied expedite criterion.",
        }
    if "seriousnessdeath" in cases.columns:
        death = normalize_string(cases["seriousnessdeath"]).isin(["1", "true", "yes"])
        count = int(death.sum())
        alerts["death_cases"] = {
            "count": count,
            "percentage": percentage(count, total_cases),
            "interpretation": "Cases containing a supplied death seriousness indicator.",
        }
    if "seriousnesslifethreatening" in cases.columns:
        life_threatening = normalize_string(cases["seriousnesslifethreatening"]).isin(
            ["1", "true", "yes"]
        )
        count = int(life_threatening.sum())
        alerts["life_threatening_cases"] = {
            "count": count,
            "percentage": percentage(count, total_cases),
            "interpretation": "Cases containing a supplied life-threatening seriousness indicator.",
        }
    return alerts


def analyze_reaction_concentrations(reactions, cases):
    monthly = analyze_reaction_trends(reactions, cases)
    if not monthly or reactions.empty:
        return {}
    total = len(reactions)
    concentrations = {}
    top = reactions["reaction_pt"].astype("string").str.strip().value_counts().head(5)
    for reaction, count in top.items():
        concentrations[str(reaction)] = {
            "count": int(count),
            "percentage_of_reactions": percentage(count, total),
        }
    return concentrations


def analyze_data_quality(cases, reactions, drugs):
    limitations = []
    if "age_years" in cases.columns:
        missing_age = int(cases["age_years"].isna().sum())
        if missing_age > 0:
            limitations.append(
                f"Age was unavailable or could not be normalized for {missing_age} cases."
            )
    if "patient_patientsex" in cases.columns:
        missing_sex = int(cases["patient_patientsex"].isna().sum())
        if missing_sex > 0:
            limitations.append(f"Sex was missing for {missing_sex} cases.")
    if "report_date" in cases.columns:
        missing_dates = int(pd.to_datetime(cases["report_date"], errors="coerce").isna().sum())
        if missing_dates > 0:
            limitations.append(f"Reporting date was unavailable for {missing_dates} cases.")
    limitations.extend(
        [
            "System Organ Class (SOC) analysis was not performed unless SOC information was explicitly supplied in the dataset.",
            "Expectedness analysis was not performed because label/CCDS/reference safety information was not supplied.",
            "No causality inference was performed beyond information explicitly present in the supplied dataset.",
            "No regulatory or safety action conclusion was generated unless explicit action information was supplied.",
        ]
    )
    return limitations


def determine_reporting_period(cases):
    if "report_date" not in cases.columns:
        return {"available": False, "start_date": None, "end_date": None, "number_of_months": None}
    dates = pd.to_datetime(cases["report_date"], errors="coerce").dropna()
    if dates.empty:
        return {"available": False, "start_date": None, "end_date": None, "number_of_months": None}
    start = dates.min()
    end = dates.max()
    months = (end.to_period("M") - start.to_period("M")).n + 1
    return {
        "available": True,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "number_of_months": int(months),
    }


def build_evidence(cases, reactions, drugs):
    limitations = analyze_data_quality(cases, reactions, drugs)
    reaction_analysis = analyze_reactions(reactions)
    evidence = {
        "metadata": {
            "analysis_type": "Deterministic ICSR safety analysis",
            "target_product": "Bisoprolol",
            "source": "Bisoprolol ICSR dataset",
            "analysis_principle": "Python-calculated facts are the source of truth.",
        },
        "reporting_period": determine_reporting_period(cases),
        "case_summary": {
            **analyze_cases(cases),
            "cases_by_month": case_counts_by_month(cases),
        },
        "seriousness": analyze_seriousness(cases),
        "demographics": analyze_demographics(cases),
        "reactions": {
            **reaction_analysis,
            "frequency_by_month": analyze_reaction_trends(reactions, cases),
            "reaction_concentrations": analyze_reaction_concentrations(reactions, cases),
        },
        "outcomes": analyze_outcomes(cases, reactions),
        "trends": analyze_trends(cases, reactions),
        "alerts": analyze_alerts(cases),
        "data_quality": {
            "cases": len(cases),
            "reaction_records": len(reactions),
            "drug_records": len(drugs),
            "missingness_notes": limitations,
        },
        "limitations": limitations,
    }
    return clean_dict(evidence)


def save_evidence(evidence):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_FILE, "w", encoding="utf-8") as file:
        json.dump(evidence, file, indent=2, ensure_ascii=False)
    print(f"Evidence JSON saved to: {EVIDENCE_FILE}")


def run_analysis():
    print("\n")
    print("=" * 60)
    print("DETERMINISTIC SAFETY ANALYSIS")
    print("=" * 60)
    cases, reactions, drugs = load_processed_data()
    validate_data(cases, reactions, drugs)
    evidence = build_evidence(cases, reactions, drugs)
    save_evidence(evidence)
    print("\nAnalysis Summary")
    print("-" * 40)
    print("Unique cases:", evidence["case_summary"]["total_unique_cases"])
    print("Serious cases:", evidence["case_summary"]["serious_cases"])
    print("Non-serious cases:", evidence["case_summary"]["non_serious_cases"])
    print("Expedite/alert cases:", evidence["case_summary"]["expedite_alert_cases"])
    print("Reaction occurrences:", evidence["reactions"]["total_reaction_occurrences"])
    print("Unique reaction terms:", evidence["reactions"]["unique_reaction_terms"])
    print("\nTop reactions:")
    for reaction, count in evidence["reactions"]["most_frequent_reactions"].items():
        print(f" {reaction}: {count}")
    print("\nAnalysis complete.")
    return evidence


if __name__ == "__main__":
    run_analysis()

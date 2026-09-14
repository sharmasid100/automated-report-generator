"""ICSR preprocessing for the PADER-style safety reporting pipeline."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paths import (
    CASES_FILE,
    DRUGS_FILE,
    FILTER_TO_TARGET_DRUG,
    INPUT_FILE,
    PROCESSED_DATA_DIR,
    REACTIONS_FILE,
    TARGET_DRUG_PATTERN,
)


def clean_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    return None if value == "" else value


def split_values(value):
    if pd.isna(value):
        return []
    value = str(value).strip()
    if not value:
        return []
    return [item.strip() for item in value.split(",")]


def get_item(values, index):
    if index < len(values):
        return values[index]
    return None


def contains_bisoprolol(value):
    if pd.isna(value):
        return False
    return bool(re.search(TARGET_DRUG_PATTERN, str(value).upper()))


def parse_date(value):
    if pd.isna(value):
        return pd.NaT
    value = str(value).strip()
    if not value:
        return pd.NaT
    if re.fullmatch(r"\d{8}", value):
        return pd.to_datetime(value, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(value, errors="coerce")


def derive_age_group(age):
    if pd.isna(age):
        return "unknown"
    if age < 1:
        return "infant"
    if age < 12:
        return "child"
    if age < 18:
        return "adolescent"
    if age < 65:
        return "adult"
    return "elderly"


def preprocess_data():
    print("\n" + "=" * 60)
    print("STARTING PREPROCESSING")
    print("=" * 60)

    print("\nLoading dataset...")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"ICSR dataset not found: {INPUT_FILE}. "
            "Place the Excel file in data/ or set ICSR_INPUT_FILE."
        )

    df = pd.read_excel(INPUT_FILE)
    print(f"Raw rows: {len(df)}")
    print(f"Raw columns: {len(df.columns)}")

    df.columns = df.columns.str.strip().str.lower()
    if df.columns.duplicated().any():
        duplicated_columns = df.columns[df.columns.duplicated()].tolist()
        raise ValueError(
            f"Duplicate column names detected after normalization: {duplicated_columns}"
        )

    df = df.replace(r"^\s*$", np.nan, regex=True)
    object_columns = df.select_dtypes(include="object").columns
    for column in object_columns:
        df[column] = df[column].astype("string").str.strip()

    required_columns = [
        "safetyreportid",
        "safetyreportversion",
        "serious",
        "seriousnessdeath",
        "seriousnesslifethreatening",
        "seriousnesshospitalization",
        "seriousnessdisabling",
        "seriousnesscongenitalanomali",
        "seriousnessother",
        "fulfillexpeditecriteria",
        "primarysourcecountry",
        "occurcountry",
        "reporttype",
        "patient_patientonsetage",
        "patient_patientonsetageunit",
        "patient_patientsex",
        "patient_reaction_reactionmeddrapt",
        "patient_reaction_reactionoutcome",
        "patient_drug_drugcharacterization",
        "patient_drug_medicinalproduct",
        "patient_drug_activesubstance_activesubstancename",
    ]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError("Required columns are missing:\n" + "\n".join(missing_columns))

    df["safetyreportid"] = pd.to_numeric(df["safetyreportid"], errors="coerce").astype("Int64")
    df["safetyreportversion"] = pd.to_numeric(df["safetyreportversion"], errors="coerce").fillna(0)

    print("\nSelecting latest version of each case...")
    df = df.sort_values(["safetyreportid", "safetyreportversion"])
    latest_cases = df.drop_duplicates(subset=["safetyreportid"], keep="last").copy()
    print(f"Unique cases after version handling: {len(latest_cases)}")

    latest_cases["contains_bisoprolol"] = latest_cases[
        "patient_drug_activesubstance_activesubstancename"
    ].apply(contains_bisoprolol)
    bisoprolol_case_count = int(latest_cases["contains_bisoprolol"].sum())
    print(f"Cases containing Bisoprolol: {bisoprolol_case_count}")
    print(f"Cases without Bisoprolol: {len(latest_cases) - bisoprolol_case_count}")

    if FILTER_TO_TARGET_DRUG:
        latest_cases = latest_cases[latest_cases["contains_bisoprolol"]].copy()
        print(f"\nFiltering to Bisoprolol cases: {len(latest_cases)}")

    valid_case_ids = set(latest_cases["safetyreportid"])

    case_columns = [
        "safetyreportid",
        "safetyreportversion",
        "primarysourcecountry",
        "occurcountry",
        "reporttype",
        "report_date",
        "serious",
        "seriousnessdeath",
        "seriousnesslifethreatening",
        "seriousnesshospitalization",
        "seriousnessdisabling",
        "seriousnesscongenitalanomali",
        "seriousnessother",
        "fulfillexpeditecriteria",
        "patient_patientonsetage",
        "patient_patientonsetageunit",
        "patient_patientsex",
        "patient_patientweight",
        "primarysource_qualification",
        "patient_summary_narrativeincludeclinical",
    ]
    case_columns = [column for column in case_columns if column in latest_cases.columns]
    cases = latest_cases[case_columns].copy()

    if "report_date" in cases.columns:
        cases["report_date"] = cases["report_date"].apply(parse_date)

    if "patient_patientonsetage" in cases.columns:
        cases["age"] = pd.to_numeric(cases["patient_patientonsetage"], errors="coerce")
    else:
        cases["age"] = np.nan

    if "patient_patientonsetageunit" in cases.columns:
        cases["age_unit"] = (
            cases["patient_patientonsetageunit"].astype("string").str.lower().str.strip()
        )
    else:
        cases["age_unit"] = pd.Series(pd.NA, index=cases.index, dtype="string")

    cases["age_years"] = np.nan
    cases.loc[cases["age_unit"].eq("year"), "age_years"] = cases.loc[
        cases["age_unit"].eq("year"), "age"
    ]
    cases.loc[cases["age_unit"].eq("month"), "age_years"] = (
        cases.loc[cases["age_unit"].eq("month"), "age"] / 12
    )
    cases.loc[cases["age_unit"].eq("day"), "age_years"] = (
        cases.loc[cases["age_unit"].eq("day"), "age"] / 365.25
    )
    cases["age_group"] = cases["age_years"].apply(derive_age_group)

    categorical_columns = [
        "primarysourcecountry",
        "occurcountry",
        "reporttype",
        "serious",
        "seriousnessdeath",
        "seriousnesslifethreatening",
        "seriousnesshospitalization",
        "seriousnessdisabling",
        "seriousnesscongenitalanomali",
        "seriousnessother",
        "fulfillexpeditecriteria",
        "patient_patientsex",
        "primarysource_qualification",
    ]
    for column in categorical_columns:
        if column in cases.columns:
            cases[column] = cases[column].astype("string").str.lower().str.strip()

    reaction_rows = []
    for _, row in latest_cases.iterrows():
        case_id = row["safetyreportid"]
        if case_id not in valid_case_ids:
            continue
        reactions_list = split_values(row["patient_reaction_reactionmeddrapt"])
        outcomes = split_values(row["patient_reaction_reactionoutcome"])
        meddra_versions = split_values(
            row.get("patient_reaction_reactionmeddraversionpt")
            if "patient_reaction_reactionmeddraversionpt" in latest_cases.columns
            else None
        )
        for i, reaction in enumerate(reactions_list):
            if not reaction:
                continue
            reaction_rows.append(
                {
                    "safetyreportid": case_id,
                    "reaction_pt": reaction,
                    "reaction_outcome": get_item(outcomes, i),
                    "meddra_version": get_item(meddra_versions, i),
                    "case_serious": row["serious"],
                    "case_death": row["seriousnessdeath"],
                    "case_life_threatening": row["seriousnesslifethreatening"],
                    "case_hospitalization": row["seriousnesshospitalization"],
                    "case_disabling": row["seriousnessdisabling"],
                    "case_congenital_anomaly": row["seriousnesscongenitalanomali"],
                    "case_other_serious": row["seriousnessother"],
                }
            )
    reactions = pd.DataFrame(reaction_rows)

    drug_rows = []
    optional_drug_fields = {
        "patient_drug_drugdosagetext": "dose_text",
        "patient_drug_drugstructuredosagenumb": "dose_number",
        "patient_drug_drugstructuredosageunit": "dose_unit",
        "patient_drug_drugadministrationroute": "route",
        "patient_drug_drugindication": "indication",
        "patient_drug_actiondrug": "action_taken",
        "patient_drug_drugstartdate": "start_date",
        "patient_drug_drugenddate": "end_date",
    }

    for _, row in latest_cases.iterrows():
        case_id = row["safetyreportid"]
        if case_id not in valid_case_ids:
            continue
        characterizations = split_values(row["patient_drug_drugcharacterization"])
        medicinal_products = split_values(row["patient_drug_medicinalproduct"])
        active_substances = split_values(row["patient_drug_activesubstance_activesubstancename"])
        split_optional = {
            dest: split_values(row[source]) if source in latest_cases.columns else []
            for source, dest in optional_drug_fields.items()
        }
        number_of_drugs = max(
            len(characterizations),
            len(medicinal_products),
            len(active_substances),
            0,
        )
        for i in range(number_of_drugs):
            active_substance = get_item(active_substances, i)
            if not contains_bisoprolol(active_substance):
                continue
            record = {
                "safetyreportid": case_id,
                "drug_characterization": get_item(characterizations, i),
                "medicinal_product": get_item(medicinal_products, i),
                "active_substance": active_substance,
            }
            for dest, values in split_optional.items():
                record[dest] = get_item(values, i)
            drug_rows.append(record)
    target_drugs = pd.DataFrame(drug_rows)

    if not reactions.empty:
        reactions["reaction_pt"] = reactions["reaction_pt"].astype("string").str.strip()
        reactions["reaction_outcome"] = (
            reactions["reaction_outcome"].astype("string").str.lower().str.strip()
        )
    if not target_drugs.empty:
        target_drugs["active_substance"] = (
            target_drugs["active_substance"].astype("string").str.strip().str.upper()
        )
        if "drug_characterization" in target_drugs.columns:
            target_drugs["drug_characterization"] = (
                target_drugs["drug_characterization"].astype("string").str.lower().str.strip()
            )
        if "route" in target_drugs.columns:
            target_drugs["route"] = target_drugs["route"].astype("string").str.lower().str.strip()
        if "action_taken" in target_drugs.columns:
            target_drugs["action_taken"] = (
                target_drugs["action_taken"].astype("string").str.lower().str.strip()
            )

    cases = cases.drop_duplicates(subset=["safetyreportid"])
    reactions = reactions.drop_duplicates()
    target_drugs = target_drugs.drop_duplicates()

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    cases.to_csv(CASES_FILE, index=False)
    reactions.to_csv(REACTIONS_FILE, index=False)
    target_drugs.to_csv(DRUGS_FILE, index=False)

    print("\n" + "=" * 60)
    print("PREPROCESSING COMPLETE")
    print("=" * 60)
    print(f"Raw Excel rows      : {len(df)}")
    print(f"Unique cases        : {df['safetyreportid'].nunique()}")
    print(f"Cases retained      : {len(cases)}")
    print(f"Reaction records    : {len(reactions)}")
    print(f"Bisoprolol drug rows: {len(target_drugs)}")
    print("\nFiles created:")
    print(f"  {CASES_FILE}")
    print(f"  {REACTIONS_FILE}")
    print(f"  {DRUGS_FILE}")

    return {
        "cases": cases,
        "reactions": reactions,
        "target_drugs": target_drugs,
        "cases_path": CASES_FILE,
        "reactions_path": REACTIONS_FILE,
        "target_drugs_path": DRUGS_FILE,
    }

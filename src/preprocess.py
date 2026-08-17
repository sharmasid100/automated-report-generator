import pandas as pd
import numpy as np
import re
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "data/Bisoprolol_icsr_sample_1068rows.xlsx"
OUTPUT_DIR = Path("processed_data")

# Recommended for a Bisoprolol PADER
FILTER_TO_TARGET_DRUG = True

TARGET_DRUG_PATTERN = r"\bBISOPROLOL(?:\s+FUMARATE)?\b"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(value):
    """Normalize text values."""

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def split_values(value):
    """
    Split comma-separated ICSR values.

    Example:
        'Headache,Dizziness,Nausea'
    becomes:
        ['Headache', 'Dizziness', 'Nausea']
    """

    if pd.isna(value):
        return []

    value = str(value).strip()

    if not value:
        return []

    return [item.strip() for item in value.split(",")]


def get_item(values, index):
    """
    Safely retrieve an item from a list.

    Some ICSR fields may have missing values or
    different list lengths.
    """

    if index < len(values):
        return values[index]

    return None


def contains_bisoprolol(value):
    """Check whether a drug field contains Bisoprolol."""

    if pd.isna(value):
        return False

    return bool(
        re.search(
            TARGET_DRUG_PATTERN,
            str(value).upper()
        )
    )


def parse_date(value):
    """
    Parse ICSR dates safely.

    Handles:
        YYYYMMDD
        YYYY-MM-DD
        datetime
    """

    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()

    if not value:
        return pd.NaT

    # YYYYMMDD
    if re.fullmatch(r"\d{8}", value):
        return pd.to_datetime(
            value,
            format="%Y%m%d",
            errors="coerce"
        )

    return pd.to_datetime(
        value,
        errors="coerce"
    )


def preprocess_data():
    """
    Execute the complete preprocessing pipeline.

    The function:
        1. Loads the ICSR Excel dataset.
        2. Normalizes column names.
        3. Performs basic cleaning.
        4. Validates required columns.
        5. Normalizes case identifiers.
        6. Keeps the latest version of each case.
        7. Identifies and filters Bisoprolol cases.
        8. Creates the case-level dataset.
        9. Normalizes dates, age, and categorical fields.
        10. Creates the reaction-level dataset.
        11. Creates the Bisoprolol drug-level dataset.
        12. Removes duplicates.
        13. Saves processed CSV files.
        14. Prints a validation summary.

    Returns
    -------
    dict
        Dictionary containing the processed DataFrames and
        paths to the generated files.
    """

    print("\n" + "=" * 60)
    print("STARTING PREPROCESSING")
    print("=" * 60)

    # ============================================================
    # 1. LOAD DATA
    # ============================================================

    print("\nLoading dataset...")

    df = pd.read_excel(INPUT_FILE)

    print(f"Raw rows: {len(df)}")
    print(f"Raw columns: {len(df.columns)}")

    # ============================================================
    # 2. NORMALIZE COLUMN NAMES
    # ============================================================

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
    )

    # Prevent unexpected duplicate column names from causing
    # DataFrame/Series ambiguity later in the pipeline.
    if df.columns.duplicated().any():

        duplicated_columns = (
            df.columns[df.columns.duplicated()]
            .tolist()
        )

        raise ValueError(
            "Duplicate column names detected after normalization: "
            f"{duplicated_columns}"
        )

    # ============================================================
    # 3. BASIC CLEANING
    # ============================================================

    # Convert empty strings to NaN
    df = df.replace(
        r"^\s*$",
        np.nan,
        regex=True
    )

    # Strip whitespace from object columns
    object_columns = df.select_dtypes(
        include="object"
    ).columns

    for column in object_columns:

        df[column] = (
            df[column]
            .astype("string")
            .str.strip()
        )

    # ============================================================
    # 4. VALIDATE REQUIRED COLUMNS
    # ============================================================

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

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Required columns are missing:\n"
            + "\n".join(missing_columns)
        )

    # ============================================================
    # 5. NORMALIZE CASE IDENTIFIERS
    # ============================================================

    df["safetyreportid"] = (
        pd.to_numeric(
            df["safetyreportid"],
            errors="coerce"
        )
        .astype("Int64")
    )

    df["safetyreportversion"] = (
        pd.to_numeric(
            df["safetyreportversion"],
            errors="coerce"
        )
        .fillna(0)
    )

    # ============================================================
    # 6. KEEP LATEST VERSION OF EACH CASE
    # ============================================================

    print("\nSelecting latest version of each case...")

    df = df.sort_values(
        [
            "safetyreportid",
            "safetyreportversion"
        ]
    )

    latest_cases = (
        df
        .drop_duplicates(
            subset=["safetyreportid"],
            keep="last"
        )
        .copy()
    )

    print(
        f"Unique cases after version handling: "
        f"{len(latest_cases)}"
    )

    # ============================================================
    # 7. IDENTIFY BISOPROLOL CASES
    # ============================================================

    latest_cases["contains_bisoprolol"] = (
        latest_cases[
            "patient_drug_activesubstance_activesubstancename"
        ]
        .apply(contains_bisoprolol)
    )

    bisoprolol_case_count = (
        latest_cases["contains_bisoprolol"].sum()
    )

    print(
        f"Cases containing Bisoprolol: "
        f"{bisoprolol_case_count}"
    )

    print(
        f"Cases without Bisoprolol: "
        f"{len(latest_cases) - bisoprolol_case_count}"
    )

    # ============================================================
    # 8. FILTER TO TARGET DRUG
    # ============================================================

    if FILTER_TO_TARGET_DRUG:

        latest_cases = latest_cases[
            latest_cases["contains_bisoprolol"]
        ].copy()

        print(
            f"\nFiltering to Bisoprolol cases: "
            f"{len(latest_cases)}"
        )

    # Create a set for fast lookup
    valid_case_ids = set(
        latest_cases["safetyreportid"]
    )

    # ============================================================
    # 9. CREATE CASE-LEVEL DATASET
    # ============================================================

    case_columns = [
        "safetyreportid",
        "safetyreportversion",

        # Location
        "primarysourcecountry",
        "occurcountry",

        # Report information
        "reporttype",
        "report_date",

        # Seriousness
        "serious",
        "seriousnessdeath",
        "seriousnesslifethreatening",
        "seriousnesshospitalization",
        "seriousnessdisabling",
        "seriousnesscongenitalanomali",
        "seriousnessother",

        # Expedite
        "fulfillexpeditecriteria",

        # Demographics
        "patient_patientonsetage",
        "patient_patientonsetageunit",
        "patient_patientsex",
        "patient_patientweight",

        # Reporter
        "primarysource_qualification",

        # Case narrative
        "patient_summary_narrativeincludeclinical",
    ]

    case_columns = [
        column
        for column in case_columns
        if column in latest_cases.columns
    ]

    cases = latest_cases[
        case_columns
    ].copy()

    # ============================================================
    # 10. NORMALIZE CASE DATA
    # ============================================================

    if "report_date" in cases.columns:

        cases["report_date"] = (
            cases["report_date"]
            .apply(parse_date)
        )

    # Age normalization
    if "patient_patientonsetage" in cases.columns:

        cases["age"] = pd.to_numeric(
            cases["patient_patientonsetage"],
            errors="coerce"
        )

    else:

        cases["age"] = np.nan

    if "patient_patientonsetageunit" in cases.columns:

        cases["age_unit"] = (
            cases["patient_patientonsetageunit"]
            .astype("string")
            .str.lower()
            .str.strip()
        )

    else:

        cases["age_unit"] = pd.Series(
            pd.NA,
            index=cases.index,
            dtype="string"
        )

    # Create normalized age in years
    cases["age_years"] = np.nan

    cases.loc[
        cases["age_unit"].eq("year"),
        "age_years"
    ] = cases.loc[
        cases["age_unit"].eq("year"),
        "age"
    ]

    cases.loc[
        cases["age_unit"].eq("month"),
        "age_years"
    ] = cases.loc[
        cases["age_unit"].eq("month"),
        "age"
    ] / 12

    cases.loc[
        cases["age_unit"].eq("day"),
        "age_years"
    ] = cases.loc[
        cases["age_unit"].eq("day"),
        "age"
    ] / 365.25

    # ============================================================
    # 11. DERIVE AGE GROUPS
    # ============================================================

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

    cases["age_group"] = (
        cases["age_years"]
        .apply(derive_age_group)
    )

    # ============================================================
    # 12. NORMALIZE CATEGORICAL VALUES
    # ============================================================

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

            cases[column] = (
                cases[column]
                .astype("string")
                .str.lower()
                .str.strip()
            )

    # ============================================================
    # 13. CREATE REACTION-LEVEL DATASET
    # ============================================================

    reaction_rows = []

    for _, row in latest_cases.iterrows():

        case_id = row["safetyreportid"]

        if case_id not in valid_case_ids:
            continue

        reactions_list = split_values(
            row["patient_reaction_reactionmeddrapt"]
        )

        outcomes = split_values(
            row["patient_reaction_reactionoutcome"]
        )

        meddra_versions = split_values(
            row["patient_reaction_reactionmeddraversionpt"]
        )

        for i, reaction in enumerate(reactions_list):

            if not reaction:
                continue

            reaction_rows.append({

                "safetyreportid":
                    case_id,

                "reaction_pt":
                    reaction,

                "reaction_outcome":
                    get_item(
                        outcomes,
                        i
                    ),

                "meddra_version":
                    get_item(
                        meddra_versions,
                        i
                    ),

                # Case-level seriousness
                "case_serious":
                    row["serious"],

                "case_death":
                    row["seriousnessdeath"],

                "case_life_threatening":
                    row["seriousnesslifethreatening"],

                "case_hospitalization":
                    row["seriousnesshospitalization"],

                "case_disabling":
                    row["seriousnessdisabling"],

                "case_congenital_anomaly":
                    row["seriousnesscongenitalanomali"],

                "case_other_serious":
                    row["seriousnessother"],
            })

    reactions = pd.DataFrame(
        reaction_rows
    )

    # ============================================================
    # 14. CREATE DRUG-LEVEL DATASET
    # ============================================================

    drug_rows = []

    for _, row in latest_cases.iterrows():

        case_id = row["safetyreportid"]

        if case_id not in valid_case_ids:
            continue

        # Split parallel drug fields
        characterizations = split_values(
            row["patient_drug_drugcharacterization"]
        )

        medicinal_products = split_values(
            row["patient_drug_medicinalproduct"]
        )

        active_substances = split_values(
            row[
                "patient_drug_activesubstance_activesubstancename"
            ]
        )

        doses = split_values(
            row["patient_drug_drugdosagetext"]
        )

        dose_numbers = split_values(
            row["patient_drug_drugstructuredosagenumb"]
        )

        dose_units = split_values(
            row["patient_drug_drugstructuredosageunit"]
        )

        routes = split_values(
            row["patient_drug_drugadministrationroute"]
        )

        indications = split_values(
            row["patient_drug_drugindication"]
        )

        actions = split_values(
            row["patient_drug_actiondrug"]
        )

        drug_start_dates = split_values(
            row["patient_drug_drugstartdate"]
        )

        drug_end_dates = split_values(
            row["patient_drug_drugenddate"]
        )

        # Determine number of drug records
        number_of_drugs = max(
            len(characterizations),
            len(medicinal_products),
            len(active_substances)
        )

        for i in range(number_of_drugs):

            active_substance = get_item(
                active_substances,
                i
            )

            # Keep only Bisoprolol drug records
            if not contains_bisoprolol(
                active_substance
            ):
                continue

            drug_rows.append({

                "safetyreportid":
                    case_id,

                "drug_characterization":
                    get_item(
                        characterizations,
                        i
                    ),

                "medicinal_product":
                    get_item(
                        medicinal_products,
                        i
                    ),

                "active_substance":
                    active_substance,

                "dose_text":
                    get_item(
                        doses,
                        i
                    ),

                "dose_number":
                    get_item(
                        dose_numbers,
                        i
                    ),

                "dose_unit":
                    get_item(
                        dose_units,
                        i
                    ),

                "route":
                    get_item(
                        routes,
                        i
                    ),

                "indication":
                    get_item(
                        indications,
                        i
                    ),

                "action_taken":
                    get_item(
                        actions,
                        i
                    ),

                "start_date":
                    get_item(
                        drug_start_dates,
                        i
                    ),

                "end_date":
                    get_item(
                        drug_end_dates,
                        i
                    ),
            })

    target_drugs = pd.DataFrame(
        drug_rows
    )

    # ============================================================
    # 15. CLEAN REACTION DATA
    # ============================================================

    if not reactions.empty:

        reactions["reaction_pt"] = (
            reactions["reaction_pt"]
            .astype("string")
            .str.strip()
        )

        reactions["reaction_outcome"] = (
            reactions["reaction_outcome"]
            .astype("string")
            .str.lower()
            .str.strip()
        )

    # ============================================================
    # 16. CLEAN TARGET DRUG DATA
    # ============================================================

    if not target_drugs.empty:

        target_drugs["active_substance"] = (
            target_drugs["active_substance"]
            .astype("string")
            .str.strip()
            .str.upper()
        )

        target_drugs["drug_characterization"] = (
            target_drugs["drug_characterization"]
            .astype("string")
            .str.lower()
            .str.strip()
        )

        target_drugs["route"] = (
            target_drugs["route"]
            .astype("string")
            .str.lower()
            .str.strip()
        )

        target_drugs["action_taken"] = (
            target_drugs["action_taken"]
            .astype("string")
            .str.lower()
            .str.strip()
        )

    # ============================================================
    # 17. REMOVE EXACT DUPLICATES
    # ============================================================

    cases = cases.drop_duplicates(
        subset=["safetyreportid"]
    )

    reactions = reactions.drop_duplicates()

    target_drugs = target_drugs.drop_duplicates()

    # ============================================================
    # 18. CREATE OUTPUT DIRECTORY
    # ============================================================

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # ============================================================
    # 19. SAVE PROCESSED DATA
    # ============================================================

    cases_path = OUTPUT_DIR / "cases.csv"
    reactions_path = OUTPUT_DIR / "reactions.csv"
    target_drugs_path = OUTPUT_DIR / "target_drugs.csv"

    cases.to_csv(
        cases_path,
        index=False
    )

    reactions.to_csv(
        reactions_path,
        index=False
    )

    target_drugs.to_csv(
        target_drugs_path,
        index=False
    )

    # ============================================================
    # 20. VALIDATION SUMMARY
    # ============================================================

    print("\n" + "=" * 60)
    print("PREPROCESSING COMPLETE")
    print("=" * 60)

    print(
        f"Raw Excel rows       : {len(df)}"
    )

    print(
        f"Unique cases         : "
        f"{df['safetyreportid'].nunique()}"
    )

    print(
        f"Cases retained       : {len(cases)}"
    )

    print(
        f"Reaction records     : {len(reactions)}"
    )

    print(
        f"Bisoprolol drug rows : "
        f"{len(target_drugs)}"
    )

    print("\nMissing values in case dataset:")

    print(
        cases.isna()
        .sum()
        .sort_values(
            ascending=False
        )
        .head(15)
    )

    print("\nFiles created:")

    print(f"  {cases_path}")
    print(f"  {reactions_path}")
    print(f"  {target_drugs_path}")

    # ============================================================
    # RETURN RESULTS
    # ============================================================

    return {
        "cases": cases,
        "reactions": reactions,
        "target_drugs": target_drugs,
        "cases_path": cases_path,
        "reactions_path": reactions_path,
        "target_drugs_path": target_drugs_path,
    }
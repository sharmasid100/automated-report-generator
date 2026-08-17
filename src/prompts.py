"""
prompts.py

Prompt construction module for the PADER-style safety reporting pipeline.

Responsibilities:
    - Build section-specific prompts for Qwen2.5-0.5B-Instruct.
    - Provide strict grounding instructions.
    - Prevent the model from calculating statistics.
    - Prevent unsupported medical/regulatory/causal claims.
    - Keep prompts small and focused on the relevant Evidence JSON.

This module does NOT:
    - Load the dataset.
    - Perform statistical calculations.
    - Load the Hugging Face model.
    - Generate text.
    - Validate the generated report.

Architecture:

    analysis.py
        |
        v
    Evidence JSON
        |
        v
    prompts.py
        |
        v
    llm_pipeline.py
        |
        v
    Qwen2.5-0.5B-Instruct
        |
        v
    Generated Section
"""


import json
from typing import Any, Dict


# ---------------------------------------------------------------------
# Global grounding rules
# ---------------------------------------------------------------------

GROUNDING_RULES = """
Use only the supplied evidence.
Do not invent facts or numbers.
Do not calculate statistics.
Do not infer causality, expectedness, or clinical significance.
Do not make regulatory recommendations.
Use concise, neutral regulatory-style language.
Return only the requested section.
Do not repeat the instructions.
"""


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def _remove_availability(value):
    if isinstance(value, dict):
        return {
            key: _remove_availability(val)
            for key, val in value.items()
            if key != "available"
        }

    if isinstance(value, list):
        return [
            _remove_availability(item)
            for item in value
        ]

    return value


def _serialize_evidence(
    evidence: Dict[str, Any]
) -> str:

    compact_evidence = _remove_availability(
        evidence
    )

    return json.dumps(
        compact_evidence,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str
    )

def _compact_evidence(
    evidence: Dict[str, Any],
    section_name: str
) -> Dict[str, Any]:
    """
    Create a section-specific compact representation
    of the deterministic Evidence JSON.

    Important:
        - No calculations are performed here.
        - No statistics are derived here.
        - Values come directly from evidence.json.
        - The function only removes information that is
          irrelevant to the requested report section.
    """

    # ========================================================
    # NARRATIVE SUMMARY
    # ========================================================

    if section_name == "Narrative Summary":

        case = evidence.get(
            "case_summary",
            {}
        )

        demographics = evidence.get(
            "demographics",
            {}
        )

        reactions = evidence.get(
            "reactions",
            {}
        )

        return {
            "reporting_period": evidence.get("reporting_period"),

            "case_summary": {
                "total_cases": case.get("total_unique_cases"),
                "serious_cases": case.get("serious_cases"),
                "non_serious_cases": case.get("non_serious_cases"),
                "serious_percentage": case.get("serious_percentage"),
                "expedite_cases": case.get("expedite_alert_cases"),
                "expedite_percentage": case.get("expedite_alert_percentage")
            },

            "seriousness": {
                "death": evidence.get("seriousness", {}).get("death"),
                "life_threatening": evidence.get("seriousness", {}).get("life_threatening"),
                "medical_event": {
                    "hospitalization or disability or congenital anomaly":
                      evidence.get("seriousness", {}).get("hospitalization"),
                    "disability": evidence.get("seriousness", {}).get("disability"),
                    "congenital_anomaly": evidence.get("seriousness", {}).get("congenital_anomaly"),
                    "other_serious": evidence.get("seriousness", {}).get("other_serious")
                }
            },

            "demographics": {
                "age": {
                    # "mean": demographics.get("age", {}).get("mean_years"),
                    # "median": demographics.get("age", {}).get("median_years"),
                    "groups": demographics.get("age_group_distribution")
                },
                "sex": demographics.get("sex_distribution")
            },

            "reactions": {
                "total": reactions.get("total_reaction_occurrences"),
                "top": reactions.get("most_frequent_reactions")
            },

            "outcomes": evidence.get("outcomes"),

            "alerts": evidence.get("alerts")
        }
    # ========================================================
    # SUMMARY ANALYSIS
    # ========================================================

    if section_name == "Summary Analysis":

        case = evidence.get("case_summary", {})
        demographics = evidence.get("demographics", {})
        reactions = evidence.get("reactions", {})
        trends = evidence.get("trends", {}).get("case_trends", {})

        return {
    "cases": {
        k: case.get(k)
        for k in (
            "total_unique_cases",
            "serious_cases",
            "non_serious_cases",
            "serious_percentage",
            "expedite_alert_cases",
            "expedite_alert_percentage"
        )
    },

    "seriousness": {
        "death": evidence.get("seriousness", {}).get("death"),
        "life_threatening": evidence.get("seriousness", {}).get("life_threatening"),
        "other_serious": {
            k: evidence.get("seriousness", {}).get(k)
            for k in (
                "hospitalization",
                "disability",
                "congenital_anomaly",
                "other_serious"
            )
        }
    },

    "demographics": {
        "age_groups": demographics.get("age_group_distribution"),
        "sex": demographics.get("sex_distribution")
    },

    "reactions": {
        "total": reactions.get("total_reaction_occurrences"),
        "top": reactions.get("most_frequent_reactions")
    },

    "outcomes": evidence.get("outcomes"),

    "trends": {
        k: trends.get(k)
        for k in (
            "highest_month",
            "lowest_month",
            "first_month",
            "last_month",
            "absolute_change",
            "percentage_change"
        )
    }
}

        # ========================================================
        # REACTION ANALYSIS
        # ========================================================

    if section_name == "Reaction Analysis":

        reactions = evidence.get(
            "reactions",
            {}
        )

        concentrations = reactions.get(
            "reaction_concentrations",
            {}
        )

        # Preserve only the same top five reactions
        # already identified deterministically by Python.
        top_reactions = reactions.get(
            "most_frequent_reactions",
            {}
        )

        top_reaction_names = list(
            top_reactions.keys()
        )[:5]

        compact_concentrations = {
            reaction: concentrations.get(
                reaction
            )
            for reaction in top_reaction_names
            if reaction in concentrations
        }

        return {
            "total_reaction_occurrences":
                reactions.get(
                    "total_reaction_occurrences"
                ),

            "unique_reaction_terms":
                reactions.get(
                    "unique_reaction_terms"
                ),

            "most_frequent_reactions":
                top_reactions,

            "most_frequent_serious_reactions":
                reactions.get(
                    "most_frequent_serious_reactions"
                ),

            "reaction_concentrations":
                compact_concentrations
        }

    # ========================================================
    # SERIOUS / ALERT ANALYSIS
    # ========================================================

    if section_name == "Serious and Alert Case Analysis":

        case = evidence.get(
            "case_summary",
            {}
        )

        return {
            "case_summary": {
                "total_unique_cases":
                    case.get(
                        "total_unique_cases"
                    ),

                "serious_cases":
                    case.get(
                        "serious_cases"
                    ),

                "non_serious_cases":
                    case.get(
                        "non_serious_cases"
                    ),

                "unknown_seriousness":
                    case.get(
                        "unknown_seriousness"
                    ),

                "serious_percentage":
                    case.get(
                        "serious_percentage"
                    ),

                "expedite_alert_cases":
                    case.get(
                        "expedite_alert_cases"
                    ),

                "expedite_alert_percentage":
                    case.get(
                        "expedite_alert_percentage"
                    )
            },

            "seriousness": evidence.get(
                "seriousness"
            ),

            "alerts": evidence.get(
                "alerts"
            ),

            "outcomes": evidence.get(
                "outcomes"
            )
        }

    # ========================================================
    # TREND INTERPRETATION
    # ========================================================

    if section_name == "Trend Interpretation":

        trends = evidence.get(
            "trends",
            {}
        )

        case_trends = trends.get(
            "case_trends",
            {}
        )

        return {
            "reporting_period": {
                "start_date": evidence.get(
                    "reporting_period",
                    {}
                ).get("start_date"),

                "end_date": evidence.get(
                    "reporting_period",
                    {}
                ).get("end_date"),

                "number_of_months": evidence.get(
                    "reporting_period",
                    {}
                ).get("number_of_months")
            },

            "case_trend_summary": {
                "highest_month": case_trends.get(
                    "highest_month"
                ),

                "lowest_month": case_trends.get(
                    "lowest_month"
                ),

                "first_month": case_trends.get(
                    "first_month"
                ),

                "last_month": case_trends.get(
                    "last_month"
                ),

                "absolute_change": case_trends.get(
                    "absolute_change"
                ),

                "percentage_change": case_trends.get(
                    "percentage_change"
                )
            }
        }


    # ========================================================
    # FALLBACK
    # ========================================================

    return evidence


def _build_prompt(
    section_name: str,
    instructions: str,
    evidence: Dict[str, Any]
) -> str:

    compact_evidence = _compact_evidence(
        evidence,
        section_name
    )

    evidence_text = _serialize_evidence(
        compact_evidence
    )

    return f"""
{GROUNDING_RULES}

SECTION:
{section_name}

TASK:
{instructions}

EVIDENCE:
{evidence_text}

Write only the final section text.
""".strip()


# ---------------------------------------------------------------------
# Narrative Summary
# ---------------------------------------------------------------------

def narrative_summary_prompt(evidence: Dict[str, Any]) -> str:
    """
    Build a compact prompt for the narrative safety summary.
    Qwen2.5-0.5B-Instruct should only verbalize validated evidence.
    """

    instructions = """
Write a concise narrative summary using only the supplied evidence.

Only use the information provided in the evidence section passed.
Do not invent or create new evidences or information.
Use the evidence to generate a fully gramatically concise and correct english paragraph.
"""

    return _build_prompt(
        section_name="Narrative Summary",
        instructions=instructions,
        evidence=evidence
    )
# ---------------------------------------------------------------------
# Summary Analysis
# ---------------------------------------------------------------------

def summary_analysis_prompt(evidence: Dict[str, Any]) -> str:
    """
    Prompt for overall summary analysis.
    """

    instructions = """
        Write a concise narrative summary using only the supplied evidence.

        Only use the information provided in the evidence section passed.
        Do not invent or create new evidences or information.
        Use the evidence to generate a fully gramatically concise and correct english paragraph.
    """

    return _build_prompt(
        section_name="Summary Analysis",
        instructions=instructions,
        evidence=evidence
    )


# ---------------------------------------------------------------------
# Reaction Analysis
# ---------------------------------------------------------------------

def reaction_analysis_prompt(evidence: Dict[str, Any]) -> str:
    """
    Prompt for reaction-level analysis.
    """

    instructions = """
        Analyze the supplied reaction evidence and write a concise regulatory-style summary covering:

        - Total reaction occurrences and the most frequently reported reactions.
        - Important changes or patterns in reaction frequency over time.
        - Any notable reaction concentrations identified in the evidence.

        Use only the supplied evidence. 
        Do not calculate, infer causality, or introduce unsupported clinical or safety conclusions.
    """

    return _build_prompt(
        section_name="Reaction Analysis",
        instructions=instructions,
        evidence=evidence
    )


# ---------------------------------------------------------------------
# Serious / Alert Case Analysis
# ---------------------------------------------------------------------

def serious_alert_analysis_prompt(evidence: Dict[str, Any]) -> str:
    """
    Prompt for serious and alert case analysis.
    """

    instructions = """
Describe the supplied serious and alert case evidence in a concise regulatory-style summary covering:

- Total serious, non-serious, and expedite/alert cases.
- Main seriousness categories, including death, life-threatening, and other serious outcomes.
- Important outcomes or reactions identified in the evidence.

Use only the supplied evidence. 
Do not calculate, infer causality or clinical significance, or describe alerts as confirmed safety signals.
"""

    return _build_prompt(
        section_name="Serious and Alert Case Analysis",
        instructions=instructions,
        evidence=evidence
    )


# ---------------------------------------------------------------------
# Trend Interpretation
# ---------------------------------------------------------------------

def trend_interpretation_prompt(evidence: Dict[str, Any]) -> str:
    """
    Prompt for interpretation of deterministic temporal trends.
    """

    instructions = """
Analyze the supplied temporal evidence and write a concise regulatory-style summary covering:

- Reporting period and highest/lowest monthly case counts.
- First and last month case counts.
- Observed absolute and percentage change between the first and last month.

Use only the supplied values. 
Do not calculate, modify dates, reconstruct monthly data, or infer causality, clinical significance, or safety signals.
Return only the trend interpretation.
"""
    return _build_prompt(
        section_name="Trend Interpretation",
        instructions=instructions,
        evidence=evidence
    )


# ---------------------------------------------------------------------
# Generic section prompt
# ---------------------------------------------------------------------

def generic_section_prompt(
    section_name: str,
    evidence: Dict[str, Any],
    instructions: str
) -> str:
    """
    Create a prompt for an additional section without duplicating
    the grounding rules.
    """

    return _build_prompt(
        section_name=section_name,
        instructions=instructions,
        evidence=evidence
    )


# ---------------------------------------------------------------------
# Prompt dispatcher
# ---------------------------------------------------------------------

PROMPT_BUILDERS = {
    "narrative_summary": narrative_summary_prompt,
    "summary_analysis": summary_analysis_prompt,
    "reaction_analysis": reaction_analysis_prompt,
    "serious_alert_analysis": serious_alert_analysis_prompt,
    "trend_interpretation": trend_interpretation_prompt,
}


def get_prompt(
    section: str,
    evidence: Dict[str, Any]
) -> str:
    """
    Return the appropriate prompt for a report section.

    Parameters
    ----------
    section:
        Section identifier.

    evidence:
        Validated Evidence JSON produced by analysis.py.

    Returns
    -------
    str
        Fully constructed prompt.

    Raises
    ------
    ValueError
        If the requested section is not supported.
    """

    section = section.strip().lower()

    if section not in PROMPT_BUILDERS:
        supported = ", ".join(PROMPT_BUILDERS.keys())

        raise ValueError(
            f"Unsupported report section: '{section}'. "
            f"Supported sections: {supported}"
        )

    return PROMPT_BUILDERS[section](evidence)


# ---------------------------------------------------------------------
# Deterministic report section helpers
# ---------------------------------------------------------------------

def methodology_text() -> str:
    """
    Deterministic methodology section.

    This section does not require an LLM because the master design
    recommends template generation for methodology.
    """

    return (
        "The supplied ICSR dataset was validated and processed using "
        "deterministic Python-based analysis. Case-level calculations were "
        "performed using the appropriate safety report identifier, while "
        "reaction-level calculations were performed separately. Missing "
        "values and categorical fields were handled during preprocessing. "
        "The resulting validated evidence was supplied to a lightweight "
        "Hugging Face language model for controlled narrative generation."
    )


def limitations_text(evidence: Dict[str, Any]) -> str:
    """
    Build a deterministic limitations section from the evidence.

    Any limitations explicitly identified by analysis.py are included.
    """

    limitations = evidence.get("limitations", {})

    if not limitations:
        return (
            "The analysis is limited to information available in the "
            "supplied dataset. Information not present in the dataset "
            "was not inferred or supplemented from external sources."
        )

    if isinstance(limitations, dict):
        items = []

        for key, value in limitations.items():
            if value is None:
                continue

            if isinstance(value, list):
                for item in value:
                    items.append(f"{key}: {item}")
            else:
                items.append(f"{key}: {value}")

        if items:
            return (
                "The following limitations were identified from the "
                "supplied dataset:\n\n"
                + "\n".join(f"- {item}" for item in items)
            )

    return (
        "The analysis is limited to information available in the "
        "supplied dataset. Information not present in the dataset "
        "was not inferred or supplemented from external sources."
    )


def review_status_text() -> str:
    """
    Deterministic human-review status required by the master prompt.
    """

    return """Report Status: PENDING HUMAN REVIEW

Review Checklist:

- [ ] Analysis verified
- [ ] Generated sections reviewed
- [ ] Evidence checked
- [ ] Final report approved
"""


# ---------------------------------------------------------------------
# Exported section names
# ---------------------------------------------------------------------

LLM_SECTIONS = [
    "narrative_summary",
    "summary_analysis",
    "reaction_analysis",
    "serious_alert_analysis",
    "trend_interpretation",
]


DETERMINISTIC_SECTIONS = [
    "reporting_period",
    "case_listing",
    "history_of_actions",
    "methodology",
    "limitations",
]
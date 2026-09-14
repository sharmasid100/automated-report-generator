"""Section-specific prompt construction. Does not calculate statistics."""

from __future__ import annotations

import json
from typing import Any, Dict

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


def _remove_availability(value):
    if isinstance(value, dict):
        return {key: _remove_availability(val) for key, val in value.items() if key != "available"}
    if isinstance(value, list):
        return [_remove_availability(item) for item in value]
    return value


def _serialize_evidence(evidence: Dict[str, Any]) -> str:
    compact_evidence = _remove_availability(evidence)
    return json.dumps(
        compact_evidence,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _compact_evidence(evidence: Dict[str, Any], section_name: str) -> Dict[str, Any]:
    if section_name == "Narrative Summary":
        case = evidence.get("case_summary", {})
        demographics = evidence.get("demographics", {})
        reactions = evidence.get("reactions", {})
        return {
            "reporting_period": evidence.get("reporting_period"),
            "case_summary": {
                "total_cases": case.get("total_unique_cases"),
                "serious_cases": case.get("serious_cases"),
                "non_serious_cases": case.get("non_serious_cases"),
                "serious_percentage": case.get("serious_percentage"),
                "expedite_cases": case.get("expedite_alert_cases"),
                "expedite_percentage": case.get("expedite_alert_percentage"),
            },
            "seriousness": {
                "death": evidence.get("seriousness", {}).get("death"),
                "life_threatening": evidence.get("seriousness", {}).get("life_threatening"),
                "medical_event": {
                    "hospitalization": evidence.get("seriousness", {}).get("hospitalization"),
                    "disability": evidence.get("seriousness", {}).get("disability"),
                    "congenital_anomaly": evidence.get("seriousness", {}).get("congenital_anomaly"),
                    "other_serious": evidence.get("seriousness", {}).get("other_serious"),
                },
            },
            "demographics": {
                "age": {"groups": demographics.get("age_group_distribution")},
                "sex": demographics.get("sex_distribution"),
            },
            "reactions": {
                "total": reactions.get("total_reaction_occurrences"),
                "top": reactions.get("most_frequent_reactions"),
            },
            "outcomes": evidence.get("outcomes"),
            "alerts": evidence.get("alerts"),
        }

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
                    "expedite_alert_percentage",
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
                        "other_serious",
                    )
                },
            },
            "demographics": {
                "age_groups": demographics.get("age_group_distribution"),
                "sex": demographics.get("sex_distribution"),
            },
            "reactions": {
                "total": reactions.get("total_reaction_occurrences"),
                "top": reactions.get("most_frequent_reactions"),
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
                    "percentage_change",
                )
            },
        }

    if section_name == "Reaction Analysis":
        reactions = evidence.get("reactions", {})
        concentrations = reactions.get("reaction_concentrations", {})
        top_reactions = reactions.get("most_frequent_reactions", {})
        top_reaction_names = list(top_reactions.keys())[:5]
        compact_concentrations = {
            reaction: concentrations.get(reaction)
            for reaction in top_reaction_names
            if reaction in concentrations
        }
        return {
            "total_reaction_occurrences": reactions.get("total_reaction_occurrences"),
            "unique_reaction_terms": reactions.get("unique_reaction_terms"),
            "most_frequent_reactions": top_reactions,
            "most_frequent_serious_reactions": reactions.get("most_frequent_serious_reactions"),
            "reaction_concentrations": compact_concentrations,
        }

    if section_name == "Serious and Alert Case Analysis":
        case = evidence.get("case_summary", {})
        return {
            "case_summary": {
                "total_unique_cases": case.get("total_unique_cases"),
                "serious_cases": case.get("serious_cases"),
                "non_serious_cases": case.get("non_serious_cases"),
                "unknown_seriousness": case.get("unknown_seriousness"),
                "serious_percentage": case.get("serious_percentage"),
                "expedite_alert_cases": case.get("expedite_alert_cases"),
                "expedite_alert_percentage": case.get("expedite_alert_percentage"),
            },
            "seriousness": evidence.get("seriousness"),
            "alerts": evidence.get("alerts"),
            "outcomes": evidence.get("outcomes"),
        }

    if section_name == "Trend Interpretation":
        trends = evidence.get("trends", {})
        case_trends = trends.get("case_trends", {})
        reporting_period = evidence.get("reporting_period", {})
        return {
            "reporting_period": {
                "start_date": reporting_period.get("start_date"),
                "end_date": reporting_period.get("end_date"),
                "number_of_months": reporting_period.get("number_of_months"),
            },
            "case_trend_summary": {
                "highest_month": case_trends.get("highest_month"),
                "lowest_month": case_trends.get("lowest_month"),
                "first_month": case_trends.get("first_month"),
                "last_month": case_trends.get("last_month"),
                "absolute_change": case_trends.get("absolute_change"),
                "percentage_change": case_trends.get("percentage_change"),
            },
        }

    return evidence


def _build_prompt(section_name: str, instructions: str, evidence: Dict[str, Any]) -> str:
    compact_evidence = _compact_evidence(evidence, section_name)
    evidence_text = _serialize_evidence(compact_evidence)
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


def narrative_summary_prompt(evidence: Dict[str, Any]) -> str:
    instructions = """
Write a concise narrative summary using only the supplied evidence.
Do not invent or create new evidence or information.
Write a grammatically correct, concise English paragraph.
"""
    return _build_prompt("Narrative Summary", instructions, evidence)


def summary_analysis_prompt(evidence: Dict[str, Any]) -> str:
    instructions = """
Write a concise summary analysis using only the supplied evidence.
Cover case counts, seriousness, demographics, reactions, outcomes, and trend values.
Do not calculate or recompute statistics.
"""
    return _build_prompt("Summary Analysis", instructions, evidence)


def reaction_analysis_prompt(evidence: Dict[str, Any]) -> str:
    instructions = """
Analyze the supplied reaction evidence and write a concise regulatory-style summary covering:
- Total reaction occurrences and the most frequently reported reactions.
- Any notable reaction concentrations identified in the evidence.
Use only the supplied evidence. Do not calculate, infer causality, or introduce unsupported conclusions.
"""
    return _build_prompt("Reaction Analysis", instructions, evidence)


def serious_alert_analysis_prompt(evidence: Dict[str, Any]) -> str:
    instructions = """
Describe the supplied serious and alert case evidence in a concise regulatory-style summary covering:
- Total serious, non-serious, and expedite/alert cases.
- Main seriousness categories, including death, life-threatening, and other serious outcomes.
Use only the supplied evidence. Do not describe alerts as confirmed safety signals.
"""
    return _build_prompt("Serious and Alert Case Analysis", instructions, evidence)


def trend_interpretation_prompt(evidence: Dict[str, Any]) -> str:
    instructions = """
Analyze the supplied temporal evidence and write a concise regulatory-style summary covering:
- Reporting period and highest/lowest monthly case counts.
- First and last month case counts.
- Observed absolute and percentage change between the first and last month.
Use only the supplied values. Do not invent dates or reconstruct monthly data.
"""
    return _build_prompt("Trend Interpretation", instructions, evidence)


PROMPT_BUILDERS = {
    "narrative_summary": narrative_summary_prompt,
    "summary_analysis": summary_analysis_prompt,
    "reaction_analysis": reaction_analysis_prompt,
    "serious_alert_analysis": serious_alert_analysis_prompt,
    "trend_interpretation": trend_interpretation_prompt,
}

LLM_SECTIONS = list(PROMPT_BUILDERS.keys())


def get_prompt(section: str, evidence: Dict[str, Any]) -> str:
    section = section.strip().lower()
    if section not in PROMPT_BUILDERS:
        supported = ", ".join(PROMPT_BUILDERS.keys())
        raise ValueError(
            f"Unsupported report section: '{section}'. Supported sections: {supported}"
        )
    return PROMPT_BUILDERS[section](evidence)

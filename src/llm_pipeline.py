"""Controlled language-generation layer. Never calculates safety statistics."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from paths import AUDIT_FILE, EVIDENCE_FILE, MOCK_LLM, MODEL_NAME, OUTPUT_DIR, REPORT_FILE
from prompts import get_prompt

MAX_INPUT_TOKENS = 2048
MAX_NEW_TOKENS = 180


def load_evidence() -> Dict[str, Any]:
    if not EVIDENCE_FILE.exists():
        raise FileNotFoundError(f"Evidence file not found: {EVIDENCE_FILE}")
    with open(EVIDENCE_FILE, encoding="utf-8") as file:
        evidence = json.load(file)
    if not isinstance(evidence, dict):
        raise ValueError("Evidence JSON must contain a JSON object.")
    return evidence


def get_evidence_section(evidence: Dict[str, Any], section_name: str) -> Dict[str, Any]:
    section_map = {
        "narrative_summary": [
            "reporting_period",
            "case_summary",
            "seriousness",
            "demographics",
            "outcomes",
            "limitations",
        ],
        "summary_analysis": [
            "case_summary",
            "seriousness",
            "demographics",
            "outcomes",
            "limitations",
            "trends",
        ],
        "reaction_analysis": ["reactions", "seriousness", "limitations"],
        "serious_alert_analysis": ["case_summary", "seriousness", "alerts", "limitations"],
        "trend_interpretation": ["reporting_period", "trends", "reactions", "limitations"],
    }
    keys = section_map.get(section_name, [])
    return {key: evidence.get(key) for key in keys}


def load_model():
    if MOCK_LLM:
        print("MOCK_LLM is enabled. Skipping Hugging Face model download.")
        return None, None

    from transformers import AutoModelForCausalLM, AutoTokenizer

    print("=" * 60)
    print("Loading Hugging Face model")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print("Device: CPU")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
    model.to("cpu")
    model.eval()
    print("Model loaded successfully.")
    return tokenizer, model


def generate_text(prompt: str, tokenizer, model) -> str:
    if MOCK_LLM or tokenizer is None or model is None:
        return _deterministic_fallback(prompt)

    import torch

    messages = [
        {
            "role": "system",
            "content": (
                "You are a controlled pharmacovigilance reporting assistant. "
                "Use only the supplied evidence. "
                "Return only the requested report section. "
                "Do not repeat the instructions."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    formatted_prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    original_tokens = len(tokenizer(formatted_prompt, add_special_tokens=False)["input_ids"])
    if original_tokens > MAX_INPUT_TOKENS:
        raise ValueError(
            f"Prompt exceeds model input limit: {original_tokens} > {MAX_INPUT_TOKENS}"
        )
    inputs = tokenizer(formatted_prompt, return_tensors="pt", truncation=False)
    inputs = {key: value.to("cpu") for key, value in inputs.items()}
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            num_beams=1,
            no_repeat_ngram_size=3,
            pad_token_id=tokenizer.eos_token_id,
        )
    input_length = inputs["input_ids"].shape[1]
    generated_tokens = outputs[0, input_length:]
    text = tokenizer.decode(generated_tokens, skip_special_tokens=True)
    return text.strip()


def _deterministic_fallback(prompt: str) -> str:
    """Evidence-only prose used when MOCK_LLM=true (CI and local tests)."""
    if "EVIDENCE:" not in prompt:
        return "Evidence was not supplied for this section."
    evidence_text = prompt.split("EVIDENCE:", 1)[1].split("Write only the final section text.", 1)[
        0
    ]
    try:
        evidence = json.loads(evidence_text.strip())
    except json.JSONDecodeError:
        return "Evidence could not be parsed for this section."
    return json.dumps(evidence, ensure_ascii=False)


def extract_numbers(text: str) -> List[str]:
    if not text:
        return []
    pattern = r"(?<![A-Za-z])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?"
    return re.findall(pattern, text)


def normalize_number(number: str) -> str:
    number = number.replace(",", "").replace("%", "").strip()
    try:
        value = float(number)
        if value.is_integer():
            return str(int(value))
        return str(value)
    except ValueError:
        return number


def extract_evidence_numbers(evidence: Any) -> set:
    numbers = set()

    def recursive_extract(value):
        if isinstance(value, dict):
            for item in value.values():
                recursive_extract(item)
        elif isinstance(value, list):
            for item in value:
                recursive_extract(item)
        elif isinstance(value, bool):
            return
        elif isinstance(value, (int, float)):
            numbers.add(normalize_number(str(value)))
        elif isinstance(value, str):
            for number in extract_numbers(value):
                numbers.add(normalize_number(number))

    recursive_extract(evidence)
    return numbers


def validate_numbers(generated_text: str, evidence: Dict[str, Any]) -> Tuple[bool, List[str]]:
    generated_numbers = extract_numbers(generated_text)
    evidence_numbers = extract_evidence_numbers(evidence)
    unsupported = []
    for number in generated_numbers:
        normalized = normalize_number(number)
        if normalized not in evidence_numbers:
            unsupported.append(number)
    return len(unsupported) == 0, unsupported


def detect_unsupported_claims(text: str) -> List[str]:
    if not text:
        return ["Generated text is empty."]
    text_lower = text.lower()
    flagged_phrases = [
        "caused by",
        "causes",
        "caused",
        "proves that",
        "confirmed safety signal",
        "confirmed signal",
        "causal relationship",
        "causally related",
        "definitively related",
        "regulatory action",
        "should be withdrawn",
        "should be discontinued",
        "should be contraindicated",
        "clinically significant safety signal",
    ]
    findings = []
    for phrase in flagged_phrases:
        if phrase in text_lower:
            findings.append(f"Potentially unsupported claim: '{phrase}'")
    return findings


def validate_section(generated_text: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    number_valid, unsupported_numbers = validate_numbers(generated_text, evidence)
    unsupported_claims = detect_unsupported_claims(generated_text)
    valid = number_valid and len(unsupported_claims) == 0 and bool(generated_text.strip())
    return {
        "valid": valid,
        "unsupported_numbers": unsupported_numbers,
        "unsupported_claims": unsupported_claims,
        "human_review_required": not valid,
    }


def generate_section(
    section_name: str, evidence: Dict[str, Any], tokenizer, model
) -> Dict[str, Any]:
    print(f"\nGenerating section: {section_name}")
    section_evidence = get_evidence_section(evidence, section_name)
    prompt = get_prompt(section_name, section_evidence)
    generated_text = generate_text(prompt, tokenizer, model).strip()
    validation = validate_section(generated_text, section_evidence)
    if validation["human_review_required"]:
        print(f"WARNING: {section_name} requires human review.")
    else:
        print(f"{section_name}: validation passed.")
    return {
        "section": section_name,
        "evidence": section_evidence,
        "prompt": prompt,
        "text": generated_text,
        "validation": validation,
        "mock_llm": MOCK_LLM,
        "model": MODEL_NAME if not MOCK_LLM else "deterministic-fallback",
    }


def generate_ai_sections(evidence: Dict[str, Any], tokenizer, model) -> Dict[str, Dict[str, Any]]:
    sections = [
        "narrative_summary",
        "summary_analysis",
        "reaction_analysis",
        "serious_alert_analysis",
        "trend_interpretation",
    ]
    generated = {}
    for section in sections:
        generated[section] = generate_section(section, evidence, tokenizer, model)
    return generated


def format_reporting_period(evidence: Dict[str, Any]) -> str:
    data = evidence.get("reporting_period", {})
    if not data.get("available") and not data.get("start_date"):
        return "Reporting period information was not available in the supplied dataset."
    start = data.get("start_date")
    end = data.get("end_date")
    months = data.get("number_of_months")
    return (
        f"The available reporting period extends from {start} to {end}, covering {months} month(s)."
    )


def format_case_summary(evidence: Dict[str, Any]) -> str:
    data = evidence["case_summary"]
    total = data["total_unique_cases"]
    serious = data["serious_cases"]
    non_serious = data["non_serious_cases"]
    expedite = data["expedite_alert_cases"]
    return (
        f"A total of {total:,} unique cases were identified. Of these, "
        f"{serious:,} were classified as serious and {non_serious:,} as non-serious. "
        f"{expedite:,} cases met the supplied expedite/alert criterion."
    )


def format_methodology() -> str:
    return (
        "The analysis was performed using a deterministic Python pipeline. "
        "The supplied ICSR dataset was validated and cleaned before case-level and "
        "reaction-level analyses were performed.\n\n"
        "Case-level statistics were calculated using unique safety report identifiers, "
        "while reaction occurrences were analyzed separately. Missing information was "
        "retained as unavailable/unknown where appropriate.\n\n"
        "The resulting validated statistics were stored in an Evidence JSON structure. "
        f"A language model ({MODEL_NAME} unless MOCK_LLM is enabled) was subsequently "
        "used only to convert selected validated findings into concise narrative text.\n\n"
        "Generated content was subjected to numerical and claim-level grounding checks "
        "and sections failing validation were flagged for human review."
    )


def format_limitations(evidence: Dict[str, Any]) -> str:
    limitations = evidence.get("limitations", [])
    if not limitations:
        return "No additional limitations were identified by the deterministic analysis pipeline."
    if isinstance(limitations, dict):
        items = []
        for key, value in limitations.items():
            if value is None:
                continue
            if isinstance(value, list):
                items.extend(f"{key}: {item}" for item in value)
            else:
                items.append(f"{key}: {value}")
        if not items:
            return "The analysis is limited to information available in the supplied dataset."
        return (
            "The following limitations were identified from the supplied dataset:\n\n"
            + "\n".join(f"- {item}" for item in items)
        )
    return "\n".join(f"- {item}" for item in limitations)


def format_review_status(generated_sections: Dict[str, Any]) -> str:
    sections_requiring_review = [
        name
        for name, result in generated_sections.items()
        if result["validation"]["human_review_required"]
    ]
    if sections_requiring_review:
        listed = "\n".join(f"- {section}" for section in sections_requiring_review)
        return (
            "**Report Status: PENDING HUMAN REVIEW**\n\n"
            "The following generated sections require human review:\n\n"
            f"{listed}"
        )
    return (
        "**Report Status: PENDING HUMAN REVIEW**\n\n"
        "Automated grounding validation passed for the generated sections. "
        "Human review is still required before final approval."
    )


def assemble_report(evidence: Dict[str, Any], generated_sections: Dict[str, Any]) -> str:
    return f"""# PADER-Style Safety Report

## 1. Reporting Period

{format_reporting_period(evidence)}

---

## 2. Narrative Summary

{generated_sections["narrative_summary"]["text"]}

---

## 3. Case Summary

{format_case_summary(evidence)}

---

## 4. Summary Analysis

{generated_sections["summary_analysis"]["text"]}

---

## 5. Reaction Analysis

{generated_sections["reaction_analysis"]["text"]}

---

## 6. Serious and Alert Case Analysis

{generated_sections["serious_alert_analysis"]["text"]}

---

## 7. Trend Interpretation

{generated_sections["trend_interpretation"]["text"]}

---

## 8. Methodology

{format_methodology()}

---

## 9. Limitations

{format_limitations(evidence)}

---

## 10. Human Review

{format_review_status(generated_sections)}

### Review Checklist

- [ ] Analysis verified
- [ ] Generated sections reviewed
- [ ] Evidence checked
- [ ] Final report approved

---

## 11. Evidence Traceability

The report was generated from deterministic analysis results stored in `output/evidence.json`.

The language model was not provided with the raw ICSR Excel dataset.

Numerical and categorical analysis was performed before language generation.

Unsupported generated content is flagged for human review.
""".strip()


def save_report(report: str) -> None:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as file:
        file.write(report)
    print(f"\nReport saved to: {REPORT_FILE}")


def save_generation_audit(generated_sections: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_FILE, "w", encoding="utf-8") as file:
        json.dump(generated_sections, file, indent=2, ensure_ascii=False)
    print(f"Generation audit saved to: {AUDIT_FILE}")


def generate_report() -> str:
    print("\n")
    print("=" * 60)
    print("LLM REPORT GENERATION PIPELINE")
    print("=" * 60)
    evidence = load_evidence()
    tokenizer, model = load_model()
    generated_sections = generate_ai_sections(evidence, tokenizer, model)
    report = assemble_report(evidence, generated_sections)
    save_report(report)
    save_generation_audit(generated_sections)
    return report


if __name__ == "__main__":
    generate_report()

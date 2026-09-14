# PADER-Style Safety Reporting — Prompt Contract

The language model is a controlled narrative component only.

> Deterministic Python calculates and owns the facts. The language model verbalizes those facts. Validation determines whether generated text may be accepted.

## Model

`Qwen/Qwen2.5-0.5B-Instruct`, unless `MOCK_LLM=true`.

Generation uses `do_sample=False`, `num_beams=1`, bounded `max_new_tokens`, and a no-repeat n-gram constraint.

System message:

> You are a controlled pharmacovigilance reporting assistant. Use only the supplied evidence. Return only the requested report section. Do not repeat the instructions.

## Global rules

- Use only supplied Evidence JSON.
- Do not calculate statistics or invent dates.
- Do not infer causality, expectedness, clinical significance, or a confirmed safety signal.
- Do not recommend regulatory action unless that exact information is in the evidence.
- Return only the requested section.

Executable prompts live in `src/prompts.py`. Update this file when those prompts change.

## LLM sections

1. Narrative Summary
2. Summary Analysis
3. Reaction Analysis
4. Serious and Alert Case Analysis
5. Trend Interpretation

## Deterministic sections

Reporting period, case summary, methodology, limitations, human review, and evidence traceability stay in Python.

## Validation

Numbers in generated text must appear in the section evidence. High-risk phrases such as "caused by", "confirmed safety signal", and "should be withdrawn" are flagged. A pass is not proof of field-level semantic correctness. Human review remains required.

# PADER-Style Safety Reporting Pipeline

## GenAR AI Engineering Challenge

A CPU-friendly, evidence-grounded pipeline for generating a PADER-style pharmacovigilance safety report from an ICSR dataset.

The system deliberately separates **deterministic safety analysis** from **LLM-based narrative generation**:

> **Python calculates the facts. The LLM verbalizes those facts. Validation controls whether generated text can be accepted.**

This design is intended to reduce hallucination risk and make every generated narrative traceable to deterministic evidence.

---

## 1. Overview

The pipeline takes an ICSR Excel dataset through the following stages:


ICSR Excel Dataset
       |
       v
Preprocessing
       |
       v
Deterministic Safety Analysis
       |
       v
Validated Evidence JSON
       |
       +-----------------------------+
       |                             |
       v                             v
Deterministic Report Sections   Section-specific Evidence
                                     |
                                     v
                              Prompt Construction
                                     |
                                     v
                                    LLM
                                     |
                                     v
                              Generated Narrative
                                     |
                                     v
                               Claim Validation
                                     |
                              +------+------+
                              |             |
                            PASS           FAIL
                              |             |
                              v             v
                          Accepted     Review / Fallback
                              |             |
                              +------+------+
                                     |
                                     v
                              Report Assembly
                                     |
                                     v
                           PADER-Style Markdown
                                     |
                                     v
                             Human Final Review


The LLM is not used to calculate case counts, reaction frequencies, seriousness classifications, percentages, or trends.

---

## 2. Design Goals

The implementation is designed around five goals:

1. **Deterministic factual analysis**
   - Python/Pandas performs the calculations.
   - The resulting Evidence JSON is treated as the source of truth.

2. **Controlled LLM generation**
   - The model receives only the evidence relevant to the requested section.
   - Section-specific prompts constrain the generated narrative.

3. **Grounding**
   - Generated text is checked against the evidence after generation.
   - Unsupported numerical and high-risk claims are flagged.

4. **Auditability**
   - Evidence and generation/validation metadata are written to output files.
   - The pipeline records which sections require human review.

5. **Human oversight**
   - This is a PADER-style reporting prototype, not an autonomous regulatory reporting system.
   - Final output remains subject to human review.

---

## 3. AI vs. Deterministic Responsibilities

### Deterministic Python

Python is responsible for:

- ICSR preprocessing.
- Data cleaning and normalization.
- Case identification.
- Unique case counting.
- Seriousness analysis.
- Demographic analysis.
- Reaction analysis.
- Outcome analysis.
- Alert/expedite analysis.
- Temporal trend calculations.
- Evidence JSON construction.
- Deterministic report sections.
- Validation decisions.
- Human-review status.
- Final report assembly.

### LLM

The LLM is responsible only for:

- Converting supplied evidence into readable prose.
- Organizing supplied observations.
- Producing concise regulatory-style language.
- Generating the five controlled narrative sections.

### The LLM does not own

- Numerical truth.
- Statistical calculations.
- Case classification.
- Trend calculations.
- Causal inference.
- Regulatory decisions.
- Safety-signal confirmation.

This separation is the central safety boundary of the system.

---

## 4. Model

The current implementation uses:


Qwen/Qwen2.5-0.5B-Instruct


The model is loaded through Hugging Face Transformers and is intended to run on CPU.

Generation is configured for deterministic behavior:


do_sample=False
num_beams=1
no_repeat_ngram_size=3


The exact runtime parameters are controlled by `src/llm_pipeline.py`.

---

## 5. Project Structure

ssidharth_sharma_genar_challenge/
|
├── README.md
├── architecture.md
├── requirements.txt
├── setup_venv.bat
|
├── prompts/ report_prompts.md
|
├── src/
│   ├── main.py
│   ├── preprocess.py
│   ├── analysis.py
│   ├── prompts.py
│   └── llm_pipeline.py
|
└── output/
    ├── evidence.json
    ├── generation_audit.json
    └── pader_report.md


---

## 6. Module Responsibilities

### `src/main.py`

The orchestration layer.

It:

1. Creates required directories.
2. Runs preprocessing.
3. Runs deterministic analysis.
4. Calls the LLM report-generation pipeline.
5. Verifies that the expected output files were created.

It does not perform the actual data analysis or prompt construction.

---

### `src/preprocess.py`

Responsible for preparing the ICSR data.

Typical responsibilities include:

- Reading the supplied Excel workbook.
- Parsing dates.
- Cleaning missing values.
- Normalizing relevant fields.
- Producing cleaned intermediate data for analysis.

The preprocessing stage does not generate narrative conclusions.

---

### `src/analysis.py`

Responsible for deterministic pharmacovigilance analysis.

It produces the Evidence JSON used downstream by the report generator.

The analysis layer is the authoritative source for calculated facts.

---

### `src/prompts.py`

Responsible for:

- Selecting evidence relevant to each report section.
- Compacting the Evidence JSON.
- Constructing section-specific prompts.
- Preventing unnecessary raw data from being passed to the LLM.

`src/prompts.py` is the **executable prompt source of truth**.

---

### `src/llm_pipeline.py`

Responsible for:

- Loading the evidence.
- Loading the model/tokenizer.
- Building section-specific prompts.
- Generating narrative text.
- Validating generated sections.
- Recording validation results.
- Building the final report.

---

## 7. Evidence Layer

The deterministic analysis produces:


output/evidence.json


The Evidence JSON contains structured information such as:

- Reporting period.
- Case summary.
- Demographics.
- Reactions.
- Seriousness.
- Outcomes.
- Alerts/expedites.
- Temporal trends.
- Other deterministic analysis outputs.

The LLM should never be given the raw ICSR dataset simply to "figure out" the report.

Instead:


Raw data
   |
   v
Deterministic analysis
   |
   v
Evidence JSON
   |
   v
Section-specific evidence
   |
   v
LLM


This reduces both context size and the model's opportunity to introduce unsupported information.

---

## 8. Prompt Design

The system uses section-specific prompts rather than one unrestricted report-generation prompt.

The current LLM-assisted sections are:

1. Narrative Summary
2. Summary Analysis
3. Reaction Analysis
4. Serious and Alert Case Analysis
5. Trend Interpretation

Each prompt instructs the model to:

- Use only supplied evidence.
- Avoid unsupported information.
- Preserve supplied numerical values.
- Avoid new calculations.
- Avoid causal claims.
- Avoid unsupported regulatory conclusions.
- Return only the requested section.

The complete prompt specification is documented in:


prompts/ report_prompts.md


---

## 9. Grounding Strategy

The system uses a post-generation validation layer.

At minimum, validation checks:

### Numerical grounding

Numbers appearing in the generated text are compared with numerical values contained in the relevant evidence.

### High-risk claim detection

Potentially unsupported phrases related to:

- Causality.
- Confirmed safety signals.
- Regulatory actions.
- Unsupported clinical conclusions.

are flagged.

### Important limitation

A numerical membership check does not prove that a number is associated with the correct evidence field.

For example, if evidence contains both `1015` and `1016`, a sentence using both numbers could still associate them with the wrong concepts.

Therefore, validation is a **risk-control layer**, not a mathematical proof of correctness.

Human review remains required.

---

## 10. Validation and Human Review

The intended flow is:


Generated section
       |
       v
Validation
       |
  +----+----+
  |         |
 PASS      FAIL
  |         |
  v         v
Accept    Reject / Fallback
             |
             v
      Human review required


A failed section should not be silently treated as authoritative.

The generation audit records validation status and whether human review is required.

The final report should clearly communicate review status.

---

## 11. Deterministic Report Sections

Sections that do not require generative language should remain deterministic.

These include:

- Reporting Period.
- Case Listing.
- History of Actions.
- Methodology.
- Limitations.
- Human Review / Review Status.
- Evidence Traceability.

If safety or regulatory action information is absent, the system should explicitly state that the information was not supplied rather than infer an action.

---

## 12. Output Files

### `output/evidence.json`

Structured deterministic evidence used as the factual basis for the report.

### `output/generation_audit.json`

Records generation and validation information for the AI-assisted sections.

Useful audit fields include:

- Section name.
- Model.
- Section evidence.
- Generated text.
- Validation results.
- Human-review status.

### `output/pader_report.md`

The assembled PADER-style Markdown report.

The report is a **draft requiring human review**, not a claim that the generated output is ready for regulatory submission without review.

---

## 13. Setup

### Requirements

Recommended environment:


Python 3.10+
CPU-compatible PyTorch
Internet access for the initial Hugging Face model download


Install dependencies:


pip install -r requirements.txt


The repository includes:


setup_venv.bat


for Windows environment setup.

---

## 14. Input Data

The pipeline expects the supplied ICSR Excel dataset to be available under:


data/


The exact dataset is intentionally not included in the final submission ZIP because the challenge submission guide states that the dataset is already provided to the evaluator.

For local execution, place the supplied dataset in the expected `data/` location.


---

## 15. Running the Pipeline

From the project root:


python src/main.py


This is the primary command for regenerating the report.

The pipeline executes:


[1/4] Preprocessing and validating the ICSR dataset
[2/4] Running deterministic safety analysis
[3/4] Generating PADER-style report
[4/4] Verifying generated output


The main output files are written to:


output/


Specifically:


output/evidence.json
output/generation_audit.json
output/pader_report.md


The first model execution may require downloading the Hugging Face model.

---

## 16. Reproducibility

The main reproducibility controls are:

- Pinned dependency ranges in `requirements.txt`.
- Explicit model identifier.
- Deterministic generation (`do_sample=False`).
- Fixed generation configuration in `llm_pipeline.py`.
- Deterministic evidence generation.
- Section-specific prompts.
- Saved evidence and generation audit artifacts.

---

## 17. Evaluation Strategy

A single successful report is not enough to establish reliability.

The intended scale evaluation is to run the pipeline over a larger set of reports or held-out report contexts, for example 1,000 generated reports.

Recommended metrics:

### Deterministic correctness

- Case-count accuracy.
- Seriousness-count accuracy.
- Reaction-count accuracy.
- Outcome-count accuracy.
- Trend-calculation accuracy.

### Grounding

- Unsupported numerical claims / total numerical claims.
- Unsupported entity claims / total entity claims.
- Unsupported sentences / total generated sentences.
- Validation pass rate.

### Reliability

- Human-review rate.
- Validation failure rate.
- Fallback rate.
- Empty-generation rate.

### Human evaluation

Reviewers can score:

1. Factual correctness.
2. Evidence traceability.
3. Regulatory tone.
4. Completeness.
5. Conciseness.
6. Unsupported inference.

The goal is not merely fluent text; it is **factually grounded and reviewable regulatory-style text**.

---

## 18. Known Limitations

This is a prototype and has several limitations.

### Grounding limitations

The current numerical validation checks whether generated numbers occur in the evidence, but does not fully establish field-level semantic correctness.

### Claim detection limitations

Phrase-based high-risk claim detection cannot identify every possible hallucination or unsupported inference.

### Small-model limitations

A small CPU-friendly model may produce:

- Repetitive wording.
- Incomplete sentences.
- Poor grammar.
- Incorrect associations between evidence fields.

### Missing-data limitations

Missing evidence must not be interpreted as evidence that an event did not occur.

### Human review

The final report requires human verification.

### Regulatory scope

This implementation is a PADER-style reporting prototype. It is not intended to autonomously make regulatory decisions or establish causality.

---

## 19. Design Decisions

### Why deterministic analysis?

Pharmacovigilance reports contain safety-critical facts where numerical or categorical errors can materially change interpretation.

Therefore, calculations are performed outside the LLM.

### Why use an LLM?

The LLM is useful for converting structured evidence into readable, concise narrative while keeping deterministic analysis separate.

### Why section-specific prompts?

Different report sections require different evidence.

Section-specific evidence reduces:

- Prompt size.
- Irrelevant context.
- Hallucination opportunities.
- Unnecessary model reasoning.

### Why validate after generation?

Even a strongly constrained model can produce fluent but unsupported claims.

Post-generation validation creates an additional safety boundary.

### Why retain human review?

Automated checks cannot guarantee complete semantic correctness. Human review is therefore retained as the final control.

---

## 20. Example Safety Boundary

The intended behavior is:


Python:
"total_unique_cases": 1016

        |
        v

LLM:
"There were 1,016 unique cases during the reporting period."

        |
        v

Validator:
Number supported?
Association plausible?
High-risk claim detected?

        |
        v

Accept / Review


The LLM should **not** do this:


Raw dataset
     |
     v
LLM decides:
"there were approximately 1,000 cases"


The first architecture is deterministic and auditable.

The second makes the language model responsible for factual extraction and calculation.

---


## 21. Final Principle

The system is intentionally designed so that:


                DETERMINISTIC LAYER
                       |
                       v
                Validated Evidence
                       |
                       v
                 GENERATIVE LAYER
                       |
                       v
                Generated Narrative
                       |
                       v
                 VALIDATION LAYER
                       |
                +------+------+
                |             |
               PASS          FAIL
                |             |
                v             v
             Accept      Review/Fallback
                |             |
                +------+------+
                       |
                       v
                Human Review


The core principle is:

> **Facts are calculated deterministically; language is generated probabilistically; validation and human review control acceptance.**

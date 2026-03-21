# SmartBots — Bank Reconciliation AI Agent

## Implementation Plan & Progress Tracker

> **Stack:** Python · FastAPI · LangGraph · GPT-4o · ChromaDB (local)  
> **Deployment target:** Local dev  
> **Transaction volume:** < 10,000 / day  
> **Last updated:** March 21, 2026

---

## Progress Overview

| Phase | Description                    | Status  |
| ----- | ------------------------------ | ------- |
| 1     | Project Scaffolding            | ✅ Done |
| 2     | Data Ingestion Layer           | ✅ Done |
| 3     | Deterministic Matching Engine  | ✅ Done |
| 4     | RAG Layer (ChromaDB)           | ✅ Done |
| 5     | LangGraph Agent / LLM Layer    | ✅ Done |
| 6     | Validation & Guardrails        | ✅ Done |
| 7     | Workflow Engine (FastAPI)      | ✅ Done |
| 8     | Output Layer                   | ✅ Done |
| 9     | Testing                        | ✅ Done |
| 10    | Metrics & Accuracy Measurement | ✅ Done |

> Legend: ⬜ Not started · 🔄 In progress · ✅ Done

---

## Architecture Overview

```
Data Sources (BAI2 · CSV · Excel · Core banking APIs)
          │
          ▼
  Data Ingestion Layer
  (Format normalisation · Schema mapping · Validation & enrichment)
          │
          ▼
  Deterministic Matching Engine
  (Exact match · Rule-based · Tolerance-based · Ledger vs bank alignment)
          │
          ▼
   ┌──────────────┐    context    ┌─────────────────┐
   │  LLM Layer   │◄─────────────►│   RAG Layer      │
   │  Exception   │               │  Policies/SOPs   │
   │  classification│              │  Prior recons    │
   │  Explanation │               │  Audit logs      │
   │  Soft match  │               │  Bank rules      │
   │  Edge-case   │               └─────────────────┘
   └──────────────┘
          │
          ▼
  Validation & Guardrails
  (Schema enforcement · No hallucinated numbers · Confidence scoring · Human fallback)
          │
          ▼
  Workflow Engine
  (Exception queues · AI-assisted recommendations · Human-in-the-loop approvals)
          │
          ▼
  Outputs & Enterprise Systems
  (Reconciliation reports · Daily close status · Audit docs · ERP/GL/Compliance)
```

---

## Phase 1 — Project Scaffolding

### Checklist

- [x] Create root directory `bank-reconciliation-agent/`
- [x] Create full source tree (`src/`, `tests/`, `data/`, `config/`)
- [x] Add `requirements.txt` (pinned versions)
- [x] Add `pyproject.toml` with project metadata
- [x] Create `.env.example` (template for `OPENAI_API_KEY`, `CHROMA_PATH`)
- [x] Create `config/thresholds.yaml` — tolerance values
- [x] Create `config/bank_rules.yaml` — bank-specific matching rules
- [x] Create root `README.md` with quick-start instructions

### Directory Structure

```
bank-reconciliation-agent/
├── src/
│   ├── ingestion/
│   │   ├── parsers/
│   │   └── validators/
│   ├── matching_engine/
│   │   ├── algorithms/
│   │   └── rules/
│   ├── graph/
│   │   ├── nodes/
│   │   ├── state.py
│   │   ├── routes.py
│   │   └── graph_builder.py
│   ├── llm/
│   │   ├── prompts/
│   │   ├── embeddings.py
│   │   └── tools.py
│   ├── rag/
│   │   ├── collection_manager.py
│   │   ├── retriever.py
│   │   └── ingest.py
│   ├── validation/
│   │   ├── hallucination_guard.py
│   │   └── audit_trail.py
│   ├── workflow/
│   │   └── api.py
│   ├── output/
│   │   └── report_generator.py
│   └── utils/
│       ├── metrics.py
│       ├── logging.py
│       └── config.py
├── tests/
│   ├── fixtures/
│   │   ├── generate_fixtures.py
│   │   └── golden_answers.json
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── data/
│   ├── test_samples/
│   └── reference/
├── config/
│   ├── thresholds.yaml
│   └── bank_rules.yaml
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Phase 2 — Data Ingestion Layer

### Checklist

- [ ] Define unified `Transaction` Pydantic schema (`src/ingestion/schema.py`)
  - Fields: `id, date, posting_date, amount, description, reference, source_type, raw_metadata`
- [ ] Implement `bai2_parser.py` (wraps `bai2` library)
- [ ] Implement `csv_parser.py` (pandas + configurable column mapping)
- [ ] Implement `excel_parser.py` (openpyxl multi-sheet support)
- [ ] Implement `api_parser.py` (stub for core banking JSON responses)
- [ ] Implement `validator.py`
  - [ ] Null field checks
  - [ ] Amount sign validation
  - [ ] Date sanity check (no future dates beyond T+5)
  - [ ] Duplicate detection by ID
- [ ] Implement `enricher.py`
  - [ ] Normalize dates to UTC
  - [ ] Standardize amount sign conventions (credits positive, debits negative)
  - [ ] Tag `source_type` field
- [ ] Unit tests for all parsers

---

## Phase 3 — Deterministic Matching Engine

### Checklist

- [ ] Implement `exact_matcher.py`
  - [ ] Match on: `amount == amount AND date == date AND reference == reference`
- [ ] Implement `rule_matcher.py`
  - [ ] Load rules from `config/bank_rules.yaml`
  - [ ] Configurable rule chain with priority ordering
- [ ] Implement `tolerance_matcher.py`
  - [ ] Amount tolerance: ± configurable threshold (default $0.01)
  - [ ] Date tolerance: ± configurable days (default ±2 days)
  - [ ] Description fuzzy score via `rapidfuzz`
  - [ ] Composite score: amount 40% + date 30% + description 30%
- [ ] Implement `ledger_bank_aligner.py`
  - [ ] Run matchers in priority order: exact → rule → tolerance
  - [ ] Emit `matched_pairs[]`, `unmatched_ledger[]`, `unmatched_bank[]`
- [ ] Define `MatchResult` model: `{ledger_id, bank_id, confidence: float, method: Literal["exact","rule","tolerance","soft","llm"]}`
- [ ] Unit tests for each matcher including boundary conditions

---

## Phase 4 — RAG Layer (ChromaDB)

### Checklist

- [ ] Install and configure ChromaDB (local persistent client)
- [ ] Implement `collection_manager.py`
  - [ ] `policies_sops` collection (metadata: `bank, type, effective_date, version`)
  - [ ] `prior_reconciliations` collection (metadata: `outcome, exception_type, bank, date_range`)
  - [ ] `exception_catalog` collection (metadata: `exception_id, category, frequency, resolution`)
  - [ ] `bank_rules` collection (metadata: `bank_name, rule_type, priority`)
  - [ ] `audit_logs` collection (metadata: `transaction_id, match_confidence, validated`)
- [ ] Implement `embeddings.py` (OpenAI `text-embedding-3-small` wrapper)
- [ ] Implement `retriever.py`
  - [ ] Cosine similarity query
  - [ ] Metadata filter support
  - [ ] Returns top-N results with scores
- [ ] Implement `ingest.py` (seed `data/reference/` documents into collections)
- [ ] Create seed documents in `data/reference/`
  - [ ] At least 3 SOP markdown files
  - [ ] At least 20 historical reconciliation case JSONs
  - [ ] Exception type catalog JSON
- [ ] Integration test: retrieval returns relevant docs for known exception types

---

## Phase 5 — LangGraph Agent / LLM Layer

### Checklist

- [ ] Define `ReconciliationState` TypedDict (`src/graph/state.py`)
  - [ ] `ledger_transactions`, `bank_transactions`
  - [ ] `unmatched_ledger`, `unmatched_bank`
  - [ ] `matches`, `exceptions`, `soft_match_candidates`
  - [ ] `explanations`, `validation_results`
  - [ ] `confidence_scores`, `human_review_queue`
  - [ ] `audit_log`, `final_report`
- [ ] Implement `exception_classifier.py` node
  - [ ] GPT-4o few-shot classification
  - [ ] Categories: `timing_diff | rounding | duplicate | missing | unknown`
  - [ ] Output confidence score per classification
- [ ] Implement `soft_matcher.py` node
  - [ ] RAG context retrieval + rapidfuzz scoring
  - [ ] Proposes soft matches with confidence
- [ ] Implement `explainer.py` node
  - [ ] GPT-4o generates human-readable explanation per exception
  - [ ] Injects top-3 RAG-retrieved similar cases as context
- [ ] Implement `edge_case_reasoner.py` node
  - [ ] Chain-of-thought prompting for reversals
  - [ ] Partial payment detection
  - [ ] Currency mismatch handling
- [ ] Implement `validator_node.py` node
  - [ ] Enforce Pydantic schemas on all LLM outputs
  - [ ] Flag schema violations → route to human fallback
- [ ] Implement `routes.py` (conditional edges)
  - [ ] After ingestion → deterministic engine
  - [ ] If `unmatched > 0` → exception classifier
  - [ ] After classification → parallel: soft_match + rag_retrieval
  - [ ] If `confidence < threshold` → human_review_queue
  - [ ] After validation → output
- [ ] Implement `graph_builder.py` — assemble and compile StateGraph
- [ ] Write system prompts in `src/llm/prompts/`
  - [ ] `exception_classification.txt`
  - [ ] `explanation_generation.txt`
  - [ ] `edge_case_reasoning.txt`
- [ ] Integration test: full LangGraph run on smoke fixture

---

## Phase 6 — Validation & Guardrails

### Checklist

- [ ] Implement `hallucination_guard.py`
  - [ ] Verify every amount in LLM output exists in source data
  - [ ] Verify every transaction ID in LLM output exists in source data
  - [ ] Any invented value → route to human fallback (never auto-approve)
- [ ] Implement confidence scorer (`src/validation/confidence_scorer.py`)
  - [ ] Normalize all scores to `[0.0, 1.0]`
  - [ ] Below `thresholds.yaml:human_fallback_confidence` → add to review queue
- [ ] Implement `audit_trail.py`
  - [ ] Append-only audit log of all decisions
  - [ ] Record: match method, confidence, timestamp, LLM explanation reference
- [ ] Unit tests
  - [ ] Guard rejects invented amounts
  - [ ] Guard rejects invalid transaction IDs
  - [ ] Confidence threshold triggers fallback correctly

---

## Phase 7 — Workflow Engine (FastAPI)

### Checklist

- [ ] Set up FastAPI app (`src/workflow/api.py`)
- [ ] Implement `POST /reconcile`
  - [ ] Accept file upload (BAI2 / CSV / Excel) + `bank_name` form field
  - [ ] Detect file format automatically
  - [ ] Trigger full LangGraph run as background task
  - [ ] Return `{run_id}` immediately
- [ ] Implement `GET /reconcile/{run_id}/status`
  - [ ] States: `queued | running | completed | failed`
- [ ] Implement `GET /reconcile/{run_id}/report`
  - [ ] Return full reconciliation report JSON
- [ ] Implement `GET /exceptions/queue`
  - [ ] List all pending human review items with details
- [ ] Implement `POST /exceptions/{id}/approve`
- [ ] Implement `POST /exceptions/{id}/reject`
- [ ] Implement `POST /exceptions/{id}/manual-match` (human provides correct match)
- [ ] Add request validation (file size limit, supported formats)
- [ ] Integration tests for all API endpoints

---

## Phase 8 — Output Layer

### Checklist

- [ ] Implement `report_generator.py`
  - [ ] Report schema: `{run_id, generated_at, bank, matched_count, unmatched_count, match_rate_pct, total_matched_amount, unreconciled_amount, exception_summary[], audit_trail[]}`
- [ ] Implement CSV export of unmatched items (ERP-ready format)
- [ ] Implement JSON export of full report
- [ ] Implement plain-text audit document (immutable, no overwrites)
- [ ] Unit tests for report generation with sample data

---

## Phase 9 — Testing

### 9a. Test Fixtures

- [ ] Implement `tests/fixtures/generate_fixtures.py`
- [ ] Generate **Smoke dataset** (100 txns/side)
  - [ ] 40 exact matches
  - [ ] 10 timing differences (1–3 day delay)
  - [ ] 5 rounding mismatches ($0.01–$0.99)
  - [ ] 5 duplicates (on ledger side)
  - [ ] 5 missing from bank (not yet posted)
  - [ ] 5 reversals / credit memos
  - [ ] 30 edge cases (mixed anomalies)
- [ ] Generate **Integration dataset** (5,000 txns/side, same ratios)
- [ ] Generate **Adversarial dataset**
  - [ ] Malformed BAI2 inputs
  - [ ] Missing required fields
  - [ ] Hallucination-trigger inputs (amounts not in source data)
  - [ ] Extreme values ($0.001, $999,999,999)
- [ ] Create `tests/fixtures/golden_answers.json` — ground-truth labels for all fixtures

### 9b. Unit Tests

- [ ] Parser: each format returns valid `Transaction` list
- [ ] Exact matcher: correct match on perfect data
- [ ] Tolerance matcher: boundary — amount at exactly ±threshold (should match vs. should not)
- [ ] Hallucination guard: rejects invented amount not in source
- [ ] Confidence scorer: returns value in `[0,1]`; triggers fallback below threshold

### 9c. Integration Tests

- [ ] Full LangGraph run on smoke fixture → output matches `golden_answers.json`
- [ ] RAG retrieval returns relevant docs for each known exception type
- [ ] FastAPI `POST /reconcile` → `GET /reconcile/{id}/report` full round-trip
- [ ] Human approval flow: exception → approve → report updated

### 9d. E2E / Production Simulation Tests

- [ ] Full pipeline on 5k integration fixture; all metrics meet targets
- [ ] Low-confidence exception → assert it enters review queue, is NOT auto-resolved
- [ ] Adversarial input → pipeline fails gracefully, no hallucinated data in output
- [ ] Concurrent reconciliation runs (2 simultaneous) — no state bleed

---

## Phase 10 — Accuracy & Recall Measurement

### Metric Targets

| Metric                   | Formula                   | **Target** | CI Gate           |
| ------------------------ | ------------------------- | ---------- | ----------------- |
| **Precision**            | TP / (TP + FP)            | **≥ 95%**  | ✅ Fail if < 95%  |
| **Recall**               | TP / (TP + FN)            | **≥ 98%**  | ✅ Fail if < 98%  |
| **F1 Score**             | 2·P·R / (P+R)             | **≥ 0.96** | ✅ Fail if < 0.96 |
| False Positive Rate      | FP / (FP + TN)            | ≤ 2%       | —                 |
| Exception Detection Rate | Found / Total exceptions  | ≥ 95%      | —                 |
| Human Fallback Rate      | Manual / Total txns       | ≤ 5%       | —                 |
| Amount Variance %        | \|Δ\| / Ledger total      | ≤ 0.001%   | —                 |
| **MCC**                  | (TP·TN − FP·FN) / √...    | **≥ 0.90** | —                 |
| Explanation ROUGE-L      | vs reference explanations | ≥ 0.60     | —                 |
| RAG MRR (top-3)          | Mean reciprocal rank      | ≥ 0.70     | —                 |
| Confidence ECE           | Calibration error         | ≤ 0.05     | —                 |

### Checklist

- [ ] Implement `src/utils/metrics.py`
  - [ ] `evaluate_run(predicted, ground_truth) → MetricsReport`
  - [ ] Precision, Recall, F1 computation
  - [ ] MCC computation
  - [ ] False positive rate
  - [ ] Exception detection rate
  - [ ] Human fallback rate
  - [ ] Amount variance %
  - [ ] ROUGE-L for explanation quality
  - [ ] MRR for RAG retrieval quality
  - [ ] ECE for confidence calibration
- [ ] Implement `src/utils/metrics_runner.py`
  - [ ] Runs metrics against smoke + integration fixtures automatically
  - [ ] Outputs `metrics.jsonl` log per run
  - [ ] Prints pass/fail per CI gate threshold
- [ ] Wire metrics runner into pytest via `conftest.py` post-run hook
- [ ] Verify all CI gate metrics pass on smoke fixture before moving to production test

---

## Scope Boundaries

### Included ✅

- Full 7-layer pipeline (ingest → match → LLM → validate → workflow → output)
- Local ChromaDB (no cloud infra needed)
- FastAPI human-in-the-loop approval endpoints
- Labeled golden test fixtures
- Automated metrics runner with CI gate

### Excluded ❌

- Cloud deployment (AWS / Azure / GCP)
- Real bank API credentials / live connections
- Authentication & authorization (AuthN/AuthZ)
- UI dashboard / frontend
- Multi-tenancy
- Real-time streaming / webhooks
- Multi-currency FX conversion engine

---

## Key Decisions Log

| Decision       | Choice           | Reason                                                             |
| -------------- | ---------------- | ------------------------------------------------------------------ |
| Orchestration  | LangGraph        | Native stateful graph; best for multi-node conditional flows       |
| LLM            | GPT-4o           | Best reasoning for financial edge cases; structured output support |
| Vector DB      | ChromaDB (local) | No cloud infra needed; fast local cosine search                    |
| Parser (BAI2)  | `bai2` library   | Production-grade; handles SWIFT-style statements                   |
| Fuzzy match    | `rapidfuzz`      | 10–50× faster than `fuzzywuzzy`; MIT license                       |
| Validation     | Pydantic v2      | Strict mode; schema enforcement on all LLM outputs                 |
| Human fallback | Always explicit  | Never silently auto-approve; safety-first for financial data       |

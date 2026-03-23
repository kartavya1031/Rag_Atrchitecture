# SmartBots — Bank Reconciliation AI Agent

## Complete Architecture & Documentation Guide

> **An AI-powered bank reconciliation engine that automates the matching of ledger transactions against bank statements using a multi-layer pipeline combining deterministic algorithms, LLM reasoning, and Retrieval-Augmented Generation (RAG).**

---

## Table of Contents

1. [Project Vision & Problem Statement](#1-project-vision--problem-statement)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Technology Stack & Rationale](#3-technology-stack--rationale)
4. [Data Flow Pipeline](#4-data-flow-pipeline)
5. [Folder & File Reference](#5-folder--file-reference)
6. [Module Deep-Dives](#6-module-deep-dives)
7. [Configuration System](#7-configuration-system)
8. [Testing Strategy](#8-testing-strategy)
9. [API Reference](#9-api-reference)
10. [Frontend Pages](#10-frontend-pages)
11. [Quality Gates & Metrics](#11-quality-gates--metrics)
12. [Setup & Running](#12-setup--running)
13. [Sharing This Project — LinkedIn & Presentation Guide](#13-sharing-this-project--linkedin--presentation-guide)

---

## 1. Project Vision & Problem Statement

### The Problem

Bank reconciliation is one of the most tedious, error-prone, and time-consuming processes in corporate finance. Every day, accountants manually compare thousands of transactions between internal ledger systems and external bank statements, hunting for discrepancies caused by timing differences, rounding, duplicates, reversals, and missing entries.

- **Manual reconciliation** of 10,000 transactions/day takes 4–8 hours
- **Error rates** in manual processes range from 2–5%
- **Exceptions** (unmatched items) require deep domain knowledge and historical context
- Audit trails are often incomplete or inconsistent

### The Solution

SmartBots Bank Reconciliation Agent is an **AI-powered, multi-layer reconciliation engine** that:

1. **Ingests** bank statements and ledger exports in multiple formats (BAI2, CSV, Excel)
2. **Matches** transactions using a 3-tier deterministic engine (exact → rule-based → fuzzy tolerance)
3. **Classifies exceptions** using GPT-4o with RAG-retrieved policy context
4. **Explains** every decision in audit-ready language
5. **Routes** low-confidence items to human reviewers with AI recommendations
6. **Produces** reconciliation reports, audit documents, and ERP-ready exports

### Key Differentiators

| Feature              | Traditional Tools    | SmartBots Agent                           |
| -------------------- | -------------------- | ----------------------------------------- |
| Matching             | Static rules only    | 3-tier deterministic + LLM reasoning      |
| Exception handling   | Manual investigation | AI classification with 7 categories       |
| Context awareness    | None                 | RAG over SOPs, historical cases, policies |
| Explanations         | None                 | GPT-4o generated, audit-ready             |
| Hallucination safety | N/A                  | Amount/ID verification guard              |
| Audit trail          | Manual logs          | Automatic JSONL append-only trail         |

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STREAMLIT FRONTEND                              │
│  Dashboard │ Documents │ Reconciliation │ Exceptions │ KB Search        │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTP REST
┌──────────────────────────────▼──────────────────────────────────────────┐
│                         FASTAPI BACKEND                                 │
│  /reconcile  /exceptions  /knowledge-base                               │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────┐    ┌────────────────┐    ┌──────────────────┐
│  INGESTION   │    │   MATCHING     │    │  KNOWLEDGE BASE  │
│  Layer       │    │   ENGINE       │    │  (ChromaDB RAG)  │
│              │    │                │    │                  │
│ CSV Parser   │    │ Exact Matcher  │    │ 6 Collections:   │
│ Excel Parser │    │ Rule Matcher   │    │ • policies_sops  │
│ BAI2 Parser  │    │ Tolerance      │    │ • prior_recons   │
│ API Parser   │    │   Matcher      │    │ • exception_cat  │
│ Validator    │    │                │    │ • bank_rules     │
│ Enricher     │    │ Aligner        │    │ • audit_logs     │
└──────┬───────┘    │ (orchestrator) │    │ • knowledge_base │
       │            └───────┬────────┘    └────────┬─────────┘
       │                    │                      │
       └────────────────────┼──────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH STATE MACHINE                           │
│                                                                       │
│  deterministic_match ──→ exception_classifier ──→ soft_matcher        │
│                          (GPT-4o + RAG)          + edge_case_reasoner │
│                                                         │             │
│                                                         ▼             │
│                                               explainer (GPT-4o)      │
│                                                         │             │
│                                                         ▼             │
│                                               validator_node          │
│                                               (schema + confidence)   │
│                                                         │             │
│                                                         ▼             │
│                                               output_node             │
│                                               (reports + audit)       │
└───────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     VALIDATION & GUARDRAILS                           │
│  Hallucination Guard │ Confidence Scorer │ Audit Trail (JSONL)        │
└───────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│                          OUTPUT                                       │
│  JSON Report │ CSV Export (ERP-ready) │ Audit Text Document           │
└───────────────────────────────────────────────────────────────────────┘
```

### Architecture Principles

1. **Deterministic First** — Cheap, fast, provably correct matching runs before any LLM call
2. **LLM as Fallback** — GPT-4o is only invoked for genuinely ambiguous exceptions
3. **RAG-Grounded** — Every LLM decision is grounded in retrieved policy documents and historical cases
4. **Hallucination-Safe** — Every LLM output is validated against source amounts and IDs
5. **Human-in-the-Loop** — Low-confidence decisions are routed to humans with AI recommendations
6. **Auditable** — Append-only JSONL audit trail records every decision

---

## 3. Technology Stack & Rationale

### Core Language & Runtime

| Technology      | Version | Why We Chose It                                                                                                                         |
| --------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Python 3.12** | 3.12.7  | Industry standard for AI/ML, rich ecosystem for data processing, async support for FastAPI, type hints for Pydantic                     |
| **Pydantic v2** | 2.11.1  | Schema validation at system boundaries — ensures every transaction and match result is structurally correct. V2 is 5–50x faster than v1 |

### AI & LLM

| Technology                 | Version | Why We Chose It                                                                                                                                                           |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OpenAI GPT-4o**          | via API | Best-in-class reasoning for exception classification, handles financial domain nuances, JSON mode for structured output                                                   |
| **text-embedding-3-small** | via API | Cost-efficient embeddings (62,500 pages/$1) with strong semantic similarity for financial text                                                                            |
| **LangGraph**              | 0.3.21  | Explicit state machine for multi-step agent workflows — deterministic routing, conditional edges, no hidden control flow. Better than raw LangChain for complex pipelines |
| **LangChain-core**         | 0.3.49  | Minimal dependency — only used for core abstractions that LangGraph builds on, not the bloated LangChain ecosystem                                                        |

### Vector Store & RAG

| Technology                     | Version | Why We Chose It                                                                                                                                           |
| ------------------------------ | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ChromaDB**                   | 1.0.21  | Local-first vector store — no external server required, persistent SQLite storage, cosine similarity search. Perfect for local dev and small-medium scale |
| **Why not Pinecone/Weaviate?** | —       | This is a local-first project. ChromaDB runs embedded, no cloud dependency, no API costs for vector storage                                               |

### Web Framework

| Technology    | Version  | Why We Chose It                                                                                                                 |
| ------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **FastAPI**   | 0.115.11 | Async-first REST API with automatic OpenAPI docs, Pydantic integration, dependency injection. Industry standard for Python APIs |
| **Uvicorn**   | 0.34.0   | ASGI server that powers FastAPI with high-performance async I/O                                                                 |
| **Streamlit** | 1.55.0   | Rapid prototyping of data-centric dashboards with zero frontend code. Perfect for internal tools and demos                      |

### Data Processing

| Technology         | Version | Why We Chose It                                                                                    |
| ------------------ | ------- | -------------------------------------------------------------------------------------------------- |
| **Pandas**         | 2.2.3   | De facto standard for tabular data manipulation — CSV parsing, column mapping, data transformation |
| **openpyxl**       | 3.1.5   | Native Python Excel (.xlsx) reader — no external dependencies, handles multi-sheet workbooks       |
| **PyMuPDF (fitz)** | 1.27.2  | Fastest Python PDF text extractor — 10x faster than pdfplumber, handles complex layouts            |
| **python-docx**    | 1.2.0   | Word document text extraction for knowledge base ingestion                                         |

### Matching & NLP

| Technology       | Version | Why We Chose It                                                                                                                             |
| ---------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **RapidFuzz**    | 3.12.1  | C++-accelerated fuzzy string matching — `token_set_ratio` handles reordered words in transaction descriptions. 10x faster than `fuzzywuzzy` |
| **scikit-learn** | 1.6.1   | Used for Expected Calibration Error (ECE) computation in metrics                                                                            |

### Logging & Observability

| Technology        | Version | Why We Chose It                                                                                  |
| ----------------- | ------- | ------------------------------------------------------------------------------------------------ |
| **structlog**     | 25.1.0  | Structured JSON logging — machine-parseable, correlatable by run_id, compatible with ELK/Datadog |
| **python-dotenv** | 1.1.0   | Loads `.env` files for local configuration without touching system environment                   |

### Testing & Quality

| Technology         | Version | Why We Chose It                                                              |
| ------------------ | ------- | ---------------------------------------------------------------------------- |
| **pytest**         | 8.3.5   | Standard Python test framework with fixtures, parametrize, and async support |
| **pytest-asyncio** | 0.26.0  | Async test support for FastAPI endpoint tests                                |
| **rouge-score**    | 0.1.2   | ROUGE-L metric for evaluating LLM explanation quality                        |
| **httpx**          | 0.28.1  | Async HTTP client for TestClient and API testing                             |

---

## 4. Data Flow Pipeline

### End-to-End Transaction Flow

```
Step 1: FILE UPLOAD
    User uploads bank_statement.csv + ledger.csv via Streamlit or API
    ↓
Step 2: PARSING
    csv_parser.py detects columns, maps to canonical Transaction schema
    Each row → Transaction(id, date, amount, description, reference, source_type)
    ↓
Step 3: VALIDATION
    validator.py checks: null fields? zero amounts? future dates (>T+5)? duplicate IDs?
    Output: valid Transaction[] + rejected Transaction[] + error messages
    ↓
Step 4: ENRICHMENT
    enricher.py strips bank-specific prefixes using bank_rules.yaml
    "INCOMING TRANSFER - Payroll" → "Payroll"
    ↓
Step 5: DETERMINISTIC MATCHING (3-tier pipeline)
    Layer 1 — Exact Matcher: amount + date + reference must all match exactly
             → Confidence: 1.00
    Layer 2 — Rule Matcher: amount exact + date within bank timing offset + reference
             → Confidence: 0.95
    Layer 3 — Tolerance Matcher: composite score =
               0.4 × amount_similarity + 0.3 × date_similarity + 0.3 × description_fuzz
             → Confidence: 0.70 – 0.85
    ↓
Step 6: EXCEPTION CLASSIFICATION (only for remaining unmatched)
    GPT-4o classifies each unmatched item with RAG context:
    → timing_diff | rounding | duplicate | missing | reversal | partial_payment | unknown
    ↓
Step 7: SOFT MATCHING + EDGE CASE REASONING
    Soft matcher: rapidfuzz composite scoring on remaining items
    Edge case reasoner: GPT-4o chain-of-thought for reversals, splits, partial payments
    ↓
Step 8: EXPLANATION GENERATION
    GPT-4o writes audit-ready explanations for each exception (≤300 tokens)
    Grounded in RAG-retrieved similar historical cases
    ↓
Step 9: VALIDATION & GUARDRAILS
    Hallucination guard: verifies all amounts/IDs in LLM outputs exist in source data
    Confidence scorer: normalizes scores, routes < 0.70 to human review queue
    ↓
Step 10: OUTPUT
    JSON report + CSV unmatched export + plain-text audit document
    All decisions logged to JSONL audit trail
```

### Matching Priority & Confidence Levels

| Layer | Method                    | Confidence | Speed                 | When It Fires                                                 |
| ----- | ------------------------- | ---------- | --------------------- | ------------------------------------------------------------- |
| 1     | Exact Match               | 1.00       | O(n) with hash index  | Amount + Date + Reference all identical                       |
| 2     | Rule Match                | 0.95       | O(n × m)              | Amount exact + Date within bank offset + Reference compatible |
| 3     | Tolerance Match           | 0.70–0.85  | O(n × m) with scoring | Composite weighted score above threshold                      |
| 4     | Soft Match (LLM-assisted) | 0.50–0.70  | LLM call              | Fuzzy + GPT-4o reasoning for edge cases                       |

---

## 5. Folder & File Reference

### Root Directory

```
bank-reconciliation-agent/
├── pyproject.toml              # Build config, package metadata, pytest settings
├── requirements.txt            # Pinned dependencies (30+ packages)
├── README.md                   # Quick-start guide
├── instructions.md             # This file — comprehensive documentation
├── .env.example                # Environment variable template
├── .env                        # Actual env vars (gitignored)
│
├── config/                     # YAML configuration files
├── data/                       # ChromaDB store, reference data, test samples
├── frontend/                   # Streamlit dashboard
├── src/                        # Core application source code
├── tests/                      # Unit, integration, E2E tests
└── smartbots_bank_reconciliation.egg-info/  # Editable install metadata
```

### Config Directory

| File                     | Purpose                                                                                                                                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config/thresholds.yaml` | Matching tolerances (amount: ±$0.01, date: ±2 days, fuzzy: 75/100), composite weights (amount 40%, date 30%, description 30%), confidence ceilings per method, RAG settings (top_k=5, min_relevance=0.60) |
| `config/bank_rules.yaml` | Bank-specific rules — Chase (1-day timing offset), BankOfAmerica (0-day offset), Generic (2-day offset). Description prefix stripping patterns per bank                                                   |

### Data Directory

| Path                                             | Purpose                                                                                 |
| ------------------------------------------------ | --------------------------------------------------------------------------------------- |
| `data/chroma_db/`                                | ChromaDB persistent storage (SQLite + binary segments)                                  |
| `data/reference/exception_catalog.json`          | 7 exception types with IDs, categories, frequencies, and recommended resolutions        |
| `data/reference/historical_cases.json`           | 20 detailed historical reconciliation cases spanning Chase & BofA — used as RAG context |
| `data/reference/sop_001_daily_reconciliation.md` | SOP: Daily reconciliation procedure with timing requirements and approval authority     |
| `data/reference/sop_002_timing_differences.md`   | SOP: Timing difference handling with bank-specific offsets                              |
| `data/reference/sop_003_duplicate_handling.md`   | SOP: Duplicate transaction identification, resolution, and prevention                   |
| `data/test_samples/bank_statement.csv`           | Test bank statement (15 transactions)                                                   |
| `data/test_samples/ledger.csv`                   | Test ledger export (15 transactions)                                                    |

---

## 6. Module Deep-Dives

### 6.1 Ingestion Module (`src/ingestion/`)

**Purpose:** Normalize heterogeneous financial data formats into a single canonical `Transaction` model.

| File                      | What It Does                                                                                                                                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `schema.py`               | Defines the `Transaction` Pydantic model — the universal data contract. Fields: `id`, `date`, `posting_date`, `amount` (Decimal, signed), `description`, `reference`, `source_type` (enum: bai2/csv/excel/api), `raw_metadata` (dict for extra fields) |
| `parsers/csv_parser.py`   | Reads CSV files via pandas with configurable column mapping. Handles missing dates, auto-generates IDs (`CSV-{idx}`) when absent                                                                                                                       |
| `parsers/excel_parser.py` | Reads .xlsx files via openpyxl with case-insensitive header matching and multi-sheet support. Handles both date objects and ISO strings                                                                                                                |
| `parsers/bai2_parser.py`  | Parses BAI2 bank statement format (industry standard). Converts cents to dollars, infers credit/debit from type codes (1xx–3xx = credit, 4xx–5xx = debit)                                                                                              |
| `parsers/api_parser.py`   | Stub for core banking JSON API responses. Converts list-of-dicts to Transaction objects, passes extra fields to `raw_metadata`                                                                                                                         |
| `validators/validator.py` | Data quality checks: null field detection, zero amount rejection, future date sanity (>T+5 rejected), duplicate ID detection. Returns `ValidationResult` with `valid`, `rejected`, `errors` lists                                                      |
| `enricher.py`             | Strips bank-specific description prefixes using `bank_rules.yaml` config. Example: "INCOMING TRANSFER - Payroll" → "Payroll" for Chase                                                                                                                 |
| `__init__.py`             | Module exports                                                                                                                                                                                                                                         |

**Data Contract:**

```python
class Transaction(BaseModel):
    id: str
    date: date
    posting_date: date | None = None
    amount: Decimal
    description: str
    reference: str | None = None
    source_type: SourceType  # bai2, csv, excel, api
    raw_metadata: dict = {}
```

---

### 6.2 Matching Engine (`src/matching_engine/`)

**Purpose:** Deterministic 3-tier matching pipeline that handles 80–95% of transactions without any LLM calls.

| File                              | What It Does                                                                                                                                                                 |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `models.py`                       | `MatchResult` Pydantic model: `ledger_id`, `bank_id`, `confidence` (0.0–1.0), `method` (exact/rule/tolerance/soft/llm), `details` (dict)                                     |
| `algorithms/exact_matcher.py`     | O(n) exact matching via hash index on `(amount, date, reference)` tuple. Confidence: 1.00. Fastest, most reliable layer                                                      |
| `algorithms/rule_matcher.py`      | Bank-aware matching — accounts for per-bank timing offsets from `bank_rules.yaml`. Chase transactions get 1-day leeway. Confidence: 0.95                                     |
| `algorithms/tolerance_matcher.py` | Composite fuzzy scoring: `0.4 × amount_score + 0.3 × date_score + 0.3 × description_fuzz`. Uses RapidFuzz `token_set_ratio` for descriptions. Minimum confidence from config |
| `ledger_bank_aligner.py`          | Orchestrator — runs exact → rule → tolerance in sequence. Each layer passes remaining unmatched to the next. Returns `{matched_pairs, unmatched_ledger, unmatched_bank}`     |

**Why 3 Tiers?**

- **Exact** catches identical transactions (typical: 60–70% of volume)
- **Rule** catches bank-specific timing/formatting differences (typical: 15–25%)
- **Tolerance** catches minor discrepancies (typical: 5–10%)
- **Remaining 2–5%** go to LLM for intelligent classification

---

### 6.3 Graph Module (`src/graph/`) — LangGraph Orchestration

**Purpose:** Orchestrates the full reconciliation pipeline as an explicit state machine with conditional routing.

| File                            | What It Does                                                                                                                                                                                                                                 |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `state.py`                      | `ReconciliationState` TypedDict — the shared state flowing through the graph. Contains: transactions, matches, unmatched items, exceptions, explanations, validation results, confidence scores, human review queue, audit log, final report |
| `routes.py`                     | Conditional edge logic: if unmatched transactions exist → route to `exception_classifier`, else skip directly to `output`                                                                                                                    |
| `graph_builder.py`              | Assembles and compiles the LangGraph `StateGraph`. Defines the full flow: `deterministic_match` → `exception_classifier` → `soft_match_and_reason` → `explainer` → `validator` → `output` → END                                              |
| `nodes/exception_classifier.py` | GPT-4o few-shot classification of unmatched transactions into 7 categories: timing_diff, rounding, duplicate, missing, reversal, partial_payment, unknown. Uses RAG context from `prior_reconciliations` collection                          |
| `nodes/soft_matcher.py`         | Fuzzy soft matching using composite scoring (amount + date + description fuzz via RapidFuzz). No LLM calls — purely algorithmic                                                                                                              |
| `nodes/edge_case_reasoner.py`   | Chain-of-thought GPT-4o reasoning for complex edge cases (reversals, partial payments, split transactions). Retrieves policy context from `policies_sops` collection                                                                         |
| `nodes/explainer.py`            | GPT-4o generates human-readable, audit-ready explanations per exception (≤300 tokens). Retrieves top-3 similar historical cases via RAG for grounding                                                                                        |
| `nodes/validator_node.py`       | Validates all LLM-proposed matches against Pydantic schemas. Routes low-confidence exceptions (< 0.70) to `human_review_queue`                                                                                                               |

**Graph Flow:**

```
START
  ↓
deterministic_match_node
  ↓
[conditional: unmatched exist?]
  ├── YES → exception_classifier → soft_match_and_reason → explainer → validator → output → END
  └── NO  → output → END
```

**Why LangGraph (not raw LangChain)?**

- **Explicit state machine** — every transition is visible and testable
- **Conditional routing** — skip expensive LLM calls when not needed
- **TypedDict state** — full type safety throughout the pipeline
- **No hidden chains** — easier to debug than deeply nested LangChain pipelines

---

### 6.4 LLM Module (`src/llm/`)

**Purpose:** Embeddings wrapper and prompt templates for all LLM interactions.

| File                                   | What It Does                                                                                                                                                   |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `embeddings.py`                        | OpenAI embeddings wrapper — `get_embeddings(texts)` for batch, `get_single_embedding(text)` for single. Uses `text-embedding-3-small` model                    |
| `prompts/exception_classification.txt` | Prompt template for GPT-4o exception classification. Injects `{rag_context}` and `{transaction}` placeholders. Asks for JSON output with category + confidence |
| `prompts/explanation_generation.txt`   | Prompt template for audit-ready explanations. Cites similar cases, under 200 words                                                                             |
| `prompts/edge_case_reasoning.txt`      | Chain-of-thought prompt for complex edge cases. Returns JSON with `proposed_matches` and `unresolvable`                                                        |

---

### 6.5 RAG Module (`src/rag/`)

**Purpose:** ChromaDB-based vector store for grounding LLM decisions in real policy documents and historical cases.

| File                    | What It Does                                                                                                                                                                                                                                                      |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `collection_manager.py` | ChromaDB collection CRUD. Manages 6 collections: `policies_sops`, `prior_reconciliations`, `exception_catalog`, `bank_rules`, `audit_logs`, `knowledge_base`. `get_chroma_client()` creates PersistentClient with local SQLite storage                            |
| `retriever.py`          | Generic retrieval function — queries any ChromaDB collection with cosine similarity, supports metadata filters, converts L2 distances to similarity scores (1/(1+distance)), filters below `min_relevance_score`                                                  |
| `ingest.py`             | Seeds reference data into ChromaDB — ingests 3 SOPs, 20 historical cases, 7 exception catalog entries, 3 bank rules. `ingest_all()` is the bootstrap function                                                                                                     |
| `document_loader.py`    | Universal document loader with format-specific extractors: PDF (PyMuPDF), Word (python-docx), Excel (openpyxl), text files. Includes `chunk_text()` with paragraph/sentence-aware splitting (1000 chars, 200 overlap) and `file_content_hash()` for deduplication |
| `knowledge_base.py`     | Full CRUD for the general-purpose `knowledge_base` collection — `ingest_document()`, `list_documents()`, `delete_document()`, `query_knowledge_base()`. Deduplicates by content hash                                                                              |

**6 RAG Collections Explained:**

| Collection              | Content                                          | Used By                                          |
| ----------------------- | ------------------------------------------------ | ------------------------------------------------ |
| `policies_sops`         | 3 Standard Operating Procedures                  | Edge case reasoner — retrieves relevant policies |
| `prior_reconciliations` | 20 historical cases with resolutions             | Exception classifier — finds similar past cases  |
| `exception_catalog`     | 7 exception type definitions                     | Reference for classification categories          |
| `bank_rules`            | 3 bank configurations                            | Rule matcher context                             |
| `audit_logs`            | Reconciliation decision history                  | Compliance queries                               |
| `knowledge_base`        | User-uploaded documents (PDF, Word, Excel, text) | Knowledge Base Search page                       |

---

### 6.6 Validation Module (`src/validation/`)

**Purpose:** Ensure LLM outputs are trustworthy and every decision is traceable.

| File                     | What It Does                                                                                                                                                                                                                                      |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hallucination_guard.py` | **Critical safety layer.** Recursively walks all LLM JSON outputs and verifies that every amount and transaction ID mentioned actually exists in the source data. Accepts negated amounts (debit ↔ credit). Returns `(is_clean, violations_list)` |
| `confidence_scorer.py`   | Normalizes confidence scores to [0, 1] range. `needs_human_review(confidence)` returns `True` if below 0.70 threshold (configurable via env)                                                                                                      |
| `audit_trail.py`         | Append-only JSONL audit log. `record()` writes entries with timestamp, run_id, transaction_id, match_method, confidence, and decision. `read_all()` reads back. Immutable once written                                                            |

**Why Hallucination Guard Matters:**

- LLMs can "invent" plausible-looking transaction amounts or IDs
- In financial reconciliation, a single hallucinated amount could cause a material misstatement
- The guard mathematically verifies every number against source data before it reaches the report

---

### 6.7 Utils Module (`src/utils/`)

| File                | What It Does                                                                                                                                                                                                                                                                            |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config.py`         | Configuration loader — reads YAML from `config/` directory, loads `.env` via python-dotenv. Exposes `get_thresholds()`, `get_bank_rules()`, `get_env()`                                                                                                                                 |
| `logging.py`        | Structured JSON logging via structlog — machine-parseable, correlatable by run_id                                                                                                                                                                                                       |
| `metrics.py`        | Full metrics computation suite: precision, recall, F1, MCC (Matthews Correlation Coefficient), FPR, exception detection rate, human fallback rate, amount variance %, confidence ECE (Expected Calibration Error). `evaluate_run()` computes all metrics from predicted vs ground truth |
| `metrics_runner.py` | Runs the deterministic aligner on fixture datasets and evaluates against golden answers. CI gates: Precision ≥ 0.95, Recall ≥ 0.98, F1 ≥ 0.96. Outputs `data/metrics.jsonl`                                                                                                             |

---

### 6.8 Workflow Module (`src/workflow/`)

| File     | What It Does                                                                                                                                                                                                                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api.py` | **The main FastAPI application.** All REST endpoints in one file. Handles file uploads, triggers reconciliation, manages exception queues, knowledge base CRUD, and semantic search with optional GPT-4o summarization. Uses in-memory dicts for run/exception storage (single-process local dev) |

---

### 6.9 Output Module (`src/output/`)

| File                  | What It Does                                                                                                                                                                                                                           |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `report_generator.py` | Report generation in 3 formats: (1) JSON — canonical report dict with summary stats, matched pairs, exceptions, audit trail; (2) CSV — unmatched items export (ERP-ready); (3) Plain text — immutable audit document with all sections |

---

### 6.10 Frontend (`frontend/`)

| File     | What It Does                                                                                                                                               |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py` | Streamlit interactive dashboard with 5 pages. Communicates with FastAPI backend via HTTP REST calls. See [Section 10](#10-frontend-pages) for page details |

---

## 7. Configuration System

### Environment Variables (`.env`)

| Variable                    | Default                  | Purpose                                          |
| --------------------------- | ------------------------ | ------------------------------------------------ |
| `OPENAI_API_KEY`            | —                        | OpenAI API authentication                        |
| `OPENAI_EMBEDDING_MODEL`    | `text-embedding-3-small` | Embedding model for RAG                          |
| `OPENAI_CHAT_MODEL`         | `gpt-4o`                 | Chat model for classification/explanation        |
| `CHROMA_PATH`               | `data/chroma_db`         | ChromaDB persistent storage path                 |
| `AMOUNT_TOLERANCE`          | `0.01`                   | Maximum amount difference for tolerance matching |
| `DATE_TOLERANCE_DAYS`       | `2`                      | Maximum date difference in days                  |
| `HUMAN_FALLBACK_CONFIDENCE` | `0.70`                   | Below this confidence, route to human review     |
| `API_HOST`                  | `0.0.0.0`                | FastAPI bind address                             |
| `API_PORT`                  | `8000`                   | FastAPI bind port                                |

### YAML Configs

**`thresholds.yaml`** controls matching sensitivity:

```yaml
matching:
  amount_tolerance: 0.01 # ±$0.01
  date_tolerance_days: 2 # ±2 days
  description_fuzzy_min: 75 # Fuzzy score threshold (0–100)

weights:
  amount: 0.4 # 40% of composite score
  date: 0.3 # 30% of composite score
  description: 0.3 # 30% of composite score

confidence:
  exact_match: 1.0
  rule_match: 0.95
  soft_match_max: 0.85
  soft_match_min: 0.70

rag:
  top_k: 5
  min_relevance_score: 0.60
```

**`bank_rules.yaml`** defines bank-specific behaviors:

```yaml
Chase:
  timing_offset_days: 1
  description_strip_prefixes:
    - "INCOMING TRANSFER - "
    - "OUTGOING WIRE - "

BankOfAmerica:
  timing_offset_days: 0
  description_strip_prefixes:
    - "ACH CREDIT "
    - "ACH DEBIT "

Generic:
  timing_offset_days: 2
  description_strip_prefixes: []
```

---

## 8. Testing Strategy

### Test Pyramid

```
         ╱╲
        ╱ E2E ╲          1 file  — Live OpenAI calls (skipped without API key)
       ╱────────╲
      ╱Integration╲      4 files — Full HTTP round-trips, RAG pipeline, KB CRUD
     ╱──────────────╲
    ╱   Unit Tests    ╲   7 files — Every module tested in isolation (mocked)
   ╱____________________╲
```

### Test Coverage by Module

| Test File                                   | What It Covers                                                                                                                                  |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/unit/test_ingestion.py`              | CSV/Excel/API parsers, validator (zero amount, future date, duplicates), enricher (prefix stripping)                                            |
| `tests/unit/test_matching.py`               | Exact matcher, rule matcher (Chase timing), tolerance matcher (boundary conditions), full aligner priority chain                                |
| `tests/unit/test_validation.py`             | Hallucination guard (invented amounts/IDs, nested data), confidence scorer (normalization, threshold boundary), audit trail (CRUD, append-only) |
| `tests/unit/test_output.py`                 | Report builder, JSON/CSV/audit-text exports, structural validation                                                                              |
| `tests/unit/test_metrics.py`                | Confusion matrix, P/R/F1/MCC/FPR, exception detection rate, ECE, full evaluate_run                                                              |
| `tests/unit/test_graph.py`                  | Deterministic match node, routing logic, soft matcher, validator node, output node, graph compilation (all mocked)                              |
| `tests/unit/test_fixtures.py`               | Fixture parsing, exact matcher on smoke set (≥30 matches), tolerance boundary, adversarial no-crash                                             |
| `tests/integration/test_api.py`             | Full HTTP round-trip: POST /reconcile → GET status → GET report, exception queue CRUD                                                           |
| `tests/integration/test_rag.py`             | Seed & retrieve from all 4 collections, metadata filtering, ingest count verification                                                           |
| `tests/integration/test_knowledge_base.py`  | Document loader chunking, KB CRUD, duplicate detection, API endpoint tests                                                                      |
| `tests/integration/test_attention_paper.py` | PDF ingestion + query (skipped if PDF not found)                                                                                                |
| `tests/e2e/test_live_openai.py`             | Live embeddings, chat completion, exception classification, explanation generation                                                              |

### Synthetic Test Data Generator

`tests/fixtures/generate_fixtures.py` creates realistic test datasets:

- **Smoke set** (100 txns/side): 40 exact matches, 10 timing diffs, 5 rounding, 5 duplicates, 5 missing, 5 reversals, 30 edge cases
- **Integration set** (5,000 txns): Scaled-up smoke set for performance testing
- **Adversarial set**: Empty IDs, extreme values ($0.001, $999M), hallucination trigger strings

Golden answers in `golden_answers.json` for automated correctness verification.

---

## 9. API Reference

### Reconciliation Endpoints

| Method | Path                         | Purpose                                                                                      |
| ------ | ---------------------------- | -------------------------------------------------------------------------------------------- |
| `POST` | `/reconcile`                 | Upload bank file + optional ledger file, run matching. Returns `{run_id}`. Max 50MB per file |
| `GET`  | `/reconcile/{run_id}/status` | Poll reconciliation status: `queued`, `running`, `completed`, `failed`                       |
| `GET`  | `/reconcile/{run_id}/report` | Full reconciliation report JSON (matches, exceptions, stats)                                 |

### Exception Queue Endpoints

| Method | Path                            | Purpose                             |
| ------ | ------------------------------- | ----------------------------------- |
| `GET`  | `/exceptions/queue`             | List all pending human review items |
| `POST` | `/exceptions/{id}/approve`      | Approve an exception with reason    |
| `POST` | `/exceptions/{id}/reject`       | Reject an exception with reason     |
| `POST` | `/exceptions/{id}/manual-match` | Human provides correct match        |

### Knowledge Base Endpoints

| Method   | Path                                          | Purpose                                      |
| -------- | --------------------------------------------- | -------------------------------------------- |
| `POST`   | `/knowledge-base/upload`                      | Upload PDF/Word/Excel/text into ChromaDB     |
| `GET`    | `/knowledge-base/documents`                   | List all ingested documents                  |
| `DELETE` | `/knowledge-base/documents/{filename}`        | Delete document by filename or hash          |
| `GET`    | `/knowledge-base/search?q=...&summarize=true` | Semantic search with optional GPT-4o summary |

---

## 10. Frontend Pages

### Page 1: Dashboard

- **Purpose:** At-a-glance overview of reconciliation system health
- **Shows:** Active reconciliation runs, completion status, summary statistics

### Page 2: Document Management

- **Purpose:** Manage the knowledge base document collection
- **Features:** Upload new documents (PDF, Word, Excel, text), view list of all ingested documents with metadata, delete documents
- **Use case:** Upload bank policies, SOPs, regulatory guidelines that the AI will reference during exception handling

### Page 3: Reconciliation

- **Purpose:** The core workflow — run a bank reconciliation
- **Features:** Upload bank statement + ledger file, choose file format, trigger matching, view results with matched pairs, unmatched items, and confidence scores
- **Use case:** Daily reconciliation process

### Page 4: Exception Queue

- **Purpose:** Human-in-the-loop review of AI decisions
- **Features:** View all exceptions flagged for human review, see AI classification + confidence + explanation, approve/reject/manual-match each exception
- **Use case:** Treasury analysts review the 2–5% of transactions the AI couldn't confidently match

### Page 5: Knowledge Base Search

- **Purpose:** Semantic search across all uploaded knowledge base documents
- **Features:** Natural language query input, AI-generated summary of search results (GPT-4o), expandable raw chunks with similarity scores
- **Use case:** Quick policy lookup — "What's the SOP for handling timing differences with Chase?"

---

## 11. Quality Gates & Metrics

### CI Accuracy Thresholds

| Metric              | Threshold | Formula                          |
| ------------------- | --------- | -------------------------------- |
| Precision           | ≥ 95%     | TP / (TP + FP)                   |
| Recall              | ≥ 98%     | TP / (TP + FN)                   |
| F1 Score            | ≥ 0.96    | 2 × (P × R) / (P + R)            |
| MCC                 | ≥ 0.90    | Matthews Correlation Coefficient |
| False Positive Rate | ≤ 2%      | FP / (FP + TN)                   |

### Additional Tracked Metrics

| Metric                   | Purpose                                                                         |
| ------------------------ | ------------------------------------------------------------------------------- |
| Exception Detection Rate | % of true exceptions correctly identified                                       |
| Human Fallback Rate      | % of transactions routed to human review                                        |
| Amount Variance %        | Average amount discrepancy in tolerance matches                                 |
| Confidence ECE           | Expected Calibration Error — how well confidence scores predict actual accuracy |

---

## 12. Setup & Running

### Prerequisites

- Python 3.11+ (recommended: 3.12)
- OpenAI API key
- Windows/macOS/Linux

### Installation

```powershell
# Navigate to project
cd bank-reconciliation-agent

# Create virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .

# Configure environment
copy .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### Start Backend

```powershell
uvicorn src.workflow.api:app --host 0.0.0.0 --port 8001 --reload
```

### Start Frontend

```powershell
streamlit run frontend/app.py
```

### Run Tests

```powershell
# All unit tests (no API key needed)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# E2E tests (requires API key)
pytest tests/e2e/ -v

# Metrics runner (accuracy gates)
python -m src.utils.metrics_runner
```

---

## 13. Sharing This Project — LinkedIn & Presentation Guide

### Elevator Pitch (30 seconds)

> "I built an AI-powered bank reconciliation agent that replaces 4–8 hours of daily manual work. It uses a 3-tier deterministic matching engine for speed and accuracy, GPT-4o for classifying the exceptions humans struggle with, and RAG to ground every AI decision in actual company policies. It catches hallucinated numbers before they reach the report, and routes uncertain decisions to human reviewers with full explanations."

### LinkedIn Post (Ready to Copy)

---

**🏦 I Built an AI Agent That Automates Bank Reconciliation — Here's How It Works**

Bank reconciliation is one of finance's most painful daily tasks. Thousands of transactions, multiple formats, timing differences, duplicates, reversals — and it all needs to balance to the penny.

So I built **SmartBots Bank Reconciliation Agent** — a multi-layer AI system that handles the entire process:

**🔧 The Architecture:**

- **3-Tier Deterministic Engine** — Exact matching → bank-specific rule matching → fuzzy tolerance matching. Handles 95%+ of transactions with zero LLM costs.
- **GPT-4o Exception Classifier** — For the 2-5% that can't be matched deterministically, AI classifies them into 7 categories (timing, rounding, duplicate, reversal, etc.)
- **RAG-Grounded Decisions** — Every AI decision is backed by retrieved SOPs, historical cases, and bank policies from a ChromaDB vector store
- **Hallucination Guard** — Mathematically verifies every number in LLM outputs against source data. In finance, you can't afford invented amounts.
- **Human-in-the-Loop** — Low-confidence decisions route to reviewers with AI explanations

**⚡ Tech Stack:**
Python 3.12 · FastAPI · LangGraph · GPT-4o · ChromaDB · Streamlit · RapidFuzz · Pydantic v2

**📊 Quality Gates:**
Precision ≥95% · Recall ≥98% · F1 ≥0.96 · MCC ≥0.90

**🎯 Key Design Decisions:**

- Deterministic matching runs FIRST — LLMs are expensive, slow, and unreliable for exact matching
- LangGraph over raw LangChain — explicit state machines > hidden chains
- ChromaDB local — no cloud dependency for vector storage
- Append-only audit trail — every decision is traceable

This isn't just a demo — it's a production-grade architecture with unit tests, integration tests, synthetic data generators, and CI accuracy gates.

Would love to hear how others are approaching AI in financial operations.

#AI #FinTech #BankReconciliation #LangGraph #RAG #GPT4o #Python #MachineLearning #FinancialAutomation

---

### Key Talking Points for Presentations

1. **"Why not just use an LLM for everything?"**
   - Cost: GPT-4o costs ~$5/1M input tokens. For 10,000 daily transactions, that's $50–100/day just for matching
   - Speed: Deterministic matching is 1000x faster
   - Accuracy: Exact matching is provably correct. LLMs are probabilistic
   - Our approach: Use deterministic matching for the easy 95%, LLMs only for the hard 5%

2. **"How do you prevent hallucinations in financial data?"**
   - The hallucination guard recursively checks every amount and ID in LLM outputs against source data
   - If the LLM invents a number, it gets caught before reaching the report
   - This is the difference between a demo and a production system

3. **"Why LangGraph instead of a simple script?"**
   - Bank reconciliation has conditional logic: if everything matches, skip LLM calls entirely
   - The state machine makes every transition visible, testable, and debuggable
   - Each node is independently testable with mocked inputs

4. **"Why RAG for a reconciliation tool?"**
   - Exception handling requires context — "What's our SOP for Chase timing differences?"
   - Historical cases help the LLM make better classifications
   - Policy documents ground explanations in actual company procedures

5. **"What are the accuracy metrics?"**
   - Precision ≥ 95% (minimal false matches)
   - Recall ≥ 98% (almost no missed matches)
   - MCC ≥ 0.90 (balanced metric even with class imbalance)
   - Confidence ECE tracks calibration — are 90% confidence predictions actually correct 90% of the time?

### Architecture Diagram for Slides

Use the ASCII diagram from [Section 2](#2-high-level-architecture) or create visual versions using:

- **Mermaid** (embeddable in GitHub, Notion, Confluence)
- **draw.io** (free, exports to PNG/SVG)
- **Excalidraw** (hand-drawn style, great for presentations)

### Target Audiences

| Audience                   | Emphasize                                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------------------ |
| Engineers                  | LangGraph state machine, hallucination guard, 3-tier matching algorithm, test pyramid            |
| Product Managers           | Time savings (4–8 hrs → minutes), accuracy metrics, human-in-the-loop safety                     |
| Finance Teams              | Exception handling, audit trail, compliance readiness, SOP grounding                             |
| Executives                 | ROI (labor cost reduction), risk reduction (no hallucinated amounts), scalability                |
| Recruiters/Hiring Managers | System design thinking, production-grade architecture, multi-layer safety, comprehensive testing |

---

## Appendix: Module Dependency Graph

```
                    ┌─────────────────┐
                    │   config/*.yaml  │
                    │   .env           │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  src/utils/     │
                    │  config.py      │
                    │  logging.py     │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────▼──────┐   ┌──────▼───────┐   ┌─────▼──────┐
    │ ingestion/ │   │ matching_    │   │  rag/      │
    │ schema     │   │ engine/      │   │ retriever  │
    │ parsers    │   │ algorithms   │   │ ChromaDB   │
    │ validator  │   │ aligner      │   │ doc_loader │
    │ enricher   │   └──────┬───────┘   └─────┬──────┘
    └─────┬──────┘          │                  │
          │                 │                  │
          └─────────────────┼──────────────────┘
                            │
                   ┌────────▼────────┐
                   │  src/graph/     │
                   │  LangGraph      │
                   │  state machine  │
                   │  GPT-4o nodes   │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │ src/validation/ │
                   │ hallucination   │
                   │ confidence      │
                   │ audit trail     │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │  src/output/    │
                   │  JSON / CSV /   │
                   │  audit text     │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │ src/workflow/   │
                   │ FastAPI API     │
                   └────────┬────────┘
                            │ HTTP
                   ┌────────▼────────┐
                   │ frontend/       │
                   │ Streamlit       │
                   └─────────────────┘
```

---

_Generated for SmartBots Bank Reconciliation AI Agent. Last updated: 2025._

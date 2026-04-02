# SmartBots Bank Reconciliation Agent — Architecture Guide

## Table of Contents
1. [High-Level Architecture](#high-level-architecture)
2. [Application Startup](#application-startup)
3. [Screen-by-Screen Flow](#screen-by-screen-flow)
4. [Complete Call Chain — Reconciliation](#complete-call-chain--reconciliation)
5. [Complete Call Chain — Knowledge Base](#complete-call-chain--knowledge-base)
6. [Module Reference](#module-reference)
7. [Latency Optimizations Applied](#latency-optimizations-applied)
8. [Accuracy Optimizations Applied](#accuracy-optimizations-applied)

---

## High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                     STREAMLIT FRONTEND                            │
│                    (frontend/app.py)                              │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐ │
│  │Dashboard │ │Doc Mgmt   │ │Reconcile │ │Exception│ │KB      │ │
│  │          │ │           │ │          │ │Queue    │ │Search  │ │
│  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └────┬────┘ └───┬────┘ │
└───────┼─────────────┼────────────┼────────────┼──────────┼───────┘
        │  HTTP       │            │            │          │
        ▼             ▼            ▼            ▼          ▼
┌───────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                               │
│                   (src/workflow/api.py)                           │
│                     Port: 8001                                    │
│                                                                   │
│  Endpoints:                                                       │
│  POST /reconcile              GET  /exceptions/queue              │
│  GET  /reconcile/{id}/report  POST /exceptions/{id}/approve       │
│  GET  /reconcile/{id}/status  POST /exceptions/{id}/reject        │
│  POST /knowledge-base/upload  POST /exceptions/{id}/manual-match  │
│  GET  /knowledge-base/documents  GET  /knowledge-base/search      │
│  DELETE /knowledge-base/documents/{name}                          │
└──────────┬─────────────────────────────┬─────────────────────────┘
           │                             │
           ▼                             ▼
┌─────────────────────┐    ┌──────────────────────────┐
│  MATCHING ENGINE     │    │  RAG / KNOWLEDGE BASE     │
│  (deterministic)     │    │  (ChromaDB + OpenAI)      │
│                      │    │                           │
│  1. Exact Matcher    │    │  Collections:             │
│  2. Rule Matcher     │    │  - knowledge_base         │
│  3. Tolerance Matcher│    │  - policies_sops          │
│       │              │    │  - prior_reconciliations  │
│       ▼              │    │  - exception_catalog      │
│  (if unmatched) ─────┼───▶│  - bank_rules             │
│                      │    │  - audit_logs             │
│  LangGraph Pipeline  │    │                           │
│  4. Exception Class. │◀───│  RAG Retrieval            │
│  5. Soft Matcher     │    │                           │
│  6. Edge-Case Reason.│◀───│  RAG Retrieval            │
│  7. Explainer        │◀───│  RAG Retrieval            │
│  8. Validator        │    │                           │
│  9. Output           │    │                           │
└──────────────────────┘    └──────────────────────────┘
           │                             │
           ▼                             ▼
┌─────────────────────┐    ┌──────────────────────────┐
│  OpenAI GPT-4o       │    │  OpenAI Embeddings        │
│  (shared singleton)  │    │  text-embedding-3-small   │
└─────────────────────┘    └──────────────────────────┘
```

---

## Application Startup

### Step 1: Start the FastAPI Backend
```bash
uvicorn src.workflow.api:app --host 127.0.0.1 --port 8001 --reload
```
**What loads:**
1. `src/workflow/api.py` → creates FastAPI app, registers all endpoints
2. Imports parsers, enricher, aligner, knowledge base, LLM client
3. Config loaded lazily on first use (cached with `@lru_cache`)
4. ChromaDB client created lazily on first RAG query (singleton)
5. OpenAI client created lazily on first LLM call (singleton)

### Step 2: Start the Streamlit Frontend
```bash
streamlit run frontend/app.py --server.port 8501
```
**What loads:**
1. `frontend/app.py` → creates Streamlit UI with sidebar navigation
2. Connects to FastAPI backend at `http://127.0.0.1:8001`
3. No direct database or LLM connections (all via API)

---

## Screen-by-Screen Flow

### Screen 1: Dashboard
```
User opens app → Sidebar "Dashboard"
    │
    ▼
frontend/app.py (Dashboard section)
    │
    ├── Shows welcome text and feature overview
    │
    └── GET /knowledge-base/documents
         │
         └── api.py:kb_list()
              └── knowledge_base.py:list_documents()
                   └── ChromaDB query: knowledge_base collection
                        └── Returns: document count metric
```
**Purpose:** Landing page with quick status metrics.

---

### Screen 2: Document Management
```
User selects "Document Management"
    │
    ├── UPLOAD FLOW:
    │   User picks file → clicks "Ingest Document"
    │       │
    │       └── POST /knowledge-base/upload (multipart file)
    │            │
    │            └── api.py:kb_upload()
    │                 │
    │                 ├── Validates extension (.pdf,.docx,.xlsx,.txt,.md,.csv,.json)
    │                 ├── Validates size (< 50 MB)
    │                 │
    │                 └── knowledge_base.py:ingest_document()
    │                      │
    │                      ├── document_loader.py:detect_and_extract()
    │                      │    ├── PDF  → extract_pdf()  (PyMuPDF/fitz)
    │                      │    ├── DOCX → extract_docx() (python-docx)
    │                      │    ├── XLSX → extract_excel() (openpyxl)
    │                      │    └── TXT  → extract_text() (raw read)
    │                      │
    │                      ├── document_loader.py:file_content_hash() → SHA-256 dedup
    │                      ├── document_loader.py:chunk_text() → 1000 chars, 200 overlap
    │                      │
    │                      └── ChromaDB upsert → knowledge_base collection
    │                           (with embeddings via OpenAI text-embedding-3-small)
    │
    ├── LIST FLOW:
    │   GET /knowledge-base/documents
    │       └── knowledge_base.py:list_documents()
    │            └── ChromaDB get → unique (filename, content_hash) pairs
    │
    └── DELETE FLOW:
        User clicks "Delete" on a document
            └── DELETE /knowledge-base/documents/{filename}?content_hash=xxx
                 └── knowledge_base.py:delete_document()
                      └── ChromaDB delete by filename + content_hash filter
```

---

### Screen 3: Reconciliation (Main Flow)
```
User selects "Reconciliation"
    │
    ├── Selects bank name (Generic / Chase / BankOfAmerica)
    ├── Uploads bank statement (CSV/Excel)
    ├── Optionally uploads ledger file
    ├── Clicks "Run Reconciliation"
    │
    └── POST /reconcile (multipart: file + ledger_file + bank_name)
         │
         └── api.py:reconcile()    [FULL PIPELINE — see detailed chain below]
              │
              ├── Returns: { run_id: "uuid" }
              │
              └── Frontend immediately calls:
                   GET /reconcile/{run_id}/report
                        │
                        └── api.py:get_report()
                             └── Returns: {
                                   matched_count,
                                   unmatched_ledger_count,
                                   unmatched_bank_count,
                                   matches: [...],
                                   exception_ids: [...]
                                 }
    │
    └── Frontend displays:
        ├── 3 metric cards (Matched / Unmatched Ledger / Unmatched Bank)
        ├── Matched Pairs table (first 20)
        └── Exception count + link to Exception Queue
```

---

### Screen 4: Exception Queue
```
User selects "Exception Queue"
    │
    └── GET /exceptions/queue
         │
         └── api.py:exception_queue()
              └── Filters _exceptions dict for status == "pending"
                   └── Returns: list of exception dicts
    │
    └── For each exception, user can:
        │
        ├── APPROVE:
        │   POST /exceptions/{id}/approve  { "reason": "..." }
        │       └── api.py:approve_exception()
        │            └── Sets status = "approved", records reason
        │
        ├── REJECT:
        │   POST /exceptions/{id}/reject   { "reason": "..." }
        │       └── api.py:reject_exception()
        │            └── Sets status = "rejected", records reason
        │
        └── (Future: Manual Match)
            POST /exceptions/{id}/manual-match { "ledger_id", "bank_id" }
                └── api.py:manual_match()
                     └── Sets status = "manually_matched"
```

---

### Screen 5: Knowledge Base Search
```
User selects "Knowledge Base Search"
    │
    ├── Enters search query
    ├── Sets result count (1-20)
    ├── Optional filename filter
    ├── Optional "Generate AI Summary" checkbox
    ├── Clicks "Search"
    │
    └── GET /knowledge-base/search?q=...&n=5&summarize=true
         │
         └── api.py:kb_search()
              │
              ├── knowledge_base.py:query_knowledge_base()
              │    └── ChromaDB similarity search on knowledge_base collection
              │         └── Returns: chunks with similarity scores
              │
              └── IF summarize=true:
                   └── OpenAI GPT-4o call
                        ├── System: "summarize retrieved chunks for the query"
                        └── User: query + retrieved chunk text
                             └── Returns: AI-synthesized summary
    │
    └── Frontend displays:
        ├── AI Summary (if enabled)
        └── Individual chunks with similarity scores in expandable sections
```

---

## Complete Call Chain — Reconciliation

This is the step-by-step execution when user clicks **"Run Reconciliation"**:

```
POST /reconcile
│
├── PHASE 1: FILE PARSING
│   ├── api.py:_detect_format(filename) → "csv" or "excel"
│   │
│   ├── CSV path:
│   │   ├── csv_parser.py:parse_csv(bank_bytes) → list[Transaction]
│   │   └── csv_parser.py:parse_csv(ledger_bytes) → list[Transaction]
│   │
│   └── Excel path:
│       ├── excel_parser.py:parse_excel(bank_bytes, sheet="bank")
│       └── excel_parser.py:parse_excel(ledger_bytes, sheet="ledger")
│
├── PHASE 2: ENRICHMENT (NEW — accuracy improvement)
│   └── enricher.py:enrich_transactions(transactions, bank_name)
│       ├── Loads bank config from config/bank_rules.yaml (cached)
│       ├── Strips bank-specific description prefixes
│       │   (e.g., Chase: "INCOMING TRANSFER - ", "OUTGOING WIRE - ")
│       └── Returns normalized Transaction list
│
├── PHASE 3: DETERMINISTIC MATCHING
│   └── ledger_bank_aligner.py:align(ledger, bank, bank_name)
│       │
│       ├── Stage 1: exact_matcher.py:exact_match()
│       │   ├── Indexes bank txns by (amount, date, reference) → O(n) lookup
│       │   ├── Match condition: amount == amount AND date == date AND reference == reference
│       │   ├── Confidence: 1.0
│       │   └── Returns: (matched, unmatched_ledger, unmatched_bank)
│       │
│       ├── Stage 2: rule_matcher.py:rule_match(remainders, bank_name)
│       │   ├── Loads bank_rules.yaml → timing_offset, prefix_strips (cached)
│       │   ├── Indexes bank txns by amount → O(n) lookup (optimized)
│       │   ├── Match condition: amount == AND date within offset AND reference matches
│       │   ├── Confidence: 0.95
│       │   └── Returns: (matched, unmatched_ledger, unmatched_bank)
│       │
│       └── Stage 3: tolerance_matcher.py:tolerance_match(remainders)
│           ├── Loads thresholds.yaml (cached)
│           ├── Composite scoring per pair:
│           │   ├── Amount: 40% weight — 1.0 if within $0.01 tolerance
│           │   ├── Date:   30% weight — 1.0 if same day, scaled within 2-day window
│           │   └── Desc:   30% weight — rapidfuzz token_set_ratio / 100
│           ├── Min confidence: 0.70
│           └── Returns: (matched, unmatched_ledger, unmatched_bank)
│
├── PHASE 4: BUILD EXCEPTIONS
│   └── For each unmatched transaction:
│       └── Creates exception dict → stored in _exceptions (in-memory)
│
├── PHASE 5: BUILD REPORT
│   └── report = {
│         run_id, bank, matched_count,
│         unmatched_ledger_count, unmatched_bank_count,
│         matches: [...MatchResult dicts],
│         exception_ids: [...]
│       }
│
└── Returns: { run_id: "uuid" }
```

### When LangGraph Pipeline Is Used (Future / Advanced)

If the graph is invoked (via `build_graph().compile().invoke(state)`), additional phases run:

```
PHASE 6: EXCEPTION CLASSIFICATION (parallel LLM)
│   └── exception_classifier.py:exception_classifier(state)
│       ├── For EACH unmatched txn (parallel via ThreadPoolExecutor):
│       │   ├── retriever.py:retrieve("prior_reconciliations", description, n=3)
│       │   │   └── ChromaDB similarity search → top-3 historical cases
│       │   │
│       │   └── OpenAI GPT-4o call:
│       │       ├── Prompt: exception_classification.txt (cached)
│       │       ├── Input: transaction + RAG context
│       │       └── Output: { category, confidence, reasoning }
│       │
│       └── Returns: { exceptions: [...ExceptionItem] }
│
PHASE 7: SOFT MATCHING + EDGE-CASE REASONING
│   ├── soft_matcher.py:soft_matcher(state)
│   │   ├── Same composite scoring as tolerance_matcher
│   │   ├── Uses config date tolerance (not hard-coded)
│   │   └── Returns: { soft_match_candidates: [...MatchResult] }
│   │
│   └── edge_case_reasoner.py:edge_case_reasoner(state)
│       ├── retriever.py:retrieve("policies_sops", "reversal partial payment...")
│       ├── OpenAI GPT-4o chain-of-thought call:
│       │   ├── Prompt: edge_case_reasoning.txt (cached)
│       │   ├── Checks: reversals, partial payments, splits, currency diffs
│       │   └── Output: { proposed_matches, unresolvable }
│       └── Returns: { soft_match_candidates: [...MatchResult] }
│
PHASE 8: EXPLANATION GENERATION (parallel LLM)
│   └── explainer.py:explainer(state)
│       ├── For EACH exception (parallel via ThreadPoolExecutor):
│       │   ├── Uses cached RAG context from classification step
│       │   └── OpenAI GPT-4o call:
│       │       ├── Prompt: explanation_generation.txt (cached)
│       │       └── Output: human-readable explanation (< 200 words)
│       └── Returns: { explanations: { txn_id: explanation } }
│
PHASE 9: VALIDATION
│   └── validator_node.py:validator_node(state)
│       ├── Deduplicates soft matches (keeps highest confidence per ledger_id)
│       ├── Validates MatchResult Pydantic schemas
│       ├── Builds confidence_scores map
│       └── Routes low-confidence exceptions (< 0.70) → human_review_queue
│
PHASE 10: OUTPUT
    └── graph_builder.py:output_node(state)
        └── Assembles final_report: {
              matched_count, unmatched_ledger_count,
              unmatched_bank_count, exception_count,
              human_review_count
            }
```

### LangGraph State Machine

```
                    ┌──────────────────────┐
                    │  deterministic_match  │ (entry point)
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  after_deterministic  │ (conditional routing)
                    └──┬───────────────┬───┘
                       │               │
              (has unmatched)    (all matched)
                       │               │
          ┌────────────▼──────┐        │
          │exception_classifier│        │
          └────────────┬──────┘        │
                       │               │
          ┌────────────▼──────────┐    │
          │soft_match_and_reason  │    │
          │  ├ soft_matcher       │    │
          │  └ edge_case_reasoner │    │
          └────────────┬──────────┘    │
                       │               │
          ┌────────────▼──────┐        │
          │    explainer      │        │
          └────────────┬──────┘        │
                       │               │
          ┌────────────▼──────┐        │
          │    validator      │        │
          └────────────┬──────┘        │
                       │               │
                    ┌──▼───────────────▼──┐
                    │       output         │
                    └──────────┬───────────┘
                               │
                              END
```

---

## Complete Call Chain — Knowledge Base

### Upload Document
```
POST /knowledge-base/upload
│
├── Validate extension + file size
│
└── knowledge_base.py:ingest_document(filename, source, content_bytes)
    │
    ├── document_loader.py:detect_and_extract(filename, source)
    │   ├── .pdf  → extract_pdf()   uses PyMuPDF (fitz)
    │   ├── .docx → extract_docx()  uses python-docx
    │   ├── .xlsx → extract_excel() uses openpyxl
    │   └── .txt/.md/.csv/.json → extract_text() raw read
    │
    ├── document_loader.py:file_content_hash(content_bytes)
    │   └── SHA-256 first 16 chars (for deduplication)
    │
    ├── Check duplicate: query ChromaDB by content_hash
    │   └── If exists → return { status: "already_exists" }
    │
    ├── document_loader.py:chunk_text(text, chunk_size=1000, overlap=200)
    │   └── Splits at paragraph/sentence boundaries
    │
    ├── document_loader.py:generate_chunk_id(filename, index, hash)
    │   └── Deterministic: "{filename}_chunk{index}_{hash}"
    │
    └── ChromaDB upsert → knowledge_base collection
        ├── IDs: chunk IDs
        ├── Documents: chunk text
        └── Metadatas: filename, doc_type, content_hash, chunk_index, total_chunks, uploaded_at
```

### Search Knowledge Base
```
GET /knowledge-base/search?q=...&n=5&summarize=true
│
├── knowledge_base.py:query_knowledge_base(q, n_results, filename_filter)
│   └── ChromaDB similarity search on knowledge_base collection
│       ├── L2 distance → similarity: 1/(1+distance)
│       └── Filter by min_relevance_score (0.60)
│
└── IF summarize=true:
    └── OpenAI GPT-4o (shared singleton client)
        ├── System prompt: "summarize for bank reconciliation context"
        └── Returns: AI-synthesized summary from retrieved chunks
```

---

## Module Reference

| Module | File | Purpose |
|--------|------|---------|
| **Frontend** | `frontend/app.py` | Streamlit UI: 5 pages, calls FastAPI backend |
| **API** | `src/workflow/api.py` | FastAPI REST endpoints, orchestrates pipeline |
| **Graph Builder** | `src/graph/graph_builder.py` | LangGraph StateGraph assembly |
| **Graph Routes** | `src/graph/routes.py` | Conditional routing functions |
| **Graph State** | `src/graph/state.py` | TypedDict for ReconciliationState |
| **Exception Classifier** | `src/graph/nodes/exception_classifier.py` | GPT-4o few-shot classification (parallel) |
| **Soft Matcher** | `src/graph/nodes/soft_matcher.py` | Fuzzy matching with composite scoring |
| **Edge-Case Reasoner** | `src/graph/nodes/edge_case_reasoner.py` | Chain-of-thought LLM reasoning |
| **Explainer** | `src/graph/nodes/explainer.py` | Human-readable explanation generation (parallel) |
| **Validator** | `src/graph/nodes/validator_node.py` | Schema validation + deduplication + human routing |
| **Aligner** | `src/matching_engine/ledger_bank_aligner.py` | Runs exact → rule → tolerance matchers |
| **Exact Matcher** | `src/matching_engine/algorithms/exact_matcher.py` | O(n) hash-indexed exact matching |
| **Rule Matcher** | `src/matching_engine/algorithms/rule_matcher.py` | Bank-specific rules with amount indexing |
| **Tolerance Matcher** | `src/matching_engine/algorithms/tolerance_matcher.py` | Composite scoring: amount+date+desc fuzzy |
| **Models** | `src/matching_engine/models.py` | Pydantic `MatchResult` model |
| **CSV Parser** | `src/ingestion/parsers/csv_parser.py` | pandas-based CSV → Transaction |
| **Excel Parser** | `src/ingestion/parsers/excel_parser.py` | openpyxl-based XLSX → Transaction |
| **Schema** | `src/ingestion/schema.py` | Pydantic `Transaction` model |
| **Enricher** | `src/ingestion/enricher.py` | Strip bank prefixes, normalize descriptions |
| **Validator** | `src/ingestion/validators/validator.py` | Transaction validation (amounts, dates, dupes) |
| **LLM Client** | `src/llm/client.py` | Singleton OpenAI client + model config |
| **Embeddings** | `src/llm/embeddings.py` | OpenAI text-embedding-3-small |
| **Collection Manager** | `src/rag/collection_manager.py` | ChromaDB singleton client + 6 collections |
| **Retriever** | `src/rag/retriever.py` | ChromaDB query with L2 → similarity conversion |
| **Knowledge Base** | `src/rag/knowledge_base.py` | Ingest/list/delete/query documents |
| **Document Loader** | `src/rag/document_loader.py` | PDF/Word/Excel/text extraction + chunking |
| **Config** | `src/utils/config.py` | YAML loader with `@lru_cache` |
| **Hallucination Guard** | `src/validation/hallucination_guard.py` | Checks LLM output against source data |
| **Confidence Scorer** | `src/validation/confidence_scorer.py` | Normalizes scores per method ceiling |
| **Audit Trail** | `src/validation/audit_trail.py` | JSONL audit log recorder |
| **Report Generator** | `src/output/report_generator.py` | JSON/CSV/text report assembly |

---

## Latency Optimizations Applied

| Optimization | Before | After | Impact |
|---|---|---|---|
| **Config caching** | `get_thresholds()` reads YAML from disk every call | `@lru_cache(maxsize=1)` — reads once | ~5ms saved per call × dozens of calls |
| **Prompt caching** | `_load_prompt()` reads .txt file every LLM call | `@lru_cache(maxsize=1)` — reads once | ~2ms saved per LLM call |
| **Singleton OpenAI client** | `OpenAI()` created per graph node (3-4 times) | `src/llm/client.py:get_openai_client()` — created once | Avoids repeated connection setup |
| **Singleton ChromaDB client** | `PersistentClient()` created per `retrieve()` call | `collection_manager.py` — created once | Avoids reopening SQLite DB |
| **Parallel exception classification** | Sequential: N unmatched × 1 GPT call each | ThreadPoolExecutor(max_workers=8) | N× speedup for I/O-bound LLM calls |
| **Parallel explanation generation** | Sequential: N exceptions × 1 GPT call each | ThreadPoolExecutor(max_workers=8) | N× speedup for I/O-bound LLM calls |
| **Rule matcher indexing** | O(n×m) brute force over all bank txns | Index by amount → O(n) average-case | 10-100× faster for large datasets |
| **Import moved to top-level** | `from datetime import date` inside for-loop in soft_matcher | Moved to module-level `from datetime import date` | Avoids repeated import overhead |

---

## Accuracy Optimizations Applied

| Optimization | Before | After | Impact |
|---|---|---|---|
| **Enricher integrated** | `enrich_transactions()` existed but was NEVER called | Called before `align()` in `api.py` | Bank description prefixes now stripped → better fuzzy matching |
| **Soft matcher date scoring** | Hard-coded `day_diff / 10.0` | Uses `date_tolerance_days` from config | Consistent scoring with tolerance_matcher |
| **Match deduplication** | soft_matcher + edge_case_reasoner could propose duplicate matches for same txn | `validator_node` deduplicates by `ledger_id`, keeps highest confidence | Prevents double-counting matches |
| **Rule matcher amount indexing** | Iterated all bank txns even when amounts don't match | Dict lookup by amount — only checks matching amounts | More efficient AND avoids false comparisons |

---

## Config Files

### `config/thresholds.yaml`
```yaml
matching:
  amount_tolerance: 0.01    # Max $ delta for tolerance match
  date_tolerance_days: 2    # Max day delta
  description_fuzzy_score: 75  # Min rapidfuzz score (0-100)
  weights:
    amount: 0.40
    date: 0.30
    description: 0.30

confidence:
  exact_match: 1.00
  rule_match: 0.95
  tolerance_match: 0.85
  soft_match_min: 0.70      # Min composite score for soft match
  human_fallback: 0.70      # Below this → human review queue

rag:
  top_k: 5
  min_relevance_score: 0.60
```

### `config/bank_rules.yaml`
```yaml
banks:
  - name: Chase
    timing_offset_days: 1
    description_prefix_strip:
      - "INCOMING TRANSFER - "
      - "OUTGOING WIRE - "
  - name: BankOfAmerica
    timing_offset_days: 0
    description_prefix_strip:
      - "ACH CREDIT "
      - "ACH DEBIT "
  - name: Generic
    timing_offset_days: 2
    description_prefix_strip: []
```

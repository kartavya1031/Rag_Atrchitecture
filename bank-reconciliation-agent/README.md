# SmartBots — Bank Reconciliation AI Agent

AI-powered bank reconciliation engine using LangGraph, GPT-4o, and ChromaDB.

## Quick Start

```powershell
# 1. Create and activate virtual environment
cd bank-reconciliation-agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
copy .env.example .env
# Edit .env and set your OPENAI_API_KEY

# 4. Run tests
pytest tests/ -v
```

## Project Structure

- `src/ingestion/` — Data parsers (BAI2, CSV, Excel) and validators
- `src/matching_engine/` — Deterministic matching (exact, rule-based, tolerance)
- `src/graph/` — LangGraph agent orchestration
- `src/llm/` — LLM prompts and tools
- `src/rag/` — ChromaDB vector store management
- `src/validation/` — Hallucination guards and audit trail
- `src/workflow/` — FastAPI endpoints
- `src/output/` — Report generation
- `config/` — Matching thresholds and bank-specific rules
- `tests/` — Unit, integration, and E2E tests

## Configuration

- `config/thresholds.yaml` — Matching sensitivity and confidence thresholds
- `config/bank_rules.yaml` — Bank-specific parsing rules
- `.env` — API keys and runtime settings

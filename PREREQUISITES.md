# Prerequisites & Setup Guide

## SmartBots — Bank Reconciliation AI Agent

Everything you need installed and configured before writing a single line of code.

---

## 1. System Requirements

| Requirement | Minimum                              | Recommended                                    |
| ----------- | ------------------------------------ | ---------------------------------------------- |
| OS          | Windows 10 / macOS 12 / Ubuntu 20.04 | Windows 11 / macOS 14 / Ubuntu 22.04           |
| Python      | 3.11                                 | **3.12**                                       |
| RAM         | 8 GB                                 | **16 GB** (LLM inference + ChromaDB in-memory) |
| Disk space  | 5 GB free                            | 20 GB free (vector index + test data)          |
| CPU         | 4 cores                              | 8+ cores                                       |

---

## 2. Accounts & API Keys

| Service    | Purpose                                                  | Where to get it                                                      | Required? |
| ---------- | -------------------------------------------------------- | -------------------------------------------------------------------- | --------- |
| **OpenAI** | GPT-4o (LLM) + `text-embedding-3-small` (RAG embeddings) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | ✅ Yes    |

> **Cost estimate (local dev):** ~$2–$5 per full integration test run (5k transactions) using GPT-4o. Smoke tests (100 txns) cost < $0.10.

---

## 3. Software to Install

### 3a. Python 3.12

- Windows: download from [python.org](https://www.python.org/downloads/) — tick **"Add to PATH"** during install
- Verify: `python --version` → should print `Python 3.12.x`

### 3b. pip (comes with Python)

- Verify: `pip --version`

### 3c. Git

- Download from [git-scm.com](https://git-scm.com/downloads)
- Verify: `git --version`

### 3d. (Optional but recommended) uv — fast Python package manager

```powershell
pip install uv
```

Replaces `pip install` with `uv pip install` for 10–100× faster installs.

### 3e. (Optional) VS Code extensions

| Extension   | ID                         | Purpose                                     |
| ----------- | -------------------------- | ------------------------------------------- |
| Python      | `ms-python.python`         | Python IntelliSense                         |
| Pylance     | `ms-python.vscode-pylance` | Type checking                               |
| REST Client | `humao.rest-client`        | Test FastAPI endpoints from `.http` files   |
| YAML        | `redhat.vscode-yaml`       | Edit `config/*.yaml` with schema validation |

---

## 4. Environment Setup (step by step)

```powershell
# 1 — Clone / open the project
cd d:\personal_project\bank-reconciliation-agent

# 2 — Create a virtual environment
python -m venv .venv

# 3 — Activate it (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 4 — Install all dependencies
pip install -r requirements.txt

# 5 — Copy env template and fill in your key
copy .env.example .env
# Then open .env and set OPENAI_API_KEY=sk-...
```

---

## 5. `.env` File Contents

Create `.env` (never commit this file):

```dotenv
# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o

# ChromaDB (local persistent storage)
CHROMA_PATH=./data/chroma_db

# Reconciliation engine
AMOUNT_TOLERANCE=0.01
DATE_TOLERANCE_DAYS=2
HUMAN_FALLBACK_CONFIDENCE=0.70

# API server
API_HOST=127.0.0.1
API_PORT=8000
```

---

## 6. Config Files to Populate

### `config/thresholds.yaml`

Controls matching sensitivity. Tune these as you measure accuracy.

```yaml
matching:
  amount_tolerance: 0.01 # Max $ delta for tolerance match
  date_tolerance_days: 2 # Max day delta for tolerance match
  description_fuzzy_score: 75 # Min rapidfuzz score (0-100)

  weights:
    amount: 0.40
    date: 0.30
    description: 0.30

confidence:
  exact_match: 1.00
  rule_match: 0.95
  tolerance_match: 0.85
  soft_match_min: 0.70
  human_fallback: 0.70 # Anything below this → human review queue

rag:
  top_k: 5 # Number of ChromaDB results to retrieve
  min_relevance_score: 0.60 # Discard retrieved docs below this cosine score
```

### `config/bank_rules.yaml`

Bank-specific quirks. Add a new block for each bank.

```yaml
banks:
  - name: Chase
    swift_bic: CHASUS33
    timing_offset_days: 1 # Chase posts same-day ACH with 1d delay in statement
    description_prefix_strip: # Strip these from bank narrative before fuzzy match
      - "INCOMING TRANSFER - "
      - "OUTGOING WIRE - "
    amount_sign_convention: standard # credits positive, debits negative

  - name: BankOfAmerica
    swift_bic: BOFAUS3N
    timing_offset_days: 0
    description_prefix_strip:
      - "ACH CREDIT "
      - "ACH DEBIT "
    amount_sign_convention: standard

  - name: Generic
    swift_bic: null
    timing_offset_days: 2
    description_prefix_strip: []
    amount_sign_convention: standard
```

---

## 7. Verify Everything Works

Run this checklist before starting development:

```powershell
# Python version
python --version                          # Expect: Python 3.12.x

# Packages installed
python -c "import openai; print('openai OK')"
python -c "import langgraph; print('langgraph OK')"
python -c "import chromadb; print('chromadb OK')"
python -c "import fastapi; print('fastapi OK')"
python -c "import pandas; print('pandas OK')"

# OpenAI key works
python -c "
from openai import OpenAI
client = OpenAI()
r = client.models.list()
print('OpenAI connection OK — models accessible')
"

# ChromaDB local client spins up
python -c "
import chromadb
client = chromadb.PersistentClient(path='./data/chroma_db')
col = client.get_or_create_collection('test')
print('ChromaDB OK — collection created at ./data/chroma_db')
"

# Run tests (should show 0 collected until you write them)
pytest tests/ -v
```

---

## 8. Dependency Version Notes

| Library          | Why this version matters                                                          |
| ---------------- | --------------------------------------------------------------------------------- |
| `langgraph>=0.3` | StateGraph's `send()` API for parallel node dispatch (needed for Phase 5)         |
| `pydantic>=2.0`  | v2 strict mode used for LLM output validation (not backward-compatible with v1)   |
| `chromadb>=0.6`  | Persistent client API changed in 0.5; earlier versions use deprecated `.Client()` |
| `openai>=1.0`    | v1 client required; v0.x uses completely different API                            |
| `rapidfuzz>=3.0` | `process.extractOne` signature changed in v3                                      |

---

## 9. Known Platform Notes (Windows)

- If `Activate.ps1` is blocked by execution policy, run:  
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- `bai2` library may need `pip install bai2 --no-build-isolation` on Windows if the C extension fails
- ChromaDB's SQLite backend on Windows requires Visual C++ Redistributable — install from Microsoft if you get a DLL error

"""Match result model used across all matchers."""

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    """A single matched pair of transactions."""

    ledger_id: str
    bank_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    method: Literal["exact", "rule", "tolerance", "soft", "llm"]
    details: Optional[str] = None

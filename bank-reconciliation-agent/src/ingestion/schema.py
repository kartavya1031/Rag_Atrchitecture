"""Unified Transaction schema for all data sources."""

import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    BAI2 = "bai2"
    CSV = "csv"
    EXCEL = "excel"
    API = "api"


class Transaction(BaseModel):
    """Canonical transaction representation used across the entire pipeline."""

    id: str = Field(..., description="Unique transaction identifier")
    date: datetime.date = Field(..., description="Transaction / value date")
    posting_date: Optional[datetime.date] = Field(None, description="Date posted to ledger")
    amount: Decimal = Field(..., description="Signed amount (credits +, debits -)")
    description: str = Field("", description="Transaction narrative / memo")
    reference: str = Field("", description="Bank reference or cheque number")
    source_type: SourceType = Field(..., description="Origin format of this txn")
    raw_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Passthrough bag for format-specific fields",
    )

    model_config = {"str_strip_whitespace": True}

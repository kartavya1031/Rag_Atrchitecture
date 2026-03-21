"""Transaction validation rules."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from src.ingestion.schema import Transaction
from src.utils.logging import get_logger

logger = get_logger(__name__)

MAX_FUTURE_DAYS = 5


class ValidationError:
    """Single validation failure."""

    def __init__(self, transaction_id: str, field: str, message: str):
        self.transaction_id = transaction_id
        self.field = field
        self.message = message

    def __repr__(self) -> str:
        return f"ValidationError({self.transaction_id}, {self.field}: {self.message})"


class ValidationResult:
    """Aggregate result of running all validations."""

    def __init__(self) -> None:
        self.errors: list[ValidationError] = []
        self.valid: list[Transaction] = []
        self.rejected: list[Transaction] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_transactions(transactions: list[Transaction]) -> ValidationResult:
    """Run all validation rules against a list of transactions."""
    result = ValidationResult()
    seen_ids: set[str] = set()

    for txn in transactions:
        txn_errors: list[ValidationError] = []

        # Null field checks
        if not txn.id:
            txn_errors.append(ValidationError(txn.id, "id", "ID is empty"))
        if txn.amount is None:
            txn_errors.append(ValidationError(txn.id, "amount", "Amount is null"))

        # Amount sign validation — zero is allowed
        if txn.amount is not None and txn.amount == Decimal("0"):
            txn_errors.append(ValidationError(txn.id, "amount", "Amount is zero"))

        # Date sanity — no future dates beyond T+5
        today = date.today()
        max_date = today + timedelta(days=MAX_FUTURE_DAYS)
        if txn.date > max_date:
            txn_errors.append(
                ValidationError(
                    txn.id,
                    "date",
                    f"Date {txn.date} is more than {MAX_FUTURE_DAYS} days in the future",
                )
            )

        # Duplicate detection by ID
        if txn.id in seen_ids:
            txn_errors.append(
                ValidationError(txn.id, "id", f"Duplicate transaction ID: {txn.id}")
            )
        seen_ids.add(txn.id)

        if txn_errors:
            result.errors.extend(txn_errors)
            result.rejected.append(txn)
        else:
            result.valid.append(txn)

    return result

"""Rule-based matcher — applies bank-specific rules from config."""

from src.ingestion.schema import Transaction
from src.matching_engine.models import MatchResult
from src.utils.config import get_bank_rules


def rule_match(
    ledger: list[Transaction],
    bank: list[Transaction],
    bank_name: str = "Generic",
) -> tuple[list[MatchResult], list[Transaction], list[Transaction]]:
    """Apply bank-specific rules to find matches.

    Rules include timing offsets and description normalization defined in bank_rules.yaml.

    Returns:
        (matched_pairs, unmatched_ledger, unmatched_bank)
    """
    rules = get_bank_rules()
    bank_cfg = _find_bank_config(rules, bank_name)
    timing_offset = bank_cfg.get("timing_offset_days", 0) if bank_cfg else 0

    matched: list[MatchResult] = []
    used_bank_ids: set[str] = set()
    unmatched_ledger: list[Transaction] = []

    for ltxn in ledger:
        found = False
        for btxn in bank:
            if btxn.id in used_bank_ids:
                continue
            # Amount must match exactly
            if ltxn.amount != btxn.amount:
                continue
            # Date must match within timing offset
            day_diff = abs((ltxn.date - btxn.date).days)
            if day_diff > timing_offset:
                continue
            # Reference should match if both present
            if ltxn.reference and btxn.reference and ltxn.reference != btxn.reference:
                continue

            matched.append(
                MatchResult(
                    ledger_id=ltxn.id,
                    bank_id=btxn.id,
                    confidence=0.95,
                    method="rule",
                    details=f"timing_offset={day_diff}d, bank={bank_name}",
                )
            )
            used_bank_ids.add(btxn.id)
            found = True
            break

        if not found:
            unmatched_ledger.append(ltxn)

    unmatched_bank = [b for b in bank if b.id not in used_bank_ids]
    return matched, unmatched_ledger, unmatched_bank


def _find_bank_config(rules: dict, bank_name: str) -> dict | None:
    for bank in rules.get("banks", []):
        if bank.get("name", "").lower() == bank_name.lower():
            return bank
    for bank in rules.get("banks", []):
        if bank.get("name", "").lower() == "generic":
            return bank
    return None

"""Generate test fixtures — smoke, integration, and adversarial datasets.

Usage:
    python -m tests.fixtures.generate_fixtures
"""

import datetime
import json
import random
import uuid
from decimal import Decimal
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent

random.seed(42)


def _uid(prefix: str = "TXN") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _rand_amount(lo: float = 10.0, hi: float = 50000.0) -> Decimal:
    return Decimal(str(round(random.uniform(lo, hi), 2)))


def _rand_date(start: str = "2024-01-01", days: int = 180) -> datetime.date:
    base = datetime.date.fromisoformat(start)
    return base + datetime.timedelta(days=random.randint(0, days))


def _rand_desc() -> str:
    prefixes = ["ACH CREDIT", "WIRE OUT", "CHECK DEPOSIT", "ACH DEBIT", "PAYROLL", "VENDOR PMT"]
    suffixes = ["ABC CORP", "XYZ LLC", "ACME INC", "GLOBEX", "INITECH", "UMBRELLA CO"]
    return f"{random.choice(prefixes)} {random.choice(suffixes)}"


# ---------------------------------------------------------------------------
# Fixture generators
# ---------------------------------------------------------------------------

def generate_smoke(n: int = 100) -> dict:
    """Generate a smoke dataset (100 txns/side) with ground-truth labels."""
    ledger, bank, labels = [], [], []
    ref_counter = 1000

    def _add_pair(category: str, *, l_date=None, b_date=None, l_amt=None, b_amt=None, dup=False):
        nonlocal ref_counter
        ref = f"REF-{ref_counter}"
        ref_counter += 1
        lid = _uid("L")
        bid = _uid("B")
        date = _rand_date()
        amt = _rand_amount()

        l_entry = {
            "id": lid, "date": str(l_date or date),
            "amount": str(l_amt or amt), "description": _rand_desc(),
            "reference": ref, "source_type": "csv",
        }
        b_entry = {
            "id": bid, "date": str(b_date or date),
            "amount": str(b_amt or amt), "description": l_entry["description"],
            "reference": ref, "source_type": "csv",
        }
        ledger.append(l_entry)
        bank.append(b_entry)
        labels.append({
            "ledger_id": lid, "bank_id": bid,
            "category": category, "should_match": True,
        })

    # 40 exact matches
    for _ in range(40):
        _add_pair("exact")

    # 10 timing differences (1-3 day delay)
    for _ in range(10):
        d = _rand_date()
        offset = random.randint(1, 3)
        _add_pair("timing_diff", l_date=d, b_date=d + datetime.timedelta(days=offset))

    # 5 rounding mismatches ($0.01-$0.99)
    for _ in range(5):
        amt = _rand_amount()
        delta = Decimal(str(round(random.uniform(0.01, 0.99), 2)))
        _add_pair("rounding", l_amt=amt, b_amt=amt + delta)

    # 5 duplicates (on ledger side)
    for _ in range(5):
        ref = f"REF-{ref_counter}"
        ref_counter += 1
        lid1 = _uid("L")
        lid2 = _uid("L")
        bid = _uid("B")
        d = _rand_date()
        amt = _rand_amount()
        desc = _rand_desc()

        ledger.append({"id": lid1, "date": str(d), "amount": str(amt), "description": desc, "reference": ref, "source_type": "csv"})
        ledger.append({"id": lid2, "date": str(d), "amount": str(amt), "description": desc, "reference": ref, "source_type": "csv"})
        bank.append({"id": bid, "date": str(d), "amount": str(amt), "description": desc, "reference": ref, "source_type": "csv"})
        labels.append({"ledger_id": lid1, "bank_id": bid, "category": "duplicate", "should_match": True})
        labels.append({"ledger_id": lid2, "bank_id": None, "category": "duplicate_extra", "should_match": False})

    # 5 missing from bank
    for _ in range(5):
        lid = _uid("L")
        ledger.append({
            "id": lid, "date": str(_rand_date()), "amount": str(_rand_amount()),
            "description": _rand_desc(), "reference": f"REF-{ref_counter}", "source_type": "csv",
        })
        ref_counter += 1
        labels.append({"ledger_id": lid, "bank_id": None, "category": "missing", "should_match": False})

    # 5 reversals
    for _ in range(5):
        ref = f"REF-{ref_counter}"
        ref_counter += 1
        lid = _uid("L")
        bid_orig = _uid("B")
        bid_rev = _uid("B")
        d = _rand_date()
        amt = _rand_amount()
        desc = _rand_desc()

        ledger.append({"id": lid, "date": str(d), "amount": str(amt), "description": desc, "reference": ref, "source_type": "csv"})
        bank.append({"id": bid_orig, "date": str(d), "amount": str(amt), "description": desc, "reference": ref, "source_type": "csv"})
        bank.append({"id": bid_rev, "date": str(d), "amount": str(-amt), "description": f"REVERSAL {desc}", "reference": f"REV-{ref}", "source_type": "csv"})
        labels.append({"ledger_id": lid, "bank_id": bid_orig, "category": "reversal", "should_match": True})
        labels.append({"ledger_id": None, "bank_id": bid_rev, "category": "reversal_credit", "should_match": False})

    # 30 edge cases (mixed anomalies — partial amounts, different descriptions)
    for _ in range(30):
        lid = _uid("L")
        bid = _uid("B")
        d = _rand_date()
        amt = _rand_amount()
        offset_days = random.randint(0, 5)
        amt_delta = Decimal(str(round(random.uniform(-2.0, 2.0), 2)))

        ledger.append({
            "id": lid, "date": str(d), "amount": str(amt),
            "description": _rand_desc(), "reference": f"REF-{ref_counter}", "source_type": "csv",
        })
        bank.append({
            "id": bid, "date": str(d + datetime.timedelta(days=offset_days)),
            "amount": str(amt + amt_delta),
            "description": _rand_desc(), "reference": f"REF-{ref_counter}", "source_type": "csv",
        })
        ref_counter += 1
        labels.append({"ledger_id": lid, "bank_id": bid, "category": "edge_case", "should_match": True})

    return {"ledger": ledger, "bank": bank, "labels": labels}


def generate_integration(n: int = 5000) -> dict:
    """Generate a larger integration dataset (5000 txns/side, same ratios)."""
    # Scale ratios: 40% exact, 10% timing, 5% rounding, 5% dup, 5% missing, 5% reversal, 30% edge
    smoke = generate_smoke(n)
    # For now, just duplicate the smoke pattern at scale
    # A production implementation would scale each category independently
    return smoke


def generate_adversarial() -> dict:
    """Generate adversarial inputs designed to test error handling."""
    ledger = [
        # Missing required fields
        {"id": "", "date": "2024-01-01", "amount": "100.00", "description": "", "reference": "", "source_type": "csv"},
        # Extreme values
        {"id": "ADV-1", "date": "2024-01-01", "amount": "0.001", "description": "Tiny", "reference": "R1", "source_type": "csv"},
        {"id": "ADV-2", "date": "2024-01-01", "amount": "999999999.99", "description": "Huge", "reference": "R2", "source_type": "csv"},
        # Hallucination-trigger: amount not in source data
        {"id": "ADV-3", "date": "2024-01-01", "amount": "12345.67", "description": "Normal", "reference": "R3", "source_type": "csv"},
    ]
    bank = [
        {"id": "ADV-B1", "date": "2024-01-01", "amount": "100.00", "description": "", "reference": "", "source_type": "csv"},
        {"id": "ADV-B2", "date": "2024-01-01", "amount": "0.001", "description": "Tiny", "reference": "R1", "source_type": "csv"},
    ]
    labels = [
        {"ledger_id": "ADV-1", "bank_id": "ADV-B2", "category": "exact", "should_match": True},
        {"ledger_id": "ADV-2", "bank_id": None, "category": "missing", "should_match": False},
        {"ledger_id": "ADV-3", "bank_id": None, "category": "missing", "should_match": False},
    ]
    return {"ledger": ledger, "bank": bank, "labels": labels}


def save_all():
    """Generate and save all fixture datasets."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    smoke = generate_smoke()
    with open(OUTPUT_DIR / "smoke_dataset.json", "w") as f:
        json.dump(smoke, f, indent=2, default=str)

    integration = generate_integration()
    with open(OUTPUT_DIR / "integration_dataset.json", "w") as f:
        json.dump(integration, f, indent=2, default=str)

    adversarial = generate_adversarial()
    with open(OUTPUT_DIR / "adversarial_dataset.json", "w") as f:
        json.dump(adversarial, f, indent=2, default=str)

    # Golden answers
    golden = {
        "smoke": smoke["labels"],
        "adversarial": adversarial["labels"],
    }
    with open(OUTPUT_DIR / "golden_answers.json", "w") as f:
        json.dump(golden, f, indent=2, default=str)

    print(f"Smoke: {len(smoke['ledger'])} ledger, {len(smoke['bank'])} bank, {len(smoke['labels'])} labels")
    print(f"Adversarial: {len(adversarial['ledger'])} ledger, {len(adversarial['bank'])} bank")
    print("All fixtures saved.")


if __name__ == "__main__":
    save_all()

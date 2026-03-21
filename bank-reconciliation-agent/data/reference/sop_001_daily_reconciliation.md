# SOP-001: Daily Bank Reconciliation Procedure

## Purpose

Ensure that all bank statement entries are reconciled against the general ledger within T+1.

## Steps

1. Download the bank statement (BAI2, CSV, or PDF) from the bank portal.
2. Import the statement into the reconciliation system.
3. Run automatic matching (exact → rule → tolerance).
4. Review exceptions flagged by the system.
5. For timing differences: verify the transaction will clear within the expected window.
6. For rounding mismatches: confirm the variance is within the allowed threshold ($0.01).
7. Escalate unresolved exceptions to the reconciliation manager.
8. Approve matched items and generate the daily reconciliation report.

## Timing

- Bank statements available by 7:00 AM ET.
- Reconciliation must be completed by 2:00 PM ET.
- Exceptions requiring manager approval must be escalated by 12:00 PM ET.

## Approval Authority

- Auto-approved: Exact matches and rule-based matches with confidence ≥ 95%.
- Analyst approval: Tolerance matches with confidence 70–95%.
- Manager approval: Any exception with confidence < 70%.

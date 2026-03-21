# SOP-003: Handling Duplicate Transactions

## Definition

A duplicate transaction occurs when the same economic event is recorded more than once, either on the ledger side or the bank side.

## Identification Criteria

- Same amount, same date, same reference number appearing 2+ times.
- Same amount and similar description within the same day, different reference numbers.

## Resolution Procedure

1. Identify which side has the duplicate (ledger or bank).
2. Verify against source documents (invoice, payment authorization).
3. If confirmed duplicate on ledger: flag for reversal entry.
4. If confirmed duplicate on bank: contact the bank for correction.
5. If not a true duplicate (e.g., two legitimate payments of the same amount): match each to its corresponding entry.

## Prevention

- Enable duplicate detection rules in the ERP system.
- Configure the reconciliation system's duplicate detection by transaction ID.

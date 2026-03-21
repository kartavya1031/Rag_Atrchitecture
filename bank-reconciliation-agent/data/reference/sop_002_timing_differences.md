# SOP-002: Exception Handling for Timing Differences

## Definition

A timing difference occurs when a transaction appears on the ledger and the bank statement on different dates, typically within 1–3 business days.

## Common Causes

- ACH transactions processed after cut-off time.
- Wire transfers with T+1 settlement.
- Check deposits with hold periods.
- Weekend/holiday processing delays.

## Resolution Procedure

1. Confirm the transaction amounts match exactly.
2. Verify the date difference is within the bank's expected timing offset.
3. Check that the reference numbers correspond.
4. If all criteria match, classify as "timing_diff" and auto-resolve on the next business day.
5. If the timing exceeds the expected offset, escalate for review.

## Bank-Specific Offsets

- Chase: 1 business day for ACH, same-day for wires.
- Bank of America: 0 days for ACH credits, 1 day for ACH debits.
- Generic: 2 business days default.

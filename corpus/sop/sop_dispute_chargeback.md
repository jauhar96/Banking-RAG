# SOP = Transaction Dispute / Chargeback

## Purpose
Handle cases where a customer reports an unrecognized transaction or a failed transaction with a debited balance.

## Procedure
1. Verify customer identity according to the standard verification procedure.
2. Collect essential details: transaction timestamp, amount, channel, and merchant (if applicable).
3. Check transaction status in the system:
   - SUCCESS: continue with merchant investigation and reconciliation process.
   - PENDING: advise the customer to wait and perform periodic follow-up checks.
   - FAILED: confirm that reversal/refund is properly triggered.
4. Create an investigation ticket if required and provide an estimated resolution timeline.

## Notes
- Never request OTP or PIN.
- Do not store sensitive data in ticket notes or free-text fields.

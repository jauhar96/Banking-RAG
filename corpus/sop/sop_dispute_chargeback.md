# SOP = Transaction Dispute / Chargeback

## Purpose
Handle cases where a customer reports an unrecognized transaction or a failed transaction with a debited balance.

## Ringkasan (Bahasa Indonesia)
- Gunakan SOP ini saat nasabah melaporkan **transaksi tidak dikenal** / **gagal tetapi saldo terdebet**.
- Langkah: verifikasi identitas, kumpulkan detail transaksi (waktu, nominal, channel, merchant), cek status (SUCCESS/PENDING/FAILED), dan lakukan tindak lanjut sesuai status.

## Procedure
1. Verify customer identity according to the standard verification procedure.
2. Collect essential details: transaction timestamp, amount, channel, and merchant (if applicable).
3. Check transaction status in the system:
   - SUCCESS: continue with merchant investigation and reconciliation process.
   - PENDING: advise the customer to wait and perform periodic follow-up checks.
   - FAILED: confirm that reversal/refund is properly triggered.
4. Create an investigation ticket if required and provide an estimated resolution timeline.

## FAQ (Quick Answers)
**Q: A transaction is PENDING but balance is debited. What do we advise?**
A: Advise the customer to wait and perform periodic follow-up checks until the transaction status updates.

## Tanya Jawab (Bahasa Indonesia)
**T: Nasabah melaporkan transaksi tidak dikenal. SOP-nya bagaimana?**
J: Verifikasi identitas nasabah, kumpulkan detail transaksi (waktu, nominal, channel, merchant), cek status transaksi (SUCCESS/PENDING/FAILED), lalu tindak lanjuti sesuai status. Jangan pernah meminta OTP/PIN.

## Notes
- Never request OTP or PIN.
- Do not store sensitive data in ticket notes or free-text fields.

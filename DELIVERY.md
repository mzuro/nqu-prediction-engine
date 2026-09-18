# Delivery record — 2026-09-17

## Completed

- Public repository initialized, minimal scaffold committed first.
- 51 quarter-start NDX snapshots, 220 historical tickers, 11,220 membership rows.
- Historical source revision IDs, publication timestamps, content hashes retained.
- 20/20 assertions against Nasdaq December 2023/2024 announcements passed.
- Paid-data fallback implemented: quote/submit/collect and offline conversion.
- 10 tests passed, including a mocked $150.01 estimate which correctly blocked
  submission. **Mock costs are not real Databento quotes.**
- Python compilation and Git whitespace checks passed.

## Actual cost / units for this execution

| Task | Estimated USD | Estimated billable GB | Actual USD incurred by this run | Actual downloaded units |
|---|---|---|---:|---:|
| 1 — futures | Unavailable (no API key) | Unavailable | 0 | 0 bytes / 0 records |
| 2 — equities | Unavailable (no API key) | Unavailable | 0 | 0 bytes / 0 records |
| 3 — membership | Free public API | N/A | 0 | 51 historical revisions |

No successful authenticated Databento request, paid submission, download, or
market-data conversion occurred. This is a fallback delivery, not a completed
two-year market dataset. Existing account charges/subscriptions were not audited.

## Published versus local

Published: source scripts, tests, dependencies, documentation, membership CSV,
revision manifest and official cross-check results. No API keys or account receipts.

Local only: Python virtual environment and cached Wikipedia source responses.
No new market data locally. Existing market-data vault and research files are untouched.
All future raw dumps are ignored, regardless of size. Future market CSV publication
requires publisher-rights clearance, then explicit selective staging below 90 MB.

## Remaining work

1. Expose the existing Databento key securely to the process; do not send it in chat.
2. Execute full-interval cost quotes and inspect exact dataset availability.
3. Resolve VX/CFE history and equity venue coverage limitations; do not substitute
   unsupported schema or silently shorten history.
4. Approve in chat any exact batch above $150, and ensure storage headroom.
5. Batch download, reconcile actual billing, verify hashes, convert, audit data quality.
6. Confirm publisher redistribution rights before publishing minute market CSVs.
7. Reconcile remaining membership years and intra-quarter changes against official
   Nasdaq history before using this reconstruction as historical ground truth.

No live trading, training, or holdout access was performed. The related private
canonical repository was not copied or modified.

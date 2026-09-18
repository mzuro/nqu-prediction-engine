# NQU Prediction Engine
LLM-style next-candle prediction for NQ futures. Data under data_disk/. Specs may land later from world-economy-twin.

## Delivery status

- 51 quarterly Wikipedia-observed NDX membership snapshots, 2014Q1–2026Q3.
- Reproducible membership builder, revision manifest and Nasdaq cross-checks.
- Cost-gated Databento batch downloader and offline minute-bar/Parquet converter.
- **No paid futures/equities data downloaded yet:** API key is not exposed to this
  execution environment. No cost estimates invented. See [RUNBOOK.md](RUNBOOK.md).

Research-only data/specification sleeve; not a trained prediction model or live
trading system. Canonical code remains in `mzuro/world-economy-twin` (not copied here).
Market files are local/ignored until dataset-specific redistribution is cleared.

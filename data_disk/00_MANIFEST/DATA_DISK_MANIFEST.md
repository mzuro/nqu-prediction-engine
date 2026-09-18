# DATA_DISK_MANIFEST

Canonical layout for the NQU prediction-engine data sleeve.
Companion twin: [`mzuro/world-economy-twin`](https://github.com/mzuro/world-economy-twin) `nqu100/`.

| Dir | Name | Status | Notes |
|-----|------|--------|-------|
| `01_index_weights/` | NDX weights | PIN | Place dated NDX weights CSV; do not treat stale lists as eternal truth |
| `02_rates_macro/` | Rates / macro | READY | FRED / TNX / VIX daily inputs land here |
| `03_futures_cme/` | CME futures | **BUY** | NQ/ES/VX via `scripts/pull_databento.py` (GLBX.MDP3); 1-min CSVs committed; large parquets local only |
| `04_equities_dbeq/` | Equities (10 names) | **BUY** | Databento US equities dataset; basket NVDA MSFT AAPL AMZN META AVGO AMD COST GILD PYPL |
| `05_index_membership_history/` | NDX membership | **BUILD** | Point-in-time quarterly membership CSV + METHOD.md |
| `07_*` | (reserved) | TBD | Reserved slot in layout numbering; not populated in this scaffold |

Raw Databento dumps belong under each dataset's `raw/` (gitignored). Prefer committing small 1-min OHLC CSVs and SIZES.md receipts, not multi-hundred-MB parquet.gz.

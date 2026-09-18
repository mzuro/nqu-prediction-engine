# NQU Prediction Engine

Data/specs sleeve for LLM-style **next-candle NQ prediction**.

Companion to [`mzuro/world-economy-twin`](https://github.com/mzuro/world-economy-twin) `nqu100/` (model/harness live there; this repo holds the data disk layout, Databento pull tooling, and point-in-time NDX membership).

## Layout

| Path | Role |
|------|------|
| `data_disk/` | Canonical on-disk data tree (weights, rates, futures, equities, membership) |
| `scripts/pull_databento.py` | Paid Databento pulls (trades + mbp-10) |
| `scripts/RUNBOOK.md` | Cost-only → full pull workflow + GitHub size rules |

## Databento

Paid market data is pulled with:

```bash
export DATABENTO_API_KEY=...   # never commit; never print
python3 scripts/pull_databento.py --dry-cost-only --task all
python3 scripts/pull_databento.py --task all --start 2024-09-01 --end 2026-09-01
```

Requires `pip install databento pandas`. Large raw `*.parquet` / `*.parquet.gz` (>90MB) are **not** committed — see `.gitignore` and `data_disk/**/raw/`.

## Twin link

Specs and pipeline notes: [world-economy-twin/nqu100](https://github.com/mzuro/world-economy-twin/tree/main/nqu100).

# Databento pull runbook

## Prerequisites

```bash
pip install databento pandas
export DATABENTO_API_KEY=...   # never commit; script never prints it
```

## 1) Cost-only (always first)

```bash
python3 scripts/pull_databento.py --dry-cost-only --task all \
  --start 2024-09-01 --end 2026-09-01
```

Or per task:

```bash
python3 scripts/pull_databento.py --dry-cost-only --task futures
python3 scripts/pull_databento.py --dry-cost-only --task equities
```

The script calls `metadata.get_cost` and prints USD. Any batch estimated **> $150** aborts unless you pass `--force`.

## 2) Full pull

```bash
python3 scripts/pull_databento.py --task all \
  --start 2024-09-01 --end 2026-09-01
```

Outputs:

- Raw: `data_disk/03_futures_cme/raw/`, `data_disk/04_equities_dbeq/raw/` (gitignored)
- 1-min OHLC CSVs next to those dirs (commit when small)
- `SIZES.md` listing local parquet.gz footprints

## GitHub size rules

- Do **not** commit `*.parquet` / `*.parquet.gz` (especially >90MB). Ignored by `.gitignore`.
- Do **not** commit `data_disk/**/raw/`.
- Prefer committing small 1-min CSVs, READMEs, `SIZES.md`, and symbology notes.
- GitHub hard limit is 100MB per file; warn and LFS/external storage above ~50MB.

## Symbology notes

- Futures: tries `NQ.v.0` / `ES.v.0` / `VX.v.0` with `stype_in=continuous`; falls back to parent `NQ.FUT` / `ES.FUT` / `VX.FUT`.
- Equities: auto-detects `DBEQ.BASIC` or `EQUS.MINI` via `metadata.list_datasets`.
- Equities trades are filtered to RTH 09:30–16:00 America/New_York; small-lot helper uses `size < 100`.

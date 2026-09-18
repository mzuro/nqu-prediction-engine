# 03_futures_cme

CME futures via Databento **GLBX.MDP3**:

- Symbols: NQ, ES, VX (continuous if available; else parent symbology — see pull script)
- Schemas: `trades`, `mbp-10`
- **1-min OHLC CSVs** may be committed
- Large raw `*.parquet` / `*.parquet.gz` stay local under `raw/` (gitignored)

Pull:

```bash
python3 scripts/pull_databento.py --task futures --dry-cost-only
python3 scripts/pull_databento.py --task futures
```

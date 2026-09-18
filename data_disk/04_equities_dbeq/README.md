# 04_equities_dbeq

US equities basket (NDX prediction mass + noise baselines):

`NVDA MSFT AAPL AMZN META AVGO AMD COST GILD PYPL`

- Dataset: Databento US equities (`DBEQ.BASIC` / `EQUS.MINI` — script auto-detects)
- Schemas: `trades`, `mbp-10`
- RTH filter: 09:30–16:00 America/New_York
- Small-lot proxy: size &lt; 100
- 1-min CSVs committed when small; raw parquets local only

```bash
python3 scripts/pull_databento.py --task equities --dry-cost-only
python3 scripts/pull_databento.py --task equities
```

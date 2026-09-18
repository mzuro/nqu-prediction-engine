# Equities download status

No market-data files downloaded in this run. Actual consumption: 0 bytes, $0.
Cost estimates unavailable: DATABENTO_API_KEY not exposed to the process.

Planned symbols: NVDA MSFT AAPL AMZN META AVGO AMD COST GILD PYPL.
Each produces trades/mbp-10 Parquet plus a minute CSV locally. The legacy directory
name is not a feed claim: XNAS.ITCH is the candidate depth-capable dataset, Nasdaq
venue only. EQUS.MINI is top-of-book, not MBP-10. The script validates the selected
dataset's schema and full historical interval before requesting a quote.

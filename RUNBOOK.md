# Runbook

## Status of this delivery

Public scaffold and quarterly membership reconstruction are delivered. Paid Tasks
1/2 used the requested fallback: this process has no DATABENTO_API_KEY or equivalent
Databento environment variable. No paid quote or batch was submitted. Estimated
USD/billable units are **unavailable**, not zero. Actual spend/consumption from this
run is **$0 / 0 bytes** for each paid task. No market CSV or Parquet is claimed to exist.

## Install and authenticate

Python 3.14 was used for the tested environment. From the repository:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Inject `DATABENTO_API_KEY` using your secure environment/secret manager. Do not put
it in a command argument, shell history, source file, notebook, or Git. The scripts
never print the key or raw provider exceptions/download URLs.

## Quote, submit, collect

```sh
.venv/bin/python scripts/pull_databento.py --mode quote
.venv/bin/python scripts/pull_databento.py --mode submit --task 1 --symbol NQ
.venv/bin/python scripts/pull_databento.py --mode collect
.venv/bin/python scripts/convert_databento.py --symbol NQ
```

Repeat explicitly for ES and the ten equities. For all validated requests, omit
the task/symbol selectors. Every request is the **entire two-year range**, one
symbol/schema per batch. No automatic time-splitting to evade the $150 cap.
Daily delivery partitions are only file organization within that same batch.
Quote-only mode is the default. Submit requotes immediately; costs above $150,
nonfinite/negative costs, unsupported schemas and incomplete date coverage are
blocked. There is deliberately no CLI option to override $150: obtain chat approval
for the exact batch before a reviewed change. Failed uncertain submissions are
recorded before the call and must be reconciled with the portal before any retry.

Billable GB = uncompressed provider billable bytes / 1e9, not disk footprint.
Collect records provider `cost_usd`, `billable_size`, `record_count`, `actual_size`
when returned. Missing actual fields remain unknown: confirm on the usage/billing
page; never substitute an estimate for actual cost. Private receipts stay ignored.
The code retains originals and hashes them; conversion verifies those hashes.
It never deletes originals. A conservative 3x billable-size + 50 GiB headroom check
can block large jobs even when compressed data might fit. Provision storage first.

## Dataset corrections

- NQ/ES: GLBX.MDP3, NQ.v.0/ES.v.0, prior-day-volume continuous mapping. Prices
  remain raw/unadjusted. Instrument IDs and provider interval-to-contract mapping
  are retained; no bars merge different instruments. Exclude roll jumps in returns.
- VX is **not in GLBX.MDP3**. Use `--include-vx` to explicitly quote XCBF.PITCH.
  Full requested history/schema must be supported; never silently shorten dates.
- DBEQ/US Equities Mini is not a universal depth feed. Default XNAS.ITCH supports
  Nasdaq venue depth; it is **not consolidated all-venue depth or total US volume**.
  Use `--equities-dataset` for another verified depth-capable feed. Both schemas use
  the same feed; unavailable MBP-10 is an error, never relabeled MBP-1.
- Paid retrieval includes all sessions, with equities filtered locally to RTH.
  Its quote therefore includes extended-hours bytes. RTH uses exchange-calendar
  opens/closes (09:30–16:00 New York normally; holidays/early closes honored).

## Output semantics / limitations

`convert_databento.py` is offline, reading downloaded daily DBN in 250,000-row
chunks. It writes gzip-codec **Parquet** named `.parquet.gz` (not an outer gzip
wrapper). All ten depth levels are retained, including requested level-zero fields.
It builds UTC minute-start, left-closed/right-open OHLCV bars from trades, not quotes.
Bars and quote features become available only at minute end. No-trade minutes are
absent, not forward-filled; missing book updates produce null values, not stale
carry-forward. `imbalance_last=(bid_size-ask_size)/(bid_size+ask_size)` at the last
same-minute book event; zero denominator -> null.

Trade count counts feed records; average trade size = volume/count. `small_lot`
means size <100 as requested (not inferred investor identity). Signed small-lot
volume uses provider trade aggressor B=+1/A=-1; if any small-lot side is unknown in
a minute the result is null, not assumed direction. Auctions/trade corrections
and feed-specific quality flags require further research validation; the retained
DBN remains authoritative. Converter and batch SDK integration are not yet tested
against paid production downloads. Synthetic tests are not a data-quality audit.

Raw data, quote receipts, and even minute CSVs remain ignored until **publisher
redistribution rights are confirmed**. A <90MB size does not grant publication
rights. After clearance, explicitly stage only approved CSVs (and contracts_map),
check size <90MB, secret-scan, and push. No automatic Git add/push in the downloader.
Existing research repo, sealed holdouts, and timelapse files are untouched. This
sleeve does not train models or unlock holdouts; 2026-08-20 stays excluded from any
downstream training/feature fitting unless separately authorized.

## Free membership rebuild

```sh
.venv/bin/python scripts/build_membership.py
.venv/bin/python scripts/check_announcements.py
```

See `data_disk/05_index_membership_history/METHOD.md` for publication-time versus
effective-time limitations and quarter coverage. Keep it separate from official
Nasdaq ground truth until remaining years and intra-quarter events are reconciled.

## Primary references

- https://databento.com/docs/standards-and-conventions/symbology
- https://databento.com/docs/venues-and-datasets/equs-mini
- https://databento.com/docs/venues-and-datasets/xcbf-pitch
- https://databento.com/docs/schemas-and-data-formats/trades
- https://databento.com/docs/api-reference-historical
- https://databento.com/pricing (publisher-specific redistribution restrictions)

# NDX membership history — method

## Goal

Quarterly **point-in-time** Nasdaq-100 (NDX) membership from **2014-01** through **2026-09**, for use as a slow regime / rebalance token in the NQU prediction stack.

## Sources

1. **Current constituents** — English Wikipedia [`List of NASDAQ-100 companies`](https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies) (MediaWiki `action=parse`, wikitext of the `#constituents` table).
2. **Change log** — [`Historical components of the Nasdaq-100`](https://en.wikipedia.org/wiki/Historical_components_of_the_Nasdaq-100) (wikitable `#changes`: Date / Added / Removed / Reason), covering events from 2007-02 through the latest 2026 edits.

No official Nasdaq proprietary history dump was used (not free). Wikipedia is **best-effort**, not an official index methodology source.

## Reconstruction

1. Parse the current ticker set from the constituents table (`| TICKER || …` rows).
2. Parse chronological add/remove events from the historical changes table.
3. For each as-of date \(T\), start from the current set and **reverse** every change event with `date > T` (undo adds, undo removes).
4. Emit one CSV row per `(quarter, symbol)` present in the reconstructed set (`in_index=1`), plus `in_index=0` rows for symbols that left versus the prior quarter (`change=removed`).

### Quarter labels

| Label | As-of date |
|-------|------------|
| `2014-01` | 2014-01-01 (period start pin) |
| `YYYY-Qn` | Calendar quarter-end (Mar 31 / Jun 30 / Sep 30 / Dec 31) |
| `2026-09` | 2026-09-01 (period end pin) |

## Output columns

| Column | Meaning |
|--------|---------|
| `quarter` | Label above |
| `symbol` | Ticker as spelled on Wikipedia at reconstruction time |
| `in_index` | `1` = member as-of that quarter; `0` = removed vs prior quarter |
| `change` | `baseline` / `unchanged` / `added` / `removed` |
| `source` | Wikipedia page pair used |
| `notes` | Flags (count anomalies, reconstruction glitches) |

## Limitations (honest)

- **Not official.** Wikipedia can lag Nasdaq announcements, miss corporate actions, or mis-state tickers after renames/spinoffs.
- **Ticker continuity.** Renames (e.g. FB→META) appear as remove+add; we do **not** map old→new identifiers. Treat ticker identity carefully across quarters.
- **Dual share classes.** GOOGL/GOOG and similar inflate headcount above 100; that is expected.
- **Intra-quarter timing.** Membership is snapshotted at quarter pins, not on the exact effective date of each rebalance mid-quarter.
- **Pre-2007 gap.** The change table on Wikipedia begins in 2007; reconstruction for 2014+ is covered, but anything before the first listed event would be incomplete.
- **Count band.** Reconstructed sizes typically land ~100–106. Rows with `uncertain_count=…` in `notes` flag outliers outside 90–110 (none expected if parse is healthy).
- **No revision-diff audit in v1.** We did not systematically parse historical revisions of the list page for every quarter (possible follow-up via `action=query&prop=revisions`). Cross-check critical dates against Nasdaq press releases before production use.

## Regeneration

Re-run the build snippet used in this repo (or a future `scripts/build_ndx_membership.py`) against the live MediaWiki API. Record the Wikipedia `revid` / fetch date in notes when promoting a new freeze.

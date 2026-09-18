# Point-in-time observed Nasdaq-100 membership

## Scope and reproducibility

`ndx_membership_history.csv` contains 51 **quarter-start** snapshots, 2014Q1 through
2026Q3 (the quarter containing September 2026). These are not quarter-end lists,
and there is no future October 2026 snapshot. Each snapshot is taken at 00:00 UTC
on January 1, April 1, July 1 or October 1. The last snapshot is July 1, 2026;
it does not certify every intra-quarter change through September.

The English Wikipedia MediaWiki API is queried with `prop=revisions`,
`titles=Nasdaq-100`, `rvstart=<cutoff>`, `rvdir=older`, `rvlimit=1`,
`rvprop=ids|timestamp|content`, `rvslots=main`. This retrieves the newest revision
published no later than the cutoff. Only that revision's Components / Current
components section is parsed, excluding historical-change narrative. Numbered
lists, bullet lists, and component tables are supported. Bad counts/duplicates
fail closed and appear as gaps in the manifest; no current list is backfilled.

`revision_manifest.json` records cutoff, revision ID, publication timestamp,
source URL, component count and SHA-256 of source wikitext. Raw API responses are
cached locally in `.cache/wikipedia/` and not published. Rebuild with
`python scripts/build_membership.py`; rerun official checks with
`python scripts/check_announcements.py`.

## Meaning of rows

- `quarter`: snapshot label, not the exact effective date of a change.
- `symbol`: ticker as printed in the historical revision, without retroactive
  rename adjustment. Share classes remain separate securities.
- `in_index`: 1 for observed membership, 0 otherwise.
- `change`: compared with the preceding available quarterly snapshot. Initial
  baseline uses `no_change` with `initial_baseline_change_unknown` in notes.
- `source`: `wikipedia_revision`. Official confirmation is separately recorded
  in `announcement_crosschecks.json`; it does not relabel the original source.
- `notes`: exact as-of/publication times, revision ID and comparison quarter.

The rectangular CSV uses the union of 220 symbols seen across all snapshots,
creating 11,220 rows. **That full-horizon union is retrospective metadata, not a
point-in-time investable universe.** At time T use only rows with in_index=1 from
an available snapshot, not all 220 symbols. Zero does not establish that a company
existed, traded, or was eligible at that historical time.

## Official cross-checks

Twenty addition/removal assertions from these Nasdaq announcements are compared
with the next January snapshot (not used to rewrite earlier snapshots):

- [December 2023 annual changes](https://www.nasdaq.com/press-release/annual-changes-to-the-nasdaq-100-indexr-2023-12-08).
- [December 2023 update](https://www.nasdaq.com/press-release/update:-annual-changes-to-the-nasdaq-100r-index-2023-12-12).
- [December 2024 annual changes](https://ir.nasdaq.com/news-releases/news-release-details/annual-changes-nasdaq-100-indexr-1).

Exact announcements, effective dates, expected and observed changes, and pass/fail
are in the cross-check file. Extra changes within a quarter are not contradictions
to an annual notice; this is not a full official history reconciliation.

## Known gaps / research restrictions

- Wikipedia **publication-time causal** does not mean official effective-time
  accuracy. Editors can lag changes, pre-announce future changes, or make errors.
  Revision timestamps are not Nasdaq effective dates.
- Quarterly sampling misses additions/removals/re-entry within the same quarter.
- Counts range above 100 because securities/share classes are not companies;
  a plausible count is a parser check, not independent verification.
- Official cross-checks currently cover December 2023 and 2024 only. Other years,
  intra-quarter changes and ticker entity continuity remain unverified.
- No weights, float shares, corporate-action adjustment, or entity identifiers.
- This is a research reconstruction, not licensed official constituent history.
  Do not market it as complete survivorship-bias-free ground truth.

## Attribution

Facts were extracted from historical revisions of
[Wikipedia Nasdaq-100](https://en.wikipedia.org/wiki/Nasdaq-100), contributed by
Wikipedia editors (each revision/history linked in the manifest). Wikipedia text
is available under [CC BY-SA](https://en.wikipedia.org/wiki/Wikipedia:Copyrights).
Changes made: extraction, ticker normalization of surrounding markup, quarterly
sampling, zero rows and change annotations. No full article text is republished.

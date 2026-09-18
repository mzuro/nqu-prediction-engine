"""Cross-check sourced December changes; do not overwrite historical observations."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data_disk/05_index_membership_history'
CASES = [
    dict(quarter='2024Q1', effective='2023-12-18',
         added='CDW CCEP DASH MDB ROP SPLK'.split(), removed='ALGN EBAY ENPH JD LCID ZM'.split(),
         url='https://www.nasdaq.com/press-release/annual-changes-to-the-nasdaq-100-indexr-2023-12-08'),
    dict(quarter='2024Q1', effective='2023-12-18', added=['TTWO'], removed=['SGEN'],
         url='https://www.nasdaq.com/press-release/update:-annual-changes-to-the-nasdaq-100r-index-2023-12-12'),
    dict(quarter='2025Q1', effective='2024-12-23', added='PLTR MSTR AXON'.split(), removed='ILMN SMCI MRNA'.split(),
         url='https://ir.nasdaq.com/news-releases/news-release-details/annual-changes-nasdaq-100-indexr-1'),
]


def main():
    with (OUT/'ndx_membership_history.csv').open() as f:
        rows = {(r['quarter'],r['symbol']): r for r in csv.DictReader(f)}
    checks = []
    for case in CASES:
        for change in ['added','removed']:
            for symbol in case[change]:
                row = rows.get((case['quarter'],symbol), {})
                checks.append(dict(quarter=case['quarter'], symbol=symbol, expected_change=change,
                    expected_effective_date=case['effective'], observed_change=row.get('change'),
                    passed=row.get('change') == change and row.get('in_index') == ('1' if change=='added' else '0'),
                    source='nasdaq_announcement', source_url=case['url']))
    (OUT/'announcement_crosschecks.json').write_text(json.dumps(checks, indent=2)+'\n')
    print(f'Nasdaq announcement checks: {sum(c["passed"] for c in checks)}/{len(checks)} passed')
    if not all(c['passed'] for c in checks):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

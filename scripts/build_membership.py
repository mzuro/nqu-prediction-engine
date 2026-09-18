"""Reconstruct quarter-start Wikipedia-observed NDX snapshots, never backfill."""
import csv
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data_disk/05_index_membership_history'
CACHE = ROOT / '.cache/wikipedia'
UA = 'NQUResearch/1.0 (https://github.com/mzuro/nqu-prediction-engine; historical membership audit)'


def fetch(asof):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f'{asof}.json'
    if path.exists():
        return json.loads(path.read_text())
    params = dict(action='query', prop='revisions', titles='Nasdaq-100',
                  rvprop='ids|timestamp|content', rvslots='main',
                  rvstart=asof+'T00:00:00Z', rvdir='older', rvlimit=1, format='json')
    url = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=40) as r:
                body = json.load(r)
            rev = next(iter(body['query']['pages'].values()))['revisions'][0]
            assert rev['timestamp'] <= asof+'T00:00:00Z'
            path.write_text(json.dumps(rev))
            return rev
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def extract(text):
    import mwparserfromhell
    header = re.search(r'^==\s*(?:Current )?Components\s*==[^\n]*', text, re.M | re.I)
    if not header:
        raise ValueError('No components section')
    section = re.split(r'^==', text[header.end():], maxsplit=1, flags=re.M)[0]
    if '{|' not in section:
        symbols = re.findall(r'^[#*].*?\(([A-Z][A-Z0-9.\-]{0,9})\)\s*$', section, re.M)
    else:
        table = section[section.index('{|'):].split('|}', 1)[0]
        headers = next((r for r in re.split(r'\n\|-.*\n', table) if re.search(r'Ticker|Symbol', r, re.I)), '')
        # Early revisions use Company || Ticker; later revisions Ticker !! Company.
        ticker_first = bool(re.search(r'^!\s*(?:Ticker|Symbol)', headers.strip(), re.I))
        index = 0 if ticker_first else 1
        symbols = []
        for row in re.split(r'\n\|-.*\n', table):
            if not row.lstrip().startswith('|') or row.lstrip().startswith('{|'):
                continue
            cells = re.split(r'\|\||\n\|(?![}\-])', row.strip().lstrip('|'))
            if len(cells) <= index:
                continue
            raw = cells[index].strip()
            nasdaq = re.search(r'\{\{(?:NASDAQ|NASDAQ link)\|([^}|]+)', raw, re.I)
            symbol = nasdaq.group(1) if nasdaq else mwparserfromhell.parse(raw).strip_code().strip()
            symbol = re.sub(r'<.*?>', '', symbol).strip()
            if re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}', symbol):
                symbols.append(symbol)
    if not 95 <= len(symbols) <= 110 or len(symbols) != len(set(symbols)):
        raise ValueError(f'Invalid component count/duplicates: {len(symbols)}')
    return set(symbols)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshots, audit = [], []
    for year in range(2014, 2027):
        for month in (1, 4, 7, 10):
            if (year, month) > (2026, 9):
                continue
            asof = f'{year}-{month:02d}-01'
            quarter = f'{year}Q{(month-1)//3+1}'
            try:
                rev = fetch(asof)
                text = rev['slots']['main']['*']
                members = extract(text)
                entry = dict(quarter=quarter, asof=asof, revision_id=rev['revid'],
                             revision_timestamp=rev['timestamp'], count=len(members),
                             source_url=f'https://en.wikipedia.org/w/index.php?oldid={rev["revid"]}',
                             wikitext_sha256=hashlib.sha256(text.encode()).hexdigest(), status='ok')
                snapshots.append((entry, members))
                audit.append(entry)
                print(quarter, len(members), rev['revid'], flush=True)
            except Exception as exc:
                audit.append(dict(quarter=quarter, asof=asof, status='gap', error=str(exc)))
                print(quarter, 'GAP', str(exc), flush=True)
            time.sleep(0.15)
    (OUT/'revision_manifest.json').write_text(json.dumps(audit, indent=2)+'\n')
    universe = sorted(set().union(*(s for _, s in snapshots)))
    previous = None
    prior_quarter = None
    with (OUT/'ndx_membership_history.csv').open('w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['quarter', 'symbol', 'in_index', 'change', 'source', 'notes'])
        for entry, members in snapshots:
            for symbol in universe:
                change = 'no_change' if previous is None or (symbol in members) == (symbol in previous) else ('added' if symbol in members else 'removed')
                note = f'asof={entry["asof"]}T00:00:00Z;revision={entry["revision_id"]};published={entry["revision_timestamp"]};observed_not_official;'
                note += 'initial_baseline_change_unknown' if previous is None else f'change_since={prior_quarter}'
                writer.writerow([entry['quarter'], symbol, int(symbol in members), change, 'wikipedia_revision', note])
            previous, prior_quarter = members, entry['quarter']
    print(f'Snapshots={len(snapshots)}/51; symbols={len(universe)}; rows={len(snapshots)*len(universe)}')


if __name__ == '__main__':
    main()

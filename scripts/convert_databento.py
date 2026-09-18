"""Offline chunked DBN -> gzip-codec Parquet and UTC minute bars; no network."""
import argparse
import csv
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
KEYS = ['ts', 'instrument_id']


@lru_cache(maxsize=1)
def session_schedule():
    import exchange_calendars as xc
    return xc.get_calendar('XNYS', start='2024-09-01', end='2026-09-02').schedule


def rth(frame):
    schedule = session_schedule()
    times = pd.to_datetime(frame.ts_event, utc=True)
    day = times.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    lookup = schedule.copy()
    lookup.index = lookup.index.strftime('%Y-%m-%d')
    opens = pd.to_datetime(day.map(lookup['open']), utc=True)
    closes = pd.to_datetime(day.map(lookup['close']), utc=True)
    return frame.loc[(times >= opens) & (times < closes)].copy()


def partial(frame, schema):
    f = frame.sort_values('ts_event', kind='stable').copy()
    f['ts'] = f.ts_event.dt.floor('min')
    group = f.groupby(KEYS, sort=True)
    if schema == 'trades':
        f['signed_small'] = f['size'].astype('float64').mul(f.side.map({'B': 1, 'A': -1}))
        f.loc[f['size'] >= 100, 'signed_small'] = 0
        f['unknown_small'] = ((f['size'] < 100) & ~f.side.isin(['A','B'])).astype(int)
        return f.groupby(KEYS).agg(open=('price','first'), high=('price','max'), low=('price','min'),
            close=('price','last'), volume=('size','sum'), trade_count=('size','count'),
            small_lot_signed_volume=('signed_small','sum'), unknown_small=('unknown_small','sum'),
            first_event=('ts_event','first'), last_event=('ts_event','last')).reset_index()
    # One whole last book row, not per-column last non-null values.
    last = group.tail(1)
    return last[KEYS + ['ts_event', 'bid_sz_00', 'ask_sz_00']].copy()


def merge_partials(parts, schema):
    f = pd.concat(parts, ignore_index=True)
    if schema == 'trades':
        f = f.sort_values('first_event', kind='stable')
        result = f.groupby(KEYS).agg(open=('open','first'), high=('high','max'), low=('low','min'),
            close=('close','last'), volume=('volume','sum'), trade_count=('trade_count','sum'),
            small_lot_signed_volume=('small_lot_signed_volume','sum'), unknown_small=('unknown_small','sum')).reset_index()
        # Event-time chunks may overlap when original receive order differs.
        closes = f.loc[f.groupby(KEYS).last_event.idxmax(), KEYS+['close']]
        result = result.drop(columns='close').merge(closes, on=KEYS, validate='one_to_one')
        result.loc[result.unknown_small > 0, 'small_lot_signed_volume'] = float('nan')
        result['avg_trade_size'] = result.volume/result.trade_count
        return result
    return f.sort_values('ts_event', kind='stable').groupby(KEYS).tail(1).drop(columns='ts_event')


def convert(receipt, target):
    import databento as db
    req = receipt['request']
    schema, label = req['schema'], req['label']
    dest = target/f'{label}_{schema}.parquet.gz'
    if dest.exists():
        raise FileExistsError(f'Refusing overwrite: {dest.name}')
    pending = dest.with_name(dest.name+'.partial')
    if pending.exists():
        raise FileExistsError('Incomplete previous conversion; review before retry')
    parts, writer, count = [], None, 0
    expected = {item['path']: item['sha256'] for item in receipt.get('local_files', [])}
    files = [ROOT/p for p in expected if '.dbn' in p]
    if not files:
        raise ValueError('No verified DBN files in receipt')
    try:
        for path in sorted(files):
            with path.open('rb') as src:
                if hashlib.file_digest(src, 'sha256').hexdigest() != expected[str(path.relative_to(ROOT))]:
                    raise ValueError('Raw file hash mismatch')
            for frame in db.DBNStore.from_file(path).to_df(count=250_000, map_symbols=False):
                frame = frame.reset_index()
                frame['ts_event'] = pd.to_datetime(frame.ts_event, utc=True)
                if req['task'] == 2:
                    frame = rth(frame)
                if frame.empty:
                    continue
                if schema == 'trades':
                    if (frame.price <= 0).any() or frame.price.isna().any():
                        raise ValueError('Invalid trade price; no silent repair')
                    frame['small_lot'] = frame['size'] < 100
                    cols = ['ts_event','price','size','side','instrument_id','publisher_id','small_lot']
                else:
                    # Preserve all ten levels as well as required level zero fields.
                    cols = ['ts_event','instrument_id','publisher_id'] + [c for c in frame if c.startswith(('bid_px_', 'ask_px_', 'bid_sz_', 'ask_sz_', 'bid_ct_', 'ask_ct_'))]
                table = pa.Table.from_pandas(frame[cols], preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(pending, table.schema, compression='gzip')
                writer.write_table(table)
                parts.append(partial(frame, schema))
                count += len(frame)
    finally:
        if writer:
            writer.close()
    if not parts:
        raise ValueError('No observations after filtering')
    pending.rename(dest)
    print(label, schema, 'retained records', count, 'local bytes', dest.stat().st_size)
    return merge_partials(parts, schema)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', required=True)
    args = parser.parse_args()
    receipts = [json.loads(p.read_text()) for p in (ROOT/'data_disk/private_receipts').glob('*.json')]
    chosen = {r['request']['schema']: r for r in receipts if r['request']['label'] == args.symbol and r.get('download_complete')}
    if set(chosen) != {'trades', 'mbp-10'}:
        raise ValueError('Both downloaded schema receipts required')
    task = chosen['trades']['request']['task']
    if chosen['trades']['request']['dataset'] != chosen['mbp-10']['request']['dataset']:
        raise ValueError('Mismatched feeds')
    target = ROOT/'data_disk'/('03_futures_cme' if task == 1 else '04_equities_dbeq')
    target.mkdir(parents=True, exist_ok=True)
    bars = convert(chosen['trades'], target)
    book = convert(chosen['mbp-10'], target)
    joined = bars.merge(book, on=KEYS, how='left', validate='one_to_one')
    joined = joined.sort_values(KEYS)
    joined = joined.rename(columns={'bid_sz_00':'bid_sz_00_last', 'ask_sz_00':'ask_sz_00_last'})
    common = ['ts','open','high','low','close','volume','trade_count']
    if task == 1:
        den = joined.bid_sz_00_last + joined.ask_sz_00_last
        joined['imbalance_last'] = (joined.bid_sz_00_last.astype(float)-joined.ask_sz_00_last.astype(float))/den.where(den > 0)
        columns = common+['imbalance_last','instrument_id']
        mapping = chosen['trades'].get('contract_resolution', {})
        map_path = target/'contracts_map.csv'
        rows = []
        if map_path.exists():
            with map_path.open() as f:
                rows = [r for r in csv.DictReader(f) if r['root'] != args.symbol]
        for continuous, intervals in mapping.get('result', {}).items():
            for interval in intervals:
                rows.append(dict(root=args.symbol, continuous=continuous, contract=interval['s'],
                    start_date=interval['d0'], end_date_exclusive=interval['d1'], rule='previous_day_volume'))
        with map_path.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['root','continuous','contract','start_date','end_date_exclusive','rule'], lineterminator='\n')
            w.writeheader(); w.writerows(rows)
    else:
        columns = common+['avg_trade_size','small_lot_signed_volume','bid_sz_00_last','ask_sz_00_last','instrument_id']
    joined[columns].to_csv(target/f'{args.symbol}_1min.csv', index=False)
    inventory = ['# Local market-data sizes', '', 'All market files excluded from Git pending publisher redistribution review.', '']
    for path in sorted(target.glob('*')):
        if path.suffix == '.csv' or path.name.endswith('.parquet.gz'):
            inventory.append(f'- `{path.relative_to(ROOT)}`: {path.stat().st_size:,} bytes')
    (target/'SIZES.md').write_text('\n'.join(inventory)+'\n')


if __name__ == '__main__':
    main()

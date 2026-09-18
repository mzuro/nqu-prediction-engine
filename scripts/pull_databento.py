"""Cost-gated batch downloader. No keys, signed URLs or raw exceptions logged."""
import argparse
import hashlib
import json
import math
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = '2024-09-01', '2026-09-01'
EQUITIES = 'NVDA MSFT AAPL AMZN META AVGO AMD COST GILD PYPL'.split()
LIMIT_USD = 150.0


def allowed(cost):
    return math.isfinite(float(cost)) and 0 <= float(cost) <= LIMIT_USD


def requests(equity_dataset, include_vx=False):
    jobs = []
    for symbol in ['NQ', 'ES'] + (['VX'] if include_vx else []):
        for schema in ['trades', 'mbp-10']:
            jobs.append(dict(task=1, label=symbol, dataset='XCBF.PITCH' if symbol == 'VX' else 'GLBX.MDP3',
                             symbols=[symbol+'.v.0'], stype_in='continuous', schema=schema, start=START, end=END))
    for symbol in EQUITIES:
        for schema in ['trades', 'mbp-10']:
            jobs.append(dict(task=2, label=symbol, dataset=equity_dataset, symbols=[symbol],
                             stype_in='raw_symbol', schema=schema, start=START, end=END))
    return jobs


def identity(req):
    return hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()[:20]


def safe_error(exc):
    # Exceptions may contain signed download URLs or credentials: never serialize them.
    return type(exc).__name__


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['quote', 'submit', 'collect'], default='quote')
    p.add_argument('--equities-dataset', default='XNAS.ITCH', help='Nasdaq-only depth default; no consolidated-depth claim')
    p.add_argument('--include-vx', action='store_true', help='Explicitly permit separate CFE venue; full-range coverage still required')
    p.add_argument('--task', type=int, choices=[1, 2])
    p.add_argument('--symbol', help='Optional exact label, e.g. NQ; never changes the two-year batch interval')
    args = p.parse_args()
    if not os.environ.get('DATABENTO_API_KEY'):
        print('BLOCKED: DATABENTO_API_KEY unavailable. No quote, submission, download or charge made.')
        return 2
    import databento as db
    import pandas as pd
    client = db.Historical()
    receipts = ROOT/'data_disk/private_receipts'
    receipts.mkdir(parents=True, exist_ok=True)
    if args.mode == 'collect':
        jobs = {j['id']: j for j in client.batch.list_jobs(states='queued,processing,done,expired', since=START)}
        for path in sorted(receipts.glob('*.json')):
            receipt = json.loads(path.read_text())
            jobid = receipt.get('job_id')
            if not jobid or receipt.get('download_complete'):
                continue
            job = jobs.get(jobid, {})
            # Values are provider-reported, never inferred from estimates.
            receipt['provider_accounting'] = {k: job[k] for k in ['state', 'cost_usd', 'billable_size', 'record_count', 'actual_size'] if k in job}
            print(receipt['request']['label'], receipt['request']['schema'], receipt['provider_accounting'])
            if job.get('state') == 'done':
                required = int(job.get('actual_size') or receipt['estimated_billable_bytes'])
                if shutil.disk_usage(ROOT).free < required * 3 + 50 * 2**30:
                    print('BLOCKED: insufficient headroom for download plus conversion'); continue
                folder = ROOT/'data_disk/batch_jobs'/path.stem
                client.batch.download(job_id=jobid, output_dir=folder)
                receipt['download_complete'] = True
                receipt['local_files'] = []
                for file in sorted(folder.rglob('*')):
                    if file.is_file():
                        with file.open('rb') as f:
                            digest = hashlib.file_digest(f, 'sha256').hexdigest()
                        receipt['local_files'].append(dict(path=str(file.relative_to(ROOT)), bytes=file.stat().st_size, sha256=digest))
            path.write_text(json.dumps(receipt, indent=2)+'\n')
        return 0
    for req in requests(args.equities_dataset, args.include_vx):
        if args.task and req['task'] != args.task or args.symbol and req['label'] != args.symbol:
            continue
        path = receipts / (identity(req)+'.json')
        if path.exists() and json.loads(path.read_text()).get('status') == 'submission_uncertain':
            print(req['label'], 'STOP: reconcile uncertain submission in portal before any retry'); continue
        if path.exists() and json.loads(path.read_text()).get('job_id'):
            print(req['label'], req['schema'], 'already submitted; use collect'); continue
        params = {k:v for k,v in req.items() if k not in ['task', 'label']}
        try:
            schemas = client.metadata.list_schemas(dataset=req['dataset'])
            if req['schema'] not in schemas:
                print(req['label'], req['dataset'], req['schema'], 'BLOCKED: unsupported schema'); continue
            coverage = client.metadata.get_dataset_range(dataset=req['dataset'])
            available_start = coverage.get('start')
            available_end = coverage.get('end')
            if not available_start or not available_end or pd.to_datetime(available_start, utc=True) > pd.Timestamp(START, tz='UTC') or pd.to_datetime(available_end, utc=True) < pd.Timestamp(END, tz='UTC'):
                print(req['label'], 'BLOCKED: full requested interval unavailable', coverage); continue
            cost = float(client.metadata.get_cost(**params))
            size = int(client.metadata.get_billable_size(**params))
            print(f"{req['dataset']} | {req['label']} | {req['schema']} | {START} | {END} | {size/1e9:.6f} billable GB | ${cost:.6f} estimated")
            receipt = dict(request=req, estimated_usd=cost, estimated_billable_bytes=size, status='quoted', actual_usd=None)
            if not allowed(cost):
                receipt['status'] = 'BLOCKED_OVER_150_REQUIRES_CHAT_CONFIRMATION'
                print('STOP: batch exceeds $150 or invalid estimate. No automatic splitting or override.')
            elif args.mode == 'submit':
                if shutil.disk_usage(ROOT).free < size*3 + 50*2**30:
                    receipt['status'] = 'BLOCKED_DISK_HEADROOM'
                else:
                    if req['stype_in'] == 'continuous':
                        receipt['contract_resolution'] = client.symbology.resolve(
                            dataset=req['dataset'], symbols=req['symbols'], stype_in='continuous',
                            stype_out='raw_symbol', start_date=START, end_date=END)
                    # Reserve intent before network submission. Never automatically retry uncertain submissions.
                    if path.exists() and json.loads(path.read_text()).get('status') == 'submission_uncertain':
                        print('STOP: reconcile uncertain submission in portal'); continue
                    receipt['status'] = 'submission_uncertain'
                    path.write_text(json.dumps(receipt, indent=2)+'\n')
                    job = client.batch.submit_job(**params, encoding='dbn', compression='zstd', split_duration='day')
                    receipt['job_id'] = job['id']
                    receipt['status'] = 'submitted'
                    print('Submitted', req['label'], req['schema'], 'actual cost pending provider accounting')
            path.write_text(json.dumps(receipt, indent=2)+'\n')
        except Exception as exc:
            print(req['label'], req['schema'], 'FAILED', safe_error(exc), '(details suppressed for credential safety)')
    print('Cost estimates are not actual charges. Collect reconciles provider accounting; unavailable fields remain unknown.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('FAILED', safe_error(exc), '(details suppressed for credential safety)')
        raise SystemExit(1)

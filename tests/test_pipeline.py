import json
import sys
import unittest
import tempfile
import io
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from pull_databento import allowed, requests
from convert_databento import partial, merge_partials, rth
from build_membership import extract
import pull_databento


class PipelineTests(unittest.TestCase):
    def test_over_cap_never_submits(self):
        client = MagicMock()
        client.metadata.list_schemas.return_value = ['trades','mbp-10']
        client.metadata.get_dataset_range.return_value = {'start':'2020-01-01','end':'2026-09-02'}
        client.metadata.get_cost.return_value = 150.01
        client.metadata.get_billable_size.return_value = 1000
        with tempfile.TemporaryDirectory() as folder, patch.object(pull_databento,'ROOT',Path(folder)), \
             patch.dict('os.environ', {'DATABENTO_API_KEY':'test-not-a-real-key'}), \
             patch('databento.Historical', return_value=client), \
             patch.object(sys,'argv',['pull_databento.py','--mode','submit','--task','1','--symbol','NQ']):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(pull_databento.main(),0)
            self.assertEqual(client.metadata.get_cost.call_count,2)
            client.batch.submit_job.assert_not_called()

    def test_official_crosschecks(self):
        p = ROOT/'data_disk/05_index_membership_history/announcement_crosschecks.json'
        checks = json.loads(p.read_text())
        self.assertEqual(len(checks),20)
        self.assertTrue(all(c['passed'] for c in checks))

    def test_cost_limit(self):
        self.assertTrue(allowed(150)); self.assertTrue(allowed(0))
        for x in [150.01, float('nan'), float('inf'), -1]:
            self.assertFalse(allowed(x))

    def test_no_cme_vx_or_batch_splitting(self):
        jobs = requests('XNAS.ITCH', True)
        self.assertEqual(len(jobs), 26)
        self.assertTrue(all(j['start']=='2024-09-01' and j['end']=='2026-09-01' for j in jobs))
        self.assertTrue(all(j['dataset']=='XCBF.PITCH' for j in jobs if j['label']=='VX'))

    def test_bars_chunk_boundaries(self):
        f = pd.DataFrame(dict(ts_event=pd.to_datetime(['2025-01-02T14:30:00Z','2025-01-02T14:30:20Z','2025-01-02T14:30:50Z']),
            instrument_id=[1,1,1], price=[10.,12.,11.], size=[50,150,25], side=['B','A','A']))
        b = merge_partials([partial(f.iloc[:2], 'trades'), partial(f.iloc[2:], 'trades')], 'trades').iloc[0]
        self.assertEqual([b.open,b.high,b.low,b.close], [10,12,10,11])
        self.assertEqual(b.volume,225); self.assertEqual(b.trade_count,3)
        self.assertEqual(b.small_lot_signed_volume,25)
        self.assertEqual(b.avg_trade_size,75)

    def test_unknown_side_not_assumed(self):
        f = pd.DataFrame(dict(ts_event=pd.to_datetime(['2025-01-02T14:30:00Z']),instrument_id=[1],price=[10.],size=[10],side=['N']))
        b = merge_partials([partial(f,'trades')],'trades')
        self.assertTrue(pd.isna(b.small_lot_signed_volume.iloc[0]))

    def test_rth_dst_holiday_and_half_day(self):
        f = pd.DataFrame(dict(ts_event=pd.to_datetime(['2025-01-02T14:29:59Z','2025-01-02T14:30:00Z',
            '2025-07-02T13:30:00Z','2025-07-04T14:00:00Z','2025-11-28T17:59:59Z','2025-11-28T18:00:00Z'])))
        self.assertEqual(list(rth(f).index), [1,2,4])

    def test_contracts_never_merged(self):
        f = pd.DataFrame(dict(ts_event=pd.to_datetime(['2025-01-02T14:30:00Z']*2),instrument_id=[1,2],price=[10.,100.],size=[1,1],side=['B','B']))
        self.assertEqual(len(merge_partials([partial(f,'trades')],'trades')),2)

    def test_membership_integrity(self):
        folder = ROOT/'data_disk/05_index_membership_history'
        manifest = json.loads((folder/'revision_manifest.json').read_text())
        self.assertEqual(len(manifest),51)
        for row in manifest:
            self.assertEqual(row['status'],'ok')
            self.assertLessEqual(row['revision_timestamp'],row['asof']+'T00:00:00Z')
        f = pd.read_csv(folder/'ndx_membership_history.csv')
        self.assertFalse(f.duplicated(['quarter','symbol']).any())
        self.assertEqual(set(f.in_index),{0,1})
        for q, g in f.groupby('quarter'):
            self.assertTrue(95 <= g.in_index.sum() <= 110)

    def test_member_parser_fails_closed(self):
        with self.assertRaises(ValueError): extract('==Components==\n* Example (FAKE)')


if __name__ == '__main__':
    unittest.main()

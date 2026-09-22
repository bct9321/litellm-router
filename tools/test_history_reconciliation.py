import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from router.spend_ledger import Ledger, BudgetDenied

LIMITS = {'daily': 100, 'monthly': 100, 'request': 80, 'models': {'m': {'daily':100,'monthly':100}}}
NOW = datetime(2026,9,21,12,tzinfo=timezone.utc)

class HistoryTests(unittest.TestCase):
    def test_identity_unknown_and_breach(self):
        with tempfile.TemporaryDirectory() as d:
            l=Ledger(str(Path(d)/'x'),LIMITS,clock=lambda:NOW)
            l.reserve('a','r','m','selected','dep',40,entry_alias='entry',provider_model='provider',kind='classifier')
            l.settle('a','partial',10,'pending')
            t=l.report()['overall']['today']
            self.assertIsNone(t['estimated'])
            self.assertEqual(t['pending_exposure'],40)
            l.settle('a','final',50,'provider-reported')
            self.assertEqual(l.report()['attempts'][0]['contract_breached'],1)
            self.assertEqual(l.report()['attempts'][0]['entry_alias'],'entry')
            with self.assertRaises(BudgetDenied): l.reserve('b','s','m','x','dep',1)

    def test_scoped_opening_and_unknown_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            l=Ledger(str(Path(d)/'x'),LIMITS,clock=lambda:NOW,billing_scope='account-a',coverage_mode='provider-period')
            with self.assertRaises(BudgetDenied): l.reserve('a','r','m','x','dep',20)
            row={'id':'legacy-label:row','date':'2026-09-20','model':'provider','canonical':'m','usage':70,'requests':1,
                 'scope':'account-a','endpoint_id':'ep','disposition':'opening-balance','revision':1}
            l.import_activity('source',[row])
            l.import_activity('renamed',[dict(row,id='different-id')])
            l.attest_history_coverage('account-a','2026-09-01T00:00:00+00:00',NOW.isoformat())
            l.reserve('a','r','m','x','dep',20)
            self.assertEqual(l.report()['overall']['month']['exposure'],90)
            with self.assertRaises(BudgetDenied): l.reserve('b','s','m','x','dep',11)
            l.import_activity('corrected',[dict(row,usage=75,revision=2)])
            self.assertEqual(l.report()['overall']['month']['exposure'],95)
            self.assertEqual(len(l.report()['historical_imports']),1)

    def test_overlap_unknown_and_distinct_scopes(self):
        with tempfile.TemporaryDirectory() as d:
            l=Ledger(str(Path(d)/'x'),LIMITS,clock=lambda:NOW)
            row={'id':'x','date':'2026-09-20','model':'m','usage':None,'requests':0,'scope':'a'}
            l.import_activity('source',[row,dict(row,scope='b')])
            self.assertEqual(len(l.report()['historical_imports']),2)
            self.assertIsNone(l.report()['historical_models']['m']['month']['provider_reported'])
            with self.assertRaises(ValueError):
                l.import_activity('source',[dict(row,date='2026-09-21',usage=1,disposition='opening-balance')])

    def test_legacy_rows_migrate_once_and_reimport_deduplicates(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'x')
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE imports (id TEXT PRIMARY KEY, source TEXT, day TEXT, model TEXT, usage INTEGER, requests INTEGER, coverage TEXT)')
                db.execute("INSERT INTO imports VALUES ('old-source:2026-09-20:m:ep','old','2026-09-20','m',20,1,'aggregate')")
            db.close()
            l=Ledger(path,LIMITS,clock=lambda:NOW)
            l.import_activity('new',[{'id':'new-source:2026-09-20:m:ep','date':'2026-09-20','model':'m','usage':20,'requests':1}])
            self.assertEqual(len(Ledger(path,LIMITS,clock=lambda:NOW).report()['historical_imports']),1)

    def test_unknown_correction_and_event_conflicts_do_not_release(self):
        with tempfile.TemporaryDirectory() as d:
            l=Ledger(str(Path(d)/'x'),LIMITS,clock=lambda:NOW)
            l.reserve('a','r','m','x','dep',70,50)
            l.settle('a','partial',10,'pending')
            l.settle('a','cancel',None,'unknown')
            self.assertEqual(l.request_remaining('r'),10)
            self.assertEqual(l.report()['overall']['today']['unknown_exposure'],70)
            self.assertEqual(l.report()['overall']['today']['provisional_reported'],10)
            l.settle('a','final',20,'provider-reported')
            l.settle('a','final',20,'provider-reported')
            with self.assertRaises(ValueError): l.settle('a','conflict',21,'provider-reported')
            self.assertEqual(l.request_remaining('r'),10)
            with self.assertRaises(BudgetDenied): l.reserve('b','s','m','x','dep',1)

    def test_opening_rejects_overlap_with_existing_attempt(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'x')
            l=Ledger(path,LIMITS,clock=lambda:NOW)
            l.reserve('a','r','m','x','dep',10)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE attempts SET day='2026-09-20', month='2026-09'")
            db.close()
            with self.assertRaises(ValueError):
                l.import_activity('s',[{'id':'a','scope':'account','date':'2026-09-20','model':'m','usage':10,'requests':1,'disposition':'opening-balance'}])

    def test_policy_revision_required_for_dispatch_after_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'x')
            l=Ledger(path,LIMITS,clock=lambda:NOW,policy_revision='one')
            with self.assertRaises(ValueError): Ledger(path,LIMITS,clock=lambda:NOW,policy_revision='two')
            reader=Ledger(path,LIMITS,clock=lambda:NOW)
            self.assertEqual(reader.report()['overall']['today']['exposure'],0)
            with self.assertRaises(BudgetDenied): reader.reserve('a','r','m','x','dep',1)
            l.reserve('a','r','m','x','dep',1)

    def test_conflicting_legacy_metadata_requires_reconciliation(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'x')
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE imports (id TEXT PRIMARY KEY, source TEXT, day TEXT, model TEXT, usage INTEGER, requests INTEGER, coverage TEXT)')
                db.executemany('INSERT INTO imports VALUES (?,?,?,?,?,?,?)',[
                    ('old:2026-09-20:m:ep','old','2026-09-20','m',20,1,'aggregate'),
                    ('new:2026-09-20:m:ep','new','2026-09-20','m',20,2,'aggregate')])
            db.close()
            with self.assertRaises(ValueError): Ledger(path,LIMITS,clock=lambda:NOW)

    def test_reservation_period_is_measured_after_write_lock(self):
        import sqlite3
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'x')
            clock=[datetime(2026,9,30,23,59,59,tzinfo=timezone.utc)]
            l=Ledger(path,LIMITS,clock=lambda:clock[0])
            blocking=sqlite3.connect(path,isolation_level=None)
            blocking.execute('BEGIN IMMEDIATE')
            connecting=threading.Event(); proceed=threading.Event()
            real_connect=sqlite3.connect
            def delayed_connect(*args,**kwargs):
                connecting.set()
                if not proceed.wait(5): raise AssertionError('Missing lock release')
                return real_connect(*args,**kwargs)
            try:
                with patch('router.spend_ledger.sqlite3.connect',side_effect=delayed_connect):
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future=pool.submit(l.reserve,'a','r','m','x','dep',10)
                        self.assertTrue(connecting.wait(5))
                        clock[0]=datetime(2026,10,1,tzinfo=timezone.utc)
                        blocking.commit();proceed.set()
                        future.result(timeout=5)
                l.settle('a','final',10,'provider-reported')
                self.assertEqual(l.report()['attempts'][0]['day'],'2026-10-01')
                self.assertEqual(l.report()['overall']['today']['provider_reported'],10)
            finally:
                proceed.set();blocking.close()

    def test_report_timestamp_matches_snapshot_acquisition(self):
        import sqlite3
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            clock=[datetime(2026,9,30,23,59,59,tzinfo=timezone.utc)]
            l=Ledger(str(Path(d)/'x'),LIMITS,clock=lambda:clock[0])
            real_connect=sqlite3.connect
            def crossing_connect(*args,**kwargs):
                clock[0]=datetime(2026,10,1,tzinfo=timezone.utc)
                return real_connect(*args,**kwargs)
            with patch('router.spend_ledger.sqlite3.connect',side_effect=crossing_connect):
                report=l.report()
            self.assertEqual(report['as_of'],'2026-10-01T00:00:00+00:00')
            self.assertEqual(report['overall']['month']['reset_at'],'2026-11-01T00:00:00+00:00')

if __name__=='__main__': unittest.main()

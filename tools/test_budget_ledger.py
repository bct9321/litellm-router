"""Public durable accounting seam; monetary examples are synthetic nanodollars."""
import sys
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from router.spend_ledger import Ledger, BudgetDenied


LIMITS = {'daily': 100, 'monthly': 150, 'request': 80,
          'models': {'canonical': {'daily': 100, 'monthly': 150}}}


def competing_worker(args):
    path, number = args
    try:
        Ledger(path, LIMITS).reserve(str(number), str(number), 'canonical', 'alias', 'deployment', 30)
        return True
    except BudgetDenied:
        return False


class LedgerTests(unittest.TestCase):
    def test_atomic_reservations_across_worker_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'spend.sqlite')
            Ledger(path, LIMITS)
            with ProcessPoolExecutor(max_workers=4) as workers:
                results = list(workers.map(competing_worker, [(path, n) for n in range(8)]))
            self.assertEqual(sum(results), 3)
            self.assertEqual(Ledger(path, LIMITS).report()['overall']['today']['exposure'], 90)

    def test_pending_charge_carries_across_daily_and_monthly_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            clock = [datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)]
            ledger = Ledger(str(Path(folder) / 'spend.sqlite'), LIMITS, clock=lambda: clock[0])
            ledger.reserve('one', 'request', 'canonical', 'alias', 'deployment', 70)
            clock[0] = datetime(2026, 10, 1, tzinfo=timezone.utc)
            self.assertEqual(ledger.report()['overall']['month']['exposure'], 70)
            with self.assertRaises(BudgetDenied):
                ledger.reserve('two', 'request', 'canonical', 'alias', 'deployment', 20)
            ledger.settle('one', 'final', 20, 'provider-reported')
            self.assertEqual(ledger.report()['overall']['today']['exposure'], 0)

    def test_aliases_share_budget_and_pending_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'spend.sqlite')
            limits = {'daily': 100, 'monthly': 150, 'request': 80,
                      'models': {'canonical': {'daily': 100, 'monthly': 150}}}
            ledger = Ledger(path, limits)
            ledger.reserve('attempt-1', 'request-1', 'canonical', 'alias-one', 'deployment-one', 70, 50)
            second = Ledger(path, limits)
            with self.assertRaises(BudgetDenied):
                second.reserve('attempt-2', 'request-2', 'canonical', 'alias-two', 'deployment-two', 40, 30)
            self.assertEqual(second.report()['models']['canonical']['today']['exposure'], 70)
            second.settle('attempt-1', 'event-1', None, 'unknown')
            self.assertEqual(ledger.report()['models']['canonical']['today']['exposure'], 70)
            second.settle('attempt-1', 'event-2', 20, 'provider-reported')
            second.settle('attempt-1', 'event-2', 20, 'provider-reported')
            self.assertEqual(ledger.report()['models']['canonical']['today']['exposure'], 20)
            ledger.reserve('attempt-2', 'request-2', 'canonical', 'alias-two', 'deployment-two', 40, 30)
            self.assertEqual(ledger.report()['models']['canonical']['today']['exposure'], 60)


if __name__ == '__main__':
    unittest.main()

"""Durable canonical-model reservations. Amounts are integer USD nanodollars.

This module trusts only server-created dispatch identities and charge bounds.
It does not establish that a provider obeys a billing bound; the dispatch layer
must reject candidates without that contract. SQLite requires a local disk shared
by workers, not separate databases or a network filesystem.
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import json
import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_CEILING


class BudgetDenied(ValueError):
    pass


def amount(value):
    if type(value) is not int or value < 0 or value > 9223372036854775807:
        raise ValueError('Amounts must be finite nonnegative integer USD nanodollars')
    return value


def usd_nanos(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed < 0:
            return None
        return int((parsed * 1_000_000_000).to_integral_value(rounding=ROUND_CEILING))
    except (InvalidOperation, ValueError, OverflowError):
        return None


class Ledger:
    def __init__(self, path, limits, clock=None, *, billing_scope="router-only", coverage_mode="router-only", policy_revision=None):
        if coverage_mode not in ("router-only", "provider-period") or not billing_scope:
            raise ValueError("Explicit accounting scope required")
        self.policy_revision = policy_revision
        self.billing_scope = billing_scope
        self.coverage_mode = coverage_mode
        self.path = path
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.limits = json.loads(json.dumps(limits))
        for field in ('daily', 'monthly', 'request'):
            amount(self.limits[field])
        for cap in self.limits['models'].values():
            amount(cap['daily'])
            amount(cap['monthly'])
        with self._transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, policy TEXT NOT NULL)')
            policy = json.dumps(self.limits, sort_keys=True)
            old = db.execute('SELECT policy FROM settings WHERE id=1').fetchone()
            if old and old['policy'] != policy:
                raise ValueError('Ledger policy differs; workers must share identical limits')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1, ?)', (policy,))
            db.execute('''CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY, request_id TEXT NOT NULL, model TEXT NOT NULL,
                alias TEXT NOT NULL, deployment TEXT NOT NULL, created TEXT NOT NULL,
                day TEXT NOT NULL, month TEXT NOT NULL, reserved INTEGER NOT NULL,
                estimated INTEGER, reported INTEGER, state TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, attempt TEXT NOT NULL, payload TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS imports (
                id TEXT PRIMARY KEY, source TEXT NOT NULL, day TEXT NOT NULL,
                model TEXT NOT NULL, usage INTEGER NOT NULL, requests INTEGER NOT NULL,
                coverage TEXT NOT NULL, canonical TEXT NOT NULL DEFAULT '')''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(imports)')}
            if 'canonical' not in columns:
                db.execute("ALTER TABLE imports ADD COLUMN canonical TEXT NOT NULL DEFAULT ''")
                db.execute("UPDATE imports SET canonical=model WHERE canonical=''" )

            db.execute("CREATE TABLE IF NOT EXISTS scope_settings (id INTEGER PRIMARY KEY, scope TEXT, mode TEXT, activated TEXT)")
            previous = db.execute("SELECT * FROM scope_settings WHERE id=1").fetchone()
            if previous and (previous['scope'], previous['mode']) != (billing_scope, coverage_mode):
                raise ValueError('Workers must share accounting scope')
            db.execute("INSERT OR IGNORE INTO scope_settings VALUES (1,?,?,?)", (billing_scope, coverage_mode, self.clock().astimezone(timezone.utc).isoformat()))
            self.activated = db.execute("SELECT activated FROM scope_settings WHERE id=1").fetchone()['activated']
            columns = {r['name'] for r in db.execute('PRAGMA table_info(attempts)')}
            for name, declaration in {'entry_alias':"TEXT", 'provider_model':"TEXT", 'selected_tier':"TEXT", 'deployment_id':"TEXT", 'contract_revision':"TEXT", 'kind':"TEXT NOT NULL DEFAULT 'solver'", 'billing_scope':"TEXT NOT NULL DEFAULT 'router-only'", 'contract_breached':"INTEGER NOT NULL DEFAULT 0"}.items():
                if name not in columns:
                    db.execute(f'ALTER TABLE attempts ADD COLUMN {name} {declaration}')
            db.execute("CREATE TABLE IF NOT EXISTS history_coverage (scope TEXT, start TEXT, end TEXT, PRIMARY KEY(scope,start,end))")
            db.execute("CREATE TABLE IF NOT EXISTS history (identity TEXT PRIMARY KEY, source TEXT, day TEXT, model TEXT, canonical TEXT, usage INTEGER, requests INTEGER, coverage TEXT, scope TEXT, endpoint_id TEXT, revision INTEGER, disposition TEXT)")
            # Legacy aggregate identity did not include account scope. Retain once as
            # comparison evidence; never promote a guessed account or overlap.
            for old in db.execute('SELECT * FROM imports').fetchall():
                endpoint = old['id'].rsplit(':',1)[-1]
                identity = json.dumps(['legacy-unscoped',old['day'],old['model'],endpoint])
                existing = db.execute('SELECT * FROM history WHERE identity=?',(identity,)).fetchone()
                if existing and any(existing[field] != old[field] for field in ('usage','requests','canonical','coverage')):
                    raise ValueError('Conflicting legacy aggregates require explicit reconciliation')
                db.execute('INSERT OR IGNORE INTO history VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (identity,old['source'],old['day'],old['model'],old['canonical'],old['usage'],old['requests'],old['coverage'],'legacy-unscoped',endpoint,0,'comparison-only'))
            db.execute('DELETE FROM imports')
            db.execute('CREATE TABLE IF NOT EXISTS policy_identity (id INTEGER PRIMARY KEY, revision TEXT NOT NULL)')
            prior_revision = db.execute('SELECT revision FROM policy_identity WHERE id=1').fetchone()
            if policy_revision is not None:
                if not isinstance(policy_revision,str) or not policy_revision:
                    raise ValueError('Policy revision required')
                if prior_revision and prior_revision['revision'] != policy_revision:
                    raise ValueError('Workers must share identical full policy revision')
                db.execute('INSERT OR IGNORE INTO policy_identity VALUES (1,?)',(policy_revision,))

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA busy_timeout=30000')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _periods(self):
        now = self.clock().astimezone(timezone.utc)
        return now, now.strftime('%Y-%m-%d'), now.strftime('%Y-%m')

    @staticmethod
    def _exposure(row):
        # Only final provider-reported accounting releases a reservation.
        return row['reported'] if row['state'] == 'provider-reported' else max(row['reserved'], row['reported'] or 0)

    def reserve(self, attempt, request, model, alias, deployment, bound, estimate=None, *, entry_alias=None, provider_model=None, selected_tier=None, deployment_id=None, contract_revision=None, kind="solver", billing_scope=None):
        amount(bound)
        if estimate is not None:
            amount(estimate)
            if estimate > bound:
                raise ValueError('Estimate exceeds conservative bound')
        if not all(isinstance(x, str) and x for x in (attempt, request, model, alias, deployment)):
            raise ValueError('Server dispatch identities are required')
        if model not in self.limits['models']:
            raise BudgetDenied('Canonical model lacks explicit limits')
        with self._transaction() as db:
            now, day, month = self._periods()
            if db.execute('SELECT 1 FROM attempts WHERE id=?', (attempt,)).fetchone():
                raise BudgetDenied('Attempt already reserved; never dispatch it again')
            stored_revision=db.execute('SELECT revision FROM policy_identity WHERE id=1').fetchone()
            if stored_revision and stored_revision['revision'] != self.policy_revision:
                raise BudgetDenied('Full policy revision required for dispatch')
            if db.execute('SELECT 1 FROM attempts WHERE contract_breached=1').fetchone():
                raise BudgetDenied('Billing contract breached; explicit reconciliation required')
            if billing_scope is not None and billing_scope != self.billing_scope:
                raise BudgetDenied('Attempt billing scope mismatch')
            rows = db.execute('SELECT * FROM attempts').fetchall()
            history = db.execute('SELECT * FROM history').fetchall()
            if self.coverage_mode == 'provider-period' and not self._coverage_complete(db, month+'-01T00:00:00+00:00'):
                raise BudgetDenied('Provider-period historical coverage unknown')
            if sum(self._exposure(r) for r in rows if r['request_id'] == request) + bound > self.limits['request']:
                raise BudgetDenied('Per-request ceiling exceeded')
            for period, current in (('day', day), ('month', month)):
                name = 'daily' if period == 'day' else 'monthly'
                # Outstanding charges carry into new windows until resolved.
                relevant = [r for r in rows if r[period] == current or r['state'] != 'provider-reported']
                for target, cap in ((None, self.limits[name]), (model, self.limits['models'][model][name])):
                    spent = sum(self._exposure(r) for r in relevant if target is None or r['model'] == target)
                    spent += self._opening(history, period, current, target)
                    if spent + bound > cap:
                        raise BudgetDenied(f'{target or "overall"} {name} budget exceeded')
            db.execute('INSERT INTO attempts (id,request_id,model,alias,deployment,created,day,month,reserved,estimated,state,entry_alias,provider_model,selected_tier,deployment_id,contract_revision,kind,billing_scope) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (attempt, request, model, alias, deployment, now.isoformat(), day, month, bound, estimate, 'pending',entry_alias or alias,provider_model,selected_tier,deployment_id or deployment,contract_revision,kind,self.billing_scope))
        return attempt

    def settle(self, attempt, event, cost, state):
        if state not in ('estimated', 'provider-reported', 'pending', 'unknown'):
            raise ValueError('Invalid accounting state')
        if cost is not None:
            amount(cost)
        if state == 'provider-reported' and cost is None:
            raise ValueError('Provider-reported settlement requires a known cost')
        payload = json.dumps([attempt, cost, state])
        with self._transaction() as db:
            prior = db.execute('SELECT * FROM events WHERE id=?', (event,)).fetchone()
            if prior:
                if prior['payload'] != payload:
                    db.execute("UPDATE attempts SET state='unknown', reported=MAX(COALESCE(reported,0),?), contract_breached=1 WHERE id IN (?,?)",(cost or 0,attempt,prior['attempt']))
                    db.commit()
                    raise ValueError('Conflicting duplicate event; accounting quarantined')
                return
            row = db.execute('SELECT * FROM attempts WHERE id=?', (attempt,)).fetchone()
            if row is None:
                raise ValueError('Unknown attempt')
            if row['state'] == 'provider-reported':
                if state == 'provider-reported' and cost != row['reported']:
                    db.execute("UPDATE attempts SET state='unknown', reported=?, contract_breached=1 WHERE id=?",(max(cost,row['reported']),attempt))
                    db.execute('INSERT INTO events VALUES (?,?,?)',(event,attempt,payload))
                    db.commit()
                    raise ValueError('Conflicting final charge requires explicit reconciliation')
                # Late/duplicate unknown callbacks must not demote final evidence.
            else:
                db.execute('UPDATE attempts SET reported=?, state=?, contract_breached=? WHERE id=?', (max(cost or 0, row['reported'] or 0) if state != 'provider-reported' and (cost is not None or row['reported'] is not None) else cost, state, int(row['contract_breached'] or (cost is not None and cost > row['reserved'])), attempt))
            db.execute('INSERT INTO events VALUES (?, ?, ?)', (event, attempt, payload))

    def request_remaining(self, request_id):
        with self._transaction() as db:
            rows = db.execute('SELECT * FROM attempts WHERE request_id=?',(request_id,)).fetchall()
            return max(0,self.limits['request']-sum(self._exposure(r) for r in rows))

    def _opening(self, rows, period, current, model=None):
        if self.coverage_mode != 'provider-period':
            return 0
        return sum(r['usage'] for r in rows if r['scope']==self.billing_scope and r['disposition']=='opening-balance'
                   and (r['day'] if period=='day' else r['day'][:7])==current and (model is None or r['canonical']==model))

    def _coverage_complete(self, db, start):
        if self.coverage_mode == 'router-only' or start >= self.activated:
            return True
        cursor=datetime.fromisoformat(start)
        end=datetime.fromisoformat(self.activated)
        for row in db.execute('SELECT * FROM history_coverage WHERE scope=? ORDER BY start',(self.billing_scope,)):
            a,b=datetime.fromisoformat(row['start']),datetime.fromisoformat(row['end'])
            if a<=cursor: cursor=max(cursor,b)
        unresolved=db.execute("SELECT 1 FROM history WHERE scope=? AND day>=? AND day<=? AND (usage IS NULL OR disposition!='opening-balance')",(self.billing_scope,start[:10],self.activated[:10])).fetchone()
        return cursor>=end and not unresolved

    def attest_history_coverage(self, scope, start, end):
        a,b=datetime.fromisoformat(start),datetime.fromisoformat(end)
        if a.tzinfo is None or b.tzinfo is None or a>b or b>datetime.fromisoformat(self.activated):
            raise ValueError('Coverage must be timezone-aware and end before activation')
        with self._transaction() as db:
            db.execute('INSERT OR IGNORE INTO history_coverage VALUES (?,?,?)',(scope,a.astimezone(timezone.utc).isoformat(),b.astimezone(timezone.utc).isoformat()))

    def report(self):
        with self._transaction() as db:
            now,day,month=self._periods()
            tomorrow=(now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
            next_month=(now.replace(day=28)+timedelta(days=4)).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
            rows=[dict(r) for r in db.execute('SELECT * FROM attempts ORDER BY created,id')]
            imports=[dict(r) for r in db.execute('SELECT * FROM history ORDER BY day,model,identity')]
            complete=self._coverage_complete(db,month+'-01T00:00:00+00:00')
        def totals(selected,caps,model=None):
            result={}
            for key,period,current,cap,reset in [('today','day',day,'daily',tomorrow),('month','month',month,'monthly',next_month)]:
                active=[r for r in selected if r[period]==current or r['state']!='provider-reported']
                opening=self._opening(imports,period,current,model)
                exposure=sum(self._exposure(r) for r in active)+opening
                missing=sum(r['estimated'] is None for r in active)
                pending=[r for r in active if r['state'] in ('pending','estimated')]
                unknown=[r for r in active if r['state']=='unknown']
                result[key]={'provider_reported':sum(r['reported'] for r in active if r['state']=='provider-reported'),
                    'estimated':None if missing else sum(r['estimated'] for r in active),
                    'known_estimated':sum(r['estimated'] or 0 for r in active),'estimate_unknown_count':missing,
                    'opening_balance':opening,'exposure':exposure,'remaining':max(0,caps[cap]-exposure) if complete else None,
                    'limit':caps[cap],'reset_at':reset.isoformat(),'pending_or_unknown':len(pending)+len(unknown),
                    'pending_count':len(pending),'unknown_count':len(unknown),
                    'pending_exposure':sum(self._exposure(r) for r in pending),'unknown_exposure':sum(self._exposure(r) for r in unknown),
                    'provisional_reported':sum(r['reported'] or 0 for r in pending+unknown),
                    'admission':'coverage_unknown' if not complete else ('contract_breached' if any(r['contract_breached'] for r in rows) else ('exhausted' if exposure>=caps[cap] else 'allowed')),
                    'coverage':{'scope':self.billing_scope,'mode':self.coverage_mode,'since':self.activated,'complete':complete}}
            return result
        def history_totals(selected):
            result={}
            for key,current in [('today',day),('month',month)]:
                active=[r for r in selected if r['day'].startswith(current)]
                result[key]={'provider_reported':None if any(r['usage'] is None for r in active) else sum(r['usage'] for r in active),
                             'requests':sum(r['requests'] for r in active),'coverage':'scoped aggregates; only explicit nonoverlap openings affect provider-period budgets'}
            return result
        return {'unit':'USD nanodollars','timezone':'UTC','as_of':now.isoformat(),
            'coverage':{'scope':self.billing_scope,'mode':self.coverage_mode,'complete':complete,'provider_history':'explicit openings only; comparison aggregates excluded'},
            'overall':totals(rows,self.limits),'models':{m:totals([r for r in rows if r['model']==m],c,m) for m,c in self.limits['models'].items()},
            'historical_models':{m:history_totals([r for r in imports if r['model']==m]) for m in sorted({r['model'] for r in imports})},
            'historical_canonical':{m:history_totals([r for r in imports if r['canonical']==m]) for m in sorted({r['canonical'] for r in imports})},
            'attempts':rows,'historical_imports':imports}

    def import_activity(self, source, rows):
        if not isinstance(source,str) or not source: raise ValueError('Historical source required')
        with self._transaction() as db:
            for row in rows:
                day=str(row['date'])
                if datetime.strptime(day,'%Y-%m-%d').strftime('%Y-%m-%d') != day: raise ValueError('UTC day required')
                model=str(row['model']); canonical=str(row.get('canonical',model))
                scope=str(row.get('scope','legacy-unscoped')); endpoint=str(row.get('endpoint_id',str(row['id']).rsplit(':',1)[-1]))
                usage=row['usage']
                if usage is not None: amount(usage)
                requests=amount(row['requests']); revision=amount(row.get('revision',0))
                disposition=row.get('disposition','comparison-only')
                if disposition not in ('opening-balance','comparison-only','unresolved'): raise ValueError('Invalid history disposition')
                if disposition=='opening-balance':
                    if usage is None or day>=self.activated[:10] or canonical not in self.limits['models'] or scope=='legacy-unscoped':
                        raise ValueError('Opening requires known amount, canonical model, explicit scope and full day before activation')
                if disposition=='opening-balance' and db.execute('SELECT 1 FROM attempts WHERE day=?',(day,)).fetchone():
                    raise ValueError('Opening overlaps local attempts')
                identity=json.dumps([scope,day,model,endpoint])
                values=(identity,source,day,model,canonical,usage,requests,str(row.get('coverage','aggregate')),scope,endpoint,revision,disposition)
                old=db.execute('SELECT * FROM history WHERE identity=?',(identity,)).fetchone()
                if old:
                    equivalent=all(old[k]==v for k,v in zip(('canonical','usage','requests','coverage','disposition'),(canonical,usage,requests,values[7],disposition)))
                    if revision<old['revision']: raise ValueError('Stale historical correction')
                    if revision==old['revision']:
                        if not equivalent: raise ValueError('Conflicting historical import')
                        continue
                db.execute('INSERT OR REPLACE INTO history VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',values)

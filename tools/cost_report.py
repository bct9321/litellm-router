"""Operator-facing local spend report and optional safe historical import."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from router.spend_ledger import Ledger, usd_nanos

configured_model_map = {}


def import_openrouter_activity(ledger, source, payload, *, scope="legacy-unscoped", disposition="comparison-only", revision=0):
    rows = []
    for item in payload.get('data', []):
        usage = usd_nanos(item.get('usage'))
        requests = item.get('requests', 0)
        if type(requests) is not int or requests < 0:
            raise ValueError('OpenRouter activity requests must be a nonnegative integer')
        provider_model = str(item['model'])
        canonical = str(configured_model_map.get(provider_model, provider_model))
        rows.append({'id': 'openrouter-activity:' + str(item['date']) + ':' + provider_model + ':' + str(item.get('endpoint_id', '')),
                     'date': item['date'], 'model': provider_model, 'canonical': canonical, 'usage': usage,
                     'requests': requests,
                     'coverage': 'OpenRouter completed UTC daily aggregate', 'scope': scope,
                     'endpoint_id': str(item.get('endpoint_id', '')), 'disposition': disposition, 'revision': revision})
    ledger.import_activity(source, rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True, help='Cost-router JSON config; do not put secrets here.')
    parser.add_argument('--openrouter-activity', type=Path, help='Sanitized downloaded /api/v1/activity JSON; no network call.')
    parser.add_argument('--source', default='openrouter-activity-v1')
    parser.add_argument('--history-scope', default='legacy-unscoped')
    parser.add_argument('--history-disposition', choices=['comparison-only','opening-balance','unresolved'], default='comparison-only')
    parser.add_argument('--history-revision', type=int, default=0)
    parser.add_argument('--coverage-attestation', type=Path, help='Explicit reviewed JSON scope/start/end coverage evidence; never inferred from row absence.')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    global configured_model_map
    configured_model_map = config.get('history_model_map', {})
    if not isinstance(configured_model_map, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in configured_model_map.items()):
        raise ValueError('history_model_map must map provider model strings to canonical model strings')
    ledger = Ledger(config['ledger'], config['limits'], billing_scope=config.get('billing_scope','router-only'), coverage_mode=config.get('coverage_mode','router-only'))
    if args.openrouter_activity:
        import_openrouter_activity(ledger, args.source, json.loads(args.openrouter_activity.read_text(encoding='utf-8')), scope=args.history_scope, disposition=args.history_disposition, revision=args.history_revision)
    if args.coverage_attestation:
        attestation = json.loads(args.coverage_attestation.read_text(encoding='utf-8'))
        ledger.attest_history_coverage(attestation['scope'], attestation['start'], attestation['end'])
    print(json.dumps(ledger.report(), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

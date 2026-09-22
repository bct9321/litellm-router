# Local delivery receipt — 2026-09-21

Origin: user-authorized execution with bounded subagents; coordinator's actual local command results and two independent final reviews. Status: verified supported local behavior; full goal is NOT marked complete because strict live billing cannot be established from the available provider contract. No secrets, provider inference, charges, live service/billing changes, publishing, merge or deployment.

Branch: `codex/cost-aware-router`; baseline HEAD `9f8d97b5ada521e3e9c356dfc2b305fc5c2333dc`. Existing dirty work and original raw bytes preserved. This receipt describes the full working delta, including work already present before resumed execution; it does not attribute every changed line to this turn.

## Implemented scope

- Repaired stale quota/backoff, real-user transcript filtering, failed benchmark accounting, unknown prices, missing diagnostics and answer-leaking vision prompt. Production classifier seam is exercised.
- Trusted original request/capability/route context precedes quota rewrites. Final physical dispatch checks every selected deployment/fallback against that authority, fresh bounded contract, actual endpoint/model/body, free-first and atomic limits.
- Explicit finite global/model UTC daily/monthly limits and logical request ceiling include Jev overhead and failed billable attempts. Actual outgoing output caps are enforced. Unsupported billable surfaces, missing/stale contracts and unbounded live adapters fail closed.
- SQLite persists per-attempt canonical accounting plus requested alias, selected alias, provider model, deployment and contract attribution. Complete final provider usage settles; pending/estimated/unknown exposure remains reserved across cancellation, partial streams, restart and period reset. Duplicate events are idempotent; conflicting finality quarantines accounting.
- Operator JSON reports model/day/month totals, estimates, remaining amounts, resets, separate pending/unknown and scoped coverage. History identity is scope/day/model/endpoint, independent of import label. Corrections require revisions; only explicit nonoverlapping openings affect provider-period budgets. Unknown history stays unknown.
- Late audit fixes: timestamp budgets/reports under the SQLite lock; recheck contract expiry after reservation in solver and classifier. Known no-dispatch expiry refusals conservatively keep unknown exposure pending explicit reconciliation.

## Exact validation commands and outcomes

Executed from `C:\Users\Brandon\workspaces\litellm` using the existing isolated environment:

| Command | Exit | Result |
|---|---:|---|
| `.venv312\Scripts\python.exe -m unittest discover -s tools -p 'test_*.py'` | 0 | 53 focused tests |
| `.venv312\Scripts\python.exe tools/local_proxy_probe.py` | 0 | 19 real-proxy scenarios; 20 solver HTTP attempts and 2 classifier HTTP attempts |
| `.venv312\Scripts\python.exe tools/proxy_budget_matrix.py` | 0 | 10 real-proxy budget/recovery scenarios |
| `.venv312\Scripts\python.exe tools/cost_report.py --config outputs/local-proxy/run-76347cbb5e8148d6b0f52805108b6356/budget.json` | 0 | Operator report; 22 attributed attempts, router-only coverage |
| `.venv312\Scripts\python.exe tools/prepare_tokenizer_cache.py` | 0 | Two existing public tokenizer assets match fixed SHA256; no download |
| `.venv312\Scripts\python.exe -m pip check` | 0 | No broken installed requirements |
| `py -3 tools/check_workspace.py` | 0 | Pre-receipt gate: 12 raw hashes, 17 Markdown files, 25 Python syntax checks; no API calls |
| `git -c safe.directory=C:/Users/Brandon/workspaces/litellm diff --check` | 0 | No whitespace errors; informational line-ending notices |

The final post-ingestion structural check is separately recorded in `wiki/log.md`. Earlier intentional RED failures and smallest repairs are retained there; they are not replaced by the final GREEN results.

## Scenario results

The 19 main scenarios all passed: free-to-paid fallback; per-attempt settlement; complete stream final usage; canceled stream retains bound; quota exhaustion rewrite; stale quota fails closed; unconfigured alias refusal; emergency fallback including failed billable charge; concurrent clients; shared alias/canonical/provider/deployment attribution; restart recovery; duplicate stream settlement; successful strict Jev selection; classifier failure retains unknown; wire output cap; partial usage retains reserve; incompatible quota target refusal; incompatible ordinary fallback refusal; output ceiling refusal.

The 10 matrix scenarios all passed: overall daily, overall monthly, model daily, model monthly, per-request ceiling; synchronized two-process admission and restart; combined classifier/solver request ceiling; missing-price startup rejection; stale-price startup rejection; kill-midflight/restart retention. Budget denials require structured HTTP429 and zero forbidden HTTP. Contention admits exactly one worker and rejects one while exposure=60, then settlement/restart are inspected. Jev final10 plus paid solver bound120 cannot fit request125; paid upstream delta=0. Crash retains60 and restart cannot dispatch another60 under daily100. These are synthetic nanodollar fixtures, not live limits.

Focused tests additionally cover unknown/conflicting usage, duplicate callbacks, stale price during reservation wait, midnight lock crossing/report snapshot, unsupported tools/surfaces/adapters, malformed quota counts, full policy identity, explicit history scopes, overlap/corrections/unknown coverage and legacy migration conflicts. Mock-focused checks supplement rather than replace real proxy proof.

## Final independent reviews

1. `/root/completion_review_one`: fresh review CLEAN, zero medium-or-higher findings after repairs. Independently ran53 tests, reviewed both real proof receipts and all recorded source hashes, and inspected the operator report. Earlier review was NOT CLEAN due to expiry race; that fix reset the clean count.
2. `/root/completion_review_two`: CLEAN within the supported local contract; zero medium-or-higher findings. Independently ran 53 tests and workspace checker, both exit 0. Verified 20/20 main source hashes, 7/7 matrix source hashes and 20/20 configuration hashes; inspected retained real-proxy assertions/receipts without rerunning the full harnesses. Standards: no material violations. No file edits. Live provider billing, clean-machine installation and deployment are not certified.

Consecutive independent clean reviews: **2**; no runtime changes between these final reviews. Reviews apply to supported bounded loopback contracts, not live provider billing guarantees.

## Configuration and local start

Use an isolated Python3.12 environment named `.venv312`; the current environment is verified, a fresh clean-machine install is not. Install pinned dependencies with `.venv312\Scripts\python.exe -m pip install -r requirements.txt`. Run tokenizer preparation with `--download` only when its checksum-only check reports missing public assets; this explicit setup command downloads public tokenizers, not inference. Downloads were not performed in this execution.

Run the two harness commands above. Each starts real temporary loopback LiteLLM proxy/fake upstream services, records proof and stops its processes. Child environments exclude inherited provider credentials, and a self-tested socket audit guard blocks external connects. This is the verified local start procedure, not a persistent live deployment recipe.

`COST_ROUTER_CONFIG` activates strict policy. It must satisfy `router/cost-router.schema.json`: explicit integer nanodollar limits, identical policy/shared local SQLite across workers, deployment IDs matching LiteLLM model_info IDs, dated bounded contracts and route membership/capabilities. Generated fixture `budget.json`/`proxy.yaml` demonstrate the exact shape; they refer to temporary servers that stop when the harness finishes. There are no default invented live paid limits. Without this variable, legacy routing has no strict-budget guarantee.

The report command reads only the local policy/SQLite file. Optional sanitized historical JSON is imported with `--openrouter-activity <path> --history-scope <scope> --history-disposition comparison-only|opening-balance|unresolved`; `--history-revision <integer>` records corrections; `--coverage-attestation <json>` accepts explicit reviewed scope/start/end evidence. It neither obtains account access nor treats absent history as zero. See `wiki/operations.md` for details.

## Precise remaining blocker and risks

The available live OpenRouter/alpha Decisions contract reports usage after execution but does not establish the verified pre-dispatch upper billable charge required here for every supported dimension. Strict mode therefore supports only the loopback fixed-bound contract and refuses live paid/classifier contracts. A token-price guess is not substituted. The full goal remains incomplete; live billing, deployment and real model quality are unverified. No user key or invented limit resolves this contract gap.

Router-only coverage excludes account activity outside this ledger. Available daily historical aggregates cannot establish a partial activation day; provider-period admission stays closed without sufficient explicit coverage. Policy changes against an existing ledger are refused pending deliberate reconciliation. SQLite workers must share a local file; separate hosts/network filesystems and large-scale performance are unverified. Unknown reservations may conservatively exhaust capacity indefinitely. Full clean-machine dependency/bootstrap reproduction and transitive lockfile reproducibility remain unverified.

## Changed files

- `.gitignore`
- `README.md`
- `raw/notes/2026-09-21-cost-aware-router-contract.md`
- `raw/notes/2026-09-21-cost-aware-router-research.md`
- `raw/notes/2026-09-21-local-delivery-receipt.md`
- `raw/notes/2026-09-21-other-routers-research.md`
- `raw/notes/2026-09-21-router-plan-execution.md`
- `raw/notes/2026-09-21-router-review-plan-evidence.md`
- `requirements.txt`
- `router/config.yaml`
- `router/cost-router.schema.json`
- `router/cost_guard.py`
- `router/cost_policy.py`
- `router/cost_transport.py`
- `router/jev_classifier.py`
- `router/openrouter_quota_guard.py`
- `router/spend_ledger.py`
- `tools/benchmark-classifiers.py`
- `tools/cost_report.py`
- `tools/discover-free-models.py`
- `tools/local_proxy_probe.py`
- `tools/prepare_tokenizer_cache.py`
- `tools/proxy_budget_matrix.py`
- `tools/test-models.py`
- `tools/test_budget_ledger.py`
- `tools/test_classifier_controls.py`
- `tools/test_cost_policy.py`
- `tools/test_dispatch_controls.py`
- `tools/test_history_reconciliation.py`
- `tools/test_router_repairs.py`
- `wiki/architecture.md`
- `wiki/classifier.md`
- `wiki/cost-awareness.md`
- `wiki/decisions.md`
- `wiki/evaluation.md`
- `wiki/index.md`
- `wiki/log.md`
- `wiki/open-questions.md`
- `wiki/operations.md`
- `wiki/quota-guard.md`
- `wiki/router-delivery-plan.md`
- `wiki/source-manifest.json`
- `wiki/sources.md`

## Measured environment

```json
{
  "python": "3.12.14",
  "packages": {
    "litellm": "1.99.0",
    "jsonschema": "4.26.0",
    "httpx": "0.28.1",
    "openai": "2.54.0",
    "fastapi": "0.141.1",
    "uvicorn": "0.53.0",
    "tiktoken": "0.14.0",
    "aiohttp": "3.14.3",
    "pydantic": "2.13.5"
  }
}
```

## Retained immutable proof copies

Original local proof: `outputs/local-proxy/run-76347cbb5e8148d6b0f52805108b6356/proof.json`. SHA256 `88d1f2d1b9f9a413f96c43189c7bdd22d7d080fe1bddb05cf22987b2a6e008ab`.

```json
{
  "litellm": "1.99.0",
  "python": "3.12.14",
  "scenario": "real-proxy-http-smoke",
  "status": 200,
  "upstream_attempts": 20,
  "classifier_attempts": 2,
  "result": "PASS",
  "scenarios": [
    "free-to-paid fallback",
    "per-attempt settlement",
    "stream final usage",
    "cancel retains bound",
    "quota exhaustion rewrite",
    "stale quota fails closed",
    "unconfigured alias refuses dispatch",
    "emergency fallback",
    "concurrent clients",
    "shared aliases and provider deployment attribution",
    "restart recovery",
    "duplicate stream settlement",
    "strict Jev selection",
    "classifier failure retains unknown reservation",
    "output cap enforced on wire",
    "partial usage retains reservation",
    "incompatible quota target rejected",
    "incompatible fallback rejected",
    "output ceiling prevents dispatch"
  ],
  "ledger": "C:\\Users\\Brandon\\workspaces\\litellm\\outputs\\local-proxy\\run-76347cbb5e8148d6b0f52805108b6356\\spend-093db1e2c28d409c8380b71725acc9b1.sqlite",
  "source_sha256": {
    "router/cost_guard.py": "852aebcc94ac6a9cbbc481d19f272a860dbb50e897f1363221234505166c05a9",
    "router/cost_policy.py": "f81e8f55465887977e063d0c4f22ae699521cdefe3704d9a24fe5f90c114df45",
    "router/cost_transport.py": "b197abbc7442f5919fb9233fa2add5fb591b57a627df3d4f71ca7d4d13f1fdbf",
    "router/jev_classifier.py": "ed69714f294379af6b1e12f89ffea86dd7a7b9403210ca513c7ea54039393c07",
    "router/openrouter_quota_guard.py": "b48acfd8edb3670c34a7cc15d5adabe015984cd1a01b859503e3e6ad9e92c2f6",
    "router/spend_ledger.py": "07693345d96d14edf34ce9b495fcf1d8ada164b6a95e8db7702bb7cce3092165",
    "tools/benchmark-classifiers.py": "552208a8ce2c95f7443e7cb56a3abe3f5bd9b5c8e4786501fd9e47e5fff38fc5",
    "tools/check_workspace.py": "9a01a75a8ae541a63a9b06c068de15d939b5b0c02717e6c3450ddf329afeae4a",
    "tools/cost_report.py": "c12fb06ff0a886f9b5e4825ce40ba9769ff62eccb029b4a02b067b63e458bcc7",
    "tools/discover-free-models.py": "3eedff131ce03b166dc22f6cc0288315893184465b1a1e72a5a5cd7850364055",
    "tools/local_proxy_probe.py": "78fef6f81da0228b0cfc006ef47fb193fd9d691db5abe63a40f1593172503084",
    "tools/prepare_tokenizer_cache.py": "b36b8de41eea7d43f198c24711c4e27f61486f94a345c024044bf54ae16ae5ea",
    "tools/proxy_budget_matrix.py": "b532977c10383620ea18c3475d650f6f3145fe2383819042a1b5502c6b0794f9",
    "tools/test-models.py": "adee5b0ae0a1b6d83ddb7cb4bf994596a853ca84e73dd0050a639fc92048c1b1",
    "tools/test_budget_ledger.py": "c49c2f45408cfbc1aaf3975115c4af3d09b5993a5b1dfd5e95ce56beb6314575",
    "tools/test_classifier_controls.py": "08c11f45a0ac1d785b08cb7d55acaf2ab4a989744feafefdf90b99ac34d1bb2c",
    "tools/test_cost_policy.py": "fd7ba9af0906290e82472a917308231c5558b53a205a2ef0ad209642f3ff0cab",
    "tools/test_dispatch_controls.py": "bc9bb76cad8a7a1810e890f5e3ee2801758aa7d56024bab1b7851fd43933e3ad",
    "tools/test_history_reconciliation.py": "0103bcfd8b245b686e993b6ce4044aa2feb08791196d44b1d8c03341a24aeb24",
    "tools/test_router_repairs.py": "cff8732b6916a122bfec779a5802a08ae86bbf9cdb1b9e6072a23c1de685efa7"
  },
  "policy_sha256": "57b48afa4f9f4b99a847ef961687db1f767c452b3a31ec88475c79aaaf07a4f8"
}
```

Original local proof: `outputs/budget-matrix/38cf874ea4344300b6f85e1722157de6/proof.json`. SHA256 `5022c5b02d1de007f94fc06c78c7dc3a73aa6957e8a92cc10e1cde6b949b4673`.

```json
{
  "result": "PASS",
  "python": "3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]",
  "litellm": "1.99.0",
  "scenarios": [
    {
      "scenario": "overall-daily",
      "status": 429,
      "upstream_delta": 0,
      "error": {
        "error": {
          "message": "{\"code\": \"cost_budget_denied\", \"reason\": \"No priced, capability-compatible candidate has remaining budget\"}",
          "type": "None",
          "param": "None",
          "code": "429",
          "provider_specific_fields": {
            "code": "cost_budget_denied",
            "reason": "No priced, capability-compatible candidate has remaining budget"
          }
        }
      }
    },
    {
      "scenario": "overall-monthly",
      "status": 429,
      "upstream_delta": 0,
      "error": {
        "error": {
          "message": "{\"code\": \"cost_budget_denied\", \"reason\": \"No priced, capability-compatible candidate has remaining budget\"}",
          "type": "None",
          "param": "None",
          "code": "429",
          "provider_specific_fields": {
            "code": "cost_budget_denied",
            "reason": "No priced, capability-compatible candidate has remaining budget"
          }
        }
      }
    },
    {
      "scenario": "model-daily",
      "status": 429,
      "upstream_delta": 0,
      "error": {
        "error": {
          "message": "{\"code\": \"cost_budget_denied\", \"reason\": \"No priced, capability-compatible candidate has remaining budget\"}",
          "type": "None",
          "param": "None",
          "code": "429",
          "provider_specific_fields": {
            "code": "cost_budget_denied",
            "reason": "No priced, capability-compatible candidate has remaining budget"
          }
        }
      }
    },
    {
      "scenario": "model-monthly",
      "status": 429,
      "upstream_delta": 0,
      "error": {
        "error": {
          "message": "{\"code\": \"cost_budget_denied\", \"reason\": \"No priced, capability-compatible candidate has remaining budget\"}",
          "type": "None",
          "param": "None",
          "code": "429",
          "provider_specific_fields": {
            "code": "cost_budget_denied",
            "reason": "No priced, capability-compatible candidate has remaining budget"
          }
        }
      }
    },
    {
      "scenario": "request",
      "status": 429,
      "upstream_delta": 0,
      "error": {
        "error": {
          "message": "{\"code\": \"cost_budget_denied\", \"reason\": \"Per-request ceiling exceeded\"}",
          "type": "None",
          "param": "None",
          "code": "429",
          "provider_specific_fields": {
            "code": "cost_budget_denied",
            "reason": "Per-request ceiling exceeded"
          }
        }
      }
    },
    {
      "scenario": "two-workers-and-restart",
      "accepted": 1,
      "denied": 1,
      "inflight_exposure": 60,
      "final_exposure_after_restart_request": 40
    },
    {
      "scenario": "classifier-plus-solver-request-ceiling",
      "request_limit": 125,
      "classifier_final": 10,
      "paid_bound": 120,
      "paid_upstream_delta": 0,
      "status": 429
    },
    {
      "scenario": "missing-price",
      "startup_exit": 3,
      "diagnostic": "'output_nanos_per_token' is a required property",
      "upstream_delta": 0
    },
    {
      "scenario": "stale-price",
      "startup_exit": 3,
      "diagnostic": "billing_contract_invalid",
      "upstream_delta": 0
    },
    {
      "scenario": "crash-midflight-restart",
      "retained_exposure": 60,
      "upstream_delta_after_restart": 0
    }
  ],
  "upstream_attempts": 4,
  "source_hashes": {
    "tools\\proxy_budget_matrix.py": "b532977c10383620ea18c3475d650f6f3145fe2383819042a1b5502c6b0794f9",
    "router\\cost_guard.py": "852aebcc94ac6a9cbbc481d19f272a860dbb50e897f1363221234505166c05a9",
    "router\\cost_transport.py": "b197abbc7442f5919fb9233fa2add5fb591b57a627df3d4f71ca7d4d13f1fdbf",
    "router\\spend_ledger.py": "07693345d96d14edf34ce9b495fcf1d8ada164b6a95e8db7702bb7cce3092165",
    "router\\cost_policy.py": "f81e8f55465887977e063d0c4f22ae699521cdefe3704d9a24fe5f90c114df45",
    "router\\jev_classifier.py": "ed69714f294379af6b1e12f89ffea86dd7a7b9403210ca513c7ea54039393c07",
    "tools\\local_proxy_probe.py": "78fef6f81da0228b0cfc006ef47fb193fd9d691db5abe63a40f1593172503084"
  },
  "configuration_hashes": {
    "classifier-and-solver-request\\policy.json": "7c187a85b330aa037379680118c81b9a45b0c40dc5e11603fad976adff97a786",
    "crash-recovery\\policy.json": "2421bedb324dbeb3ce49be483755982ba2287a3ded1d6709bb2e7033755df2d4",
    "missing-price\\policy.json": "280d32b97911a6db9dfb4ab64d993fe1f72ebc3fe68996919ee06958d0597e92",
    "model-daily\\policy.json": "c7bd55905e75742d3f9c5077a29f765a62915ef4ed6d442c6f8dbba150ad9a32",
    "model-monthly\\policy.json": "35c914bce0cd8723b7701ae008b3ce740b609a50168770682a3595b2036b8c81",
    "overall-daily\\policy.json": "68d32406646731a7863f1d0ef27155699994d7cbeb64228b33f76ec30c0bf26c",
    "overall-monthly\\policy.json": "c691ef6ddf5ae32a382668310e7b87b06aead0706773bcaa1454a5cdbc294e2c",
    "request\\policy.json": "fd42d20fb3401d9b5f17697bd0dd64d1b966add7601cc8947783cba206ffaf04",
    "stale-price\\policy.json": "62940e120eda023e1b660d523ce119a8a6ed268655575c309ee21236d174f779",
    "workers\\policy.json": "868b942ef7abb479ba7a005a46a8a04ba9086e48107d5ef86b5732697399ad2f",
    "classifier-and-solver-request\\proxy.yaml": "f23d500584834484e53f325d3a40c8589fa703c9d78899739f2d37e0944091f6",
    "crash-recovery\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "missing-price\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "model-daily\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "model-monthly\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "overall-daily\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "overall-monthly\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "request\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "stale-price\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc",
    "workers\\proxy.yaml": "aa053ed5b2d527b41845523085db5f7df2a8c4bea73069013bff173991db8bfc"
  }
}
```

Source maps and matrix configuration hashes were recomputed against the frozen files with zero mismatches. The operator report is retained beside the main proof as `operator-report.json`.

# Routing policy and contracts

Status: observed configuration, 2026-09-20; upstream availability unverified.
Sources: [config.yaml](../raw/config.yaml) (`model_list`, `router_settings`),
[health checker](../raw/test-models.py) (`CONTRACTS`, `ALIASES`),
[discovery](../raw/discover-free-models.py) (`TIERS`).

## Classification tiers

Each capability combines with EFFICIENT or CAPABLE. Tier names map to the matching
`free-<capability>-<strength>` alias, for example `CODING_CAPABLE` →
`free-coding-capable`. The current aliases may share the same concrete solver;
different tier names do not establish different model quality.

| Capability | EFFICIENT target / hard seconds | CAPABLE target / hard seconds |
|---|---:|---:|
| GENERAL | 1.5 / 4 | 3 / 8 |
| REASONING | 2 / 5 | 4 / 10 |
| AGENTIC | 1.5 / 4 | 3 / 8 |
| CODING | 1.5 / 4 | 3 / 8 |

These are small-probe contracts, not maximum completion times for arbitrary tasks.
The eight discovery tiers require at least 128,000 advertised context tokens;
agentic tiers additionally require advertised tools. Config descriptions mention
97.5–98% availability targets, while health-check acceptance uses 95%; this remains
an [unresolved contract difference](open-questions.md).

## Ordered fallbacks

For each capability, the efficient free alias falls through its free backup, free
capable pair, paid efficient pair, paid capable pair, then `paid-emergency`.
The capable free alias starts at its own backup and then the paid capable pair and
emergency. Each backup's list starts at the next step. Paid aliases remain on paid
paths. `jev` itself falls back to `paid-general-capable`, its backup, then emergency.

`num_retries: 0`, `allowed_fails: 2`, and `cooldown_time: 15` are the imported router
settings. Zero retries does not remove the configured fallback lists.

## Specialized and emergency routes

| Alias family | Path | Probe target / hard seconds |
|---|---|---:|
| `fast` | fast → fast-backup → paid-fast → paid-fast-backup → paid-emergency | 0.8 / 2 |
| `vision` | vision → vision-backup → paid-vision → paid-vision-backup → paid-emergency | 2 / 5 |
| `compression` | compression → compression-backup → paid-compression → paid-compression-backup | 3 / 8 |
| `free-emergency-capable` | OpenRouter free router → paid-emergency | 5 / 10 |
| `paid-emergency` | `openrouter/openrouter/auto`; no further fallback configured | 5 / 10 |

Compression has no generic emergency fallback in this config. Discovery requires
one million advertised context tokens for compression, but its probe is much
smaller; it does not validate full-window quality. Vision's generic emergency path
has no supplied evidence of image compatibility.

The full alias-to-model mapping is maintained in [working config](../router/config.yaml),
with baseline expectations duplicated in [health checks](../tools/test-models.py).
Change and verify both together. Current model slugs are imported choices, not
live recommendations or verified prices.

Related: [classifier](classifier.md), [quota guard](quota-guard.md), [evaluation](evaluation.md).

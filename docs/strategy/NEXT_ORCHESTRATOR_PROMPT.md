# Next orchestrator kickoff — integrate D-149 G4 closure, then contract direct MapLight reauthentication

The current objective is the strongest scientifically defensible path to a
competitive OpenADMET CYP 2026 submission. Global-v2 is closed: G2-7G is
permanently UNDERPOWERED before science, selected no candidate or runner-up,
and opens no G2-8 authority. The distinct Global-v3 `EXP-G4-GIN300` lane is
also permanently closed before claim consumption under D-149 status
`G3_2_EXP_G4_GIN300_PRECLAIM_CLOSED`. Do not implement, retry, repair,
replace, or redesign G4.

The active backout is separate: first integrate the exact D-149 terminal
record, then prospectively contract a read-only reauthentication of the already
accepted direct MapLight candidate. That route preserves the strongest
validated internal baseline without calling it selected or robustness-accepted
and without reopening G2-8. No portal or upload authority is active.

## Restore authoritative context first

Read completely, in order:

1. `AGENTS.md`;
2. `docs/strategy/PROJECT_STATE.md`;
3. `docs/phases/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/strategy/PROJECT_CHARTER.md`;
6. D-076, D-147, D-148, and D-149 in `docs/strategy/DECISIONS.md`;
7. the final relevant rows of `runs/experiment_ledger.csv`;
8. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_contract.json`;
9. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_capability_contract.json`;
10. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json`;
11. `tests/test_openadmet_global_v3_g4_gin300_transition_rejection.py`;
12. `benchmarks/openadmet_cyp_2026/DIRECT_BASELINE_HANDOFF.md`.

D-147 is immutable integrated scientific-contract history at signed commit
`b5cf47c6bc8ccc2dc29c7167b1a436d792338509`; PR #184 CI run `33327853790`
and exact-SHA post-main CI run `33328374514` are green. D-148 is immutable
integrated capability-contract history at signed commit
`f0f3b6f9380eebef0b03d87f29eb659ffc84f8d5`; PR #185 CI run `33337794223`
and exact-SHA post-main CI run `33338342415` are green. Their prospective
implementation/run schedule never activated and is superseded by D-149's
terminal preclaim closure.

Treat signed Git history, canonical tracked bytes, and exact public receipts as
authority. Do not open a protected path merely to refresh context. Never
inspect, import, copy, execute, patch, or derive code from a barred runner or
driver. D-127/D-128 and every closed G2-7 path remain barred.

## Exact D-149 terminal record

The record schema is
`cypshift.openadmet_cyp_2026.global_v3_g4_gin300_transition_rejection.v1` and
its status is `G3_2_EXP_G4_GIN300_PRECLAIM_CLOSED`.

- Rejection record:
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json`,
  SHA-256
  `10a7f783d73ae60c6da479ffbd8cd3e3443b3f8dace88e177fd9c17c44e1331c`,
  14,871 bytes / 276 LF.
- Strict public rejection test:
  `tests/test_openadmet_global_v3_g4_gin300_transition_rejection.py`,
  SHA-256
  `f033a7577dca4eafd3cec979938292fcb0d7b6ef80f0e86d6134fc8d9f4d944f`,
  43,378 bytes / 1,226 LF, focused result `4 passed`, and 76 independent
  fail-closed mutations.

Ruff check/format, Python 3.10 AST parsing, temporary compilation, and
exact-scope diff checks are green. Recompute every identity from the final
worktree; do not trust prose alone. Parse the record
with duplicate-key, BOM, nonfinite-number, negative-zero, non-UTF-8, and
trailing-byte rejection and require exact canonical UTF-8 bytes plus terminal
LF.

The following attempted prospective identities are permanently rejected and
non-integrable:

- transition contract SHA-256
  `2c11b90d08038a05efd01bd40cb92ac79bc74544cc67807d2dd9b09111fa94af`,
  72,296 bytes / 582 LF;
- transition static test SHA-256
  `0c685112421929b715912450e8eeb0e8e7ae5534806c19a7bee8fac6ecdada2d`,
  67,654 bytes / 1,905 LF;
- corrected transition contract SHA-256
  `1def7c6c31a84508e8d50f67a817ff486c30fad3f502dbefcc094e7b6ea7615f`,
  79,319 bytes / 646 LF.

None was integrated. None grants implementation, execution, claim, result,
model-quality, scientific, submission, or portal authority. Do not recreate or
repair them, use them as implementation bases, or carry their prospective
launcher/supervision design into current instructions.

## Why G4 is closed

Independent terminal audit showed that the attempted transition's
unqualified zero-accounting claims could not truthfully describe its own
public repository validation. A green suite does not prove zero network,
download, import, internal model operation, or cache effect unless those facts
were instrumented. The final prospective correction boundary was therefore
falsified before claim consumption. The correct outcome is permanent G4
closure, not another transition contract.

The first bounded safe suite passed `1452 passed, 14 skipped, 0 failed` in
358.81 pytest seconds / 359.31 wall-seconds at 900,212 KiB maximum RSS. Its
aggregate raw network transactions/bytes, downloads, package imports, internal
scientific/model operations, and cache effects were not instrumented or
retained. Every such total remains unknown and must not be guessed.

With `UV_OFFLINE=1` configured, one isolated build produced a 338,214-byte
sdist and a 406,405-byte wheel. Their hashes are incidental and non-frozen.
One temporary CPython 3.12.3 environment installed four cached distributions:
`cypshift 0.2.0.dev0`, NumPy 2.5.2, Pillow 12.3.0, and RDKit 2026.3.5. No
download was observed, but raw build/install network transactions and bytes
were not instrumented and remain unknown.

Two successful explicit public-fixture audit/train/predict/report roots were
byte-identical at 9 files / 36,758 bytes each. Each reported 7 accepted,
1 quarantined, 7 warnings, 3 supported, 1 unsupported, and 21 predictions, for
exactly 2 train, 2 predict, 2 report, and 42 prediction operations. Internal
library fit/metric/import totals, build-isolation environment/cache counts, and
global cache mutation/access-time effects were not instrumented and remain
unknown. One pre-audit failed closed on an already-existing path before it
reported work. The preexisting ignored `.mypy_cache/3.12/cache.3.db` was
observed modified, but the exact mutating operation was not instrumented and
remains unknown; the authoritative mypy rerun used temporary state. Every
explicit task temporary root was deleted and is absent.

After record/test freeze and before ledger mutation, the exact eight pre-ledger
identities were unchanged across command `PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=1 /usr/bin/time -v uv run --locked --offline --no-sync pytest -p no:cacheprovider --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`.
It exited 0 with `1453 passed, 14 skipped, 0 failed` in 345.74 pytest seconds /
346.19 wall-seconds at 904,176 KiB maximum RSS. These offline controls do not
convert uninstrumented raw network, cache, or import totals into zero.

These are public CI operations, not G4 execution. The fixed G4 vector is
comprehensive zero: all seven restricted roots and seven future implementation
paths stayed absent; no isolated runtime/wheel, checkpoint/model body or tensor,
scientific import, parity process, graph, embedding, synthetic root, fit,
prediction, official/private/confirmatory/blinded-test/TDI read, metric,
bootstrap, selection token, contender, systemd unit, delegated cgroup, claim,
result, submission, validator, leaderboard-selection observation, portal
credential, upload, or GPU use occurred. G4 remains preclaim and has no retry,
repair, replacement, relaxed accounting, alternate contract, or outcome-driven
successor.

## Exact D-149 package

D-149 changes exactly nine paths:

1. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json`;
2. `tests/test_openadmet_global_v3_g4_gin300_transition_rejection.py`;
3. `benchmarks/openadmet_cyp_2026/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/phases/README.md`;
6. `docs/strategy/DECISIONS.md`;
7. `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`;
8. `docs/strategy/PROJECT_STATE.md`;
9. `runs/experiment_ledger.csv`.

The ledger is bound at SHA-256
`515801a45120ea07fada9b3193a4f10614074b77674d0f3b0ea0c01dabaa26fa`
(437,803 bytes / 200 LF). Its unchanged 431,853-byte prefix has SHA-256
`53def734ac3bb96d83fb8af2f7c37d42504382caacc63f2e2395f115e0aace56`;
the sole appended 18-field row has SHA-256
`0bd57d22c25b5162ca811e0dde542c4a45abee27d4f21662bd2c21c1a2992baf`
(5,950 bytes including LF). Its compact `config` and `metrics` JSON round-trip
exactly, and visual audit is clean.

No implementation, isolated-project lock, capability result, claim, model,
runtime, or submission artifact belongs in this package. Prove every other path
absent from the diff. A defect in the record/test/narrative package blocks
integration but cannot reopen G4.

## Competitive backout

Historical receipts describe the accepted direct MapLight candidate that is the
concrete submission backout:

- submission SHA-256
  `9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`;
- manifest SHA-256
  `96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6`.
- immutable tracked handoff SHA-256
  `6a9402ca3fdf02dbcad079cba82162132e5b149f6adf69f80ea05d177e1ecec4`,
  2,919 bytes / 55 LF.

It was accepted after two independent byte-identical four-endpoint rehearsals,
contains 750 ordered rows and 3,000 finite predictions, and historically passed
the pinned competition validator with zero errors. Fixed MapLight remains the
strongest validated internal baseline at component-macro MAE
`0.5837812652150708`.
Those are meaningful historical receipts. The MAE is prior internal development
evidence, not an official or leaderboard score, reselection, or robustness
result. The receipts do not make MapLight selected or robustness-accepted by
G2-7G, do not create a G2-8 contender lock, and do not open G2-8. Current
private candidate existence and bytes are deliberately unknown and unopened;
the candidate is not currently reauthenticated or upload-ready.

The next milestone is a new exact nine-path contract-only package:

1. `benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_handoff_contract.json`;
2. `tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py`;
3. `benchmarks/openadmet_cyp_2026/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/phases/README.md`;
6. `docs/strategy/DECISIONS.md`;
7. `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`;
8. `docs/strategy/PROJECT_STATE.md`;
9. `runs/experiment_ledger.csv`.

That contract-only package may bind the immutable handoff and historical
candidate receipts against current public requirements. It performs zero
private candidate read, validator call, portal/credential access, or upload and
does not claim current private-byte existence. A future one-use read-only
reauthentication result is a separate milestone. Any upload remains a later
human-authorized operation. Do not mutate or regenerate the candidate or use
leaderboard/private-portal state for model choice.

## Exact next action

1. Recompute the exact record/test hashes, byte counts, and LF counts; require
   canonical JSON, the focused rejection test, stale-live-G4 scans, exact
   nine-path scope, and the bounded repository-safe checks. Preserve truthful
   known/unknown public-CI accounting.
2. Create one coherent SSH-signed `zchboswell` D-149 commit with no AI
   attribution. Push it, open an exact-head pull request, and require all checks
   on that signed head.
3. Recheck mergeability and integrate locally by fast-forward only. Do not use
   GitHub's hosted rebase merge. Push `main` without rewriting the commit and
   require green exact-SHA post-main CI.
4. Only then draft the exact nine-path direct-baseline reauthentication-handoff
   contract package above. Keep it contract/static evidence only, with zero
   private candidate read, validator call, portal/credential access, or upload.

Throughout D-149, do not access official structures or targets, baseline OOF
rows, confirmatory truth, historical row-level artifacts, blinded-test bytes,
TDI, private portal state, credentials, leaderboard observations, or upload
capabilities. Do not call MapLight selected, retained by G2-7G, or robustness-
accepted. Do not reopen G2-8. `global_TDI` remains only the frozen TDI fallback.

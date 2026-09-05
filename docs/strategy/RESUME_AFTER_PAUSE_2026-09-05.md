# Restart checkpoint — paused September 5, 2026

The user explicitly requested a pause. All agents and project compute stopped;
`cypshift-recovery-and-releases` is PAUSED. No second TDI seed, production fits,
new environment installation or further GPU profiling is authorized while paused.
Wait for the user to resume. No new upload file is ready; **glhf** remains current.

## Repository checkpoint

Passing integrated main is signed `c756a508b546983f12284884567ddad44341b509`.
PRs #198 and #199 passed all three Python CI jobs before local fast-forward and
push. This results checkpoint is on `codex/phase3-next-results`; inspect its PR
checks before integration. Do not wait for or merge pending CI during the pause.

The tested but unfinished production driver is preserved separately on
`codex/tdi-production`, worktree `/tmp/cypshift-tdi-production`, as a draft PR.
It has two new Python files and 25 passing combined TDI tests. It still pins
audit V2: update those pins to the approved V3 identities below and validate the
qualification boundary before any use. It has performed no production fits.

## First work after explicit resume

1. Read PROJECT_STATE, active phase, charter and relevant decisions. Inspect Git,
   private `active-compute.json`, actual processes and results before launching.
   Review/integrate the passing results checkpoint; retain all historical failures.
2. Prioritize TDI: the first 80-fit seed is complete and independently audited.
   Run the unchanged second seed 20260906 under D-162, then audit it with the
   same frozen V3 script and plan. Both-seed qualification is still required.
3. If qualified, finish the production driver and independently review it. Seal
   both-seed qualification; production requires 8 logistic or 14 selected-procedure
   fits, fresh checkpoint replay, current public-validator/source verification,
   and an actual immutable 750-row CSV before the manual upload handoff.
4. In parallel with useful CPU computation, review the private CheMeleon readiness
   plan. Dependency resolution alone is complete; no installation or inference
   has occurred. Freeze and run bounded isolated synthetic readiness before any
   new official-data experiment. Keep the working GPU and legacy environments.
5. Reassess safe memory headroom before retrying synthetic GPU concurrency work.
   The previous attempt stopped before a single fit. Do not infer a speedup or
   relax limits from GPU utilization alone. Reactivate monitoring only after
   explicit user resume, preserving meaningful-change-only notifications.

## Evidence worth carrying forward

- **TDI promising, not yet qualified:** internal public-wrapper macro MCC
  0.1456377965 logistic versus 0.1717317899 selected; gain 0.0260939934;
  paired-family 95% gain interval [0.0024858401, 0.0516373898]. All 80 saved models
  replay exactly; all 20 independent threshold checks and OOF metrics match.
- **Both small MLP recipes retired:** descriptor recipe failed both repeats;
  Morgan-only failed all first-seed incumbent gates and triggered frozen futility.
  All 105 Morgan-only checkpoint predictions replay exactly. Do not repeat these
  recipes or generate their production CSVs.
- **GPU profile unmeasured:** memory preflight found about 6.52 GB free in the
  shared slice, below the required 8 GiB, mainly due to charged file cache.
  Zero GPU fits, no throughput recommendation; all three services used 0.511 CPU
  seconds. No global cache flush or memory-limit changes were performed.
- **Graph hypothesis prepared only:** generic MIT-licensed CheMeleon checkpoint
  is hash-verified, 34,859,448 bytes and 8,714,240 finite parameters. Chemprop 2.2.1
  dependency closure preserves all 19 GPU pins and proposes 45 new wheels
  (134,987,052 bytes). No new environment was installed. This generic asset differs
  from the historical failed CYP-finetuned container attempt.

## Private restart map

Base: `/home/zbos/cypshift-private/openadmet-2026/phase3/`.

- `tdi-v1/`: complete first seed, source signed c756a50; experiment SHA
  `d7b89d9170fa8d2848c67076c24a3c09e32497f1369e65f621b00497be0b0857`.
- `tdi-independent-audit-v3/`: script SHA
  `c6839f3a754eee0f665200d26ac2299bf8cd9df172613720fb4a170450b866ce`;
  plan SHA `095ddb0e73b930222d8cf25b33c4c7453444e0938909ad100029be1720ee35a1`;
  passed `repeat1/result.json` SHA
  `2fccc8f008c316263e6ba7f50bdb93b02fb629473fcf412e78c8491c975590c3`.
  Read `repeat1-authorization-and-disclosure.json`: the report inherited stale
  V2 prose. A read-only edit failed but the following command still launched the
  approved V3 behavior; the separate disclosure corrects the prose without
  changing frozen evidence. V3 permits only three named CatBoost metadata fields,
  original within one float64 ULP of float32 expansion and saved value with the
  same float32 bits. Inference tolerance remains 1e-12; measured error is zero.
  Preserve failed V1/V2 audits (21.93/22.13 CPU seconds), passed V3 (51.28), and
  metadata diagnosis (0.36919 process CPU seconds). Ensure these audit costs are
  registered once in cumulative resource accounting before future fits.
- `tdi-protocol-preparation-v1/QUALIFICATION_SCHEMA_EXAMPLE.json`: nonexecutable
  placeholders for the required root-sealed both-seed qualification receipt.
- `mlp-morgan-only-v1/` and `mlp-morgan-only-preliminary-v1.json`: completed
  negative experiment and canonical futility result, no repeat 2.
- `deep-audit-20260905/mlp-worker-concurrency-profile-v1/`: frozen plan, driver,
  synthetic arrays, preflight failure and resource receipt; no model run.
- `chemeleon-foundation-readiness-v1/`: asset receipts, CPU-only checkpoint
  metadata, `RUNTIME_PLAN.md`, `dependency-resolution.json` and hashed pylock.
  Closure SHA `d1e25a578bf17e8346088ec7f4a8a7712d75fae1890f79a9008972f2d4352e1e`;
  runtime-plan SHA `dacbcea1207f41f8d1b38dfbb96fd001aa724f5afb664b19219fbd7ae8fcb70d`.
  Resolver cache was reclaimed; original wheels/environments remain intact.

The reserved 997 molecules remain closed. Public leaderboard evidence stays
secondary to frozen internal validation. Official data, models and predictions
remain outside Git. Keep CPU at or below 24 equivalents, shared RAM 20 GiB,
private storage 100 GB and program CPU 1000 core-hours; full GPU compute is
authorized after resumption within those host limits.

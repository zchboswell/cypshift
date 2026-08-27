# Next orchestrator kickoff — G2-7G formal acceptance gate

This handoff becomes active only after D-134 is integrated on `main` through
the repository's signed fast-forward-only workflow and the post-main Python
3.11, 3.12.3/MapLight, and 3.14 CI matrix is green. Until then, finish only
that integration and do not run the formal acceptance.

The long-term objective remains the smallest scientifically defensible path to
a materially better OpenADMET CYP 2026 submission. Frozen family-safe evidence
outranks leaderboard evidence. Fixed MapLight remains the best validated system
at internal component-macro MAE `0.5837812652` (reported as `0.5838`). D-134 is
implementation evidence only and does not change model quality.

## Restore authoritative context first

Read and follow `AGENTS.md`, then read in order:

1. `docs/strategy/PROJECT_STATE.md`
2. `docs/phases/README.md`
3. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`
4. `docs/strategy/PROJECT_CHARTER.md`
5. D-122 through D-134 in `docs/strategy/DECISIONS.md`
6. the final rows of `runs/experiment_ledger.csv`

Treat the live clean `main` worktree as authoritative. The rejected G2-7B
runner and driver remain immutable barred history and may not be opened,
imported, copied, executed, patched, benchmarked, or used to derive code.

## Exact integrated implementation receipts

- scientific runner:
  `dca9b8d1be51a29fa4e2269949d1f3339ecf14d99b91f203aa2cacdd2ca90bde`
- official one-use driver:
  `1675336e449ba9a8327406cb37f82f08e3547076ce6c69fa0ade70c5a3de57fc`
- fixed formal acceptance driver:
  `7cb471ce6c39e4633b91556cd2c09ee7406dd39912b5d69200fad9372a42e473`
- focused tests:
  `3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f`

D-134's nine focused tests and exact 55-test relevant suite pass. The two
independent test-only profiles invoked 720 and 1,020 model doubles, retained one
selection token and no runner-up per path, enforced exact paired joins and all
endpoint diagnostics, and measured 56 tutorial-metric calls per path against
the frozen maximum of 80. No formal record, official operation, real CatBoost
fit, scientific development metric, claim consumption, submission, or upload
occurred.

The formal driver statically enforces two opposite-order roots, both profiles
per root, 3,480 total model-double identities, byte-identical model/scorer and
aggregate-terminal maps, exact M0/full and deterministic M2/Avalon deletion
profiles, exactly two ordered real CatBoost controls, cumulative supervision,
owned-only cleanup, and zero official or claim operations. Do not reinterpret
those synthetic values as model-quality evidence.

## Next exact gate

From clean synchronized `main`, first authenticate all four receipts above and
the green post-main CI run. Then confirm only that these public fixed paths are
absent:

- `/tmp/cypshift-g2-7g`
- `benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_execution_acceptance_v2.json`
- `benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_execution_acceptance_rejection_v2.json`

If and only if those preconditions hold, invoke the fixed acceptance driver
exactly once, with no root or output arguments, under the repository's Python
3.12.3 environment:

```text
uv run --python 3.12.3 python research/maplight-fixed/run_global_v2_maplight_robustness_execution_acceptance_v2.py
```

Do not run it from an implementation branch. Do not retry, repair, resume,
move, overwrite, or reinterpret the attempt. If it rejects, stop and preserve
only the aggregate rejection. If it accepts, stop again: package the aggregate
acceptance receipt in a separate reviewed signed milestone and require green
post-main CI before deriving or consuming any private official claim.

## Hard boundaries

- Do not mutate the tracked claim or fill its five null future hashes.
- Do not open, list, hash, or copy official source or baseline bytes.
- Do not run the official 720–1,020-fit battery.
- Do not access confirmatory truth, historical row-level artifacts, blinded
  test, or TDI data.
- Do not generate or upload a submission or call an official metric.
- Do not use private leaderboard or prior-submission evidence for selection,
  and never publish any private submission identifier, score, or rank.
- Do not add candidates, features, seeds, groups, calibration, blends, clips,
  retries, caches, concurrency, frameworks, or services.

The D-127 claim/root and D-128 attempt remain permanently barred. EXP-G3 and
G1/G2/M1/X1/T2 plus immutable R5D/I0 remain closed; `global_TDI` remains only
the TDI fallback.

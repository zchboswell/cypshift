# Next orchestrator kickoff — integrate D-140, then implement D-141

This handoff becomes active on the contract-only D-140 source-shape transition
branch. Signed D-139 commit `3b9c251f6875fedb33e51c4420cd8634c6e4cf29` is
integrated and exact-SHA post-main CI run `33103967048` is green across Python
3.11, 3.12.3, and 3.14. Review, integrate, and require green post-main CI for
the exact D-140 contract before packaging any D-141 implementation byte.

The objective remains the smallest scientifically defensible path to a
materially better OpenADMET CYP 2026 submission. Frozen family-safe evidence
outranks leaderboard evidence. Fixed MapLight remains the best validated
system at internal component-macro MAE `0.5837812652`. D-135 is immutable
science-kernel mechanics evidence, D-136 is historical test provenance, D-137
is the driver-only repair contract, D-138 corrects the seal order, and D-139
freezes the first exact historical-test transition. D-140 adds only the two-node
source-shape transition exposed by safe-suite negative evidence. None is
implementation or model-quality evidence.

## Restore authoritative context first

Read and follow `AGENTS.md`, then read completely in order:

1. `docs/strategy/PROJECT_STATE.md`
2. `docs/phases/README.md`
3. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`
4. `docs/strategy/PROJECT_CHARTER.md`
5. D-122 through D-140 in `docs/strategy/DECISIONS.md`
6. the final relevant rows of `runs/experiment_ledger.csv`
7. the exact G2-7G contract, claim, D-135 receipt, D-136 bridge, D-137 repair
   contract, D-138 seal erratum, D-139 test-transition contract, and D-140
   source-shape transition contract

Treat clean synchronized `main`, immutable receipts, exact-SHA CI, and exact
fixed-root existence checks as authoritative. If a one-use attempt already
exists or the claim appears changed, partial, or consumed, stop; do not repair
or repeat it. Never inspect, import, copy, execute, patch, or derive code from
the rejected G2-7B runner/driver. D-127/D-128 remain permanently barred.

## Exact accepted lineage

- corrected execution contract:
  `9464b0947255298a8de8836af6178857841bb2a55bc5c0f4897be2ba91151bcf`
- tracked immutable claim:
  `d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f`
- scientific runner:
  `dca9b8d1be51a29fa4e2269949d1f3339ecf14d99b91f203aa2cacdd2ca90bde`
- D-135 formal acceptance:
  `4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390`
- D-136 bridge:
  `2820c30f387d138d115b36f621b038dc75a1f5af43a7fa9f97b3b837a33a0dc3`
- D-137 repair contract:
  `f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967`
- D-137 integrated commit:
  `0dbbc7013b5303ef2f1535455d458b87208df1b9`
- D-137 post-main CI:
  `33096357416` (`success`)
- D-138 seal-order erratum:
  `a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33`
- D-138 erratum tests:
  `de7aafde522d0c9c61cc2e6f9747a0a577cd9c4b7b8e2b5896b0a6e32ba3f13b`
- D-138 integrated commit:
  `158dffcadfb71305d7de7b84279cfee96a6e8318`
- D-138 PR CI:
  `33100049450` (`success`)
- D-138 post-main CI:
  `33101131039` (`success`; Python 3.11, 3.12.3, and 3.14)
- D-139 test-transition contract:
  `6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c`
- D-139 contract tests:
  `185555b254acdbd13d0b6424ca074b8ba9096e877bcd636a2f0b22b1a0df90a0`
- D-139 integrated commit:
  `3b9c251f6875fedb33e51c4420cd8634c6e4cf29`
- D-139 post-main CI:
  `33103967048` (`success`; Python 3.11, 3.12.3, and 3.14)
- D-140 source-shape transition contract:
  `d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417`
- D-140 contract tests:
  `35bcb0958bc66c386b82ab13171b453c6f60fde81dcb40d329a2f9b659c67da6`

D-135 already proved two opposite-order roots and both conditional profiles,
3,480 model-double fits, 667,872 synthetic predictions, two real CatBoost
controls, byte-identical maps, cumulative supervision, and cleanup. Do not
rerun or reinterpret it.

## D-140 contract-only evidence

An uncommitted prospective implementation passed 118 safe focused/contract
tests, but the safe repository suite, run with permanently barred
`tests/test_openadmet_global_v2_maplight_robustness_synthetic.py` explicitly
ignored, reported `1415 passed, 8 skipped, 2 failed` in about 352.96 seconds.
All seven D-140 tests and all 25 combined D-137 through D-140 contract tests
pass. This is negative pre-integration evidence. It neither accepts nor
binds the implementation. The two failures are exact source-shape assertions
in immutable D-134 focused snapshot SHA-256
`3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f`:

- `tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::test_exact_fit_topology_and_conditional_stage_c_are_unchanged`
- `tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::test_supervisor_starts_before_claim_consumption_and_official_access`

D-140 preserves that file byte-identically and freezes exactly these future
D-141 replacement nodes:

- `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_corrected_child_preserves_fit_topology_and_cleans_before_terminal_staging`
- `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_supervisor_precedes_claim_consumption_and_common_seal_owns_terminal_publication`

The first replacement must prove Stage A=540, Stage B=180, and conditional
Stage C=300 fit identities; exact widths `2563/1539/1539/2248/2363`; both
predictor-authority cross rejections for `synthetic=True` with
`real_catboost_predictor` and `synthetic=False` with
`deterministic_test_predictor`; Stage A -> selection -> Stage B ->
conditional Stage C with exact condition `selected != "G2-7-M0-FULL"`; and
`_terminal_bytes -> _cleanup_owned_root(work) -> _stage_payload(files)`.

The second replacement must prove `run_supervised` is in, and `_consume_claim`
is absent from, `run_official_attempt`; child chronology `resource_checkpoint
-> derive_consumed_claim -> _consume_claim -> compile_capabilities -> Stage A`;
exact `raw_observed = supervisor.run_supervised`; exact
`publication_root=PUBLICATION_STAGING_ROOT` and
`writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent`; equal official and
acceptance limits; the exact absent official attempt root at
`/home/zbos/cypshift-private/openadmet-2026/g2-7g-maplight-robustness-development-attempt-1`;
`_failure_payload` accounting-complete aggregate bytes with no terminal path or
publication;
outer `run_supervised -> _seal_with_fallback`; exclusive common-seal terminal
publication; and absence of parent `_finalize_terminal` and child
`PENDING_TERMINAL_ROOT`.

D-141 may add exactly two skip markers to `tests/conftest.py`, preserving the
previous four for six total, and must bind field
`d140_source_shape_transition_contract_sha256` in the corrected driver,
composite driver/receipt, and focused tests. D-140 itself changes no production
or collection file and grants zero collection, implementation, formal-
acceptance, official, claim, science, model-quality, confirmatory, submission,
or upload authority. The prospective D-141 implementation remains uncommitted;
its hashes are not D-140 evidence.

## Exact next gate

Run the remaining contract-focused and normal repository checks, make one
atomic signed D-140 contract-only commit, push the branch, open a PR, require
all checks, integrate locally by fast-forward only, push `main`, and require
green exact-SHA post-main CI. Then package only the still-uncommitted D-141
corrected implementation, exact six-marker conftest transition, and both
replacement nodes/bindings. Review, integrate, and require green exact-SHA
post-main CI for D-141. Do not run the fixed acceptance from either branch.
Only after D-141 is green on clean synchronized `main`, prove the fixed
composite parent/work/acceptance/rejection roots absent and invoke the sole
fixed no-argument composite acceptance exactly once. Package its aggregate as
a separate reviewed milestone before any official G2-7G preflight.

## Closed capabilities

Until the composite acceptance receipt is reviewed, integrated, and green:

- do not invoke the official G2-7G driver;
- do not create, mutate, derive privately, or consume the tracked claim;
- do not open, list, hash, or copy official source or baseline bytes;
- do not access confirmatory truth, historical row-level artifacts, blinded
  test, TDI, external acquisition, submission, official metric, leaderboard,
  private portal, or upload capabilities; and
- do not retry, resume, move, overwrite, replace, or reinterpret any one-use
  gate.

EXP-G3 and G1/G2/M1/X1/T2 plus immutable R5D/I0 remain closed;
`global_TDI` remains only the TDI fallback.

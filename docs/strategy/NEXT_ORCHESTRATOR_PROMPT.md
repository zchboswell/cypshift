# Next orchestrator kickoff — integrate D-139, then implement G2-7H

This handoff becomes active on the contract-only D-139 test-provenance
transition branch. Signed D-138 commit
`158dffcadfb71305d7de7b84279cfee96a6e8318` is integrated after green PR CI
run `33100049450` and green exact-SHA post-main CI run `33101131039` across
Python 3.11, 3.12.3, and 3.14. Review and integrate D-139 through the signed
fast-forward-only workflow, then require green post-main CI for its exact
commit before packaging any D-140 implementation byte.

The objective remains the smallest scientifically defensible path to a
materially better OpenADMET CYP 2026 submission. Frozen family-safe evidence
outranks leaderboard evidence. Fixed MapLight remains the best validated
system at internal component-macro MAE `0.5837812652`. D-135 is immutable
science-kernel mechanics evidence, D-136 is historical test provenance, D-137
is the driver-only repair contract, D-138 corrects the seal order, and D-139
freezes the exact historical-test transition required by D-140. None is
model-quality evidence.

## Restore authoritative context first

Read and follow `AGENTS.md`, then read completely in order:

1. `docs/strategy/PROJECT_STATE.md`
2. `docs/phases/README.md`
3. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`
4. `docs/strategy/PROJECT_CHARTER.md`
5. D-122 through D-139 in `docs/strategy/DECISIONS.md`
6. the final relevant rows of `runs/experiment_ledger.csv`
7. the exact G2-7G contract, claim, D-135 receipt, D-136 bridge, D-137 repair
   contract, D-138 seal erratum, and D-139 test-transition contract

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

D-135 already proved two opposite-order roots and both conditional profiles,
3,480 model-double fits, 667,872 synthetic predictions, two real CatBoost
controls, byte-identical maps, cumulative supervision, and cleanup. Do not
rerun or reinterpret it.

## Exact D-139 boundary

The D-139 contract is
`benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_official_orchestration_test_transition_contract.json`.
It changes no implementation or test collection. Keep the D-136 historical
audit file at SHA-256 `719c0f71...61bb4a2f` and the historical pytest hook at
`e931ec84...d5848727a` byte-for-byte unchanged in D-139.

D-140 may retire exactly these three nodes and no others:

- `tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::test_acceptance_binds_exact_contract_and_integrated_implementation`
- `tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::test_provenance_bridge_retires_only_the_obsolete_pre_acceptance_state`
- `tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::test_claim_derivation_is_read_only_and_fills_exactly_five_receipts`

The exact `pytest.mark.skip` reasons and constant
`_PRE_D140_ORCHESTRATION_STATE_NODES` are frozen in D-139. Preserve D-136's
existing pre-acceptance skip. Deselect, xfail, prefix/file/class skips, and
additional retired nodes are forbidden. D-140 must prove the exact replacement
map through these new focused nodes:

- `test_historical_lineage_uses_immutable_driver_hash_and_composite_is_required`
- `test_two_orders_cover_six_scenarios_and_build_one_zero_operation_record`
- `test_candidate_bytes_prove_all_five_future_claim_fields_before_publication`

## D-140 implementation milestone

Only after D-139 is integrated and green, package exactly this surface on a
fresh `codex/` branch:

- patch only
  `research/maplight-fixed/run_global_v2_maplight_robustness_official_v2.py`
  in production;
- add fixed no-argument composite acceptance driver
  `research/maplight-fixed/run_global_v2_maplight_robustness_official_orchestration_acceptance.py`;
- add dedicated focused tests
  `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py`;
- update only `tests/conftest.py` among existing test files, adding the exact
  three D-139 markers while preserving the existing D-136 marker; and
- bind field `d139_test_transition_contract_sha256` into the live driver,
  composite driver and receipt, and focused tests.

Do not edit the D-136 historical audit, scientific runner, compiler, scoring
compiler, wrapper, supervisor, MapLight implementation, historical formal
driver/tests/receipt, tracked claim, candidates, features, seeds, groups,
fits, predictions, metrics, gates, resources, selection token, or no-runner-up
rule.

The D-137/D-138 repair must make all five statuses reachable only from their
exact frozen cause, parse canonical supervisor exceptions with exactly 13
typed fields, classify only the four hard-resource reasons as
resource-aborted, preserve truthful aggregate accounting, make compiler
underpower reachable, publish claims through fixed staged/fsynced/no-replace
mechanics, clean exact roots without following symlinks, and use one bounded
status-specific aggregate seal. Predictions remain exact completed-stage
manifest sums strictly below the `562,752`/`797,232` branch projections. Fits
remain exactly 720 or 1,020 and tutorial calls exactly 56 under maximum 80.

Run focused and safe full checks, create one signed D-140 commit, open a PR,
require all checks, integrate locally by fast-forward only, push `main`, and
require green post-main CI. Do not run the fixed composite acceptance from the
implementation branch. Only afterward run that acceptance exactly once from
clean synchronized `main`, package its aggregate result as a separate reviewed
milestone, and again require green post-main CI before the still-unrun official
driver may be preflighted.

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

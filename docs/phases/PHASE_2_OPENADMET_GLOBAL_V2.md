# Phase 2 — OpenADMET global-v2

Status: active; strategy and orchestration handoff accepted; no Phase 2 model,
metric, external-data, prediction, or submission authority yet.

Authorized: 2026-08-24.

## Objective

Build the smallest family-safe global system that produces a reproducible,
material improvement over fixed MapLight on frozen internal evidence, then
permit local chemistry to contribute only if a separately preregistered,
default-to-global residual experiment passes. Win through stronger evidence,
not leaderboard iteration.

The strategy source is the exact externally supplied
[`2026-08-24 audit`](../strategy/OPENADMET_CYP_2026_AUDIT_2026-08-24.md),
whose imported SHA-256 is
`88cfcb717e1ac21a40300e78d73ff3caa3387a41933cb15893ba40831472f79e`.
The audit is retained verbatim as provenance. This phase file is the
authoritative repository synthesis; factual claims become repository evidence
only through the normal contract, receipt, execution, and review gates.

The audit reported that it could not execute two local checks. On this checkout
both gaps are closed: `sha256sum -c` passes all ten files in the public R5D
bundle, and `uv run pytest -q
tests/test_openadmet_r5d_public_audit_bundle.py` passes. This does not rewrite
the audit's original limitation.

## Scientific posture

- Fixed MapLight is the accepted baseline and falsification control.
- The primary build is a heterogeneous, cross-fitted global ensemble.
- Multitask and external-transfer systems are retained only by controlled
  ablation on challenge-only family holdout.
- R5D and I0 remain immutable negative history and may not be rerun, repaired,
  or tuned from their row-level outcomes.
- A materially new TRACE-v2 residual expert is conditionally authorized by
  D-085. It is not a continuation or reinterpretation of R5D.
- Every added model, representation, loss, calibration, and fusion weight must
  target a named failure mode and pass a frozen acceptance rule. Otherwise
  remove it.

## Control plane

Use this knowledgebase, immutable JSON experiment contracts, the existing
append-only experiment ledger, and narrow direct runners. Do not build a
generic workflow platform, service, dashboard, database, plugin system, or
agent swarm.

Every scientific objective follows three separately reviewed milestones:

1. contract freeze before numeric target, fit, prediction, or score access;
2. synthetic implementation and capability-firewall acceptance;
3. one frozen training-only evidence run followed by an accepted or rejected
   result record.

Each milestone uses a `codex/` branch, coherent signed commits, a pull request,
independent review, passing scoped and repository checks, fast-forward-only
local integration, and a pushed `main`. Update `PROJECT_STATE.md` whenever the
best validated system, evidence, risks, active gate, or exact next action
changes. Update the experiment ledger for every experiment, including negative
and infrastructure results.

Generated features, targets, predictions, weights, raw/external data, sealed
truth, and unrestricted run roots stay outside Git. The public RDKit-only core
and `audit`, `train`, `predict`, and `report` CLI do not acquire research
dependencies.

## Program gates

### G2-0 — Freeze evaluation and authority

Targeted failures: family leakage, metric mismatch, post-result selection, and
test/leaderboard contamination.

Freeze before modeling:

- refreshed dataset, tutorial, Space, rules, validator, and permission
  receipts;
- the unchanged D-032 component proxy and repeated grouped development folds;
- a separately capability-sealed component holdout for one confirmatory score;
- experiment IDs `EXP-G1`, `EXP-G2`, `EXP-M1`, `EXP-X1`, and `EXP-T2`;
- exact candidate sets, seeds, resource ceilings, metrics, aggregation,
  bootstrap arithmetic, endpoint guardrails, rejection rules, and prohibited
  capabilities;
- an explicitly provisional interval-aware proxy that is never called official
  MA-ST-RAE unless organizer examples or backend behavior establish parity.

Component-macro MAE remains the internal selection authority until that parity
gate passes. Do not guess missing metric semantics.

Acceptance: contract tests prove exact receipts, family containment,
cross-fitting, sealed confirmation, and denied test/submission/leaderboard
authority. No scientific target or outcome is opened.

### G2-1 — Reproduce MapLight and generate reusable OOF evidence

Reproduce the accepted fixed MapLight result under the new harness before
adding a model. Generate family-safe OOF predictions, residuals, uncertainty,
and per-component diagnostics for all four endpoints. Any preprocessing,
calibration, error model, or later stack must consume only cross-fitted values.

Acceptance: exact input and split receipts match; deterministic payloads replay;
the accepted R3C population and aggregates reproduce within the frozen numeric
tolerance; no blinded-test, TDI, submission, or official metric operation
occurs. Mismatch stops Phase 2 modeling until explained prospectively.

### G2-2 — Global tree and representation ensemble

Run `EXP-G1` first: a frozen 12-configuration, three-seed CatBoost screen over
the current MapLight representation. Run `EXP-G2` only afterward: a small set
of CatBoost, LightGBM, and XGBoost experts over deliberately different Morgan
bit/count radii, Avalon, AtomPair, TopologicalTorsion, ErG, RDKit descriptor,
controlled Mordred, and at most two receipt-bound pretrained representation
blocks. Put heavy dependencies in isolated locked research environments.

Fit scaling, dimensionality reduction, feature selection, iteration choice,
and nonnegative/ridge stack weights inside inner component folds only. Freeze
the constituent set before outer scoring and reject redundant experts by OOF
error correlation and ablation.

Acceptance:

- `EXP-G1`: at least 3% relative primary improvement and 0.015 absolute
  component-MAE improvement, paired upper 95% bound below zero, and no endpoint
  degradation above 0.015;
- `EXP-G2`: at least 5% primary improvement and 0.025 absolute component-MAE
  improvement, at least 10/15 favorable cells, and no endpoint degradation
  above 0.015.

If no candidate passes, retain fixed MapLight and stop this lane without grid
expansion from observed scores.

### G2-3 — Masked multitask and interval alignment

Compare four independent heads with the smallest shared four-endpoint MLP over
frozen fingerprints/embeddings. Add a Chemprop-style shared encoder only as a
separately ablated candidate. Use missing-target masks. Compare central-value
loss with explicitly named reported-bound losses; do not invent censoring,
confidence, credible, or official-scoring semantics. TDI is out of scope unless
separately contracted.

Acceptance: at least 0.020 macro component-MAE improvement, material gains on
at least two endpoints, and no endpoint degradation above 0.020. A multitask
model with correlated errors and no stack ablation value is removed even if its
standalone point estimate looks competitive.

### G2-4 — Provenance-first external transfer

Before acquiring or fitting external records, freeze exact source revisions,
licenses, release dates, organism, endpoint, units, assay format, quality,
standardization, and disclosure policy. Candidate sources are public
OpenADMET, curated ChEMBL, and optional confirmatory PubChem CYP records.

For every outer challenge fold, componentize the challenge/external union and
exclude external exact duplicates, equivalent forms, and analog-family members
of held-out challenge components. External validation is diagnostic only.
If permission to compare against blinded-test structures remains unresolved,
the lane may produce internal evidence but cannot supply a final candidate.

Acceptance: at least 5% primary and 0.025 macro component-MAE improvement on
challenge-only rows, no endpoint degradation above 0.020, and a passing
external/no-external ablation. Random-split or external-only gains do not count.

### G2-5 — Consolidate, then conditionally test TRACE v2

Freeze a small global constituent set using development evidence only. Run
`EXP-T2` only if cross-fitted global residuals show a positive
improvement-versus-coverage region before a local model is selected.

`EXP-T2` predicts cross-fitted global residuals, defaults exactly to global,
abstains on activity-cliff and high-uncertainty cases, and has maximum local
weight 0.25. It may test robust multi-anchor shrinkage only within the same
prospective contract. It may not reuse R5D row losses, reopen T0, alter I0/F1,
or use leaderboard evidence.

Acceptance: at least 0.015 component-MAE improvement, a wholly favorable paired
component-bootstrap interval, and activity-cliff degradation no greater than
0.010. Otherwise reject TRACE v2 and keep the global system unchanged.

### G2-6 — Robustness and one confirmatory score

Before opening sealed truth, run frozen seed, component-threshold,
duplicate/tautomer, influential-family, assay-source, endpoint-harm,
metric/clipping, and constituent-ablation checks. Predesignate exactly one
primary contender and fixed MapLight control. The sealed scorer returns only
the contracted aggregate evidence.

If the contender fails, promote no runner-up and return to fixed MapLight. Do
not reopen development from confirmatory or leaderboard outcomes.

### G2-7 — Candidate freeze and rehearsal

Only a confirmatory pass permits full-training fitting and blinded-test
prediction. Produce two independent roots, require byte-identical 750-row CSVs,
run the current official validator, freeze candidate/environment/input hashes,
record external-data disclosures, and publish through atomic no-replace
acceptance. No result changes the historical MapLight or R5D artifacts.

### G2-8 — Submission boundary

The existing MapLight candidate remains ready for immediate manual upload by
the user. The orchestrator may record a user-supplied portal timestamp, remote
receipt, and score, but may not access credentials or alter model selection.

Automated uploading is outside the critical path. A thin dry-run integration
may be considered only after an organizer-approved challenge endpoint is
documented. Live mode additionally requires current rule/API receipts,
security review, a candidate-specific human arm action, duplicate protection,
and an unambiguous remote receipt. Until all gates pass, live upload code and
scheduling remain absent.

`global_TDI` remains the TDI fallback. This phase does not authorize a new TDI
model, inferred TDI labels, official metric guessing, or transductive use.

## Compute and stopping policy

The planning ceiling is 5,000–15,000 CPU core-hours, 150–400 GPU-hours, and
150–300 GB restricted temporary storage. Every contract must set a smaller
lane-specific ceiling and targeted falsifier before an expensive run. Exhaustive
architecture search is forbidden. Spend compute on repeated family-safe
evaluation, representation diversity, transfer ablation, and uncertainty.

Stop a lane when its simplest falsifier passes, its preregistered acceptance
gate fails, its authority or provenance cannot be established, or its compute
ceiling is reached. Do not expand grids or add representations from observed
outer, confirmatory, test, or leaderboard outcomes.

## New-orchestrator restart capsule

At every fresh start or context restoration:

1. read `docs/strategy/PROJECT_STATE.md`;
2. read `docs/phases/README.md` and this file;
3. read `docs/strategy/PROJECT_CHARTER.md`;
4. read D-082 through D-086 in `docs/strategy/DECISIONS.md`;
5. verify clean synchronized `main` and the exact active gate;
6. inspect the last relevant experiment-ledger rows and immutable receipts;
7. execute only the next unpassed gate through its contract-first microcycle.

Do not treat the imported audit, archived plans, conversation history, or a
plausible improvement as execution authority.

## Exact next action

Create `codex/global-v2-contract` from the passing integrated knowledgebase
milestone. Freeze G2-0 only: refreshed public receipts, authority boundaries,
the development/confirmatory split design, experiment registry, metrics,
candidate budgets, acceptance rules, and synthetic contract tests. Open no new
numeric target, model fit, prediction, test relationship, metric outcome,
external record, or submission operation during that milestone.

# Phase 2 — OpenADMET global-v2

Status: active; G2-2B MapLight synthetic runner accepted; no official Phase 2
target, feature, model, prediction, metric-evaluation, external-record,
blinded-test, submission, or leaderboard-selection authority yet.

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

G2-0 is now frozen in
[`global_v2_experiment_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_experiment_contract.json)
at SHA-256 `612b8cea...e5c0d`. The refresh found unchanged dataset and Space
heads and tutorial revision `858ae63...`, which adds the backend-derived
ST-RAE implementation and endpoint-macro arithmetic while leaving the accepted
submission validator unchanged. The local metric remains explicitly named the
tutorial metric until live-backend parity is independently established.

The contract fixes a label-free 20% component-hash confirmatory partition:
913/4,553 direct components and 997/4,905 direct molecules are confirmatory;
the other 3,640 components and 3,908 molecules are development. Membership is
independent of target availability and magnitude, cannot be rebalanced or
reseeded, and permits one aggregate confirmatory score only. The five
experiments, candidate sets, seeds, nested selection, paired uncertainty,
effect-size gates, resource ceilings, and simplest falsifiers are frozen. This
is contract evidence only; all predictive operations remain unopened.

G2-1 is accepted under
[`global_v2_synthetic_firewall_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_synthetic_firewall_contract.json)
at SHA-256 `be583b5b...4541c8`. The metric and firewall implementation source
receipts are `e63f12af...43269` and `047c3b49...2976c`; the acceptance receipt
is
[`global_v2_synthetic_firewall_acceptance.json`](../../benchmarks/openadmet_cyp_2026/global_v2_synthetic_firewall_acceptance.json)
at SHA-256 `3e897b61...b919fd`. Two fresh synthetic roots replayed all five
stages byte-identically at combined tree receipt `b7fa39eb...a8b93`, including
reversed input order. Pinned tutorial metric fixtures, capability isolation,
cross-root binding, immutable publication, and adversarial failures pass 26
focused tests. This accepts synthetic mechanics only; all official-operation
counters remain zero.

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

### G2-1 — Accept the synthetic capability and metric firewall

Before opening an official numeric target, prove the label-free confirmatory
assignment, development-versus-sealed-truth capability split, clean-room
tutorial metric, model-stage interfaces, receipt binding, and immutable
publication using synthetic inputs only. Two fresh roots must replay to an
identical relative byte map. Wrong receipts, leakage, cross-root mixing,
nonfinite or degenerate metrics, symlinks, traversal, and overwrite must fail
closed.

Acceptance: the child contract, pinned tutorial parity fixtures, deterministic
endpoint-mean control, aggregate-only score terminal, adversarial tests, exact
implementation hashes, and all zero official-operation counters pass review.
This gate grants synthetic mechanics only; it cannot open an official target,
feature, fit, prediction, metric outcome, external record, test relationship,
submission, or leaderboard observation.

### G2-2 — Reproduce MapLight and generate reusable OOF evidence

G2-2A freezes the reproduction contract at SHA-256
`7983e767...a344b`. The historical R3C population overlaps the new sealed
confirmatory partition, so a full-population rerun would prematurely open
confirmatory truth. Authenticate the immutable historical R3C aggregate
receipts without reading row-level outcomes, prove the fixed recipe and
cross-fit mechanics in G2-2B using synthetic data, and only then authorize a
distinct G2-2C execution contract for two development-only replays. Never
compare development scores with historical full-population R3C scores because
the populations differ.

G2-2B is accepted under exact receipt
[`global_v2_maplight_synthetic_acceptance.json`](../../benchmarks/openadmet_cyp_2026/global_v2_maplight_synthetic_acceptance.json),
SHA-256 `1a498f21...a3bb`. Two fresh 200-molecule, 100-component roots
performed 600 real fixed-MapLight fits total in the locked runtime. The second
source order was reversed; model capability, scorer capability, predictions,
residuals, q90 bands, component diagnostics, and manifests matched across all
318 files at tree receipt `e81bfb92...5de06`. The model stage received only
per-cell training targets and opened neither outer nor inner validation truth;
the scorer opened synthetic truth only after immutable prediction publication.

The negative path is part of the evidence. A 20-molecule fixture stopped after
one fit because CatBoost automatically resolved `subsample=1`; increasing
support preserved the omitted-constructor recipe and recovered the exact
historical resolved parameter hash. The first two-root replay was then rejected
despite byte identity because unique components could not falsify inner-family
leakage. The accepted fixture uses two-molecule components and an explicit
inner component-containment gate.

G2-2C froze the development-execution contract at SHA-256
`962484b7...985c2` and its immutable authorization template at SHA-256
`59d7d691...30659`, later consumed exactly once under D-094. The contract binds
exact G2-2A, G2-2B, runner, compiler, runtime, and official input receipt
strings; the 3,908-molecule/3,640-component
development partition; the three support minima; two sequential fresh replays;
and a 600-fit total ceiling. The tracked claim keeps its three future
implementation fields null and remains an immutable authorization template.
The additive compiler/wrapper implementation is accepted under superseding
official-shaped synthetic receipt `ffb3956c...83b2`, which binds compiler
`8317a225...f8b4`, wrapper `3d161a43...ac52`, and acceptance driver
`d50b6016...f947`. Two distinct 326-molecule sparse roots completed 600 real
CatBoost fits total and matched all six terminal files at tree receipt
`49e56607...80e5`; root B reversed physical source order. Each replay retained
only its terminal, scored 1,043 finite truth rows after prediction freeze, and
recorded every official and forbidden operation as zero.

The negative path remains evidence. The first 600-fit deterministic run was
rejected for omitted forbidden counters, non-exact summation, and incomplete
parent binding. The repaired run was interrupted after one complete replay
when audit found terminal lineage, exact-claim, pre-consumption gate,
fixed-root, and stage-authority defects. The final implementation adds a fixed
no-replace private source builder and one bound CLI; twelve adversarial tests
pass. This acceptance did not itself grant official execution authority. D-093
then integrated the exact bytes and passed post-main CI, permitting the sole
claim-bound attempt. Actual consumption was an atomic no-replace event at the
fixed private attempt root. All confirmatory, historical-row, test, TDI,
external, submission, official-metric, leaderboard, and upload authorities
remained false.

Post-main CI for D-092 is green on Python 3.11, locked Python 3.12.3, and
Python 3.14. The following read-only parent-layout preflight rejected official
execution before source publication or claim consumption because the compiler
expected the accepted R3A manifest at `manifest.json`; the immutable accepted
root correctly stores exact receipt `32a95095...026b` at
`feature_manifest.json`. At that preflight both fixed G2-2C roots remained
absent and every official counter remained zero. The explicit two-name adapter
then passed a fresh two-root, 600-fit synthetic acceptance in about 1.78
wall-hours; all six
terminal files matched at tree SHA-256 `49e56607...80e5`. D-093 reviewed and
integrated those exact bytes and post-main CI passed.

D-094 accepts the single official development execution as
`G2_2_MAPLIGHT_REPRODUCED`. Two sequential 300-fit replays completed in 3,643.6
wall-seconds and matched all six terminal files byte-for-byte at terminal
manifest SHA-256 `62c88f7d...77fe`. Each replay covered 3,908 molecules, 5,197
finite truth rows, 46,896 outer predictions, 187,584 inner predictions, 60 q90
contexts, and 15,591 residual/uncertainty rows. Model stages opened zero outer
or inner validation truth; scorer truth opened only after prediction freeze.
Every confirmatory, historical-row, blinded-test, TDI, external, submission,
official-metric, leaderboard, and upload counter is zero. The claim is consumed
and the attempt is terminal: retry, resume, move, and overwrite are forbidden.
The tracked aggregate receipt is
[`global_v2_maplight_official_reproduction.json`](../../benchmarks/openadmet_cyp_2026/global_v2_maplight_official_reproduction.json)
at SHA-256 `76775030...a4482`; row-level official outputs remain outside Git.

The family-safe development OOF component-macro MAE is 0.5838. Repeat means are
0.58355, 0.58368, and 0.58412, a span of only 0.00057. Endpoint means are
CYP1A2 0.6673, CYP2D6 0.5986, CYP3A4 0.5793, and CYP2C9 0.4900. This is a
stable internal development baseline, not the official challenge metric or
confirmatory evidence. G2-3 should target CYP1A2 and CYP2D6 while retaining the
preregistered no-endpoint-harm gate.

Generate family-safe development OOF predictions, residuals, component-equal
absolute-residual q90 bands, and per-component diagnostics for all four
endpoints. Any preprocessing, calibration, error model, or later stack must
consume only cross-fitted values.

Acceptance: exact historical aggregate receipts authenticate; exact input and
split receipts match; deterministic payloads replay; the fixed recipe,
runtime, split mechanics, counts, and internal consistency reproduce; no
confirmatory truth, historical row-level R3C artifact, blinded-test, TDI,
submission, or official metric operation occurs. Mismatch stops Phase 2
modeling until explained prospectively.

### G2-3 — Global tree and representation ensemble

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

### G2-4 — Masked multitask and interval alignment

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

### G2-5 — Provenance-first external transfer

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

### G2-6 — Consolidate, then conditionally test TRACE v2

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

### G2-7 — Robustness and primary contender freeze

Before opening sealed truth, run frozen seed, component-threshold,
duplicate/tautomer, influential-family, assay-source, endpoint-harm,
metric/clipping, and constituent-ablation checks. Predesignate exactly one
primary contender, its complete recipe and receipts, and the fixed MapLight
control.

### G2-8 — One confirmatory score

The sealed scorer opens only after the G2-7 contender lock and returns only the
contracted aggregate evidence. It evaluates exactly one contender once.

If the contender fails, promote no runner-up and return to fixed MapLight. Do
not reopen development from confirmatory or leaderboard outcomes.

### G2-9 — Candidate acceptance and submission boundary

Only a confirmatory pass permits full-training fitting and blinded-test
prediction. Produce two independent roots, require byte-identical 750-row CSVs,
run the current official validator, freeze candidate/environment/input hashes,
record external-data disclosures, and publish through atomic no-replace
acceptance. No result changes the historical MapLight or R5D artifacts.

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
4. read D-082 through D-094 in `docs/strategy/DECISIONS.md`;
5. verify clean synchronized `main` and the exact active gate;
6. inspect the last relevant experiment-ledger rows and immutable receipts;
7. execute only the next unpassed gate through its contract-first microcycle.

Do not treat the imported audit, archived plans, conversation history, or a
plausible improvement as execution authority.

## Exact next action

Freeze the smallest additive G2-3 `EXP-G1` contract before another scientific
fit. Bind the exact D-094 aggregate receipt and the private development OOF
inputs while keeping confirmatory truth, historical R3C row-level artifacts,
blinded test, TDI, external records, submission, official metric, leaderboard,
and upload capabilities closed. Run only the preregistered 12-configuration,
three-seed CatBoost screen over unchanged MapLight features. Fit iteration
choice and any later comparison inside inner component folds; outer predictions
remain score-only. Target CYP1A2 and CYP2D6, but do not alter endpoint-specific
acceptance after observing outcomes. Accept only at least 3% relative and 0.015
absolute component-macro MAE improvement, a paired upper 95% bound below zero,
and no endpoint degradation above 0.015. Failure retains fixed MapLight and
stops `EXP-G1` without widening the grid from outer evidence.

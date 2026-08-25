# Phase 2 — OpenADMET global-v2

Status: active; G2-2 development baseline reproduced, G2-3A `EXP-G1` frozen,
G2-3B synthetic implementation accepted, G2-3C official-shaped mechanics
accepted but resource feasibility rejected, and the one-shot G2-3D resource
falsifier terminally rejected; G2-4A `EXP-M1` is frozen, G2-4B implementation
is accepted, and G2-4C terminally rejects `EXP-M1` on CPU resources after its
sole deterministic formal attempt; the G2-3C claim remains unconsumed, and
confirmatory, historical-row, blinded-test, TDI, additional external-file
acquisition, program submission, official-metric, leaderboard-selection, and
upload capabilities remain closed. A pre-contract documentation view exposed
at least 45 public external CYP3A4 preview records; D-108 rejects that path
without scientific use and requires a metadata-only restart.
G2-5A provenance and G2-5B synthetic compiler mechanics are accepted; G2-5D
accepted the real-source adapter on two official-shaped synthetic roots. D-114
then consumed the sole G2-5C claim and terminally rejected `EXP-X1`: the exact
archive passed checksum, extraction, and SQLite integrity, but the frozen
synthetic physical-schema contract failed against the real `assays` table
before any activity row, support decision, model fit, prediction, or metric.
D-115 records `EXP-T2` as not activated: no accepted stronger global successor
produced cross-fitted OOF residuals and no prospective positive improvement-
versus-coverage region exists. MapLight remains the stable baseline, and no T2
contract, fit, prediction, metric, or model-quality result exists.
D-116 now freezes the separately named `EXP-G3` recovery contract: one
deterministic LightGBM L1 expert, one fixed representation, 60 family-safe
outer fits, no tuning or blend, and no official operation at this milestone.
D-117 freezes its isolated-runtime, two-root synthetic mechanics, exact real-
fit determinism, cleanup, and 20%-margin resource contract; no runtime or fit
operation occurs at the freeze.

Authorized: 2026-08-24.

## Objective

Build the smallest family-safe global system that produces a reproducible,
material improvement over fixed MapLight on frozen internal evidence, then
permit local chemistry to contribute only if a separately preregistered,
default-to-global residual experiment passes. Win through stronger evidence,
not leaderboard iteration.

The strategy source is the exact externally supplied
[`2026-08-24 audit`](../strategy/OPENADMET_CYP_2026_AUDIT_2026-08-24.md),
whose original imported SHA-256 remains frozen as
`88cfcb717e1ac21a40300e78d73ff3caa3387a41933cb15893ba40831472f79e`.
The current public copy is privacy-sanitized at SHA-256 `0b87f86e...0c10312`
under redaction receipt `8a738405...a23798`; only six occurrences of one
private portal identifier changed, with no scientific meaning changed. The
original receipt remains immutable lineage in G2-0, while the public tree
retains no private identifier or result. This phase file is the authoritative
repository synthesis; factual claims become repository evidence only through
the normal contract, receipt, execution, and review gates.

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

G2-3A freezes the additive `EXP-G1` contract in
[`global_v2_g1_screen_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g1_screen_contract.json)
at SHA-256 `ce39721f...d97c3`. It binds the D-094 baseline, exact parent grid,
three model seeds, unchanged 2,563-feature MapLight order, repeated component
folds, nested selection, paired evaluation, terminal statuses, aggregate-only
publication, and resource ceiling. All three seed predictions are frozen and
averaged before a configuration is scored. Each outer cell selects only from
its inner OOF truth; outer evidence cannot revise the grid or fit. Exact
arithmetic is 8,640 inner plus 180 selected outer fits, totaling 8,820. The
parent's unused 60-fit difference is not a repair budget. A later full-
development endpoint recipe may be derived only from the separate complete
inner cross-fit projection and cannot enter or revise G1/G2 outer evidence.
Every promotion member is conjunctive, including 8/15 favorable cells and the
endpoint-harm ceiling. This is contract-only evidence: all official input, fit,
prediction, and metric counters are zero. G2-3B must prove the exact nested
capability and terminal mechanics twice on fresh synthetic roots before any
execution claim.

G2-3B freezes the distinct additive synthetic implementation contract in
[`global_v2_g1_synthetic_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g1_synthetic_contract.json)
at SHA-256 `c8c706a8...ba866`. Its two-layer Occam design tests the exact control
flow without spending the official-sized fit budget on meaningless synthetic
outcomes. A deterministic model double must traverse all 8,820 configuration,
seed, and selected-outer model-stage identities per root; across two roots that
is 17,640 invocations. A separate locked-runtime probe performs exactly 14 real
CatBoost fits per root: all twelve configurations under the first seed and
G1-C00 under the remaining two seeds, totaling 28. The 80-molecule fixture has
40 two-molecule families, exact 2,563-column shape, three repeats, five outer
folds, four scoped inner folds, predeclared selection/tie oracles, and sealed
truth capabilities. Reversed physical input order must publish byte-identical
terminal maps. Acceptance is mechanics and runtime evidence only; synthetic
scores or selections cannot rank science. This freeze executes neither layer
and opens no official input.

The exact G2-3B implementation is now accepted in
[`global_v2_g1_synthetic_acceptance.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g1_synthetic_acceptance.json)
at SHA-256 `479ba130...7ff06`. Two fresh sequential roots completed in 15.85
wall-seconds at about 1.0 GB peak RSS. Root B reversed both physical source
order and model-stage execution order; all seven terminal files nevertheless
matched at tree receipt `bf40c3f6...2f872`. The exact total is 17,640 model-
double invocations and 28 real CatBoost fits. Per root, the mechanics froze
138,240 raw inner rows, 46,080 three-seed inner means, 11,520 complete
projection rows, 2,880 raw outer rows, 960 three-seed outer means, 60 nested
selection tokens, four future endpoint tokens, and 2,000 paired bootstrap
replicates. Twenty-three focused tests cover the fourteen contracted
adversarial classes. The 933-test repository suite, Ruff, and mypy pass
locally. Synthetic values are engineered controls only, not scientific
performance evidence. All official and forbidden counters remain zero.

G2-3C freezes the later execution envelope in
[`global_v2_g1_execution_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g1_execution_contract.json)
at SHA-256 `c75cb01e...0b869` and its tracked unconsumed claim at SHA-256
`1c9f3438...46154`. The fixed private roots and all development-source and G2-2
baseline receipts are named without opening row-level input. The single future
attempt must execute exactly 8,820 new fits, refit the baseline zero times, run
one sixteen-thread CatBoost fit at a time, and terminate without retry, resume,
move, or overwrite. Promotion remains the same five-way conjunction frozen in
G2-3A. Four future implementation receipts are null until a separate additive
official-shaped compiler/wrapper milestone passes two-root synthetic
falsification and reviewed integration. Therefore this contract and claim
grant no current official access, fitting, prediction, or metric authority.

D-099 accepts the additive compiler/wrapper mechanics under
[`global_v2_g1_execution_synthetic_acceptance.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g1_execution_synthetic_acceptance.json),
SHA-256 `87065e0c...65f9e`. Two fresh 312-development-molecule roots matched all
nine terminal files at tree receipt `a8848562...c2f1b`, including reversed
physical source order. The sparse masks are explicit and distinct: 999 finite
central targets, 860 tutorial-eligible intervals, 139 point-only rows, and 424
tutorial rows without standard deviations; 352 confirmatory rows stayed opaque
and zero confirmatory values were parsed. Each root traversed the exact 8,820
model-stage identities and 888 tutorial calls. The exact 28 real runtime probes
matched, but consumed 1,443.87 wall-seconds and 19,203.67 CPU-seconds. Linear
projection from the smaller fixture is already 126.339 wall-hours and 1,680.321
CPU-core-hours, above the frozen 120-hour and 1,200-core-hour limits. Mechanics
acceptance therefore does not permit claim consumption. No official input was
opened and every forbidden counter remains zero.

D-100 freezes the sole G2-3D implementation-equivalent resource falsifier in
[`global_v2_g1_resource_feasibility_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g1_resource_feasibility_contract.json)
at SHA-256 `17327310...24a92`. It permits only fold-local reuse of CatBoost
1.2.1 quantized training and prediction Pools. Every one of the 8,820 future
fit identities, constructor arguments, sixteen threads, sequential execution,
feature, target, fold, metric, and decision remains unchanged. Two synthetic
roots pair the accepted raw-array reference with the optimization across the
same fourteen probe identities. Exact float64 prediction bytes and resolved-
parameter JSON bytes are required; a first mismatch rejects the remedy. If
equivalence passes, the worse optimized-root linear projection must be at most
96 wall-hours and 960 CPU-core-hours, 20% below both existing ceilings. The
contract freeze executes no probe and keeps the claim unconsumed.

D-101 accepts the exact negative G2-3D receipt
[`global_v2_g1_resource_feasibility_rejection.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g1_resource_feasibility_rejection.json)
at SHA-256 `67585830...a9be4` and terminally rejects `EXP-G1` as
resource-infeasible. Two opposite-order roots completed all 56 real CatBoost
fits and 3,584 synthetic prediction values. Quantized-Pool reuse matched every
raw float64 prediction byte and resolved-parameter receipt, proving scientific
identity, but root A was 0.8% slower by wall time and used 0.6% more CPU. The
worse optimized-root projection is 125.497 wall-hours and 1,680.519 CPU-core-
hours, failing both 96/960 acceptance maxima. The work root was cleaned, peak
RSS stayed below 1.46 GB, the G2-3C claim remains unconsumed, the official
attempt root is absent, and every forbidden counter is zero. No second G1
optimization, grid change, official run, or claim consumption is permitted.

D-102 freezes G2-4A in
[`global_v2_m1_screen_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_m1_screen_contract.json)
at SHA-256 `63516e0f...b1c2cc0`. The smallest parent-faithful design contains one
shared 512/256 fingerprint MLP, four independent copies, and one shared
training-only label-permutation control on identical 2,248-column inputs.
Central MAE and reported-bound dead-zone loss are selected only from the four
inner component folds; three seeds are averaged before selection and scoring.
Fold-fitted preprocessing, early stopping, outer epoch reduction, permutation,
prediction identity, paired bootstrap, and all acceptance rules are exact. The
budget is 2,430 fits and 562,752 raw outer prediction rows, with zero baseline
refits. Both independent losses are fit so the shared candidate must beat its
matching-loss control and the independently inner-selected strongest control.
Promotion requires a 0.020 component-macro MAE gain over fixed MapLight,
positive tutorial-primary direction, at least two endpoint gains of 0.010, no
endpoint harm above 0.020, 8/15 favorable cells, and paired upper bounds below
zero versus both independent and permuted controls. A two-root synthetic
resource projection must remain 20% below the 300 CPU-hour, 80 GPU-hour, 80 GB,
and 48 wall-hour execution ceilings before a one-shot claim can exist. This
milestone is contract-only and every official and forbidden counter is zero.

D-103 freezes G2-4B in
[`global_v2_m1_synthetic_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_m1_synthetic_contract.json)
at SHA-256 `f80a6e8d...48df7`. The prospective runtime is isolated under
`research/multitask-mlp`: Python 3.12.3, NumPy 2.5.2, RDKit 2026.3.5, and the
exact PyTorch 2.13.0 CPU wheel. The pinned 16-core host runs four spawned
workers on disjoint four-core affinity slots with deterministic algorithms,
MKLDNN disabled, and zero accelerator use. Per root, an exhaustive model
double traverses all 2,430 scientific fit identities; across two roots, 32
full-width, 300-epoch real fits cover shared, permuted, independent, both-loss,
all-seed, and exact-repeat runtime forms. The worse-root projection must stay
at or below 240 CPU-core-hours, zero GPU-hours, 38.4 wall-hours, 64 GB stored,
and 24 GiB peak RSS. Twelve focused tests freeze topology, counts, balanced
family folds, firewalls, one-shot terminals, and zero current accounting.
This milestone installs nothing and executes no synthetic or official model.
After reviewed integration and green post-main CI it authorizes only the
isolated environment, additive implementation, model-double tests, and at most
four three-epoch API smokes; the formal two-root probe and its claim remain
unauthorized until a separate reviewed source-binding freeze.

D-104 accepts the additive G2-4B implementation under aggregate receipt
[`global_v2_m1_implementation_acceptance.json`](../../benchmarks/openadmet_cyp_2026/global_v2_m1_implementation_acceptance.json)
at SHA-256 `8b195bc6...26622`. The isolated environment resolves Python 3.12.3,
NumPy 2.5.2, RDKit 2026.03.5, and PyTorch 2.13.0+cpu with CUDA unavailable; the
root project and lock remain unchanged. Two fresh roots, one reversing physical
and execution order, matched all six model-double terminal files after 2,430
fit receipts and 75 selection tokens per root. Four bounded real PyTorch fits
then covered shared, permuted, independent, central-MAE, and interval-loss API
forms at three epochs and at most 64 rows; all completed and produced 160 finite
prediction values. Their 3.5-second elapsed time is explicitly not resource
evidence. Twenty-four focused tests cover topology, family isolation,
preprocessing, intact-bundle permutation, deterministic architecture,
worst-case projection, exact repeats, claim authentication, safe cleanup, and
network isolation. Temporary roots were cleaned; every official and forbidden
counter remains zero. Reviewed integration and green post-main CI must precede
a distinct single-use claim binding the exact sources and fixed roots. The
formal 32-fit probe remains unauthorized.

D-105 freezes the sole G2-4C formal-attempt claim in
[`global_v2_m1_formal_attempt_claim.json`](../../benchmarks/openadmet_cyp_2026/global_v2_m1_formal_attempt_claim.json)
at SHA-256 `d6693d11...16497`. It binds implementation commit `229d31c...aa46a`,
the exact D-103/D-104 receipts, all six implementation source hashes, the
prepared 13-package Python 3.12.3/PyTorch 2.13.0+cpu environment, a dedicated
offline cache, and destructively narrow fixed root A, root B, receipt, and
cache paths. Its only future execution is two sequential roots with 16
full-width 300-epoch fits each, four pinned workers, four cores per worker,
zero GPU, and a fresh `unshare` network namespace. It preserves the exact
worst-root resource formulas and requires cleanup of both public/private work
roots and the dedicated cache. Five focused claim tests pass. The claim is
unconsumed and this milestone ran zero fit, prediction, or metric operation;
every official and forbidden counter is zero. Reviewed signed integration and
green post-main CI are mandatory before the sole consumption.

D-106 records that sole consumption in
[`global_v2_m1_resource_rejection.json`](../../benchmarks/openadmet_cyp_2026/global_v2_m1_resource_rejection.json)
at SHA-256 `3222856d...54297`. Both sequential roots completed all 32
full-width, 300-epoch CPU fits; root B reversed physical and launch order, and
all five scientific terminal receipts plus every runtime identity matched
exactly. The worse-root projection is 266.737 CPU-core-hours versus the frozen
240 maximum, a 26.737-hour or 11.14% miss. Wall time (17.207/38.4 hours),
restricted storage (4.304/64 GB), peak RSS (2.164/24 GiB), and GPU use (0/0
hours) pass. The exact runtime also emitted 32 identical non-writable-input
PyTorch warnings; the contract treats warnings as rejection, while the CPU
miss independently decides the lane. Both work roots, both private roots, and
the dedicated cache were removed; no failure receipt exists. Every official
and forbidden counter remains zero, so this is mechanics/resource evidence
only and contains no model-quality result. `EXP-M1` is closed permanently: do
not repair the warning, change threads/device/concurrency, reduce the design,
or retry. Because `EXP-G1` produced no selected recipe, the parent-defined
`EXP-G2` required anchor is unavailable and G2-3 remains closed at fixed
MapLight. The next preregistered lane is G2-5 `EXP-X1`, beginning with a
contract-only provenance and acquisition-feasibility freeze before any
external record is acquired.

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

D-108 rejects the first source-audit preflight under tracked receipt
[`global_v2_x1_prefreeze_preview_rejection.json`](../../benchmarks/openadmet_cyp_2026/global_v2_x1_prefreeze_preview_rejection.json),
SHA-256 `6f0f063c...a5efc`. A dataset-card schema view unexpectedly rendered at
least 45 public CYP3A4 record rows before a child contract existed. No external
file or byte was written locally, no row value was retained or used, and no
official input, fit, prediction, metric, submission, leaderboard selection, or
upload occurred. Nevertheless any positive exposure fails the required zero-
record precondition. Do not reopen or repair that preview path and do not use
an exposed identity, structure, value, order, or distribution. After reviewed
integration and green post-main CI, a separate G2-5A contract may use only
allowlisted repository metadata and protocol/license prose and must expose zero
additional external records.

D-109 freezes the replacement source-specific G2-5A contract in
[`global_v2_x1_provenance_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_x1_provenance_contract.json),
SHA-256 `a51f81a4...a21c1d`. ChEMBL 37 is the sole selected source: its exact
pre-challenge SQLite archive, SHA-256, DOI, CC BY-SA 3.0 obligations, four
human single-protein target identifiers, IC50 eligibility, raw assay and
document provenance, challenge-family exclusion, external/no-external
ablation, rights and resources are frozen before acquisition. The prospective
support falsifier requires at least 1,000 novel eligible molecules per endpoint
after exact/equivalent challenge removal and 750 family-safe external
components per endpoint in every outer cell. Any endpoint failure rejects
EXP-X1 without adding OpenADMET, PubChem, or third-party weights. This milestone
downloaded no archive, opened no new external record or official input, and ran
no fit, prediction, or metric.

D-110 freezes the synthetic-only G2-5B implementation contract in
[`global_v2_x1_synthetic_compiler_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_x1_synthetic_compiler_contract.json),
SHA-256 `db36935e...a3442`. One isolated read-only SQLite compiler must preserve
every raw ChEMBL field, assign one ordered IC50 filter reason, recompute the
accepted core structure and a conservative InChI connectivity exclusion key,
and reuse exact D-032 Morgan/Tanimoto union components. External exact or
equivalent matches lose all values but remain label-free ghost nodes, so their
analog neighbors cannot evade an outer, inner, or confirmatory boundary. Two
synthetic roots reverse every physical insertion order while preserving 336
logical activity rows, 320 eligible rows, 20 forbidden external structures,
and exact cell-support oracles. The miniature 50/35 mechanics gate must pass
while the real 1,000/750 gate fails. This freeze runs no synthetic operation,
opens no external or official record, and grants no acquisition or model
authority.

D-111 accepts the exact G2-5B implementation under aggregate receipt
[`global_v2_x1_synthetic_compiler_acceptance.json`](../../benchmarks/openadmet_cyp_2026/global_v2_x1_synthetic_compiler_acceptance.json),
SHA-256 `5ea379d1...001a8`. Two sequential opposite-order roots produced
different physical SQLite hashes but the same logical source and all seven
terminal files at tree SHA-256 `a5e7d2d3...88111`. Per root, 320/336 rows were
eligible across 80 structures; ten exact and ten connectivity-equivalent
external matches were removed from values but retained as ghost topology;
5,995 exhaustive comparisons yielded 110 nodes in 40 union components. The
outer 52/36, inner 44/32, and confirmatory 52/36 molecule/component support
oracles all matched. Twenty-one focused implementation adversaries pass and
all disposable roots were cleaned. The real 1,000/750 support gate remains a
deliberate failure on synthetic counts. No real external record, official
input, fit, prediction, metric, submission, leaderboard-selection, upload, or
claim operation occurred, so this result has no model-quality meaning and
grants no acquisition authority.

D-112 freezes the immutable G2-5C acquisition claim in
[`global_v2_x1_acquisition_claim.json`](../../benchmarks/openadmet_cyp_2026/global_v2_x1_acquisition_claim.json),
SHA-256 `f1bea832...1ba5c60`. It permits at most one future download of the exact
ChEMBL 37 SQLite archive and binds checksum-before-inspection, fixed absent
restricted roots, exact target verification before activity query, immutable
read-only SQLite, the frozen label-free R2B receipts for exactly 4,905 challenge
training structures and fold identities, no-network extraction/compilation, the
conjunctive 1,000/750 support gate, lane-specific resources, aggregate-only
publication, and complete cleanup. It forbids retry, resume, alternate URL, mirror, source repair,
threshold change, partial reuse, or a second acquisition. The tracked claim
cannot yet be consumed: the real-source adapter, acquisition wrapper,
official-shaped synthetic driver/acceptance, and private consumed-claim receipt
hashes are null. This claim-only milestone downloaded no file, opened no
external record or official input, and performed no model-quality or submission
operation.

D-113 accepts the G2-5D additive adapter boundary in
[`global_v2_x1_real_source_adapter_acceptance.json`](../../benchmarks/openadmet_cyp_2026/global_v2_x1_real_source_adapter_acceptance.json),
SHA-256 `c29aaaf4...33f3fb4`. The adapter authenticates the accepted R2B file set
but decodes only observation identity, source identity, endpoint, and raw
SMILES; 160/160 synthetic target-bearing suffixes were discarded and zero
target values were parsed in each replay. It reuses the accepted component
outer/inner folds exactly and delegates source filtering, chemistry, union
components, ghost-node exclusion, and support decisions to the unchanged
G2-5B compiler. The wrapper fixes one HTTPS GET, checksum before tar listing,
safe extraction, an offline namespace, aggregate-only publication, and cleanup.
Opposite physical SQLite and R2B order yielded identical seven-file terminal
maps at tree SHA-256 `7789290d...8f6b8a`; 22 focused adversarial tests pass and
all disposable roots were removed. This is synthetic mechanics evidence only.
The tracked claim remained unchanged and unconsumed, and all real external,
official, model, metric, submission, leaderboard-selection, and upload counters
remained zero at this synthetic milestone.

D-114 terminally rejects `EXP-X1` under
[`global_v2_x1_acquisition_failure.json`](../../benchmarks/openadmet_cyp_2026/global_v2_x1_acquisition_failure.json),
SHA-256 `ac08140b...50e4eb2`. After reviewed D-113 integration and green
post-main CI, the one-shot claim was consumed. The exact ChEMBL 37 archive was
downloaded once, checksum-verified before listing, safely extracted, opened
read-only without network access, and passed SQLite integrity. Schema preflight
then rejected `assays` before the ordered activity query: the synthetic fixture
had frozen API-style aliases such as `assay_chembl_id`, while the physical
SQLite schema uses `chembl_id`. The same contract error also affects the
logical aliases frozen for target and document identifiers. No external
activity row, official challenge input, support count, chemistry union, model
fit, prediction, or metric was opened or produced. Cleanup removed the archive,
30,480,314,368-byte database, and all mutable/private attempt state; only a
read-only aggregate failure receipt remains outside Git. Retry, repair, mirror,
alternate source, threshold change, and partial reuse are forbidden, so
`EXP-X1` is closed with no model-quality evidence.

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

D-115 records `G2_6_TRACE_V2_NOT_ACTIVATED` under
[`global_v2_t2_not_activated.json`](../../benchmarks/openadmet_cyp_2026/global_v2_t2_not_activated.json),
SHA-256 `75eb8d10...0f59c98`. No accepted stronger global system produced
scientific OOF predictions, and no prospective positive improvement-versus-
coverage receipt exists. Fixed MapLight cannot satisfy the stronger-successor
condition by serving as its own successor. Therefore no T2 contract,
implementation, fit, threshold, local learner, or coverage region is
authorized. The aggregate-only audit opened no row-level artifact or official
input and ran zero fits, predictions, residual computations, or metrics. This
is a terminal activation-order decision, not a negative model score. Any later
local residual idea requires a new named prospective hypothesis after separate
stronger-global evidence; it cannot reinterpret T2.

### G2-6R — Occam global recovery with one fixed expert

D-116 freezes `EXP-G3` under
[`global_v2_g3_single_expert_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g3_single_expert_contract.json),
SHA-256 `ee2725ba...5da47`. This is not a repair of G1, an instantiation of
parent-defined G2, or a reopening of M1/X1/T2. It tests exactly one fixed
LightGBM 4.7.0 `regression_l1` expert on a 2,048-column chiral Morgan-count
block plus the accepted 200-column RDKit descriptor block. Descriptor NaN is
preserved for native missing routing; no column is imputed, scaled, selected,
dropped, or target-encoded.

The model uses one seed, all 1,500 trees, full rows and features, deterministic
forced col-wise CPU histograms, one fit at a time with sixteen threads, and no
validation set, early stopping, grid, extra seed, blend, calibration, external
data, or endpoint-specific parameter. With no selection, the exact scientific
topology is only 3 repeats x 5 outer folds x 4 endpoints = 60 fits, 46,896
candidate predictions, and zero baseline refits.

Promotion requires every gate: at least 3% pinned tutorial-primary improvement,
0.015 component-macro MAE improvement, a paired component-bootstrap upper 95%
bound below zero, at least 8/15 favorable outer cells, no endpoint degradation
above 0.015, and at least 0.010 component-MAE improvement on CYP1A2 or CYP2D6.
A clean miss retains fixed MapLight and closes G3 without a post-result blend,
grid, feature change, extra seed, or successor. Before any execution claim, a
separate contract must create an isolated exact runtime and accept two opposite-
order synthetic roots plus a real-fit resource probe at 20% margin. D-116
itself installs no dependency, opens no official input, and performs no fit,
prediction, metric, submission, leaderboard selection, or upload.

D-117 freezes the next gate under
[`global_v2_g3_synthetic_contract.json`](../../benchmarks/openadmet_cyp_2026/global_v2_g3_synthetic_contract.json),
SHA-256 `6ec0e73b...da4f9f`. After its reviewed integration, one isolated
`research/lightgbm-global` project may bind the exact D-116 runtime without
changing the root project. Across two opposite-order roots, the exhaustive
model double must cover 120 fit identities and 1,920 outer prediction rows.
The real runtime probe uses eight exact 1,500-tree fits on 3,908x2,248 synthetic
matrices, with 3,120 labeled training and 788 prediction rows per endpoint.
All 6,304 finite float64 predictions, resolved parameters, and seven scientific
terminal files must match byte-for-byte across roots.

Resource feasibility uses 60 times the worse root's maximum individual exact-
fit wall and CPU cost plus the worse non-fit overhead; it cannot average roots,
use mean fit cost, subtract probe overhead, or omit the isolated environment,
dedicated cache, storage, or RSS. The conjunctive 20%-margin maxima are 128
CPU-core-hours, 19.2 wall-hours, 25.6 GB restricted storage, 19.2 GiB RSS, and
zero GPU. A miss closes G3 before official access without another runtime,
optimization, reduced probe, sparse input, or retry. D-117 itself creates no
environment, dependency, implementation, synthetic or official fit,
prediction, metric, claim, submission, leaderboard selection, or upload.

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
4. read D-082 through D-117 in `docs/strategy/DECISIONS.md`;
5. verify clean synchronized `main` and the exact active gate;
6. inspect the last relevant experiment-ledger rows and immutable receipts;
7. execute only the next unpassed gate through its contract-first microcycle.

Do not treat the imported audit, archived plans, conversation history, or a
plausible improvement as execution authority.

## Exact next action

Review and integrate D-117 synthetic contract SHA-256
`6ec0e73b...da4f9f`, then require green post-main CI. After integration,
create only the isolated runtime, narrow runner and synthetic driver,
adversarial tests, at most two bounded API smokes, and one formal two-root
synthetic acceptance. Require exact scientific terminal and real-prediction
parity, complete cleanup, and all resource gates. Do not create a claim, open
an official input, fit or score an official model, inspect blinded test,
generate a submission, call an official metric, use portal evidence, or upload.

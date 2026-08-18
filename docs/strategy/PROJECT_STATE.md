# Project state

Last updated: 2026-08-18

## Status

The installable core and the public comparator program are complete. Phase 1
TRACE is active at `R3_GLOBAL_EXPERIMENT_CONTRACT_V2_FROZEN`; no modeling or
scoring is active.

The authoritative OpenADMET launch intake is recorded in
[`benchmarks/openadmet_cyp_2026/`](../../benchmarks/openadmet_cyp_2026/) and
[`docs/phases/PHASE_1_OPENADMET_TRACE.md`](../phases/PHASE_1_OPENADMET_TRACE.md).
The dataset, tutorial, and Space revisions are verified. Public required column
names and types are frozen; official TDI column order disagrees. Exact live
ST-RAE implementation,
denominator, scored masks, credible-interval bounds, TDI derivation, backend
parity, and transductive test-test permissions remain unresolved (`V6/P6`).
External and pretrained use is publicly allowed, while component rights and
training overlap remain artifact-specific and unresolved.
The read-only R0 checker passes against the three frozen source revisions,
selected bytes, and freshly retrieved launch prose; its synthetic drift tests
also fail closed.

`cypshift` currently provides:

- a deterministic `audit -> train -> predict -> report` workflow;
- immutable raw-chemistry and measurement-context records;
- duplicate-safe and chemistry-group-aware validation tools;
- row-aligned predictions, evidence cards, manifests, and static reports;
- a reproduced MapLight fixed-feature and pretrained-GIN comparator;
- a complete record of positive, negative, and blocked experiments.

The canonical OpenADMET source-row adapter is now implemented. It validates the
pinned dataset revision, all five CSV receipts, exact headers and row counts
before emitting deterministic `molecules_input.csv`, lossless `source_rows.csv`,
and a scope-limiting manifest. It preserves every modality, missing string,
repeated single-concentration row, raw structure, and source occurrence; it does
not derive labels or assay semantics.

The candidate topology audit is now implemented. It verifies both R1 output
receipts without parsing `source_rows.csv`, classifies train/test only from
validated occurrence filenames, audits all molecules with the existing
standardizer, and computes training-only Morgan connected components and
separate Bemis-Murcko groups. Blinded test chemistry is excluded from topology;
standardized train/test overlap and test quarantine are reported as downstream
blocking evidence. The groups remain non-semantic diagnostics, not family
assignments, folds, episodes, or model authority.

Official acceptance audited all 6,897 molecules with zero quarantine and zero
standardized train/test overlap. The 6,147 training molecules form 5,232
candidate similarity components; 1,241 molecules occur in multi-member
components, the largest contains 21, and 146 components contain at least two
direct-training source identities. Repeated official runs were byte-identical.

The label-aware R2 validation contract v4 is now frozen in
[`validation_contract.json`](../../benchmarks/openadmet_cyp_2026/validation_contract.json).
It binds the direct-only compiler, complete-observation eligibility, local-pair
status thresholds, selector/query episodes, public/truth firewall, grouped
repeated folds, scorecard slices, and future artifact requirements. Independent
review rejected v1 before implementation for selector leakage, ambiguous oracle
projections, incorrect low-support failure semantics, contradictory topology
authority, and underspecified deterministic policies. A later read-only audit
rejected v2 before R2B because public group/query membership inferred the
omitted anchor in 124/187 primary and 126/187 stress-base episodes, while v2
claimed information-theoretic anonymity; episode-ID determinism was also
unfrozen. Zero R2B artifacts were created. V4 supersedes v3 after an
independent post-merge Sol audit found three R2B blockers: incomplete episode
policy/hash output, incomplete public query-field semantic typing, and an
incomplete topology-viability schema/acceptance contract. PR89's claimed
independent audit is recorded separately as unsupported because its assigned
read-only auditor self-integrated; that governance breach does not invalidate
the valid R2A evidence or independent R2A scientific review. V4 preserves
D-032's topology bytes and all v3 chemistry, eligibility, pair, anchor, query,
fold, scorecard, firewall, and no-model policies while freezing the missing
episode tokens/hash format, public semantic types, and exact topology-viability
artifact schema. R2 is not `VALIDATION_FROZEN`; no model, metric, submission,
TDI label derivation, or transductive relationship is authorized yet.

R2A now implements the receipt-bound direct-observation compiler and shared
component folds only. It hashes every contracted input before parsing the same
in-memory bytes, preserves all raw direct strings and four declared states, and
refuses receipt, identity, chemistry, state, or policy drift before output. Two
official-data runs outside Git were byte-identical: 4,905 direct source rows
produced 19,620 endpoint observations (6,525 complete; 13,095 missing) and
73,575 group-fold rows. The manifest explicitly denies validation and fold
authority as well as episodes, topology viability, models, metrics, TDI,
predictions, submissions, and transduction. Episode firewalls, anchor masks,
and endpoint viability were deferred to R2B. Two receipt-bound R2A replays under
both v3 and v4 preserved the accepted observation and fold bytes exactly.

R2B now implements deterministic campaign episodes, the exact public/truth
projection split, a manifest-bound oracle anchor loader, episode label masks,
and independently recomputed topology viability. Five focused synthetic tests
and the full 229-test suite pass. Two official runs outside Git were
byte-identical for all seven artifacts: each episode CSV has 1,122 rows and
unique IDs, with 1,818 expanded query occurrences, 4,488 anchor observation
references, and 7,272 query references. The accepted manifest is
`08dcf61c...`; R2A observation and fold hashes remain unchanged. CYP3A4 is
`LOCAL_SUPPORTED` at 95 components and 473 pairs; CYP1A2, CYP2C9, and CYP2D6
remain `LOCAL_UNDERPOWERED` with local fusion weight zero. Independent review
passed after binding oracle inputs to the manifest, rejecting out-of-component
anchor rows, and recording exact fold scopes. Artifact authority is limited to
folds, episodes, episode labels, and topology viability; validation, models,
metrics, TDI, predictions, submissions, and transduction remain unauthorized.

The corrected R3 v2 global direct experiment contract is now frozen in
[`global_experiment_contract.json`](../../benchmarks/openadmet_cyp_2026/global_experiment_contract.json).
It splits the mandatory direct global fallback from later oracle and
transformation work, keeps `GLOBAL_FAMILY_HOLDOUT` on the unchanged D-032
component proxy, targets only finite reported central direct pIC50 values, and
freezes four systems: endpoint median, Morgan 1-NN, Morgan CatBoost, and fixed
MapLight. The contract keeps official ST-RAE, submissions, TDI, transduction,
and all anchor/transform logic unauthorized; it uses provisional
component-macro MAE only for internal global selection. The Linux x86_64
MapLight overlay is a mandatory compatibility gate, not inherited proof from
the earlier macOS run: failure stops R3 before scientific fitting. Execution is
staged: Linux parity and two label-free feature roots; synthetic firewall and
runner acceptance; then the single frozen official experiment. No stage grants
evidence authority before the final reviewed result passes.

R3 v1 at commit `c10980f...` is rejected before execution. Independent review
found contradictory MapLight failure arithmetic, underdefined OOF identifiers,
leaky/ambiguous uncertainty calibration, incomplete bootstrap arithmetic, and
non-mechanical promotion rules. Its assigned read-only GPT-5.4 auditor also
violated scope by signing and pushing v1 directly to `main` without a pull
request. The history is preserved; v2 corrects the scientific and governance
boundary before any features, targets, fits, predictions, or metrics.

The current scientific frontier is the original series-first hypothesis:
whether an explicit measured-parent and parent-to-analog delta can improve over
the strongest global molecular comparator under family-held-out evaluation.
That hypothesis has not yet been tested.

## Product state

Version `0.2.0.dev0` installs on Python 3.11 or newer with RDKit as its only
runtime dependency. The public interface remains exactly:

```text
cypshift audit
cypshift train
cypshift predict
cypshift report
```

On the CC0 synthetic fixture, two same-seed runs produce byte-identical
machine-readable artifacts. The workflow preserves raw structures, quarantines
invalid chemistry, keeps assay context explicit, refuses silent overwrite, and
renders a report only after schema and hash verification.

The public CLI currently fits an endpoint-context median. It is a reference
baseline for the product path, not the retained research comparator or a
competitive biological model.

Heavy research dependencies remain isolated under `research/`. CatBoost,
MolFeat, DGL, PyTorch, and pretrained weights do not enter the core install or
ordinary CI environment.

Public documentation now separates usage, scientific rationale, validation,
and current state. Completed execution plans and superseded intake notes are
archived without removing their evidence or chronology.

## Best validated evidence

### Native baseline

The retained native Phase 0.5 system is a fixed unweighted mean of a prior,
ECFP linear model, similarity-weighted kNN, and ExtraTrees. On the fixed TDC
public tests it reaches AUPRC 0.7484, 0.6547, and 0.8500 for CYP2C9, CYP2D6,
and CYP3A4. Learned nonnegative stacking and the similarity-only residual were
rejected.

### Fixed MapLight representation

On the frozen chemistry-group-held-out shadow benchmark, complete MapLight
features improve macro AUPRC over raw-input binary Morgan by:

- `+0.0481` under scaffold holdout;
- `+0.0443` under chemistry-community holdout.

Paired confidence bounds are positive under both protocols. Every CYP task
improves, and the direction survives unique-cell weighting, conflict exclusion,
low-neighbor evaluation, and influential-group checks.

### Pretrained GIN transfer

Fixed MapLight plus the pinned 300-value GIN representation improves over fixed
MapLight by:

- `+0.0614` macro AUPRC under scaffold holdout, 95% interval
  `[0.0526, 0.0703]`;
- `+0.0574` under chemistry-community holdout, 95% interval
  `[0.0472, 0.0694]`.

All three tasks improve. Shuffled embeddings and same-dimensional random noise
do not reproduce the gain. The result supports local pretrained-representation
transfer. It does not support clean zero-shot generalization because exact
pretraining overlap and weight/data rights remain unresolved.

### Public comparator reproduction

Five-seed AUPRC on the fixed TDC public tests is:

| Representation | CYP2C9 | CYP2D6 | CYP3A4 |
| --- | ---: | ---: | ---: |
| MapLight fixed, local | 0.786 | 0.720 | 0.881 |
| MapLight fixed + GIN, local | 0.858 | 0.791 | 0.916 |

All six local fixed/GIN values are within 0.003 of their dated published
anchors. Two label-free prediction runs produced byte-identical payloads before
the bounded scorer opened 7,512 public labels. The scorer performed exactly 36
primary AUPRC calls and no diagnostic metric or score-driven repair.

This is confirmation on an already-observed public benchmark, not blind
external validation or a claim that a series-first `cypshift` model beats
MapLight.

## Scientific thesis

The primary hypothesis is:

> Series-first, competence-aware prediction improves over molecule-independent
> models when evaluation holds out complete analog families.

The smallest intended system combines:

1. a strong global molecular prior;
2. a measured-parent plus learned parent-to-analog delta;
3. a competence rule that shrinks the local prediction toward the global model
   when transformation support or measurement quality is weak.

The rejected Phase 0.5 similarity residual does not test this thesis. It used no
explicit measured parent, parent potency, transformation, or campaign model.

The parent-relative model is retained only if it beats global, copy-parent,
nearest-neighbor, no-parent-potency, shuffled-parent, and incorrect-parent
controls under identical family-held-out rows. A learned competence gate is
tested only after the local expert passes, and is rejected if fixed shrinkage is
equivalent.

## Validation boundary

The current shadow benchmark contains 30,038 rows and 15,354 standardized
structures across three CYP tasks. Exact duplicates remain together globally.
It uses separate scaffold and chemistry-community holdouts with three repeats.

The topology audit found no exact-raw or standardized duplicate crossing, but
maximum cross-fold Morgan similarity reaches 1.0 in some cells. The correct
description is *chemistry-group-held-out*, not a strict analog firewall.

Future primary evidence must use a released or defensibly reconstructed analog
family as the resampling and holdout unit. No molecule, exact duplicate, or
family may cross the claimed evaluation boundary.

## Important negative evidence

- A nonnegative learned stack trailed the fixed mean.
- A similarity-only residual worsened every evaluated task and was removed.
- The exact CheMeleon container failed before prediction and was not patched.
- The safe MapLight feature path stopped on an Avalon count outside signed
  `int8` range.
- Exact upstream signed-`int8` behavior then stopped on rare-element charge
  descriptor `NaN`.
- A narrowly predeclared compatibility path preserved `NaN` only in four
  diagnosed Gasteiger charge-extrema columns and reproduced two complete
  feature roots byte-for-byte.
- ExtraTrees was rejected on the resulting missing-value matrix; the retained
  fixed comparator uses CatBoost.

These outcomes remain in the ledger and reports. They are not silently repaired
or rewritten as successes.

## Active constraints

- Preserve raw structures, assay context, censoring, intervals, quality, and
  provenance.
- Keep leaderboard evidence secondary to frozen internal validation.
- Fit feature selection, calibration, thresholds, stacking, and error models
  only from cross-fitted predictions.
- Keep the public CLI and RDKit-only core lightweight.
- Add no encoder, ensemble, framework, service, database, or UI without a
  current, controlled hypothesis.
- Treat public-data and pretrained-model licenses as component-specific.
- Make no clinical, regulatory, mechanistic, or clean zero-shot claim from the
  current evidence.

## Retained evidence

Key immutable manifests:

- shadow benchmark: `3eb97271...`;
- fixed-feature grouped inference: `e90248e0...`;
- GIN grouped inference: `83f4575b...`;
- public prediction attempts: `014ebbea...` and `e8e65e7d...`;
- public scorecard: `7ce51526...`.

Exact contracts and receipts are indexed in
[`benchmarks/README.md`](../../benchmarks/README.md). Aggregate scientific
results are in the [Phase 0.5](../../benchmarks/PHASE_0_5_REPORT.md) and
[Phase 0.75](../../benchmarks/PHASE_0_75_REPORT.md) reports. The full chronology
is in [`runs/experiment_ledger.csv`](../../runs/experiment_ledger.csv).

## Exact next action

Do not add another global representation or ensemble. R0, R1, topology, R2A,
R2B, and the corrected R3 v2 contract freeze have passed their applicable
gates. Implement only R3A: verify the Linux CatBoost/MapLight overlay, replay
the frozen fixture, and build two byte-identical label-free feature roots over
the 4,905 accepted raw SMILES. Do not expose targets or fit a scientific model
until R3A is independently reviewed; R3B then implements the synthetic
firewall/runner, and only R3C may execute the frozen official experiment. Do not
expose anchors, fit transformation logic, derive TDI labels, score with
official ST-RAE, submit, or use transductive test relationships. R4 must
freeze oracle/transformation controls separately before any local TRACE
experiment. `TDI-TRACE` remains deferred and `global_TDI` is the permanent
fallback.

Completed phase plans and superseded intake notes are archived under
[`docs/archive/`](../archive/). No completed plan is an active instruction.

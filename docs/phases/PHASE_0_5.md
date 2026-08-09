# Phase 0.5 — public CYP benchmark and real-data rehearsal

Status: active — 2026-08-09

Plan frozen: 2026-08-09

Completion deadline: 2026-08-16

## Objective

Build and benchmark the smallest real-data version of `cypshift`. Produce
apples-to-apples public CYP comparisons, exercise the ETL, validation,
out-of-fold prediction, and reporting path, and improve the user experience
without freezing any provisional competition contract.

Phase 0.5 supersedes the complete pre-launch pause only. The 2026-08-17
authoritative freeze remains in force.

## Scientific questions

Answer in order:

1. Can the Phase 0 provenance and chemistry guarantees survive real public CYP
   data?
2. How strong are prior, ECFP linear, local-neighbor, and one nonlinear
   fixed-feature model on frozen public benchmarks?
3. Where do those models sit relative to conventional and strongest dated
   public references on the exact same TDC split?
4. Does the released OpenADMET CheMeleon model transfer under honestly stated
   training-overlap limitations?
5. How much optimism does random validation introduce relative to grouped or
   scaffold validation?
6. Do similarity, local label variance, and model disagreement identify lower
   or higher error?
7. Does one minimal shrinkage-weighted series residual improve the supported
   analog subset without harming remote chemistry?
8. Can the evidence be communicated clearly to chemists and executive readers?

## Public datasets

### Track A — OpenADMET Octant CYP data (required)

Source:
`https://huggingface.co/datasets/openadmet/Octant_CYP_inhibition_reactivity_blog_release`

Freeze the exact revision, dataset card, license, citation, acquisition time,
source files, file hashes, row counts, and observed schemas before ingestion.
The core endpoint is compound-level CYP3A4 pIC50 regression. Every derived
artifact and report must state that active-enzyme preincubation may combine
reversible inhibition with metabolism-dependent effects and is not equivalent
to the challenge's minus-NADPH direct-inhibition endpoint.

Well-level data is limited to provenance, linkage, QC, and measurement-structure
rehearsal. Do not build a general curve-fitting system. CYP3A4 reactivity is an
optional turnover/substrate proxy only after the inhibition benchmark runs; it
must not be called TDI. CYP2J2 and ionization profiling may be audited only when
they exercise an already needed interface at negligible extra cost.

### Track B — TDC CYP benchmarks (required)

Source: `https://tdcommons.ai/benchmark/admet_group/overview/`

Required fixed-split classification tasks:

- `TDC.CYP2C9_Veith`
- `TDC.CYP2D6_Veith`
- `TDC.CYP3A4_Veith`

Supplemental: `CYP1A2_Veith` under a separately documented scaffold protocol.
Optional turnover proxies are deferred until the required scorecard exists.

Use the TDC benchmark-group fixed train/test contract. Candidate selection uses
only deterministic grouped inner validation within `train_val`; retrain the
frozen candidate on all `train_val`, then evaluate the public test split once
per retained model family. Record every public-test evaluation.

### Track C — MoleculeACE activity cliffs (optional)

Run only after Tracks A and B are reproducible and reported. Preselect at most
three tasks before inspecting model results: one small, one medium, and one
with a substantial cliff subset. This track tests reporting and local failure
analysis; it is not a CYP performance claim.

## Public references

Capture and date-stamp the live TDC pages after this plan merges. The
directive-supplied anchors below are provisional until source freeze:

| Task | MapLight + GNN | Chemprop-RDKit | Chemprop |
| --- | ---: | ---: | ---: |
| CYP2C9 | 0.859 ± 0.001 | 0.777 ± 0.003 | 0.754 ± 0.002 |
| CYP2D6 | 0.790 ± 0.001 | 0.673 ± 0.007 | 0.649 ± 0.016 |
| CYP3A4 | 0.916 ± 0.000 | 0.876 ± 0.003 | 0.862 ± 0.003 |

For every reference record the capture date, URL, dataset size, split, metric,
benchmark package version, and discrepancies from locally retrieved data. Do
not report a rank if revisions, labels, hashes, or splits differ.

External inference priority is:

1. OpenADMET CheMeleon CYP model at an immutable revision;
2. local Chemprop or Chemprop-RDKit only if both required tracks already run
   and reproduction remains isolated and small.

CheMeleon must carry an exact standardized-structure overlap audit when its
training structures are accessible. Otherwise contamination risk is unknown,
and the result is not clean zero-shot. Abandon its adapter after one focused,
reproducible attempt if it would destabilize the core.

## Comparison contract

A comparison is apples-to-apples only when dataset revision, target, label
definition, split, metric, evaluation population, and preprocessing policy
match or the preprocessing difference is disclosed. Keep separate scorecard
sections for:

1. TDC fixed-public-test comparisons;
2. Octant same-split internally reproduced comparisons;
3. optional MoleculeACE cliff comparisons.

Never combine regression and classification scores, active-preincubation and
direct-inhibition claims, random and scaffold/grouped splits, internal CV and
public-test results, or best-seed and multi-seed means without explicit labels.

The canonical scorecard records benchmark, endpoint, revision, split hash,
metric, native model and score, uncertainty, public reference and score,
delta, runtime, hardware, contamination/comparability warning, and
official/unofficial comparison status.

## Data and split integrity

For each source:

- preserve raw downloads unchanged outside Git;
- write an immutable download manifest and hash every source file;
- retain source identifiers and exact raw structures;
- map into canonical molecule and measurement tables without losing assay
  context, censoring, intervals, or quality;
- standardize structures as a separate audited derivation;
- report invalid structures, salts, fragment handling, stereochemistry,
  standardized duplicates, label conflicts, and standardized train/test
  overlap.

Preserve official TDC splits even when they contain leakage. Report the official
score unchanged, then publish a distinct strict leakage-audited analysis.

Freeze one deterministic chemistry-cluster definition for Octant before model
selection. Use grouped cross-validation plus similarity and local-density
audits. Quantify cluster sizes, scaffold support, nearest-neighbor similarity,
matched pairs, analog counts, and within-neighborhood label variance before
claiming that the dataset supports a series simulation. A single random split
may quantify optimism but may not select models.

## Model ladder and selection

Evaluate no more than four native learnable families:

1. prevalence or training-median prior;
2. regularized logistic regression or ridge/elastic net on ECFP;
3. endpoint-conditioned similarity-weighted kNN;
4. one justified nonlinear fixed-feature scikit-learn estimator.

A compact RDKit descriptor model may replace or augment the nonlinear model
only when it adds orthogonal residual behavior without expanding the family
count. Use at most 12 predefined configurations per family per task and three
seeds for retained stochastic estimators. Do not add AutoML, an unconstrained
optimizer, a custom GNN, or multiple interchangeable boosting libraries.

After complete OOF predictions exist, compare the best single model,
unweighted mean, median, and nonnegative linear stack. Fit every learned
combination, calibration, feature choice, and threshold using cross-fitted
predictions only.

If classical performance is within approximately 0.02 AUPRC of the matching
Chemprop-RDKit anchor, do not add a deep model for a cosmetic gain. If it trails
conventional public baselines by more than approximately 0.05 across tasks,
audit split, target polarity, preprocessing, prevalence, leakage, metric, and
features before considering architecture.

## Metrics

TDC primary metric is AUPRC. Also report AUROC, balanced accuracy, MCC, Brier
score, calibration error, and sensitivity/specificity at an OOF-selected
threshold, with prevalence, allowed-seed intervals, similarity/scaffold strata,
and duplicate-inclusive versus duplicate-excluded views where relevant.

Octant primary metrics are MAE, median absolute error, and Spearman
correlation. Also report RMSE, a plainly named interval-aware absolute error,
potent-compound error, similarity/local-variance/QC strata, interval coverage
when calibrated intervals exist, and cliff error only when enough pairs exist.
Do not call any provisional metric ST-RAE.

For series or cliff analyses, always pair rates with supported sample counts.

## Series-first rehearsal

After freezing the strongest molecule-independent baseline, test at most one
shrinkage-weighted local or transformation residual. Compare global-only, kNN,
valid series residual, shuffled residual, and randomized family-label controls.

Retain the residual only when it improves grouped folds consistently, improves
the predefined analog-supported subset, does not materially degrade remote
chemistry, and has an explicit support/abstention rule. Otherwise record the
negative result and remove the implementation.

## Research artifacts

For every retained model and observation, store molecule ID, endpoint, split,
fold, model, prediction, uncertainty when available, applicability, nearest
neighbor similarity, local support count and variance, scaffold support,
target, measurement quality, and configuration/data/split hashes.

Use files, not a database or feature-store service. Benchmark dependencies may
live in an isolated optional extra and must not burden the core installation.
Implement the two concrete adapters rather than a general benchmark framework.

Expected closeout outputs include:

- immutable source and split manifests;
- canonical public molecule and measurement tables outside Git;
- duplicate and overlap audits;
- complete native OOF predictions and frozen TDC public-test predictions;
- Octant grouped-CV predictions;
- baseline, simple-stack, and CheMeleon comparisons or a precise blocker;
- one series-residual keep/reject record;
- runtime and hardware accounting;
- canonical CSV and JSON scorecards;
- a static benchmark report and at most five primary figures;
- public benchmark documentation, data/model cards, five-minute quickstart,
  and clean-cache reproduction instructions.

Use repository paths that match the existing structure. Do not track raw,
licensed, unrestricted generated, or challenge data.

The current experiment ledger has no planned-status field, so do not add
placeholder rows. Add a row when each experiment begins and update it at the
keep/reject decision. Encode the benchmark name and version, source revision
and hash, split hash, model configuration, seed, train/validation/test policy,
metrics, runtime and hardware, external reference source, result, decision,
artifact paths, and commit in the existing ledger fields.

Before producing any post-Phase-0 run manifest, advance the development version
as required by D-009. Do not modify or move signed tag `v0.1.0`.

## Product and report work

The public CLI remains exactly `audit`, `train`, `predict`, and `report`.
Research runs through focused reproduction modules, scripts, or Make targets
that reuse package APIs.

Evidence-driven UX work may improve help examples, input-column descriptions,
raw-versus-standardized distinctions, optional-dependency errors, progress
messages, version visibility, assay labels, experimental-use warnings, and
output summaries. Preserve no-silent-overwrite behavior and avoid decorative
console output.

The disk-readable static benchmark report contains an executive summary,
assay context, provenance, scorecard, split explanation, endpoint and
similarity/support performance, calibration or uncertainty, failure examples,
limitations, and the next decision. Prefer tables; use at most five clear
figures. Browser visual QA is desirable when available but not a platform
project.

## Acceptance criteria

Phase 0.5 passes only when:

1. this KB-only milestone merged before implementation;
2. signed `v0.1.0` remains immutable and verifiable;
3. public inputs reconstruct from a clean cache with revisions and hashes;
4. Octant maps without assay-context loss;
5. all three required TDC tasks have exact fixed-split AUPRC results and dated
   MapLight + GNN, Chemprop-RDKit, and Chemprop anchors;
6. provenance, comparability, and leakage warnings are explicit;
7. the minimum native ladder and complete retained-model OOF predictions exist;
8. random-versus-grouped optimism is measured but not used for selection;
9. a supported series residual receives a controlled keep/reject test;
10. CheMeleon is reproduced or rejected with a precise blocker;
11. core installation and the four-command CLI remain unchanged in scope;
12. existing checks pass and new tests cover adapters, split integrity, metric
    polarity, prediction alignment, and report inputs;
13. the benchmark report is readable, reproducible, and candid;
14. a fresh independent reviewer audits source/split freeze, the first complete
    scorecard, and the final release candidate;
15. closeout records what worked, failed, was removed, and transfers to launch.

There is no minimum score for Phase 0.5 completion. Trustworthy evidence and a
correct next decision are the deliverables.

## Non-goals

Do not build official competition adapters or guessed metrics, final challenge
series definitions, custom GNNs, full deep-learning infrastructure, a
production competence gate, LLM adjudication, docking, microstates, conformer
or metabolite pipelines, TDI causal models, a web UI, services, databases, a
general dataset plugin framework, broad hyperparameter infrastructure, all
MoleculeACE tasks, or a collection of web-predictor integrations.

## Stopping rules

Stop expanding Phase 0.5 when both required tracks reproduce, the scorecard and
report identify the material gaps, the series residual has a keep/reject result,
and launch-day ingestion readiness has improved. Reject experiments that lack
split comparability, have incompatible assay context, require a framework, do
not affect an August 17 decision, duplicate an expert, cannot reproduce cleanly,
or lack a predeclared acceptance criterion.

Maintain at most three active experimental branches and prefer three or four
focused PRs for the phase.

## Implementation order

1. Merge this signed KB-only milestone.
2. Freeze public revisions, licenses, source hashes, package versions, and dated
   public anchors; advance the development version before new run manifests.
3. Implement and test Octant compound-level ingestion.
4. Implement and test TDC retrieval and fixed splits.
5. Produce dataset, duplicate, overlap, and leakage audits.
6. Freeze Octant grouped validation before inspecting model results.
7. Run the minimum native ladder and store complete OOF predictions.
8. Publish the first scorecard immediately and compare dated TDC anchors.
9. Attempt one isolated CheMeleon reference.
10. Test one minimal series residual only if topology supports it.
11. Improve the report and documentation, then reproduce from a clean cache.
12. Obtain independent review, remediate material findings, and close the KB.

## Launch-day handoff

Closeout identifies reusable ingestion and audit components, models retained or
rejected, best simple model and stack, series and external-model evidence,
assumptions requiring review, forbidden automatic mappings, and unresolved
risks.

On 2026-08-17, capture and hash the authoritative release, verify license and
rules, freeze official schema and metric, write the Phase 1 plan, and construct
challenge-faithful validation before model selection. Treat every Phase 0.5
model as a candidate, never an incumbent, and do not force official data through
Octant or TDC assumptions.

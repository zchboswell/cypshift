# Phase 3 — Competition recovery and regular submissions

Authorized by the user's 2026-09-04 approval of the repository audit and plan,
including autonomous execution, signed milestone commits/pushes, and manual
uploads by the user. D-151 supersedes conflicting prospective execution and
backout restrictions in prior documents. Historical results remain unchanged.

## Outcome and release cadence

Produce stronger internally validated direct-inhibition and TDI entries for
OpenADMET CYP 2026. Aim for 3–4 qualified releases per week across both tracks,
approximately 24–32 additional entries before November 3. This is a throughput
target, never a requirement to manufacture different prediction bytes.

Every release has a concrete hypothesis/change, grouped OOF evidence, an
immutable private CSV and manifest, a current submission-validation receipt,
and a user-facing handoff. Notify the user when an actual upload file is ready.
The user uploads manually. Do not access credentials or automate portal uploads.
Honor the current 12-hour per-track spacing; distinguish readiness from actual
submission, which is recorded only after the user confirms it. The latest valid
entry replaces the previous entry on that track. Each handoff identifies the
current recommended candidate and whether the new entry is a challenger.

Submission eligibility and final promotion are different decisions. A release
must be motivated, complete, valid, and evaluated without leakage. It must not
be clearly dominated by the current recommendation on the paired development
metrics. Challenger handoffs disclose uncertain or conflicting evidence. The
stronger promotion gates below govern the recommendation and final contender.
Never use public/private leaderboard outcomes to choose parameters, thresholds,
features, masks, or weights. Keep the final reserved comparison closed during
interim releases. TRACE R5D/I0 remains retired after its real scientific failure.

## Current evidence and source snapshot

Audit base: signed `ac043aaaf8dd3a7db1815859f7fa60f05c52277d`.
The preexisting uncommitted midnight handoff is preserved byte-for-byte at
`../archive/intake/NEXT_ORCHESTRATOR_PROMPT_2026-08-31.md`.

- 72 Global-v2/v3 ledger entries yielded one new official development
  model-quality result: fixed MapLight component-macro MAE 0.5837812652150708.
  Its two 300-fit replays used 3643.6 wall-seconds and <=16.194 CPU-core-hours.
  No tutorial ST-RAE was computed in that result.
- G1/M1 resource stops, X1 physical-schema failure, G3 manifest mismatch, and
  G4 pre-execution accounting rejection are not model-quality rejections.
- G2-7G passed all 240 numerical support cells but stopped on absent
  `TAUTOMER_MERGED:confirmatory_touch_not_exercised`; it selected no model.
- TRACE oracle G0 MAE 0.432732 versus T0 0.715892, only 1/15 favorable cells:
  retain this scientific rejection and do not rebuild a local expert.
- The audit's 45 targeted synthetic tests passed. Historical full CI is not
  represented as a newly rerun suite.

Read-only public metadata/code inspection on September 4 found dataset head
`3ac9c5dbb83eec5780ec7fa511908698cfe1396d`, Space head
`453a39a27c9671aa6790bbc2d618606a9cc556c3`, and unchanged tutorial head
`858ae63ce79934113bccdb7fc65467de5f7b1935`. Relative to the old dataset
snapshot, only Emax changed; the direct, TDI, primary-screen and blinded-test
Git blob identities are unchanged. A production intake records full hashes.
The current Space adds regression sample-STD >=0.01 and nonconstant checks,
and requires non-null binary TDI predictions containing both classes per
endpoint. Refresh this evidence before release rather than trusting old hashes.

Sources:

- [Current Space submission code](https://huggingface.co/spaces/openadmet/cyp-challenge/blob/453a39a27c9671aa6790bbc2d618606a9cc556c3/submission.py)
- [Public evaluation](https://github.com/OpenADMET/CYP-Challenge-Tutorial/tree/858ae63ce79934113bccdb7fc65467de5f7b1935/evaluation)
- [Assay design and hit-expansion test construction](https://openadmet.github.io/octant-cyp-inhib-blog-post/)
- [Organizer's PXR lessons on auxiliary data and complementary models](https://openadmet.ghost.io/dont-look-back-in-error-what-we-learned-predicting-pxr-induction-part-i/)
- [Selection bias and nested validation](https://www.jmlr.org/papers/v11/cawley10a.html)
- [Molecular validation and cross-split similarity](https://www.nature.com/articles/s42256-024-00931-6)

## Small, recoverable implementation

Use the existing feature/model kernels and locked research environments with a
thin typed runner, explicit split manifests, keyed OOF predictions, and result
manifests. No workflow platform, registry, service, or agent swarm. The public
CLI and RDKit-only core stay lightweight.

Freeze scientific choices before outcomes. Integrate coherent tested milestones
using signed commits, PR checks, local fast-forward-only merges and pushed main.
Review actual behavior and the diff; never claim an independent review that did
not occur. Full milestone checks follow focused tests during implementation.

Allow two documented engineering repairs per failure class inside the budget.
Preserve failure records and use distinct attempt IDs. A changed scientific
choice requires a new prospective experiment version. Resume a completed fit
only if source, training membership, preprocessing, feature, parameter, seed,
and runtime identities match. Publish outputs atomically; never overwrite an
accepted release. Preserve reusable permitted inputs and checkpoints outside
Git instead of deleting expensive work after routine failures.

Inspect real public metadata, physical schemas, layouts, and runtime APIs before
building synthetic adapters. Production safety requires absence of illegal
crossings, not occurrence of a particular synthetic witness. Warning severity
depends on correctness effects. Record actual fits, resources, failures and
hashes; incidental import counts and cache mutations are not scientific gates.
Bind implementation by Git commit. Historical contracts test historical bytes;
behavioral tests test current code and use temporary roots, not private-machine
state. Preserve old tests unless a demonstrated stale assumption needs a
documented replacement; do not blanket-skip failures.

A reserved evaluation allows one frozen comparison per track, not one fragile
process invocation. An identical-input retry may finish the same report; no
different candidate or outcome-driven tuning is allowed afterward.

## Validation and candidate menu

Preserve the 997-molecule reserved partition and disclose its R3C/R5 historical
reuse. It is a prospective selection barrier, not wholly unseen external data.
The development compiler must not expose reserved target values. Exclude
auxiliary records connected to reserved families. Across all participating
training tables keep duplicates, connectivity-equivalent identities and the
declared similarity-component relationships together. Preserve raw structures,
reported bounds, censoring, assay arms and provenance without silent chemistry
or label changes. No blinded-test geometry or relationships select a model.

Use five outer and three inner grouped folds, deterministically balanced by
endpoint availability with seed 20260905. Freeze before model outcomes; reserve
20260906 for robustness. All auxiliary tasks, stopping, imputation/scaling,
calibration, feature selection, and stacking respect each outer/inner boundary.
Reuse historical OOF only with exact matching training/input identities.
Recompute MapLight on any changed folds. Add existing training-only episode
and activity-cliff diagnostics, without inventing a new local expert.

Use one seed during initial nested evaluation of this menu:

| Candidate | Fixed design and falsifier |
| --- | --- |
| MapLight | Existing accepted MAE recipe/feature semantics; baseline under complete public scoring. |
| Corrected counts | Same learner; nonnegative count features without signed-int8 overflow; compare with exact legacy features. |
| Tanimoto SVR | Binary Morgan radius 2/4096 bits; precomputed kernel; C in {1,10}, epsilon 0.1; inner-only selection. |
| Frozen GIN | Existing 300-dimensional supervised-masking GIN plus MapLight; documented provenance and matched shuffle/noise controls; drop if readiness unresolved after two working days. |
| Auxiliary MLP | Morgan/descriptor inputs; 256/128 ReLU units, dropout 0.1, Adam 1e-3, batch 128, <=200 epochs; four direct and four primary-screen heads. |

For MLP, fit preprocessing inside training folds. Average masked losses within
tasks; combine direct MAE at weight 1 with standardized auxiliary Huber(delta=1)
at weight 0.25. Auxiliary standardization uses training median/IQR (unit scale
for a constant target). Inner stopping patience is 20; outer refit epochs use
the median selected inner epoch. Controls are the identical direct-only model
and shuffled whole-molecule auxiliary bundles including masks within training.
Retain auxiliary learning only when the paired ablation supports it.

Compare identity with affine calibration fitted on inner OOF interval-distance
loss, slope [0.8,1.2], intercept [-0.25,0.25]. Permit nonnegative blend weights
summing to one and <=3 constituents per endpoint. Choose constituents/weights
inside outer-training OOF only; ties favor fewer models and identity calibration.
Evaluate finalist bagging {1,17,29} as a declared ablation, never add untested
bagging only during final fitting. Cache label-free features/kernels and metric
ingredients; repeated scoring does not require repeated model fits.

TDI is a separate bounded track: released labels, Morgan logistic regression
C=1, and CatBoost depth 6/1000 iterations/learning_rate 0.03/Logloss. Select
models and MCC thresholds in grouped inner OOF; ties in threshold MCC favor
the threshold closest to 0.5. Keep missing labels missing; report derivation
conflicts without replacing organizer labels. Use the same family boundaries.
If five folds cannot support both classes, freeze three before fitting; defer
the track if three cannot. No perturbations or forced class flips to satisfy
submission validation. Defer new external datasets, encoders, docking and TRACE.

## Metrics, promotion and release quality

Reproduce the public evaluation wrapper including masks, 1000 bootstraps with
its seed, endpoint means and bootstrap-result averaging. Distinguish this from
verified live-backend parity. Unknown backend internals do not block useful
local research or compliance with the public upload checks. Undefined scores
are reported as failures/unsupported, never replaced with perfect scores.
Also report a separate 2000-replicate paired family bootstrap (seed 20260906)
on pooled OOF macro ST-RAE, retaining all endpoint rows for each sampled family.
Compare identical eligible populations; repeats/endpoints are not independent.

Final direct promotion requires >=2% relative improvement in competition-style
macro ST-RAE over MapLight, paired family upper 95% difference bound <0, no
endpoint component-MAE harm >0.02 pIC50, supportive component ablations and
the same direction in the second frozen repeat. TDI promotion requires >=0.02
macro-MCC gain over the simpler classifier and positive paired family evidence.
The simpler supported valid classifier remains fallback; omit TDI if none is
useful. Freeze one contender/fallback per track before the final reserved
comparison. A failure chooses that fallback, never a newly scored runner-up.

Submission validation checks exact IDs/SMILES/endpoint mapping/order, numeric
finiteness and variation, and TDI binary/both-class requirements. Differential
metric tests cover bounds, masks, denominators and bootstrap behavior. Leakage
tests cover auxiliary tables and cached fits; recovery tests cover interrupted
jobs and damaged/incompatible checkpoints. Ruff lint/format, strict mypy,
relevant research tests, package build and installed-fixture replay must pass.
Require exact identity/serialization and same-runtime repeatability; declare
numerical portability tolerances before outcomes where exact equality is not
appropriate. Data, models, prediction CSVs and unrestricted artifacts stay
outside Git; public evidence is aggregate and privacy-safe.

## Milestones and limits

1. September 5–7: policy, source/current-validator refresh, authenticated
   baseline handoff and complete metric parity.
2. September 8–14: baseline/corrected-count/SVR nested evidence and OOF cache;
   GIN readiness decision; release qualifying challengers as they become ready.
3. September 15–21: GIN/auxiliary ablations and TDI; freeze interim recipes.
4. September 23: interim upload files and method report ready; reserve closed.
5. September 25–October 25: predefined robustness/calibration/blend/bagging
   evidence and continued qualified releases without leaderboard selection.
6. October 26–29: contender freeze and reserved comparison.
7. October 30–November 2: full-training reproduction and final manual handoff.

Official submission deadlines are September 24 and November 3, 23:59 UTC.
Use the existing Ryzen 7950X; no paid compute or GPU dependency. Limits: 16
active CPU threads, 20 GiB working memory, 100 GB private working storage and
1000 CPU-core-hours total. Profile representative real fits before allocation;
do not infer feasibility only from tiny or constant synthetic matrices.

First executable action after this milestone: refresh public source receipts,
add current submission-validation tests, authenticate and validate the existing
baseline, then produce new OOF-backed candidates. A baseline revalidation is
not counted as an additional entry. Every ready release must give the user its
absolute upload path, track, change, evidence, caveats and recommendation.

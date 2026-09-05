# Deep audit and revised strategy — September 5, 2026

The user requested a substantial audit after the second public result remained
poor. Four parallel work streams checked raw targets and scoring, production
artifacts, validation design, and model skill. The audit found **no catastrophic
row, endpoint, unit, feature, or calibration-application error**. It did find
weak modeling behavior and important evaluation/reproducibility gaps. Passing
integrity checks does not establish competitive generalization.

## What was independently verified

| Boundary | Evidence |
| --- | --- |
| Official raw data → development targets | All 46,896 point/lower/upper cells match exactly, including missingness, for 3,908 development molecules. All 997 reserved numeric suffixes were excluded before decoding. |
| Units and endpoint mapping | Released direct pIC50 values are copied without a logarithm, inverse transform, scaling, or assay-arm substitution. All 5,197 finite development labels have bounds and training eligibility. |
| Public scoring | The actual pinned tutorial wrapper, including all metrics, 1,000 bootstraps, right join, reversed prediction rows, NaN masks and aggregation, reproduces baseline and calibrated first-repeat ST-RAE within 1.11e-16. |
| Training features | All four blocks for all 4,905 molecules reproduce the historical NPY bytes exactly. |
| Inference features | Independently regenerated 750-row features reconstruct the exact historical test-feature manifest and matrix hashes. |
| Submission | Both historical rehearsals equal accepted bytes; all 750 names/SMILES retain exact order; all 3,000 affine transforms and the resulting CSV bytes reproduce exactly. |
| Model skill sanity check | Training-fold-only medians score 0.978776 / 0.977768 across the two frozen repeats, versus MapLight 0.757525 / 0.749608. Paired-family 95% upper differences are -0.201431 / -0.208955. Every endpoint beats its median reference. |

These checks use development labels and permitted artifact-integrity reads.
No reserved numeric labels, hidden labels, test-neighbor relationships or new
official-data model fits were used. Small synthetic fits checked native optimizer
defaults. Exact source identifiers and aggregate receipts appear
in [the audit evidence](phase3_deep_audit_v1.json). Detailed audit scripts and
outputs are retained privately under `phase3/deep-audit-20260905`.

The wrapper result establishes parity with public code, not access to the
organizer's private backend. Historical estimators were intentionally deleted;
therefore a fresh estimator reload could not be performed. Two prior identical
rehearsals, verified source, and exact features are strong evidence, but are
not a substitute for retaining and reloading future production models.

## Findings that change the work

### 1. The current model has weak dynamic range and poor potent-tail predictions

In first-repeat OOF, predicted/observed standard deviations are approximately
0.40 / 0.47 / 0.28 / 0.70 for 1A2 / 2C9 / 2D6 / 3A4. Near-zero pooled bias
conceals substantial opposite errors: weak compounds are overpredicted and
potent compounds underpredicted. In both repeats, all 110 / 29 / 88 / 37
endpoint observations with pIC50 >=6 fall below their reported lower bound,
for both baseline and calibrated predictions. Calibration helps this tail but
still leaves average potent-tail underprediction around 1.1–1.5 pIC50 in the
first repeat, and worsens weak-compound interval errors.

These are outcome-conditioned diagnostics. They do not prove MAE is the cause,
nor justify inflating all predictions. Conditional medians, noisy targets,
weak structural signal, and sparse chemical support can all compress outputs.
A controlled loss comparison will distinguish one actionable explanation.
Increasing prediction variance alone is not an acceptance criterion.

### 2. Our main validation does not simulate the challenge's acquisition process

Development has 3,528 singleton molecules (90.28%), with 380 molecules in 112
multi-member families; largest family size is 12. Inclusive >=0.60 chiral
Morgan similarity components plus identity/connectivity/tautomer unions prevent
the declared family crossings. No such crossing was found. These are proxy
chemical families, not a reconstruction of every medicinal-chemistry series.

The organizers selected highly inhibitory parents and subsequently purchased
analogs for a shared four-endpoint panel. Training DRCs were selected
from a diversity library using the TDI-arm primary screen. Thus sparse,
singleton-heavy grouped OOF tests a different information and sampling regime.
Two repeats establish stability within that regime, not independent campaign
generalization. [Organizer assay and acquisition report](https://openadmet.github.io/octant-cyp-inhib-blog-post/)

The completed support diagnostic finds zero >=0.60 outer-training crossings in
either repeat and reproduces all 3,908 standardized structure hashes. Using
fixed similarity bands and training-only top-decile potency thresholds, approximately 72–84% across both repeats
of scored rows lack a potent training neighbor at similarity >=0.30. Closer
labeled support does not consistently reduce error for 1A2 or 2D6; 3A4 shows
the clearest improvement. Global affine gains also vary across support strata.
These descriptive subgroups do not authorize offsets or selection changes.
No test structures or reserved targets entered this diagnostic.

### 3. Historical selected-anchor episodes condition on future query outcomes

The historical selected-anchor policy chooses the maximum complete selector
pIC50 from the whole component, then chooses query neighbors. Consequently a
complete query's selector value cannot exceed the anchor selected from that
same pool. Real newly acquired analogs did not participate in parent selection.
See [episode construction](../../src/cypshift/openadmet_campaign.py) and the
[explicit historical rule](../../src/cypshift/openadmet_validation_contract.py).
The separate deterministic random-anchor stress policy remains distinct.

This is a limitation of the historical selected-anchor estimand, not a newly
demonstrated Phase 3 training leak. Preserve TRACE's recorded negative result
and keep that implementation retired; it does not reject every possible use
of valid known-parent information. A new supporting episode experiment must
assign discovery/query membership without query outcomes, select parents only
from discovery labels, and keep all query labels hidden until evaluation.
Explicit measured-anchor context changes the evaluation setting and must not
be advertised as strict whole-family generalization.

### 4. Production hardening must retain real estimators

Future release packages must retain private fitted endpoint estimators,
resolved parameters, training-membership hashes and feature receipts. Reload
models and require identical predictions in the pinned runtime before handoff.
Current storage use leaves ample room; discarding small useful artifacts saved
little and prevented the strongest independent deployment replay.

The current affine file also transfers development-OOF calibration to a larger
historical full-training model. This was disclosed, but its observed nested gain
is not a measured guarantee for that transfer. New model releases must generate
predictions from their own saved/reloaded estimators and an explicitly evaluated
calibration procedure. RMSE calibration must never transform the old MAE CSV.

### 5. One real feature defect is sparse; unused-data value remains unproven

Signed-int8 Avalon counts wrap in 11 training cells and three test cells; Morgan
counts do not overflow. Both training and inference reproduce the same defect.
Keep the declared corrected-count ablation; the count alone does not establish
that this explains broad poor performance.

The TDI file contains all 4,905 direct identities plus 1,240 additional IDs and
paired direct columns. For established development IDs, all 5,197 paired direct
values/bounds/std match exactly and provide **zero additional direct labels**.
The subsequent family-safe intake independently rebuilt all 6,145 identities'
unions before decoding any extra numeric fields. Of 1,240 extras, 1,237 are
reserve-disconnected and three are excluded. The expanded graph introduces no
new reserved connection or crossing between old development folds. All four
direct endpoints have **zero finite direct points, bounds or standard deviations**
on the 1,237 eligible extras. This source cannot augment direct target coverage;
do not build an augmentation pipeline for nonexistent labels. TDI-arm primary
screen measurements remain a distinct potential auxiliary task.

## Revised order of work

1. **Test the loss hypothesis now.** Use unchanged features and shared tree
   settings, replacing MAE with RMSE. Fix learning rate 0.03, depth 6 and 1,000
   iterations rather than accepting objective-dependent automatic choices.
   Run 80 nested fits per frozen seed, 160 total, capped at 10 CPU-core-hours
   per seed. Compare raw and inner-OOF affine RMSE with the corresponding saved
   MAE and calibrated-MAE OOF. Record optimizer defaults, which differ by loss.
2. **Improve diagnostic relevance and data coverage.** Support summaries and
   family-safe extra direct-field intake are complete; the latter adds zero
   direct labels. Design honest discovery/query episodes before any new anchor
   experiment. Do not change the existing frozen folds retrospectively.
3. **Then test complementary structure models.** Keep the reviewed SVR ready;
   prioritize it and useful auxiliary assay learning over another encoder
   installation unless measured evidence changes the allocation. GIN retains
   a bounded readiness window rather than becoming a prerequisite.
4. **Release qualifying actual files.** No new entry is produced by this audit
   or by relabeling the existing CSV. Retain negative experiments. Select with
   internal evidence, make signed passing milestones, and give the user the
   validated private upload path.

The RMSE protocol and acceptance criteria are frozen in
[the prospective recipe](phase3_rmse_ablation_v1.json). A larger tail prediction
range alone establishes neither success nor failure. A globally dominated candidate is
not uploaded merely because it differs. If the loss comparison fails, retain
the data/validation improvements and move to the complementary-data/model
hypothesis; do not stretch affine bounds to chase public scores.

## Hardware-aware follow-through

The first two follow-through experiments now reject simple loss replacement
and the frozen standalone SVR recipe:

| Candidate | Repeat 1 primary | Repeat 2 primary | Outcome |
| --- | --- | --- | --- |
| Current affine-MAE incumbent | 0.737146 | 0.729011 | Retain interim recommendation |
| Raw RMSE | 0.764717 | 0.755300 | Worse by 3.74% / 3.61% |
| Affine RMSE | 0.746420 | 0.735770 | Worse by 1.26% / 0.93% |
| Raw Tanimoto SVR | 0.825871 | Not planned | Worse by 12.04% |
| Affine Tanimoto SVR | 0.808147 | Not planned | Worse by 9.63% |

These are internal public-wrapper scores; lower is better. Both RMSE variants
also fail the frozen potent-tail mechanism criterion. SVR paired-family primary
difference intervals are wholly positive, and its endpoint component-MAE harms
exceed +0.02. No variant warrants a new production fit or upload. RMSE consumed
160 fits / 2.63144 invocation CPU-core-hours; SVR completed 140 fits in 16.65
seconds / 0.00304 accounted CPU-core-hours. Preserve these negative results,
not just passing candidates. See [RMSE evidence](phase3_rmse_ablation_v1_result.json)
and [SVR evidence](phase3_tanimoto_svr_v1_result.json).

The user authorizes future work to use 75% of CPU capacity and the discrete GPU
at full compute utilization. The audited machine has 32 logical CPUs, 30.46 GiB
RAM and a Radeon RX 7900 XT / gfx1100 GPU with about 20 GiB VRAM. The historical
CatBoost runtime remains unchanged. A separate pinned ROCm/PyTorch environment
now passes actual GPU matrix/backward checks, 20 synthetic Adam steps and exact
prediction parity after checkpoint reload. All 19 package artifacts have verified
hashes. A duplicate-cache storage breach was caught before GPU execution and
repaired without changing packages or test criteria. This establishes synthetic
readiness, not official-data training performance. The shared 24-CPU-equivalent /
20-GiB host-memory limits are active and verified. See
[GPU readiness evidence](phase3_gpu_readiness_v1.json).

A compact direct-only versus genuine-auxiliary versus shuffled-auxiliary MLP
is a stronger first GPU hypothesis than another encoder installation. Use
continuous primary-screen measurements as a distinct task, preserving assay
context and family masks. Do not interpret TDI-arm screen inhibition as a
mechanism-specific binary label or a direct-potency bound. The screen also
selected DRC follow-up, so auxiliary learning may reproduce selection bias;
it must beat both controls and the incumbent on frozen internal evidence.
The exact intake, stopping, fit count and resource recipe must be frozen before
official fits. This is a research priority, not a qualified candidate.
[Organizer assay methods](https://openadmet.github.io/octant-cyp-inhib-blog-post/)
and [the organizers' PXR auxiliary-data lessons](https://openadmet.ghost.io/dont-look-back-in-error-what-we-learned-predicting-pxr-induction-part-i/)
motivate the hypothesis without establishing CYP transfer.

The quote-aware primary-screen metadata audit verifies 17,504 rows covering
4,376 molecules. Of the existing development molecules, 3,493 have four screen
records and 415 have none. No molecule/enzyme pair is duplicated: use each
published estimate once, with no aggregation. Preserve the actual concentration
49.5049505 uM rather than filtering for exactly 50 uM. Quoted metadata prefixes
occur in 784 rows, including SMILES containing commas; a naive comma split is
incorrect. The future compiler must exclude nondevelopment numeric suffixes
before decoding and retain assay context. No screen response values have yet
been decoded, so finite auxiliary-label coverage remains unverified. See
[the intake metadata](phase3_primary_screen_metadata_v1.json).

Aggregate intake, support and hardware receipts appear in
[the audit follow-up](phase3_audit_followup_v1.json). Detailed scripts, the
four-panel OOF diagnostic figure and immutable receipts remain private.

## Follow-through: count correction and new assay signal

Both frozen count-correction repeats completed: 160 fits / 2.82403 invocation
CPU-core-hours. Corrected affine predictions are 0.39% and 0.87% worse than
the calibrated incumbent. Independent and canonical audits pass; neither raw
nor affine variant qualifies. The sparse defect is real but is not evidence
for a more competitive predictor. See [count results](phase3_corrected_counts_v1_result.json).

The reviewed response preflight verifies 13,972 finite primary-screen estimates
on 3,493 development identities, with excluded assay responses never decoded.
These are separate auxiliary outcomes. The controlled GPU MLP tests real versus
shuffled auxiliary supervision against matched direct-only training. See
[coverage](phase3_primary_screen_coverage_v1.json) and D-160.

A query assignment frozen before availability masks leaves 73 CYP3A4 families /
157 queries for a possible known-parent diagnostic. Other heads lack comparable
support. No parent was selected or potency read; availability is not a power
calculation or evidence of acquisition-distribution fidelity. See
[feasibility](phase3_known_parent_feasibility_v1.json).

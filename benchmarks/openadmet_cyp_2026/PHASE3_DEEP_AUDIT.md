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

Add the already planned support diagnostics using fixed similarity bands,
training-neighbor potency and error/count/uncertainty summaries. Compute support
from outer-training labels only. Do not inspect test geometry to choose bands,
weights, candidates or thresholds.

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
Extra identities' numeric fields were not decoded: first build family unions
and exclude reserved-connected rows, then count valid same-arm measurements.
Do not call 1,240 extra rows 1,240 new usable direct labels. Keep TDI-arm primary
screen measurements distinct from direct dose-response targets.

## Revised order of work

1. **Test the loss hypothesis now.** Use unchanged features and shared tree
   settings, replacing MAE with RMSE. Fix learning rate 0.03, depth 6 and 1,000
   iterations rather than accepting objective-dependent automatic choices.
   Run 80 nested fits per frozen seed, 160 total, capped at 10 CPU-core-hours
   per seed. Compare raw and inner-OOF affine RMSE with the corresponding saved
   MAE and calibrated-MAE OOF. Record optimizer defaults, which differ by loss.
2. **Improve diagnostic relevance and data coverage.** Reuse OOF for support
   summaries, audit family-safe extra direct measurements, and design honest
   discovery/query episodes before any new anchor experiment. Do not change
   the existing frozen folds retrospectively.
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

# Project charter

Last reviewed: 2026-08-09

## Mission

Build `cypshift`, an open-source Python package that makes competitive,
scientifically defensible, reproducible CYP inhibition predictions while
remaining useful to chemists after the competition.

In one sentence, the project aims to build a system that:

> reconstructs hidden analog campaigns, predicts where each model is
> likely to fail, and makes the simplest defensible CYP prediction.

## Primary scientific thesis

The primary hypothesis is that series-first, competence-aware prediction
outperforms molecule-independent ensembles under analog-family distribution
shift.

The intended contributions are, in priority order:

1. Evidence that explicit analog-family modeling improves blind-like
   parent-expansion prediction.
2. Evidence that predicting local expert failure can improve fusion more than
   adding another potency model.
3. A controlled evaluation of an optional bounded scientific adjudicator,
   retained only if it passes deterministic and shuffled-evidence controls.

These are hypotheses, not established claims. `PUBLICATION_CLAIMS.md` defines
their evidence requirements.

## Current implementation boundary

The repository currently contains the audited data-to-report product path and a
reproduced strong global molecular comparator. It does not yet contain a
validated measured-parent predictor or competence gate. Those remain the
primary scientific tests, not implied capabilities of the present CLI.

## Endpoint scope

Direct-inhibition regression:

- CYP1A2 pIC50
- CYP2C9 pIC50
- CYP2D6 pIC50
- CYP3A4 pIC50

Time-dependent-inhibition classification:

- CYP3A4
- CYP2D6

## Competition contract

### Confirmed in the 2026-07-29 announcement

- The challenge launches on 2026-08-17 and closes on 2026-11-03.
- The test set contains 750 compounds: ten close analogs for each of 75 potent
  hit compounds selected across CYP1A2, CYP2C9, and CYP3A4.
- All 750 test compounds were assayed across four CYP isoforms; the training
  dose-response matrix is sparse and the test matrix is dense.
- The direct-inhibition task predicts four pIC50 targets.
- TDI classification is scored for CYP3A4 and CYP2D6 using MCC.
- The preliminary TDI definition is based on a two-fold IC50 shift with special
  handling for values below the measurable direct-inhibition range.
- The preliminary direct-inhibition metric is a macro-averaged
  soft-threshold relative absolute error using credible intervals and reduced
  influence from low-activity measurements.
- Half of the test set is used for the live leaderboard, grouped so an analog
  family remains wholly in the live or fully blinded subset.
- A one-time intermediate full-test reveal follows the 2026-09-24 submission
  deadline.

### Frozen only on or after 2026-08-17

The launch-day official resources are authoritative for:

- data files and licenses;
- schema and field names;
- endpoint and assay encodings;
- censoring and interval semantics;
- metric implementation;
- TDI label implementation;
- submission format and validation;
- competition rules, including external and transductive data use;
- leaderboard and submission limits.

No pre-launch announcement overrides released code or rules.

## Non-negotiable constraints

- No hidden-label use or label inference from submission feedback.
- No analog-family leakage in the primary evaluation.
- All learned fusion, calibration, thresholds, feature selection, and error
  modeling are cross-fitted.
- Final model selection uses frozen internal blind-like validation.
- Raw structures and measurement context remain immutable and auditable.
- The core package works on CPU without an LLM, GPU, service, or database.
- Complexity is retained only after a predefined controlled ablation.
- Negative results remain part of the scientific record.
- The public CLI remains `audit`, `train`, `predict`, and `report`.
- The permanent repository, package, and CLI name is `cypshift`.

## Definition of success

### Competition

- Reproduce official metrics exactly.
- Simulate analog-family shift without leakage.
- Produce a final submission selected from frozen internal evidence.
- Tune TDI thresholds only on grouped out-of-fold predictions.

### Science

- Test the series-first claim against independent, shuffled-series,
  scaffold-only, and nearest-neighbor controls.
- Compare the competence gate with simple mean, median, nonnegative stacking,
  inverse-variance weighting, and shuffled controls.
- Evaluate activity cliffs, worst-series behavior, uncertainty calibration, and
  TDI threshold stability explicitly.
- Bound or remove the LLM contribution according to controlled evidence.

### Product and engineering

- A chemist can install the package and generate documented predictions in
  approximately five minutes.
- CI, leakage tests, metric tests, CLI smoke tests, and clean-environment
  reproduction pass.
- Outputs contain predictions, warnings, provenance, manifests, and a static
  report.
- The repository contains no abandoned frameworks or unused dependencies.

## Authoritative source

- OpenADMET, “Announcing OpenADMET’s CYP inhibition blind challenge,”
  2026-07-29:
  https://openadmet.ghost.io/announcing-openadmets-cyp-inhibition-blind-challenge/

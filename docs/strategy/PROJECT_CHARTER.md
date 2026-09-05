# Project charter

Last reviewed: 2026-09-04

## Mission

Build `cypshift`, an open-source Python package that makes competitive,
scientifically defensible, reproducible CYP inhibition predictions while
remaining useful to chemists after the competition.

In one sentence, the project aims to build a system that:

> reconstructs hidden analog campaigns, predicts where each model is
> likely to fail, and makes the simplest defensible CYP prediction.

## Competition priority

Phase 3 prioritizes stronger internally validated global CYP models and regular
manual submission handoffs. Family-safe evaluation, metric alignment and useful
auxiliary assay data take priority over proving the original series-first idea.
The original measured-parent TRACE design failed its official oracle test and
is retired. Historical hypotheses and claims remain documented in Git and
PUBLICATION_CLAIMS.md; no unsupported clinical or mechanistic claim follows.

The RDKit-only public product path and its median fixture model remain separate
from the isolated research models. Current work follows
[Phase 3](../phases/PHASE_3_COMPETITION_RECOVERY.md), authorized 2026-09-04.

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

Launch-day truth supersedes the pre-launch announcement assumptions. The
receipt-bound release is indexed in
[`benchmarks/openadmet_cyp_2026/`](../../benchmarks/openadmet_cyp_2026/).

Organizer-confirmed launch facts:

- the challenge is live and closes on 2026-11-03;
- the test set has 750 compounds and two independently scored tracks;
- direct inhibition predicts four pIC50 targets: CYP1A2, CYP2C9, CYP2D6, and
  CYP3A4;
- TDI classification is evaluated for CYP3A4 and CYP2D6 with MCC;
- the live leaderboard uses half of the test set and the final leaderboard uses
  the full set;
- one ranked account represents each cooperating team/lab; repeated per-track
  uploads are accepted every 12 hours and only the latest valid entry counts;
- external data and pretrained models are publicly allowed, with proprietary
  training data disclosed. Component rights and overlap remain artifact-
  specific.

Required public column names are frozen as `SMILES`, `Molecule_Name`, four
direct targets, and two TDI targets. Official TDI column order disagrees across
the Space and tutorial. The launch prose names MA-ST-RAE and a two-fold TDI
shift with special low-activity rules, but R0 does not freeze executable
ST-RAE, denominators, scored masks, interval-field meaning, TDI derivation,
validator/backend parity, or transductive test-test permissions. Those are
historical R0 uncertainties. Phase 3 must refresh the public source
contracts and distinguish unresolved backend internals from implementable public
metric and upload checks; unknown internals do not impose a blanket work stop.

No pre-launch announcement overrides the released source receipts, and no
pre-launch model, metric, schema, or permission assumption transfers
automatically.

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

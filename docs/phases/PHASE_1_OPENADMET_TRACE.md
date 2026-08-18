# Phase 1 — OpenADMET TRACE

Status: active, records/contracts only; gate `R0_CONTRACT_FROZEN`; freeze date 2026-08-17.

## Context capsule

Active hypothesis: a series-first, competence-aware predictor can improve
blind-like analog-family performance over a strong global comparator when parent
evidence, assay state, intervals, and family boundaries remain auditable. Hypothesis only.

Frozen identifiers are recorded in [`source_receipts.json`](../../benchmarks/openadmet_cyp_2026/source_receipts.json):

- dataset `85f8b358d0a2056a98b990dd75d3b3ec9247862b`; tutorial `9d4925eb4a0fb914256da1b27d110593bcbe3cf0`; Space `13c5057b37d1e72b3f036dd0d59718b1823f8fdd`.

The public test has 750 compounds. Direct requires `SMILES`, `Molecule_Name`,
and four direct pIC50 values. TDI requires those identifiers plus
`CYP2D6_is_TDI` and `CYP3A4_is_TDI`; official source order disagrees. Direct is
continuous and TDI is binary. Preserve raw structures, available bounds,
standard deviations, and missingness. Raw curves, censor qualifiers, per-row
assay/probe state, QC, and label origin are not released and must not be
invented.

## Validation protocols

1. **GLOBAL_FAMILY_HOLDOUT:** evaluate global direct and TDI baselines with no
   molecule, duplicate, or reconstructed family crossing a boundary.
2. **ANCHOR_EXPANSION_HOLDOUT:** expose exactly one measured anchor in a held-
   out family; exclude every other family member from global labels, delta
   support, and candidate pools. All learned choices remain cross-fitted.

`TDI-TRACE` is deferred/optional after `direct_TRACE` and `global_TDI` are frozen;
`global_TDI` remains the permanent fallback.

Direct endpoint outcomes are `LOCAL_SUPPORTED`, `LOCAL_FAILED`, or
`LOCAL_UNDERPOWERED`; local fusion weight is zero for the latter two.
`ORACLE_SIGNAL_PASS` is evidence that true-anchor structural reasoning works,
not permission to claim `DEPLOYMENT_PASS` for inferred anchors.

## Endpoint-state semantics

- Direct inhibition is direct-arm pIC50 for CYP1A2/2C9/2D6/3A4; rows carry
  fitted bounds and/or standard deviations. Do not collapse bounds or missing
  values into guessed points.
- TDI is an operational +NADPH versus -NADPH IC50-shift state, not proof of
  irreversible inhibition. The public two-fold/inferred rule is unresolved:
  among non-null labels, all arm-missing rows are `False` (CYP2D6: 4;
  CYP3A4: 1,250), including 1,055 direct-missing rows with TDI pIC50 at least
  4.301. Preserve the M2/M6/P6 conflict and do not derive hidden labels.
- Public prose names MA-ST-RAE and MCC; implementation, denominator, masks,
  bounds, and backend parity remain unresolved (`V6`).

## Paths and gates

Accepted: source receipts, submission names/types, launch prose, raw-state
preservation, family-safe intent, and global TDI fallback.

Killed: guessed schema/metric/rules; public-test optimization; interval/state
collapse; TDI proxy labels; copying official raw data/source code.

Blocked: exact metrics, masks/denominators, backend parity, validator identity/
order, family assignment, and transductive permission (`V6/P6`).

Targeted failure: a stale/contradictory contract causes metric mismatch, family
leakage, or unsupported claims (`V2`, `V6`, `P6`).

Acceptance: receipts verify; source names/types and order discrepancies are
recorded; unresolved items are named; no raw source is tracked; adapter fails closed.

Kill: source digest/revision mismatch, unresolvable schema disagreement,
interval/state loss, family leakage, or metric-specific optimization. Preserve a
blocker receipt and do not model.

Exact next action: implement a thin receipt-bound drift checker comparing
revisions, hashes, headers, row counts, and submission names/types; stop on
drift. The canonical adapter follows only after that check passes review.

Non-goals: metric reimplementation, redistribution, features, modeling, submissions,
transductive use, held-out threshold tuning, broad adapters, services, dependencies.

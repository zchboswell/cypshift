# Failure taxonomy

This taxonomy defines failure classes that experiments and prediction cards may
reference. Add a class only when evidence does not fit an existing one.

## C — Chemical truth

- C1: invalid or unparsable structure
- C2: salt, mixture, or fragment ambiguity
- C3: stereochemistry loss or ambiguity
- C4: tautomer, charge, or microstate sensitivity
- C5: duplicate structures with conflicting identifiers or measurements
- C6: silent standardization change

## M — Measurement truth

- M1: unit or endpoint normalization error
- M2: censoring or credible-interval misrepresentation
- M3: assay condition, probe, readout, or NADPH-state mismatch
- M4: low-quality or weakly identified dose-response curve
- M5: conflicting replicates or cross-assay measurements
- M6: unstable TDI assignment near potency or shift thresholds

## V — Validation and leakage

- V1: molecule or exact-duplicate leakage
- V2: analog-family leakage
- V3: training-derived prediction used without cross-fitting
- V4: split instability or non-determinism
- V5: leaderboard-driven selection or threshold tuning
- V6: evaluation metric mismatch

## S — Series and SAR

- S1: incorrect series assignment
- S2: weak or unsupported transformation
- S3: inconsistent transformation direction
- S4: activity cliff
- S5: internally contradictory family
- S6: unsupported or ambiguous parent/anchor

## E — Expert competence and uncertainty

- E1: out-of-domain global model
- E2: sparse or high-variance local neighborhood
- E3: expert disagreement
- E4: gate miscalibration or unstable weighting
- E5: undercoverage or overwide uncertainty
- E6: conflated measurement, extrapolation, SAR, or mechanism uncertainty

## T — TDI mechanism and labels

- T1: turnover evidence absent or extrapolated
- T2: direct and TDI potency models disagree
- T3: threshold-sensitive classification
- T4: rare-class or isoform-specific failure
- T5: unmodeled persistent/reactive pathway

## P — Product and reproducibility

- P1: non-reproducible run or missing seed/hash/configuration
- P2: silent overwrite or incomplete manifest
- P3: optional dependency breaks the core installation
- P4: CLI failure or unactionable error
- P5: restricted data, secret, or private artifact exposure
- P6: stale, duplicated, or contradictory canonical artifact

## A — Adjudication

- A1: unsupported mechanistic claim
- A2: evidence citation mismatch
- A3: unstable repeated output
- A4: adjustment exceeds configured bound
- A5: shuffled-evidence or deterministic control performs equivalently
- A6: deterministic fallback failure

## Phase 0.5 public-benchmark applications

The following named risks must be checked explicitly even when an existing
class already captures the underlying failure:

- **Cross-dataset metric comparison (V6):** scores from different revisions,
  targets, labels, splits, metrics, preprocessing policies, or evaluation
  populations are presented as one ranking.
- **Assay-context mismatch (M3):** active-preincubation, direct-inhibition,
  reactivity, turnover, or substrate measurements are treated as equivalent.
- **Public benchmark test-set overfitting (V5):** accessible test labels or
  repeated public-test evaluations influence candidate selection.
- **Train/test standardized-structure leakage (V1):** exact structures become
  duplicates only after the audited standardization policy.
- **External-model training overlap (V1/V5):** an external predictor is called
  zero-shot without excluding benchmark structures from its training data.
- **Public leaderboard version drift (P6/V6):** current pages, local benchmark
  packages, data revisions, or splits no longer describe the same benchmark.
- **Hidden preprocessing differences (C6/V6):** structure or label processing
  changes comparability without being recorded.
- **Class-prevalence effects on AUPRC (V6):** AUPRC values are compared without
  the associated evaluation prevalence and population.
- **Inferred-series instability (S1/S6):** conclusions depend on an unsupported
  or unstable chemistry grouping.
- **Substrate behavior mislabeled as TDI (M3/T1):** turnover or depletion is
  treated as proof of time-dependent inhibition.
- **Active-preincubation inhibition mislabeled as direct inhibition (M3):** an
  assay that permits metabolism-dependent effects is represented as the
  challenge's minus-NADPH endpoint.
- **Benchmark framework expansion (P3/P6):** generalized infrastructure,
  dependencies, or abstractions displace the two required concrete adapters
  and the core product.

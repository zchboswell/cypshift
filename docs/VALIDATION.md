# Validation and evidence

This document is the short audit path. Exact rows, environments, hashes,
metrics, blockers, and statistical procedures remain in the linked benchmark
reports and experiment ledger.

## Current evidence levels

| Layer | Status | What it proves |
| --- | --- | --- |
| Installable core | Passed | Deterministic `audit -> train -> predict -> report` workflow on a synthetic fixture |
| Native public baseline | Passed | Reproducible classical CYP models with grouped selection and one-time evaluation |
| Fixed MapLight representation | Passed | Complementary count, pharmacophore, and descriptor blocks improve grouped CYP ranking over binary Morgan |
| Pretrained GIN transfer | Passed locally | The pinned 300-value representation adds grouped benchmark value beyond fixed MapLight and controls |
| Public comparator reproduction | Passed | All six fixed/GIN seed-metric aggregates reproduce their dated anchors within 0.003 AUPRC |
| Parent-relative prediction | Not yet tested | No differentiated series-first claim is supported yet |
| Clinical or regulatory use | Not validated | No patient, dosing, DDI, or safety decision claim is permitted |

## Public comparator

Five-seed AUPRC on the frozen TDC CYP test populations:

| Representation | CYP2C9 | CYP2D6 | CYP3A4 |
| --- | ---: | ---: | ---: |
| MapLight fixed, local | 0.786 ± 0.004 | 0.720 ± 0.002 | 0.881 ± 0.001 |
| MapLight fixed, published | 0.783 ± 0.002 | 0.723 ± 0.003 | 0.881 ± 0.001 |
| Fixed + GIN, local | 0.858 ± 0.001 | 0.791 ± 0.002 | 0.916 ± 0.000 |
| Fixed + GIN, published | 0.859 ± 0.001 | 0.790 ± 0.001 | 0.916 ± 0.000 |

Two label-free prediction runs produced byte-identical payloads before the
bounded scorer opened public labels. The local results are confirmations on an
already-observed public benchmark, not blind external validation.

## Chemistry-aware shadow result

The frozen shadow benchmark contains 30,038 `train_val` rows and 15,354 global
standardized structures across CYP2C9, CYP2D6, and CYP3A4. Exact duplicates
remain together across tasks. It evaluates three repeats under separate
Bemis-Murcko scaffold and chemistry-community holdouts.

Macro AUPRC:

| Protocol | Fixed seed 1 | GIN alone | Fixed + GIN seed 1 | Fixed + GIN five-seed mean |
| --- | ---: | ---: | ---: | ---: |
| Scaffold | 0.7876 | 0.8440 | 0.8489 | 0.8512 |
| Community | 0.8003 | 0.8553 | 0.8577 | 0.8589 |

Fixed MapLight improves over binary Morgan by 0.0481 and 0.0443 macro AUPRC.
Fixed plus GIN improves over fixed MapLight by another 0.0614 and 0.0574. The
paired 95% intervals for the latter contrast are `[0.0526, 0.0703]` and
`[0.0472, 0.0694]`.

The direction remains positive under:

- all three CYP tasks;
- unique structure-task weighting;
- exclusion of conflicting structure-task cells;
- validation structures without a training neighbor at Tanimoto 0.60;
- predeclared influential-group absence checks;
- shuffled-GIN and same-dimensional random-noise controls.

## Leakage and interpretation limits

The shadow split is chemistry-group-held-out, not a proven strict analog
firewall. Maximum cross-fold binary-Morgan similarity reaches 1.0 in some
cells, although exact-raw and standardized duplicate crossing are zero. The
assignment was frozen before candidate results and was not rebuilt after the
topology audit.

The GIN weight and exact feature bytes are reproducible locally. Its artifact
license, pretraining-data license, and exact structure or target overlap remain
unknown. The supported statement is *pretrained-representation transfer*, not
clean zero-shot generalization.

The public benchmark predicts binary Veith CYP inhibition labels. It does not
by itself validate continuous potency, time-dependent inhibition, another
assay system, or a clinical endpoint.

## Negative evidence

Negative results remain first-class evidence:

- learned nonnegative stacking did not beat a fixed unweighted mean;
- a similarity-only residual worsened every evaluated task and was removed;
- an exact external CheMeleon container failed before prediction and was not
  patched;
- safe and exact-upstream MapLight feature attempts stopped on signed-`int8`
  overflow and rare-element descriptor `NaN` before a narrow, predeclared
  compatibility rule was allowed;
- shuffled GIN and random noise did not reproduce the retained GIN gain.

These failures explain why the retained system is smaller than the set of
components explored.

## Reproduction and provenance

The evidence chain records:

- source URLs, revisions, licenses, sizes, and SHA-256 hashes;
- raw-row and standardized identities;
- label-independent split assignments;
- environment locks and model-weight hashes;
- per-seed row-aligned predictions;
- fit, prediction, label-access, and metric counts;
- preserved failure receipts and reversal boundaries.

Generated data and model artifacts remain outside Git. Compact contracts,
receipts, aggregate reports, and the experiment ledger are tracked.

For complete evidence, read:

- [Phase 0.5 native benchmark report](../benchmarks/PHASE_0_5_REPORT.md)
- [Phase 0.75 representation report](../benchmarks/PHASE_0_75_REPORT.md)
- [Benchmark contracts](../benchmarks/README.md)
- [Publication claim bars](strategy/PUBLICATION_CLAIMS.md)
- [Experiment ledger](../runs/experiment_ledger.csv)

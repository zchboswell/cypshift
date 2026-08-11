# Phase 0.75 report

Date: 2026-08-11

## Result

Phase 0.75 produced positive fixed-representation and pretrained-GIN results on
the frozen chemistry-cluster-held-out shadow benchmark. Fixed MapLight first
improves macro AUPRC over raw-input binary Morgan by 0.0481 on scaffold holdout
and 0.0443 on community holdout. Fixed MapLight plus GIN then improves over
fixed MapLight by another 0.0614 and 0.0574. The paired GIN 95% intervals are
[0.0526, 0.0703] and [0.0472, 0.0694]. All three CYP tasks improve under both
protocols, and shuffled-GIN and random-noise controls do not reproduce the gain.

The result required two preserved negative experiments and one narrowly
authorized compatibility path. The safe implementation stopped on an Avalon
count of 144. Exact upstream signed-`int8` behavior then stopped on rare-element
charge-descriptor `NaN`. D-027 preserved `NaN` unchanged only in the four
diagnosed charge columns for pinned CatBoost; two independent full feature
roots then matched byte-for-byte.

Both gains survive unique structure-task weighting, conflict exclusion,
validation structures with no training neighbor at or above 0.60, and every
predeclared influential-group absence check. This supports a fixed MapLight
representation-value and pretrained-transfer claims on the shadow benchmark.
They do not establish public-test performance, clean external validation, or
challenge transfer.

## Stage B GIN feature gate

The exact MolFeat `gin_supervised_masking` model is 7,467,310 bytes and matches
SHA-256 `6d0f8feb...`. The artifact remains outside Git and is not redistributed.
Artifact-specific and pretraining-data licenses and exact TDC overlap are
unknown, so this path is limited to local pretrained-transfer benchmarking.

Two packaging blockers are preserved from before embedding: MolFeat 0.9.2
omits `python-dotenv` from its dependencies and imports its optional Hugging
Face module on the DGL path. A final compatible environment pins those import
dependencies and forces Hugging Face offline; no Hugging Face model or feature
is used.

Fixture parity then passed exactly across one pinned MapLight process and two
fresh direct MolFeat processes. Their 8-by-300 float64 NPY bytes match. Two
real builds independently featurized 15,399 exact raw inputs and expanded them
to all 30,038 rows. The GIN arrays are finite and byte-identical with SHA-256
`9bd56931...`.

The raw-row audit validates the cache policy. Forty-one standardized hashes
have multiple raw forms, but only two groups have identical GIN values. The
largest absolute difference is 0.7140. Caching by standardized hash would
silently substitute representations and is rejected.

## Stage B GIN shadow result

Eighteen isolated model cells completed the eight predeclared new fits per
cell: GIN alone, fixed plus GIN at five seeds, fixed plus shuffled GIN, and
fixed plus seeded noise. The immutable prediction manifest is `a9b78b38...`.
It binds 144 fits, 36,045 validation rows, 324,405 finite probabilities, exact
five-seed means, and zero validation-label or metric access during fitting.

Macro point AUPRC was:

| Protocol | Fixed seed 1 | GIN alone | Fixed + GIN seed 1 | Fixed + GIN mean | Shuffled GIN | Random noise |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Scaffold | 0.7876 | 0.8440 | 0.8489 | 0.8512 | 0.7784 | 0.7775 |
| Community | 0.8003 | 0.8553 | 0.8577 | 0.8589 | 0.7896 | 0.7894 |

Task-level fixed-plus-GIN seed-1 deltas for CYP2C9, CYP2D6, and CYP3A4 are
`+0.0658`, `+0.0780`, and `+0.0402` on scaffold holdout and `+0.0697`,
`+0.0645`, and `+0.0379` on community holdout. The maximum cell AUPRC is
0.9319, below the mandatory 0.95 forensic trigger.

Synchronized global-group bootstrap results are:

| Protocol | Contrast | Point macro delta | Paired 95% interval |
| --- | --- | ---: | ---: |
| Scaffold | Fixed + GIN minus fixed | +0.0614 | [0.0526, 0.0703] |
| Community | Fixed + GIN minus fixed | +0.0574 | [0.0472, 0.0694] |
| Scaffold | Fixed + GIN minus shuffled GIN | +0.0705 | [0.0613, 0.0797] |
| Community | Fixed + GIN minus shuffled GIN | +0.0681 | [0.0566, 0.0815] |
| Scaffold | Fixed + GIN minus random noise | +0.0714 | [0.0620, 0.0813] |
| Community | Fixed + GIN minus random noise | +0.0683 | [0.0570, 0.0811] |

Primary macro deltas remain positive under unique-cell weighting
(0.0613/0.0574), conflict exclusion (0.0612/0.0573), and the below-0.60-neighbor
subset (0.0827/0.0738). The smallest predeclared absent-group macro lower bound
is 0.0463. Every frozen keep-gate component passes. Because weight and
pretraining-data licenses and exact TDC overlap remain unknown, the defensible
claim is reproducible local pretrained-representation transfer—not clean
zero-shot generalization or automatic challenge eligibility.

## Frozen shadow benchmark

`TDC-CYP-shadow-v1` preserves all 30,038 `train_val` rows and 15,354 global
standardized structures across CYP2C9, CYP2D6, and CYP3A4. It contains 9,114
scaffold groups and 9,902 chemistry communities under three deterministic
repeats.

The label-independent topology audit covers 35,963 validation-structure
records and 287,433,973 train-validation pair comparisons. Exact-raw and
standardized duplicate crossing are zero. The maximum cross-fold Morgan
similarity reaches 1.0 in some cells, and 0.198 to 0.346 of validation
structures have a training neighbor at or above 0.60. The defensible term is
`chemistry-cluster-held-out`, not `strict analog firewall`.

## Exact fixture parity

The pinned MapLight source and the local implementation matched on the frozen
eight-row fixture in the compatible Python 3.10 environment. The four fixed
MapLight blocks and the complete 2,563-column matrix matched element-for-element
and byte-for-byte. The local-only binary Morgan block also repeated exactly.

The original safe parity receipt is `68ee584a...`. The later compatibility
parity receipt is `a5d1c000...`. Compatibility parity used one upstream and two
fresh local processes, generated 17 arrays across 24 fixture-row loads, and
completed nine signed-`int8` boundary conversions:

| Preconversion count | Stored `numpy.int8` value |
| ---: | ---: |
| 127 | 127 |
| 128 | -128 |
| 144 | -112 |

The retained six compatibility arrays are read-only non-pickle NPY v1.0 files.
No real row was parsed during parity.

## Real-row blockers

### Safe count contract

The first safe real build stopped at exact-raw index 66 in the Avalon block.
One sparse bin had count 144, outside the frozen range 0 through 127. The safe
contract forbids wrapping, widening, clipping, binarizing, or retaining a
partial matrix. The immutable blocker receipt is `f5276200...`; the tracked
diagnosis receipt is `c69bd826...`.

### Exact-upstream signed-`int8` contract

The compatibility experiment changed only the count upper-bound behavior. Its
first real build parsed 30,038 label-free source rows and computed all five
blocks in memory. The container validation then found at least one non-finite
value in the RDKit descriptor matrix. The first affected exact-raw row was
index 1,563, structure hash `6911fe92...`. The receipt does not establish the
total affected-cell count or a descriptor column.

The build completed zero validated complete exact-raw feature bundles and
persisted zero arrays. All 15,399 exact-raw inputs had five block arrays
computed before container rejection. Runtime was 88.95 seconds and peak RSS
was 0.8955 GiB. The immutable failure receipt is `b337f965...`. The contract
stops on any finiteness mismatch and permits no further scientific change.
Build 2 was not started.

## D-027 fixed-feature result

The owner-authorized D-027 experiment changed only the non-finite policy. It
preserves `NaN` in descriptor indices 39, 41, 43, and 45 and rejects every
infinity and every other `NaN`. Two independent builds processed all 30,038
rows from 15,399 exact raw inputs. Their row files and five NPY payloads are
byte-identical. The matrices contain exactly 328 expanded `NaN` cells across
82 rows, all in the four permitted columns.

Eighteen isolated cell processes then fitted R1 through R5 from outer-training
targets only. They retained 162 model vectors and 18 five-seed mean vectors over
36,045 validation rows. Model processes parsed zero validation labels. A
separate scorer revalidated every prediction artifact before parsing the
30,038 frozen `train_val` scoring labels.

Point macro AUPRC was:

| Protocol | Binary Morgan R1 | Fixed MapLight R5 seed 1 | Delta | R5 five-seed mean |
| --- | ---: | ---: | ---: | ---: |
| Scaffold | 0.7395 | 0.7876 | +0.0481 | 0.7905 |
| Community | 0.7560 | 0.8003 | +0.0443 | 0.8019 |

Task-level R5-minus-R1 deltas were positive for CYP2C9, CYP2D6, and CYP3A4 in
both protocols. The maximum cell AUPRC was 0.9017, below the 0.95 forensic
trigger.

Paired synchronized global-group bootstrap results were:

| Protocol | Point macro delta | Paired 95% interval |
| --- | ---: | ---: |
| Scaffold | +0.0481 | [0.0372, 0.0583] |
| Community | +0.0443 | [0.0354, 0.0540] |

All six task-protocol lower bounds are also positive. The macro deltas remain
positive under unique-cell weighting (0.0482/0.0442), conflict exclusion
(0.0491/0.0447), and the below-0.60-neighbor subset (0.0661/0.0585). Across the
60 predeclared task/protocol influential-group checks, the smallest absent-group
macro lower bound is 0.0347. The representation-value gate passes.

## Accounting

Across the compatibility execution:

- synthetic parity processes: 3 completed;
- synthetic arrays generated: 17;
- synthetic fixture-row loads: 24;
- signed-`int8` boundary conversions: 9;
- real feature-build attempts: 1;
- completed real feature builds: 0;
- real block arrays completed in memory: 5;
- persisted real arrays: 0;
- target values parsed: 0;
- model fits: 0;
- predictions: 0;
- metric evaluations: 0;
- public-test rows used: 0;
- public-test labels parsed: 0;
- public-test family-task slots consumed: 0;
- GIN weight bytes downloaded: 0;
- challenge assumptions added: 0.

The final D-027 accounting adds two completed full feature builds, 162
scientific model fits, 180 point prediction vectors, 180 initial point AUPRC
evaluations, and 72,182 confirmatory/sensitivity metric evaluations. It uses
zero public-test rows or labels, zero GIN weights, and zero challenge
assumptions. The prior blockers remain immutable negative evidence.

The Stage B feature gate adds one verified 7,467,310-byte model artifact,
three successful fixture embedding processes, two completed real embedding
builds, 30,798 exact-raw featurizations, and two retained 30,038-by-300 arrays.
It parsed zero targets and performed zero model fits, predictions, metrics,
public-test operations, Hugging Face model loads, or challenge assumptions.

Stage B prediction and inference add 144 model fits, 144 model vectors, 18
five-seed mean vectors, 198 point AUPRC calls, 108 sensitivity calls, and
144,000 grouped-bootstrap calls. The scorer parsed 30,038 frozen `train_val`
scoring labels and generated no new fit or prediction. Public-test rows,
labels, and family-task slots remain zero; challenge assumptions remain zero.

## Scientific conclusion

Both hypotheses are supported: complementary fixed MapLight blocks materially
improve ranking beyond binary Morgan, and the pinned GIN representation adds an
additional distinct-representation gain. Neither result is explained by
duplicate weighting, conflicting cells, close neighbors, shuffled vectors,
random noise, or one large chemistry group. Rights and contamination remain
explicitly unknown.
The result authorizes only jointly frozen label-free public prediction families;
it does not authorize sequential public-test tuning or a challenge model.

## Handoff

Phase 0.75 remains bounded by D-024. On the authoritative OpenADMET release,
freeze the original bytes, rules, endpoint semantics, MA-ST-RAE, MCC and TDI
label implementations, censoring, validator, submission contract, external-data
permissions, and challenge-faithful family splits before any model fit or
score. No TDC feature, split, model, or threshold transfers automatically.

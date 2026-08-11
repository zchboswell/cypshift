# Phase 0.75 report

Date: 2026-08-11

## Result

Phase 0.75 produced a positive fixed-representation result on the frozen
chemistry-cluster-held-out shadow benchmark. With identical rows, CatBoost
seed, and validation cells, the complete fixed MapLight representation improves
macro AUPRC over raw-input binary Morgan by 0.0481 on scaffold holdout and
0.0443 on community holdout. Paired grouped 95% intervals are [0.0372, 0.0583]
and [0.0354, 0.0540]. All three CYP tasks improve under both protocols.

The result required two preserved negative experiments and one narrowly
authorized compatibility path. The safe implementation stopped on an Avalon
count of 144. Exact upstream signed-`int8` behavior then stopped on rare-element
charge-descriptor `NaN`. D-027 preserved `NaN` unchanged only in the four
diagnosed charge columns for pinned CatBoost; two independent full feature
roots then matched byte-for-byte.

The gain survives unique structure-task weighting, conflict exclusion,
validation structures with no training neighbor at or above 0.60, and every
predeclared influential-group absence check. This supports a fixed MapLight
representation-value claim on the shadow benchmark. It does not establish
MapLight+GIN superiority, public-test performance, clean external validation,
or challenge transfer. The subsequent label-free GIN feature gate also passed,
but no GIN predictive result exists yet.

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
30,038 frozen train-only scoring labels.

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

## Scientific conclusion

The fixed-representation hypothesis is supported: complementary MapLight blocks
materially improve CYP ranking beyond binary Morgan under both frozen shadow
protocols. The result is not explained by duplicate weighting, conflicting
cells, close neighbors, or one large chemistry group.

The next permissible step is only the predeclared Stage B shadow controls.
The weight, environment, exact-raw behavior, parity, and repeat gates pass;
rights and contamination remain explicitly unknown. The fixed and GIN feature
results authorize no public-test scoring and no challenge model.

## Handoff

Phase 0.75 remains bounded by D-024. On the authoritative OpenADMET release,
freeze the original bytes, rules, endpoint semantics, MA-ST-RAE, MCC and TDI
label implementations, censoring, validator, submission contract, external-data
permissions, and challenge-faithful family splits before any model fit or
score. No TDC feature, split, model, or threshold transfers automatically.

# Phase 0.75 report

Date: 2026-08-11

## Result

Phase 0.75 did not produce a new predictor or score. It produced a frozen,
chemistry-cluster-held-out shadow benchmark, exact MapLight fixture parity, and
two precise real-row blockers.

The public fixed MapLight representation could not be generated on every
frozen shadow row without changing a second scientific rule. The safe
implementation stopped on an Avalon sparse count of 144 because its frozen
range ended at 127. The separately authorized exact-upstream signed-`int8`
implementation reproduced that overflow behavior, then stopped because the
RDKit descriptor matrix contained at least one non-finite value. No complete
feature matrix, model fit, prediction, metric, or public-test evaluation was
produced.

The Phase 0.5 fixed mean therefore remains the best validated public-data
research model. No superiority, representation-gain, GIN, or challenge claim
is supported.

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

Two independent reviews passed the compatibility parity artifact and the real
blocker. The blocker prevents retry and build 2.

## Scientific conclusion

The richer-representation hypothesis remains unanswered. Exact fixture parity
is implementation evidence, not predictive evidence. No MapLight or GIN shadow
score exists, and the published leaderboard anchors remain unpaired external
references.

The smallest defensible action is to preserve the negative evidence and stop.
Imputing the non-finite value, removing a descriptor, changing RDKit, or
continuing with a partial ladder would create a new result-aware experiment.
That work is not authorized in Phase 0.75.

## Handoff

Phase 0.75 returns the project to D-024. On the authoritative OpenADMET release,
freeze the original bytes, rules, endpoint semantics, MA-ST-RAE, MCC and TDI
label implementations, censoring, validator, submission contract, external-data
permissions, and challenge-faithful family splits before any model fit or
score. No TDC feature, split, model, or threshold transfers automatically.

# Project state

Last updated: 2026-08-10

## Current phase

Phase 0.75 active — evidence execution for exact comparator reproduction and
representation value.

## Active operating goal

Produce row-aligned local MapLight evidence. Measure the frozen shadow
topology, reproduce the exact fixed representation, and determine whether the
fixed and GIN representations improve CYP ranking on chemistry-aware grouped
validation. Add no research framework, source adapter, dataset, encoder, or
ensemble before comparator evidence exists.

Phase 0.75 is explicitly authorized before 2026-08-17 for public-benchmark
research only. Phase 0.5 remains immutable. D-024's authoritative challenge
freeze remains in force: no Phase 0.75 assumption, feature, split, score, or
model automatically transfers to the released challenge.

TDC AUPRC is a representation benchmark, not a challenge metric or expected
challenge-rank proxy. The announced challenge tracks are direct-inhibition
pIC50 regression and CYP3A4/CYP2D6 TDI classification. Their authoritative
metric implementations, including MA-ST-RAE and MCC behavior, remain subject
to the August 17 release freeze.

## Best validated system

Phase 0 `v0.1.0` remains the best validated installable product workflow. On the
CC0 synthetic fixture, `audit -> train -> predict -> report` produces canonical
data, a duplicate-safe fixture split, an endpoint-context median, 21
predictions, cards, a hashed manifest, and a static report. Independent
same-seed runs are byte-identical.

The Phase 0.5 fixed unweighted mean is the best validated public-data research
model. It combines prior, ECFP linear, similarity kNN, and ExtraTrees families.
On frozen TDC public tests it reaches AUPRC 0.7484, 0.6547, and 0.8500 for
CYP2C9, CYP2D6, and CYP3A4. It trails the matching Chemprop-RDKit anchors by
0.0286, 0.0183, and 0.0260, and the dated MapLight + GNN anchors by 0.1106,
0.1353, and 0.0660. On the Octant grouped outer population its MAE is 0.5434.
No superiority or challenge-performance claim is supported.

The final Phase 0.5 review passed exact signed commit `9150e93`. A clean clone
verified the tracked report from aggregate-only evidence and passed all 90
tests. The public source reconstruction, grouped splits, prediction firewall,
scorecards, negative results, signatures, hosted CI, and minimal codebase all
passed independent review.

No Phase 0.75 model result exists yet. The Phase 0.5 fixed mean remains the best
validated public-data research model until a new frozen result passes its
declared gates.

## Phase 0.75 operating contract

Phase 0.75 closes no later than 2026-08-17. Required Tier 1 work is limited to:

- exact MapLight fixed-feature reproduction;
- one isolated MapLight + GIN reproduction attempt;
- one global leakage-safe TDC `train_val` shadow benchmark;
- representation ablations on the shadow benchmark only;
- a row-level comparator scorecard, accurate public documentation, and launch
  handoff.

The new TDC public-test budget contains exactly three prediction families per
task: fixed MapLight, MapLight + GIN, and at most one final locked `cypshift`
contender. The third family may remain unused. Every permitted label-free
prediction family must be complete, hashed, and independently reviewed before
any new public-test label is inspected. The completed families are then scored
together. There is no sequential score-and-develop cycle, score-driven repair,
or public-test feature ablation.

The shadow benchmark uses one label-independent global molecule table across
CYP2C9, CYP2D6, and CYP3A4. Standardized duplicates always share an assignment.
Scaffolds are indivisible in the scaffold protocol, and frozen chemistry
communities are indivisible in the community protocol. No task-specific
regrouping is allowed. All representation, dependency, model, and combination
choices use shadow evidence only.

The frozen assignment is currently a chemistry-cluster-held-out shadow
benchmark. It is not yet proven to be a strict analog firewall. That language
is allowed only after a label-independent topology audit measures maximum
train-validation Morgan similarity and the declared similarity strata for
every validation structure. The assignment must not be rebuilt, tuned, or
reseeded in response to that audit.

Heavy MapLight and GIN dependencies remain in separately locked research
environments or digest-pinned containers. They do not enter the core install or
ordinary all-groups CI environment. The public CLI remains exactly `audit`,
`train`, `predict`, and `report`.

Conditional Tier 2 work is limited to an AID 1851 source and leakage audit, a
cross-isoform panel feasibility assessment, and a parent/analog topology audit.
No AID label may enter training before primary field semantics and the strict
cross-task structure firewall pass independent review. Full multitask,
parent-relative, Chemprop, additional encoder, and LLM work is deferred beyond
launch unless separately authorized as trivial after Tier 1 closes early.

The complete contract is
[`PHASE_0_75.md`](../phases/PHASE_0_75.md).

## Active evidence-execution packet

- **Objective:** produce exact fixed-MapLight fixture parity and row-aligned
  shadow predictions, or a precise reproducible blocker, while measuring what
  the frozen shadow split actually holds out.
- **Required inputs:** the pinned MapLight source and compatible environment,
  the tracked parity fixture, the immutable shadow rows and manifest, and only
  the receipt-bound train-only targets authorized by the Stage A contract.
- **Required outputs:** a label-independent topology report, two matching
  label-free feature roots, a parity and row-alignment receipt, the frozen
  Stage A shadow predictions and metrics, runtime and hardware evidence, or one
  exact blocker.
- **Pass/fail gate:** preserve every raw row; verify dimensions, ordering,
  finiteness, hashes, and duplicate handling; use no public-test label; run no
  undeclared candidate; retain a representation claim only under the frozen
  paired and sensitivity gates.
- **Non-goals:** no new framework, research layer, source adapter, dataset,
  encoder, ensemble, calibration, threshold optimization, feature family, or
  challenge-specific model.

The frozen Stage A comparator reached its predeclared stop rule before a real
matrix was retained. Synthetic fixed-feature parity passed exactly, but the
first real feature build found an Avalon sparse count of 144 where the frozen
safe range ends at 127. No retry, second build, fit, prediction, metric, or
public-test action is authorized under this contract. This is the precise
reproducible blocker permitted by the evidence-execution packet.

## Phase 0.75 source, budget, and shadow freeze

The exact MapLight source, paper, method, dated anchors, environment gaps, and
claim boundaries are frozen in
[`maplight_source_contract.json`](../../benchmarks/maplight_source_contract.json).
The six-file source tree remains at revision `c249378c`; the paper is
`arXiv:2310.00174v1`. The fixed representation declares 2,563 values and the
GIN variant 2,863. No exact historical environment can be recovered from the
pinned public evidence because the upstream notebooks install unversioned
dependencies.

Two source corrections now control reproduction. The unchanged notebook runs
`ppbr_az`, not VDss or a CYP task. The notebook sends five seed-specific
prediction vectors separately and does not average their probabilities. The
historical PyTDC version is unpinned; local reproduction therefore uses the
frozen PyTDC 1.1.15 seed-metric rounding rule with that gap disclosed. A
predeclared arithmetic probability mean is retained separately as the local
paired comparator.

The three-family public-test budget is frozen in
[`phase_0_75_evaluation_budget.json`](../../benchmarks/phase_0_75_evaluation_budget.json).
All nine family-task slots remain reserved and unconsumed. The public test was
already observed in Phase 0.5, so a new complete task prediction consumes its
slot before scoring. The fixed and GIN families each retain five seed columns
plus one separately labeled probability-mean column. No AUROC, strict companion,
bootstrap, or other diagnostic score is authorized by this initial budget.

The global split input and deterministic assignment algorithm are frozen in
[`tdc_cyp_shadow_v1_contract.json`](../../benchmarks/tdc_cyp_shadow_v1_contract.json).
The generated artifact preserves all 30,038 `train_val` rows and 15,354 global
standardized structures. It contains 9,114 scaffold groups and 9,902 chemistry
communities. It uses one global assignment for all tasks, three predeclared
repeats, a nonchiral Bemis-Murcko protocol, and a chiral Morgan Taylor-Butina
community protocol at Tanimoto 0.60. Exact duplicates are always global.
Scaffold and community groups are indivisible in their respective protocols;
the two systems are not unioned.

The topology contains 70 duplicated structure-task cells and 11 cells with
conflicting labels. Every official row remains. Forty-one standardized hashes
also map to more than one raw SMILES. Grouping uses standardized identity, but
exact MapLight features must remain keyed to each raw official input rather
than silently deduplicating by standardized hash.

Two independent trusted projections produced byte-identical row and manifest
files. Their SHA-256 values are `924deea0` and `35ef619f`. Two independent
label-free assignments produced byte-identical `shadow_rows.csv` bytes with
SHA-256 `b633af0c`. The assignment receipts differ only in runtime and peak RSS:
27.95 seconds and 3.91 GiB for the canonical run, and 31.17 seconds and 3.58 GiB
for the repeat. Both remain below the 240-minute and 12-GiB caps.

The reviewed parent contract left six byte-level implementation choices open.
The pre-result implementation contract now fixes the full one-to-one identity
join, numeric source-row sorting, semantic non-use of canonical provenance,
raw-form counts, logical receipt paths, and exact artifact schemas. Focused
research code implements three process boundaries: trusted train-only
projection, label-free global assignment, and post-hash train-only summary.
Three thin scripts expose only those paths. Synthetic tests cover determinism,
immutability, raw-string preservation, scaffold fallback, chiral Morgan
community mechanics, the real inclusive distance-0.40 API boundary, exact fold
hashes, duplicate rows, class support, identity-first label access, clean source
binding, active resource caps, complete receipt-chain validation, and retained
blocker evidence. Assignment output is promoted atomically from a staging root.
All real inputs remained stable and read-only for each process lifetime.

The separate summary verified the complete assignment chain before parsing
exactly 30,038 frozen `train_val` labels. It parsed zero public-test labels.
The final manifest SHA-256 is `3eb97271`; its output aggregate is `20b00bf7`.
It confirms 29,961 structure-task cells, 70 duplicated cells, 77 excess rows,
11 conflicting-label cells, and 9 affected structures. Every task, protocol,
repeat, outer fold, inner fold, and corresponding training population contains
both classes. Total positives and negatives are 3,275/6,398 for CYP2C9,
2,071/8,433 for CYP2D6, and 4,028/5,833 for CYP3A4.

Three independent artifact reviews verified projection and assignment bytes,
global group and fold assignments, class-support arithmetic, frozen duplicate
and conflict counts, receipt hashes, and exact accounting. Generated roots are
ignored by Git and read-only. The
freeze generated no feature matrix, model fit, prediction, public-test label
parse, or metric evaluation. All nine public-test family-task slots remain
unconsumed.

## Phase 0.75 Stage A contract freeze

The fixed-feature execution contract is frozen in
[`maplight_fixed_stage_a_contract.json`](../../benchmarks/maplight_fixed_stage_a_contract.json).
It uses exact raw TDC strings for every representation so preprocessing cannot
explain a feature-block contrast. Raw rows remain bound to task, molecule ID,
numeric source row, raw-string hash, and standardized hash. Exact-raw caching
is allowed; standardized-hash caching is forbidden.

The compatible environment is separate from the core install and locked under
`research/maplight-fixed/`. It uses Python 3.10.13, RDKit 2023.03.3, CatBoost
1.2.1, NumPy 1.25.2, pandas 2.0.3, scikit-learn 1.3.0, and SciPy 1.11.2. The
transitive release cutoff is 2023-08-29 UTC. This is a new result-blind
compatible environment, not the unrecoverable historical MapLight environment.
The pinned source's six files are preserved in one read-only ignored root.

Stage A has six unique candidates. Five CatBoost representation states move
from binary chiral Morgan through the complete 2,563-value MapLight matrix.
The sixth candidate applies one frozen ExtraTrees diagnostic to the complete
matrix. The complete CatBoost state is also the predesignated five-seed
comparator, so it is not fitted twice. Across three tasks, two protocols, and
three repeats, the contract authorizes exactly 162 CatBoost fits and 18
ExtraTrees fits. There is no inner selection and no Stage A winner selection.

Only two contrasts are confirmatory: complete MapLight versus binary Morgan at
CatBoost seed 1, and CatBoost versus ExtraTrees on the complete representation.
Each protocol uses 2,000 synchronized global-group bootstrap replicates. The
full budget is 198 point AUPRC evaluations plus 108,000 bootstrap AUPRC
evaluations. Scaffold and community intervals remain separate. Any point
AUPRC at or above 0.95 stops work for an independent forensic audit.

The contract requires synthetic byte-level parity before real features, two
byte-identical label-free feature roots before fitting, cell-specific
outer-training target files, model predictions hashed before scoring labels can
be opened, and independent review at every irreversible boundary. Contract
freeze generated no synthetic or real feature array, target projection, model
fit, prediction, metric evaluation, public-test use, GIN weight, or challenge
assumption. All nine public-test family-task slots remain unconsumed.

Three independent reviews passed exact signed source head `63a3c8c`. They
verified the source and environment receipts, six-candidate design, fit and
metric arithmetic, process firewalls, claim limits, zero scientific accounting,
and Occam scope. Hosted CI passed Python 3.11 and 3.14. The tracked contract
test file contains four test functions. An immediate pull-request comment
corrects one earlier commit body that said five; reviewed history was not
rewritten.

## Phase 0.75 topology, parity, and feature-build outcome

The label-independent topology report is frozen under
`artifacts/benchmarks/tdc-cyp-shadow-topology-v1`. It covers 35,963 validation
structure records and 287,433,973 pair comparisons. Exact-raw and standardized
duplicate crossing are zero in every task, protocol, and repeat. The maximum
train-validation Morgan similarity nevertheless reaches 1.0 in some cells,
and the proportion with a training neighbor at or above 0.60 ranges from about
0.198 to 0.346. The correct claim remains chemistry-cluster-held-out; the
shadow is not a demonstrated strict analog firewall. The manifest SHA-256 is
`cf4d4bb7`; the detailed validation topology SHA-256 is `0f575a2d`.

The exact eight-row fixed-feature parity passed in the frozen Python 3.10
environment. Five upstream arrays matched both independent local processes
element-for-element and byte-for-byte. The complete matrix has 2,563 columns;
the retained parity receipt SHA-256 is `68ee584a`. Morgan and Avalon fixture
maxima are 10 and 24, so the fixture proves count rather than binary behavior.
An initial infrastructure attempt stopped before local feature generation
because the dynamic loader did not register the dataclass module. Its immutable
receipt is preserved with SHA-256 `bd5a580b`; the signed loader fix introduced
no feature-rule change.

The first real label-free feature build then stopped at exact-raw input index
66, hash `ad830254...`, in the Avalon block. Independent diagnosis under the
same pinned RDKit found one sparse bin with count 144. Upstream's zero-length
`numpy.int8` conversion would wrap that value. The frozen Stage A contract
explicitly requires counts in 0 through 127 and forbids wrapping, widening,
clipping, binarizing, or retaining any matrix after a violation. The blocker
receipt SHA-256 is `f5276200`. The compact tracked diagnosis receipt is
[`maplight_fixed_stage_a_feature_blocker.json`](../../benchmarks/receipts/maplight_fixed_stage_a_feature_blocker.json),
SHA-256 `c69bd826`. It records 0 persisted arrays, targets, fits, predictions,
metrics, public-test rows, labels, or consumed family-task slots.

This contract cannot produce the row-aligned fixed comparator. Stage B cannot
start because it requires fixed-MapLight shadow predictions. A separately
authorized, pre-result compatibility experiment could reproduce upstream
signed-`int8` wrapping exactly, but that would be a new experiment with a
different safety rule. Do not infer that authority or silently alter the
frozen contract.

## Phase 0.5 benchmark contract

- Required Track A uses the compound-level CYP3A4 inhibition table from the
  public OpenADMET Octant CYP release as an assay-conditioned pIC50 regression
  benchmark. Its active-enzyme preincubation context is not equivalent to the
  challenge's minus-NADPH direct-inhibition endpoint.
- Required Track B uses the TDC benchmark-group fixed train/test contract for
  `CYP2C9_Veith`, `CYP2D6_Veith`, and `CYP3A4_Veith`, with AUPRC as the primary
  comparison metric. `CYP1A2_Veith` is supplemental and must be labeled as
  using a separately documented scaffold protocol.
- Candidate selection uses only grouped inner validation within TDC
  `train_val`; the fixed public test split is evaluated once per retained
  model family and every evaluation is recorded.
- External scores are comparable only when dataset revision, target and label
  definition, split, metric, preprocessing or disclosed difference, and
  evaluation population match. Official, strict leakage-audited, Octant, and
  optional activity-cliff results remain separate.
- The minimum native model ladder is prior, ECFP linear, similarity-weighted
  kNN, and one justified nonlinear fixed-feature model. All learned
  combinations use complete out-of-fold predictions.

## Selected public sources

- OpenADMET Octant CYP inhibition/reactivity blog release:
  `openadmet/Octant_CYP_inhibition_reactivity_blog_release` on Hugging Face.
- TDC ADMET benchmark group: the three required Veith CYP inhibition tasks
  listed above.
- OpenADMET CheMeleon CYP model as the first external inference reference,
  subject to an explicit training-overlap audit and contamination warning.
- MoleculeACE is optional and limited to at most three preselected tasks after
  both required tracks are reproducible and reported.

Exact revisions, licenses, file hashes, row counts, schemas, package versions,
and dated leaderboard anchors are frozen in
`benchmarks/public_sources.json`. Raw source files and generated benchmark
artifacts remain outside Git.

## Strongest evidence

- The official 2026-07-29 announcement confirms a 750-compound test set built
  as ten close analogs for each of 75 potent hits.
- The live and fully blinded leaderboard subsets are grouped by analog family.
- Direct inhibition covers CYP1A2, CYP2C9, CYP2D6, and CYP3A4; TDI scoring
  covers CYP3A4 and CYP2D6.
- The official schema, metric code, submission contract, data snapshot, and
  complete rules are not frozen until the 2026-08-17 launch.
- The locked Phase 0 toolchain builds with RDKit as the sole runtime dependency;
  pandas, Pydantic, and a CLI framework remain absent.
- The synthetic audit detects and records invalid chemistry, fragment-parent
  changes, assigned and unassigned stereochemistry, and standardized
  duplicates without using official challenge data.
- The deterministic fixture split keeps standardized duplicates together,
  excludes quarantined chemistry, and is explicitly labeled as a pipeline test
  rather than challenge-faithful validation.
- The trivial median model uses only uncensored numeric training measurements;
  its model and split hashes bind the 21 deterministic predictions and cards
  to the recorded inputs and resolved seed.
- The report verifies all manifest-listed artifact hashes before rendering and
  states that the fixture, split, and model do not support biological or
  competition-performance claims.
- Hosted CI passed the installed-wheel vertical slice twice on Python 3.11 and
  3.14 using read-only permissions, locked dependencies, and full action SHAs.
- Independent review found silent raw-structure trimming, non-finite numeric
  acceptance, malformed-row acceptance, missing source revision binding, and
  an unreported unsupported context. The release candidate preserves exact raw
  text, rejects malformed numerics and rows, binds `v0.1.0`, and reports the
  unsupported context explicitly.
- The Octant source contract pins dataset revision
  `96dc1cceaa545a22041d1e16a9c2524a658403f8` and compound-level file SHA-256
  `19e537166a17a42dd50cc262dd6eb0a963c181830fdc52db0fba98533e01c9c6`.
- Independent source review found that Octant adapter v1 incorrectly labeled
  the NADPH condition as unreported. The pinned protocol actually supplies
  100 uM NADP+ with G6P/G6PD regeneration during active preincubation. Adapter
  v1 is rejected; v2 pins the protocol and represents NADPH-generating
  metabolic conditions without claiming exogenous NADPH was directly added.
- The remediated adapter preserves raw structure text, source QC values, assay
  context, revision, data hash, and protocol hashes. Its full-data rehearsal
  retains all 1,340 molecules, maps the 1,084 numeric pIC50 rows, and explicitly
  records 256 missing-pIC50 omissions. Two v2 runs are byte-identical.
- All 1,340 Octant structures pass the Phase 0 chemistry audit; 424 carry an
  unspecified-stereochemistry warning. No molecule is quarantined, silently
  standardized, or linked to a quarantined measurement.
- Development metadata advances to `0.2.0.dev0` with source state
  `unreleased`; signed Phase 0 tag `v0.1.0` remains immutable.
- The exact TDC archive maps all 37,550 rows across the three required tasks;
  all molecules are accepted. The canonical audit records 1,731
  standardization changes and 21,492 repeated standardized structures across
  task and partition rows. Adapter artifacts reproduce byte-for-byte.
- The TDC source record binds Harvard Dataverse DOI `10.7910/DVN/21LKWG`
  version 105.0 and discloses that its CC0-1.0 declaration conflicts with the
  TDC task pages' CC-BY-4.0 declaration. The more conservative CC-BY attribution
  policy remains in force. The hashed PyPI sdist is authoritative for PyTDC
  1.1.15; inspected evaluator-source revision `c310c35f` declares 1.1.14 and is
  cited only as evidence that `pr-auc` maps to average precision.
- The frozen Octant split contains 937 Bemis-Murcko scaffold groups and five
  exactly balanced 268-row folds. Fold 0 is outer validation; the other folds
  are training and four grouped inner folds. Assignment is deterministic and
  label-independent.
- TDC has no raw-SMILES train/test overlap, but standardization exposes 4, 2,
  and 1 test rows overlapping `train_val` for CYP2C9, CYP2D6, and CYP3A4.
  Official test populations remain unchanged; a hashed 7-row strict companion
  exclusion set is frozen separately. The later official scorecard preserves
  all rows and reports the strict population as a separate companion analysis.
- Independent review showed that split-audit v1 accepted coordinated task,
  partition, and source-row tampering. Split-audit v2 binds official split bytes
  to the adapter manifest and validates every row against canonical provenance,
  source, and expected isoform; adversarial tampering now fails.
- All 30,038 TDC `train_val` rows are frozen in four label-independent,
  row-balanced scaffold folds per task. No test row, standardized duplicate, or
  scaffold group crosses an inner fold. The retained root receipt documents and
  hashes every split artifact with aggregate
  `b7f2d0f7d18bcc7d5815cdc3919a9681523ccf380246449c32e54b7c80465b12`.
- One focused command rebuilt the entire public-data freeze from an absent
  root: fetch, Octant and TDC preparation/audit, and validation. It verified
  exact source sizes and hashes, reproduced every retained artifact
  byte-for-byte, and emitted deterministic aggregate
  `0dc587c61b02f90df04e599deff771117ad52b5cfe16f10d606359bc8548d8d4`.
  Average precision tests enforce the TDC higher-is-better metric polarity.
- Independent re-review passed on exact signed head `58b0661` after a separate
  live reconstruction. It verified source and receipt hashes, row and group
  integrity, adversarial tamper rejection, 24/24 byte-identical retained files,
  zero model fits and public-test evaluations, 57 tests, static checks, builds,
  signatures, and hosted Python 3.11/3.14 CI. PR 11 merged by fast-forward with
  the reviewed signature intact.
- The native selection contract freezes 1 prior, 3 ECFP-linear, 6 Tanimoto-kNN,
  and 3 ExtraTrees candidates per task. It verifies the full validation receipt
  chain before fitting and keeps NumPy, SciPy, and scikit-learn 1.9 outside the
  core wheel in a benchmark-only dependency group.
- Two real selection runs each complete 240 grouped fits in about 216 seconds
  on a local Apple CPU and produce byte-identical outputs: 401,830 candidate
  OOF rows, 123,640 retained OOF rows, and 92,730 retained stochastic-seed
  rows. A separate scikit-learn recomputation matches all 16 retained
  task-family scores and every receipt hash.
- Octant inner-selection MAE is 0.7270 for the median prior, 0.6818 for ECFP
  ridge, 0.6565 for kNN, and 0.6496 for three-seed ExtraTrees. TDC grouped-inner
  AUPRC for the retained linear, kNN, and ExtraTrees models is respectively
  0.7527/0.7081/0.7417 for CYP2C9, 0.6513/0.6042/0.6607 for CYP2D6, and
  0.8293/0.7828/0.8187 for CYP3A4. These values are not comparable to the dated
  fixed-public-test anchors.
- Held-out prediction v1 is frozen separately and reproduces byte-for-byte
  across two runs: 7,724 structures, 30,896 retained prediction rows, 23,172
  stochastic-seed rows, 24 fits, aggregate
  `d9ca7e6d236a11fa031f485d68d05af5521b3a91e439ca154b9d08d9e4168b0d`,
  and zero numeric held-out labels parsed or evaluations. Independent review
  rejected the stronger structural label-blind claim because v1 still opened
  and hashed complete measurement tables before filtering.
- The corrected source/split boundary materializes 30,910 training
  measurements and zero held-out measurements. Prediction v2 accepts only this
  label-absent view and reproduces both frozen prediction CSVs byte-for-byte;
  no canonical measurement path exists in the model-facing interface.
- Real scoring attempt 1 parsed the 7,724 frozen held-out labels, then failed
  before writing a score because the anchor loader expected
  `tdc_leaderboards` beneath `tdc_admet` rather than at its actual sibling
  source-manifest path. No score or partial output exists; models,
  configurations, thresholds, predictions, and populations remain unchanged.
  A retrospective durable receipt records the supported facts and explicitly
  discloses that the exact raw traceback was not retained.
- After a signed path-only remediation and an explicit attempt-number fix,
  scoring attempt 2 completed: 12 official TDC evaluations, 12 strict companion
  analyses, and 4 Octant outer evaluations. Scorecard aggregate is
  `2cc47a1600b5809a4317b8c8ec719bc702e43d6e6f9b335d0f189c3546720a1a`.
- Best native official TDC AUPRC is ECFP logistic 0.7340 for CYP2C9,
  ExtraTrees 0.6474 for CYP2D6, and ECFP logistic 0.8431 for CYP3A4. These trail
  dated Chemprop-RDKit anchors by 0.0430, 0.0256, and 0.0329 and MapLight + GNN
  by 0.1250, 0.1426, and 0.0729. No superiority claim is supported.
- Removing the seven standardized-overlap test rows changes AUPRC by no more
  than 0.0006 for any retained native family. Best Octant grouped-outer MAE is
  0.5489 from ExtraTrees versus 0.6663 for the training-median prior.
- Independent scorecard review reproduced all selection and held-out scores,
  populations, thresholds, seed means, and hashes, but blocked PR 18 on the
  firewall and artifact-contract gaps above. Scorecard v4 preserves every v1
  point field while adding revisions, split/population hashes, public-reference
  standard deviations and deltas, runtime/hardware, comparison status, and
  aggregation warnings. It records 21 additional label-dependent evaluations
  of the three already frozen ExtraTrees seeds and no seed/model selection;
  aggregate is `03a3ee6c1dc14b57c1c6cff47abf1d3e2f1b093e6aed7783b03cf984deb436bc`.
- Re-review validated every remediation mechanic but found that scorecard v2
  repeated the seven-row cross-task contamination total on each task row.
  V3 corrected 4/2/1 counts but used plural wording for CYP3A4. Both remain
  rejected local candidates. V4 reports four CYP2C9, two CYP2D6, and one
  CYP3A4 overlap row while explicitly identifying seven across all tasks; its
  two completed artifact roots are byte-identical.
- The completed 123,640-row OOF observation artifact carries uncertainty when
  available, explicit applicability availability, scaffold support, measurement
  quality, and observation-level configuration/data/split hashes. Its aggregate
  is `5b9262fa2e178c1ea08d0660904f08f211dc297b72ef8b9f4eb95e79272844e6`.
  Independent same-input repeats of the prediction view, corrected prediction,
  OOF artifact, and v4 scorecard are byte-identical across all 16 retained files.
- Final independent re-review passed on exact signed head `dd7960c`. It verified
  the structural firewall, every receipt chain and repeat, all OOF enrichment,
  every allowed-seed analysis, exact preservation of the 28 original point
  rows, accurate 4/2/1 task warnings, signatures, sole `zchboswell` authorship,
  local checks, and hosted Python 3.11/3.14 CI. PR 18 merged by exact
  fast-forward with the reviewed GitHub-verified signature intact.
- D-019 was signed and merged before fitting. Independent review rejected
  combination v1 because it opened full canonical measurement tables before
  filtering, despite using no held-out numeric value. V2 corrected the
  interface but omitted 20 NNLS solves from its fit count. Both remain rejected
  immutable evidence.
- Combination v3 accepts only the receipt-bound label-absent training view. It
  reports 384 base-model fits, 16 nested NNLS fits, 4 final NNLS fits, and 404
  total operations. Its two complete runs took 470 and 471 seconds, reproduce
  all eight files byte-for-byte and every v1 scientific payload exactly, and
  have aggregate
  `c63b40b2c80981a437fdc2baa48d4ece5ecdc8b7e50594e75578cf04e8503b12`.
  Held-out label access and evaluations are structurally zero.
- The unweighted mean is retained for all four tasks. Versus the grouped-OOF
  best single family, it lowers Octant MAE from 0.6496 to 0.6344 and raises TDC
  AUPRC from 0.7527/0.6607/0.8293 to 0.7665/0.6723/0.8370. The nested NNLS
  stack trails the mean on every task and is rejected by the frozen complexity
  gate; no learned stack survives.
- The exact-structure-grouped random companion makes every learned family look
  better: Octant MAE optimism is 0.0247-0.0347 and TDC AUPRC optimism is
  0.0100-0.0376. These results quantify split optimism only and were not used
  for configuration or combination retention.
- Independent re-review passed on exact signed head `d02dc9b`. It verified the
  structural label firewall, 384+16+4 fit accounting, all eight repeat files,
  full scientific invariance, nested isolation, random grouping, zero held-out
  access, repository checks, and Occam's Razor. It found no actionable excess
  complexity. PR 21 merged by exact fast-forward with the reviewed signature.
- The retained-mean prediction stage accepts only combination v3 and held-out
  prediction v2. Two runs produce 7,724 byte-identical predictions with
  aggregate
  `b6e6db44f7436655cd978f181b326ef445fe39057430dae68ccb51afb2c5c873`.
  The receipt records 30,896 base predictions averaged, zero fits, zero
  measurement tables opened, zero labels parsed, and zero evaluations.
  Independent review passed on exact signed head `725d162`; it reproduced all
  arithmetic and receipts, exercised malformed-input rejection, found no
  actionable complexity, and confirmed hosted CI. PR 23 merged by exact
  fast-forward. The prediction remains unscored.
- Independent review rejected scorer head `8da9aa9` because two deterministic
  checks occurred after synthetic label loading. Remediation `9f0b706` moved
  them before both label loaders; re-review passed on exact head `9c02043`, and
  PR 25 merged by exact fast-forward.
- The first real invocation then failed in preflight because the validation
  root retains the official-split hash but does not duplicate the split file.
  It opened zero labels, ran zero evaluations, and created no output. The
  retained failure receipt is
  `benchmarks/receipts/retained_mean_scoring_preflight_attempt_1.json`; all real
  retained-mean scores remain unknown.
- Remediation `925dccf` makes the audited source official split an explicit
  scorer input. The regression test removes the fixture copy from the
  validation root. Independent review passed on exact head `27c11ae`, and PR
  26 merged by exact fast-forward. No metric, threshold, candidate, population,
  or evaluation count changed.
- The one authorized real scoring attempt completed in 2.94 seconds. The
  retained mean improves every native held-out result: Octant MAE is 0.5434,
  and TDC AUPRC is 0.7484/0.6547/0.8500. The gains over the prior native best
  are 0.0055 lower MAE and +0.0144/+0.0073/+0.0068 AUPRC. It still trails the
  Chemprop-RDKit anchors by 0.0286/0.0183/0.0260 AUPRC. The raw score aggregate
  is `e91329cca76159b42d9f539850420ecf1b960aafe66592148788001864064db0`.
  Independent review passed on exact head `c112d40`, and PR 27 merged by exact
  fast-forward. No superiority claim is supported.
- Offline scorecard completion opens no canonical measurement path and adds no
  evaluation. V1 is rejected because it combined base and combination
  selection runtime in one row field. V2 separates the components but encodes
  manifest seconds as text. V3 corrects runtime types but does not bind the
  public-source file and Octant split back to the scoring receipt. V4 adds both
  exact hash checks. It has seven rows, 51 columns, byte-identical repeats,
  unchanged point results, and aggregate
  `d07d52e6b826c0f01e498c60330d163d747a09b4f4c5ba6a0e507b53bbd58afa`.
  Independent re-review passed on exact signed head `d34ba02`. It verified the
  two scoring-receipt bindings and tamper tests, exact v3/v4 scorecard
  invariance, byte-identical roots, all 51 fields, zero added label access,
  evaluations, fits, point changes, or selection changes, repository checks,
  signatures, hosted Python 3.11/3.14 CI, and Occam's Razor. PR 28 merged by
  exact fast-forward with the reviewed signature intact.
- D-021 freezes one external-model attempt before inference. It binds the exact
  CheMeleon checkpoint, required files, resolved 7.72 GB linux/amd64 container
  digest, five-column label-free 7,724-structure projection,
  standardized-structure overlap audit, fixed task mappings and polarity,
  two-run reproducibility requirement, eight scoring analyses, 120-minute and
  25-GiB budgets, and a no-patch failure boundary. It adds no core dependency,
  CLI surface, or ensemble candidate. Contract v1 at head `2596469` is rejected
  because it incorrectly treated outcome-bearing molecule provenance as
  model-facing label-absent input; the stripped projection is its remediation.
- The corrected preparation boundary projects only benchmark, task, molecule
  ID, standardized structure, and structure hash. Two real preparation runs
  are byte-identical across 7,724 rows with exact 212/2,419/2,626/2,467 task
  counts, population-key hash `ebdc065f`, and aggregate `18332ea6`. The receipt
  records zero measurement tables opened, provenance outcomes parsed, held-out
  labels parsed, native predictions consumed, fits, or evaluations. The
  broader roots cannot be mounted into the future container.
- Independent re-review passed on exact signed head `db51e24`. It verified the
  checkpoint and container provenance, all five projection columns, exact key
  order and task counts, source and output receipt chains, hidden-outcome
  stripping, tamper rejection, the read-only mount boundary, zero label or
  prediction consumption, repository checks, signatures, hosted Python
  3.11/3.14 CI, and Occam's Razor. PR 30 merged by exact fast-forward.
- Prediction-path revision `a9c6b41` verifies every pinned checkpoint file,
  audits exact training overlap with the frozen standardizer, constructs a
  network-disabled container command with only the safe input, model, and
  output mounts, validates the four-row smoke probe, aligns finite multitask
  predictions, and requires two byte-identical canonical runs. Six new focused
  tests bring the suite to 76. No model has been downloaded or run and no
  benchmark label has been opened. This code awaits pre-attempt review.
- Independent code review rejected head `7d0b9ea` before external action: the
  reviewed input uses literal task values while contract v1 used prefixed
  mapping keys, so the smoke probe would have failed after download and pull.
  Remediation `0936323` introduces contract v2, validates exact task-set
  equality before output creation, strengthens runtime and image-plus-file disk
  enforcement, and binds raw outputs, logs, and failure-state files. Input v3
  reproduces all five columns, 7,724 rows, task counts, key hash, CSV hash, and
  aggregate exactly; only its contract receipt changes. No external action has
  occurred.
- Independent re-review rejected signed head `4808121`. The input mapping,
  runtime, disk accounting, raw/log binding, and safe container boundary pass,
  but prediction did not verify the overlap receipt against the current
  contract and input. The runner also accepted caller-selected output paths and
  source revisions. Remediation `d613116` and input v4 remove those freedoms:
  one fixed repository input, output, and adjacent exclusive start sentinel are bound to
  a clean Git revision, and all overlap provenance is checked before canonical
  prediction. Input bytes and scientific hashes remain unchanged. Eight new
  focused checks bring the suite to 86. No external action has occurred.
- Final review passed exact signed head `e324d11`: 8/8 provenance tamper cases,
  all 86 tests, repository checks, hosted Python 3.11/3.14 CI, signatures,
  authorship, input-v4 repeat, zero external action, and Occam simplicity pass.
  PR 32 merged by exact fast-forward. The 25-GiB rule is checkpoint accounting
  over retained apparent files plus Docker's reported image size. It is not an
  OS quota and does not measure transient pull storage or Docker metadata.
- The single fixed CheMeleon attempt ran from clean merged revision `7f631c1`.
  The exact model download, all file hashes, 7,724-row overlap audit, and exact
  image pull passed. The four-row smoke then failed before prediction: the
  upstream image's `boto3` import requests `DocumentModifiedShape` from its
  incompatible installed `botocore`. Elapsed time was 4,079.057 seconds.
  Exact training-structure overlaps were 8/13/8 for TDC CYP2C9/2D6/3A4 and 4
  for Octant. Smoke predictions, full runs, label parses, fits, evaluations,
  and scores are all zero. The retained-files aggregate is
  `374f46222e5ce75d93e7e578133ab1c352d6084b77e056a7e89693161e76f4c6`.
  D-021 forbids a patch or retry; CheMeleon is rejected as upstream environment
  evidence for Phase 0.5.
- Independent audit passed the failure evidence: all 15 retained hashes, nine
  model files, exact image/platform, 33 overlaps, four smoke identities, zero
  scientific counts, 4,079.06-second runtime, 7.771-GB checkpoint accounting,
  clean source revision, and permanent no-retry sentinel match. No CheMeleon
  scoring or replacement external model is permitted in Phase 0.5.
- A label-agnostic topology audit supports one minimal residual test at frozen
  nearest-neighbor Tanimoto >=0.50: 377 Octant rows and 4,208/4,678/4,086 TDC
  CYP2C9/2D6/3A4 rows, with at least 81 supported rows per grouped fold. D-022
  freezes one fit-free correction from the retained unweighted mean toward the
  existing cross-fitted kNN prediction. The formula, abstention, two controls,
  paired bootstrap, and all-or-nothing retention rule are fixed before any new
  candidate score is computed. No held-out artifact is in scope.
- Independent pre-result review rejected contract v1 because it left OOF join,
  control permutation, bootstrap, clipping, direction, tie, and fold-population
  details open. Contract v2 fixes exact 30,910-row alignment, SHA-256-derived
  permutations, paired scaffold-group resampling within folds, percentile
  interpolation, directional formulas, all-row fold consistency, and strict
  tie failure. It also discloses 476 threshold-equality rows that are supported
  but receive zero correction. No candidate result has been computed.
- Final pre-result review passed exact signed head `b16967e` and contract hash
  `824bff16`. It independently verified all receipt, join, topology, control,
  bootstrap, retention, chronology, signature, CI, and Occam checks. PR 35
  merged by exact fast-forward. Candidate outcomes, held-out access, fits, and
  implementation code were zero at this gate.
- Signed implementation commit `8a4f351` added one direct package module, one
  research script, and six focused synthetic tests. Independent review passed
  exact head `129af20`: receipt ordering, alignment, formula, controls,
  bootstrap, decision logic, 92 tests, CI, signatures, and Occam all passed.
- Two real grouped-OOF runs from `129af20` each process 30,910 rows in about
  325 seconds and produce five byte-identical files with aggregate `a6248c4e`.
  The residual worsens full and supported performance on all four tasks, has
  zero positive folds on every task, and fails both control requirements.
  Supported lower 95% bounds are all negative. All 17,561 remote rows abstain
  exactly. Fits and held-out parses, predictions, and evaluations are zero.
- Independent post-result audit regenerated every formula/control row, all 300
  point evaluations, all 80,000 bootstrap evaluations, all 32 intervals, and
  the decision. Maximum metric and interval differences were 2.6e-15 and
  4.3e-15. D-022 therefore rejects the candidate. The implementation, script,
  and tests are removed; the compact contract, ledger, Git history, and ignored
  local result roots preserve the negative evidence. Tracked rejection receipt
  SHA-256 is `4def7727`. No retry is permitted.
- The final tracked Phase 0.5 report synthesizes the exact retained-mean and
  family scorecards, source/split evidence, CheMeleon blocker, and series
  rejection in tables only. Report SHA-256 is `3a70e9f3`; receipt SHA-256 is
  `06af9e6e`. Receipt v2 preserves every aggregate table input so a clean clone
  can verify the report without repeating a held-out evaluation. It tracks no
  raw row, label, structure, or prediction and adds zero fit, score, or
  held-out access.
- Final closeout review passed exact signed head `9150e93`. The reviewer used a
  clone without local artifacts, verified every receipt and canonical origin,
  passed the four focused report tests before benchmark dependencies and all 90
  tests after locked installation, and confirmed zero new scoring or held-out
  access. PR 38 merged by exact fast-forward with both reviewed signatures.

## Active hypotheses

1. The fixed MapLight method can be reproduced on exact TDC rows within a
   declared tolerance or its version drift can be diagnosed precisely.
2. Count fingerprints, pharmacophore features, and ordered physicochemical
   descriptors add shadow-benchmark information beyond binary ECFP estimator
   diversity.
3. A frozen pretrained GIN representation adds real shadow-benchmark value
   beyond the fixed representation and does not pass shuffled-row or
   same-dimensional-noise controls.

The broader parent-relative and cross-isoform hypotheses remain scientifically
important but are not active Tier 1 model experiments. The rejected Phase 0.5
similarity residual remains closed; it is not evidence for or against a future
measured-parent transformation model.

## Unresolved risks

- Launch-day schema and scoring details may invalidate provisional assumptions.
- The provisional RDKit fragment-parent policy must be re-evaluated against
  official structure semantics before it is used on challenge data.
- Series inference may be ambiguous without explicit parent identifiers.
- Low-activity interval handling may dominate regression behavior.
- TDI labels may be unstable near potency and shift thresholds.
- Browser-rendered visual QA of the static report remains unperformed; its
  deterministic content, escaping, and artifact validation are tested.
- Windows installation remains untested.
- GitHub cannot enforce branch protection while the personal repository is
  private on the current account plan; branch and pull-request discipline is
  procedural until publication or a plan change.
- Public benchmark scores can be misleading when dataset revisions, splits,
  assay contexts, preprocessing, class prevalence, or evaluation populations
  differ.
- Accessible public test labels create a test-overfitting risk; all test-set
  evaluations must be counted and isolated from candidate selection.
- Standardized structures or near-duplicates may cross official TDC split
  boundaries. Official scores must remain unchanged and be accompanied by a
  separate strict leakage analysis.
- External predictors may have trained on benchmark structures. A result is
  not clean zero-shot unless overlap is excluded with evidence.
- Public benchmark plumbing could expand into a framework and displace the
  product. Only two concrete required adapters are authorized.
- The repository is now intentionally public, but the README still describes
  it as private and understates the public benchmark record.
- MapLight has no frozen upstream environment, so RDKit, CatBoost, MolFeat,
  DGL, and pretrained-weight drift may prevent exact reproduction.
- Exact MapLight featurization uses raw TDC `Drug` strings, while leakage groups
  use standardized structures. Forty-one standardized hashes have multiple raw
  forms; a standardized-only feature cache would silently change the comparator.
- The TDC public test is already observed. Any new prediction family or repair
  after scoring could turn comparator reproduction into public-test-aware
  model selection.
- A feature or model consumer that ignores the frozen global shadow assignment
  could reintroduce cross-isoform molecule or chemistry-family leakage.
- The frozen Butina/community protocol has not yet been shown to exclude every
  close analog across train and validation. Until maximum cross-fold
  similarities are measured, call it chemistry-cluster-held-out rather than a
  strict analog firewall.
- Pretrained GIN training overlap may be known, present, or unknowable. Unknown
  provenance forbids a clean zero-shot claim.
- Heavy research dependencies could enter the all-groups core CI path unless
  environments remain isolated.

## Maximum Phase 0.5 scope

Two required public benchmark tracks, at most four native model families, at
most two external systems, one controlled series-residual keep/reject test when
the data topology supports it, one static benchmark report, and focused UX and
reproduction improvements. Benchmark dependencies remain optional, the core
installation remains lightweight, and the public CLI remains exactly
`audit`, `train`, `predict`, and `report`.

Phase 0.5 completed on 2026-08-10. Its scope is frozen. Reopen a Phase 0.5
artifact only for a demonstrated factual or provenance defect, not for model
tuning.

## Maximum Phase 0.75 scope

Tier 1 is one exact fixed comparator, one exact pretrained-GIN comparator
attempt, two frozen global shadow protocols, fixed representation ablations,
three possible TDC public-test prediction families, one scorecard, public
documentation, and the August 17 handoff. Tier 2 may audit AID 1851 and public
parent/analog topology but may not displace Tier 1. Add no challenge adapter,
foundation-model tournament, full multitask system, parent-relative model,
LLM adjudicator, service, database, dashboard, or general research framework.

## Exact next action

Preserve the topology, parity, infrastructure-failure, and real-feature blocker
artifacts. Do not retry the failed feature build, start build 2, fit Stage A,
start GIN, or consume a public-test slot under the current contract. Obtain
explicit authority either to close Phase 0.75 with this precise blocker or to
freeze one separate upstream-compatibility experiment that permits the exact
signed-`int8` count conversion while keeping all other rows, features, seeds,
and public-test boundaries unchanged.

Do not parse a real feature row until the synthetic implementation passes its
existing review gate. Do not inspect a new public-test label until fixed
MapLight, MapLight + GIN, and any eligible final contender prediction families
are all complete, hashed, reviewed, and frozen together. It is valid to leave
the final-contender family unused.

The following pre-freeze research already supports that action.

Selective pre-freeze source inspection identifies MapLight + GNN as the first
conditional comparator candidate. Its exact public method, source hashes,
reproducibility gaps, eligibility gate, and paired significance requirements
are recorded in
[`PUBLIC_COMPARATOR_INTAKE.md`](PUBLIC_COMPARATOR_INTAKE.md). This research adds
no model, dependency, fit, evaluation, or authority to bypass the launch freeze.
The same note records the official ExpansionRx postmortem as transfer evidence:
pretrained multitask graph models led that different blind challenge, while
four of its top five entries used proprietary data. It is a method prior, not a
CYP score or permission to copy an architecture.

One FDA-led public database is recorded in
[`PUBLIC_CYP_DATA_INTAKE.md`](PUBLIC_CYP_DATA_INTAKE.md) as a conditional
auxiliary-data source. It separates 623 CYP3A4 TDI labels from reversible CYP
labels, but combines heterogeneous evidence types and has no automatic mapping
to the challenge. External-data permission, assay compatibility, source terms,
overlap, and a grouped ablation must all pass after the launch freeze. Its
58-alert supplement is qualitative only: it lacks executable substructure
definitions, so the structural-alert feature path is rejected.

The official announcement now links to the public
`openadmet/cyp-challenge` Space. Its captured revision remains explicitly in
pre-challenge state with no dataset or tutorial link and TODO-marked values.
[`LAUNCH_INTAKE.md`](LAUNCH_INTAKE.md) records the official entry points,
current non-authoritative state, release-detection gate, and exact capture order.

On 2026-08-17, perform the launch freeze before model work:

1. acquire the authoritative release and preserve original bytes;
2. record URLs, timestamps, licenses, citations, file sizes, and SHA-256 hashes;
3. freeze the released schema, assay and censoring semantics, metric code,
   submission validator, rules, and external or transductive-data permissions;
4. audit structures and measurements without silently applying Phase 0.5
   assumptions;
5. construct label-independent analog-family and duplicate-safe validation
   groups before inspecting candidate results;
6. reproduce the strongest relevant public comparator on the exact evaluation
   rows before running the predeclared breakthrough ladder.

Do not map Octant or TDC fields automatically. Do not fit, select, or score a
challenge model until items 1–5 are frozen and independently reviewable.

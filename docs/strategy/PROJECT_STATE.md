# Project state

Last updated: 2026-08-10

## Current phase

Phase 0.5 complete — pre-launch hold for the authoritative challenge release.

## Active operating goal

Preserve the independently reviewed Phase 0.5 evidence without further public-
test tuning. On 2026-08-17, capture and hash the authoritative challenge
release, then freeze its license, rules, data snapshot, schema, assay semantics,
metric implementation, submission contract, and challenge-faithful validation
groups before model selection or adaptation.

After that freeze, reproduce the strongest relevant public comparator on the
same rows and run the smallest predeclared model ladder that can test fixed
chemical features, one pretrained graph representation, assay-conditioned
multitask learning, and family-safe combination. Claim superiority only from
paired, leakage-safe evidence with a positive lower confidence bound.

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

1. Parent-expansion validation will better predict blind performance than
   molecule-random validation.
2. Simple series residuals or shrinkage will improve predictions for close
   analog campaigns.
3. Local support and disagreement can predict expert error well enough to
   improve a simple cross-fitted stack.

The first hypothesis has supporting random-versus-grouped evidence. This one
predeclared test rejects the second hypothesis in its tested form; it does not
prove that every future series method must fail. The third remains untested.

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

## Exact next action

Selective pre-freeze source inspection identifies MapLight + GNN as the first
conditional comparator candidate. Its exact public method, source hashes,
reproducibility gaps, eligibility gate, and paired significance requirements
are recorded in
[`PUBLIC_COMPARATOR_INTAKE.md`](PUBLIC_COMPARATOR_INTAKE.md). This research adds
no model, dependency, fit, evaluation, or authority to bypass the launch freeze.

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

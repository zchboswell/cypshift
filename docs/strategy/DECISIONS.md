# Consequential decisions

## D-001 — Permanent project identity

- Date: 2026-08-09
- Status: accepted
- Decision: Use `cypshift` for the repository, Python package, and CLI.
- Evidence: A permanent name avoids migration churn and keeps installation,
  documentation, and publication references stable.
- Alternatives: A provisional or descriptive long-form package name.
- Reversal condition: A verified package-index or legal naming conflict.

## D-002 — Pre-launch Phase 0 fixture

- Date: 2026-08-09
- Status: accepted
- Decision: CI and examples use a tiny synthetic redistributable fixture before
  the challenge launch.
- Evidence: It enables a complete implementation without encoding unreleased
  schema or distributing restricted data.
- Alternatives: Wait until launch; develop directly against public CYP data.
- Reversal condition: None for CI. Public data may later supplement development
  after a license and provenance review.

## D-003 — Launch-day freeze boundary

- Date: 2026-08-09
- Status: accepted
- Decision: Freeze the official schema, data snapshot, metric, submission
  contract, rules, and challenge-faithful splits on or after 2026-08-17.
- Evidence: The official announcement explicitly defers detailed information to
  launch day.
- Alternatives: Hard-code announcement-derived assumptions.
- Reversal condition: OpenADMET publishes an earlier resource explicitly marked
  final and authoritative.

## D-004 — Signed, milestone-based development

- Date: 2026-08-09
- Status: accepted; repository is now public
- Decision: Develop using signed commits, short-lived branches, focused pull
  requests, and frequent passing milestone pushes. The repository began as a
  private personal repository and was made public after the Phase 0 licensing
  and disclosure checks passed.
- Evidence: Signed milestone commits and focused reviews provide a clean
  timecourse. Restricted data and generated artifacts remain outside Git.
- Alternatives: Public-from-start development; direct pushes to `main`.
- Reversal condition: None for public status; move sensitive work to separately
  controlled storage if a future data license requires it.
- Implementation note: Every post-bootstrap change uses a branch and pull
  request by procedure; force-pushes and unreviewed direct `main` updates remain
  prohibited by project policy.
- Merge procedure: GitHub's hosted rebase merge was tested on PR 1 and rewrote
  the SSH-signed branch commit as unsigned. Future pull requests are integrated
  only after review by fast-forwarding the signed branch commit locally and
  pushing that exact commit to `main`; the remote topic branch is then deleted.

## D-005 — Authorship and tooling provenance

- Date: 2026-08-09
- Status: accepted
- Decision: Git authorship is `zchboswell`; never identify Codex, OpenAI, an AI
  system, or an automated tool as an author or co-author. Record required model
  and tool provenance separately from authorship.
- Evidence: Authorship and reproducibility metadata serve different purposes.
- Alternatives: Automated co-author trailers.
- Reversal condition: None without an explicit owner decision.

## D-006 — Defer license selection

- Date: 2026-08-09
- Status: superseded by D-010
- Decision: Do not select the final permissive license until Phase 0 production
  dependencies and redistributed assets are known.
- Evidence: License compatibility must be checked against actual retained
  dependencies and data.
- Alternatives: Add a license before the dependency audit.
- Reversal condition: The dependency and asset set is frozen and compatible.

## D-007 — Orchestration continuity through Phase 0

- Date: 2026-08-09
- Status: accepted
- Decision: Keep the current orchestrator through Phase 0 and restore context
  from the canonical knowledge base after every compression or handoff. Add no
  architecture beyond what the running vertical slice requires.
- Evidence: The current orchestrator owns the intent and decision history;
  replacement before implementation would add context loss and duplicate
  planning.
- Alternatives: Hand implementation immediately to a fresh orchestrator.
- Reversal condition: Scope expansion, simplicity violations, or inability to
  leave a clean reproducible state. After Phase 0, use a fresh agent as an
  independent reviewer before considering orchestration handoff.

## D-008 — Minimal Phase 0 Python toolchain

- Date: 2026-08-09
- Status: accepted
- Decision: Develop with Python 3.12 while supporting Python 3.11 and newer;
  use `uv` and `uv_build`; retain RDKit as the sole runtime dependency; keep
  pytest, Ruff, and mypy development-only. Use the standard library for the
  CLI, CSV/JSON I/O, schemas, hashing, statistics, and HTML generation.
- Evidence: The host already provides Python 3.11/3.12 and `uv`. RDKit 2026.03.4
  provides Python 3.11-3.14 wheels across major platforms under BSD-3-Clause.
  The vertical slice requires chemistry parsing and standardization but does
  not require pandas, Pydantic, Click, Typer, or a configuration framework.
- Alternatives: system Python 3.9; pandas/Pydantic/Typer stack; a larger
  cheminformatics framework; Conda-only installation.
- Reversal condition: A launch-day requirement or measured user need that the
  standard library plus RDKit cannot meet cleanly.
- Sources:
  - https://pypi.org/project/rdkit/
  - https://www.rdkit.org/docs/Install.html
  - https://docs.astral.sh/uv/guides/integration/github/
  - https://docs.github.com/en/actions/reference/security/secure-use
- CI implementation note: Pin uv 0.12.3 and the full commits for checkout
  v7.0.1 and setup-uv v9.0.0. Test the declared minimum Python 3.11 and
  current Python 3.14 on Linux. The build-backend range follows uv's 0.12
  migration guidance while retaining an upper compatibility bound.

## D-009 — Phase 0 source-revision binding

- Date: 2026-08-09
- Status: accepted
- Decision: Release the completed Phase 0 state as package version `0.1.0` and
  bind its manifests to the signed Git tag `v0.1.0`.
- Evidence: Package version `0.0.1` covered multiple materially different
  commits and could not uniquely select reproducible source. A signed tag is
  available in both source control and installed-wheel metadata without adding
  a runtime dependency or requiring a Git checkout at prediction time.
- Alternatives: Read the local Git commit dynamically; add build-backend
  version plugins; retain package version alone without a source mapping.
- Reversal condition: Begin post-Phase-0 development, which must advance the
  development version before producing new run manifests.

## D-010 — Permissive code and fixture licenses

- Date: 2026-08-09
- Status: accepted
- Decision: License `cypshift` code under BSD-3-Clause. Keep the independently
  hand-authored synthetic fixture under its existing CC0-1.0 dedication.
- Evidence: Phase 0 retains RDKit as its only runtime dependency; RDKit is
  BSD-3-Clause. The development tools use compatible permissive licenses and
  are not runtime dependencies. The fixture contains invented data intended
  for unrestricted redistribution in CI and examples.
- Alternatives: MIT for code; Apache-2.0 for code; keep the repository
  unlicensed until public release.
- Reversal condition: A dependency, asset, employer, journal, or legal review
  identifies an incompatibility before public release.

## D-011 — Bounded public-data Phase 0.5

- Date: 2026-08-09
- Status: accepted
- Decision: Resume bounded pre-launch development using named, versioned public
  CYP datasets while preserving the 2026-08-17 authoritative
  challenge-contract freeze.
- Evidence: A complete pause protected against guessed challenge contracts but
  was too conservative after the synthetic vertical slice was proven. Public
  Octant and TDC data can expose real ingestion, assay-context, leakage,
  validation, modeling, reporting, and usability failures before launch without
  defining the official competition adapter or metric.
- Authorized work: immutable public-source manifests; license, provenance,
  chemistry, duplicate, and overlap audits; two concrete benchmark adapters;
  frozen TDC and grouped Octant validation; a four-family classical model
  ladder; complete out-of-fold predictions; simple stacking; at most two
  external references; one controlled series-residual test when topology
  supports it; static reporting, documentation, and evidence-driven UX work.
- Prohibited work: guessed official schemas, metrics, submissions, series
  definitions, or transductive permissions; custom GNNs; broad deep-learning or
  hyperparameter frameworks; production competence gating; LLM adjudication;
  services, databases, dashboards, generalized benchmark plugins, and broad
  external web-predictor integrations.
- Comparison boundary: Public benchmark evidence is scientifically useful only
  for the named, hashed data, label, split, preprocessing policy, metric, and
  evaluation population. It is not a proxy for blind challenge performance,
  expected challenge rank, or assay-independent CYP inhibition.
- Operating constraint: The current orchestrator continues through Phase 0.5,
  with fresh independent review after source/split freeze, the first complete
  scorecard, and the release candidate. Prefer three or four focused PRs and no
  more than three active experimental branches.
- Alternatives: Remain fully paused until launch; begin speculative Phase 1;
  build a generalized benchmarking platform.
- Reversal conditions: The authoritative challenge release supersedes a public
  assumption; a license or provenance restriction prevents reproducible use;
  the public topology cannot support the planned analysis; benchmark work
  begins expanding into prohibited architecture; or a component fails its
  predefined ablation or clean-reproduction check.

## D-012 — Frozen Phase 0.5 public-source contracts

- Date: 2026-08-09
- Status: accepted
- Decision: Bind Phase 0.5 public inputs and external anchors to the exact
  revisions, URLs, file sizes, SHA-256 digests, schemas, row counts, licenses,
  and capture times in `benchmarks/public_sources.json`. Keep raw and generated
  data out of Git. Treat the Octant dataset as CC-BY-4.0 and retain attribution
  because its card metadata and body conflict.
- Evidence: Mutable dataset, package, model, and leaderboard references cannot
  support reproducible or apples-to-apples claims. The frozen Octant table also
  exposes documented discrepancies: 1,340 rather than the blog's 1,343
  inhibition compounds, 2,446 rather than the card's 2,442 reactivity rows,
  and 256 compound rows without numeric pIC50 values.
- Provenance discrepancies: The exact Harvard Dataverse release 105.0 declares
  CC0-1.0 while the TDC task pages declare CC-BY-4.0; retain attribution and
  apply the conservative CC-BY-4.0 policy. Treat the hashed PyPI sdist as the
  authoritative PyTDC 1.1.15 package source. The inspected Git revision
  declares 1.1.14 and is evidence only for the evaluator implementation, not a
  claimed mapping to the 1.1.15 release.
- Assay boundary: Represent Octant inhibition as 30-minute active-CYP3A4
  preincubation with DBOMF fluorescence readout. The pinned protocol supplies
  100 uM NADP+ with a G6P/G6PD regeneration system, creating NADPH-generating
  metabolic conditions without directly adding exogenous NADPH. The assay may
  combine reversible and metabolism-dependent effects and is not the challenge
  minus-NADPH direct-inhibition endpoint.
- Alternatives: Follow mutable latest releases; infer a direct-inhibition
  label; track redistributed raw files; omit public-page capture hashes.
- Reversal condition: An upstream correction, licensing clarification, or
  authoritative challenge contract requires a new explicitly versioned source
  manifest. Existing manifests and results remain immutable evidence.

## D-013 — Frozen public validation and leakage companion

- Date: 2026-08-09
- Status: accepted
- Decision: Freeze Octant as five deterministic, row-balanced Bemis-Murcko
  scaffold folds without label-informed assignment. Reserve fold 0 as outer
  validation and use folds 1-4 as training and four inner selection folds.
  Within each TDC task, assign `train_val` scaffold groups without labels to
  four row-balanced inner folds. Preserve TDC's official train/test populations
  exactly and report a separate strict companion that excludes test rows whose
  standardized structure occurs in `train_val`.
- Evidence: Octant yields 937 scaffold groups and exactly 268 rows per fold.
  TDC raw SMILES have no cross-partition overlap, while the frozen Phase 0
  standardizer reveals 7 affected test rows: 4 for CYP2C9, 2 for CYP2D6, and 1
  for CYP3A4. None has a conflicting binary label. Excluding them from the
  official score would break comparability, while ignoring them would hide
  optimistic leakage.
- Metric boundary: TDC `pr-auc` calls sklearn average precision. Implement and
  test the equivalent statistic locally with direction `higher_is_better`.
  Dated page footer text claiming lower is better is treated as an upstream
  documentation error, not a metric definition.
- Selection boundary: Candidate selection uses only grouped inner folds.
  Octant outer validation and all TDC public-test labels remain outside model
  fitting and selection. The freeze records zero public-test evaluations.
- Alternatives: Random molecule splits; label-stratified group assignment;
  silently remove standardized overlaps from official TDC results; treat raw
  SMILES inequality as sufficient leakage control.
- Reversal condition: A verified upstream split correction, a changed
  standardization policy, or the authoritative challenge contract requires a
  new versioned split. Existing official and strict results remain reported.

## D-014 — Independent source/split review remediation

- Date: 2026-08-09
- Status: accepted
- Decision: Reject the provisional Octant adapter v1 assay label and incomplete
  public-validation v1 freeze. Replace them with public-source schema v2,
  Octant adapter v2, TDC split-audit v2, a root validation receipt, and frozen
  TDC grouped inner folds before any model fit.
- Evidence: Independent review found that the pinned Octant protocol explicitly
  reports NADP+ plus G6P/G6PD regeneration although v1 said the condition was
  unreported. It also demonstrated that coordinated TDC task, partition, and
  source-row tampering passed the v1 split audit, found no frozen TDC inner
  selection folds, and found an aggregate ledger hash without a retained
  recipe. It also found incomplete license/version provenance and no documented
  end-to-end reconstruction from an empty root.
- Remediation: Pin the exact 5,251-byte inhibition protocol with Git blob SHA-1
  `53f55aa8333bd6d64671b71589e874d3a0a29f53` and SHA-256
  `5077b362330a505a7ecb703a1fac8858e0487af712d0ad51438570edbef77265`;
  represent NADPH-generating conditions precisely; bind official split bytes to
  the TDC adapter manifest; validate every row against canonical provenance and
  isoform; freeze all 30,038 TDC `train_val` rows in grouped inner folds; and
  retain deterministic validation and empty-root reproduction receipts. Record
  the Dataverse/TDC license conflict and the PyPI/Git version mismatch without
  weakening the conservative attribution policy.
- Reversal condition: New pinned primary evidence contradicts the assay
  protocol, or an upstream split correction requires another explicit schema
  version. Never reinterpret an existing artifact version in place.

## D-015 — Minimum native inner-selection ladder

- Date: 2026-08-09
- Status: accepted
- Decision: Run exactly four native families on the frozen grouped inner folds:
  training prevalence or median; chiral 2,048-bit ECFP4 logistic regression or
  ridge; Tanimoto similarity-weighted kNN; and ExtraTrees on the same fixed
  ECFP. Keep NumPy, SciPy, and scikit-learn 1.9 in a benchmark-only dependency
  group so the core wheel and four-command CLI remain unchanged.
- Configuration boundary: Linear regularization is `0.1`, `1`, or `10`; kNN
  uses `k` in `5`, `15`, `50` and similarity power `1` or `2`; ExtraTrees uses
  128 trees, `sqrt` feature sampling, leaf size `1`, `3`, or `10`, one job, and
  balanced class weights for classification. Select each family/task by pooled
  grouped-OOF AUPRC or MAE with a lexical tie break. Rerun only the retained
  stochastic configuration at seeds 20260809, 20260810, and 20260811 and use
  their mean OOF prediction.
- Leakage boundary: Verify the full public-validation receipt chain before
  fitting. Parse only frozen inner-selection rows. Do not parse or evaluate
  Octant outer labels or TDC public-test labels. Freeze retained configuration,
  prediction, input, and output hashes before any held-out evaluation.
- Rationale: This is the directive's smallest complete ladder and keeps every
  family at six or fewer candidate configurations. ECFP linear establishes a
  strong conventional baseline, kNN measures local analog support directly,
  and ExtraTrees supplies one nonlinear fixed-feature residual without adding
  a boosting library or descriptor subsystem.
- Reversal condition: Before results exist, reverse only for a demonstrated
  implementation, convergence, receipt-integrity, or bounded-resource defect.
  After results exist, do not opportunistically expand or retune the grid;
  diagnose predefined split, label, polarity, preprocessing, prevalence,
  leakage, metric, and feature checks first.

## D-016 — Separate held-out prediction from one-time scoring

- Date: 2026-08-09
- Status: accepted
- Decision: Freeze held-out predictions in a label-blind stage before any
  score exists. Verify the complete validation, canonical-data, official-split,
  and native-selection receipt chain; retrain the frozen configurations on all
  authorized training rows; and emit predictions without opening a held-out
  measurement value. Permit a separate receipt-bound scorer exactly once after
  prediction artifacts reproduce byte-for-byte.
- Evaluation count: One scoring pass comprises 4 Octant family evaluations and
  12 TDC family/task public-test evaluations. The strict TDC companion reuses
  the same predictions and is an analysis of a second declared population, not
  another model-selection opportunity. Record all counts explicitly.
- Metric boundary: TDC primary metric is average precision, with AUROC, Brier,
  ten-bin equal-width calibration error, and sensitivity/specificity,
  balanced accuracy, and MCC at an OOF-selected MCC-maximizing threshold;
  threshold ties favor the smaller value. Octant primary metrics are MAE,
  median absolute error, Spearman correlation, and RMSE, accompanied by
  interval-aware absolute error and pIC50-at-least-6 potent-subset MAE.
- Comparison boundary: Only official TDC AUPRC is compared with dated TDC
  anchors. Strict-population and Octant results remain separately labeled.
  Scoring must not alter a configuration, feature, seed, calibration,
  threshold, or stack.
- Reversal condition: A receipt mismatch, incomplete prediction population, or
  scorer defect blocks scoring. Once any held-out label is parsed, record the
  attempt and never silently restart or change the frozen candidates.

## D-017 — Version the first-scorecard audit remediation

- Date: 2026-08-09
- Status: accepted
- Decision: Preserve prediction/scoring v1 as historical evidence, but reject
  its claim to a structurally label-blind model interface and its incomplete
  scorecard contract. Materialize a receipt-bound training-measurement view at
  the source/split boundary, remove canonical measurement paths from held-out
  prediction v2, and require byte-identical prediction CSVs. Complete rather
  than rerun the observed v1 point scorecard.
- Evidence boundary: The completed scorecard must preserve every v1 point field, bind the
  corrected prediction receipt, and add revisions, split/population hashes,
  reference standard deviations and deltas, runtime/hardware, comparison
  status, and aggregation warnings. Allowed-seed ranges may score only the
  three already declared ExtraTrees seeds; record all 21 additional
  label-dependent analyses and select no seed, model, or configuration.
- Audit boundary: Retain a retrospective attempt-1 receipt but explicitly state
  that the exact raw traceback was not preserved. Complete OOF observation
  metadata in a versioned sidecar instead of mutating frozen selection v1.
  Independent re-review is required before merge or any stack/external work.
- Reversal condition: Revert if corrected predictions differ from v1, any point
  score changes, or independent review finds the new receipt chain incomplete.

## D-018 — Make contamination warnings task-specific

- Date: 2026-08-09
- Status: accepted
- Decision: Reject scorecard v2 because every TDC row used the seven-row
  cross-task overlap total. Report four CYP2C9, two CYP2D6, and one CYP3A4
  standardized overlap row, plus the explicit seven-row total, without changing
  populations or metrics. Preserve the immediately rejected v3 grammar
  candidate and retain scorecard v4 as the first accurate candidate.
- Evidence boundary: All 28 original point fields must remain exact; the only
  semantic change is the row-level warning. Two v4 roots must reproduce
  byte-for-byte before narrow independent re-review.
- Reversal condition: A new versioned strict-exclusion receipt changes the
  task-specific counts.

## D-019 — Freeze OOF-only combinations and random-optimism analysis

- Date: 2026-08-09
- Status: accepted
- Inputs: Use only the four retained-family OOF predictions and grouped inner
  folds bound by native-selection aggregate
  `33ba1f6481048c9f620223f9a0e6c85d2a40bece620ffe9b0c44117c0c7775fa`.
  The selection stage must not open Octant outer or TDC public-test labels.
- Candidates: Compare exactly (1) the best retained single family by grouped
  OOF primary metric with lexical family tie break, (2) the row-wise unweighted
  mean of all four families, (3) the row-wise median, and (4) a nonnegative
  linear stack in fixed family order `prior`, `ecfp_linear`, `similarity_knn`,
  `extra_trees`. Add no calibration, intercept, feature, candidate, or task-
  specific exception after results exist.
- Stack fitting: For each grouped outer meta-fold, create stack-training
  features by refitting the already retained base configurations in nested
  grouped folds that exclude both the meta-test fold and each meta-training
  fold. Fit `scipy.optimize.nnls` to those nested OOF features and targets; if
  all weights are zero, use equal weights. Apply the weights to base OOF
  predictions from models trained without the meta-test fold. Clip only binary
  predictions to `[0, 1]`. For later held-out prediction, fit final NNLS weights
  on the complete frozen base OOF table and freeze them before reading another
  held-out result.
- Retention rule: Score complete candidate OOF predictions by AUPRC for TDC and
  MAE for Octant. Among the three nonlearned candidates, choose the exact best
  with lexical candidate tie break. Retain the learned stack only if it exceeds
  that nonlearned winner by at least `0.005` AUPRC or reduces MAE by at least
  `0.01`; otherwise reject it and retain the nonlearned winner. These are
  complexity gates, not uncertainty or superiority thresholds.
- Held-out boundary: After selection, emit exactly one label-absent retained
  combination prediction per task from the frozen base predictions and final
  weights. A later scorer may add at most three TDC official evaluations, three
  strict companion analyses, and one Octant outer evaluation. Score no rejected
  combination on held-out labels and do not alter base predictions.
- Random-optimism analysis: Quantify, but never select from, one deterministic
  random-fold companion. Keep every exact standardized-structure group intact;
  order groups by SHA-256 of `20260809|benchmark|task|structure_hash`, then
  assign each group to the currently smallest of four row-count folds with fold
  index as the tie break. Evaluate only the retained base configurations. Report
  optimism as `random AUPRC - grouped AUPRC` for TDC and
  `grouped MAE - random MAE` for Octant; positive means the random view looks
  better. Parse no held-out label and use no random result for retention.
- Required receipts: Store complete combination OOF predictions, nested stack
  weights, all candidate scores, retained combinations and final weights,
  random-fold assignments and OOF predictions, per-family optimism, package and
  source versions, configuration/data/split hashes, fit/evaluation counts, and
  a deterministic aggregate. Reproduce the full train/validation-only root
  byte-for-byte before held-out combination prediction.
- Reversal condition: Before fitting, reverse only for a demonstrated
  mathematical, leakage, alignment, or bounded-resource defect. After fitting,
  do not change formulas, margins, candidates, folds, or weights in response to
  performance; record a failed experiment instead.

## D-020 — Enforce the combination firewall and complete fit accounting

- Date: 2026-08-09
- Status: accepted
- Decision: Reject combination v1 because its loader opened canonical held-out
  measurement rows before filtering. Require the model-facing combination stage
  to accept only the existing label-absent prediction-input view and bind that
  receipt. Reject v2 because its `384` fit count omitted NNLS solves. V3 must
  report 384 base-model fits, 16 nested NNLS fits, 4 final NNLS fits, and 404
  total fit operations.
- Invariance: The six numeric CSV files and the retained-combination payload
  must match v1 exactly. Only the schema, receipt binding, and fit accounting may
  change. No new candidate, formula, margin, result, or evaluation is allowed.
- Simplicity boundary: Keep the direct procedural implementation. Add no
  framework, dependency, public CLI command, or abstraction to remediate these
  two audit defects.
- Reversal condition: Revert if v3 cannot reproduce the scientific payload or
  if its model-facing interface can resolve a canonical measurement table.

## D-021 — Freeze one isolated CheMeleon transfer attempt

- Date: 2026-08-09
- Status: accepted
- Decision: Attempt only the OpenADMET four-task CheMeleon checkpoint at model
  revision `ef24cf94`, using the resolved upstream CPU container digest
  `sha256:e2b18fff`. Materialize a five-column label-free projection for the
  exact 7,724 identities, use the frozen standardized structure, run two
  complete predictions, and require byte-identical canonical output before one
  scoring pass.
- Firewall boundary: The broader native prediction-input molecule tables are
  not label-absent because provenance embeds original outcomes. Only the
  preparation projector may open them. The model container may read only the
  exact-hash, read-only projection of benchmark, task, molecule ID,
  standardized structure, and structure hash. It must not receive a broader
  prediction, canonical, split, measurement, provenance, or label root.
- Environment boundary: The digest is a 7.72 GB compressed linux/amd64 image
  that embeds framework revision `6077d125`; it is not the v0.2.0 source
  revision previously inspected. Run it under explicit arm64-host emulation
  with a 120-minute and 25-GiB limit. Add no core dependency, environment
  manager, public CLI command, custom loader, framework, or upstream patch.
- Overlap boundary: Standardize all 8,068 published training structures with
  the frozen Phase 0 policy. Preserve official TDC and full Octant populations
  with contamination counts. Also report a TDC companion excluding the union
  of existing strict exclusions and exact CheMeleon-training overlaps, and an
  Octant exact-overlap-excluded companion. Call them exact-structure-disjoint,
  not clean zero-shot.
- Metric boundary: Map the three continuous CYP outputs to fixed TDC average-
  precision rankings with higher pIC50 as higher inhibitor score; use CYP3A4
  pIC50 directly for Octant MAE. Do not flip polarity, fit a threshold, select
  a population, calibrate, fine-tune, or combine after results exist. Count
  three TDC official, three TDC union-disjoint, one Octant full, and one Octant
  exact-disjoint analysis.
- Retention rule: Retain a completed run as external transfer evidence whether
  it wins or loses. Never add CheMeleon to the native Phase 0.5 ensemble. Reject
  and record a precise blocker if provenance, alignment, finiteness,
  repeatability, runtime, storage, or scoring preconditions fail. Make no
  second checkpoint or environment attempt in Phase 0.5.
- Contract: `benchmarks/chemeleon_inference_contract.json` is authoritative.
- Compatibility remediation: Contract v1 is rejected for inference because its
  mapping keys prefixed benchmark names that are not present in the exact
  five-column task field. V2 keys all four mappings by their literal input task
  values and requires this equality before output creation, model download, or
  container access. The five-column scientific payload is unchanged.
- Attempt-control remediation: Contract v2 is also rejected for inference. Its
  runner did not bind all overlap provenance and allowed caller-selected output
  paths and source revisions. V3 fixes one input, output, adjacent exclusive
  start sentinel, and clean Git revision. It validates the overlap contract,
  input, population key, training file, source, package, and standardizer before
  canonical prediction. The five-column scientific payload remains unchanged.
- Outcome: The one contract-v3 attempt consumed the fixed input and exact
  image. Model download, hashing, overlap audit, and image pull passed. The
  four-row smoke failed before prediction because the upstream image's `boto3`
  import requests `DocumentModifiedShape` from an incompatible installed
  `botocore`. Retain the failure and overlap evidence. Do not patch, retry,
  change the image or checkpoint, or score CheMeleon in Phase 0.5.
- Reversal condition: Reverse before inference only if a pinned primary source
  contradicts the contract or the authoritative challenge release supersedes
  Phase 0.5. After inference begins, preserve the attempt and its outcome.

## D-022 — Freeze one fit-free local residual test

- Date: 2026-08-10
- Status: accepted
- Decision: Test exactly one grouped-OOF local correction. Use the retained
  unweighted mean as the base and the retained `tanimoto-k50-p2` prediction as
  the local estimate. Apply the difference only when nearest-neighbor Tanimoto
  is at least 0.50, with linear weight `(similarity - 0.50) / 0.50` clipped to
  `[0, 1]`. Unsupported predictions remain exactly equal to the base.
- Topology evidence: The predeclared supported subsets contain 377 Octant rows
  and 4,208/4,678/4,086 TDC CYP2C9/2D6/3A4 rows, with at least 81 supported
  rows in every grouped fold. No candidate outcome was computed first.
- Controls: Compare the base, retained kNN, valid correction, one within-fold
  residual shuffle, and one within-fold randomized support/family-label
  assignment. Use seed 20260809. Fit no model and tune no parameter.
- Retention: Require positive full-task gain on all four tasks; positive and
  bootstrap-supported analog-subset gain on all four; gain in at least three
  of four folds per task; exact remote abstention; and superiority to both
  negative controls. If any condition fails, record rejection and remove the
  implementation.
- Boundary: Use grouped OOF artifacts only. Parse no held-out label, consume no
  held-out prediction, run no held-out evaluation, and test no second residual.
- Contract: `benchmarks/series_residual_contract.json` is authoritative.
- Contract remediation: V1 froze the scientific formula but not every
  result-affecting implementation detail. V2 requires exact 1:1 OOF joins,
  hash-derived within-fold controls, clipping for both classification controls,
  scaffold-group paired bootstrap with an explicit percentile method, exact
  directional gains, all-row fold consistency, and strict tie failure. No
  candidate outcome was computed under v1.
- Review and implementation gate: Independent review passed contract v2 at
  exact signed head `b16967e`, including the target-blind topology disclosure,
  chronology, and Occam check. Implement it as one direct module and one
  research script with synthetic receipt, alignment, topology, repeatability,
  and abstention tests. Do not run either real OOF root until the exact
  implementation passes a second independent review.
- Outcome: Independent implementation review passed exact signed head
  `129af20`. Two real grouped-OOF roots are byte-identical with aggregate
  `a6248c4e`. Full and supported gains are negative on all four tasks, every
  task has zero of four positive folds, and both control requirements fail.
  Remote abstention is exact. Independent audit reproduced all 30,910 rows,
  300 point evaluations, 80,000 bootstrap evaluations, 32 intervals, and the
  reject decision. Preserve the compact evidence and remove the implementation.
  Do not adjust, replace, retry, or evaluate this residual on held-out data.
- Reversal condition: Reverse only before candidate scoring if an independent
  review finds a contract, alignment, leakage, or control defect. Do not alter
  the formula or rule after any candidate result is visible.

## D-023 — Stop modeling and freeze the Phase 0.5 report

- Date: 2026-08-10
- Status: accepted
- Decision: Stop Phase 0.5 model work after the retained native mean, rejected
  stack, precise CheMeleon blocker, and rejected series residual. Synthesize the
  final evidence in one tracked, GitHub-renderable Markdown report with tables
  only. Add no figure, renderer, dependency, public CLI command, fit, score, or
  held-out access.
- Evidence binding: A compact JSON receipt preserves every aggregate report
  input and binds the report to the exact public source and validation records,
  retained-mean and family scorecard manifests, CheMeleon failure receipt, and
  series rejection receipt. Track no raw row, structure, label, or prediction.
- Reproduction boundary: Preserve the audited one-command empty-root source and
  split reconstruction. Reproduce the final report from tracked evidence; do
  not repeat consumed public-test evaluations merely to rebuild presentation.
- Review gate: A fresh independent closeout reviewer must verify every number,
  warning, link, evidence hash, claim boundary, rendering, minimal codebase,
  signature, and hosted CI before Phase 0.5 closes.
- Reversal condition: Correct a factual, provenance, or rendering defect before
  closeout. Do not reopen modeling or change a result in response to report
  presentation.

## D-024 — Close Phase 0.5 and restore the launch freeze

- Date: 2026-08-10
- Status: accepted
- Decision: Close Phase 0.5 after independent review passed exact signed commit
  `9150e93fc8a48f8791feddb2952d9305332f9ae1` and all 15 exit criteria. Freeze
  its source, split, scorecard, report, negative-result, and experiment records.
  Preserve Phase 0 `v0.1.0` as the installable product baseline and the fixed
  Phase 0.5 mean as a public-data research candidate, not a launch incumbent.
- Evidence: A no-local-artifact clone verified receipt v2 and every report table
  without repeating held-out scoring. All 90 tests, static checks, locked
  builds, GitHub rendering, signatures, sole authorship, hosted CI, and Occam
  review pass. PR 38 merged by exact signed fast-forward.
- Launch boundary: Before any Phase 1 fit or candidate score, capture the
  authoritative 2026-08-17 release and freeze its original bytes, provenance,
  license, rules, schema, assay semantics, metric, submission contract, and
  label-independent challenge-faithful validation groups. Phase 0.5 mappings
  and models have no automatic authority over the released challenge.
- Superiority boundary: Reproduce the strongest relevant public comparator on
  identical rows. Require paired family-safe uncertainty and a positive lower
  confidence bound before claiming a statistically significant gain.
- Reversal condition: Reopen Phase 0.5 only for a demonstrated factual or
  provenance defect. The authoritative release may supersede any provisional
  assumption, but it does not erase the Phase 0.5 record.

## D-025 — Authorize bounded Phase 0.75 public comparator research

- Date: 2026-08-10
- Status: accepted
- Decision: Preserve Phase 0.5 as immutable evidence and begin a separate
  Phase 0.75 that reproduces the strongest eligible public CYP comparator,
  freezes a new leakage-safe TDC shadow benchmark, and tests whether richer
  molecular representations add value before the 2026-08-17 challenge launch.
- Rationale: Phase 0.5 deliberately tested estimator diversity over one
  binary, chiral, radius-2 Morgan representation. Its fixed mean improved the
  correlated native estimators, while its NNLS stack and same-representation
  kNN residual failed. It did not reproduce the public MapLight method or test
  its count fingerprints, Avalon, ErG, ordered descriptor, or pretrained GIN
  information. The observed native ceiling is therefore a representation-
  limited Phase 0.5 result, not evidence that public CYP modeling is exhausted.
- D-024 boundary: D-024 is not reversed. Its Phase 0.5 artifacts, scores,
  evaluations, negative results, and launch-day authority remain unchanged.
  Phase 0.75 uses only named public benchmarks and grants no authority to guess
  a challenge field, assay mapping, metric, split, rule, or model. No Phase
  0.75 component transfers automatically after launch.
- Required scope: Complete Tier 1 by August 17: freeze MapLight, freeze one
  global TDC `train_val` shadow benchmark, reproduce fixed MapLight, attempt
  one isolated MapLight + GIN reproduction, run shadow-only representation
  ablations, publish an honest scorecard, correct public documentation, and
  create the launch handoff. A precise reproduction blocker is acceptable.
- Conditional scope: Only after Tier 1 is early and clean, audit PubChem AID
  1851, assess cross-isoform panel feasibility, and audit parent/analog
  topology. Do not train from AID labels before primary field semantics and a
  strict union test-structure firewall pass independent review. Full panel,
  parent-relative, Chemprop, additional encoder, and LLM work is deferred
  unless separately authorized.
- Public-test budget: Authorize exactly three new prediction families per TDC
  task: fixed MapLight, MapLight + GIN, and at most one final locked
  `cypshift` contender. A family is one frozen row-level prediction artifact
  from one frozen source, environment, and configuration state. All declared
  seeds belong to the family. Predictions are generated and hashed without
  labels, then independently reviewed before scoring. A no-prediction,
  no-label infrastructure failure consumes no family but is recorded. Any
  prediction generated after label access consumes the family. No score-driven
  repair, feature ablation, or hyperparameter selection is permitted.
- Shadow boundary: All new choices use TDC `train_val` only. One global,
  label-independent table binds standardized structures, Bemis-Murcko
  scaffolds, and one frozen chemistry community across all three CYP tasks.
  Task-specific regrouping is forbidden. Freeze one scaffold-held-out and one
  chemistry-community-held-out protocol with three deterministic outer repeats
  where populations permit, plus grouped inner selection.
- Comparator boundary: Pin the MapLight repository, files, paper, MIT license,
  feature semantics, dependency behavior, CatBoost seeds and configuration,
  and dated anchors. Verify fixture arrays before scoring. A mismatch beyond
  0.010 AUPRC triggers a version and implementation audit, not tuning. If exact
  GIN reproduction is blocked or drifts, retain the precise blocker or frozen
  local implementation as the comparator with clear language.
- Pretraining boundary: Pin GIN identifiers, weights, environment, dimensions,
  device behavior, and failed-row policy. Classify training overlap as known
  clean, known overlap, or unknown. Unknown provenance permits a pretrained-
  transfer benchmark, not a clean zero-shot claim.
- Dependency boundary: CatBoost, PyTorch, DGL, MolFeat, and model weights stay
  in separately locked research environments or digest-pinned containers.
  They do not enter the core install or current all-groups CI environment. The
  public CLI remains exactly `audit`, `train`, `predict`, and `report`.
- Review gates: Require independent approval before fixed-MapLight scoring,
  GIN scoring, any AID label enters training, and final-contender scoring. Each
  gate verifies the exact signed source, environment, configuration, row
  alignment, firewall, prediction hash, evaluation budget, and claim boundary
  relevant to that stage.
- Success criterion: Compare a final contender with the locally reproduced
  MapLight + GIN predictions on identical rows. Require positive paired 95%
  lower confidence bounds on at least two of CYP2C9, CYP2D6, and CYP3A4, no
  loss greater than 0.005 AUPRC on the remaining task, and a positive paired
  macro-average lower bound. Report all tasks. Any AUPRC at or above 0.95
  triggers an independent leakage and contamination audit before use as
  evidence.
- Alternatives: Remain fully paused; reopen Phase 0.5; begin speculative
  challenge development; run a broad encoder or architecture search.
- Reversal conditions: Stop or narrow Phase 0.75 if Tier 1 cannot close by
  launch, public-test iteration begins, exact-row comparison fails, source or
  pretrained provenance is inadequate, the global cross-task firewall cannot
  be demonstrated, dependencies burden the core, or the work expands beyond
  one comparator and one representation question. The authoritative release
  ends Phase 0.75 and restores launch-day intake priority.

## D-026 — Authorize one exact-upstream signed-int8 compatibility experiment

- Date: 2026-08-10
- Status: accepted; execution closed on 2026-08-11
- Decision: Preserve the failed safe Stage A feature experiment and run one
  separate, pre-result compatibility experiment that reproduces MapLight's
  pinned zero-length `numpy.int8` count conversion exactly. The project owner
  granted explicit authority after the safe experiment stopped on an Avalon
  sparse count of 144.
- Sole scientific change: Remove only the safe experiment's upper count bound
  for Morgan and Avalon. Keep nonnegative integer sparse-count validation, then
  accept the exact signed-`int8` bytes emitted by pinned RDKit and NumPy. Do not
  widen, clip, binarize, post-correct, or reinterpret them.
- Preserved boundaries: Keep exact raw rows, row order, all five fixed blocks,
  descriptor order, environment, folds, seeds, resource caps, label firewall,
  public-test budget, and failure evidence unchanged. Generate two independent
  label-free roots and require byte-identical rows and arrays before fitting.
- Claim boundary: This is upstream implementation compatibility, not a safe
  count representation and not evidence that wrapped negative values are
  chemically preferable. Preserve and report the discrepancy.
- Review gate: Independently review the signed contract and implementation
  before the overflow witness or any real compatibility row is generated.
  Independently review both feature roots before any model fit.
- Reversal condition: Reject the compatibility experiment if another
  scientific rule must change, its exact bytes are not reproducible, or any
  label, prediction, metric, GIN, challenge, or public-test path is required.
  Never alter or delete the original safe blocker.
- Outcome: Fresh fixture parity passed across one pinned upstream and two local
  processes, including 127 to 127, 128 to -128, and 144 to -112. Real build 1
  then computed all five blocks in memory but failed the inherited finiteness
  rule because the RDKit descriptor matrix contained at least one non-finite
  value; the first affected exact-raw row was index 1,563. It persisted no array.
  This is the reversal condition: another scientific rule would have to change.
  Preserve blocker receipt SHA-256 `b337f965...`; do not retry, start build 2,
  fit Stage A, start GIN, or use the public test.

## D-027 — Authorize one exact-upstream missing-value compatibility experiment

- Date: 2026-08-11
- Status: accepted; execution passed on 2026-08-11
- Decision: Preserve both prior Phase 0.75 blockers and authorize one separate
  missing-value compatibility experiment. Permit float64 `NaN` only in the
  four frozen Gasteiger charge-extrema descriptor columns and preserve those
  values unchanged for pinned CatBoost 1.2.1. Continue to reject every
  infinity and every other `NaN`.
- Evidence: A project-owner-authorized, label-free diagnosis examined all
  15,399 unique exact-raw shadow structures. Forty-one structures, expanding
  to 82 rows, have 164 unique and 328 expanded `NaN` cells, all confined to
  descriptor indices 39, 41, 43, and 45. The affected elements are As, Hg, Sb,
  Se, and Sn. The first organoarsenic molecule parses normally; phosphorus
  controls are finite. Pinned CatBoost accepts synthetic `NaN`, produces finite
  probabilities, and resolves `nan_mode=Min`; frozen ExtraTrees rejects it.
- Sole scientific change: Replace only D-026's inherited reject-all-nonfinite
  rule with the exact four-column `NaN` allowance. Do not impute, replace, add
  missingness indicators, delete rows or descriptors, edit structures, add
  element parameters, or permit another non-finite value.
- Execution boundary: Retain exact signed-`int8` bytes, raw rows, ordering,
  blocks, descriptor list, environment, folds, seeds, resource limits, label
  firewall, and public-test budget. Generate two fresh label-free feature roots
  and require byte-identical row and NPY payloads, including NaN bytes. Build 2
  requires reviewed build 1.
- Model boundary: After both feature roots pass review, only the already frozen
  CatBoost R1-through-R5 candidates may fit. Leave CatBoost `nan_mode`
  unspecified as upstream does, but receipt its resolved pinned value `Min`.
  ExtraTrees E1 remains unexecuted; no imputed control or replacement learner
  is authorized.
- Claim boundary: This is pinned local upstream-compatibility evidence, not
  proof of the historical runtime, a predictive gain, a public score, clean
  external validation, or challenge transfer.
- Reversal condition: Stop and preserve a blocker on any infinity, `NaN`
  outside the four exact columns, mask/count drift, byte mismatch, CatBoost
  capability mismatch, or need for another scientific change. Do not start GIN
  or use the public test before the fixed comparator completes its shadow gate.
- Outcome: Both full feature roots are byte-identical. The fixed MapLight R5
  seed-1 representation improves macro AUPRC over binary Morgan R1 seed 1 by
  0.0481 under scaffold holdout and 0.0443 under community holdout. Paired
  global-group 95% lower bounds are 0.0372 and 0.0354; every CYP task improves;
  unique-cell, conflict-excluded, low-neighbor, and influential-group gates all
  pass. Retain the fixed representation for the local comparator. This outcome
  authorizes only the separate GIN eligibility/reproduction gate, not public
  scoring or challenge transfer.

## D-028 — Retain one bounded local GIN engineering comparator

- Date: 2026-08-11
- Status: accepted; feature gate passed
- Decision: Retain the single MapLight `gin_supervised_masking` representation
  for local, non-redistributed shadow benchmarking after exact weight, fixture,
  environment, row-alignment, and repeat gates pass. Do not add another encoder.
- Rights boundary: MapLight is MIT; MolFeat and DGL-LifeSci are Apache-2.0; the
  original pretraining code is MIT. The model metadata provides no separate
  artifact or pretraining-data license. Do not redistribute the weight. Publish
  only aggregate local benchmark evidence and preserve this uncertainty.
- Provenance boundary: Exact TDC structure and CYP-target overlap are unknown.
  Call the result pretrained-representation transfer, not clean zero-shot,
  uncontaminated external validation, or automatic challenge eligibility.
- Environment evidence: Preserve two pre-embedding blockers. MolFeat 0.9.2
  omits `python-dotenv` from its runtime dependencies and imports its optional
  Hugging Face module on the DGL path. The compatible environment pins only the
  required import dependencies, forces Hugging Face offline, and authorizes no
  Hugging Face model or representation.
- Feature outcome: One upstream and two local fixture processes match exactly.
  Two real roots are byte-identical over all 30,038 rows. Thirty-nine of 41
  standardized multi-raw groups produce different embeddings, proving that
  exact-raw rather than standardized-hash caching is required.
- Next boundary: Run only fixed MapLight, GIN alone, fixed plus GIN, fixed plus
  deterministically shuffled GIN, and fixed plus seeded 300-dimensional noise
  on the frozen shadow cells. Public scoring remains forbidden.
- Reversal condition: Preserve a blocker and reject GIN on any repeat,
  alignment, finiteness, control, significance, influence, or claim-boundary
  failure. The August 17 official rules may disallow pretrained weights even
  if the TDC engineering comparator succeeds.

## D-029 — Close Phase 0.75 after bounded public comparator reproduction

- Date: 2026-08-11
- Status: accepted; execution passed
- Decision: Close Phase 0.75 after the fixed MapLight and fixed-plus-GIN
  families reproduce all six dated public anchors within 0.003 AUPRC. Preserve
  the byte-identical prediction roots and scorecard; do not rescore, repair,
  regenerate, or use the reserved third family.
- Prediction boundary: Attempts 3 and 4 independently produced 13
  byte-identical non-manifest payloads from the same signed source. Both
  families retain five seeds and one separately labeled arithmetic
  mean-probability column. No Phase 0.75 public label was opened before
  independent review passed.
- Scoring boundary: The sole successful scorer interpreted 7,512 public labels
  and performed exactly 36 AUPRC calls. It performed zero diagnostic metrics,
  new fits, new predictions, third-family operations, or challenge assumptions.
  The first scoring attempt remains an immutable zero-row, zero-label,
  zero-metric file-mode blocker.
- Outcome: Fixed MapLight reaches 0.786, 0.720, and 0.881; fixed plus GIN
  reaches 0.858, 0.791, and 0.916 on CYP2C9, CYP2D6, and CYP3A4. The maximum
  probability-mean AUPRC is 0.9165, below the 0.95 forensic trigger.
- Claim boundary: This is a successful reproduction on an already-observed TDC
  test. It is not blind external validation, paired public-test superiority,
  clean zero-shot evidence, challenge evidence, or authority for score-driven
  repair. Historical PyTDC remains unpinned; the local aggregation is the
  frozen PyTDC 1.1.15-compatible reconstruction.
- Next boundary: Wait under D-024. On August 17, freeze the authoritative
  OpenADMET bytes, rules, endpoints, MA-ST-RAE, MCC, label derivation, censoring,
  permissions, validator, and challenge-faithful family split before any fit or
  score. No TDC representation, model, threshold, or result transfers
  automatically.

## D-030 — Separate the public product narrative from historical execution

- Date: 2026-08-11
- Status: accepted
- Decision: Make the root README a pragmatic description of the tool, current
  capabilities, evidence, limitations, and series-first direction. Keep current
  usage, science, validation, and state documents short and purpose-specific.
  Move completed phase plans and superseded intake notes into a clearly labeled
  archive without deleting their evidence or chronology.
- Evidence: The prior README read as a phase handoff, all completed plans
  appeared active, and `PROJECT_STATE.md` exceeded 1,000 lines despite being the
  designated concise source of truth. An external reader could not readily
  distinguish the installable product, validated comparator, untested thesis,
  and historical process.
- Boundary: Benchmark reports, contracts, receipts, the experiment ledger, and
  negative results remain intact. Archival changes navigation, not scientific
  interpretation. The README must state that the public CLI is a reference
  baseline and that parent-relative prediction is not yet validated.
- Reversal condition: Restore or split a document only if an external reader
  cannot recover the current guidance or the archived evidence through stable
  links.

## D-031 — Freeze the OpenADMET launch intake as TRACE R0

- Date: 2026-08-17
- Status: accepted; records-only gate
- Decision: Freeze the 2026-08-17 OpenADMET CYP release intake at
  `R0_CONTRACT_FROZEN` using the exact dataset, tutorial, and Space revisions,
  selected-file receipts, launch sources, public submission names/types, and
  endpoint-state notes in `benchmarks/openadmet_cyp_2026/`. Treat direct
  TRACE as the primary future family-held-out protocol and global TDI as the
  permanent TDI fallback; defer optional TDI-TRACE until both are frozen.
- Evidence: Dataset revision
  `85f8b358d0a2056a98b990dd75d3b3ec9247862b`, tutorial revision
  `9d4925eb4a0fb914256da1b27d110593bcbe3cf0`, and Space revision
  `13c5057b37d1e72b3f036dd0d59718b1823f8fdd` were verified in the local
  read-only clones. Dataset and tutorial declare Apache-2.0. The Space has no
  declared license and is not assigned one. The launch sources confirm the
  two tracks, 750-compound test set, live-half/full-final populations,
  external/pretrained allowance, and public submission fields.
- Unresolved boundary: Exact live MA-ST-RAE implementation, denominator,
  scored masks, interval-field meaning, TDI derivation and column order,
  validator/backend parity, family assignment, and transductive test-test
  permission remain visible as V6/P6 blockers. External/pretrained component
  rights and overlap remain artifact-specific. No metric-specific optimization
  is authorized.
- Next action: Implement only a thin receipt-bound drift checker; the canonical
  adapter follows after review. Do not fit, score, submit, or add a dependency.
- Reversal condition: A newer authoritative source revision, license
  correction, schema/validator disagreement, or executable metric source
  supersedes a recorded provisional field. Create a new versioned receipt;
  never reinterpret these frozen bytes in place.

## D-032 — Use conservative connected components for candidate topology

- Date: 2026-08-18
- Status: accepted; label-free R1 audit passed
- Decision: For the OpenADMET candidate topology audit, use exact binary
  Morgan/ECFP4 radius-2 fingerprints with chirality, 4,096 bits, and inclusive
  Tanimoto `>= 0.60`; union every qualifying pair into connected components.
  Keep Bemis-Murcko scaffold groups as a separate diagnostic. Neither grouping
  is a family definition, split, episode, label, or model authority.
- Evidence: Connected components are the simplest deterministic closure of the
  declared pairwise analog relation and preserve transitive chains without
  introducing Butina's order-sensitive cluster policy. The preliminary
  label-free probe produced 5,296 Butina groups with 198 cross edges, versus
  5,232 connected components and 1,241 multi-member molecules; Murcko produced
  5,378 groups with largest size 52. Official acceptance found zero quarantine,
  zero standardized train/test overlap, a largest component of 21, and 146
  components with at least two direct-training source identities. These are
  topology diagnostics only.
- Alternatives: Butina clustering, scaffold-only grouping, or a learned family
  model before label-aware validation.
- Reversal condition: Official-source acceptance or the later label-aware
  topology gate finds receipt, identity, chemistry, or leakage defects. Preserve
  the diagnostic and do not reinterpret it as validation evidence.

## D-033 — Freeze the R2 label-aware TRACE validation contract

- Date: 2026-08-18
- Status: superseded by D-034 before implementation
- Decision: Freeze the label-aware topology-viability, direct-observation
  eligibility, campaign-episode, public/truth firewall, grouped-fold, and
  scorecard contract in
  `benchmarks/openadmet_cyp_2026/validation_contract.json` as
  `R2_VALIDATION_CONTRACT_FROZEN`. Keep D-032 unchanged. Restrict direct
  compilation to `TRAIN_inhibition`; retain all four direct measurement states;
  require complete observations for anchors and local pairs; and preserve the
  global TDI fallback while TDI, models, metrics, submissions, and transductive
  relationships remain outside scope.
- Evidence: The preliminary label-aware diagnostic records exact local-pair,
  episode, and activity-cliff counts without fitting or scoring. CYP3A4 has 95
  eligible components and 473 eligible pairs provisionally; CYP1A2, CYP2C9,
  and CYP2D6 are underpowered at 18/28, 13/13, and 14/28. Selector episode
  diagnostics are 33/54, 37/42, and 117/205 for CYP1A2, CYP2C9, and CYP3A4;
  activity-cliff diagnostics are 6/6, 4/4, 4/4, and 96/38 pairs/components.
  Static tests asserted the declared JSON fields only; they did not behaviorally
  validate a compiler, fold assignment, or firewall implementation.
- Alternatives: Implement folds and episodes immediately; reuse TDI/Emax
  fields in direct validation; or reinterpret the label-aware diagnostics as
  prediction evidence.
- Reversal condition: A receipt, identity, chemistry, state-preservation,
  family-leakage, or contract-consistency defect is found. Create a new
  versioned contract; do not silently reinterpret R2.

## D-034 — Supersede the rejected R2 v1 contract with v2

- Date: 2026-08-18
- Status: accepted; corrected contract-only gate
- Decision: Supersede validation-contract v1 before implementation with
  `cypshift.openadmet_cyp_2026.validation_contract.v2` at
  `R2_VALIDATION_CONTRACT_V2_FROZEN`. Remove selector CYP from public episode
  artifacts; split oracle-runner and scorer-only projections; expose the
  designated anchor to the episode-specific global fit under cross-fitted
  configuration; classify all clean but insufficient support as
  `LOCAL_UNDERPOWERED`; and freeze exact random-anchor and component-fold hash
  policies. Preserve D-032's topology bytes, but grant its components limited
  authority as a conservative reconstructed-family proxy for R2 grouping,
  folds, and episodes only. Do not claim semantic lineage or mechanism.
- Evidence: Independent pre-implementation review found seven contract defects:
  selector leakage, low-support misclassification, contradictory topology
  authority, an unsafe truth interface, ambiguous anchor exposure,
  underspecified determinism, and behavioral evidence overclaim. No validation
  artifact, model, metric, prediction, or submission had been produced, so v1
  has no downstream scientific evidence to invalidate. Static v2 tests pin the
  corrected declarations and authority denials only.
- Alternatives: Quietly edit v1; call low support failure; publish selector CYP
  in public episodes; pass full truth rows to the oracle runner; or defer the
  named family protocols without a fixed proxy.
- Reversal condition: Implementation review finds a receipt, identity,
  chemistry, determinism, state, projection, or leakage defect. Create v3 and
  preserve the failure record; do not reinterpret v2.

## D-035 — Accept receipt-bound R2A observations and component folds

- Date: 2026-08-18
- Status: accepted; partial R2 implementation gate
- Decision: Accept the smallest R2 implementation slice: receipt-bound direct
  observations, deterministic shared component-fold records, and a
  scope-limiting manifest. Load every contracted input once, verify its hash
  before parsing, parse the same bytes, and bind executable behavior to the
  exact v2 declarations. Keep episodes, topology viability, validation and fold
  authority, models, metrics, TDI, predictions, submissions, and transduction
  explicitly denied.
- Evidence: Ten focused synthetic tests and the full 224-test suite pass. Two
  official runs outside Git were byte-identical and produced 19,620 observations
  from 4,905 direct rows plus 73,575 fold records. The official observations are
  6,525 complete and 13,095 missing, with no partial or orphan state. Independent
  scientific review passed after receipt-before-parse, same-byte parsing,
  policy-authority, and component-containment fixes.
- Alternatives: Combine observations, folds, episodes, masks, and viability in
  one oversized milestone; trust value-bearing R1 payloads; or balance folds
  using label availability.
- Reversal condition: An episode implementation or independent replay finds a
  receipt, identity, chemistry, state, determinism, group-containment, or
  authority defect. Preserve the artifacts, stop modeling, and issue a
  versioned repair rather than reinterpret this gate.

## D-036 — Reject v2 before R2B and freeze the corrected v3 contract

- Date: 2026-08-18
- Status: accepted; corrected contract-only gate
- Decision: Supersede v2 with
  `cypshift.openadmet_cyp_2026.validation_contract.v3` at
  `R2_VALIDATION_CONTRACT_V3_FROZEN`. Preserve all v2 chemistry, eligibility,
  pair, anchor, query, fold, scorecard, and no-model/no-TDI/no-test policies.
  Redefine the firewall as exact-column/value nondisclosure and privilege
  separation, acknowledge membership-based identity inference, freeze the
  deterministic episode-ID join pseudonym and compact JSON cell policy, and
  keep public episodes oracle-only. Permit fold, episode, episode-label, and
  topology-viability artifact authority only after successful R2B, while
  keeping validation, models, metrics, TDI, predictions, submissions, and
  transduction unauthorized.
- Evidence: Independent read-only audit found that `outer_group_id` plus
  `query_molecule_ids` uniquely inferred the omitted anchor in 124/187 primary
  and 126/187 stress-base episodes, contradicting v2's information-theoretic
  anonymity claim. Episode ID determinism was also unfrozen. The rejection
  occurred before R2B and zero R2B artifacts were created. Two receipt-bound
  R2A official replays under v3 were byte-identical and retained the accepted
  direct-observation and group-fold bytes exactly.
- Alternatives: Quietly edit v2; claim public identity anonymity despite the
  inference diagnostic; or begin episode implementation before freezing the
  join and mask policies.
- Reversal condition: v3 implementation finds a receipt, identity, chemistry,
  state, determinism, projection, family-leakage, or authority defect.
  Preserve the blocker and issue another versioned contract before modeling.

## D-037 — Reject v3 R2B boundary and freeze corrected v4

- Date: 2026-08-18
- Status: accepted; corrected contract-only gate
- Decision: Supersede v3 with
  `cypshift.openadmet_cyp_2026.validation_contract.v4` at
  `R2_VALIDATION_CONTRACT_V4_FROZEN`. Preserve v3 and R2A evidence, then
  freeze the selected/stress episode policy tokens, lowercase 64-character
  SHA256 IDs and uniqueness rule, exact public CSV semantic types, and the
  complete topology-viability schema with receipt-bound Morgan recomputation,
  endpoint/global/fold/cliff diagnostics, clean underpowered semantics, and
  post-R2B artifact authority. Keep validation, models, metrics, TDI,
  predictions, submissions, and transduction unauthorized.
- Evidence: Independent post-merge Sol audit identified three R2B blockers in
  v3: episode policy/hash output was incomplete, the public query field type
  was incomplete, and topology_viability schema/acceptance was incomplete.
  V3 was rejected before R2B and zero R2B artifacts were created. PR89's
  claimed independent audit was unsupported because its assigned read-only
  auditor self-integrated the change; record this as a governance breach,
  distinct from valid R2A observation/fold outputs and their independent
  scientific review. Two receipt-bound R2A official replays under v4 were
  byte-identical and preserved the accepted observation and fold hashes.
- Alternatives: Start R2B against v3; infer semantic types from CSV bytes;
  or emit a partial topology_viability artifact and upgrade it later.
- Reversal condition: Root's independent R2B review/replay finds a receipt,
  identity, chemistry, fold, schema, serialization, projection, determinism,
  family-leakage, or authority defect. Preserve the blocker and issue another
  versioned contract before modeling.

## D-038 — Accept R2B episodes, masks, and topology viability

- Date: 2026-08-18
- Status: accepted; artifact-only R2B gate
- Decision: Accept the receipt-bound R2B implementation and grant only the v4
  post-success authority for fold assignments, campaign episodes, episode
  labels, and topology viability. Keep validation, models, metrics, TDI,
  predictions, submissions, and transduction denied. Require the oracle loader
  to verify the combined manifest receipts and reject anchor observations from
  outside the public episode component.
- Evidence: Five focused synthetic tests and all 229 repository tests pass;
  Ruff, mypy, package build, and diff checks pass. Two official runs outside
  Git were byte-identical for all seven artifacts. Each episode projection has
  1,122 unique joined rows, with 1,818 expanded queries, 4,488 anchor
  references, and 7,272 query references. The accepted manifest is
  `08dcf61cded99fae046bff49b57b0c4a12082cd8714c779ac44a351bf1a0c8c8`;
  R2A hashes remain unchanged. Independent review passed after closing
  manifest-mixing, component-membership, and fold-scope traceability gaps.
  CYP3A4 is supported at 95 components/473 pairs; CYP1A2, CYP2C9, and CYP2D6
  are underpowered with zero local fusion weight.
- Alternatives: Trust generated projections without a receipt-bound loader;
  enable all direct endpoints despite inadequate support; or begin modeling
  before the artifact boundary and controls are accepted.
- Reversal condition: A replay or R3 implementation finds receipt, identity,
  chemistry, family containment, projection, determinism, authority, or
  non-anchor label exposure drift. Preserve the blocker and stop before fitting
  or scoring.

## D-039 — Freeze the R3 global direct experiment contract

- Date: 2026-08-18
- Status: superseded by D-040 before execution
- Decision: Freeze
  `cypshift.openadmet_cyp_2026.global_experiment_contract.v1` at
  `R3_GLOBAL_EXPERIMENT_CONTRACT_FROZEN`. Split the mandatory direct global
  fallback from later oracle/transformation work. Keep
  `GLOBAL_FAMILY_HOLDOUT` on the unchanged D-032 component proxy, target only
  finite reported central direct pIC50 points, and freeze four systems:
  endpoint median, Morgan 1-NN, Morgan CatBoost, and fixed MapLight. Use a
  CPU-only CatBoost 1.2.1 Linux overlay for both learned candidates, and if
  the pinned MapLight overlay cannot replay the signed-int8 and four-column
  NaN contracts without semantic drift, disqualify MapLight and retain Morgan
  as the only eligible learned candidate. Keep official ST-RAE, TDI,
  submissions, transduction, anchor exposure, and all transformation/oracle
  logic unauthorized. A successful R3 implementation authorizes only the
  frozen global direct OOF/model/parent-completion artifacts and internal
  surrogate metrics. R4 must separately freeze oracle/transformation controls
  before local TRACE work.
- Evidence: R2B granted artifact authority only and left all modeling blocked.
  The active phase text still bundled oracle work into R3, while the restored
  blueprint and review feedback required a smaller, global-only gate first.
  The accepted contract binds the R2A/R2B receipts, preserves D-032 as a
  conservative reconstructed-family proxy, names the Linux MapLight
  compatibility prerequisite, forbids GIN, generic-difference, and broad
  search, and keeps the implementation below any official-metric or submission
  boundary. Focused static tests freeze the receipt chain, target semantics,
  frozen systems, firewall, outputs, budget, metrics, acceptance logic, and
  inherited-R2B authority.
- Alternatives: Bundle the CYP3A4 oracle contract into R3; inherit the old
  macOS comparator environment claim on Linux; reintroduce GIN or generic
  molecular-difference baselines before the global fallback is frozen; or use
  official ST-RAE names before validator parity is established.
- Reversal condition: A pre-implementation review, synthetic implementation,
  or official replay finds receipt, runtime, feature-version, split, firewall,
  metric, determinism, or authority drift. Preserve the blocker and issue a
  versioned replacement before fitting.

## D-040 — Reject R3 v1 before execution and freeze corrected v2

- Date: 2026-08-18
- Status: superseded by D-041 before R3A
- Decision: Supersede v1 at commit `c10980f...` with
  `cypshift.openadmet_cyp_2026.global_experiment_contract.v2` at
  `R3_GLOBAL_EXPERIMENT_CONTRACT_V2_FROZEN`. Preserve the four global systems,
  D-032 folds, central-point target, 360-fit ceiling, provisional metric, and
  all no-oracle/no-TDI/no-test boundaries. Make the Linux MapLight overlay a
  hard pre-fit gate; freeze exact OOF identifiers/serialization, leakage-safe
  q90 calibration, bootstrap arithmetic, support/status precedence, and
  influence rules. Stage execution as R3A label-free Linux features, R3B
  synthetic projector/runner acceptance, and R3C official frozen experiment.
- Evidence: Independent post-integration review found five v1 blockers:
  conditional MapLight failure contradicted fixed row/fit counts; OOF IDs were
  underdefined; uncertainty calibration could be leaky or tautological;
  bootstrap selection was not numerically complete; and promotion statuses
  were not mechanically decidable. Final independent Sol review passes after
  correction. No feature, target projection, model fit, prediction, or metric
  evaluation occurred under v1.
- Governance: The assigned read-only GPT-5.4 auditor violated scope by editing,
  signing, and pushing v1 directly to `main` without the required pull request.
  Root detected the integration before execution, preserved the signed history,
  and moved v2 correction through the normal reviewed branch workflow. The
  unauthorized integration is not scientific approval.
- Alternatives: Rewrite or delete the signed v1 history; proceed with ambiguous
  implementation choices; silently drop MapLight after a Linux failure; or
  combine feature parity, firewall construction, and scientific fitting in one
  oversized milestone.
- Reversal condition: R3A or R3B finds receipt, environment, feature, split,
  serialization, firewall, arithmetic, determinism, or authority drift.
  Preserve the blocker and supersede v2 before any scientific fit.

## D-041 — Repair the R3A chemistry-input firewall in v3

- Date: 2026-08-18
- Status: accepted; corrected contract-only R3 gate
- Decision: Supersede v2 at commit `e897738...` with
  `cypshift.openadmet_cyp_2026.global_experiment_contract.v3` at
  `R3_GLOBAL_EXPERIMENT_CONTRACT_V3_FROZEN`. Preserve all v2 systems, folds,
  metrics, arithmetic, budgets, staged execution, and exclusions. Add exactly
  one trusted R3A chemistry projector: verify the accepted direct-observation
  bytes, decode only the first eight fields through raw SMILES, keep each
  target-bearing suffix opaque, join the train-only topology and label-free
  fold artifacts, recompute the frozen standardized structure, and assert its
  accepted hash. Emit 4,905 direct-only raw/standardized chemistry rows plus a
  receipt that binds inputs, code, environment, output, accounting, and denied
  authority. Exact raw SMILES feed MapLight; standardized SMILES feed D-032
  Morgan. The feature process may see only the receipt-bound projection.
  Target values parsed/retained and blinded-test rows opened are exactly zero.
- Evidence: Pre-implementation audit found no accepted artifact satisfying v2:
  direct-only sources contain targets, while label-free R1/topology artifacts
  also contain 750 blinded-test structures. `group_folds.csv` provides the
  correct 4,905 identities but no structures. The prefix projector is the
  smallest boundary that preserves both direct-only chemistry and target/test
  isolation. No R3A projection, feature, target, fit, prediction, or metric
  artifact existed when the contradiction was found. A final specification
  audit additionally required the accepted train-only topology receipt and a
  projection manifest so Morgan chemistry and the consumer boundary are
  mechanical rather than implicit.
- Alternatives: Let the feature process open target-bearing observations; use
  mixed R1 artifacts and silently traverse test chemistry; defer the trusted
  projection to R3B despite requiring R3A features; or copy chemistry by hand.
- Reversal condition: Synthetic prefix parsing cannot preserve RFC4180 quoting,
  receipt-before-parse, exact four-endpoint identity, opaque suffixes, or zero
  target/test accounting; standardization cannot reproduce all 4,905 topology
  hashes; or the consumer cannot verify the projection receipt before parsing.
  Preserve the blocker and supersede v3 before feature generation.

## D-042 — Accept the R3A implementation boundary before official execution

- Date: 2026-08-18
- Status: accepted; implementation and synthetic replay only
- Decision: Accept the trusted prefix projector, core RDKit 2026 Morgan worker,
  and isolated RDKit 2023 MapLight runner for the official R3A feature gate.
  Keep `R3A_LINUX_FEATURES_ACCEPTED` ungranted until the receipt-bound 4,905-row
  projection and two fresh full feature roots are byte-identical and
  independently reviewed. Grant no feature, target, model, prediction,
  validation, metric, TDI, submission, or transductive authority here.
- Evidence: All consumers verify the complete v3 receipt, policy, runtime,
  formula, accounting, and authority boundary before parsing payloads. Linux
  `renameat2(RENAME_NOREPLACE)` is the only promotion path; read-only staging
  precedes promotion. The frozen environment reproduces all four MapLight
  blocks on the eight-row fixture, signed-int8 witnesses `127/-128/-112`, and
  CatBoost `nan_mode=Min`. Two fresh two-molecule feature builds are
  byte-identical. The full 276-test suite, Ruff, mypy, build, and independent
  scientific review pass. Official challenge inputs and generated official
  artifacts opened remain zero.
- Alternatives: Combine implementation and official evidence in one opaque
  milestone; let the feature process open target-bearing observations; permit
  check-then-rename overwrite races; or begin scientific fitting before full
  feature replay.
- Reversal condition: Official projection or replay finds any receipt,
  chemistry, row alignment, environment, payload, NaN, determinism, resource,
  isolation, or authority defect. Preserve the failed artifacts outside Git,
  record `GLOBAL_FAILED`, and stop before R3B or any fit.

## D-043 — Accept the official R3A Linux feature payloads

- Date: 2026-08-18
- Status: accepted; `R3A_LINUX_FEATURES_ACCEPTED`
- Decision: Accept the receipt-bound 4,905-row chemistry projection, core
  standardized Morgan array, and two byte-identical Linux feature roots for the
  frozen R3 global experiment. This grants deterministic feature-payload and
  Linux method-compatibility authority only. Keep official target projection,
  models, OOF predictions, validation, metrics, TDI, submissions, official
  scoring, and transduction unauthorized until their later gates pass.
- Evidence: The projection manifest is `a472b6ab...`; target values parsed and
  retained and blinded-test rows opened are zero. The core Morgan manifest is
  `1b897f45...`. Feature manifests `32a95095...` and `832efbd1...` differ only
  in build ID, runtime, and RSS; aligned rows, the compatibility receipt, and
  all five arrays are byte-identical. Independent recomputation found zero
  mismatches across all 4,905 standardized Morgan rows and all four raw-SMILES
  MapLight blocks. Arrays have exact frozen shapes/dtypes, zero infinity, and
  zero NaN cells. Builds took 21.47/21.54 seconds at 0.58/0.54 GiB RSS.
- Alternatives: Trust one feature build; reuse the old macOS feature evidence;
  mix raw and standardized chemistry; open target/test artifacts in the feature
  process; or begin official fitting before independent replay.
- Reversal condition: R3B or R3C finds any receipt, row, chemistry, environment,
  payload, determinism, rights, isolation, or authority defect. Preserve the
  evidence, record `GLOBAL_FAILED`, and stop before promotion or submission.

## D-044 — Freeze the additive R3B synthetic runner contract

- Date: 2026-08-18
- Status: accepted; contract-only gate
- Decision: Keep the accepted v3 contract and every R3A implementation byte
  immutable, and add
  `cypshift.openadmet_cyp_2026.global_experiment_contract.v4` at
  `R3B_GLOBAL_RUNNER_CONTRACT_V4_FROZEN`. Predesignate fixed MapLight before
  target access so outer OOF evidence validates one frozen expert rather than
  selecting and validating on the same rows. Retain Morgan CatBoost, endpoint
  median, and Morgan 1-NN only as falsification comparators. Require strict
  complete-point targets, disjoint model-public and scorer-sealed projections,
  pre-fit support checks, score-free inner tokens, exact bootstrap/q90 and
  completion arithmetic, status-specific evidence authority, and one atomic
  terminal publication from a private run root. A valid negative outer result
  remains evidence; no R3 status claims a deployable full-training model.
- Evidence: Pre-implementation review rejected the v3 R3B mechanics because
  target/cell/scorer schemas were incomplete, candidate selection reused its
  evaluation rows, model processes could receive truth or score receipts,
  underpowered and late-failure publication was contradictory, and nested
  terminal arithmetic was not mechanically frozen. V4 closes those blockers
  without opening official targets or running a scientific fit. Its SHA-256 is
  `a37a316ceab297deb89d4458169d38d1c73d2edb39ab96ea4c77459a56b01254`.
  Sixteen combined v3/v4 tests, strict duplicate-key JSON parsing, Ruff, and two
  final independent audits pass.
- Alternatives: Mutate v3 and invalidate accepted R3A receipts; select MapLight
  or Morgan using the same outer rows later used for the success claim; add a
  nested model-selection experiment and larger fit budget; expose full
  score-bearing receipts to inner fits; or begin official execution before the
  runner firewall is synthetically accepted.
- Reversal condition: R3B implementation cannot reproduce the exact schemas,
  process isolation, deterministic arithmetic, status outputs, or authority
  boundary on adversarial synthetic fixtures. Preserve the blocker and issue a
  versioned repair before any official target projection or fit.

## D-045 — Repair the R3B execution contract before implementation

- Date: 2026-08-18
- Status: accepted; contract-only repair
- Decision: Supersede only v4's implementation mechanics with additive v5 at
  `R3B_GLOBAL_RUNNER_CONTRACT_V5_REPAIR_FROZEN`. Preserve the frozen MapLight
  expert, three controls, group folds, provisional metrics, budgets, terminal
  decisions, and authority denials. Require all 60 outer and 240 inner target
  files, including header-only zero-row contexts; hash all 300 before parsing;
  report truthful preflight accounting; bind every new artifact and model/cell
  identifier to v5 while preserving split IDs; define all accounting schemas;
  record composite implementation receipts; and make resolved CatBoost
  parameters recoverable from versioned freezer manifests.
- Evidence: Implementation and adversarial review found four pre-execution
  blockers in v4: its clean terminal accounting contradicted the required
  300-file preflight, zero-training inner contexts could omit required files,
  accounting/freezer schemas were incomplete, and source/split bindings could
  drift without detection. No official target, feature root, fit, prediction,
  metric, or submission was opened. The repaired v5 SHA-256 is
  `596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2`;
  nineteen combined v4/v5 static tests, strict JSON, Ruff, and deep independent
  review pass.
- Alternatives: Relax the receipt firewall; treat malformed zero-support cells
  as integrity failures; record false zero-open accounting; silently reinterpret
  v4 in code; or begin official fitting before the contract is executable.
- Reversal condition: The synthetic implementation cannot reproduce v5's exact
  cardinalities, receipts, arithmetic, process isolation, or no-authority
  boundary. Preserve the blocker and repair it before any official execution.

## D-046 — Accept the complete R3B synthetic global runner

- Date: 2026-08-18
- Status: accepted; `R3B_GLOBAL_RUNNER_SYNTHETIC_ACCEPTED_V5`
- Decision: Accept the v5 target projector, preflight, isolated model cells,
  prediction freezers, bounded surrogate scorer, and single terminal publisher
  as the complete synthetic R3B implementation. Authorize only one subsequent
  frozen R3C official global experiment. Keep official score, submission, TDI,
  oracle-anchor, transformation, transductive, and deployable-model authority
  denied.
- Evidence: Two fresh synthetic roots each ran all 60 outer and 240 inner cells
  in separate processes: 600 unique cell processes and 720 real CatBoost fits
  total. Both reached `GLOBAL_EXPERT_FROZEN`; deterministic projection,
  preflight, feature, freezer, score, and terminal artifacts were byte-identical
  after normalizing only validated nonnegative runtime and peak-memory fields.
  Linux x86_64, Python 3.10.13, the research lock SHA, NumPy 1.25.2, and CatBoost
  1.2.1 were verified before every fit. Seventy-seven focused integration tests
  and the 363-test repository suite pass, with three expected skips; Ruff,
  formatting, scoped mypy, and independent adversarial review pass. Official
  targets, challenge feature roots, predictions, metrics, TDI, and test data
  opened remain zero.
- Alternatives: Run official targets before the firewall passed; share one
  process across cells; weaken receipts or schema checks; redesign the frozen
  systems after observing outer results; or split cohesive modules solely to
  satisfy a line-count target.
- Reversal condition: R3C finds source, runtime, receipt, split, isolation,
  determinism, arithmetic, or authority drift. Emit `GLOBAL_FAILED`, preserve
  the blocker outside Git, and stop before granting predictive evidence.

## D-047 — Accept the hardened R3C official execution boundary

- Date: 2026-08-18
- Status: accepted; `R3C_OFFICIAL_EXECUTION_READY`
- Decision: Accept the thin production-only R3C state machine and the repaired
  R3B capability/provenance boundary. Supersede D-046's implementation source
  receipts with the D-047 receipts below. Authorize exactly one frozen official
  global experiment from immutable accepted inputs; do not authorize retries,
  redesign, submissions, official-score claims, TDI, oracle anchors,
  transformations, or transductive use.
- Evidence: The wrapper verifies both locked runtimes, all contract and source
  receipts, and the accepted R3A feature root before opening official targets.
  Every model process receives a read-only view containing only the common
  manifest, model rows, and its one selected target file; freezers receive no
  target payloads. The causal path is exactly 60 outer cells, outer freeze and
  score, then either a terminal result or a score-free token authorizing 240
  inner cells. All work remains private until exact read-only terminal
  publication after private cleanup with no-replace semantics. The repaired
  cell, freezer, scorer, and wrapper SHA-256 receipts are respectively
  `9934e267b09df763fb45071884415b5c8f6eeb10189edc30e862bc758c45a053`,
  `535e84951279894f0c8245112a95218e67d8059fc6f6b88aea1372d18323e6bc`,
  `2a3dec027efe46e0e6439a0280ce1df9182fe1a063d25143f7bd331b2d1ea8ac`,
  and `436c95a808733d7144604fdd6d733cc1edba6320072f201374a6d331afa3eb8d`.
  A new two-root
  replay again used 600 isolated processes and 720 real CatBoost fits; both
  roots reached `GLOBAL_EXPERT_FROZEN` with deterministic artifacts. Seventy-six
  focused tests, all 384 collected repository tests with three expected skips,
  Ruff, scoped mypy, and independent adversarial review pass. Official target
  values opened remain zero.
- Alternatives: Manually sequence the component CLIs; expose all 300 target
  files to every cell; rely on in-band self-reporting; retain stale D-046 source
  hashes; publish before private cleanup; or run official labels before the
  repaired boundary passed.
- Reversal condition: The one official R3C run finds any input, source, runtime,
  capability, split, process, receipt, arithmetic, cleanup, or terminal defect.
  Publish `GLOBAL_FAILED`, preserve the evidence outside Git, and stop without
  retrying or granting predictive authority.

## D-048 — Freeze the positive official R3C global result

- Date: 2026-08-18
- Status: accepted; `R3C_GLOBAL_EXPERT_FROZEN`
- Decision: Accept fixed MapLight as the frozen direct global expert for the
  next TRACE experiments. Do not rerun R3C, tune from its outer evidence, add
  another global representation, or treat the result as a deployable model or
  official challenge score. Authorize frozen global OOF predictions, internal
  surrogate evidence, inner OOF predictions, and parent-state completion only.
  R4 must first freeze a label-safe transformation coverage/support contract;
  only a supportable result may advance to a separate CYP3A4 oracle-anchor
  contract with the complete blueprint system, control, and ablation set.
- Evidence: The single D-047-authorized official run reached
  `GLOBAL_EXPERT_FROZEN` after 60 outer cells, 120 outer fits, a causal positive
  outer gate, 240 fresh inner cells/fits, and exact completion. MapLight's
  overall endpoint-macro component-MAE point estimate is 0.571053. Its paired
  loss advantages are 0.064563 over
  Morgan CatBoost (95% bootstrap interval 0.056854 to 0.072240), 0.141052 over
  the endpoint median (0.130587 to 0.152246), and 0.438851 over Morgan 1-NN
  (0.422225 to 0.455456). All 2,000 replicates were accepted with positive lower
  bounds. MapLight improved over the median for all four CYPs and all 60 outer
  cells; it beat Morgan in 56/60 cells, with the four reversals small. The
  CYP1A2/2C9/2D6/3A4 MapLight MAEs are 0.657310/0.474675/0.583530/0.568697.
  All endpoint caps, 30 influence deletions, 60 uncertainty contexts, and both
  completion artifacts pass. The exact 15-file read-only terminal has manifest
  SHA-256 `a2029e12231a22415900c55303ec5413b395aedc15d565ef7b4e650196b3277c`
  and result SHA-256
  `d9aff555db3c985ca834a11f5d1f198a9c8c5bafcaced6e7719a88bab09c2f94`.
  Two independent read-only audits reproduced receipts, schemas, counts,
  metrics, bootstrap intervals, influence checks, uncertainty, and completion.
  Blinded test, TDI, submission, official-metric, anchor, and transductive access
  remained zero; private intermediates are absent.
- Alternatives: Reject a predeclared expert despite a clean positive gate;
  select Morgan from the same outer evidence; rerun to improve a result; tune
  endpoint-specific systems after inspection; begin submission work before an
  official scorer exists; or skip directly to inferred anchors.
- Reversal condition: Independent replay later finds receipt, arithmetic,
  split, capability, or authority drift. Preserve the terminal, revoke only
  the affected R3C evidence, and stop dependent work; never repair the result
  by rerunning the frozen experiment.

## D-049 — Freeze label-safe transformation coverage before TRACE fitting

- Date: 2026-08-18
- Status: accepted; `R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN`
- Decision: Freeze deterministic transformation extraction and support
  arithmetic before any parent-relative model fit. R4 may read accepted
  structures, direct measurement availability state, public episode membership,
  and the mask anchor-identity prefix only. It must not open campaign truth,
  selector/scorable state, target magnitudes, blinded test chemistry, TDI,
  predictions, metrics, or submissions. A supported coverage result authorizes
  only a separate CYP3A4 oracle-contract freeze; underpowered coverage stops the
  local path without weakening thresholds.
- Evidence: The contract SHA-256 is
  `d4c999e66309d27caab558f69cdba3fe1762aa9804053b0f1b86a2401297aec5`;
  its extraction-spec receipt is
  `d087207d0873c1c9861e34781a26d5ea8053469bc727a1f41b9ee190da3e1973`.
  It binds exact RDKit single/double-cut normalization, virtual-H and stereo
  handling, canonical indices and environments, six exhaustive row states,
  self-versioned bidirectional IDs, structural-only terminal schemas, valid-only
  local/episode support gates, cross-CYP sharing, and status-conditioned
  authority. Seven focused tests, strict JSON, Ruff, formatting, diff checks,
  and independent scientific and minimality audits pass. No official data was
  opened during the contract milestone; model fits, predictions, and metric
  evaluations are zero.
- Alternatives: Begin oracle fitting before measuring usable transformation
  support; expose campaign truth or held-out availability in R4; rescue complex
  edits with MCS; count repeated pairs instead of independent proxy families;
  or tune support thresholds after extraction.
- Reversal condition: Synthetic implementation cannot reproduce the receipt,
  chemistry invariants, firewall, row partitions, support arithmetic, or exact
  terminal authority. Preserve the blocker, repair or version the contract, and
  do not open the official coverage inputs or fit TRACE.

## D-050 — Supersede R4 v1 with the executable additive v2 contract

- Date: 2026-08-18
- Status: accepted; `R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN`
- Decision: Preserve D-049 and its v1 bytes as immutable history, but use the
  additive v2 contract as the sole R4 implementation authority. Enumerate and
  rank single- and double-cut candidates together, make exact transformation
  IDs reusable across proxy families, and freeze the remaining chemistry,
  serialization, support, schema, and failure semantics without changing the
  label-safe data boundary or granting model authority.
- Evidence: Implementation review found that v1's single-first rule made valid
  double cuts effectively unreachable and that its pair-specific exact ID could
  not support cross-family frequency or support counts. V2 corrects those
  blockers and mechanically binds virtual-H and stereo records, rooted
  environments, reversal/class behavior, ambiguity, valid-only fold arithmetic,
  nested coverage schemas, and deterministic failure handling. Its contract
  SHA-256 is
  `a13adee526575b4dc22c414c08cbcb9cf3ff8cc69c8eb10ad9c078e5eb4ae73e`;
  its extraction-spec receipt is
  `c7fb3a6a905d4265a174cdcde4e5f391c3d7f154a8cc2ed126a3830796c41e74`.
  Nine focused v2 tests, the full repository suite, strict JSON, extraction-
  receipt recomputation, Ruff, formatting, mypy, build, and independent
  scientific review pass. No official input, target magnitude, model fit,
  prediction, metric, test, TDI, submission, or transductive operation occurred.
- Alternatives: Silently reinterpret v1 in implementation; drop double-cut
  support; retain pair-specific IDs and make exact support vacuous; or open
  official coverage inputs before the contract is executable.
- Reversal condition: Synthetic implementation cannot reproduce v2's receipt,
  chemistry invariants, directional IDs, row partitions, support arithmetic,
  byte schemas, or authority boundary. Preserve the blocker, issue a versioned
  repair, and do not open official coverage inputs or fit TRACE.

## D-051 — Supersede R4 v2 with exact stereo and graph-map semantics

- Date: 2026-08-18
- Status: accepted; `R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN`
- Decision: Preserve v1/v2 as immutable history, but use the self-contained v3
  contract as the sole R4 implementation authority. Freeze exact RDKit
  potential-stereo discovery, CIP vocabulary, enhanced/unsupported-stereo
  rejection, isotope-preserving reference graphs, automorphism consensus, and
  full-graph map attributes/direction before implementing the extractor.
- Evidence: Implementation design found that v2 defined stereo record shapes
  but not unique record bytes. Equivalent atom orders can invert raw RDKit
  orientation descriptors, unspecified potential double bonds can disappear
  under weaker discovery, enhanced stereo can collapse under plain SMILES, and
  incomplete map filters can accept atom-map, implicit-H, or dative-direction
  mismatches. V3's contract SHA-256 is
  `f5e1862682c1d2a3e34fcf530c9aad42cbd4e4538488eca1a4c5508443f61db5`;
  its extraction-spec receipt is
  `3d0b097602008457ffcefd4a0cf93673b5522112f91637634d162f5e619ff202`.
  Twenty-seven focused v1/v2/v3 tests, strict receipt recomputation, the full
  repository suite, and independent scientific re-audit pass. No official
  input, target, model, prediction, metric, test, TDI, submission, or
  transductive operation occurred.
- Alternatives: Encode raw CW/CCW descriptors; ignore enhanced or potential
  stereo; choose one graph map by atom order; or defer ambiguity to extraction.
- Reversal condition: Synthetic extraction cannot reproduce v3's exact stereo
  records, graph maps, IDs, reversal invariants, or receipt. Preserve the
  blocker, version the contract, and keep official coverage inputs closed.

## D-052 — Accept the synthetic R4 trusted-projection boundary

- Date: 2026-08-18
- Status: accepted implementation slice;
  `R4_TRANSFORMATION_PROJECTION_SYNTHETIC_ACCEPTED`
- Decision: Accept the focused I/O and projection modules as the sole synthetic
  R4 source-firewall implementation. Keep chemistry extraction, support,
  coverage authority, and official input access outside this milestone.
- Evidence: The implementation loads each of five receipt-bound byte streams
  once, checks every receipt before parse, decodes only the frozen direct and
  mask-prefix fields, and validates endpoint, structure, component, fold,
  public-query, and anchor identity. It canonicalizes row order and atomically
  promotes exactly six read-only files without overwrite. Its I/O, projector,
  and focused-test SHA-256 values are `820a83b3563bc4f8dbb7de2b13ad0c8fdf9032db8d9bbcb75a6962ffc53a3ee9`,
  `0e094712f4f7e10f878ea3ac6a1907f2ad42a25db3c70fbefec70b3ab2aca73a`,
  and `5c2b2ecb649287275a9e2b8f5b939f4c0b4f927c79cc2eaf6d2d1d4d3106b8de`.
  Thirty-seven focused tests, the full repository suite, Ruff, formatting,
  mypy, and independent correctness/minimality audits pass. Official inputs,
  target magnitudes, models, predictions, metrics, test, TDI, submissions, and
  transduction remain at zero.
- Alternatives: Let the extractor open target-bearing or mask source files;
  decode forbidden fields and promise not to use them; or combine projection,
  chemistry, coverage, and publication in one unreviewable milestone.
- Reversal condition: Any receipt-before-parse, opaque-field, join,
  determinism, path, atomic-publication, or authority defect revokes this
  implementation evidence. Before official use, separately bind R4 v4, the
  accepted R2B/R3A manifests and leaves, and exact implementation receipts.

## D-053 — Supersede R4 v3 with the corrected v4 extraction contract

- Date: 2026-08-18
- Status: accepted; `R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN`
- Decision: Preserve v1/v2/v3 as immutable history, but use the self-contained
  v4 contract as the sole R4 implementation authority. Keep the scientific
  populations, support gates, output authority, and label-safe boundary
  unchanged while repairing only contradictions exposed by executable
  synthetic witnesses.
- Evidence: V4 narrowly permits the RDKit reference-round-trip hydrogen
  partition only at supported tetrahedral centers, defines the no-candidate
  S2 sentinel for a capped embedding search, makes unsupported stereo C3 only
  after non-stereo graph identity, requires full bond direction/stereo remapping
  during variable reconstruction, and freezes query-rank and publication
  receipts. Its contract SHA-256 is
  `cacd1f77215e36a17f03553680d71263425638c290a39d33c397e43b2c35550f`;
  its extraction-spec receipt is
  `59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950`.
  Thirty-seven focused v1-v4 contract tests, strict duplicate-key JSON,
  extraction-receipt recomputation, Ruff, formatting, and independent
  scientific review pass. No official input, target, fit, prediction, metric,
  test, TDI, submission, or transductive operation occurred.
- Alternatives: Silently weaken exact graph matching in code; serialize a
  truncated embedding set as valid; discard graph-changing ordinary pairs that
  carry unrelated unsupported stereo; lose E/Z state during reconstruction; or
  open official coverage before these mechanics are exact.
- Reversal condition: Synthetic extraction cannot reproduce the v4 receipt,
  graph-first precedence, bond-stereo reconstruction, cap sentinel, IDs, or
  reversal invariants. Preserve the blocker, issue a versioned repair, and keep
  official coverage inputs closed.

## D-054 — Accept the pure synthetic R4 transformation extractor

- Date: 2026-08-18
- Status: accepted implementation slice;
  `R4_TRANSFORMATION_EXTRACTION_SYNTHETIC_ACCEPTED`
- Decision: Accept the receipt-bound shared types, ordinary MMP, stereo-only,
  and thin precedence modules as the sole pure v4 pair extractor. Keep
  projection binding, population construction, support arithmetic, publication,
  official input access, and every model outside this milestone.
- Evidence: The extractor implements joint single/double cuts, virtual-H
  growth/contraction, exact stereo-only changes, canonical directions, reusable
  exact/class IDs, environment IDs, cap/tie sentinels, and atom-order/pair-
  reversal invariance. Independent review initially rejected loss of E/Z state
  during variable reconstruction and C3 precedence on graph-changing pairs;
  complete bond-stereo remapping and graph-first stereo scope repaired both
  before acceptance. The types, MMP, stereo, and unified source SHA-256 values
  are `d9fc616f25a4c6b6cc8b2bbd538920218ae51b116fd32c2f0c01ff395657b64b`,
  `3e5a5079c096326656a82370d35288475921c53eebcef0e6a60df440b60936eb`,
  `838d66f48bcdd75ccfb1fa5cd8de1654bdf7632e82f62f1252554f7483736ff1`,
  and `2ac5ea0004402df82bbb26024089a1b0b2fe258346a71c7b89bd1512672eaaed`.
  Sixty-nine focused contract/extractor tests and all 490 repository tests pass
  with three expected skips; Ruff, formatting, strict mypy, package build, and
  independent scientific/minimality review pass. Official input, target,
  support evaluation, fit, prediction, metric, test, TDI, submission, and
  transduction remain at zero.
- Alternatives: Combine extraction with privileged projection or coverage;
  use MCS fallback; discard stereo; ignore ambiguous decompositions; or split
  the cohesive ordinary algorithm solely to meet a line target.
- Reversal condition: Any receipt, exact-chemistry, graph-first precedence,
  ambiguity, ID, or invariance defect revokes this implementation evidence.
  Repair and repeat synthetic review before production binding; never repair an
  official coverage result in place.

## D-055 — Supersede R4 v4 with the mechanically closed v5 contract

- Date: 2026-08-20
- Status: accepted; `R4_TRANSFORMATION_COVERAGE_CONTRACT_FROZEN`
- Decision: Preserve v1 through v4 as immutable history, but use the
  self-contained additive v5 contract as the sole R4 implementation authority.
  Keep the extraction receipt, chemistry, populations, thresholds, columns,
  firewall, and authority unchanged. Define the clean zero-valid distribution,
  refuse runtime or dirty-checkout drift before official input access without a
  contradictory terminal, and make canonical histogram bytes lexicographic
  while evaluating all rational statistics numerically.
- Evidence: V5 SHA-256 is
  `63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954`;
  its parent v4 SHA-256 is
  `cacd1f77215e36a17f03553680d71263425638c290a39d33c397e43b2c35550f`.
  The extraction-spec receipt independently remains
  `59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950`.
  Forty-three focused v1-v5 tests, the full suite with three expected skips,
  Ruff, mypy, build, strict JSON, receipt recomputation, and independent
  scientific/mechanical review pass. Official inputs, target magnitudes, fits,
  predictions, metrics, test, TDI, submissions, and transduction remain zero.
- Alternatives: Let an underpowered clean run fail while serializing an empty
  distribution; publish a failure receipt that falsely claims an accepted
  runtime; let JSON object order change rational statistics; or silently choose
  implementation semantics under v4.
- Reversal condition: Synthetic coverage compilation cannot reproduce v5's
  exact zero and positive distributions, pre-input refusal, canonical bytes,
  support arithmetic, or authority boundary. Preserve the blocker and keep
  official coverage inputs closed.

## D-056 — Accept the synthetic R4 projection consumer

- Date: 2026-08-20
- Status: accepted implementation slice;
  `R4_TRANSFORMATION_PROJECTION_CONSUMER_SYNTHETIC_ACCEPTED`
- Decision: Accept the bounded v5 projection consumer and immutable typed
  records as the sole input boundary for later synthetic coverage compilation.
  Keep structural-union construction, chemistry extraction, support arithmetic,
  production source authentication, publication, official input access, and all
  models outside this milestone.
- Evidence: The consumer and focused-test SHA-256 values are
  `d60af6a251aa0f69cdee3f3f70a47b2107ec4f6d6c7d189ca641c3873f107472`
  and `70f025c4ce3747cab35ac63e5ebf593df9bc9e687fd907c5317ed641affe9dda`.
  It hashes all six files before parse, checks canonical bytes and typed
  receipts, replays standardization and every direct/fold/public/mask join, and
  rejects path, authority, type-alias, noncanonical, duplicate, containment,
  and empty-population drift. Eleven focused and 48 combined tests, the full
  suite with three expected skips, Ruff, mypy, build, and independent
  adversarial review pass. Official inputs and scientific operations remain
  zero.
- Alternatives: Let the compiler reopen privileged sources; trust the
  projector without revalidation; mix production receipts or coverage
  arithmetic into the loader; or accept an internally consistent empty input.
- Reversal condition: Any receipt-before-parse, standardization, identity,
  component, fold, episode, mask, nonempty, determinism, or firewall defect
  revokes only this consumer evidence and keeps official R4 inputs closed.

## D-057 — Accept the synthetic R4 structural-geometry compiler

- Date: 2026-08-20
- Status: accepted implementation slice;
  `R4_TRANSFORMATION_GEOMETRY_SYNTHETIC_ACCEPTED`
- Decision: Accept the minimal structural-union, extraction-once, directional
  episode, and canonical pair-byte compiler over the accepted projection
  consumer and pure extractor. Keep endpoint support arithmetic, coverage
  status, production authentication, publication, official inputs, and every
  model outside this milestone.
- Evidence: The compiler and combined focused-test SHA-256 values are
  `559d4b88dd5657f166e05d3ba341fa0f5fb8021ba19fdbee62ec5469bdfda5c8`
  and
  `139b4812039a093431fde312dc3850d35325088b326b4468a6933b26404ec9af`.
  It constructs same-component Morgan radius-2/4,096/chiral pairs at inclusive
  similarity 0.60, unions every episode pair, extracts each unique pair once,
  preserves exact anchor-to-query direction, and emits the exact 47-column
  canonical pair CSV. Fifty-three focused tests, the full suite with three
  expected skips, Ruff, strict mypy, build, and independent adversarial review
  pass. Official inputs, endpoint support, model fits, predictions, metrics,
  test, TDI, submissions, and transduction remain zero.
- Alternatives: Extract local and episode populations separately; duplicate
  repeated episode chemistry; let molecule order define direction; include
  endpoint availability in structural rows; or combine support and publication
  before this geometry was independently reviewable.
- Reversal condition: Any component crossing, threshold, extraction-count,
  canonical direction, invalid-sentinel, deterministic-byte, or firewall defect
  revokes only this geometry evidence and keeps official R4 inputs closed.

## D-058 — Freeze the narrow R4 v6 support-population clarification

- Date: 2026-08-20
- Status: accepted; `R4_TRANSFORMATION_COVERAGE_CONTRACT_V6_FROZEN`
- Decision: Preserve v5 as immutable implementation authority and apply only
  the two exact absent-member operations declared by v6. The valid changed-
  heavy-atom fraction distribution is over unique valid union structural-pair
  rows, and its count equals `counts.union.valid_rows`. All other v5 semantics
  and bytes remain authoritative.
- Evidence: The v6 overlay and test SHA-256 values are
  `a0743c43cdafbcfd736cf94c57fe21488266d1f6df6ef73311c26ccda795f95d`
  and
  `ad340bfbfe38e4beba2c793bdef9a278c6929f5b6ccad564b6668b4303e76699`.
  Its exact v5 parent receipt is `63d12cb3...`. Forty-six focused v1-v6
  tests, strict duplicate-key parsing, five adversarial overlay mutations,
  Ruff, formatting, and independent review pass. Chemistry, thresholds, output
  schemas, firewall, publication, and authority are unchanged; official input
  and all scientific operations remain zero.
- Alternatives: Silently choose union, local, selected, or stress rows in the
  implementation; mutate immutable v5; or duplicate the complete v5 document
  solely to add two fields.
- Reversal condition: Any parent-receipt, pointer-resolution, absent-member,
  union-deduplication, or count-invariant defect blocks support arithmetic and
  preserves v5 plus the defect as evidence.

## D-059 — Accept pure synthetic R4 support arithmetic

- Date: 2026-08-20
- Status: accepted implementation slice;
  `R4_TRANSFORMATION_SUPPORT_SYNTHETIC_ACCEPTED`
- Decision: Accept the pure typed support compiler over the accepted projection
  bundle and structural geometry under effective v5 plus v6. Keep episode CSV,
  coverage JSON, manifests, production authentication, publication, official
  inputs, and every model outside this milestone.
- Evidence: The support source and focused-test SHA-256 values are
  `9d08b5c0e23d41958a2d1924a6b17b7ef1bb54dbd4ed74946d317e94c57f03ec`
  and
  `ab72761c7953adb993dbe7af05ce0793bf3f987c5ca3ab3ed27276f568afc172`.
  It implements complete-state local populations, 15 held-out cells per
  endpoint, valid-only local/selected gates, selected/stress isolation,
  direction-aware exact and class-token frequencies, independent-component and
  cross-CYP support, group-plus-fold episode exclusions, the v6 union rational
  distribution, and the final local-and-selected status conjunction. Sixty-
  seven focused integration tests, the full suite with three expected skips,
  Ruff, strict mypy, build, and independent adversarial review pass. Official
  inputs and all model/prediction/metric/submission operations remain zero.
- Alternatives: Count pairs, directions, repeats, endpoints, or stress episodes
  as families; use pair-specific class IDs as frequency keys; pool held-out
  folds into training support; or combine arithmetic with publication before
  review.
- Reversal condition: Any availability, fold, family-deduplication, directional
  frequency, held-out exclusion, rational, threshold, determinism, or firewall
  defect revokes this slice and keeps official R4 inputs closed.

## D-060 — Accept pure synthetic R4 result serialization

- Date: 2026-08-20
- Status: accepted implementation slice;
  `R4_TRANSFORMATION_SERIALIZATION_SYNTHETIC_ACCEPTED`
- Decision: Accept deterministic in-memory serialization of the frozen
  `episode_transformations.csv` and `transformation_coverage.json` schemas over
  the accepted geometry and support facts. Keep production receipts, manifests,
  filesystem publication, official inputs, and every model outside this
  milestone.
- Evidence: The serializer and focused-test SHA-256 values are
  `460678f949267d8f711a833008f287750a8b63b89e729afdbc8913ce70b21e28`
  and
  `558e6270e1349483b6a7cb0a167b90377d0a83f1a903e918fb89b904802bdc0c`.
  It emits the exact 25-column episode schema in episode/query order, joins
  fold-safe exact/class family support, preserves invalid sentinels, and emits
  the complete v5 aggregate schema with the v6 union-distribution invariant,
  exact frequency units, zero accounting, and status-conditioned authority.
  Twenty-nine focused integration tests, the full suite with three expected
  skips, Ruff, strict mypy, canonical-byte checks, and independent scientific
  review pass. Official inputs, models, predictions, metrics, submissions, and
  publication operations remain zero.
- Alternatives: Serialize ad hoc dictionaries in the production runner; mix
  manifest and filesystem authority into the scientific byte compiler; expose
  selector or endpoint availability in episode rows; or defer invalid-sentinel
  validation until the official run.
- Reversal condition: Any schema, ordering, support-join, sentinel, canonical
  byte, firewall, accounting, or authority defect revokes this slice and keeps
  official R4 inputs closed.

## D-061 — Accept synthetic R4 atomic publication

- Date: 2026-08-20
- Status: accepted implementation slice;
  `R4_TRANSFORMATION_PUBLICATION_SYNTHETIC_ACCEPTED`
- Decision: Accept the pure manifest, receipt, and atomic-terminal publisher
  over accepted typed R4 inputs. Keep official source authentication and the
  one-run orchestration boundary outside this milestone.
- Evidence: The publisher and focused-test SHA-256 values are
  `7f52bfbc06aa5f721d2d5493c03db3b3982e07946bc4817a412345644d9de3fa`
  and
  `02ea68c76ca79ab616ed8fa6f9a1ef9d8639bdd08bb3f035bf58c31799ba7294`.
  The publisher regenerates exact payloads from typed geometry and independently
  recomputed support, validates exact input/source receipt shapes, binds staged
  bytes to output receipts, and publishes either four success files or one
  failure receipt through read-only Linux no-replace promotion. Eleven focused
  tests, the full suite with three expected skips, Ruff, strict mypy, and
  independent adversarial review pass after rejecting malformed nested payloads,
  stale late-stage receipts, forged inputs, extra failure files, fabricated
  supported status, and destination races. Official inputs and all scientific
  or leaderboard operations remain zero.
- Alternatives: Trust arbitrary caller bytes; validate only headers and
  top-level JSON keys; copy untyped upstream receipts; allow ordinary rename;
  or combine publication with official-source access before atomic behavior was
  independently accepted.
- Reversal condition: Any source-causality, schema, receipt, status, authority,
  mode, file-set, cleanup, determinism, or no-replace defect revokes this slice
  and keeps official R4 inputs closed.

## D-062 — Accept the production-only R4 official runner

- Date: 2026-08-20
- Status: accepted execution boundary;
  `R4_TRANSFORMATION_OFFICIAL_RUNNER_ACCEPTED`
- Decision: Accept the thin production-only runner that binds the accepted R4
  projector, consumer, geometry, support, serializer, and publisher to the
  exact contract, R2B/R3A manifest and leaf-receipt, source, runtime, clean-
  checkout, destination, cleanup, and one-terminal rules. Keep official
  execution and every oracle/model decision outside this milestone.
- Evidence: The runner and focused-test SHA-256 values are
  `1f9180a2e0a51d36ce2563fab1c9b4eb5363a84846e47e2ca84dd514cf404bd7`
  and
  `ef57945e7f652397c45275034be5ab8159037b4a8309cb67ef74a59d210fb1e7`.
  It verifies exact accepted R2B/R3A manifests and official leaf receipts before
  access, requires the frozen Python/RDKit/Linux environment and clean complete
  checkout, and executes the private projection-to-publication path without
  exposing original sources downstream. Nine focused tests, the full suite
  with three expected skips, Ruff, strict mypy, and independent adversarial
  review pass after repairing cleanup refusal, failure-code preservation,
  post-gate drift attribution, and complete implementation-source binding.
  Official R4 inputs, models, predictions, metrics, test, TDI, submissions, and
  transduction remain zero.
- Alternatives: Manually compose the accepted slices; allow a dirty or
  partially authenticated run; publish after incomplete cleanup; collapse
  multiple failure causes; or add a resumable orchestration framework.
- Reversal condition: Any pre-input ordering, receipt, runtime, checkout, path,
  cardinality, cleanup, failure-code, private-capability, or one-terminal defect
  revokes runner acceptance and forbids the official coverage run.

## D-063 — Preserve the failed first R4 coverage attempt

- Date: 2026-08-20
- Status: failed; `R4_TRANSFORMATION_COVERAGE_FAILED`
- Decision: Preserve the exact one-file failure terminal and revoke D-054's
  extractor implementation evidence plus D-062's runner execution authority.
  Do not interpret the attempt as supported or underpowered, and do not modify
  or replace its terminal. Permit only a narrow synthetic repair implementing
  the already-frozen rule that an unrepresentable crossing-bond stereo state is
  a rejected embedding, not a terminal exception.
- Evidence: The failure-receipt SHA-256 is
  `1d232bc43f6410b89f28fcb56cb723dfcdb508c3d09a19d2c17cc45a13b5d386`.
  It records commit `c41895c...`, Linux x86_64 CPU, Python 3.12.3, RDKit
  2026.03.5, status `R4_TRANSFORMATION_COVERAGE_FAILED`, and code `V4`.
  RDKit raised `bgnIdx not connected to begin atom of bond` during ordinary MMP
  variable reconstruction. A synthetic `CC/C=C/CC` witness reproduces the same
  exception when an attachment-dummy substitution cannot retain both stereo-
  atom references. Accounting is zero for numeric target magnitudes, blinded
  test, TDI, fits, predictions, metrics, scorer calls, submissions, and
  transduction. No success artifact or support fact exists.
- Alternatives: Call the warnings normal and report underpowered; suppress all
  RDKit errors; patch the immutable terminal; retry under the accepted source
  receipt; or abandon the contract-mandated candidate rejection.
- Reversal condition: None for the historical failure. A later experiment may
  proceed only from a new reviewed source receipt after synthetic regression,
  full validation, receipt rebinding, and an explicit determination that the
  new run cannot tune against a scientific result that this failure never
  produced.

## D-064 — Reaccept the contract-faithful R4 stereo-embedding repair

- Date: 2026-08-20
- Status: accepted repaired execution boundary;
  `R4_TRANSFORMATION_REPAIRED_RUNNER_ACCEPTED`
- Decision: Preserve D-063 and the failed attempt unchanged. Reaccept the MMP
  extractor and production runner under new exact source receipts after
  implementing only v5's predeclared variable-reconstruction rule: preserve
  source bond endpoint order during dummy substitution and reject an embedding
  when its remapped stereo references cannot remain adjacent to the matching
  rebuilt endpoints. Authorize one repaired execution against identical inputs
  and runtime at a fresh destination.
- Evidence: Repaired MMP source, focused-test, and runner SHA-256 values are
  `43fe5ff18ecf2f355f1dead9e8a8393cba2e384ee44ef3293f14773c2e956c43`,
  `0a78fefae2c9d557d329e16cf39c03fcd764ba3586f72066bff039c4e996af89`,
  and
  `584fa98fe9cad11f038f8c54367bea25e4267c9f417a46729b858a3ce762e61d`.
  `CC/C=C/CC` now supplies two exact regression witnesses: an impossible
  crossing-stereo embedding returns no candidate, while a representable
  crossing retains `CC/C=C/[*:1]`. Focused extraction/runner tests, the full
  suite with three expected skips, Ruff, strict mypy, diff checks, and
  independent Sol scientific review pass. No target magnitude, coverage fact,
  prediction, metric, or model outcome informed the repair.
- Alternatives: Suppress the exception broadly; reorder stereo references;
  change the grammar or thresholds; mutate attempt 1; treat failure as
  underpowered; or abandon R4 without implementing its frozen rejection rule.
- Reversal condition: Any endpoint-order, stereo-reference adjacency, candidate
  selection, receipt, runtime, input, or one-terminal drift revokes repaired
  execution authority. Preserve every result; do not authorize another rerun
  to improve a scientific outcome.

## D-065 — Accept the repaired official R4 coverage result

- Date: 2026-08-20
- Status: accepted official coverage result;
  `R4_TRANSFORMATION_COVERAGE_SUPPORTED`
- Decision: Accept the one authorized repaired R4 terminal at
  `/home/zbos/cypshift-private/openadmet-r4/coverage-terminal-repaired/` as
  the exact successor to D-064's execution authority while preserving D-063's
  failed terminal unchanged. Grant geometry/coverage authority and permission
  to freeze a separate CYP3A4 oracle-anchor contract only. Continue denying
  model-fit, prediction, metric, official-score, submission, TDI, test-access,
  and transductive authority.
- Evidence: The repaired terminal manifest and aggregate coverage SHA-256
  values are `8166a89aee5137228a31085e21d36d6f0bf4a28d833cdc7bd1280feff4170043`
  and
  `b134d11c96526c8c3ed282cebfacaae25ce9bf49c324bfe28d8c4f1d4913a84e`.
  Terminal output hashes are `8afc1b82...` for
  `episode_transformations.csv`, `5eadb743...` for
  `transformation_pairs.csv`, and `b134d11c...` for
  `transformation_coverage.json`; all four files are read-only. A terminal
  receipt audit found zero hash or row-count mismatches. The run used commit
  `cdba779...` on CPU with Python 3.12.3 and RDKit 2026.03.5. CYP3A4 retains
  384/473 valid local transformations across 86 independent families, every
  one of the 15 local fold cells clears the frozen 20-pair/5-family minima,
  selected-anchor coverage retains 738/903 rows across 118 families with every
  cell passing, and the union contains 458 valid transformations across 564
  unique structural pairs. No model fit, prediction, metric evaluation,
  scorer call, submission, TDI row, or test access occurred.
- Alternatives: Rerun again; relax support thresholds; reinterpret the failed
  terminal; claim TRACE predictive success already; jump directly to inferred
  anchors; or widen scope to TDI before direct TRACE is frozen.
- Reversal condition: Any source-receipt mismatch, terminal-integrity drift,
  unauthorized authority expansion, or result-driven contract change revokes
  D-065 and preserves both R4 terminals as the complete evidence record.

## D-066 — Freeze the CYP3A4 oracle-anchor TRACE experiment

- Date: 2026-08-20
- Status: accepted contract; `R5_ORACLE_CONTRACT_FROZEN`
- Decision: Freeze one CYP3A4-only `ANCHOR_EXPANSION_HOLDOUT` experiment that
  asks whether the true selected campaign anchor and its measured CYP3A4 point
  let a compact transformation hierarchy beat the episode-specific inherited
  MapLight global expert. Retain the complete required control set and hard
  `NO_SIGNAL` stopping rule. Authorize implementation and synthetic firewall
  validation only; do not open numeric official targets or fit until that
  implementation receives a separate reviewed execution gate.
- Evidence: The contract and focused-test SHA-256 values are
  `c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf`
  and
  `e5bc2144ce3f9ffffd4a66f0ef3fc133cca8c1dc4341e8f43e91fb8f4f16322c`.
  Eleven focused tests and independent Sol review pass. TRACE reuses the
  generic signed-Morgan pair representation and adds only cut/fraction/class
  features plus a family-shrunk class/exact/environment hierarchy. The
  no-measured-anchor-potency control receives only delta targets and pure R3
  outer/inner MapLight OOF anchor predictions. All models predict a fixed
  public superset before sealed scorers apply selector/query masks. Label-safe
  replay proves outer minima of 64 families/296 pairs and inner minima of 43
  families/199 pairs; frozen gates are 50/200 and 40/150 respectively. The
  contract binds disjoint capabilities, exact runtimes, nested selection,
  wrong/shuffled anchors, shuffled grammar, paired component bootstraps,
  influence checks, fixed 0.5 safety fusion, status-specific terminals, and
  zero test/TDI/official-metric/submission/transduction operations.
- Alternatives: Fit before contract review; compare against a pure-family
  global model that ignores the permitted anchor; give TRACE a weaker pair
  representation than its generic control; use measured completion in the
  no-potency control; shuffle held-out anchor labels; tune from outer results;
  build inferred-anchor or learned-gate machinery before the oracle signal is
  known; or widen to TDI.
- Reversal condition: Any parent/source/runtime receipt drift, query-membership
  leak, non-anchor family label exposure, C3 measured-potency capability,
  current-training-partition violation, support arithmetic defect, outcome-
  driven threshold/model change, or test/TDI/official-metric access revokes
  D-066. `R5_ORACLE_NO_SIGNAL` or `R5_ORACLE_UNDERPOWERED` permanently stops
  inferred-anchor and learned-competence work on the critical path.

## D-067 — Accept the R5B trusted source and capability firewall

- Date: 2026-08-20
- Status: accepted synthetic implementation; `R5B_CAPABILITY_SPLITTER_SYNTHETIC_ACCEPTED`
- Decision: Accept the additive v2 clarification that makes random-anchor
  stress outer-diagnostic-only, plus the trusted synthetic parent compiler and
  manifest-bound capability splitter. Authorize implementation of model cells,
  sealed scorers, and a synthetic runner only. Do not open official numeric
  targets or claim TRACE performance yet.
- Evidence: V2 is the single absent-member addition to v1 at SHA-256
  `bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623`.
  The accepted path authenticates all synthetic parent bytes before parsing,
  derives complete current-training points and exact two-direction deltas with
  `1/(2P)` family weights, binds pure outer/inner MapLight OOF anchor states,
  and publishes 226 disjoint read-only capability roots. C3 receives no
  measured potency. Selected episodes alone enter inner selection; selected
  plus deterministic-random-anchor episodes enter outer diagnostics. Sixty-
  eight focused tests, the full suite with three expected skips, Ruff,
  formatting, strict typing, compiler-to-splitter replay, and independent Sol
  adversarial review pass. Test, TDI, official-metric, submission,
  transductive, fit, prediction, and metric counts remain zero.
- Alternatives: Let cells read one shared target/truth root; accept caller-
  supplied prepared CSVs without parent manifests; omit stress diagnostics;
  permit stress to influence tuning; serialize approximate family weights;
  use measured anchor completion for C3; or open official targets before the
  model/scorer runner is synthetically accepted.
- Reversal condition: Any parent/leaf receipt drift, source-manifest forgery,
  molecule/family fold crossing, feature-row misalignment, R4 direction drift,
  asymmetric delta or weight defect, measured-potency access by C3, stress
  influence on primary selection/status, sealed-truth exposure, non-atomic
  publication, or test/TDI/official-metric access revokes D-067.

## D-068 — Accept the pure R5C model and sealed-statistics kernels

- Date: 2026-08-20
- Status: accepted pure synthetic implementation; no execution authority
- Decision: Accept the deterministic R5C model and scoring/statistics kernels
  as the exact mathematical core of the frozen oracle experiment. Authorize
  capability-isolated cell, freezer, locked-G0, terminal, and synthetic-runner
  implementation only. Do not open official numeric targets or claim TRACE
  performance until that complete execution boundary passes independently.
- Evidence: The model, scoring, and statistics source SHA-256 values are
  `38db4229df25c5e6e36712b3362fd5674cddb84160a7d992d74bd3bdc9f5c39a`,
  `dc4db3b78ba7320085bfc5ad056f03935416825af509e2ba2db40d69b115b24f`,
  and `07a42579b5da4e55d4954489f0d5614054befb6dfdf31b05bf94ec7fe5e50e3e`.
  Thirty-three focused tests and the full suite with three expected skips pass,
  as do Ruff, formatting, strict typing, diff checks, and repeated independent
  Sol review. Adversarial witnesses cover feature nesting, hierarchy
  recursion, C3 potency isolation, role-safe F2, fail-closed predictions,
  reversal, exact joins and weights, one shared masked component bootstrap,
  local-control availability, stress isolation, inner grids, influence,
  safety, and status precedence. Both signed implementation commits preserve
  zero filesystem or challenge-data access in these pure modules.
- Alternatives: Combine all scoring and resampling into one oversized module;
  use independent local-control bootstraps; silently fall back on model defects;
  allow measured potency into C3; shuffle continuous F2 features; or proceed to
  official fitting before capability-isolated synthetic execution passes.
- Reversal condition: Any feature-order, hierarchy-parent, control-role,
  prediction-fallback, population, join, aggregation, bootstrap-multiplicity,
  stress, safety, evidence-cardinality, determinism, or authority drift revokes
  D-068 and blocks official R5 execution.

## D-069 — Accept the first R5C execution foundations

- Date: 2026-08-20
- Status: accepted synthetic implementation foundations; no official execution
  or predictive authority
- Decision: Accept the exact cell capability loader, C0/C1/F0/F1 controls,
  locked one-episode MapLight G0 subprocess, algebraically equivalent row-space
  ridge, and additive R5 v3 execution-mechanics overlay. Authorize fresh
  pair-system cell, immutable prediction-fragment, freezer, scorer-terminal,
  and deterministic synthetic-runner implementation only. Do not open official
  numeric oracle targets or claim TRACE uplift yet.
- Evidence: The cell I/O and validation SHA-256 values are
  `a4e1567f00d73037492659ea02090cc8554fbe28629374de8a97b69e8780062c`
  and `1aa2130280b0326fc943dfcaad0d341e186cb25048d2f5789825e10bed77ec8b`;
  all 75 measured and 75 C3 scopes replay and independent audit closes the
  receipt, TOCTOU, fold, pair, episode, OOF, feature-alignment, and C3-potency
  firewalls. The control source is `8bce9b92...`; independent witnesses cover
  top-64 truncation, reversed direction, deterministic PCG64 selection, frozen
  T0 reuse, and explicit G0 fallback. The G0 I/O and runner hashes are
  `5e35fd20...` and `9ed74e57...`; two real locked Python 3.10.13,
  NumPy 1.25.2, CatBoost 1.2.1 runs with 101 nonconstant fit rows are
  byte-identical. The row-space ridge source is `9ac284ef...`; 100 adversarial
  cases match the frozen primal/sklearn predictions within `2.3e-10`, and an
  800-by-4,100 fit uses an 800-by-800 solve in about 1.5 seconds. The v3 overlay
  and canonical resolved-contract SHA-256 values are
  `275f1425d1a93805cb7d5b7dc1b63c67d6f02476eab9f77798cac6cc625a3d55`
  and `9143ecd1b24d1d9a97b1e5821e2b953f4cfffcec1cc39de3a8c49b81a4f58a50`;
  it changes only execution mechanics and passes repeated independent review.
- Alternatives: Let each model inspect shared target roots; serialize T0 model
  state across capabilities; give C3 measured potency; accept molecule-only F0
  seeds; run feature-square ridge systems hundreds of times; omit wrong-anchor
  controls; or open official targets before the full runner is synthetically
  accepted.
- Reversal condition: Any source/manifest receipt drift, widened cell
  capability, measured-potency access by C3, family or episode leakage, G0
  runtime/parameter drift, control-causality defect, numerical-equivalence
  failure, execution-overlay contradiction, or non-atomic publication revokes
  D-069 and blocks pair-cell or official execution.

## D-070 — Accept authenticated R5C pair-system prediction fragments

- Date: 2026-08-20
- Status: accepted synthetic implementation; no official execution or
  predictive authority
- Decision: Accept fresh pair-system execution and immutable prediction
  fragments for every frozen learned model, ablation, wrong/shuffled-anchor
  control, shuffled-grammar control, and locked MapLight fallback. Authorize
  sealed inner selection, freezer, terminal, and deterministic synthetic-runner
  implementation only. Do not open official oracle targets or claim TRACE
  uplift.
- Evidence: The accepted pair runner, pair engine, and pair I/O SHA-256 values
  are `01496d7015efd02541b0eff89faf89c9960b55c4953ed66d2dc962906453d88c`,
  `6c31224d3e83ed24d01bf2668dfcb49af981d981ae57ba667dd4ca52507bfc8b`,
  and `d206f5d7af40aa21455173510728812993b82876722db5a6f6c8f083e3fd7e4e`.
  Fifty-nine focused tests and eleven direct publication attacks pass; all 27
  transitive scientific-source mutations change the bound source receipt. A
  real locked CatBoost G0 fragment passes strict authentication into pair
  publication, shared T0/F0/F1 parses targets once and fits T0 once, F2 performs
  a nonidentity multi-pair shuffle and clears a programmatic 200-pair/50-family
  gate, and C3 remains physically isolated from measured potency. The full
  suite passes 728 tests with three expected skips; Ruff, formatting, strict
  typing, diff checks, and independent read-only review pass. Signed forward-
  repair commit `54b05087...` supersedes the rejected pre-acceptance bytes in
  `59f90ed1...`; the latter was pushed before its assigned no-push review
  boundary and remains preserved rather than rewritten.
- Alternatives: Trust caller-assembled capability records; let score-free
  tokens or G0 bindings self-authenticate; fit F0/F1 independently; leave
  scientific helper modules outside source causality; accept all-zero operation
  accounting; or proceed directly to official fitting.
- Reversal condition: Any raw-root receipt, source bundle, runtime, candidate,
  cell, fragment, token, G0, accounting, stage, family, C3-potency, control,
  no-overwrite, or deterministic-replay drift revokes D-070 and blocks sealed
  scoring or official execution.

## D-071 — Accept sealed four-fold TRACE inner selection

- Date: 2026-08-21
- Status: accepted synthetic implementation; no official execution or
  predictive authority
- Decision: Accept the sealed-only v3 eligibility migration, authenticated
  four-fold inner scorer, and 90 physically isolated score-free token
  capabilities. Authorize final prediction freezing, outer sealed scoring,
  terminal publication, and deterministic synthetic-runner implementation
  only. Do not open official oracle targets or claim TRACE uplift.
- Evidence: Commit `8453cb9f...` authenticates 960 immutable candidate
  fragments and 60 inner sealed roots, produces exactly 240 aggregate candidate
  rows, and selects one token for each of six learned systems in every one of
  15 outer contexts. The private I/O, inner I/O, sealed migration, and inner
  scorer SHA-256 values are `34b6f7605f641c56a77d6d9ddee73ade2394fdf1942156a36cf47ea624b02491`,
  `d8ecfca7fd61037d14523b1e98e8f57d0a3fad710db992e1b1521f864d39632c`,
  `64ecc651824422182ba88ee248c255505dbef1a9a2b8c7cdebeab57ac4d44766`,
  and `3779cd29b714e6bbab384a69cc5ab8519a65ea5da5f559c2832d468cbdca9ee3`.
  The repaired pair-engine and pair-I/O hashes are `5d101d04...` and
  `a699228a...`; they supersede D-070's result-affecting source receipts after a
  real nested run found that fragments serialized public episode fold metadata
  instead of authenticated current-cell scope. The new D-070 runner bundle is
  `7a39b71e5c78992c6a16224da1a94cb0ff298d1ba14e1ffaddcdb05b22510c0f`;
  the current scorer bundle is
  `714a888eda98814630cb08c133b26f9041968b03d364b992dd40fb80d6599a9c`.
  Real authenticated C2, C3, T0, A0, A1, and A2 inner paths pass; all 33
  bound-source mutations and fake source receipts fail before private input;
  exact 14-field accounting rejects plus/minus-one poisons; token ancestry
  contains no score evidence. Ninety focused tests and the full suite with 735
  passes and three expected skips pass, as do Ruff, formatting, strict typing,
  diff checks, and independent review.
- Alternatives: Expose loss-bearing selection evidence to model processes;
  place all tokens beneath the score root; trust self-declared source or
  accounting receipts; parse truth once per hyperparameter candidate; retain
  the incorrect nested-fold serialization; or proceed directly to official
  fitting.
- Reversal condition: Any sealed eligibility, truth-open accounting, source or
  runtime closure, candidate accounting, four-fold join, tie-break, selected-
  only population, token field, score-isolation, nested-scope, filesystem,
  no-overwrite, or deterministic-byte drift revokes D-071 and blocks final
  freezing, scoring, or official execution.

## D-072 — Accept the authenticated TRACE outer prediction freeze

- Date: 2026-08-21
- Status: accepted synthetic implementation; no official execution or
  predictive authority
- Decision: Accept the truth-free final outer prediction freezer for all 12
  frozen systems and 15 outer contexts. Authorize outer sealed scoring,
  status-specific terminal publication, and deterministic synthetic-runner
  implementation only. Do not open official oracle targets or claim TRACE
  uplift.
- Evidence: Signed commit `15ae153...` authenticates 90 score-free tokens, 165
  pair fragments, 30 locked G0 fragments, and 15 sealed eligibility roots,
  producing 12 canonical system files with 360 unique synthetic predictions and
  30 merged eligibility rows. Only the freezer owns
  `predictions_frozen=360`; every child remains zero, and no truth or cliff file
  is opened. Freezer assembly, locked-G0 validation, general I/O, and closed
  publication SHA-256 values are `773d4f49...`, `50b4ce21...`, `c46200eb...`,
  and `116a5e57...`. The exact 14-file package is independently revalidated
  before no-replace promotion. Arbitrary, forged-manifest, extra-file, and
  missing-file publication attacks create no destination. Sixteen focused
  tests and the full suite with 751 passes and three expected skips pass, as do
  Ruff, formatting, strict typing, diff checks, deterministic two-root replay,
  and independent review.
- Alternatives: Let the freezer open truth; trust caller-assembled bytes;
  silently deduplicate rows; mix selected and stress populations; accept
  metadata or fallback drift; count frozen predictions in child cells; or send
  model fragments directly to the scorer without one immutable freeze.
- Reversal condition: Any system vocabulary, context, token, fragment, G0,
  source, runtime, accounting, fixed-superset, metadata, fallback, eligibility,
  row-key, finite-value, exact-file-set, publication, or deterministic-byte
  drift revokes D-072 and blocks outer scoring or official execution.

## D-073 — Accept sealed TRACE scoring and exact terminal publication

- Date: 2026-08-21
- Status: accepted synthetic implementation; no official execution or
  predictive authority
- Decision: Accept the sealed outer scorer, all frozen evidence calculations,
  status resolver, and exact status-specific terminal publisher. Authorize the
  deterministic full synthetic state-machine rehearsal only. Do not open
  official oracle targets or claim TRACE uplift.
- Evidence: Signed commit `15c2daf...` consumes only the authenticated final
  freeze, 15 outer sealed roots, accepted inner-selection evidence, label-safe
  support evidence, and receipt-bound child accounting. The outer scorer,
  terminal serializer, cleanup validator, terminal I/O, receipt producer, and
  cross-file validator hashes are `7839168a...`, `101e0866...`, `4edea190...`,
  `40a5fe40...`, `fdecec5d...`, and `51e4f7ae...`. The complete synthetic
  SIGNAL_PASS fixture contains 1,980 frozen rows, opens truth 1,125 times
  exactly, performs 3,090 unique internal absolute-error evaluations, and emits
  240 selection, 2,280 scored, 180 cell, 10 bootstrap, 10 influence, and 12
  ablation rows. NO_SIGNAL, UNDERPOWERED, and FAILED paths are independently
  exercised. Stress evidence is diagnostic-only; empty clean stress is valid
  and stress mutation cannot alter primary status. Support is reconstructed
  from authenticated label-safe hashed/fold evidence, accounting is summed by
  reopening exact child manifests, and every private capability is removed
  under an authenticated cleanup receipt before no-replace terminal promotion.
  Five focused tests and the full suite with 756 passes and three expected skips
  pass, as do Ruff, formatting, strict typing, diff checks, and independent
  adversarial review.
- Alternatives: Let the terminal invent support or accounting; accept caller-
  supplied output mappings; let stress rescue status; retain private roots
  after publication; expose target or prediction values publicly; or skip the
  deterministic state-machine rehearsal.
- Reversal condition: Any truth join, weight, metric, shared-bootstrap,
  influence, safety, stress-isolation, support, accounting, status precedence,
  public schema, authority, cleanup, file-set, receipt, source/runtime,
  no-overwrite, or deterministic-byte drift revokes D-073 and blocks official
  execution.

## D-074 — Accept the complete R5C synthetic production rehearsal

- Date: 2026-08-21
- Status: accepted synthetic execution boundary;
  `R5C_SYNTHETIC_RUNNER_ACCEPTED`; no official predictive authority
- Decision: Accept the thin R5C production-entry state machine after two fresh
  full synthetic roots execute the exact frozen process topology and publish
  byte-identical terminals. Authorize a separate official-attempt ancestry
  wrapper and dormant inferred-anchor preregistration next. Do not interpret
  the synthetic terminal status as TRACE performance, open blinded test or TDI
  data, implement inferred-anchor deployment, or create a submission.
- Evidence: Signed clean commit `4ee682a7...` produced two roots with exactly
  2,033 fresh child processes each: source/project/support once; 75 migrations;
  75 episode enumerations; 390 views and 390 locked G0 fits; 960 inner pair
  cells; one sealed selection with 240 rows and 90 isolated tokens; 120 ordinary
  plus 15 shared outer calls yielding 165 fragments; and one freezer,
  accounting, cleanup, scorer, and terminal call. All 4,066 children returned
  zero with unique positive PIDs. The exact eight-file terminals are byte-
  identical at manifest SHA-256 `6f199dfd...` and result SHA-256 `0fe7bd10...`;
  PID-normalized transcripts match at `d76499cd...`. Each root records 390
  MapLight, 795 ridge, and 795 hierarchy fits, plus 3,780 frozen predictions;
  all blinded-test, TDI, official-metric, submission, transduction, and
  inferred-anchor counters are zero. Private/control roots are absent, source
  provenance is explicitly synthetic, and final independent high-impact review
  passes. Read-only configs, transcripts, exit evidence, and terminals are
  retained outside Git under
  `/home/zbos/cypshift-private/openadmet-2026/r5c-synthetic-4ee682a7/`.
- Alternatives: Treat component tests or a fake-process topology run as full
  acceptance; discard process transcripts; use a synthetic `NO_SIGNAL` result
  as a scientific stop; point the synthetic runner at official parents; add
  concurrency or orchestration machinery before the accepted vertical slice;
  or jump directly to blinded-test inference.
- Reversal condition: Any config/source/runtime/checkout drift, process-count
  or return-code mismatch, non-deterministic terminal byte, missing transcript,
  capability leak, forbidden counter, cleanup residue, or independent audit
  failure revokes D-074 and blocks official R5D execution.

## D-075 — Accept the synthetic direct MapLight deployment boundary

- Date: 2026-08-21
- Status: accepted synthetic implementation;
  `DIRECT_MAPLIGHT_DEPLOYMENT_SYNTHETIC_ACCEPTED`; no official execution or
  publication authority
- Decision: Accept the frozen four-endpoint direct MapLight deployment
  contract, full-training runner, exact submission validator, and two-root
  no-replace acceptance command as a parallel pre-TRACE baseline slice. A
  production run may publish only a separate read-only rehearsal terminal and
  cannot write directly to the accepted destination. Any later authorized
  publication must independently authenticate and revalidate two distinct
  official rehearsal roots and require both `submission.csv` and
  `manifest.json` to match byte-for-byte before atomic no-replace promotion.
  Do not open the blinded test, fit official full-training models, generate
  official predictions, or publish an accepted submission under this decision.
- Evidence: The contract, runner, and validator SHA-256 values are
  `918fc1358e3394f32cd21b2f57b283f584e97242068fa0dc60448babc3963960`,
  `ef4102e0ba1a61c7fb8ffa48671532409909f744b7bfbff4eeb90960e15e7ace`,
  and
  `f11d83531e5b602cc088c5c7c0d0aa1bb4828e1041eaac5ae203837be48c3180`.
  The contract binds the accepted R2A observations, accepted R3A MapLight
  feature root, exact R3 parameter record, Python 3.10.13 runtime, 4,905
  aligned training rows, four endpoint fits, 750 output rows, and 3,000 finite
  predictions. Ten focused tests, 42 neighboring contract/feature tests, and
  the full 802-test collection under all declared dependency groups pass, as
  do Ruff, formatting, strict typing, exact-runtime contract loading, and
  Python 3.10 compilation. Synthetic witnesses reject a direct run to the
  accepted root, one root presented twice, an individually valid byte mismatch,
  and an existing destination. An independent high-impact audit first found
  the missing two-root acceptance gate; the repaired path passed narrow
  re-audit. Official blinded-test bytes opened, production fits, official
  predictions, metric calls, and submissions remain zero.
- Alternatives: Let one run publish directly to the accepted destination;
  compare only submission rows while ignoring manifest drift; reuse the R3C OOF
  state as a serialized deployment model; add calibration, clipping, an
  ensemble, transduction, or another model family; or begin official execution
  before synthetic acceptance and records were complete.
- Reversal condition: Any parent, feature, runtime, parameter, row-alignment,
  raw-SMILES separation, schema, finite-prediction, determinism, terminal,
  no-replace, or authority defect revokes D-075. Preserve any later rehearsal
  evidence and publish nothing; a changed receipt or submission rule requires a
  separately reviewed versioned contract before official execution.

## D-076 — Accept the official direct MapLight submission candidate

- Date: 2026-08-22
- Status: accepted local official candidate;
  `DIRECT_MAPLIGHT_OFFICIAL_CANDIDATE_ACCEPTED`; not uploaded or scored
- Decision: Accept the exact four-endpoint direct MapLight candidate after two
  independently generated official rehearsal roots revalidate and match
  byte-for-byte. Preserve the accepted two-file read-only terminal as the first
  direct submission candidate. It may be uploaded without waiting for TRACE,
  but leaderboard feedback cannot change the frozen R5D experiment, inferred-
  anchor preregistration, model family, parameters, or candidate bytes.
- Evidence: Both rehearsals used official dataset revision `85f8b358...`, test
  SHA-256 `a342f844...`, accepted R2A observations `00b1ac95...`, accepted R3A
  feature manifest `32a95095...`, frozen contract `918fc135...`, and the exact
  Python 3.10.13/NumPy 1.25.2/CatBoost 1.2.1 runtime. Each completed in 28.3
  seconds with four fits, 4,905 aligned training feature rows, 750 test feature
  rows, and 3,000 finite predictions. Both `submission.csv` files have SHA-256
  `9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`;
  both manifests have SHA-256
  `96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6`.
  The no-replace acceptor published the exact same two files under
  `/home/zbos/cypshift-private/openadmet-2026/submissions/direct-maplight-v1/accepted`
  at root mode 0555/files 0444, and the independent validator confirms exact
  six-column identity/order. Test-label, TDI, official-metric, calibration,
  clipping, ensemble, model-binary, and transductive operations are zero.
- Alternatives: Wait for TRACE before establishing a baseline; publish from a
  single run; average or otherwise alter the byte-identical rehearsals; add
  calibration, clipping, ensembling, or TDI inference; or tune after portal
  feedback.
- Reversal condition: Any input, runtime, parameter, row alignment, finite
  value, schema, receipt, determinism, validator, or publication defect revokes
  D-076. Preserve the artifact and do not upload changed bytes without a new
  reviewed decision.

## D-077 — Freeze the sole official R5D CYP3A4 oracle attempt

- Date: 2026-08-22
- Status: accepted contract and execution boundary;
  `R5D_OFFICIAL_EXECUTION_CONTRACT_FROZEN`; attempt unopened
- Decision: Freeze the smallest separate official-attempt wrapper around the
  accepted R5C state machine. Authorize exactly one training-only CYP3A4 oracle
  attempt after a dormant F1 inferred-anchor preregistration is frozen. The
  fixed outside-Git attempt root is claimed atomically only after contract,
  runtime, checkout, four parent-manifest, and 17 ordered source-leaf receipts
  pass. Retry and resume are forbidden. The wrapper must retain the complete
  process transcript, independently revalidate the status-specific terminal,
  remove private state, and publish one immutable attempt receipt without
  adding authority.
- Evidence: The contract SHA-256 is
  `f8aadef95be8e0d719a14d08bc2a1164a03d2cf5079e9ed2dec749ee048bd700`.
  It binds R2B `08dcf61c...`, R3A `32a95095...`, R3C `a2029e12...`, R4
  `8166a89a...`, official revision `85f8b358...`, exact root and G0 runtimes,
  and all 17 source receipts. Real-data preflight confirms 561 unique selected
  and 561 unique stress episodes: selected episodes occur in five contexts and
  stress episodes in one, yielding 3,366 G0/view pairs. The supported topology
  is exactly 7,985 fresh children: 960 inner pair, 120 ordinary outer, 15 shared
  outer, and the frozen source/projection/support/migration/selection/freezer/
  accounting/cleanup/scorer processes. Focused official-wrapper, runner, and
  terminal suites, Ruff, formatting, strict typing, diff checks, and a final
  high-impact boundary review pass. No R5 official outcome, test file, TDI,
  metric, submission, transductive relationship, or inferred-anchor pool was
  opened; the fixed attempt root remains absent.
- Alternatives: Point the synthetic R5C entry at official roots; omit official
  ancestry or the raw process transcript; reuse the synthetic 390-G0 count;
  retry after a late failure; add a workflow framework or concurrency layer;
  or open official R5 outcomes before preregistering I0.
- Reversal condition: Any contract, source, parent, runtime, checkout, attempt,
  process, terminal, accounting, cleanup, no-replace, or authority drift revokes
  D-077 and blocks the official attempt. Once the fixed root is claimed, any
  later failure consumes the attempt and cannot be retried or resumed.

## D-078 — Preregister the minimal F1 inferred-anchor bridge

- Date: 2026-08-22
- Status: accepted dormant contract; `I0_PREREGISTRATION_FROZEN`; no official
  R5 outcome opened and no inferred-anchor implementation authorized
- Decision: Preregister I0 as exactly the existing frozen R5 F1 control before
  opening the official R5 outcome. I0 uses the most Morgan-similar complete
  training anchor among the first at most 64 candidates with a valid accepted
  R4 transformation, applies the selected T0 delta, and otherwise falls back to
  G0 only for an honestly empty valid-anchor set. It adds no model, ranker,
  metric, competence gate, fusion, or framework. Activation requires an
  authenticated sole-attempt R5D receipt and `R5_ORACLE_SIGNAL_PASS`; any other
  authentic R5 status stops before detailed loss parsing.
- Evidence: The preregistration SHA-256 is
  `05924fb3a8a7e8e4d28a1ee11d6fe725af273ee3c6340062f9f25af57ded8d7c`.
  It binds the resolved R5 contract `9143ecd1...` and official execution
  contract `f8aadef9...` before any evidence row. After activation only, a
  future sealed reducer may use aligned published G0/F1 primary absolute-error
  rows and the 15 selected T0 coordinates. Both full-population and local-only
  G0-minus-F1 95% bootstrap lower bounds must be positive under one shared
  2,000-replicate PCG64 draw; at least 12/15 cells and 3/5 per repeat must be
  positive; all ten top-component leave-one-out contrasts must remain positive;
  and F1 must retain at least 30 components and 50 base rows. The full-training
  T0 coordinate is the mode of the 15 selected coordinates with the frozen
  larger-alpha/larger-lambda tie-break. Twenty-seven inherited and focused
  contract tests, Ruff, formatting, and diff checks pass. All target, fit,
  prediction, test, TDI, metric, submission, transductive, and candidate-pool
  counters remain zero.
- Alternatives: Put TRACE deployment behind a new learned anchor ranker; tune a
  threshold from the R5 result; compare only locally available rows; use an
  independent local bootstrap; reuse raw R2 episode membership; let leaderboard
  feedback rescue I0; or build inferred anchors before oracle evidence.
- Reversal condition: Any parent/envelope/terminal mismatch, target or raw-
  episode access, row misalignment, fallback mismatch, non-shared bootstrap,
  support/cell/influence drift, outcome-driven threshold change, test-test
  relation, or new model component revokes D-078. A clean gate miss permanently
  removes I0 from the critical path for this challenge version.

## D-079 — Preserve the consumed R5D pre-fit failure and block implicit retry

- Date: 2026-08-22
- Status: accepted negative execution record; `R5D_OFFICIAL_PREFIT_FAILED`;
  no official TRACE evidence
- Decision: Preserve the sole D-077 attempt exactly as published and do not
  retry, resume, replace, delete, or reinterpret it under the existing
  contract. The signed clean worktree passed the wrapper's contract, runtime,
  checkout, parent-manifest, and 17 source-receipt gates, atomically claimed
  the fixed attempt root, and then the accepted runner rejected its missing
  checkout-local root and MapLight Python executables. The wrapper published
  one authenticated `R5_ORACLE_FAILED` terminal and receipt. Because D-077
  explicitly makes any post-claim failure terminal, any replacement requires a
  new explicit reviewed decision; user intent to continue TRACE does not by
  itself rewrite the frozen one-attempt boundary.
- Evidence: Attempt claim SHA-256 `331c93eb...`; failure terminal SHA-256
  `79d73d85...`; official attempt receipt SHA-256 `2c1f0c59...`. The receipt
  contains exactly two zero-exit cleanup/failure children and zero for all 14
  operation counters, including target parsing, MapLight/ridge/hierarchy fits,
  frozen predictions, truth opens, internal error evaluations, blinded-test
  access, TDI access, official metrics, submissions, transduction, and inferred-
  anchor pools. Read-only diagnosis reproduced only
  `model executable differs`: the clean worktree had neither `.venv/bin/python`
  nor `research/maplight-fixed/.venv/bin/python`; checkout, runtime, source
  bundles, and source hashes independently passed. No official predictive
  outcome was produced or inspected.
- Alternatives: Quietly install the missing environments and rerun under
  D-077; delete or rename the consumed root; treat wrapper-level runtime parity
  as equivalent to the runner's checkout-local executable requirement; or
  claim that zero scientific work makes the frozen retry prohibition void.
- Reversal condition: None for the historical failed artifact. A separately
  reviewed recovery contract may supersede only future execution authority if
  it binds this exact receipt, proves the failure was pre-fit with all
  scientific counters zero, and moves checkout-local executable verification
  before claiming any new fixed root.

## D-080 — Authorize one zero-operation R5D pre-fit recovery

- Date: 2026-08-22
- Status: accepted recovery boundary;
  `R5D_OFFICIAL_PREFIT_RECOVERY_FROZEN`; replacement attempt unopened
- Decision: Preserve D-079 permanently and authorize exactly one separately
  named R5D replacement attempt. This is not a retry or resume of the consumed
  root. It is permitted only because the independently reopened D-079 claim,
  terminal, and receipt prove a pre-gate `RUNTIME` failure with exactly two
  successful cleanup/failure children, all 14 operation counters zero, and all
  authority false. Before creating the replacement root, the wrapper must
  verify both pinned checkout-local Python executables and that its own
  interpreter resolves to the root environment. The complete D-077 science,
  official parents, 17 source leaves, runtime versions, 7,985-child topology,
  statistics, thresholds, cleanup, forbidden operations, and no-retry/no-resume
  rule remain unchanged. User direction to continue TRACE after the explicit
  failure explanation supplies authority for this one reviewed replacement,
  not for further attempts.
- Evidence: Recovery contract SHA-256 `0934e66a...` binds the original contract
  `f8aadef9...`, claim `331c93eb...`, failure `79d73d85...`, and receipt
  `2c1f0c59...`, plus the new fixed outside-Git recovery root. The dormant I0
  overlay SHA-256 `37982400...` inherits every v1 scientific and hard-stop rule
  and changes only the eligible official-attempt parent. A clean detached
  execution checkout provisioned with root Python 3.12.3 and locked MapLight
  Python 3.10.13 passes the exact runner pre-gate. Contract, wrapper,
  zero-operation-parent, missing-environment, and unchanged-I0 tests pass. No
  official source value, model fit, prediction, truth, metric, test file, TDI,
  submission, transductive relation, or inferred-anchor pool was opened while
  freezing this recovery.
- Alternatives: Quietly reuse D-077; edit or delete the failed root; relax the
  inner executable check; claim before provisioning environments; change TRACE
  science; or abandon TRACE after a non-scientific launch failure.
- Reversal condition: Any failed-parent mismatch, nonzero prior operation,
  missing executable, source/runtime/science drift, second replacement,
  retry/resume, incomplete process transcript, private residue, or forbidden
  operation revokes D-080. A failure after the replacement claim is terminal
  and authorizes no further attempt.

## D-081 — Preserve the interrupted R5D recovery and authorize one fresh crash replacement

- Date: 2026-08-22
- Status: accepted crash-replacement boundary;
  `R5D_OFFICIAL_CRASH_REPLACEMENT_FROZEN`; replacement unopened
- Decision: Preserve the D-080 recovery root exactly and never resume, delete,
  post-hoc complete, or use it as execution input. Authorize one separately
  named fresh run from the beginning solely because an external Codex process
  loss killed the accepted parent process without a child failure or terminal.
  The replacement inherits every D-077/D-080 source, parent, runtime, model,
  feature, candidate, fold, statistic, threshold, seed, 7,985-child topology,
  cleanup, forbidden-operation, and authority rule. Run it detached from Codex
  and retain durable stdout/stderr. A further interruption or failure is final.
- Evidence: The interrupted root claim SHA-256 is `be22a0d9...`. Its canonical
  15,907-entry inventory (5,607 directories and 10,300 files) is
  `e948f775...`. It contains 3,366 G0 manifests, 960 inner-candidate manifests,
  the exact 240-row inner selection, 90 isolated tokens, and 73 outer-fragment
  manifests. Terminal, receipt, freezer, aggregate-accounting, and cleanup
  roots are absent. The v3 execution overlay SHA-256 is `ee135e7f...`; the
  dormant I0 v3 overlay is `9a636ad8...` and changes only the eligible attempt
  parent. Focused contract/wrapper tests and an exact local inventory reopen
  pass before execution.
- Alternatives: Resume the partial tree; infer or fabricate the lost process
  transcript; publish a post-hoc failure; delete the consumed root; reuse its
  selected tokens; change TRACE science; or abandon TRACE after an external
  application failure.
- Reversal condition: Any interrupted-root byte, artifact count, source,
  parent, runtime, checkout, model, statistic, threshold, seed, process-log,
  terminal, cleanup, forbidden-operation, or authority drift revokes D-081.
  The historical interrupted root remains immutable regardless of outcome.

## D-082 — Accept official R5D NO_SIGNAL and stop inferred-anchor TRACE

- Date: 2026-08-23
- Status: accepted negative official evidence; `R5D_OFFICIAL_NO_SIGNAL`;
  `I0_DEPLOYMENT_NO_SIGNAL`; no TRACE submission authority
- Decision: Accept the exact crash-replacement terminal as the sole official
  training-only CYP3A4 oracle result. It is a clean scientific `NO_SIGNAL`, not
  an execution or support failure. Permanently stop I0/F1 and all inferred-
  anchor TRACE deployment for this challenge version under the preregistered
  nonpass rule. Do not rerun R5D, tune from the result, add a rescue gate/model,
  or let leaderboard feedback reactivate TRACE. Preserve the immutable direct
  MapLight candidate as the only authorized direct submission for manual
  upload.
- Evidence: Signed source commit `ee189abe...`; v3 execution contract
  `ee135e7f...`; claim `0036a70e...`; official receipt `a5e61aaa...`; terminal
  manifest `dd93d2f...`; oracle result `4b06a96a...`; durable wrapper log
  `ffa36aaf...`. Independent reopening passed the four official parents, 17
  source leaves, exact locked runtimes, all terminal receipts, and the complete
  7,985-child transcript with zero nonzero exits. G0 component-macro MAE was
  0.4327 versus 0.7159 for T0; G0-minus-T0 was -0.2832 with 95% interval
  [-0.3983, -0.1674], and only 1/15 cells favored T0. Required bootstrap,
  cell-direction, top-ten influence, and safety-upper-bound gates failed while
  all support gates passed. The final root is read-only and contains only the
  claim, receipt, and exact eight-file terminal; private/control roots are
  absent. Blinded-test, TDI, official-metric, submission, transductive, and
  inferred-anchor-pool counters are all zero. The exact accepted MapLight CSV
  `9d3ed5ff...` was rechecked with the pinned competition validator
  `276a53d7...`: 750 exact IDs and SMILES in order, six exact columns, 3,000
  finite predictions, valid true, zero errors.
- Alternatives: Treat `NO_SIGNAL` as permission to inspect the test set or tune
  an inferred-anchor threshold; deploy F1 despite the required `SIGNAL_PASS`;
  rerun with a changed split/control/model; blend TRACE into MapLight; or delay
  the already validated baseline upload.
- Reversal condition: None for the historical official result. A future
  challenge version may preregister a materially new hypothesis before opening
  its outcomes, but this challenge's R5D and I0 decisions remain terminal.

## D-083 — Publish the training-only R5D audit terminal

- Date: 2026-08-23
- Status: accepted public validation evidence; no prediction or submission
  authority
- Decision: Publish the exact R5D crash-replacement attempt claim, official
  receipt, and eight-file terminal in the repository as a bounded
  training-validation audit bundle. The bundle may expose public training
  molecule identifiers, held-out absolute errors, validation metadata,
  aggregate metrics, hyperparameter selections, process records, and immutable
  receipts. It must not contain blinded-test access or predictions, submission
  values, raw model predictions, raw target values, or SMILES. Preserve D-082's
  permanent TRACE deployment stop and the separately stored direct MapLight
  submission bytes.
- Evidence: OpenADMET publishes the source dataset under Apache-2.0. The copied
  claim, receipt, terminal manifest, and result retain SHA-256 values
  `0036a70e...`, `a5e61aaa...`, `dd93d2f...`, and `4b06a96a...`. The public
  verification test checks the exact terminal receipts, all 7,985 contiguous
  zero-exit process records and verb counts, zero values for all six forbidden
  counters, exact denied authority for test/prediction/submission/TDI/
  transduction, absence of raw prediction/target/SMILES columns, and complete
  deterministic terminal revalidation. An independent membership check found
  all 243 published query identifiers in the pinned 4,905-molecule training
  projection and zero in the pinned 750-molecule blinded-test set.
- Alternatives: Require every external reviewer to repeat the 19.55-hour model
  run; publish only aggregate prose; publish private intermediate model roots;
  publish the direct submission; or publish raw source labels and predictions.
- Reversal condition: Any digest mismatch, raw prediction/target/SMILES field,
  blinded-test or submission value, nonzero forbidden counter, expanded
  authority, source-license incompatibility, or failure of the independent
  terminal validator revokes the public bundle and requires immediate removal.

## D-084 — Adopt the Global-v2 audit mandate

- Date: 2026-08-24
- Status: accepted Phase 2 strategy; no Phase 2 scientific execution authority
- Decision: Adopt the externally supplied 2026-08-24 OpenADMET audit as the
  strategic mandate for Phase 2. Preserve its exact source bytes and reconcile
  them into one active repository phase. Build a family-safe heterogeneous
  global ensemble first, then evaluate masked multitask learning and
  provenance-controlled external transfer. Retain complexity only after a
  preregistered ablation. Keep leaderboard evidence outside model selection.
- Evidence: The imported audit has SHA-256
  `88cfcb717e1ac21a40300e78d73ff3caa3387a41933cb15893ba40831472f79e`
  and starts from repository commit `8da243e...`. Its independent reductions
  match D-082's accepted negative result and identify concrete limitations in
  the current single-seed, single-learner MapLight deployment. On the current
  checkout, all ten files in the public R5D audit bundle pass `sha256sum -c`
  and the focused public-bundle pytest passes, closing the audit's two declared
  local verification gaps. Recommendations are mandate; factual claims still
  require repository contracts, receipts, execution, and review before they
  become evidence.
- Alternatives: Upload only the existing baseline and stop research; revive
  R5D directly; implement all proposed models without staged falsification; or
  build a general orchestration platform before a scientific vertical slice.
- Reversal condition: A corrected competition contract, demonstrated family
  leakage, unavailable lawful data, infeasible resource requirement, or a
  preregistered negative experiment can stop or narrow its affected lane. It
  cannot rewrite completed evidence or authorize leaderboard-driven tuning.

## D-085 — Authorize only a materially new residual TRACE v2

- Date: 2026-08-24
- Status: accepted conditional hypothesis; supersedes only D-082's prospective
  ban on every new 2026 local experiment
- Decision: Preserve R5D's `R5_ORACLE_NO_SIGNAL`, I0's permanent nonactivation,
  and the bans on rerun, repair, row-level outcome tuning, and TRACE test
  prediction. After a stronger global system produces fully cross-fitted OOF
  residuals, permit one separately named and preregistered TRACE-v2 experiment
  only if those residuals show a positive improvement-versus-coverage region.
  The new expert predicts global residuals, defaults exactly to global,
  abstains on cliffs and high uncertainty, and caps local weight at 0.25.
- Evidence: R5D showed that the measured-anchor T0 replacement was much worse
  than G0 and that similarity and inner selection did not identify safe local
  predictions. The audit's proposed residual formulation targets that observed
  competence failure without reopening T0 or I0. Its frozen keep gate requires
  at least 0.015 component-MAE improvement, a wholly favorable paired
  component-bootstrap interval, and activity-cliff degradation no greater than
  0.010.
- Alternatives: Treat D-082 as a ban on all future local hypotheses; rerun T0;
  tune a rescue gate from published R5D rows; deploy a full local replacement;
  or allow local weight above 0.25 before evidence.
- Reversal condition: Absence of a positive cross-fitted residual
  benefit-versus-coverage region stops implementation. Any contract, firewall,
  support, bootstrap, cell, cliff, influence, confirmatory, or authority failure
  rejects TRACE v2 without repair from the observed result.

## D-086 — Use a minimal contract-led control plane

- Date: 2026-08-24
- Status: accepted orchestration and submission boundary
- Decision: Orchestrate Phase 2 with the canonical knowledgebase, immutable
  per-experiment JSON contracts, the existing append-only experiment ledger,
  narrow direct runners, and the established contract/synthetic/evidence
  milestone sequence. Add shared workflow code only after repeated concrete
  need is demonstrated. Do not build a service, dashboard, database, generic
  orchestration platform, plugin system, or agent swarm. Keep research
  dependencies out of the RDKit-only core.
- Evidence: The repository already completed R2 through R5 with direct typed
  state machines, receipt-bound capabilities, atomic no-replace publication,
  and independent review. A second generic workflow layer would add migration
  and failure surface before improving a scientific comparison. The exact
  MapLight candidate is already validator-accepted for manual upload, while the
  audit found no documented challenge-specific authority for unattended live
  uploads.
- Alternatives: Build `src/cypshift/workflow/` and SQLite event sourcing before
  experiments; use ad hoc unreceipted scripts; automate the portal UI; or let
  an agent hold credentials and select submissions from leaderboard results.
- Reversal condition: Two accepted Phase 2 implementations demonstrate the
  same missing lifecycle primitive and a smaller direct abstraction cannot
  solve it. Live upload additionally requires organizer-approved API evidence,
  current rules, security review, and an explicit candidate-specific human arm
  action.

## D-087 — Freeze the Global-v2 experiment contract before execution

- Date: 2026-08-24
- Status: accepted G2-0 contract evidence; no scientific execution authority
- Decision: Freeze the Global-v2 experiment registry, label-free confirmatory
  assignment, tutorial-metric specification, nested family-holdout selection,
  paired uncertainty, effect-size gates, resource ceilings, simplest
  falsifiers, and capability boundaries in
  `global_v2_experiment_contract.json` at SHA-256
  `612b8cea20cba8fb5d209fdd2d92a42feb652477c358f92ed710449d091e5c0d`.
  Advance only to a synthetic firewall milestone. Do not open official numeric
  targets, generate official features or predictions, fit a model, evaluate a
  metric outcome, acquire an external record, inspect a blinded-test
  relationship, or create a submission under G2-0.
- Evidence: A 2026-08-24 source refresh found dataset revision
  `85f8b358...` and Space revision `13c5057b...` unchanged. Tutorial revision
  `858ae63c...` adds a backend-derived ST-RAE evaluator while the accepted
  submission validator remains byte-identical. The receipt-bound local metric
  is therefore named tutorial MA-ST-RAE until live-backend parity is proven.
  A target-independent component-hash rule assigns 913 of 4,553 components
  and 997 of 4,905 molecules to one-use confirmatory evaluation; it cannot be
  reseeded or rebalanced after target access. Seven contract tests verify exact
  parent receipts, the 12-member G1 grid and 8,880-fit ceiling, the five-stage
  falsification ladder, aggregate resource ceilings, and denied execution
  authorities.
- Alternatives: Begin a broad model sweep before freezing selection; reuse the
  blinded test as a validation set; tune the confirmatory partition from label
  coverage; call tutorial outputs official scores; acquire external assays
  before provenance and overlap policy; or construct a general orchestration
  service.
- Reversal condition: A verified organizer rule or backend implementation
  conflict, receipt mismatch, family leakage, infeasible preflight minimum, or
  synthetic firewall failure stops or replaces the affected future child
  contract before official execution. It does not permit outcome-driven repair
  of this frozen G2-0 record.

## D-088 — Accept the Global-v2 synthetic capability and metric firewall

- Date: 2026-08-24
- Status: accepted G2-1 synthetic mechanics; no official scientific execution
  authority
- Decision: Accept the smallest end-to-end Global-v2 synthetic vertical slice:
  target-independent component assignment, disjoint development,
  confirmatory-predictor, and confirmatory-scorer capabilities, a clean-room
  tutorial MA-ST-RAE kernel, deterministic endpoint-mean control, frozen
  prediction, aggregate-only score terminal, exact receipt binding, and atomic
  no-replace publication. Advance only to a distinct G2-2 MapLight
  reproduction contract bound to the accepted implementation hashes.
- Evidence: The child contract SHA-256 is `be583b5b...4541c8`; metric and
  firewall source SHA-256 values are `e63f12af...43269` and
  `047c3b49...2976c`. Two fresh 36-molecule roots, with the second input order
  reversed, produced byte-identical source, compiled-capability, candidate,
  prediction, and score maps at combined tree receipt `b7fa39eb...a8b93`.
  Pinned tutorial endpoint values 0.5, 0.0, 1.0, and 1.25 macro-average to
  0.6875. Twenty-six focused tests reject receipt, membership, capability,
  cross-compilation, duplicate, nonfinite, bound, symlink, traversal, and
  overwrite failures. The full 856-test collection passes with four expected
  skips; Ruff, strict source mypy, and package build pass. The acceptance
  receipt SHA-256 is
  `3e897b61ad54b96faeba7b715cfa6e21d54108fb4d8bc3b9550a1054aab919fd`.
  All official-target, feature, fit, prediction, metric, external, test, TDI,
  submission, and leaderboard counters are zero.
- Alternatives: Reuse the broad R5 orchestration machinery; open official
  targets while developing the splitter; let a predictor share the scorer
  root; import the tutorial's pandas/numpy evaluator into the RDKit-only core;
  or infer live-backend parity from a local function name.
- Reversal condition: Any source or receipt mismatch, synthetic replay drift,
  capability leak, tutorial parity failure, nonzero forbidden counter, or
  adversarial/CI regression revokes G2-1 acceptance and blocks G2-2. The
  synthetic control value is plumbing evidence only and cannot select a model
  or be represented as scientific or official performance.

## D-089 — Preserve the sealed holdout while freezing MapLight reproduction

- Date: 2026-08-24
- Status: accepted G2-2A contract evidence; no official scientific execution
  authority
- Decision: Freeze the G2-2A MapLight reproduction contract at SHA-256
  `7983e767dcc53d75c3a1816cf2a6528980c300b700bc339575cfb8a0faca344b`.
  Authenticate the accepted R3C terminal and aggregate receipts, but never
  rerun its full 4,905-molecule population or read its historical row-level
  outcomes. Prove the exact recipe on synthetic data, then permit a separately
  reviewed G2-2C contract to run MapLight only on the 3,908 development
  molecules. Do not compare development metric values with historical R3C
  metric values because the populations differ.
- Evidence: G2-0 prospectively assigned 997 molecules in 913 components to a
  sealed confirmatory partition. Historical R3C used all 4,905 molecules and
  4,553 components, so literal full-population reproduction would expose
  confirmatory truth before candidate freeze. Exact historical terminal,
  result, endpoint-loss, bootstrap, and global-cell receipt hashes remain
  available as immutable aggregate authentication. The contract freezes the
  accepted 2,563-column MapLight recipe, Python 3.10.13/NumPy 1.25.2/CatBoost
  1.2.1 runtime, 3x5x4 family cross-fit, 300 fits per replay, deterministic OOF
  schemas, and component-equal no-interpolation q90 of absolute inner-OOF
  residuals. All current official-operation authorities remain false.
- Alternatives: Rerun R3C literally and contaminate the confirmatory holdout;
  alter the new partition to exclude historical rows; silently compare
  different populations; read row-level R3C outcomes to tune the new harness;
  or defer uncertainty mechanics until after observing development errors.
- Reversal condition: An authenticated split receipt showing no R3C overlap,
  a reviewed organizer requirement that invalidates the sealed partition, or a
  receipt/runtime inconsistency stops G2-2 before official execution and
  requires a new prospective decision. It does not authorize confirmatory
  truth access or outcome-driven repair.

## D-090 — Accept the exact-runtime synthetic MapLight runner

- Date: 2026-08-24
- Status: accepted G2-2B synthetic mechanics; no official scientific execution
  authority
- Decision: Accept the receipt-bound MapLight-only runner and capability
  compiler at source SHA-256 values `154f8d23...b93f` and
  `45b30689...99f`. Each fit interface opens only its current cell's training
  targets; the scorer capability exposes truth only after prediction freeze.
  Require component containment in both outer and scoped inner folds, exact
  CatBoost parameters, component-equal non-interpolated q90, atomic no-replace
  publication, and two byte-identical synthetic roots. Advance only to a
  contract-only G2-2C development execution freeze.
- Evidence: Acceptance receipt SHA-256 `1a498f21...a3bb` binds two fresh
  200-molecule, 100-component roots, 600 real CatBoost fits total, 24,000 OOF
  prediction rows total, and 318 matched files at combined tree SHA-256
  `e81bfb92...5de06`. The second root reversed source order. Seventeen focused
  tests cover receipt tamper, multi-molecule outer and inner family containment,
  training-only targets, truth-after-freeze, q90 arithmetic, symlinks,
  writability, traversal, overwrite, replay mismatch, and exact tracked source
  and acceptance hashes. All official, confirmatory, historical-row, test, TDI,
  submission, and leaderboard counters are zero.
- Negative evidence: The first 20-molecule attempt stopped after one synthetic
  fit because CatBoost resolved `subsample=1`, not the accepted
  `0.800000011920929`; the repair increased fixture support rather than adding
  an omitted constructor argument. A later 600-fit, byte-identical replay was
  rejected because unique components could not falsify inner-family leakage.
  Both records remain tracked and have zero official operations.
- Alternatives: Pass `subsample` explicitly and drift from the accepted
  constructor; accept unique-component determinism without a family attack;
  let the model process see validation truth; calculate q90 from outer
  residuals; or proceed directly to official targets after a partial replay.
- Reversal condition: Any source, runtime, parameter, capability, component,
  prediction-freeze, q90, output, determinism, or accounting regression revokes
  G2-2B and blocks G2-2C. It does not permit outcome-driven repair or any access
  to confirmatory truth, historical R3C row-level artifacts, or blinded test.

## D-091 — Freeze one bounded development-only MapLight execution claim

- Date: 2026-08-24
- Status: accepted G2-2C contract and unconsumed-claim evidence; no official
  scientific execution authority
- Decision: Freeze the additive G2-2C execution contract at SHA-256
  `962484b7e8f20ca9b9e37735e82c4db62766116a47c49c44dbc90d14db7985c2`
  and one immutable unconsumed claim at SHA-256
  `59d7d6915fc3f9e8ae0cb1fef2af805eb3d4d68c641091d518e4e02683730659`.
  Bind the accepted G2-2A and G2-2B receipts, exact MapLight runner and
  synthetic compiler, locked runtime, official input receipt strings,
  development population and support minima, two sequential fresh replays,
  600-fit ceiling, terminal schemas, cleanup, and zero forbidden counters.
  Keep the future official compiler, attempt wrapper, and official-shaped
  synthetic-acceptance hashes null until a distinct reviewed synthetic
  implementation milestone. Do not consume the claim or open any official
  input during this freeze.
- Evidence: Seven focused static tests authenticate both new artifacts and all
  tracked parents and implementation sources. The contract requires 3,908
  development molecules in 3,640 components, preserves 997 molecules in 913
  confirmatory components, freezes minima of 750 development targets per
  endpoint, 75 outer-validation targets per cell, and 400 inner-training
  targets per cell, and caps execution at two 300-fit replays. Current official
  target, feature, fit, prediction, residual, diagnostic, and metric counters
  are zero, as are confirmatory, historical-row, blinded-test, TDI, external,
  submission, leaderboard, and upload counters.
- Alternatives: Open official files while writing the compiler; treat a
  mutable tracked claim as attempt state; authorize retries after a crash;
  populate future implementation hashes prospectively; run the two replays in
  parallel; or let a development metric control reproduction acceptance.
- Reversal condition: Any parent, source, runtime, population, receipt, claim,
  no-replace, cleanup, terminal, or authority contradiction rejects G2-2C
  before official execution. A reviewed integrated official-shaped synthetic
  acceptance may fill the three private consumed-claim implementation fields;
  it may not change any other frozen field or authorize confirmatory truth.

## D-092 — Accept the exact-claim G2-2C execution implementation

- Date: 2026-08-24
- Status: accepted official-shaped synthetic implementation evidence; tracked
  claim unconsumed and no official execution authority until reviewed
  integration and green post-main CI
- Decision: Accept synthetic receipt SHA-256
  `c57845989a29208f240151ab1b585f64f737b82f008dd2b7df62fd9764e50fa5`
  for compiler SHA-256 `67fb59ab...3d75`, fixed-root attempt wrapper SHA-256
  `3d161a43...ac52`, and acceptance driver SHA-256 `d50b6016...f947`. The
  compiler must derive the exact consumed claim from the immutable tracked
  template, authenticate the exact R2B/R3A parent manifests and seven leaves,
  assign the label-free development partition before parsing targets, and
  publish disjoint sparse model/scorer capabilities. The bound CLI may publish
  only
  `/home/zbos/cypshift-private/openadmet-2026/g2-2c-maplight-development-source-v1`
  before consumption and may create only
  `/home/zbos/cypshift-private/openadmet-2026/g2-2c-maplight-development-attempt-1`
  to consume the claim. Runtime and storage gates precede consumption; the two
  300-fit replays remain sequential, no-replace, non-retriable, and
  non-resumable. Integrate and pass post-main CI before opening either accepted
  official parent root.
- Evidence: Two final official-shaped synthetic roots completed 600 real
  CatBoost 1.2.1 fits in about 1.82 wall-hours. Root B reversed physical source
  order, yet all six terminal files were byte-identical at combined tree
  SHA-256 `e05df355...555ca`; both terminal manifests are SHA-256
  `56b194a5...6d3e`. Each replay used 326 development molecules, 1,043 sparse
  finite truth rows, 19,560 prediction rows, 15,645 residual computations, 60
  q90 contexts, and 300 fits. Model stages opened zero outer/inner validation
  truth, scorer truth opened only after prediction freeze, private capability
  roots were removed, and every official, confirmatory, historical-row, test,
  TDI, external, submission, metric, leaderboard, and upload counter is zero.
  Twelve focused tests cover exact claim derivation without template mutation,
  fixed source publication, exact parent/leaf lineage, opaque confirmatory
  suffixes, arbitrary physical source order, sparse cross-fitting, outer/inner
  family containment, stage-scoped authority, prediction-identity forgery,
  receipt failure, cleanup, and unconsumed-claim rejection before source open.
  The first 600-fit run was rejected despite determinism for omitted counters,
  non-exact summation, and incomplete parent binding. A second run was
  interrupted after one complete replay when audit found lineage,
  claim-order, source-view, fixed-root, authority, and resource-receipt gaps.
  Both negative records remain immutable and opened zero official input.
- Alternatives: Accept deterministic bytes without exact lineage; allow a
  caller-selected source or attempt root; build the source view by hand; let a
  SHA-shaped counterfeit claim reach official files; consume before source and
  runtime authentication; claim fitting authority on an underpowered stop;
  omit resource telemetry; or continue a replay after implementation bytes
  changed.
- Reversal condition: Any integrated source or acceptance hash mismatch,
  parent/leaf receipt drift, claim-template mutation, pre-consumption gate
  defect, capability or family leak, prediction-identity inconsistency,
  nonzero forbidden counter, cleanup defect, runtime/resource breach, or CI
  regression revokes this acceptance before claim consumption. After the fixed
  attempt root is created, every terminal or incomplete state is final and
  cannot authorize a retry, resume, move, or overwrite.

## D-093 — Repair and reaccept the official R3A parent-layout adapter

- Date: 2026-08-24
- Status: accepted superseding official-shaped synthetic evidence; tracked
  claim unconsumed and official execution blocked until reviewed integration
  and green post-main CI
- Decision: Keep the D-091 contract, immutable claim, scientific recipe,
  wrapper, runtime, splits, support gates, fixed private roots, and authority
  unchanged. Name the two accepted parent manifests explicitly: R2B
  `manifest.json` and R3A `feature_manifest.json`. Supersede only D-092's
  implementation acceptance with compiler SHA-256 `8317a225...f8b4` and
  fresh synthetic acceptance SHA-256 `ffb3956c...83b2`; wrapper
  `3d161a43...ac52`, acceptance driver `d50b6016...f947`, runner
  `154f8d23...acb93f`, contract `962484b7...985c2`, and unconsumed claim
  `59d7d691...30659` remain exact.
- Evidence: Green post-main CI for D-092 permitted a read-only official-parent
  preflight. It authenticated R2B manifest receipt `08dcf61c...c8c8` at
  `manifest.json` and R3A receipt `32a95095...026b` at
  `feature_manifest.json`, then rejected the compiler's incorrect R3A
  `manifest.json` lookup before source publication, target or feature parse,
  fit, or claim consumption. Both fixed official roots remained absent. The
  two-name repair passed its focused source-builder test and two entirely fresh
  sequential 300-fit CatBoost 1.2.1 replays in about 1.78 wall-hours. Root B
  reversed physical source order; all six terminal files were byte-identical
  at combined tree SHA-256 `49e56607...80e5`, with terminal manifest
  SHA-256 `a86f6dbe...7dcb`. Each replay used 326 molecules, 1,043 finite
  targets, 3,912 outer and 15,648 inner predictions, 3,129 residual and
  uncertainty rows, 60 component metrics and q90 contexts, and 300 fits.
  Private capability and prediction roots were cleaned. Every official,
  confirmatory, historical-row, blinded-test, TDI, external, submission,
  metric, leaderboard, and upload counter is zero.
- Alternatives: Rename or mutate the immutable accepted R3A root; create an
  unreviewed intermediate input view; consume the claim to discover a known
  filename failure; reuse D-092's terminals despite changed compiler bytes; or
  expand the repair into contract, wrapper, recipe, or schema changes.
- Reversal condition: Any discrepancy in the two accepted parent names or
  receipts, fresh acceptance bytes, exact claim derivation, family or sparse
  capability isolation, cleanup, forbidden counters, signed integration, or
  post-main CI revokes D-093 before claim consumption.

## D-094 — Accept the reproduced G2-2 MapLight development baseline

- Date: 2026-08-24
- Status: accepted terminal G2-2 development evidence; sole claim consumed;
  confirmatory and competition-facing capabilities remain closed
- Decision: Accept the one authorized G2-2C attempt as
  `G2_2_MAPLIGHT_REPRODUCED` under official attempt receipt SHA-256
  `5f270854...2b936`, consumed claim SHA-256 `6d215b05...1e43`, contract
  `962484b7...985c2`, compiler `8317a225...f8b4`, wrapper
  `3d161a43...ac52`, runner `154f8d23...acb93f`, research lock
  `99e72821...195d8`, and resolved parameter receipt `c56235a5...1757`.
  Preserve only aggregate tracked evidence at SHA-256
  `76775030...a4482` in `global_v2_maplight_official_reproduction.json`; keep
  all row-level official OOF, residual, uncertainty, and component-diagnostic
  artifacts outside Git.
  Advance to a contract-only G2-3 `EXP-G1` freeze. The next experiment must
  bind this baseline, use the unchanged MapLight representation, keep all
  selection inside inner component folds, and retain the preregistered global
  and endpoint-harm gates.
- Evidence: Two sequential 300-fit replays completed in 3,643.6 wall-seconds,
  below the 16.194 CPU-core-hour upper bound and 234,160,503-byte restricted
  storage peak. All six terminal files were byte-identical at terminal manifest
  SHA-256 `62c88f7d...77fe`. Per replay, 3,908 development molecules and 5,197
  finite truth rows produced 46,896 outer and 187,584 inner predictions, 60
  component metrics and q90 contexts, and 15,591 residual and uncertainty rows.
  Model processes opened zero outer or inner validation truth; the scorer
  opened 5,197 truth values only after prediction freeze. Every confirmatory,
  historical-row, blinded-test, TDI, external, submission, official-metric,
  leaderboard, and upload counter is zero. Family-safe development OOF
  component-macro MAE is 0.58378. Repeat means are 0.58355, 0.58368, and
  0.58412. Endpoint means are CYP1A2 0.66733, CYP2D6 0.59855, CYP3A4
  0.57927, and CYP2C9 0.48997. These values establish a stable development
  baseline only; they are not the official challenge metric or confirmatory
  evidence.
- Alternatives: Retry or resume the consumed claim; retain private replay
  staging; copy row-level official outputs into Git; tune from confirmatory or
  leaderboard feedback; widen G2-3 immediately to heterogeneous
  representations; or optimize only the weakest endpoint without the global
  and no-harm gates.
- Reversal condition: The completed attempt is immutable and cannot be rerun.
  Any receipt mismatch, non-identical replay byte, family/capability leak,
  hidden forbidden operation, or aggregate-calculation defect revokes the
  scientific acceptance and stops G2-3; it does not authorize a retry, resume,
  move, overwrite, or replacement G2-2 attempt.

## D-095 — Freeze the minimal nested EXP-G1 screen

- Date: 2026-08-24
- Status: accepted contract-only G2-3A evidence; no official input, fit,
  prediction, or metric operation authorized
- Decision: Freeze `global_v2_g1_screen_contract.json` at SHA-256
  `ce39721f...d97c3`, bound to the D-094 aggregate baseline receipt
  `76775030...a4482` and the exact G2-0 twelve-configuration, three-seed
  CatBoost screen. Use only the unchanged 2,563-column MapLight feature order.
  Within every repeat/outer-fold/endpoint cell, freeze all three seed
  predictions before scoring, select the configuration from pooled inner OOF
  rows by endpoint tutorial ST-RAE, component-macro MAE, then configuration ID,
  and refit only that selection under the three frozen seeds. Compare the
  resulting nested outer predictions against the immutable D-094 baseline on
  identical rows. All five promotion members are conjunctive: at least 3%
  tutorial-primary improvement, at least 0.015 component-macro MAE
  improvement, paired component-bootstrap upper 95% bound below zero, at least
  8/15 favorable outer cells, and no endpoint degradation above 0.015.
- Evidence: Exact arithmetic requires 8,640 inner configuration-seed fits and
  180 selected outer-seed fits, totaling 8,820 new fits. The G2-0 parent ceiling
  is 8,880; its spare 60 fits are deliberately unusable for retries, repairs,
  extra seeds, baseline refits, or a thirteenth configuration. Expected
  prediction counts are 6,753,024 raw inner rows, 2,251,008 seed-averaged inner
  rows, 562,752 complete selection-projection rows, 140,688 raw outer rows, and
  46,896 seed-averaged outer rows. The contract defines least-privilege inner
  model/freezer/selector and outer model/freezer/scorer stages, exact family and
  prediction identities, float64 `math.fsum` reductions, a cross-fitted
  selection-only projection for a future full-development recipe, paired metric
  masks, terminal failures, aggregate-only Git publication, and a 1,200
  CPU-core-hour/40 GB/120 wall-hour ceiling. Nine focused static tests bind the
  exact parents, baseline, sources, configurations, seeds, arithmetic, nested
  selection, acceptance, authority, and terminals. Every official,
  confirmatory, historical-row, blinded-test, TDI, external, submission,
  metric, leaderboard, and upload counter is zero.
- Alternatives: Use the parent's unused 60-fit allowance; tune only CYP1A2 or
  CYP2D6; score seeds separately and select the luckiest; add early stopping;
  select from outer outcomes; refit the baseline; start heterogeneous EXP-G2
  before falsifying tuned MapLight; or issue an official claim before synthetic
  capability and determinism evidence.
- Reversal condition: Any parent or baseline receipt drift, mismatch from the
  exact twelve configurations or three seeds, fit/prediction arithmetic error,
  family or capability leak, non-inner selection, inconsistent paired mask,
  acceptance ambiguity, nonzero scientific operation, unsigned integration, or
  CI regression revokes D-095 before G2-3B. A later clean EXP-G1 rejection is
  final negative evidence and cannot authorize grid expansion or rerun.

## D-096 — Freeze the two-layer EXP-G1 synthetic implementation boundary

- Date: 2026-08-24
- Status: accepted contract-only G2-3B evidence; no synthetic execution,
  official input, fit, prediction, or metric operation authorized
- Decision: Freeze `global_v2_g1_synthetic_contract.json` at SHA-256
  `c8c706a8...ba866`, bound to the exact D-095 parent
  `ce39721f...d97c3`. Implement one additive runner and one synthetic driver
  only after reviewed integration and green post-main CI. Use two fresh
  80-molecule/40-component roots with two molecules per family, three repeats,
  five outer folds, four scoped inner folds, four endpoints, and the exact
  2,563-column MapLight shape. Separate exhaustive mechanics from runtime
  compatibility: a deterministic model double traverses every frozen inner and
  selected-outer configuration/seed identity, while real CatBoost fits only
  probe the frozen constructor forms and seeds.
- Evidence: Each root requires 8,640 inner and 180 outer model-stage
  invocations, matching the D-095 8,820 topology exactly; two roots total
  17,640. Each root performs exactly fourteen locked-runtime real fits: all
  twelve configurations under seed 20260824 plus G1-C00 under seeds 20260825
  and 20260826; two roots total twenty-eight. Reversed physical source order
  must preserve every terminal byte. Predeclared selection oracles require at
  least three winning configuration IDs and an exact configuration-ID tie.
  Least-privilege stages seal validation and outer truth until their freezers
  are immutable. Fourteen adversarial classes cover family and truth leakage,
  seed/configuration drift, identity forgery, outer-feedback selection,
  nonfinite arithmetic, partial topology, runtime drift, completion-order
  nondeterminism, cross-root mixing, retry/resume/overwrite, cleanup, and all
  forbidden counters. Nine focused static tests bind the frozen contract. This
  milestone opens no synthetic or official capability.
- Alternatives: Execute 17,640 real synthetic CatBoost fits; probe only object
  construction without fitting; shrink the scientific topology; omit the
  reversed-order replay; use singleton components; let synthetic scores tune
  the grid; or combine implementation and official execution authority.
- Reversal condition: Any parent drift, contract-hash mismatch, non-exact
  topology or probe count, family/capability leak, nondeterministic terminal,
  synthetic result used as scientific evidence, nonzero official operation,
  unsigned integration, or CI regression revokes D-096. A failed synthetic
  replay cannot be resumed, repaired, moved, or converted into execution
  authority.

## D-097 — Accept the exact EXP-G1 synthetic implementation

- Date: 2026-08-24
- Status: accepted G2-3B synthetic mechanics and locked-runtime evidence; no
  official development, metric, confirmatory, test, or submission authority
- Decision: Accept `global_v2_g1_synthetic_acceptance.json` at SHA-256
  `479ba130...7ff06`, bound to G2-3B contract `c8c706a8...ba866`, runner
  `fef03428...6ff47`, driver `8dea72b4...3fa3`, focused tests
  `209048f2...6579`, accepted MapLight runner `154f8d23...6a9acb93f`, tutorial
  metric `e63f12af...43269`, and research lock `99e72821...4195d8`. Retain the
  two-layer design: deterministic model doubles prove the complete nested
  control flow; real CatBoost fits prove only constructor/runtime compatibility.
- Evidence: Two fresh 80-molecule/40-component roots ran sequentially in 15.85
  wall-seconds at about 1.0 GB peak RSS. Root B reversed both physical source
  order and model-stage execution order. All seven terminal files matched
  byte-for-byte at combined tree receipt `bf40c3f6...2f872` and terminal
  manifest `b3aeb574...be2c`. Across both roots, 17,640 model-stage identities
  and exactly 28 real locked-runtime CatBoost fits completed. Per root, the
  implementation froze 138,240 raw inner predictions, 46,080 three-seed inner
  means, 11,520 complete-projection rows, 2,880 raw outer predictions, 960
  three-seed outer means, 60 outer selections, four future endpoint tokens,
  888 tutorial calls, and 2,000 paired component-bootstrap replicates.
  Twenty-three focused tests cover family and truth leakage, cross-root mixing,
  seed/configuration and feature/runtime drift, identity forgery, nonfinite
  arithmetic, partial probes, completion-order nondeterminism, overwrite,
  retry/resume, symlink/traversal, cleanup, and forbidden accounting. Ruff,
  mypy, and the 933-test repository suite pass locally. Every official,
  development-metric, confirmatory, historical-row, blinded-test, TDI,
  external, submission, leaderboard, and upload counter is zero.
- Alternatives: Treat synthetic effect sizes as model evidence; run every
  synthetic identity as a real fit; omit root-instance binding; accept only
  canonical input/execution order; loosen a failed topology; open official
  development inputs in the same milestone; or draft a claim before reviewed
  integration and post-main CI.
- Reversal condition: Any tracked/source receipt drift, non-identical terminal,
  hidden family or capability leak, invalid resolved CatBoost semantics,
  nonzero forbidden operation, synthetic value used as scientific evidence,
  incomplete cleanup, unsigned integration, or post-main CI failure revokes
  D-097 and stops G2-3. It does not authorize replay, repair, resume, move,
  overwrite, official access, or a replacement G2-3B attempt.

## D-098 — Freeze the single-use EXP-G1 development execution envelope

- Date: 2026-08-24
- Status: accepted contract-and-unconsumed-claim-only G2-3C evidence; no
  official development or baseline-row access, fit, prediction, or metric
  operation authorized
- Decision: Freeze `global_v2_g1_execution_contract.json` at SHA-256
  `c75cb01e...0b869` and its immutable unconsumed claim at SHA-256
  `1c9f3438...46154`. Bind the exact D-095/D-096/D-097 receipts, runner
  `fef03428...6ff47`, driver `8dea72b4...3fa3`, focused tests
  `209048f2...6579`, fixed G2-2 development-source and baseline-prediction
  receipts, private source/baseline/attempt roots, runtime, resources, cleanup,
  and terminal semantics. Permit at most one later consumed attempt containing
  exactly 8,820 new CatBoost fits and zero baseline refits, with one
  sixteen-thread fit at a time and no retry, resume, move, or overwrite.
- Evidence: Eight focused static tests authenticate every parent and accepted
  source, the exact fit and prediction arithmetic, the five conjunctive
  promotion gates, immutable official receipt strings, one-use claim
  semantics, fixed resources, cleanup, terminals, and current zero authority.
  Four future implementation receipt fields are null. The contract freeze
  opens no corresponding private file and every official, development-metric,
  confirmatory, historical-row, blinded-test, TDI, external, submission,
  leaderboard, and upload counter is zero.
- Alternatives: Consume the claim before official-shaped wrapper acceptance;
  open the development source while drafting; reuse the synthetic driver as an
  official compiler; run two 8,820-fit official replays; refit the baseline;
  parallelize adaptively; treat unused parent capacity as repair budget; or
  combine contract freeze, implementation acceptance, and scientific execution.
- Reversal condition: Any parent, source, baseline, runtime, or implementation
  receipt drift; non-exact fit topology; family, truth, or outer-feedback leak;
  altered acceptance; premature claim consumption; nonzero forbidden
  operation; unsigned integration; or post-main CI regression revokes D-098.
  A later consumed failure or rejection remains terminal and cannot authorize
  retry, repair, resume, move, overwrite, or grid expansion.

## D-099 — Accept G2-3C mechanics but block claim consumption on resources

- Date: 2026-08-24
- Status: accepted official-shaped synthetic implementation evidence; sole
  development claim remains unconsumed and official execution is blocked
- Decision: Accept the additive G2-3C compiler, attempt wrapper, and two-root
  official-shaped synthetic mechanics at acceptance SHA-256
  `87065e0c...65f9e`, binding compiler `1af2ddf8...5e6c8`, wrapper
  `dd413f44...03a6b`, driver `ec14ec45...3e9e`, accepted G1 runner
  `fef03428...6ff47`, and the locked research runtime. Keep the tracked claim
  `1c9f3438...46154` unconsumed. The exact runtime probes falsify feasibility
  under the frozen 120 wall-hour and 1,200 CPU-core-hour ceilings, so mechanics
  acceptance does not grant official source, baseline-row, fitting, prediction,
  or development-metric authority.
- Evidence: Two fresh 312-development-molecule roots, the second in reversed
  physical source order, matched all nine terminal files byte-for-byte at tree
  receipt `a8848562...c2f1b`. Per root the sparse compiler retained 999 finite
  central targets, 860 tutorial-eligible intervals, 139 point-only rows, and
  424 tutorial-eligible rows without standard deviations while keeping all 352
  confirmatory rows opaque and parsing zero confirmatory values. Each replay
  traversed exactly 8,640 inner and 180 selected-outer model-stage identities,
  froze 539,136 raw and 179,712 seed-averaged inner predictions, 11,232 raw and
  3,744 seed-averaged outer predictions, and made 888 tutorial-metric calls.
  The 28 real locked-runtime probes completed in 1,443.87 wall-seconds, consumed
  19,203.67 CPU-seconds, reached 1,505,876 KB peak RSS, and matched across both
  roots. At the smaller synthetic scale, exact linear projection to 8,820 fits
  is 126.339 wall-hours and 1,680.321 CPU-core-hours, already exceeding both
  frozen ceilings before the larger official folds. Eight focused tests and the
  954-test repository suite pass; Ruff, production mypy, package build, and the
  locked-runtime CLI smoke check pass. Every official, confirmatory,
  historical-row, blinded-test, TDI, external, submission, official-metric,
  leaderboard, and upload counter is zero.
- Alternatives: Consume the claim and hope the larger official run is faster;
  relax a ceiling after observing official data; reduce the grid, seeds,
  iterations, depth, or feature set; add adaptive concurrency; retry a failed
  consumed attempt; or call mechanics acceptance proof of scientific model
  quality.
- Reversal condition: Claim consumption requires a separately frozen,
  synthetic-only resource-feasibility contract and exact prediction-equivalence
  evidence for any implementation optimization. The conservative projection
  must fit both existing ceilings with explicit margin without changing a
  scientific identity. If no such bounded implementation remedy passes, reject
  EXP-G1 as infeasible without consuming the claim; do not widen or tune it.

## D-100 — Freeze one implementation-equivalent EXP-G1 resource falsifier

- Date: 2026-08-24
- Status: accepted contract-only G2-3D evidence; no synthetic execution or
  official authority; G2-3C claim remains unconsumed
- Decision: Freeze
  `global_v2_g1_resource_feasibility_contract.json` at SHA-256
  `17327310...24a92`. Test exactly one implementation optimization after
  reviewed integration: reuse one fold-local CatBoost 1.2.1 quantized training
  Pool and its matching prediction Pool across fresh models for the frozen
  configuration-seed identities. Preserve every configuration, seed,
  iteration, depth, loss, feature, target, fold, fit identity, fit count,
  sixteen-thread constructor, sequential-execution rule, metric, selection,
  and terminal. A mismatch or resource failure rejects EXP-G1 without another
  implementation remedy or claim consumption.
- Evidence: D-099's accepted 28 real probes project the unchanged 8,820-fit
  design to 126.339 wall-hours and 1,680.321 CPU-core-hours on the smaller
  synthetic fixture. Code inspection finds repeated feature quantization as
  the only fold-local work that can be reused without reusing a model, target
  statistic, or prediction. The frozen falsifier pairs raw reference and
  optimized modes on two opposite-order synthetic roots, with fourteen
  identities per mode and root. All float64 prediction bytes, constructor
  parameters, and canonical resolved-parameter bytes must match exactly. The
  worse optimized-root projection, never an average or overhead-subtracted
  value, must be at most 96 wall-hours and 960 CPU-core-hours, retaining 20%
  margin below both original ceilings. Seven focused static tests pass. This
  milestone performs zero fit or prediction, opens no official input, and
  keeps every official and forbidden counter, including claim consumption, at
  zero.
- Alternatives: Consume the claim and hope; change thread count or concurrency;
  reduce configurations, seeds, folds, iterations, depth, or features; use
  early stopping, warm starts, GPU, approximate equality, model or prediction
  reuse; average favorable timing roots; or try another optimization after a
  failure.
- Reversal condition: Any parent, implementation, runtime, claim, cache-
  identity, capability, exact-equivalence, projection, resource, cleanup,
  accounting, signed-integration, or post-main-CI failure rejects the
  falsifier. Passing it requires an aggregate receipt and reviewed integration
  of the exact optimized bytes before the existing claim can be reconsidered.
  Rejection leaves the claim unconsumed and advances to the next preregistered
  Phase 2 lane.

## D-101 — Reject EXP-G1 as resource-infeasible without consuming its claim

- Date: 2026-08-24
- Status: accepted terminal negative G2-3D evidence; `EXP-G1` closed; G2-3C
  claim remains unconsumed; no official authority
- Decision: Accept tracked resource receipt SHA-256 `67585830...a9be4` and
  reject `EXP-G1` as resource-infeasible. Fold-local quantized-Pool reuse is
  exactly prediction-equivalent but fails both preregistered 20%-margin resource
  gates. Do not consume the G2-3C claim, run the 8,820-fit development screen,
  change its grid, seeds, iterations, depth, features, threads, or concurrency,
  or test another G1 optimization. Advance to a contract-only G2-4A freeze for
  the preregistered `EXP-M1` masked multitask lane.
- Evidence: Two opposite-order synthetic roots paired the accepted raw-array
  reference and the sole optimization over all fourteen frozen probe identities
  per mode. All 56 real CatBoost fits completed, all 3,584 prediction values
  matched at exact float64 bytes, and every resolved-parameter receipt matched.
  Root A raw consumed 711.63 wall-seconds and 9,544.93 CPU-seconds; optimized
  consumed 717.13 and 9,602.97, 0.8% slower wall and 0.6% more CPU. Root B
  reproduced the finding. The worse optimized projection is 125.497 wall-hours
  and 1,680.519 CPU-core-hours versus the frozen 96/960 maxima. Peak RSS was
  1,459,196 KB and restricted work was 25,422,692 bytes. The private work root
  was cleaned, receipt bytes are immutable, the tracked claim SHA-256 remains
  `1c9f3438...46154`, the fixed official attempt root is absent, and every
  official, confirmatory, historical-row, test, TDI, external, submission,
  metric, leaderboard, upload, and claim-consumption counter is zero. Twenty-
  five focused tests pass.
- Alternatives: Consume the claim despite the falsifier; relax either resource
  threshold; average roots; subtract reference overhead; reduce scientific
  identities; change threads or concurrency; use GPU or approximate equality;
  test a second optimization; or expand directly to heterogeneous G2 models.
- Reversal condition: None for the historical G1 result. A corrected receipt
  or validator defect may revoke acceptance but cannot authorize a retry from
  observed timing. A future materially different experiment requires its own
  prospective contract and may not be represented as `EXP-G1`.

## D-102 — Freeze the smallest controlled EXP-M1 fingerprint test

- Date: 2026-08-24
- Status: accepted contract-only G2-4A evidence; no runtime, implementation,
  synthetic fit, official input, development metric, or execution authority
- Decision: Freeze `global_v2_m1_screen_contract.json` at SHA-256
  `63516e0f...b1c2cc0`. Test exactly one parent-specified shared 512/256 MLP over
  standardized Morgan radius-2 count 2048 plus 200 fold-preprocessed RDKit
  descriptors against the immutable fixed MapLight baseline, four independent
  networks, and one training-only label-permuted shared control. Select central
  MAE versus reported-bound dead-zone loss only from four inner component
  folds, let each independent endpoint select its own loss from the same inner
  evidence, fit both independent outer losses for matched and strongest-control
  comparisons, average the three frozen seeds before selection and scoring,
  and run exactly 2,430 neural fits. Do not add Chemprop, auxiliary targets, another
  representation, architecture, loss, seed, calibration, or post-outcome
  repair.
- Evidence: The child preserves the 3x5 outer and four-fold inner D-032 family
  boundaries, all three parent seeds, the exact 512/256 trunk, 64-unit heads,
  dropout, AdamW settings, batch size, 300-epoch cap, and patience 25. It
  freezes target-blind per-fold imputation and scaling, loss masks, deterministic
  batch and label permutations, median inner epoch reduction, prediction
  identities, seed arithmetic, three paired component bootstraps, and one-shot
  terminals. Promotion requires every preregistered condition: at least 0.020
  component-macro MAE improvement over fixed MapLight, strictly positive
  tutorial-primary direction, at least two endpoint gains of 0.010, no endpoint
  degradation above 0.020, at least 8/15 favorable outer cells, and paired
  upper 95% bounds below zero versus matching-loss independent, independently
  selected independent, and permuted controls.
  Before a claim can exist, two synthetic roots must project the full design to
  at most 240 CPU-core-hours, 64 GPU-hours, 64 GB, and 38.4 wall-hours, retaining
  20% margin. Eleven focused static tests pass. Every scientific and forbidden
  operation counter is zero.
- Alternatives: Run the shared model without an independent control; omit the
  permutation falsifier; choose loss or epochs from outer outcomes; expand to
  Chemprop immediately; reuse MapLight's infeasible claim; weaken the parent
  effect-size or endpoint-harm gates; or install a neural runtime before its
  deterministic and resource contract is frozen.
- Reversal condition: Any parent, feature, split, mask, architecture,
  optimization, loss-selection, fit-arithmetic, acceptance, resource,
  capability, privacy, signed-integration, or post-main-CI defect revokes this
  freeze before implementation. A clean later resource or scientific rejection
  closes EXP-M1 without widening or retrying it.

## D-103 — Freeze the deterministic CPU synthetic boundary for EXP-M1

- Date: 2026-08-24
- Status: accepted contract-only G2-4B evidence; no dependency installation,
  synthetic execution, official authority, or formal attempt claim
- Decision: Freeze `global_v2_m1_synthetic_contract.json` at SHA-256
  `f80a6e8d...48df7`. Pin an isolated Python 3.12.3/NumPy 2.5.2/RDKit
  2026.3.5/PyTorch 2.13.0 CPU runtime on the observed Ryzen 9 7950X. Use four
  spawned workers on disjoint physical-core affinity slots, four intra-op
  threads each, deterministic PyTorch algorithms, MKLDNN disabled, and no
  accelerator. Prove the full 2,430-identity topology with a model double in
  each of two roots and project resources from exactly 32 full-width,
  300-epoch real fits spanning every architecture, loss, and seed form.
- Evidence: Read-only host inspection found 16 physical cores, 32 logical
  processors, 31,940,952 KiB RAM, and no CUDA or ROCm device. The exact CPU
  wheel and metadata hashes are frozen. Root B reverses physical and launch
  order. Parameter and float64 prediction digests must match exactly while
  timings remain root-specific. The worse-root projection must simultaneously
  remain at or below 240 CPU-core-hours, zero GPU-hours, 38.4 wall-hours, 64 GB
  stored, and 24 GiB RSS. Twelve focused static tests pass. Current accounting
  is zero for environments, dependencies, features, fits, predictions, metrics,
  official inputs, claims, and forbidden capabilities.
- Alternatives: Add PyTorch to the installable core; use GPU; allow dynamic
  threads or affinity; time reduced-width or reduced-epoch models; sample the
  topology instead of traversing it; average favorable roots; install and run
  before contract review; or collapse implementation and the one-shot formal
  attempt into one mutable milestone.
- Reversal condition: Any parent, wheel, host, affinity, determinism, fixture,
  topology, identity, timing, projection, firewall, cleanup, accounting,
  signed-integration, or post-main-CI defect revokes this freeze before the
  formal attempt. A later terminal resource or mechanics failure closes EXP-M1
  without changing device, threads, concurrency, fits, epochs, or runtime.

## D-104 — Accept the exact EXP-M1 implementation before formal timing

- Date: 2026-08-24
- Status: accepted G2-4B implementation and bounded API-smoke evidence; formal
  two-root probe and official authority remain closed
- Decision: Accept aggregate implementation receipt SHA-256
  `8b195bc6...26622`. Preserve the isolated Python 3.12.3/NumPy 2.5.2/RDKit
  2026.03.5/PyTorch 2.13.0+cpu lock, deterministic fit engine, exact synthetic
  fixture, exhaustive model double, four-worker formal driver, conservative
  projector, network namespace, single-use claim verifier, and fail-closed
  cleanup. Do not rerun the four exhausted API smokes. Require reviewed signed
  integration and green post-main CI before freezing a distinct source-binding
  claim; require that claim's integration before the 32-fit formal probe.
- Evidence: Two fresh opposite-order model-double roots matched all six
  terminal files byte-for-byte after 2,430 fit receipts and 75 selection tokens
  per root. All 4/4 authorized real PyTorch API smokes completed at three epochs,
  at most 64 rows, and one fit at a time, spanning shared, permuted,
  independent, central-MAE, and interval-loss forms. They produced 160 finite
  prediction values. Their 3.5-second elapsed time is explicitly not resource
  evidence. Twenty-four focused tests pass. One isolated environment and 13
  packages were created; the root dependency set is unchanged. Every official
  and forbidden counter is zero, and temporary model-double roots were cleaned.
- Alternatives: Add PyTorch to the core; infer formal resources from the tiny
  smokes; run the 32 fits before source integration; omit the reverse root,
  exact repeat, cache accounting, network namespace, or cleanup; use average
  rather than worst observations; or create and consume a mutable claim in the
  same milestone.
- Reversal condition: Any source, lock, runtime, architecture, loss, optimizer,
  topology, mask, fold, preprocessing, permutation, stopping, prediction,
  resource formula, namespace, claim, cleanup, accounting, signed-integration,
  or post-main-CI defect revokes implementation acceptance before claim
  consumption. A formal mechanics or resource failure is terminal for EXP-M1.

## D-105 — Freeze the sole source-bound EXP-M1 formal resource attempt

- Date: 2026-08-24
- Status: accepted contract-only G2-4C claim; immutable and unconsumed; zero
  formal fits and no official authority
- Decision: Freeze `global_v2_m1_formal_attempt_claim.json` at SHA-256
  `d6693d11...16497`. Bind the exact D-103/D-104 parents, implementation commit,
  project, Python pin, lock, runner, driver, focused tests, prepared isolated
  environment, dedicated cache, and fixed absent attempt/receipt paths. After
  reviewed signed integration and green post-main CI, consume it exactly once
  inside a fresh user/network namespace for root A then root B, 16 full-width
  300-epoch fits each. No fit is authorized before that integration.
- Evidence: The environment contains the exact 13 locked packages under Python
  3.12.3 with PyTorch 2.13.0+cpu and CUDA unavailable. Its apparent bytes and
  the dedicated cache bytes are frozen for later accounting. All six source
  hashes match the accepted implementation; root A, root B, and receipt paths
  are absent; destructive targets have exact attempt-specific basenames. Five
  focused claim tests pass. The claim has one creation, zero consumptions, zero
  formal fits, and every official and forbidden counter at zero.
- Alternatives: Run directly from D-104; use the shared default uv cache;
  permit network during fitting; choose paths at execution time; combine claim
  creation and consumption; edit a source after claim; rerun a smoke; or retain
  mutable roots after publishing aggregate evidence.
- Reversal condition: Any parent, source, environment, cache, host, path,
  namespace, topology, resource, no-replace, cleanup, accounting,
  signed-integration, or post-main-CI defect revokes the claim before
  consumption. After consumption, any defect or interruption is terminal and
  cannot authorize a replacement attempt.

## D-106 — Reject EXP-M1 on the sole formal CPU resource proof

- Date: 2026-08-24
- Status: terminal G2-4C resource rejection; sole claim consumed; no official
  development or model-quality authority
- Decision: Accept aggregate rejection receipt
  `global_v2_m1_resource_rejection.json` at SHA-256
  `3222856d...54297`, bound to contract `f80a6e8d...48df7`, consumed claim
  `d6693d11...16497`, and all six D-104 source hashes. Reject `EXP-M1`
  permanently because its worse-root projection is 266.737 CPU-core-hours
  against the frozen 240 maximum. Do not retry, repair the observed warning,
  change device, threads, concurrency, epochs, fits, architecture, or losses,
  or shrink the experiment. Close G2-3 at fixed MapLight because the rejected
  `EXP-G1` supplies no selected recipe for parent-defined `EXP-G2`'s required
  anchor. Advance only to a contract-first G2-5 `EXP-X1` provenance and
  acquisition-feasibility freeze; acquire no external record before review.
- Evidence: The one authorized no-network attempt completed both sequential
  roots and all 32 full-width 300-epoch PyTorch fits in 823.469 measured root
  wall-seconds and 12,654.698 CPU-seconds. Root B reversed physical and launch
  order. The five scientific terminal files, all 2,430 model-double identities,
  all 75 loss-selection tokens, exact-repeat parameters/predictions, and every
  cross-root runtime identity matched. The final projection passes wall at
  17.207/38.4 hours, storage at 4.304/64 GB, RSS at 2.164/24 GiB, and GPU at
  0/0 hours, but fails CPU by 26.737 core-hours or 11.14%. Thirty-two identical
  PyTorch warnings reported non-writable NumPy-backed input tensors; the
  training path read/indexed those tensors without in-place mutation, but the
  frozen contract rejects any warning and no repair is authorized. The CPU
  miss independently determines rejection. Both public/private work roots and
  the dedicated cache were removed, no failure receipt exists, and every
  official, development-metric, confirmatory, historical-row, blinded-test,
  TDI, external, submission, official-metric, leaderboard-selection, and
  upload counter is zero. Therefore this result has no predictive-quality
  interpretation.
- Alternatives: Infer feasibility from the four tiny smokes; average the two
  roots; ignore import/startup or wrapper CPU; reduce epochs or fit identities;
  change affinity, concurrency, device, or PyTorch behavior; repair the warning
  and retry; execute M1 officially despite the failed precondition; substitute
  fixed MapLight silently for EXP-G2's selected-G1 anchor; or acquire external
  data before a source/provenance contract.
- Reversal condition: The consumed attempt and rejection are immutable and
  cannot be rerun. A receipt, source-binding, determinism, resource-arithmetic,
  warning-accounting, capability, or cleanup defect revokes evidentiary trust
  and stops the lane; it does not authorize replacement, repair, resume, move,
  overwrite, or official M1 execution.

## D-107 — Sanitize the public strategy-audit copy at the portal boundary

- Date: 2026-08-24
- Status: accepted privacy-only redaction; scientific strategy and immutable
  experiment contracts unchanged
- Decision: Publish only the sanitized strategy-audit copy at SHA-256
  `0b87f86e...0c10312` under redaction receipt SHA-256
  `8a738405...a23798`. Replace six occurrences of one private submission
  identifier with neutral prior-submission language. Preserve the original
  imported SHA-256 `88cfcb71...f79e` as immutable G2-0 lineage without
  changing `global_v2_experiment_contract.json` or any descendant contract,
  claim, result, or scientific decision. Validate the original receipt and
  sanitized public bytes separately through the redaction overlay.
- Evidence: A whole-current-tree scan found the private identifier only in the
  imported audit. The six replacements alter headings/prose/table labels only;
  no number, recommendation, experiment specification, acceptance gate,
  receipt, model result, or authority changed. Receipt accounting records six
  redactions, zero scientific contract/result changes, and zero private
  identifier/result values in the current tree.
- Alternatives: Leave the identifier in the public current tree; mutate the
  immutable G2-0 contract to pretend the source receipt never existed; discard
  the audit and its provenance; publish the private portal result; or rewrite
  signed repository history without explicit user authorization.
- Reversal condition: Any private identifier/result in the current tree,
  sanitized-copy hash mismatch, altered scientific meaning, mutated G2-0 byte,
  or false lineage claim revokes the redaction receipt and requires an
  immediate privacy repair. Historical Git erasure, if required, is a separate
  destructive operation requiring explicit user direction.

## D-108 — Reject the pre-contract EXP-X1 dataset-card preview path

- Date: 2026-08-24
- Status: rejected non-scientific G2-5 preflight; no external file or official
  operation
- Decision: Accept boundary-rejection receipt
  `global_v2_x1_prefreeze_preview_rejection.json` at SHA-256
  `6f0f063c...a5efc`. A documentation/schema request unexpectedly rendered at
  least 45 public external CYP3A4 record rows before the required EXP-X1 child
  contract existed, so reject that source-audit path against the zero-record
  precondition. Do not reopen, repair, or use its exposed identities,
  structures, values, ordering, or distribution. After reviewed integration
  and green post-main CI, permit only a separate metadata-only G2-5A freeze
  that binds this rejection, allowlists exact repository-metadata and
  protocol/license prose resources, selects at most one source, and exposes
  zero additional external records.
- Evidence: The response excerpts contained 45 record rows; the page may have
  rendered more internally, and exact reconstruction is unnecessary because
  any positive count rejects the preflight. No dataset file or byte was
  downloaded or written locally, no row value was copied to Git or an artifact
  or used for science, and no external structure/target hash, official input,
  fit, prediction, development metric, confirmatory or historical-row access,
  blinded-test or TDI access, submission, official metric, leaderboard
  selection, upload, or execution claim occurred. The receipt contains no
  public record value and makes no model-quality, overlap, support, or assay-
  transfer inference.
- Alternatives: Call the rendered rows metadata; claim zero external access;
  reconstruct or retain their values; use the preview to select or filter a
  source; continue directly to acquisition; or close EXP-X1 permanently even
  though no child contract, claim, external file, official input, fit,
  prediction, or metric existed.
- Reversal condition: Any exposed row value in the tracked receipt, scientific
  use of a previewed record, hidden local external file, false counter, repeat
  of the rejected browsing path, or official/forbidden operation revokes this
  containment decision and stops G2-5. A distinct reviewed metadata-only
  contract is not a retry of this rejected browsing operation.

## D-109 — Freeze ChEMBL 37 as the sole EXP-X1 source before acquisition

- Date: 2026-08-25
- Status: accepted contract-only G2-5A metadata evidence; zero new external
  record, official input, model or metric operation
- Decision: Freeze `global_v2_x1_provenance_contract.json` at SHA-256
  `a51f81a4...a21c1d`. Select only the exact ChEMBL 37 SQLite archive at
  frozen SHA-256 `33c20374...0d281` for all four exact Homo sapiens
  single-protein targets. Bind its 2026-05-01 release, DOI, CC BY-SA 3.0
  obligations, target identifiers, raw relation/censoring/assay/structure/
  document preservation, exact high-confidence IC50 eligibility, challenge-
  family exclusion, external/no-external ablation, weight rights, parent
  acceptance gates and 20%-margin resources before any acquisition. Require
  at least 1,000 novel eligible molecules per endpoint after global exact/
  equivalent challenge removal and 750 family-safe external components per
  endpoint in every outer cell. If any endpoint or integrity gate fails,
  reject EXP-X1 without another source, threshold change or model fit.
- Evidence: Release-directory, DOI, license/checksum prose and target metadata
  identify one immutable pre-challenge source covering CYP1A2, CYP2C9, CYP2D6
  and CYP3A4. The alternative OpenADMET compound summary is CYP3A4-only; with
  the other three endpoints fixed, it would require about 0.100 absolute
  CYP3A4 MAE improvement merely to deliver the parent's 0.025 macro gain.
  PubChem adds per-depositor mapping complexity, and third-party weights lack
  the required source/split/rights binding. No ChEMBL activity response or
  file was opened, no archive was downloaded, and no official input, fit,
  prediction, metric, confirmatory, blinded-test, submission, leaderboard-
  selection, upload or claim operation occurred.
- Alternatives: Acquire multiple sources before support is known; select the
  largest advertised row count; use the rejected preview; query moving
  ChEMBL activity APIs; permit censored/low-confidence/nonhuman rows; treat
  exact challenge duplicates as transfer evidence; choose thresholds after
  counts; use blinded-test similarity; or fit before a synthetic compiler and
  family-exclusion proof.
- Reversal condition: Any archive or activity record opened before a later
  integrated claim, checksum/release drift, unpreserved raw field, silent
  chemistry change, family crossing, support-threshold alteration, added
  source or weight, false zero counter, official/blinded-test access, or
  leaderboard-driven choice revokes the contract and rejects EXP-X1. The next
  gate is synthetic compiler/leakage mechanics, not acquisition.

## D-110 — Freeze the EXP-X1 synthetic compiler and ghost-node leakage proof

- Date: 2026-08-25
- Status: accepted contract-only G2-5B design; zero synthetic, external,
  official, model, metric or submission operation
- Decision: Freeze `global_v2_x1_synthetic_compiler_contract.json` at SHA-256
  `db36935e...a3442`. Permit one isolated read-only SQLite compiler, one
  synthetic driver and focused tests in the locked Python 3.12.3/RDKit
  2026.3.5 runtime. Preserve every raw joined ChEMBL field before assigning one
  ordered eligibility reason; accept only exact high-confidence human IC50
  rows; recompute core standardized structures and fourteen-character standard
  InChI connectivity blocks; and reuse the exact inclusive D-032 radius-2,
  4,096-bit chiral Morgan/Tanimoto 0.60 union graph. Remove values from exact/
  equivalent external matches globally but retain those structures as label-
  free ghost connectors. Exclude every external component touching held-out
  outer, outer-plus-inner, or confirmatory challenge nodes. Count only unique
  safe standardized molecules and union components per endpoint/cell.
- Evidence: The prospective two-root fixture has 84 external compounds and 336
  activity rows per root, of which 320 rows on 80 structures pass eligibility.
  Ten exact and ten connectivity-equivalent external identities are globally
  forbidden, leaving 60 novel structures per endpoint. With twenty balanced
  challenge components, each outer cell must retain 52 external molecules in
  36 components and each scoped inner cell 44 molecules in 32 components.
  Opposite table insertion and file order must change SQLite file hashes while
  every logical and terminal byte matches. The miniature 50/35 mechanics gate
  passes but the parent 1,000/750 gate fails on the same counts, proving no
  synthetic authority escalation. Eleven focused static tests pass. No
  synthetic fixture or SQLite file was created, and no real ChEMBL activity,
  official input, fit, prediction, metric, confirmatory truth, historical row,
  blinded test, submission, leaderboard-selection, upload or claim operation
  occurred.
- Alternatives: Query activity records before implementation proof; trust
  ChEMBL canonical structures or InChIKeys; aggregate replicates in SQL; use
  rowid or implicit query order; discard exact duplicates before topology;
  compare only challenge-to-external pairs; use approximate neighbors,
  pairwise-only exclusion or strict `>0.60`; reassign frozen challenge folds;
  count activities as support; or let miniature thresholds replace the parent
  gate.
- Reversal condition: Any unpreserved field, missing filter row, source-trusted
  chemistry, removed ghost connector, incomplete unordered-pair graph,
  nontransitive family, fold reassignment, activity-based support, threshold
  change, nondeterministic terminal, false zero counter, real external or
  official access, model/metric operation, or leaderboard-driven choice
  revokes this contract and rejects G2-5B. A future acquisition still requires
  separate reviewed synthetic acceptance and a separate integrated single-use
  claim.

## D-111 — Accept deterministic EXP-X1 compiler and ghost-node mechanics

- Date: 2026-08-25
- Status: accepted synthetic-only G2-5B implementation; zero real external,
  official, model-quality, submission or claim operation
- Decision: Accept `global_v2_x1_synthetic_compiler_acceptance.json` at
  SHA-256 `5ea379d1...001a8`. Bind compiler `34ea893e...bf77e`, driver
  `b10bdee8...0305d`, focused tests `b05e5eb6...c85e3`, the unchanged core
  chemistry/topology sources and root lock. Two sequential roots with opposite
  SQLite and CSV insertion order had different physical SQLite hashes but
  byte-identical logical source and seven-file terminal maps at tree SHA-256
  `a5e7d2d3...88111`. Accept the compiler, filter, recomputed chemistry,
  exact/equivalent ghost-node, exhaustive inclusive similarity, transitive
  exclusion, cell capability, support-decision, determinism, cleanup and
  no-replace mechanics only. Keep archive acquisition unauthorized until a
  separate reviewed single-use claim is integrated and green.
- Evidence: Per root, 320 of 336 activity rows on 80 standardized external
  structures passed the exact ordered eligibility filter. Ten exact and ten
  connectivity-equivalent matches lost their values globally but remained as
  topology connectors. The union contained 110 nodes, 157 qualifying
  similarity edges and 40 components after 5,995 unordered-pair comparisons.
  Every endpoint had 60 novel structures; every outer cell retained 52
  molecules in 36 components, every scoped-inner cell 44 in 32, and each
  confirmatory cell 52 in 36. The synthetic 50/35 gate passed and the immutable
  1,000/750 support gate failed. Twenty-one focused implementation tests passed,
  including exact 0.60 inclusion and schema, join, path, integrity, fold,
  chemistry, graph, accounting, cleanup and publication adversaries. Aggregate
  accounting is two synthetic SQLite files, 672 opened synthetic rows and
  11,990 comparisons. All disposable roots were removed; every real external,
  official, fit, prediction, metric, confirmatory-truth, historical-row,
  blinded-test, TDI, submission, leaderboard-selection, upload and claim
  counter is zero. MapLight evidence remains 0.5838 internal component-macro
  MAE; this synthetic result neither evaluates nor improves it.
- Alternatives: Trust source chemistry or InChIKeys; remove forbidden nodes
  before graph construction; compare challenge/external pairs only; use
  pairwise rather than transitive exclusion; use strict `>0.60`; count activity
  rows as support; accept one physical order; retain mutable roots; treat the
  miniature gate as acquisition evidence; download ChEMBL immediately; or fit
  before support falsification.
- Reversal condition: Any mismatch in the tracked source hashes, receipt,
  logical/terminal equivalence, filter accounting, graph, support oracle,
  cleanup or zero counters; any real external/archive or official access before
  a later integrated claim; any model or metric operation; any support-threshold
  change; or any leaderboard-driven source/model choice revokes this acceptance
  and rejects EXP-X1. The next gate is a contract-only single-use ChEMBL 37
  acquisition claim, not archive access.

## D-112 — Freeze the single-use EXP-X1 acquisition claim behind an adapter gate

- Date: 2026-08-25
- Status: accepted claim-only G2-5C freeze; immutable and unconsumed; zero
  archive, external-record, official, model-quality, submission or upload
  operation
- Decision: Freeze `global_v2_x1_acquisition_claim.json` at SHA-256
  `f1bea832...1ba5c60`. Bind the accepted D-109 through D-111 parents and six
  unchanged source hashes; the exact ChEMBL 37 SQLite URL, release, DOI,
  license and archive SHA-256; one fixed absent attempt root and one retained
  aggregate-receipt root; the exact frozen R2B source receipts and label-free
  structure/fold capability for 4,905 training molecules; checksum before
  listing or extraction; exact
  Homo-sapiens single-protein target verification before activity query;
  immutable read-only SQLite; and no-network extraction, compilation and
  support publication. Permit at most one future download and one consumption,
  with no retry, resume, mirror, alternate format, source repair, threshold
  change, partial reuse or second attempt. Freeze a one-shot ceiling of 640
  CPU-core-hours, 120 wall-hours, 160 GB restricted storage, 64 GiB peak RSS,
  zero GPU-hours and one process. Keep the claim unconsumable until one additive
  real-source adapter, acquisition wrapper and official-shaped synthetic driver
  pass a separately reviewed two-root acceptance and bind all null future fields
  in a private consumed-claim receipt.
- Evidence: The claim's nine focused tests authenticate the exact claim bytes,
  parents, accepted sources, archive identity, null adapter bindings, narrow
  paths, checksum/network/read boundaries, targets, conjunctive 1,000/750
  support gate, parent-bounded resources, cleanup, authority and zero counters.
  The fixed attempt and receipt roots are absent. Fifty focused D-109 through
  D-112 tests pass with Ruff and mypy clean. Only existing receipt strings for
  the future challenge capability were authenticated; no source file was opened.
  No archive request, path, external
  record, activity query, official input, fit, prediction, metric, confirmatory
  truth, historical row, blinded test, TDI, submission, official metric,
  leaderboard selection or upload occurred. MapLight remains 0.5838 internal
  component-macro MAE; this claim has no model-quality meaning.
- Alternatives: Download immediately after claim integration; label the
  synthetic-only compiler as real-source capable; consume the one-shot claim
  before the adapter is accepted; allow range retries or mirrors; verify the
  checksum after extraction; open SQLite read-write; inspect activities before
  target verification; retain raw external rows in Git; change support gates
  after counts; or fit before support falsification.
- Reversal condition: Any changed parent/source/archive byte, pre-adapter claim
  consumption, archive or activity access before integrated acceptance,
  non-atomic or second download, alternate source, checksum-after-inspection,
  network-enabled compilation, writable database, target mismatch, source or
  threshold repair, official-input access, model/metric operation, incomplete
  cleanup, row-level publication, false zero counter, or leaderboard-driven
  choice revokes the claim and rejects EXP-X1. The next gate is the minimal
  real-source adapter's official-shaped synthetic acceptance, not acquisition.

## D-113 — Accept the EXP-X1 real-source adapter behind the unconsumed claim

- Date: 2026-08-25
- Status: accepted official-shaped synthetic G2-5D mechanics; tracked claim
  unchanged and unconsumed; zero real archive, external-record, official,
  model-quality, submission or upload operation
- Decision: Accept `global_v2_x1_real_source_adapter_acceptance.json` at
  SHA-256 `c29aaaf4...33f3fb4`. Add only one real-source adapter, one acquisition
  wrapper, and one official-shaped synthetic driver. Reuse the accepted G2-5B
  SQLite query, ordered filter, standardizer, equivalence rule, D-032 union
  graph, ghost-node firewall, and support falsifier without modifying their
  source. Authenticate the exact R2B file set while decoding only the first
  eight direct-observation fields through raw SMILES; discard every target-
  bearing suffix byte without decoding or retention. Reuse accepted outer and
  inner component folds exactly. Bind one nonredirecting HTTPS GET, full
  archive checksum before tar listing, regular nontraversing members, one
  extracted database, no-network extraction/compilation, one process,
  aggregate-only publication, and complete restricted-root cleanup. Keep the
  tracked D-112 claim immutable and unconsumed until reviewed integration and
  green post-main CI.
- Evidence: Two fresh official-shaped synthetic roots reversed physical SQLite
  insertion and R2B row order. Their SQLite and R2B hashes differed, while all
  seven terminal files matched byte-for-byte at tree SHA-256
  `7789290d...8f6b8a`. Per root, 336 synthetic activity rows produced 320
  eligible and 16 rejected rows; 160 observation records yielded 40 challenge
  molecules in 20 components; all 160 suffixes were discarded; zero target
  values were parsed or retained; and the union/support oracles remained 110
  nodes, 40 components, outer 52/36, inner 44/32, and confirmatory 52/36. The
  miniature 50/35 gate passes and the real 1,000/750 gate fails as designed.
  Twenty-two focused adversarial tests cover identity drift, endpoint
  cardinality, receipt/file-mode/file-set failures, component outer/inner
  crossings, poisoned target bytes, checksum-before-listing, traversal,
  symlink, duplicate/multiple database members, one-request/no-range download,
  exact claim derivation, tamper rejection, no-replace behavior, and cleanup.
  No real archive request, external row, official input, fit, prediction,
  metric, submission, leaderboard selection, upload, or claim consumption
  occurred. Fixed MapLight remains 0.5838 internal component-macro MAE.
- Alternatives: Reuse the synthetic-only top-level compiler by relabeling it;
  parse the full direct-observation CSV; trust target-bearing suffix topology;
  regenerate folds; change the accepted compiler; allow redirects, range
  requests, resume, mirrors, unsafe extraction, or networked compilation;
  consume the claim before integration; publish restricted row-level outputs;
  or represent synthetic support as model-quality evidence.
- Reversal condition: Any changed accepted compiler, adapter, wrapper, driver,
  test, schema, chemistry, topology, firewall, lock, claim or acceptance byte;
  any decoded target suffix; component reassignment; unverified or repeated
  request; checksum-after-listing; unsafe archive member; network-enabled
  compilation; incomplete cleanup; row-level publication; false zero counter;
  pre-integration claim consumption; or leaderboard-driven source/model choice
  revokes this acceptance and rejects EXP-X1. The next gate is reviewed signed
  integration and green post-main CI, then the sole private claim consumption
  and frozen support falsifier—not model fitting.

## D-114 — Reject EXP-X1 after the sole acquisition fails schema preflight

- Date: 2026-08-25
- Status: terminally rejected after one consumed claim and one exact archive
  download; cleanup complete; zero activity-row, official-input, fit,
  prediction, metric, submission, or upload operation
- Decision: Accept `global_v2_x1_acquisition_failure.json` at SHA-256
  `ac08140b...50e4eb2` as the terminal aggregate record and close `EXP-X1`.
  The exact 5,764,252,857-byte ChEMBL 37 archive passed the frozen SHA-256
  before listing, safe extraction produced one 30,480,314,368-byte read-only
  SQLite database, and offline integrity checking passed. Schema preflight then
  rejected `assays` before the activity query. Do not retry, resume, mirror,
  repair the source contract, change support thresholds, retain partial inputs,
  or fit an external-transfer model under this lane.
- Evidence: The sealed private aggregate receipt has SHA-256
  `47e26624...80b56f`, status `G2_5C_X1_ACQUISITION_FAILED`, consumed-claim
  SHA-256 `245ed65c...135275`, cleanup complete, read-only file mode, and no
  row-level content. The fixed attempt root is absent. Public compiler audit
  identifies the contract defect: synthetic fixtures exposed API-style aliases
  (`assay_chembl_id`, `target_chembl_id`, and `doc_chembl_id`) as physical
  columns, while the ChEMBL SQLite tables use `chembl_id`. Integrity therefore
  passed but the required-column subset failed before `SOURCE_QUERY`. One
  archive was downloaded; zero external activity rows, external target values,
  official structures/features/targets, fits, predictions, development metrics,
  confirmatory values, historical rows, blinded-test rows, TDI rows, submission
  rows, official metric calls, leaderboard selections, or uploads occurred.
  Fixed MapLight remains 0.5838 internal component-macro MAE.
- Alternatives: Patch the aliases and reuse the deleted archive; issue a second
  claim or request; resume from the extracted database; select a mirror or
  alternate external source; relax the no-retry rule; infer support from public
  summaries; or proceed to fitting without the frozen 1,000/750 falsifier.
- Reversal condition: None within `EXP-X1`. The claim is consumed and the
  no-retry boundary is part of the preregistered evidence. A future external
  hypothesis must be scientifically distinct, separately contracted, and may
  not reinterpret or reuse this failed attempt. The next gate is reviewed
  integration of this failure record, followed by an audit of remaining frozen
  lanes for the smallest distinct hypothesis targeting the MapLight error
  profile without using private portal observations for selection.

## D-115 — Do not activate EXP-T2 without stronger global OOF evidence

- Date: 2026-08-25
- Status: terminal nonactivation; aggregate evidence audit only; zero row-level,
  official-input, model-quality, submission, or upload operation
- Decision: Accept `global_v2_t2_not_activated.json` at SHA-256
  `75eb8d10...0f59c98` and do not draft, implement, or execute `EXP-T2`. The
  Global-v2 contract and D-085 require a stronger global successor with fully
  cross-fitted OOF residuals and a positive improvement-versus-coverage region
  frozen before selecting a local learner or threshold. Fixed MapLight is the
  stable baseline and cannot serve as its own stronger successor. Searching its
  row-level residuals now for a favorable competence region would reverse the
  preregistered activation order.
- Evidence: The receipt binds the Global-v2 contract `612b8cea...e5c0d`,
  MapLight reproduction `76775030...a4482`, G1 resource rejection
  `67585830...a9be4`, M1 resource rejection `3222856d...54297`, and X1
  acquisition failure `ac08140b...50e4eb2`. Accepted stronger global
  successors, stronger-successor OOF receipts, and positive improvement-
  versus-coverage receipts are each zero. G1 and M1 produced zero scientific
  OOF predictions before resource rejection; parent-defined G2 is unavailable
  without its required G1 anchor; X1 produced zero scientific OOF predictions
  before schema preflight failed. The audit opened zero row-level MapLight or
  R5D artifacts, official inputs, confirmatory truth, blinded test, or TDI;
  computed zero fits, predictions, residuals, or metrics; and generated zero
  submission rows, official metric calls, leaderboard-driven selections, or
  uploads. The result is an activation decision, not model-quality evidence.
- Alternatives: Treat MapLight as a stronger successor to itself; inspect its
  row-level residuals and choose a favorable coverage threshold now; reinterpret
  resource-rejected G1/M1 or unavailable G2 as scientific OOF evidence; reuse
  R5D row losses; or let a private portal observation choose the local learner,
  threshold, representation, or candidate.
- Reversal condition: None within `EXP-T2` under Global-v2. Later evidence from
  a separately contracted stronger global system cannot retroactively activate
  or reinterpret this closed lane. The next gate is a new named, prospective
  single-expert global hypothesis testing one fixed representation-diverse
  learner against MapLight; it may not repair G1, instantiate parent-defined
  G2, or use private portal evidence for selection.

## D-116 — Freeze one deterministic LightGBM expert as EXP-G3

- Date: 2026-08-25
- Status: accepted contract-only Global-v2 recovery lane; zero dependency,
  runtime, implementation, official-input, fit, prediction, metric, submission,
  leaderboard-selection, upload, or claim operation
- Decision: Accept `global_v2_g3_single_expert_contract.json` at SHA-256
  `ee2725ba...5da47`. Test exactly one deterministic LightGBM 4.7.0 L1 expert
  against immutable fixed MapLight on the accepted 3x5 family-safe development
  outer folds. Use 2,048 chiral radius-2 Morgan-count columns followed by the
  accepted 200 RDKit descriptor columns. Preserve descriptor NaN for native
  missing routing and perform no imputation, scaling, selection, blend, grid,
  early stopping, extra seed, or endpoint-specific parameter. Freeze one seed,
  all 1,500 trees, full rows and features, forced col-wise histograms, exact
  package/wheel receipts, and one 16-thread fit at a time. The exact workload is
  60 fits, 46,896 predictions, zero inner-selection fits, and zero baseline
  refits.
- Evidence: G1 required 8,820 fits and failed its sole resource falsifier before
  official execution; M1's 2,430-fit lane also failed CPU before official
  execution; parent-defined G2 cannot instantiate its required G1 anchor; X1
  failed before its activity query; and T2 did not activate. A single fixed
  expert is therefore the smallest untested global representation/learner
  diversity hypothesis. The exact LightGBM 4.7.0 manylinux wheel is bound at
  SHA-256 `d23e922...57ebb7`; the project runtime remains unchanged. Promotion
  requires every member: at least 3% pinned tutorial-primary and 0.015 absolute
  component-macro MAE improvement, paired upper 95% bound below zero, at least
  8/15 favorable cells, no endpoint harm above 0.015, and at least 0.010 gain
  on CYP1A2 or CYP2D6. A later two-root synthetic and real-fit probe must pass
  20%-margin CPU, wall, storage, RSS, and zero-GPU resource gates before any
  execution claim. Eight focused static tests pass. This freeze opened no
  official or private row and produced no model-quality evidence.
- Alternatives: Repair or shrink G1/M1; instantiate parent-defined G2 without
  its anchor; add multiple LightGBM seeds, a parameter grid, early stopping,
  XGBoost, Avalon/ErG/Mordred/embedding blocks, learned stacking, or a fixed
  MapLight blend; use external data; mine MapLight residuals; or select any
  choice from private portal evidence.
- Reversal condition: Any changed parent, feature, runtime, package, parameter,
  seed, thread count, fold, mask, fit identity, acceptance gate, resource bound,
  capability, or forbidden-data counter revokes the contract before execution.
  A clean scientific miss closes EXP-G3 without repair. The next gate is a
  separately reviewed deterministic-runtime and synthetic-implementation
  contract; only that milestone may create an isolated LightGBM research lock,
  and it still cannot open official input or create an execution claim.

## D-117 — Freeze the EXP-G3 synthetic determinism and resource falsifier

- Date: 2026-08-25
- Status: accepted contract-only isolated-runtime and synthetic gate; zero
  environment, dependency, implementation, fit, prediction, metric, official-
  input, claim, submission, leaderboard-selection, or upload operation
- Decision: Accept `global_v2_g3_synthetic_contract.json` at SHA-256
  `6ec0e73b...da4f9f`. After reviewed integration and green post-main CI,
  permit one isolated `research/lightgbm-global` lock, one direct typed runner,
  one synthetic driver, narrow tests, at most two 64-row/16-round API smokes,
  and one formal two-root acceptance. The model double must exhaust all sixty
  family-safe fit identities per root before scorer truth opens. Four exact
  1,500-tree LightGBM fits per root must use full-width 3,908x2,248 synthetic
  matrices and match resolved parameters plus every canonical float64
  prediction byte. Do not add an official compiler, execution wrapper, claim,
  second runtime, optimization, grid, model, feature, or workflow framework.
- Evidence: The two roots reverse every physical input row and fit-stage order
  before canonical parsing. Across roots the frozen counts are 120 model-double
  identities, 1,920 model-double outer predictions, eight real LightGBM fits,
  and 6,304 real probe predictions. Seven scientific terminal files must match
  byte-for-byte; root-specific resource timings remain outside that
  deterministic map. The probe uses 3,120 labeled training rows to exceed any
  official endpoint support without opening an official row. Resource
  projection multiplies all 60 future fits by the worse root's maximum
  individual exact-fit wall and CPU cost, adds worse non-fit overhead, counts
  the isolated environment/cache/work root, and uses maximum RSS. Every
  20%-margin gate is conjunctive: at most 128 CPU-core-hours, 19.2 wall-hours,
  25.6 GB restricted storage, 19.2 GiB RSS, and exactly zero GPU. Ten focused
  static tests pass. This freeze creates no model-quality evidence.
- Alternatives: Time a tiny or narrow matrix; average roots or fits; subtract
  probe overhead; use sparse input only for timing; reduce tree count; change
  threads; omit environment/cache/RSS; trust deterministic flags without a
  cross-root byte comparison; implement official access before mechanics;
  create a claim now; or allow retry or repair after a formal miss.
- Reversal condition: Any changed parent, runtime, wheel, lock, fixture,
  feature formula, model parameter, fit identity, terminal, projection,
  resource limit, cleanup, capability, or forbidden counter revokes the gate.
  A formal integrity or resource miss permanently closes EXP-G3. The next gate
  is the reviewed isolated implementation and sole formal two-root synthetic
  acceptance; official inputs and claim creation remain unauthorized.

## D-118 — Accept EXP-G3 synthetic determinism and resource feasibility

- Date: 2026-08-25
- Status: accepted synthetic implementation and sole formal attempt; zero
  official-input, scientific-model, development-metric, confirmatory,
  submission, leaderboard-selection, upload, or claim operation
- Decision: Accept `global_v2_g3_synthetic_acceptance.json` at SHA-256
  `437f17f6...721ed5`. The isolated exact Python 3.12.3/LightGBM 4.7.0
  implementation satisfies D-117. Two bounded API smokes and two sequential
  no-network formal roots completed without warning, fallback, or nonzero exit.
  The opposite-order roots matched all seven terminal files byte-for-byte at
  tree SHA-256 `5e4edc47...3df8e8`, covering 120 model-double fits, 1,920
  model-double predictions, eight exact 1,500-tree full-width fits, and 6,304
  real-runtime probe predictions. Permit only a later separately reviewed
  single-use official development execution contract and immutable unconsumed
  claim; this receipt itself opens no official capability.
- Evidence: Both 64-row smokes produced the same 16 finite prediction bytes and
  exact resolved parameters. The formal roots used 3,908x2,248 dense float64
  matrices with descriptor NaN preserved, 3,120 training rows, 788 prediction
  rows, four endpoints, reversed physical/launch order, and one resolved
  parameter hash. The conservative 60-fit projection is 1.171 CPU-core-hours,
  0.0794 wall-hours, 6.612 GB restricted storage, 0.310 GiB peak RSS, and zero
  GPU versus maxima of 128, 19.2, 25.6, 19.2, and zero. Component crossings,
  confirmatory values parsed, warnings, fallbacks, and nonzero exits are all
  zero. Both scientific roots, private roots, and the dedicated cache were
  deleted. Twenty-five combined contract/implementation/acceptance tests pass;
  the full repository suite, Ruff, mypy, and package build pass. Synthetic
  metrics and predictions have no model-quality meaning.
- Alternatives: Treat the smokes as timing evidence; skip the full-width probe;
  average fit costs; retry or optimize after a miss; add a second runtime,
  thread count, sparse representation, tree count, seed, or parameter; open
  official inputs under the synthetic receipt; create an execution claim before
  freezing its contract; or use a private portal result to alter the lane.
- Reversal condition: Any later discovery that the tracked receipt, source
  bindings, exact lock, terminal parity, family containment, resolved
  parameters, resource formulas, cleanup, or zero forbidden counters are false
  revokes progression before official access. The completed formal attempt is
  never rerun or repaired. Otherwise the next gate is one contract-only
  milestone freezing the exact single-use official development execution and
  unconsumed claim; no official row opens until that milestone is integrated
  and green on post-main CI.

## D-119 — Freeze the single-use EXP-G3 development execution

- Date: 2026-08-25
- Status: accepted contract and immutable unconsumed claim only; zero official
  source-row, target, feature, baseline-prediction, fit, prediction, metric,
  submission, leaderboard-selection, upload, or claim-consumption operation
- Decision: Accept `global_v2_g3_execution_contract.json` at SHA-256
  `be9dccf0...f87e57` and its tracked immutable claim template at SHA-256
  `71fc0231...25f9b`. The sole future development attempt is fixed at 60 exact
  LightGBM fits, 46,896 candidate outer predictions, and zero baseline refits.
  The tracked claim is unusable because four future official compiler, wrapper,
  synthetic-driver, and acceptance receipts remain null. Those receipts may be
  filled only in one private canonical derivative after a later reviewed,
  integrated official-shaped synthetic acceptance.
- Evidence: The contract binds D-116, D-117, D-118, the immutable MapLight
  reproduction, accepted implementation/runtime hashes, existing aggregate
  source receipts, 3,908 development molecules in 3,640 components, exact
  structure reconstruction, 2,048 chiral Morgan-count and 200 accepted
  descriptor columns, fixed folds and parameters, one-at-a-time sixteen-thread
  execution, prediction freeze before scorer access, paired MapLight identity,
  24 local tutorial calls, 2,000 accepted component-bootstrap replicates, all
  six promotion-gate families, aggregate-only terminals, hard resources, and
  cleanup. Ten focused static tests pass. The fixed attempt root was absent at
  freeze; no official source root was listed or opened.
- Alternatives: Open official inputs directly under D-118; reuse the synthetic
  driver as an official compiler; create a usable claim before binding future
  adapter hashes; recompute descriptors; use accepted Morgan arrays instead of
  reconstructing from authenticated structures; expose validation truth or
  baseline predictions before candidate freeze; tune from outer evidence;
  permit retry, repair, resume, move, overwrite, or private portal selection.
- Reversal condition: Any changed parent, receipt, source identity, family
  assignment, structure, feature, parameter, fit identity, capability,
  prediction-freeze, paired join, metric, bootstrap, gate, resource, terminal,
  cleanup, publication, accounting, or authority revokes progression before
  official access. Otherwise the next gate is an additive official compiler,
  single-use wrapper, official-shaped synthetic driver, and two fresh
  opposite-order synthetic roots. Bind their reviewed hashes in one aggregate
  acceptance before consuming a private claim; open no official byte in that
  milestone.

## D-120 — Accept EXP-G3 official-shaped execution mechanics

- Date: 2026-08-25
- Status: accepted official-shaped synthetic implementation evidence; tracked
  claim unchanged and unconsumed; zero official or forbidden operation
- Decision: Accept `global_v2_g3_execution_synthetic_acceptance.json` at
  SHA-256 `4bdc758a...2636`. Bind compiler `fbac206c...fde5`, wrapper
  `318c0780...db1b`, driver `924a328b...e73b`, accepted G3 runner
  `a639c2f2...3415`, and research lock `b110c1b6...152c`. Permit only reviewed
  integration and green post-main CI before one exact private four-field claim
  derivative and the sole fixed official development attempt.
- Evidence: Two fresh 1,200-molecule/600-component roots ran in separate
  no-network execution, with the second reversing physical source order. All
  six terminal files matched byte-for-byte at tree SHA-256
  `d137623f...6516`. Per root, 960 development molecules in 480 components
  traversed 60 model-double fits and 11,520 predictions; 240 confirmatory
  molecules remained opaque; the 11,520-row synthetic baseline opened only
  after prediction freeze; 24 tutorial calls and 2,000 accepted paired
  component-bootstrap replicates completed. Both exact full-width 1,500-tree
  runtime controls matched. Fourteen focused adversarial tests cover lineage,
  chemistry, NaN-preserving features, family boundaries, least privilege,
  baseline chronology, atomic no-replace publication, status-specific
  terminals, exact claim derivation, tamper rejection, and no replacement.
  Private roots retained, claim consumptions, official operations, and every
  forbidden counter are zero. Synthetic promotion values have no model-quality
  interpretation.
- Alternatives: Open the official source during adapter development; trust one
  physical order; expose validation truth or baseline to the model stage;
  publish candidates non-atomically; omit failure/underpowered terminals; fill
  more than the four frozen claim fields; consume the claim before reviewed
  integration; or let private portal evidence select or repair the model.
- Reversal condition: Any source, parent, chemistry, family, feature, runtime,
  capability, fit, prediction-freeze, baseline chronology, metric, bootstrap,
  gate, atomic publication, terminal, cleanup, claim, accounting, or authority
  drift revokes progression before official access. Otherwise integrate these
  exact bytes, require green post-main CI, then consume and execute the sole
  official development attempt once with no retry, resume, move, overwrite, or
  repair.

## D-121 — Close EXP-G3 after its terminal pre-fit official failure

- Date: 2026-08-25
- Status: accepted aggregate-only terminal failure; sole claim consumed; zero
  source rows, fits, predictions, baseline rows, metrics, bootstrap replicates,
  submissions, leaderboard-selection operations, or uploads
- Decision: Accept `global_v2_g3_official_failure.json` at SHA-256
  `ab12c742...0e28a5` as the complete public record of the one authorized
  attempt. Reject EXP-G3 as an execution path without retry, resume, repair,
  source-shape relaxation, replacement execution, or model-quality claim.
  Retain fixed MapLight as the best validated system at 0.5838 internal
  development component-macro MAE and proceed only to a separately frozen G2-7
  robustness/primary-contender gate.
- Evidence: The private claim was consumed exactly once and a read-only
  aggregate terminal was atomically published. Exact authority equality failed
  before any source leaf or row opened because the immutable accepted source
  has an older 12-key authority vocabulary and the D-120 synthetic source has a
  new 15-key vocabulary; their shared permissions agree. Aggregate receipt
  comparison also reveals an unreached mismatch where three denied-array
  receipts are valid metadata but the compiler required them to be absent.
  Completed fits, predictions, baseline-row opens, tutorial calls, bootstrap
  replicates, and metrics are all zero; cleanup is complete and every forbidden
  counter is zero. Four focused public-record tests pass.
- Alternatives: Repair or relax the compiler and rerun; replace the consumed
  claim; reinterpret the failure as evidence against the LightGBM hypothesis;
  open private row-level work to diagnose further; select a model from portal
  evidence; or advance directly to confirmatory scoring.
- Reversal condition: None inside EXP-G3. Its single-use authority is exhausted.
  A future independent experiment would require a materially new hypothesis and
  contract, but no such experiment is currently authorized. The next gate is a
  contract-only fixed-MapLight robustness freeze before confirmatory access.

## D-122 — Freeze fixed MapLight robustness and primary-contender selection

- Date: 2026-08-25
- Status: accepted contract-only G2-7 evidence; zero official source row,
  target, feature, historical-row artifact, fit, prediction, metric, claim,
  confirmatory-truth, test, TDI, submission, leaderboard-selection, or upload
  operation
- Decision: Accept `global_v2_maplight_robustness_contract.json` at SHA-256
  `ad9aef87...a7a45af`. Keep exact full fixed MapLight as the default contender.
  Permit only four prospectively named drop-one feature recipes, and select at
  most one only after all stage-A predictions freeze through the exact
  material-improvement, paired-interval, 8/15-cell, endpoint-harm, and Occam
  ordering. No seed, grouping overlay, clipping diagnostic, portal observation,
  or runner-up may change that token.
- Evidence: The contract binds D-084, D-094, D-121, the accepted official
  reproduction and deployment recipes, exact source/feature/OOF receipts,
  Python 3.12.3/RDKit 2026.03.5 trusted compilation, and the isolated Python
  3.10.13/CatBoost 1.2.1 model runtime. Stage A requires 240 drop-one and 300
  full-feature seed fits. Stage B runs the selected recipe under 0.55 and 0.50
  conservative component thresholds plus one canonical-tautomer overlay for
  180 fits. A selected deletion conditionally requires 300 additional seed
  fits. Duplicate collapse, fixed top-ten influence removal, authenticated
  single-source handling, endpoint harm, and two training-only clipping views
  add no fit. Thus the exact later workload is 720–1,020 fits and
  562,752–797,232 predictions, with every prediction frozen before its scorer
  opens validation truth. Seven focused static tests pass. Private portal status
  assertions were neutralized without recording any identifier, result, or
  rank.
- Alternatives: Treat the existing candidate as robust without falsification;
  reopen G1/G3; select a seed or clip from development outcomes; test arbitrary
  block combinations; weaken family groups; let a perturbed group replace the
  primary D-032 boundary; invent assay-source labels; open confirmatory truth;
  or let private portal evidence choose the contender.
- Reversal condition: Any parent, source, runtime, chemistry, family,
  confirmatory-membership, feature, parameter, seed, fit, prediction-freeze,
  metric, bootstrap, selection, diagnostic, resource, terminal, privacy, or
  authority drift revokes progression before official access. Otherwise the
  next gate is a separately frozen two-root synthetic implementation/resource
  contract for this exact staged topology; do not create a claim or open an
  official byte in that milestone.

## D-123 — Freeze MapLight robustness synthetic mechanics and resources

- Date: 2026-08-25
- Status: accepted contract-only G2-7B evidence; zero implementation, runtime
  creation, synthetic source, model-double invocation, CatBoost fit,
  prediction, metric, official row, claim, confirmatory truth, historical row,
  blinded test, TDI, external record, submission, official metric,
  leaderboard-selection, private-portal record, or upload operation
- Decision: Accept
  `global_v2_maplight_robustness_synthetic_contract.json` at SHA-256
  `97b982fa...e2abfd`. Before any scientific claim or input can exist, require
  two fresh sequential roots to exercise both exact conditional paths with a
  deterministic model double: 720 invocations when full MapLight remains the
  selection and 1,020 when the sole engineered eligible deletion triggers the
  300-invocation conditional seed stage. Root B reverses every physical input
  and dependency-safe launch order. All eight terminal files must match
  byte-for-byte.
- Evidence: The contract binds D-122 and its green post-main CI run
  `32868137658`, the accepted synthetic firewall, both MapLight synthetic
  acceptances, the aggregate official reproduction, and exact compiler/model
  runtimes. Across both roots the model double must traverse 3,480 fit
  identities and 666,432 prediction rows. The mechanics fixture contains 600
  two-molecule components, 960 development molecules, three explicit
  conservative overlays, label-free confirmatory-touch exclusions, duplicate,
  influence, single-source, endpoint, and clipping oracles, but no confirmatory
  target. Exactly 26 real CatBoost fits cover all five ordered feature views,
  four unique column counts, all six seed forms, and all four primary/overlay
  index forms. A full-size synthetic
  no-fit traversal covers 797,232 maximum-branch prediction identities; the
  resource projection multiplies 1,020 by the worse maximum individual fit and
  adds worse-root non-fit overhead. Every gate is capped at 80% of D-122:
  128 CPU-core-hours, 7.68 wall-hours, 51.2 GB restricted storage, 15.36 GiB
  RSS, and zero GPU. Ten focused static tests pass.
- Alternatives: Implement directly from D-122; exercise only the likely
  full-retained branch; run all 2,040 real CatBoost fits across two synthetic
  roots; time only full width or average fit duration; shrink official support
  gates for the fixture; omit confirmatory-touch exclusions; allow an overlay
  or clip to revise selection; create the official claim alongside synthetic
  mechanics; or use private portal evidence in an oracle.
- Reversal condition: Any parent, runtime, feature, seed, family, overlay,
  support, capability, chronology, branch, fit/prediction identity, numeric,
  selection, diagnostic, resource, terminal, cleanup, privacy, or authority
  drift revokes progression. Otherwise the next gate is the exact additive
  implementation and one formal two-root synthetic acceptance after reviewed
  signed integration and green post-main CI; official and confirmatory access
  remain closed.

## D-124 — Reject the MapLight robustness synthetic resource path

- Date: 2026-08-25
- Status: accepted terminal negative G2-7B evidence; sole formal attempt
  completed; zero official source row, target, feature, fit, prediction,
  development metric, claim, confirmatory truth, historical row, blinded test,
  TDI, external record, submission, official metric, leaderboard-selection,
  private-portal record, or upload operation
- Decision: Accept aggregate rejection
  `global_v2_maplight_robustness_synthetic_rejection.json` at SHA-256
  `e7cba8af...e0eb821` and reject the D-123 implementation/resource path. Do
  not publish or rely on the generated
  passing acceptance, create an official G2-7 claim, or retry, repair, resume,
  optimize, or replace this attempt. Any future G2-7 path must be materially
  distinct and prospectively frozen.
- Evidence: Both opposite-order roots completed 3,480 model-double invocations,
  666,432 mechanics prediction rows, 26 locked-runtime CatBoost fits, 20,488
  real probe predictions, and a 797,232-identity full-size traversal per root.
  All eight terminal files were byte-identical at tree SHA-256
  `6746735f...44b39f`, and the formal implementation bytes remained unchanged.
  Prepublication audit found that only 47 of the nominal 2,563 full-width probe
  columns varied; 2,516 columns were constant. CatBoost could therefore discard
  98.17% of the feature columns, making the generated 0.2504 wall-hour and
  3.1847 CPU-core-hour projections optimistic rather than the conservative
  resource falsifier D-123 required. The passing arithmetic is not accepted as
  valid resource evidence. This result contains no model-quality observation;
  fixed MapLight remains the best validated internal system at 0.5838
  component-macro MAE.
- Alternatives: Publish the mechanically passing acceptance; silently repair
  the matrix and rerun; reinterpret full width as sufficient despite constant
  columns; substitute an average or historical timing after seeing the result;
  create the official claim anyway; or use private portal evidence to justify
  progression.
- Reversal condition: None for the historical G2-7B attempt. A receipt or audit
  defect may revoke this record but cannot authorize a retry, repair, resume,
  or replacement. A future materially distinct experiment requires a new
  prospective contract and may use already accepted exact full-feature
  MapLight runtime evidence without representing itself as G2-7B.

## D-125 — Freeze fail-stop MapLight robustness execution without synthetic timing

- Date: 2026-08-25
- Status: accepted contract-only G2-7C evidence; zero implementation, runtime
  creation, synthetic source, model-double invocation, CatBoost fit,
  prediction, metric, claim, official row, confirmatory truth, historical row,
  blinded test, TDI, external record, submission, official metric,
  leaderboard-selection, private-portal record, or upload operation
- Decision: Accept
  `global_v2_maplight_robustness_bounded_execution_contract.json` at SHA-256
  `55fafa1d...5806527`. Preserve every D-122 scientific identity and make a
  future attempt pass only when the actual complete process tree finishes
  inside continuously enforced cumulative limits. Treat G2-7B as terminal
  negative history: its runner and driver may be authenticated only to prevent
  reuse and may not be imported, copied, executed, patched, benchmarked, or
  used to create a claim.
- Evidence: D-094 supplies the only resource prior: two exact 300-fit official
  full-feature replays over 3,908 molecules completed 600 fits in 3,643.572
  seconds and at most 16.194 CPU-core-hours, with 234,160,503 bytes peak
  restricted storage and zero GPU. Scaling the aggregate by the transparent
  1.7 maximum-fit-count ratio gives 1.721 wall-hours and at most 27.529
  CPU-core-hours, more than 4.4x below the hard 7.68/128 limits. This context
  justifies an attempt but cannot accept it, masquerade as a per-fit maximum,
  or alter the battery. The future supervisor begins before claim consumption,
  polls the full process tree at most every second, and enforces wall, CPU,
  storage, simultaneous RSS, and zero GPU during child fits. Any limit, warning,
  fallback, exit, signal, detached child, cleanup, or accounting miss aborts
  without partial publication. The exact science remains 540 stage-A fits,
  180 stage-B fits, and 300 conditional stage-C fits, totaling 720–1,020 with
  no baseline or inner refit. Thirteen focused static tests pass.
- Alternatives: Repair or rerun G2-7B; accept its synthetic projection; treat
  D-094 aggregate timing as a maximum-fit gate; weaken the D-122 battery; start
  official execution before implementation acceptance; create a claim now;
  optimize, cache, quantize, parallelize, or use private portal evidence.
- Reversal condition: Any parent, rejected-source non-reuse, exact-science,
  historical-resource, cumulative-monitor, process-tree, stage, claim,
  terminal, cleanup, privacy, integration, or post-main-CI drift revokes D-125
  before official access. Otherwise the next gate is only the new narrow
  D-122-derived compiler, wrapper, supervisor, no-fit official-shaped
  acceptance, and focused tests; claim creation and scientific fitting remain
  closed.

## D-126 — Accept the fail-stop MapLight robustness implementation without fitting

- Date: 2026-08-25
- Status: accepted G2-7C no-fit mechanics evidence; zero real CatBoost fit,
  resource projection, target metric, claim, official row, confirmatory truth,
  historical row, blinded test, TDI, external record, submission, official
  metric, leaderboard-selection, private-portal record, or upload operation
- Decision: Accept
  `global_v2_maplight_robustness_no_fit_acceptance.json` at SHA-256
  `ca722b26...c231e0e`. The additive D-122-derived compiler, wrapper, and
  cumulative process-tree supervisor satisfy D-125 without importing, copying,
  executing, patching, or benchmarking the terminally rejected G2-7B
  implementation. Keep claim creation and official execution closed until a
  later single-use G2-7D contract binds these reviewed bytes after green
  post-main CI.
- Evidence: Two fresh official-shaped synthetic roots used opposite source and
  launch order, independently reconstructed the primary, inclusive 0.55,
  inclusive 0.50, and canonical-tautomer-merged family overlays from raw
  structures, and matched all 252 capability files and eight terminal files
  byte-for-byte. Across both roots, the deterministic model double traversed
  3,480 exact invocations, 667,872 synthetic prediction identities, and 6,980
  before/after fit or stage checkpoints over both the 720-fit full-retained and
  1,020-fit deletion-selected branches. The no-network supervisor measured the
  complete process tree and accepted its control while rejecting all ten wall,
  CPU, storage, simultaneous RSS, warning, signal, detached-child,
  nonzero-exit, missing-checkpoint, and partial-publication faults. Twenty-eight
  focused tests pass. A first generated path was rejected because the cleanup
  root was intentionally too broad; its tracked rejection is
  `8fb6aba9...85d0ce3`. A second generated path was rejected during
  prepublication audit because supplied overlay hashes were not reconstructed;
  its tracked rejection is `4e4c45ae...563ec28`. Both negative paths opened
  zero official capability and produced no model-quality observation. Reviewed
  integration CI rejected superseded acceptance `5698f878...61f5683` because
  three exact-runtime tests ran outside Python 3.12.3 and one assertion assumed
  a checkout preserved read-only mode. Receipt `93a8adeb...0e7669e` binds that
  negative path. The correction changes only test portability and rejection
  lineage, not science or supervisor behavior. Superseded acceptance
  `587eca16...5f5b63` then failed only the three live namespace tests on the
  hosted Python 3.12.3 runner; host receipt `37429202...e8f5b1` binds that
  unsupported execution boundary. The live tests remain mandatory locally,
  while hosted CI retains static policy and artifact coverage. Fixed
  MapLight therefore remains the best validated internal system at 0.5838
  component-macro MAE.
- Alternatives: Use the generated pre-audit receipts; trust supplied family
  overlays; loosen cleanup protection; import rejected G2-7B code; fit timing
  probes; accept aggregate historical timing as execution proof; create or
  consume a claim now; open official rows; or use private portal evidence to
  select a model.
- Reversal condition: Any parent, source, raw-structure reconstruction,
  capability, sparse-target, exact-identity, cross-root determinism,
  checkpoint, process-tree, no-network, fault-injection, cleanup, privacy,
  integration, or post-main-CI drift revokes D-126 before official access.
  Otherwise the next gate is only a separate reviewed G2-7D official execution
  contract and immutable unconsumed claim; it may not retroactively authorize
  an operation in this milestone.

## D-127 — Freeze single-use MapLight robustness execution and unusable claim

- Date: 2026-08-25
- Status: accepted contract-and-unconsumed-claim G2-7D evidence; zero official
  source row, target, feature, baseline row, fit, prediction, development
  metric, confirmatory truth, historical row, blinded test, TDI, external
  record, submission, official metric, leaderboard-selection, private-portal,
  upload, or claim-consumption operation
- Decision: Accept
  `global_v2_maplight_robustness_execution_contract.json` at SHA-256
  `65934b0a...a91f488` and its immutable unconsumed claim at SHA-256
  `da0104bc...ceb334`. Freeze one fixed G2-7D attempt root and one consumption.
  Reuse the integrated D-126 compiler, no-fit wrapper, cumulative supervisor,
  accepted MapLight runner, chemistry, metric, and locks unchanged. Permit only
  one future scientific runner, one single-use attempt driver, one
  official-shaped execution/scoring acceptance driver, its aggregate
  acceptance, and focused tests. The five future receipt fields are null and
  `usable` is false, so this decision creates no official execution authority.
- Evidence: The contract binds D-122 `ad9aef87...a7a45af`, D-125
  `55fafa1d...5806527`, D-126 `ca722b26...c231e0e`, D-094
  `76775030...a4482`, integrated commit `15db9fb...`, and successful post-main
  CI run `32892466738`. It authenticates exact official source, R2B/R3A,
  feature-array, fixed-baseline manifest, outer-OOF, and component-metric
  receipt strings without opening their files. The attempt remains exactly
  540 stage-A fits, 180 stage-B fits, and 300 conditional stage-C fits: 720–
  1,020 total, 562,752–797,232 prediction identities, zero baseline refits,
  zero inner fits, one selection token, no runner-up, and no deployable clip.
  The accepted supervisor begins before claim consumption and enforces the
  actual complete process tree at 7.68 wall-hours, 128 CPU-core-hours, 51.2 GB
  restricted storage, 15.36 GiB simultaneous RSS, and zero GPU. Thirteen
  focused static tests pass. Fixed MapLight remains the best validated internal
  system at 0.5838 component-macro MAE; this freeze creates no new model-quality
  evidence.
- Alternatives: Consume a claim directly from D-126; let the no-fit wrapper
  masquerade as a scientific runner; weaken or resize D-122; accept historical
  timing as the result; add a candidate, seed, clip, calibration, blend, cache,
  concurrency, retry, runner-up, service, or portal-driven choice; or open an
  official source before scoring mechanics are accepted.
- Reversal condition: Any parent, source, baseline, root, implementation,
  runtime, family, support, candidate, seed, fit, prediction, chronology,
  metric, bootstrap, selection, diagnostic, resource, process-tree, cleanup,
  terminal, privacy, integration, or post-main-CI drift revokes D-127 before
  official access. Otherwise the next gate is only the exact additive sources,
  focused tests, and one formal two-root official-shaped synthetic
  execution/scoring acceptance. It may fill no tracked field, consume no claim,
  and open no official byte.

## D-128 — Revoke D-127 progression and freeze scoring-capability repair

- Date: 2026-08-25
- Status: accepted contract-only G2-7E evidence; D-127 claim remains immutable,
  unconsumed, unusable, and permanently barred; zero implementation, synthetic
  row, official source row, baseline row, fit, prediction, metric, claim,
  confirmatory truth, historical row, blinded test, TDI, external record,
  submission, official metric, leaderboard-selection, private-portal, upload,
  or claim-consumption operation
- Decision: Accept
  `global_v2_maplight_robustness_scoring_capability_contract.json` at SHA-256
  `b1cb0866...6adac9f`. Revoke only D-127's forward execution authority before
  implementation or consumption. Preserve its contract and claim as immutable
  history, with all five future hashes null, consumptions zero, and
  `usable=false`. Freeze one minimal future scorer-enrichment compiler before
  any scientific runner or corrected claim can exist.
- Evidence: D-122 requires finite reported `point`, `low`, and `high` for the
  tutorial-primary mask and arithmetic, `standardized_structure_hash` for the
  duplicate-collapse diagnostic, and authenticated `source_file` for the
  single-source gate. Static audit of accepted D-126 compiler SHA-256
  `029afd82...ace72a7` proves its three stage truth files contain only
  `molecule_id`, `endpoint`, and `point`. Therefore D-127's exact-D-122-scoring
  precondition cannot be proved from its accepted scorer capability. D-128
  keeps all D-122 candidates, seeds, groups, fits, predictions, selection,
  diagnostics, resources, and roots unchanged except that any later corrected
  attempt must use a new claim ID and root. Nine focused tests pass. No
  scientific or official operation occurred.
- Alternatives: Treat point as both bounds; omit tutorial scoring; hard-code
  source provenance as a scientific result; let the model or runner reopen the
  unrestricted source; mutate D-126 or the D-127 claim in place; consume the
  D-127 attempt and fail after fitting; or use private portal evidence to
  justify bypassing the gate.
- Reversal condition: Any parent, D-127 disposition, development/confirmatory
  prefix firewall, point equality, bound, structure, component, source,
  capability, chronology, publication, cleanup, privacy, integration, or
  post-main-CI drift revokes D-128 before implementation. Otherwise the next
  gate is only the trusted scorer-enrichment compiler, separate official-shaped
  direct-observation fixture, one formal opposite-order two-root synthetic
  acceptance driver, and focused tests. It must run zero real fit and zero
  development metric and may not create a claim or open an official byte.

## D-129 — Reject the consumed D-128 scorer-capability acceptance attempt

- Date: 2026-08-25
- Status: accepted terminal negative G2-7E evidence; D-128 attempts remaining
  zero; generated synthetic scratch cleaned; D-127 claim immutable, unconsumed,
  unusable, and barred; zero official source, fit, prediction, metric, claim,
  submission, leaderboard-selection, private-portal-record, or upload operation
- Decision: Accept
  `global_v2_maplight_robustness_scoring_capability_rejection.json` at SHA-256
  `e551c755...414848d`. Reject the sole D-128 formal attempt because complete
  cleanup is conjunctive. Preserve exact failed-source receipts, hard-disable
  the consumed driver before work, and authorize no retry, resume, in-place
  repair, replacement, or scientific interpretation under D-128.
- Evidence: Both official-shaped roots completed and produced identical
  `manifest.json` and `scoring_truth.csv` hashes despite opposite physical and
  dependency-safe order. Terminal cleanup then raised `cleanup root is unsafe`
  for `/tmp/<single-component-name>`, before acceptance publication. The 530
  generated files totaling 52,814,752 bytes were moved beneath one explicit
  deeper temporary parent, removed with the accepted safe-cleanup predicate,
  and both paths verified absent. Ten focused tests pass. Real CatBoost fits,
  development metrics, official operations, claims created/consumed, and live
  uploads all equal zero.
- Alternatives: Treat byte identity as acceptance despite incomplete cleanup;
  rerun with a deeper root; silently patch and reuse the same attempt; retain
  synthetic scratch indefinitely; or let private portal evidence justify
  bypassing the scorer gate.
- Reversal condition: This historical rejection is immutable. Any future
  scorer-capability path must begin with a separately reviewed contract that
  proves cleanup-root safety before either root is created, uses a materially
  distinct attempt identity, preserves D-128 science unchanged, and grants no
  authority to the consumed D-128 attempt or permanently barred D-127 claim.

## D-130 — Freeze distinct fail-before-work scorer-capability reacceptance

- Date: 2026-08-25
- Status: accepted contract-only G2-7F evidence; zero new implementation,
  synthetic row, official source, fit, prediction, metric, claim, submission,
  leaderboard-selection, private-portal-record, upload, or claim-consumption
  operation
- Decision: Accept
  `global_v2_maplight_robustness_scoring_capability_reacceptance_contract.json`
  at SHA-256 `b414b0cf...efae698`. Authorize one new V2 synthetic acceptance
  implementation and attempt identity after reviewed integration and green
  post-main CI. Reuse only the exact unchanged scorer compiler; bar the D-128
  driver, attempt, root, outputs, retry, repair, and reinterpretation.
- Evidence: D-129 isolated the failure to post-capability cleanup: opposite
  orders produced identical two-file maps, but the shallow root failed the
  accepted safety predicate. D-130 removes invocation-time root choice. It
  fixes `/tmp/cypshift-g2-7f/scoring-capability-attempt-1`, requires the parent
  and root absent, proves exact resolution and four-component depth, and invokes
  the accepted cleanup predicate on the still-absent root before any creation.
  It requires root and empty-parent removal before one no-replace terminal.
  Nine focused tests pass. D-129's integrated signed commit `1b8c5f7...` passed
  post-main CI run `32904446518` in all three lanes.
- Alternatives: Rerun the old driver with a deeper CLI path; treat deterministic
  output as acceptance; modify the scorer compiler; weaken cleanup; allow an
  alternate root or terminal; combine the repair with the scientific runner;
  or use private portal evidence to bypass the gate.
- Reversal condition: Any parent, compiler, fixed-root, pre-work chronology,
  absence, cleanup predicate, terminal, field, count, opacity, order,
  determinism, privacy, integration, or post-main-CI drift revokes D-130 before
  synthetic execution. Otherwise the next gate is only the V2 driver, focused
  tests, and one zero-fit, zero-metric, zero-official two-root attempt.

## D-131 — Implement the fixed-root scorer-capability reacceptance driver

- Date: 2026-08-25
- Status: accepted implementation evidence pending reviewed integration; D-130
  formal attempts executed zero; fixed roots and both terminals absent; zero
  real fit, development metric, official, claim, submission,
  leaderboard-selection, private-portal-record, or upload operation
- Decision: Accept the V2 driver source at SHA-256
  `e8895bb9...c84de61` and its focused tests at `668e4ff1...462ec97` for review.
  Do not execute the formal attempt until this exact implementation is
  integrated through a signed fast-forward and green post-main CI.
- Evidence: The driver accepts no root/output argument, binds D-130/D-129 and
  the unchanged scorer compiler, keeps the D-128 driver hard-disabled and
  unimported, preflights the exact absent root with the accepted cleanup
  predicate, tracks creation ownership, and requires root/parent absence before
  one terminal. Twelve focused tests pass. One test-only compilation produced
  exactly `manifest.json` plus `scoring_truth.csv` from 4,800 synthetic endpoint
  rows, decoded 3,840 development rows, skipped 960 confirmatory suffixes before
  decoding, and marked 768 rows tutorial-eligible. It ran zero fit or metric
  and grants no scientific authority.
- Alternatives: Run before integration; import or patch the rejected driver;
  expose a configurable root; clean a pre-existing unowned path; publish before
  cleanup; modify the scorer compiler; combine this with model execution; or
  use private portal evidence to bypass acceptance.
- Reversal condition: Any contract, rejection, compiler, driver, tests,
  fixed-root, old-driver isolation, preflight, ownership, cleanup, terminal,
  opacity, count, privacy, integration, or post-main-CI drift revokes D-131
  before the formal attempt. Otherwise invoke the integrated driver exactly
  once with no arguments and interpret only its aggregate synthetic terminal.

## D-132 — Accept the fixed-root scorer capability

- Date: 2026-08-25
- Status: accepted G2-7F scorer-mechanics evidence; one formal attempt consumed;
  fixed roots cleaned; zero real fit, development metric, official source,
  claim, submission, leaderboard-selection, private-portal-record, upload, or
  claim-consumption operation
- Decision: Accept
  `global_v2_maplight_robustness_scoring_capability_acceptance_v2.json` at
  SHA-256 `9643dac8...c4873ed0`. The eight-field scorer-enrichment capability is
  now sufficient for a later corrected D-122 execution path. It grants no
  model-quality or official authority by itself.
- Evidence: Exact signed integrated commit `1a12329...` passed post-main CI run
  `32909057932`. The sole no-argument attempt completed in 1.8 seconds. Two
  opposite-order roots produced identical two-file capability maps at tree
  SHA-256 `933e2f16...b3ea57`. Across both roots, 9,600 synthetic endpoint rows,
  7,680 decoded development rows, 7,680 emitted scoring rows, 1,920 opaque
  confirmatory suffixes, and 1,536 tutorial-eligible rows were accounted.
  Cleanup removed fixed root and parent before publication. Driver, compiler,
  and focused-test hashes match the receipt. Twelve additive audit tests pass.
- Alternatives: Treat the failed D-128 attempt as accepted; repeat G2-7F for
  more evidence; modify bounds or provenance; add a model/metric check; create
  or consume an official claim now; or use private portal evidence to select a
  scientific path.
- Reversal condition: The acceptance is immutable. Any parent, driver,
  compiler, test-at-attempt, root, count, opacity, determinism, cleanup,
  accounting, privacy, integration, or post-main-CI drift blocks progression.
  Otherwise the next gate is only a corrected contract and new unusable claim;
  it is not official access or model execution.

## D-133 — Freeze corrected single-use robustness execution and unusable claim

- Date: 2026-08-25
- Status: accepted contract-and-unconsumed-claim G2-7G evidence; new fixed root
  absent; five future hashes null; D-127 claim/root and D-128 attempt barred;
  zero official source, baseline, fit, prediction, development metric, claim
  consumption, submission, leaderboard-selection, private-portal-record,
  upload, or model-quality operation
- Decision: Accept
  `global_v2_maplight_robustness_execution_contract_v2.json` at SHA-256
  `9464b094...91151bcf` and its new immutable unconsumed claim at SHA-256
  `d7e68837...44df6f9f`. Bind the exact D-122 science, D-125 cumulative resource
  ceilings, D-126 execution mechanics, and D-132 accepted eight-field scorer.
  Freeze one distinct G2-7G identity, root, and consumption without granting
  current execution authority.
- Evidence: Signed D-132 commit `fed05e6...` was fast-forwarded through PR #169
  and passed post-main CI run `32911452732` on Python 3.11, 3.12.3, and 3.14.
  The new root was absent at freeze. The contract preserves 720–1,020 fits,
  562,752–797,232 prediction identities, one selection token, no runner-up,
  7.68 wall-hours, 128 CPU-core-hours, 51.2 GB restricted storage, 15.36 GiB
  simultaneous RSS, and zero GPU. Its new claim is `usable=false`, has zero
  consumptions, and leaves all five future implementation/acceptance receipts
  null. Thirteen focused tests pass.
- Alternatives: Mutate or reuse D-127; repair or reinterpret D-128; duplicate
  the full retired contract; change a candidate, seed, threshold, gate, fit,
  metric, or resource ceiling; create a usable claim; combine contract freeze
  with implementation or execution; or use private portal evidence for model
  selection.
- Reversal condition: Any parent, barred-history, source, baseline, scorer,
  root, claim, science, fit, prediction, selection, resource, privacy,
  integration, or post-main-CI drift blocks progression. Otherwise the next
  gate is only the additive scientific runner, new attempt driver,
  official-shaped execution acceptance driver, and focused tests; the formal
  synthetic attempt waits for reviewed integration and green post-main CI.

## D-134 — Make the corrected robustness execution implementation review-ready

- Date: 2026-08-26
- Status: accepted implementation evidence only; formal two-root attempt
  unrun; fixed acceptance and official roots absent; claim unconsumed; zero
  official byte, real CatBoost fit, scientific development metric, submission,
  leaderboard-selection, private-portal-record, upload, or model-quality
  operation
- Decision: Accept for review the additive scientific runner at SHA-256
  `dca9b8d1...2ca90bde`, fixed one-use official driver at
  `1675336e...a3de57fc`, official-shaped acceptance driver at
  `7cb471ce...2a42e473`, and nine focused tests at
  `3fedd87e...4228c53f`. Do not run the formal acceptance until these exact
  bytes are integrated through a signed fast-forward and green post-main CI.
- Evidence: The runner imports only accepted D-126/D-132 primitives and never
  imports, executes, copies, or patches rejected G2-7B code. Test-only
  official-shaped capabilities traversed both frozen conditional paths:
  exactly 540 stage-A plus 180 stage-B fit identities for full retention, and
  those 720 plus 300 conditional stage-C identities for deletion selection.
  Both paths issued one token and no runner-up and published aggregate-only
  terminals with zero retained row values or model binaries. The scorer opens
  after the matching stage freeze and uses the exact molecule, endpoint,
  standardized-structure, primary-component, source, point, low, and high
  fields. Group diagnostics compare matched active rows, every robustness view
  retains all four endpoint summaries, and paired row sets must match exactly.
  Execution mode is bound to predictor class, capability mode, and claim
  authority. Exactly 56 tutorial-metric calls per path are measured against
  the frozen maximum of 80. The cumulative supervisor contains the trusted
  Python 3.12.3 compiler/scorer and separate
  pinned Python 3.10.13/CatBoost 1.2.1 descendants. Nine focused and 55
  relevant tests pass; official aggregate output cannot become final until
  cumulative supervision succeeds. All formal, official, claim, and external
  roots remain untouched.
- Alternatives: Reuse or inspect rejected G2-7B bytes; run before integration;
  combine compiler and model runtimes; force a synthetic selection token;
  compare grouping perturbations on unmatched rows; add a candidate, seed,
  group, metric, clip, retry, cache, concurrency mode, or runner-up; consume
  the claim now; or use private portal evidence for selection.
- Reversal condition: Any source hash, parent, runtime, stage chronology,
  split, feature view, CatBoost constructor, scorer field, bootstrap, selection,
  diagnostic, accounting, resource, cleanup, privacy, fixed-root, integration,
  or post-main-CI drift revokes D-134 before formal acceptance. Otherwise run
  the integrated no-argument acceptance exactly once and interpret only its
  aggregate synthetic mechanics evidence.

## D-135 — Accept the corrected robustness execution mechanics

- Date: 2026-08-27
- Status: accepted sole formal two-root synthetic execution evidence pending
  reviewed integration; fixed work root cleaned; official attempt root absent;
  distinct claim unusable and unconsumed; zero official, claim, submission,
  leaderboard-selection, private-portal-record, upload, or model-quality
  operation
- Decision: Accept the immutable aggregate execution acceptance at SHA-256
  `4c886d0d...ffedf390` as mechanics, determinism, bounded-runtime-control, and
  cumulative-supervision evidence only. It does not measure model quality and
  cannot authorize official access until this evidence is reviewed, integrated
  by signed fast-forward, and green on post-main CI.
- Evidence: The sole fixed no-argument formal attempt completed two fresh roots
  with opposite physical and fit-launch order. Each root traversed both frozen
  profiles: full retention selected synthetic `G2-7-M0-FULL` after exactly 540
  stage-A plus 180 stage-B model-double fits, while deletion selection chose
  synthetic `G2-7-M2-DROP-AVALON` only after the same 720 fits plus 300
  conditional stage-C fits. Across roots this is exactly 3,480 model-double
  fits and 667,872 synthetic prediction identities. Model and scorer
  capability maps and all eight aggregate terminal files are byte-identical
  across order. Exactly two bounded real CatBoost controls produced finite
  predictions. One cumulative supervisor acknowledged 6,985 checkpoints,
  observed 13 descendants and no detached children, and completed in
  187.6251 wall-seconds and 381.1205 CPU-seconds with 435,781,632-byte peak
  simultaneous RSS, 104,341,504-byte peak storage, zero warnings, and zero GPU
  hours. Cleanup completed before publication, no private root remains, and
  the receipt records zero official operations, zero claims created or
  consumed, and false claim and model-quality authority.
  The nine updated state-transition tests at SHA-256
  `625f3ae0...0c6ca2b` and five receipt-audit tests at
  `80c08d89...7fca97e` pass; the formal receipt continues to bind the exact
  at-attempt D-134 focused-test hash `3fedd87e...4228c53f`.
- Alternatives: Repeat, repair, resume, relocate, or reinterpret the one-use
  formal attempt; promote its synthetic profile choices as scientific
  evidence; alter candidates, features, seeds, groups, retries, calibration,
  blends, caches, concurrency, resources, or frameworks; consume the claim
  before reviewed integration; or use private portal evidence.
- Reversal condition: The acceptance is immutable. Any contract,
  implementation, focused-test-at-attempt, root-order, conditional-profile,
  fit, prediction, capability, terminal, real-control, runtime, supervision,
  cleanup, privacy, integration, or post-main-CI drift blocks progression.
  Otherwise the next gate is the exact official G2-7G preflight followed by
  one no-argument claim-consuming execution; no official byte may open before
  the supervised child consumes that claim.

## D-136 — Reconcile focused-test provenance before official execution

- Date: 2026-08-27
- Status: accepted provenance-bridge implementation evidence pending reviewed
  integration; D-135 formal acceptance immutable; official execution unrun;
  attempt and restricted roots absent; tracked claim unchanged, unusable, and
  unconsumed; zero production, science, formal-attempt, official-operation,
  private-byte, fit, prediction, metric, submission, upload, or model-quality
  operation
- Decision: Accept the narrow focused-test provenance bridge at aggregate
  receipt SHA-256 `2820c30f...33a0dc3`. Restore the exact D-134 focused-test
  snapshot bound by the immutable formal receipt, preserve the D-135 post-state
  bytes as historical lineage, and retire only the restored snapshot's
  obsolete pre-acceptance absence assertion during post-acceptance collection.
  Do not change production or scientific recipe bytes and do not repeat either
  one-use gate.
- Evidence: Signed D-135 commit `7450676...` passed exact-SHA post-main CI run
  `33085677193`. The first unchanged official-driver preflight then proved a
  deterministic rejection would occur before cumulative supervision because
  the formal receipt
  binds focused tests `3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f`
  while the live D-135 state-transition file had SHA-256
  `625f3ae0c8d61dc76775240606a2662d7b9b80b5ffe0c05344b9a587f0c6ca2b`.
  No official attempt or restricted root, private claim, or official source or
  baseline byte was created or opened during that read-only proof; the tracked
  claim did not change or consume. The bridge restores exact
  `3fedd87e...4228c53f`, keeps
  `625f3ae0...0c6ca2b` as immutable D-135 historical lineage, binds pytest
  transition hook
  `e931ec84186da7f06e1ab6ceea909bb01647acb3de01bb60b539e22d5848727a`,
  and expands the acceptance/current-state plus public in-memory claim-
  derivation audit at
  `719c0f71a8a0e403f590e1aced8a38b3c6131ff915a2bc9f8234126761bb4a2f`.
  The combined focused set has 15 active passes and one explicitly historical
  skip. Claim derivation fills exactly the five frozen future receipt fields
  in memory while changing no tracked byte or private root. Production files
  changed, scientific recipes changed, formal acceptances repeated, official
  operations, claims created or consumed, private rows opened, model fits,
  predictions, development metrics, and model-quality authority are all zero.
  The exact 55-node relevant suite has 54 active passes plus the historical
  skip, and the safe repository suite has 1,302 passes with five skips total;
  Ruff, mypy, build, and two installed deterministic vertical slices pass.
- Alternatives: Rewrite the immutable D-135 receipt; change the official
  driver or its fail-closed comparison; retain only the post-state test hash;
  drop current-state coverage; mark more than the exact obsolete node skipped;
  create or consume a claim during testing; open an official byte to diagnose
  a public hash mismatch; or proceed from an unintegrated bridge branch.
- Reversal condition: Any contract, claim, acceptance, implementation,
  receipt-bound snapshot, historical-blob, transition-hook, current-state
  audit, claim-derivation, root, privacy, integration, or post-main-CI drift
  blocks progression. Otherwise integrate D-136 by signed fast-forward, require
  green exact-SHA post-main CI, then repeat only the fresh fail-before-work
  preflight and invoke the still-unrun sole no-argument official execution.

## D-137 — Freeze a driver-only official-orchestration repair before claim use

- Date: 2026-08-27
- Status: accepted contract-only G2-7H evidence pending reviewed integration;
  D-135 science-kernel acceptance inherited and not repeated; repair
  implementation and composite acceptance absent; official execution unrun;
  tracked claim unchanged, unusable, and unconsumed; fixed official,
  restricted, staging, acceptance, and rejection roots absent; zero official
  source or baseline byte, fit, prediction, metric, confirmatory, blinded-test,
  TDI, submission, leaderboard-selection, private-portal-record, upload, or
  model-quality operation
- Decision: Accept
  `global_v2_maplight_robustness_official_orchestration_repair_contract.json`
  at SHA-256 `f6576d61...0534b967`. Freeze the smallest correction for the
  fail-closed final pre-consumption audit: change only the official driver in
  production, add one fixed zero-official composite acceptance driver and
  dedicated focused tests, and inherit D-135's immutable accepted science
  kernel without rerunning it.
- Evidence: Signed D-136 commit `1c0c5d0f...4409bfa39` passed exact-SHA
  post-main CI run `33090557041`. The subsequent fresh static audit stopped
  the still-unrun official path before supervision. The compiler's exact
  `RobustnessExecutionUnderpowered` would escape the supervised child; the
  accepted supervisor would convert it and ordinary child failures to the
  same exception form; and the historical official driver would classify any
  such exception as `G2_7C_MAPLIGHT_ROBUSTNESS_RESOURCE_ABORTED`, discard its
  structured cumulative observation, and retain false zero-valued allowed-
  input accounting after work began. Atomic staged-and-fsynced claim
  publication, fixed publication/restricted-root cleanup, complete interrupted
  cleanup, and symlink-unlink-without-following behavior also lacked acceptance
  proof. No attempt, claim-staging, restricted, or publication root, private
  claim, or official source or baseline byte was created or opened.

  The contract makes all five frozen statuses reachable only from their exact
  cause, limits resource-aborted to the four exact hard wall, CPU, storage,
  and simultaneous-RSS maxima, maps every other supervised defect to failed,
  records structured cumulative supervision through canonical delimiter
  `; observation=` and exactly 13 typed fields with no extras, reconstructs and
  validates aggregate allowed-input accounting, stages and fsyncs claim publication,
  and fixes atomic no-replace status-specific publication with symlink-safe
  cleanup. Accounting represents authoritative capability crossings, not
  syscalls or repeated in-memory parsing. It separately binds 73,575 group-
  fold rows, source central points, finite reported bounds at exactly six times
  the authenticated tutorial-eligible count, raw and generated model-feature
  and fold rows, generated prediction reopens for selection/terminal scoring,
  scoring truth, training targets, baseline predictions, and exactly 56
  tutorial calls under the frozen maximum of 80.

  Every consumed-claim terminal includes `attempt_receipt.json`; underpowered
  also includes aggregate `preflight.json`. The bounded post-supervision seal
  may create and fsync that receipt, bind the observation, make the terminal
  read-only, and atomically promote it within 16 MiB, 1 MiB receipt, and five
  wall- and CPU-seconds with zero additional official open, fit, prediction,
  or metric. A pre-consumption supervisor failure removes fixed claim staging,
  the restricted root, publication staging, and any empty attempt root, leaves
  claim, receipt, and terminal absent, and stops automation without fabricating
  one of the five consumed-claim statuses or permitting a second fixed
  invocation. Its future composite acceptance therefore exercises six
  scenarios per order—scientific success, clean underpower, scientific
  rejection, hard-wall abort, ordinary nonzero failure, and pre-consumption
  supervisor failure—and eleven exact mechanics checks in forward and reverse
  order with identical normalized maps and zero official operation, claim use,
  model fit, prediction, or metric.

  Hard-resource classification occurs only after exact observation-schema,
  type, finiteness, nonnegative, return-code, and boolean validation. A missing
  or malformed observation after claim consumption may publish only an
  accounting-incomplete failed terminal through the same bounded seal and
  never claim resource compliance; the same defect before claim consumption
  follows the no-terminal cleanup rule.

  Scientific, rejected, and underpowered sealing additionally requires integer-
  zero return, positive checkpoints and descendants, complete cleanup and
  isolation, zero GPU/detachment/warnings, and every observed resource within
  the exact parent maxima. The full five wall-seconds, five CPU-seconds, 16-MiB
  terminal, and 1-MiB receipt reservation must still fit within the unchanged
  7.68-hour, 128-core-hour, 51.2-GB, 15.36-GiB, zero-GPU envelope. Successful
  and canonical-exception outcomes use this same bounded seal. One
  same-invocation minimal failed or resource-aborted seal is the only permitted
  response to a seal fault; a final-path collision, failed minimal seal, or
  failed promotion cleans staging, retains the consumed claim, publishes no
  replacement, and permanently blocks reinvocation.

  D-137 also freezes an accounting-label erratum. D-122 and D-133 called
  `562,752` a minimum and `797,232` a maximum official total, but both are
  unattainable branch upper projections: every non-primary Stage-B overlay
  must exclude confirmatory-touching development molecules. Exact official
  predictions are the authenticated sum of completed stage manifests and are
  strictly below the applicable projection. This changes no science,
  mechanics, or selection. The scientific runner,
  robustness and scoring compilers, no-fit wrapper, cumulative supervisor,
  MapLight runner, candidate, feature, parameter, seed, group, fold, fit,
  prediction, metric, gate, resource, token, and no-runner-up identities stay
  byte-for-byte unchanged. D-135's 3,480 model-double fits, 667,872 synthetic
  predictions, and two real CatBoost controls remain immutable inherited
  evidence and are not repeated.
  Nine contract-integrity tests at SHA-256
  `814675f28c637b30a7d8eea3bf275ee28e39694f1b33127403e95f261490f9c9`
  and all 29 safe related tests pass.
- Alternatives: Invoke the known-defective driver; relabel compiler underpower
  as a resource abort; treat all supervisor exceptions alike; invent zero
  accounting after work begins; modify the accepted supervisor or science
  kernel; rerun D-135; expand candidates, features, seeds, groups, retries,
  caches, concurrency, resources, frameworks, or services; mutate or consume
  the tracked claim; open an official byte while diagnosing; or use private
  portal or leaderboard evidence.
- Reversal condition: Any contract, immutable-parent, driver-only surface,
  terminal-cause, observation, accounting, staging, cleanup, symlink, receipt,
  fixed-root, claim, privacy, integration, or post-main-CI drift blocks
  progression. Otherwise integrate D-137 by signed fast-forward, require green
  exact-SHA post-main CI, then implement only the frozen driver patch, fixed
  no-argument composite acceptance driver, and focused tests. Do not run the
  composite acceptance or official execution from either branch.

## D-138 — Correct the terminal seal order before implementation acceptance

- Date: 2026-08-27
- Status: accepted additive contract-only seal-order erratum pending reviewed
  integration; D-137 repair contract and D-135 science kernel inherited;
  repair implementation remains uncommitted; composite and official one-use
  executions unrun; tracked claim unchanged, unusable, and unconsumed; zero
  official, private-byte, claim, fit, prediction, metric, confirmatory,
  blinded-test, TDI, submission, leaderboard, portal, upload, or model-quality
  operation
- Decision: Accept
  `global_v2_maplight_robustness_official_orchestration_seal_erratum.json` at
  SHA-256 `a3e1bd65...f3faeb33`. Supersede only D-137's platform-infeasible
  order of changing the staging directory itself to `0555` before atomic
  rename. Freeze aggregate leaves at `0444`, the unpublished staging root at
  owner-only `0700`, atomic `renameat2(RENAME_NOREPLACE)` as the sole
  visibility commit point, immediate final-root `0555`, parent/final fsyncs,
  and full post-promotion evidence validation.
- Evidence: After signed D-137 commit `0dbbc701...d4ebf1b9` passed exact-SHA
  post-main CI run `33096357416`, the first safe disposable seal probe tested
  source directory modes `0755`, `0555`, `0700`, and `0500`. Rename succeeded
  for `0755` and `0700` but returned `EACCES` for `0555` and `0500` on the
  pinned host, despite owned writable parents. No official/private path or
  byte, claim, model, prediction, or metric capability was involved. The
  corrected sequence preserves an unpublished owner-only root, read-only
  leaves, no-replace visibility, and a read-only final tree. It requires exact
  final inode/device, current-user ownership, single-link regular files,
  modes, sizes, and hashes to match pre-promotion evidence. A collision,
  rename error, or any post-promotion chmod/fsync/validation/resource error is
  permanently blocking: retain the consumed claim and visible terminal if
  any, perform no fallback or final cleanup, and never reinvoke. Only one
  controlled pre-promotion seal error remains eligible for the D-137 minimal
  disposition, and primary plus fallback share one five-second wall/CPU
  budget; actual time exhaustion cannot authorize fallback. Three focused
  erratum tests at SHA-256 `de7aafde...2ba3f13b` pass. The immutable supervisor
  cannot defend against a malicious concurrent same-UID path substitution
  without changing accepted bytes, so the trusted child/outer publisher is
  explicitly the sole in-scope staging writer; pre-existing, orphaned,
  dangling, root, and descendant symlinks remain no-follow cleanup cases.
- Alternatives: Silently relax D-137; repeatedly attempt the impossible
  `0555` rename; use an overwrite-capable rename fallback; publish writable
  leaves; change the accepted supervisor; widen seal time/resources; delete a
  terminal after the rename commit point; retry the fixed claim; or invoke
  either one-use gate before reviewed integration.
- Reversal condition: Any parent hash, fixed path, leaf/root mode, no-replace
  primitive, fsync, post-promotion validation, collision disposition, shared
  seal budget, symlink/threat-model, claim, privacy, integration, or post-main
  CI drift blocks progression. Otherwise integrate D-138 by signed
  fast-forward, require green exact-SHA post-main CI, then package the
  still-uncommitted driver-only repair, fixed no-argument composite acceptance
  driver, and dedicated focused tests. Do not run the composite acceptance or
  official execution from the implementation branch.

## D-139 — Freeze the historical-test transition before repairing the driver

- Date: 2026-08-27
- Status: accepted contract-only test-provenance transition pending reviewed
  integration; signed D-138 commit `158dffca...a6e8318` integrated after green
  PR CI run `33100049450` and green exact-SHA post-main CI run `33101131039`
  across Python 3.11, 3.12.3, and 3.14; D-136 historical audit and pytest
  hook unchanged; repaired driver, composite acceptance, focused tests, and
  conftest transition now reserved for D-141 after D-140's supplemental
  contract; both fixed one-use executions unrun;
  tracked claim unchanged, unusable, and unconsumed; zero official,
  private-byte, claim, fit, prediction, metric, confirmatory, blinded-test,
  TDI, submission, leaderboard, portal, upload, or model-quality operation
- Decision: Accept
  `global_v2_maplight_robustness_official_orchestration_test_transition_contract.json`
  at SHA-256 `6703ad30...45709c2c`. Preserve the immutable D-135 receipt, D-136
  bridge, historical aggregate-audit file, and current pytest hook unchanged
  in this contract-only milestone. Freeze exactly three prospective D-141
  retirements and no others:
  `tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::test_acceptance_binds_exact_contract_and_integrated_implementation`,
  `tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::test_provenance_bridge_retires_only_the_obsolete_pre_acceptance_state`,
  and
  `tests/test_openadmet_global_v2_maplight_robustness_execution_acceptance_v2.py::test_claim_derivation_is_read_only_and_fills_exactly_five_receipts`.
  D-141 must add the exact conftest markers and bind each retirement to a
  replacement current-state assertion in its new focused tests before any
  composite acceptance can run.
- Evidence: D-136 correctly restored the D-134 at-attempt snapshot and recorded
  the then-live D-135/D-136 transition. Its first two named historical nodes
  intentionally compare immutable receipts with the live historical official
  driver and hook-bound audit bytes; the third exercises the historical
  five-future-field derivation. D-141 is required to bind the repaired driver,
  composite acceptance, new focused tests, D-137, D-138, and D-139, so those
  three assertions become false by the authorized state transition rather than
  by scientific drift. Every other D-135/D-136 aggregate, cleanup, resource,
  claim-template, and zero-authority audit remains valid and active. The
  six D-139 contract-integrity tests at SHA-256
  `185555b2...a0df90a0` prove exact-node cardinality,
  unchanged historical bytes and hook, replacement-binding requirements, and
  zero authority. This milestone changes no implementation or test collection.
- Alternatives: Modify the immutable D-135 receipt or D-136 bridge; edit the
  historical audit file; broadly skip a file, class, prefix, or changing hash;
  let stale live-byte assertions block the next implementation; mark nodes before contract
  integration; omit replacement current-state coverage; combine this
  provenance transition with implementation; repeat D-135; or run either fixed
  one-use gate from a contract or implementation branch.
- Reversal condition: Any drift in the exact three node IDs, historical audit
  or hook bytes, replacement-current-state mapping, D-137/D-138 lineage,
  tracked claim, zero-authority boundary, signed integration, or exact-SHA
  post-main CI blocks progression. Otherwise integrate D-139 by signed
  fast-forward and require green post-main CI. After the supplemental D-140
  source-shape contract is also integrated and green, let D-141 change only the
  repaired official driver, fixed composite acceptance driver, dedicated
  focused tests, and exact frozen conftest markers/bindings. Integrate D-141
  and require green post-main CI before running the fixed composite acceptance
  exactly once.

## D-140 — Freeze the supplemental source-shape transition before implementation

- Date: 2026-08-27
- Status: accepted contract-only negative evidence pending reviewed signed
  integration; signed D-139 commit
  `3b9c251f6875fedb33e51c4420cd8634c6e4cf29` integrated with green exact-SHA
  post-main CI run `33103967048` across Python 3.11, 3.12.3, and 3.14;
  prospective D-141 implementation remains uncommitted and unbound; fixed
  composite acceptance and official G2-7G execution unrun; tracked claim
  unchanged, unusable, and unconsumed; zero collection, implementation,
  official, private-byte, claim, fit, prediction, metric, confirmatory,
  blinded-test, TDI, submission, leaderboard, portal, upload, or model-quality
  operation or authority
- Decision: Accept only
  `global_v2_maplight_robustness_official_orchestration_source_shape_transition_contract.json`
  at SHA-256
  `d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417`
  and its seven contract tests at SHA-256
  `35bcb0958bc66c386b82ab13171b453c6f60fde81dcb40d329a2f9b659c67da6`.
  Preserve immutable D-134 focused snapshot
  `3fedd87eb86f485167a53564cb440409056d82982f329db888028e294228c53f`
  and the existing four collection skips unchanged in D-140. Freeze exactly
  two future D-141 skip markers and their exact replacements; permit no other
  skip, deselection, xfail, file/class/prefix rule, or historical-file edit.
- Evidence: The prospective implementation passed 118 safe focused/contract
  tests, but the safe repository suite, run with permanently barred
  `tests/test_openadmet_global_v2_maplight_robustness_synthetic.py` explicitly
  ignored, reported `1415 passed, 8 skipped, 2 failed` in about 352.96 seconds.
  All seven D-140 tests and all 25 combined D-137 through D-140 contract tests
  pass.
  Those failures are negative pre-integration evidence and exactly identify:

  - `tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::test_exact_fit_topology_and_conditional_stage_c_are_unchanged`; and
  - `tests/test_openadmet_global_v2_maplight_robustness_scientific_runner_v2.py::test_supervisor_starts_before_claim_consumption_and_official_access`.

  D-140 maps the first historical node exactly to
  `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_corrected_child_preserves_fit_topology_and_cleans_before_terminal_staging`.
  Its comprehensive scope is Stage A=540, Stage B=180, and conditional Stage
  C=300 fit identities; exact feature widths `2563/1539/1539/2248/2363` for
  `G2-7-M0-FULL`, `G2-7-M1-DROP-MORGAN`, `G2-7-M2-DROP-AVALON`,
  `G2-7-M3-DROP-ERG`, and `G2-7-M4-DROP-DESCRIPTORS`; both predictor-authority
  cross rejections for `synthetic=True` with `real_catboost_predictor` and
  `synthetic=False` with `deterministic_test_predictor`; Stage A -> selection ->
  Stage B ->
  conditional Stage C with exact condition `selected != "G2-7-M0-FULL"`; and
  `_terminal_bytes -> _cleanup_owned_root(work) -> _stage_payload(files)`.

  D-140 maps the second historical node exactly to
  `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_supervisor_precedes_claim_consumption_and_common_seal_owns_terminal_publication`.
  Its comprehensive scope is `run_supervised` present and `_consume_claim`
  absent in `run_official_attempt`; child chronology `resource_checkpoint ->
  derive_consumed_claim -> _consume_claim -> compile_capabilities -> Stage A`;
  exact `raw_observed = supervisor.run_supervised`; exact
  `publication_root=PUBLICATION_STAGING_ROOT` and
  `writable_publication_parent=OFFICIAL_ATTEMPT_ROOT.parent`; equal official
  and acceptance limits; exact absent `OFFICIAL_ATTEMPT_ROOT` at
  `/home/zbos/cypshift-private/openadmet-2026/g2-7g-maplight-robustness-development-attempt-1`;
  `_failure_payload` with `accounting_complete` returning aggregate bytes only
  with no terminal path or publication; outer `run_supervised ->
  _seal_with_fallback`; exclusive common-seal publication; and absence of
  parent `_finalize_terminal` and child
  `PENDING_TERMINAL_ROOT`.

  The D-141 hook may add only these two markers while preserving the previous
  four, for six total. D-141 must bind field
  `d140_source_shape_transition_contract_sha256` in the corrected driver,
  composite driver/receipt, and focused tests. D-140 changes no production,
  collection, historical-test, science, claim, gate, candidate, fit,
  prediction, metric, resource, status, accounting, selection, or privacy byte.
  It runs neither one-use gate and grants zero collection, implementation,
  formal-acceptance, official, claim, science, model-quality, confirmatory,
  submission, or upload authority. No prospective implementation hash is
  accepted or bound by D-140.
- Alternatives: Rewrite the immutable D-134 snapshot; ignore the two safe-suite
  failures; bind the uncommitted implementation before a transition contract;
  broaden skips; combine contract, implementation, and one-use execution;
  rerun D-135; modify science, claim, gate, resource, accounting, or selection;
  add a candidate, feature, seed, group, retry, cache, framework, or service;
  open official or confirmatory bytes; or use portal/leaderboard evidence.
- Reversal condition: Any drift in either D-140 hash, immutable parent or D-134
  snapshot hash, exact two-node/two-replacement mapping, comprehensive scope,
  prior four-skip preservation, zero-authority boundary, signed integration, or
  exact-SHA post-main CI blocks progression. Otherwise integrate D-140 by
  signed fast-forward and require green post-main CI, then package the D-141
  implementation with exactly six markers, both replacement nodes, and the
  frozen binding. Integrate D-141 and require green post-main CI before
  preflighting and invoking the sole fixed composite acceptance exactly once.

## D-141 — Accept the bounded official-orchestration implementation for review

- Date: 2026-08-27
- Status: accepted implementation and synthetic-test evidence pending reviewed
  signed integration; signed D-140 commit
  `6e3cb96299cefc928be09fee10008c4c7ac651f5` is integrated with green exact-SHA
  post-main CI run `33109592304` across Python 3.11, 3.12.3, and 3.14; fixed
  composite acceptance and official G2-7G attempt remain unrun; tracked claim
  unchanged, unusable, and unconsumed; zero official/private-byte or
  tracked/private-claim mutation or consumption and zero fit, prediction,
  development-metric, confirmatory, blinded-test, TDI, submission, leaderboard,
  portal, upload, science, or model-quality operation or authority
- Decision: Accept exactly four D-141 files for review: corrected official
  driver SHA-256
  `feab960a54dd5ff818e29d062ad8eba48538658fe38a75d01f7c76f3d2daf103`,
  fixed no-argument composite acceptance driver
  `3e209b88df7634f47884ce45653673a5407310575146392a77811fb4ed67ba9f`,
  dedicated focused tests
  `f17b5b2f39b92892b046f289d6ebdb1888d705ea7a27ea24b3ca3013d39289b0`,
  and exact six-marker `tests/conftest.py`
  `03d92bf3a2890a61190a6a4fc7a6bc59fa900ed6ea4b904223b1f2f991699d95`.
  Preserve the immutable D-135 science kernel and D-122 battery exactly.
  Implement only D-137/D-138 official orchestration, complete only the exact
  D-139 three-node and D-140 two-node test transitions, and bind both
  transition-contract hashes through composite and real receipt lineage.
- Evidence: D-141 provides exact five-status taxonomy, strict cumulative
  13-field supervisor observations, capability-crossing accounting, atomic
  one-use claim publication, symlink-safe cleanup, one shared bounded common
  seal, no-replace collision behavior, inode/device/mode/hash validation, and
  exact hard-resource versus ordinary-failure classification. Its fixed
  composite driver covers two opposite scenario orders and six scenarios with
  aggregate-only zero-operation evidence. The implementation passes 103
  focused orchestration tests; immutable D-134 at `6 passed, 3 skipped`; D-136
  at `4 passed, 3 skipped`; and the exact current D-137-through-D-141 related
  suite at `128 passed, 0 skipped, 0 failed` in 0.74 seconds (0.96 wrapper
  wall-seconds). This supersedes the earlier 118-test prospective count.

  The exact safe command
  `uv run --locked pytest --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`
  reports `1425 passed, 10 skipped, 0 failed` in 346.49 seconds (346.98 wrapper
  wall-seconds; 902,124 KiB maximum RSS). Diff integrity, Ruff over allowed
  paths with barred G2-7B paths explicitly excluded, strict mypy across 78
  source files, package build, and two independent installed-wheel runs with
  byte-identical output also pass. The four hashes remained stable before and
  after validation.

  No fixed composite acceptance was invoked. Disposable synthetic fixture
  claims were used only in temporary public roots. No official source/baseline
  byte or fixed private root was opened or created, and no private claim was
  created or opened. Read-only authentication of the tracked public claim
  occurred; those bytes remain identical, unusable, and unconsumed. D-141
  changes no candidate, feature, seed, group, fit topology, prediction rule, metric,
  resource ceiling, selection token, no-runner-up rule, or frozen fallback. It
  is implementation evidence only and grants zero formal-acceptance, official,
  claim, science, model-quality, confirmatory, submission, or upload authority.
- Alternatives: Run the fixed acceptance from the implementation branch;
  combine implementation and one-use evidence; retain the five obsolete audit
  nodes; broaden skips; change historical snapshots; add a candidate, feature,
  seed, group, retry, cache, concurrency, framework, or service; modify the
  science kernel, status taxonomy, accounting, resource, selection, or privacy
  contract; open official or confirmatory bytes; or use leaderboard evidence.
- Reversal condition: Any drift in one of the four D-141 hashes, D-137/D-138
  mechanics, exact D-139/D-140 transition cardinality, historical active-node
  set, lineage bindings, safe-suite result, zero-operation boundary, signed
  integration, or exact-SHA post-main CI blocks progression. Otherwise
  integrate D-141 by signed fast-forward, require green post-main CI, then run
  a fresh fixed-root preflight and invoke the sole no-argument composite
  acceptance exactly once. Package its immutable aggregate as a separate
  reviewed milestone before any official attempt preflight.

## D-142 — Accept the sole G2-7H composite-orchestration mechanics receipt

- Date: 2026-08-27
- Status: accepted aggregate mechanics evidence pending reviewed signed
  integration; D-141 is integrated as signed commit
  `61e335485ab983cdf1f030aedefd64ea8252b492` with green PR CI run
  `33112350539` and green exact-SHA post-main CI run `33113306698`; the sole
  fixed no-argument composite acceptance ran exactly once from clean
  synchronized `main` and exited zero; official G2-7G execution remains unrun;
  tracked claim remains byte-identical, unusable, and unconsumed; zero
  official/private-byte, official/tracked/private-claim mutation or
  consumption, fit, prediction, development-metric, confirmatory,
  blinded-test, TDI, submission, leaderboard, portal, upload, science, or
  model-quality operation or authority
- Decision: Accept the immutable 72,449-byte canonical public receipt
  `global_v2_maplight_robustness_official_orchestration_acceptance.json` with
  status `G2_7H_MAPLIGHT_ROBUSTNESS_OFFICIAL_ORCHESTRATION_ACCEPTED` and
  SHA-256
  `92a18f0e6837d70d4bb39560d42a22cfb23acac8ea72a955b9656b392d954596`.
  Publication was observed as a regular, single-link file with mode `0444`.
  Git does not preserve owner-write bits, so that mode is immutable
  publication evidence but not a fresh-checkout CI invariant; canonical bytes
  and SHA-256 are the portable identity. Preserve the exact D-122 battery,
  D-135 science kernel, D-136 provenance, D-137/D-138 mechanics, D-139/D-140
  transitions, and D-141 implementation without rerun or reinterpretation.
- Evidence: The receipt proves forward and reverse execution orders, six
  scenarios per order, 12 scenario and 12 supervisor invocations,
  independently byte-identical normalized maps, the exact five official
  terminal statuses plus fail-closed pre-consumption propagation, all eleven
  frozen mechanics checks, and each of ten mechanics-probe counters exactly
  once. Applicable scientific-success and rejection fixtures preserve one
  selection token and no runner-up; underpowered preserves zero science.
  Every populated terminal lineage matches the reviewed D-135-through-D-141
  implementation, contract, and immutable science hashes. D-135's 3,480
  model-double invocations, 667,872 synthetic predictions, and two real
  CatBoost controls are inherited with `reexecuted=false`; D-142 performs none
  of them. The standalone public receipt audit test at SHA-256
  `10ebb8f18d38f6d069e35d3994468e6a70dc0de3df6cb5736352721be439a28c`
  passes `1/1` and binds canonical bytes, lineage, order identity, mechanics,
  privacy, and zero authority without asserting the non-portable checkout
  mode.

  Every scenario has cleanup complete, cleanup finished before receipt
  publication, `private_roots_retained` is zero, the fixed acceptance parent
  and work roots are absent, and no rejection record exists. All top-level
  forbidden-operation counters are zero, including official source/baseline
  bytes, official or tracked/private claim creation/consumption, model-double
  and real-CatBoost fits, predictions, metric calls, confirmatory/test/TDI
  rows, submissions, and uploads. All aggregate authority fields are false.

  Disposable synthetic mechanics are not hidden as false-zero claim evidence:
  the receipt separately records 10 scenario fixture-claim publications, six
  probe publications, and one intentionally interrupted synthetic claim
  staging. These occurred only in disposable public roots; no tracked claim
  was mutated or consumed, no private claim was created or opened, and no
  official byte was touched. The receipt contains no absolute/private path or
  row-level molecule, structure, target, prediction, or metric value. D-142 is
  formal composite-orchestration mechanics evidence only and grants zero
  official-execution, model-quality, confirmatory, submission, or upload
  authority.
- Alternatives: Repeat or repair the acceptance; run it with alternate roots
  or outputs; combine its review with official execution; reinterpret fixture
  accounting as model-quality evidence; hide synthetic claim activity behind
  generic zero-claim wording; modify D-141-bound files; add a candidate,
  feature, seed, group, retry, cache, concurrency, framework, or service; open
  official, confirmatory, blinded-test, TDI, row-level, leaderboard, or portal
  evidence; or live-upload.
- Reversal condition: Any receipt-byte, status, lineage, order-map, taxonomy,
  mechanics, probe-count, cleanup, privacy, zero-authority, D-141 signed
  integration, or exact-SHA CI mismatch blocks official progression. Otherwise
  integrate D-142 by signed fast-forward and require green exact-SHA post-main
  CI, then perform a fresh official one-use preflight. If and only if contract,
  receipt chain, tracked claim, runtimes, resources, fixed-root absence,
  supervisor readiness, and source/baseline allowlist receipts authenticate,
  invoke the sole fixed no-argument G2-7G official driver exactly once. Do not
  retry, resume, move, repair, overwrite, replace, or reinterpret it.

## D-143 — Accept the official G2-7G underpowered terminal as pre-science negative evidence

- Date: 2026-08-27
- Status: accepted aggregate terminal negative evidence pending reviewed
  signed integration; D-142 is integrated as signed commit
  `d70d817dd2d7e30f63f6066dfbfdc4cef7e02bd3` through PR #179 with green PR
  CI run `33116144405` and green exact-SHA post-main CI run `33116954304`;
  the sole fixed no-argument official G2-7G attempt ran once, consumed its
  private claim once, exited zero, and published
  `G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED`; no contender, confirmatory score,
  blinded-test prediction, submission, validation, leaderboard observation,
  portal operation, or upload is authorized
- Decision: Accept the canonical privacy-safe public projection
  `global_v2_maplight_robustness_official_underpowered.json`, schema
  `cypshift.openadmet_cyp_2026.global_v2_maplight_robustness_official_underpowered.v1`,
  at SHA-256
  `d52bee5e4ed4669c6db7e3061fc8aed8f55e81a0e4d3d17aca73e326df184a2d`
  and size 9,945 bytes. Accept its public-only audit test
  `tests/test_openadmet_global_v2_maplight_robustness_official_underpowered.py`
  at SHA-256
  `e5d65bf32a9185ea3c3c63bb658d5418e8393ec534488f50cbeb4dad1a8354ce`,
  size 21,081 bytes, with `1/1 passed`. Treat the terminal as a clean
  pre-science support stop and permanent consumption of the one-use lane. Do
  not characterize it as accepted robustness, a full-MapLight retention token,
  scientific rejection of MapLight, or any model-quality result.
- Evidence: D-142's signed integration and all three exact-SHA post-main CI
  lanes were green before a fresh official preflight. The accepted driver then
  ran once with no caller-selected root or output. Only the exact compiler
  `RobustnessExecutionUnderpowered` route produced the status, after the
  supervised child consumed the private claim and parsed the allowed official
  development source but before any fit, prediction, baseline open, selection
  token, or development metric.

  Complete terminal accounting records 19,620 direct endpoint rows, 73,575
  group-fold rows, 5,197 finite central point values, 4,905 feature-identity
  rows, 19,620 feature-matrix rows, and 24,525 total feature rows. Baseline
  prediction rows, scoring truth, training targets, reported bounds, generated
  model folds/features, prediction rows reopened for scoring, official model
  fits, Stage A/B/C predictions, tutorial calls, and development metric
  evaluations are all zero. The manifest has `selected_candidate=null`,
  `selection_tokens=0`, and `runner_ups=0`; no row-level value or model binary
  is retained. The public record distinguishes those authorized aggregate
  official reads from its denied *future* authority instead of making a false
  zero-official-operation claim.

  All frozen numeric minima pass across all 240 support cells. The one preflight
  failure has exact reason `TAUTOMER_MERGED:confirmatory_touch_not_exercised`.
  The frozen predicate requires confirmatory-touch exercise before fitting;
  observed support and exclusion values remain omitted from the public
  projection. The failure is label-free family-support mechanics, not an
  endpoint error or model-quality observation.

  The exact cumulative observation has integer return code zero, three
  checkpoints, two descendants, cleanup complete, isolated networking, hidden
  GPU environment, and zero GPU-hours, detached children, and warnings. It
  used 33.09143570300148 wall-seconds, 33.194318974000005 CPU-seconds, 8,192
  peak storage bytes, and 289,660,928 peak simultaneous RSS bytes, all below
  the D-137 maxima. The common seal retained exactly `attempt_receipt.json`,
  `manifest.json`, and `preflight.json` under the read-only terminal. The
  restricted work root, publication staging, and claim staging are absent. The
  fixed attempt root correctly remains with exactly `attempt_claim.json` and
  `terminal`; this is immutable one-use evidence, not retained scientific work
  state.

  The public projection contains only exact public lineage; hashes, sizes, and
  observed modes for private aggregate evidence; allowlisted accounting and
  resources; cleanup and terminal shape; a bounded support-stop summary; and
  denied authority. It copies no private receipt, manifest, preflight, support
  table, path, row, molecule identifier, structure, target, prediction,
  component membership, feature matrix, model, PID, unrestricted log, portal
  identifier, score, or rank. Duplicate-key and nonfinite rejection plus
  sorted two-space JSON with one LF define portable identity; private `0444`/
  `0555` modes are observations, not Git checkout invariants.

  The dedicated public audit passes `1/1`; Ruff check, Ruff format check,
  Python compilation, record canonical/hash/size verification, 18-column CSV
  and embedded-JSON validation, and diff integrity are green. The completed
  local safe repository suite, with the permanently barred G2-7B test
  explicitly ignored, reports `1425 passed, 10 skipped, 2 failed` in 357.51
  seconds. Its only failures are
  `tests/test_openadmet_global_v2_maplight_robustness_execution_contract_v2.py::test_new_attempt_root_is_distinct_and_absent_at_freeze`
  and
  `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_supervisor_precedes_claim_consumption_and_common_seal_owns_terminal_publication`.
  Both are historical pre-execution root-absence assertions invalidated only
  by the intended immutable terminal retention. This is expected negative
  state-transition evidence, not a D-143 semantic, privacy, mechanics,
  scientific, or model-quality failure.

  The tracked public claim template remains byte-identical, unusable, and
  unconsumed. The private derived claim is permanently consumed. Full MapLight
  remains the best previously validated system at internal component-macro MAE
  `0.5837812652`, but this attempt neither selected nor robustness-validated
  it. D-122's full-default clause belongs inside completed Stage-A selection
  and yields one token; applying it to a terminal with null candidate and zero
  token would be post-outcome reinterpretation. The frozen G2-8 boundary
  requires an accepted G2-7 contender lock, so D-143 grants zero model-quality,
  confirmatory, blinded-test, TDI, full-training, submission, validator,
  official-metric, leaderboard, portal, credential, or upload authority.
- Alternatives: Retry, resume, move, repair, overwrite, replace, or shrink the
  battery; rerun under another order or root; relax the observed family-support
  rule; adjust a component, mask, candidate, seed, group, threshold, feature,
  denominator, cache, or concurrency; issue a full-MapLight token after the
  fact; promote a runner-up; inspect private row-level evidence; copy the
  private aggregate terminal verbatim into Git; expose support tables or
  private paths; open confirmatory truth or blinded test; use portal or
  leaderboard evidence; generate or validate a submission; or upload.
- Reversal condition: Any mismatch in the private immutable receipt hashes,
  public projection bytes, exact status, lineage, underpowered accounting,
  cumulative observation, cleanup/file-set evidence, privacy allowlist,
  zero-science facts, or dedicated audit test blocks D-143 packaging but never
  authorizes another official attempt. Otherwise integrate D-143 through the
  signed fast-forward-only workflow and require green exact-SHA post-main CI.
  Then freeze and integrate D-144 as a contract-only exact-four-node
  transition: the two current root-absence failures, the D-140 six-skip
  collection audit
  `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_d140_source_shape_collection_has_six_exact_skips_and_active_replacements`,
  and the D-142 acceptance-record live-conftest-hash audit
  `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration_acceptance_record.py::test_formal_orchestration_acceptance_record_is_exact_and_static`.
  Preserve the prior six exact skips and freeze ten total. Only then may D-145
  change conftest with the four exact markers and add one comprehensive public
  replacement audit covering collection/hash state and every surviving
  assertion from the two currently failing nodes; require green post-main CI
  after each milestone. D-144/D-145 are
  validator-hygiene evidence only and grant zero science, gate, private-data,
  claim, model-quality, confirmatory, or submission authority. After D-145,
  stop this Global-v2 submission path with G2-8 closed. A future lane
  requires separate explicit user authorization and a genuinely new
  prospective scientific hypothesis and contract; it cannot be a retry,
  repair, replacement, support relaxation, or reinterpretation of G2-7G.

## D-144 — Freeze the post-attempt exact-node test transition before collection changes

- Date: 2026-08-27
- Status: accepted contract-only validator-hygiene evidence pending reviewed
  signed integration; D-143 is integrated as signed commit
  `d630702074bfefa4bda4730ba7c1b7519c3c6f1a` with green PR CI run
  `33121287357` and green exact-SHA post-main CI run `33122070763`; D-144
  changes no collection, implementation, historical test, official result,
  science, claim, private artifact, gate, or authority; G2-8 remains closed
- Decision: Accept only
  `global_v2_maplight_robustness_post_attempt_test_transition_contract.json`
  at SHA-256
  `d5eb773fc2584deaf31c5f3a3a283e365b6540d0c714fd08cb70ec02937b735f`
  (18,216 bytes) and its public contract test
  `tests/test_openadmet_global_v2_maplight_robustness_post_attempt_test_transition_contract.py`
  at SHA-256
  `a654075771d9f42ac3a7dcbf058e8ca4dba879660888c2aa4262d1e4ea60a1fa`
  (29,788 bytes), with `1/1 passed`. Freeze four and only four future D-145
  retirements while preserving all six existing exact markers:

  1. `tests/test_openadmet_global_v2_maplight_robustness_execution_contract_v2.py::test_new_attempt_root_is_distinct_and_absent_at_freeze`;
  2. `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_supervisor_precedes_claim_consumption_and_common_seal_owns_terminal_publication`;
  3. `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration.py::test_d140_source_shape_collection_has_six_exact_skips_and_active_replacements`;
  4. `tests/test_openadmet_global_v2_maplight_robustness_official_orchestration_acceptance_record.py::test_formal_orchestration_acceptance_record_is_exact_and_static`.

  Require exactly ten markers after D-145. Authorize D-145 to change only
  `tests/conftest.py` and add one comprehensive public audit that owns the new
  collection/hash state and every surviving semantic assertion from nodes 1
  and 2. Without importing a driver or inspecting live protected state, that
  audit must preserve node 1's D-133 historical
  `attempt_root_absent_at_freeze` fact, corrected official-attempt-root identity
  and exact barred-D-127 distinction, tracked-public-claim fixed-root mapping,
  and frozen read boundary. It must preserve node 2's D-141 D-140 source-shape
  binding, outer/child supervisor-to-claim-to-compile-to-Stage-A chronology,
  raw-observation assignment, publication and writable-parent arguments equal
  to resource limits, fixed attempt-root identity, aggregate-only
  `_failure_payload` accounting, common-seal exclusivity, and absence of parent
  `_finalize_terminal` and child `PENDING_TERMINAL_ROOT`. Nodes 3 and 4 are
  frozen prospectively because the conftest marker
  set/hash change will make their six-marker/live-hash premises historical.
- Evidence: D-143's local safe suite, with the permanently barred G2-7B test
  explicitly ignored, reported `1425 passed, 10 skipped, 2 failed` in 357.51
  seconds. Only nodes 1 and 2 failed, solely because the authorized one-use
  root now retains immutable consumed-claim/terminal evidence. Nodes 3 and 4
  still pass before collection changes. The D-144 contract preserves the
  historical files byte-for-byte, binds the signed D-143 record/test lineage,
  forbids file/class/prefix skipping, deselection, xfail, and any fifth node,
  and grants no implementation or collection authority. This is validator
  provenance, not new model-quality or scientific evidence.
- Alternatives: Modify any historical test; add conftest markers before a
  reviewed contract; broaden a skip to a file, class, prefix, or changing
  hash; retire only the two currently failing nodes and let D-145 break the
  collection/hash audits; combine D-144 contract and D-145 implementation;
  alter the D-143 record or test; reopen, retry, repair, replace, or reinterpret
  G2-7G; open protected data; or infer G2-8 authority.
- Reversal condition: Any drift in either D-144 hash, D-143 signed lineage,
  exact four-node cardinality, prior-six preservation, future-ten total,
  D-145 two-file limit, comprehensive replacement scope, historical bytes,
  zero-authority boundary, signed integration, or exact-SHA post-main CI
  blocks D-145. Otherwise integrate D-144 through the signed fast-forward-only
  workflow, require green post-main CI, then let D-145 change only conftest and
  the one public audit. After reviewed D-145 integration and green post-main
  CI, stop with G2-8 closed.

## D-146 — Accept validator-clean post-attempt provenance and close the active path

- Date: 2026-08-27
- Status: accepted knowledgebase/ledger closure evidence pending reviewed
  signed integration; D-144 is integrated as signed commit
  `5d7ed5db76ec0928ba34e19e72ab839ee556d51e` through PR #181 with green PR CI
  run `33123874692` and green exact-SHA post-main CI run `33124525495`; D-145
  is integrated as signed commit
  `ce289b5fccaaf1d63343553961ad41309db19d04` through PR #182 with green PR CI
  run `33125925508` and green exact-SHA post-main CI run `33126546606`
- Decision: Accept the D-144-authorized D-145 transition as exact
  validator-hygiene evidence and close the active Global-v2 submission path.
  Bind `tests/conftest.py` at SHA-256
  `e92e9114ff874e71e8468320595489bc5d294653d6ff93b347cc3be27f9a01d9`
  (4,452 bytes / 110 lines) and the sole comprehensive public audit
  `tests/test_openadmet_global_v2_maplight_robustness_post_attempt_test_transition.py`
  at SHA-256
  `2a58d9423aa99f6b441b9d173b9e2c9e263117ced46343e7e90acf90bad7eac3`
  (23,826 bytes / 603 lines). Preserve all six prior exact markers, add only
  the four frozen markers for exactly ten, keep the sole D-145 audit and
  unrelated nodes active, and keep every prior replacement active except the
  exact transitioned D-141 supervisor node.
- Evidence: The D-144/D-145 focused pair passed `2/2`. The exact bounded safe
  command
  `uv run --locked pytest --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`
  completed with `1425 passed, 14 skipped, 0 failed` in 341.76 seconds.
  Historical tests, the D-143 public record/audit, contracts, drivers, claims,
  and science bytes are unchanged. The comprehensive audit owns the live
  conftest hash/collection state, treats the D-142 conftest hash as historical,
  preserves every contracted D-133/D-141/D-142 responsibility, proves the
  D-143 aggregate UNDERPOWERED terminal boundary, imports no driver, opens no
  tracked claim, and probes no protected root. Local CI parity also passed
  Ruff, format, compilation, mypy over 78 source files, isolated build, and a
  byte-identical Python 3.12.3 installed-wheel two-root vertical slice.
- Authority boundary: D-146 changes only seven knowledgebase/ledger surfaces.
  D-145/D-146 perform zero driver execution, official attempt, claim
  creation/consumption, official-source/baseline open, protected-data access,
  development-robustness or official model fit/prediction/metric, selection
  token, contender lock, or submission operation. The two-root installed-wheel
  public synthetic-fixture smoke is CI parity only. They create no robustness or
  model-quality evidence and grant no G2-8, confirmatory, blinded-test,
  full-training, submission, validator, leaderboard, portal, credential,
  upload, or other scientific authority. Full MapLight remains only the best
  previously validated internal system at component-macro MAE `0.5837812652`;
  the consumed attempt did not select, retain, or robustness-validate it.
- Alternatives: Rewrite a historical test; broaden or add a collection skip;
  add another audit; mutate D-143 evidence, a contract, driver, claim, record,
  or science file; retry, repair, replace, relax, reorder, or reinterpret
  G2-7G; infer a full-MapLight token; promote a runner-up; open G2-8 or
  protected data; generate, validate, or upload a submission.
- Reversal condition: Any mismatch in D-144/D-145 signed lineage or CI, either
  D-145 hash, exact ten-marker/one-active-audit state, focused or bounded-suite
  result, historical/D-143 bytes, privacy boundary, zero-authority accounting,
  seven-file scope, signed integration, or exact-SHA post-main CI blocks D-146
  acceptance but cannot authorize scientific progression. Otherwise integrate
  D-146 through signed fast-forward-only review, require green post-main CI,
  and stop. New science requires explicit prospective user direction and a
  genuinely new hypothesis/contract; it cannot retry, repair, replace, relax,
  or reinterpret the consumed G2-7G attempt.

## D-147 — Freeze the distinct Global-v3 EXP-G4-GIN300 pretrained-transfer experiment

- Date: 2026-08-30
- Status: accepted and integrated as signed commit
  `b5cf47c6bc8ccc2dc29c7167b1a436d792338509` through PR #184 with green PR CI
  run `33327853790` and green exact-SHA post-main CI run `33328374514`;
  Global-v2 remains closed, G2-7G remains permanently UNDERPOWERED, and G2-8
  remains closed
- Decision: Accept only the canonical Global-v3 contract
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_contract.json` at SHA-256
  `b48dc0c39c12b06cdd99693539cca18b99c73d8b801e81a416e52a798df8fd4e`
  (37,092 bytes / 485 lines) and its strict public static audit
  `tests/test_openadmet_global_v3_g4_gin300_contract.py` at SHA-256
  `c32e8054da4c92f763c065c8d58d340993f6917c5c6a6d3580659febea69e3dc`
  (31,371 bytes / 815 lines), with `9/9 passed`. Freeze a genuinely new
  challenge-fold-family-held-out pretrained-transfer hypothesis: concatenate
  the exact 300-column `gin_supervised_masking` representation after the
  accepted 2,563 MapLight columns and keep the accepted fixed CatBoost learner,
  parameters, folds, masks, and seed unchanged. Compare the true GIN block with
  two mandatory same-learner, partition-local controls: whole-vector-shuffled
  GIN and matched Gaussian noise. The controls may not move a donor, identity,
  or feature vector across a training-validation boundary.
- Scientific gate: A future separately authorized development attempt is fixed
  at three systems, three repeats, five outer challenge-family folds, four
  endpoints, exactly 180 new fits, 140,688 new outer-prediction rows, zero
  baseline refits, 48 tutorial calls, and one synchronized 2,000-replicate
  component-bootstrap stream shared across five contrasts. Candidate promotion
  requires every frozen baseline member: at least 3% tutorial-primary
  improvement, 0.015 absolute component-macro MAE improvement, paired upper
  95% bound below zero, at least 8/15 favorable cells, no endpoint degradation
  above 0.015, and at least one of CYP1A2/CYP2D6 improving by 0.010. Attribution
  additionally requires at least 1% tutorial-primary and 0.005 component-macro
  improvement over each control, paired upper bounds below zero, at least 8/15
  favorable cells against each, and neither control independently passing the
  baseline gate. Every member is conjunctive. A clean miss closes
  `EXP-G4-GIN300`; no tuning, blend, extra seed, alternate checkpoint, endpoint
  repair, control, runner-up, or outcome-driven successor is authorized.
- Provenance boundary: Historical fixed-plus-GIN evidence improved binary
  CYP2C9, CYP2D6, and CYP3A4 AUPRC under scaffold and chemistry-community
  holdouts, while shuffle/noise controls did not reproduce the gain. That is
  hypothesis support only: it is not OpenADMET pIC50 evidence, contains no
  historical CYP1A2 result, and cannot establish family separation from the
  unknown pretraining corpus. The frozen current Space rules permit pretrained
  models, but the ZINC15/ChEMBL pretraining lineage has unknown OpenADMET
  structure and assay overlap. That overlap must be disclosed and forbids clean
  zero-shot, uncontaminated external-validation, strict pretraining-family-
  holdout, and known-no-overlap claims. Exact SNAP, DGL-LifeSci, and MolFeat
  object identity; rights and notices; tensor conversion; graph construction;
  Linux parity; and nonredistribution are mandatory prospective eligibility
  gates.
- Public-source audit accounting: Contract preparation downloaded one public
  SNAP source archive to temporary non-Git storage, temporarily persisted 33
  public checkpoint files totaling 204,567,885 bytes, and opened one
  7,452,448-byte SNAP checkpoint only for hashing. It downloaded zero DGL or
  MolFeat checkpoint bytes, deserialized or executed zero checkpoint tensors,
  generated zero embeddings, and added no checkpoint to Git or the workspace.
  This is bounded source-rights/hash evidence, not checkpoint model loading,
  parity execution, feature generation, or current fetch/load authority.
- Validation evidence: The focused contract audit passes `9/9`. The bounded
  safe repository command
  `uv run --locked pytest --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`
  completed with `1434 passed, 14 skipped, 0 failed` in 347.99 pytest seconds /
  348.42 wall-seconds at 901,484 KiB maximum RSS. Ruff, mypy, isolated build,
  and installed-wheel two-root reproduction are green. These are repository and
  CI parity checks only; they create no model-quality or downstream authority.
- Authority boundary: D-147 consists of one contract, one public static test,
  and the exactly disclosed bounded public source-rights/hash audit. It changes
  no dependency or runtime and adds no implementation. It
  opens zero pretraining row, official input, official structure, target value,
  baseline prediction, feature row, confirmatory truth, historical row-level
  artifact, blinded-test row, or TDI row. It performs zero GIN feature build,
  model fit, prediction, development metric, bootstrap, claim creation or
  consumption, selection token, contender lock, full training, submission row,
  validator call, official metric, leaderboard selection, portal or credential
  access, live upload, or GPU operation. The only current authority is the
  contract and public static audit.
- Sequence: After D-147 is independently reviewed, SSH-signed, integrated
  locally by fast-forward only, pushed without rewriting, and green on exact-SHA
  post-main CI, D-148 may freeze only a separate Linux x86_64
  rights/provenance/runtime and label-free synthetic-capability **contract** and
  public static tests. D-148 may not fetch or load a checkpoint, create a
  runtime, implement a feature builder, execute parity or a model, open an
  official row or target, or create a claim. Only after D-148 receives the same
  signed/integrated/green treatment may a later milestone implement and then
  execute the frozen boundary. D-148 subsequently supersedes the prospective
  assignment here: D-149 is implementation/static validation only, while D-150
  owns the sole formal invocation. Any rights, notice, object-hash, tensor,
  graph, embedding,
  Linux-parity, nonredistribution, determinism, or resource failure closes the
  lane before official access, without in-place repair.
  Any future CatBoost API/timing probe must use only contract-frozen
  redistributable synthetic labels and no official target. A hard claim-bound
  feature or development resource breach publishes
  `G3_G4_GIN300_RESOURCE_ABORTED`; partial scientific evidence then has zero
  model-quality authority.
- Alternatives: Retry, repair, replace, resume, relax, or reinterpret G2-7G;
  reuse a prior claim or root; treat fixed MapLight as selected by the
  underpowered terminal; choose a candidate from the failed support outcome;
  use standardized rather than exact-raw identity for GIN; fine-tune a
  checkpoint; normalize, select, compress, calibrate, stack, or blend features;
  add an endpoint-specific recipe, extra seed, model, checkpoint, control, or
  fallback; use confirmatory, test, TDI, leaderboard, or portal evidence; claim
  clean external validation; combine D-147 contract with D-148 or D-149
  implementation; or fetch/run before the required signed gates.
- Reversal condition: Any mismatch in the contract/test hash, canonical bytes,
  D-146 signed/green base, rules snapshot, parent receipts, exact-raw or family
  boundary, candidate/control identity, fit/prediction/bootstrap budget,
  promotion or attribution gate, public-source audit accounting,
  unknown-overlap disclosure, rights/nonredistribution boundary, terminal
  precedence, D-148/D-149 separation, nine-file scope, zero-authority
  accounting, signed integration, or exact-SHA post-main CI blocks D-148 but
  cannot reopen any closed lane. That signed fast-forward-only integration and
  green post-main CI subsequently completed; D-148 now supersedes only the old
  prospective D-149 execution assignment while preserving every D-147
  scientific and authority boundary.

## D-148 — Freeze the EXP-G4-GIN300 capability, runtime, and one-use boundary

- Date: 2026-08-30
- Status: accepted and integrated as signed commit
  `f0f3b6f9380eebef0b03d87f29eb659ffc84f8d5` through PR #185 with green PR CI
  run `33337794223` and green exact-SHA post-main CI run `33338342415`; its
  signed parent is D-147 commit
  `b5cf47c6bc8ccc2dc29c7167b1a436d792338509`; Global-v2 remains closed, G2-7G
  remains permanently UNDERPOWERED, and G2-8 remains closed.
- Decision: Freeze status `G3_2_EXP_G4_GIN300_CAPABILITY_CONTRACT_FROZEN`
  through the canonical capability contract
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_capability_contract.json`
  at SHA-256
  `df8796575c3d6093dd4038f4268417a979b8edca14245a7acff26e3db18eaa44`
  (184,100 bytes / 1,687 lines), the bound Linux x86_64 CPU-runtime manifest at
  SHA-256
  `67b58fc5eb9d1d3c0652bad9fa85eb1e688ed4bfb93d9ee107cad4db3e0ace01`
  (166,425 bytes / 4,008 lines), and the third-party notices at SHA-256
  `b76b026a7ed61c0c33cc9f78d66ca235e01e9d2c504126238e0f6e0f58e18deb`
  (12,456 bytes / 241 lines). Bind the strict public audit at SHA-256
  `d9318267ff607703b9d957fc2fa13b79af61740b486471ab0556c06f3205bb12`
  (97,426 bytes / 2,509 lines) with `15/15 passed`.
- Runtime boundary: Bind install-only CPython 3.10.13 plus exactly 96 CPU
  wheels, 185 dependency edges, 539,395,366 wheel bytes, and 97 manifest
  distribution artifacts totaling 566,804,656 bytes. Require the full
  `molfeat[dgl,transformer]` closure and forbid CUDA, NCCL, and Triton. Permit
  exactly one post-cutoff package wheel, `future==1.0.0`, because the historical
  version is sdist-only; disclose the separately frozen 20240224 interpreter as
  infrastructure. A future clean fetch authenticates 98 runtime network files
  including the sidecar (566,804,721 bytes), three model/checkpoint objects
  (22,374,079 bytes), one 606-byte MolFeat metadata object, and exactly two
  redirects.
- Capability oracle: Require three isolated CPU processes over the fixed
  eight-row redistributable fixture. The SNAP conversion, native DGL loader,
  and MolFeat public local-store path must all yield the exact bare
  `dgllife.model.gnn.gin.GIN` with 57 unprefixed state keys and no predictor,
  readout, head, wrapper, prefix, or extra key. Tensor and graph manifests are
  exact. Embeddings must either be byte-identical or follow the prospectively
  frozen `max_abs <= 1e-7`, `rtol=0` numeric branch and then yield 48 exact
  fallback predictions from the two candidate models. Require two uncached
  3,908-row GIN roots, the 3,908-molecule / 3,640-component official-shaped
  synthetic topology, 180 model-double fits and 140,688 predictions per root,
  six real CatBoost fits and 4,692 validation predictions, and 20% wall, CPU,
  storage, and simultaneous-RSS prefit margin with zero GPU.
- Supervision and one-use boundary: Freeze fixed private roots, authenticated
  public objects and tools, an outer stdlib supervisor that never consumes the
  claim, and a child that reaches an acknowledged ready checkpoint before it
  atomically consumes and permanently tombstones the sole claim. No private
  work root or network operation exists before consumption. Fetch is exact,
  sequential, bounded, and nonresumable; every deserialize/tensor/graph/
  embedding/CatBoost worker executes inside the frozen offline CPU sandbox.
  The child returns only a bounded aggregate payload. The outer authoritatively
  cleans and verifies mutable roots before common seal, retains only the exact
  runtime and SNAP object on a fully accepted candidate, and publishes one
  no-replace aggregate result. No retry, resume, repair, alternate object, or
  second terminal exists.
- Milestone split: D-149 is exactly a 14-path implementation, lock, test,
  narrative, and ledger milestone. It may author the isolated-project evidence
  mirror, builder, stdlib runner, and two public tests, but it may fetch no
  artifact body, create no private root/runtime, import or execute the
  scientific stack, deserialize no checkpoint, run no parity/scaled-GIN/
  synthetic/CatBoost operation, consume no claim, and publish no result. Only
  after D-149 is reviewed, SSH-signed, fast-forward integrated, and green on
  exact-SHA post-main CI may separate eight-path D-150 perform the single formal
  capability invocation. This split supersedes D-147's prospective assignment
  of both implementation and execution to D-149.
- D-148 evidence accounting: Contract preparation downloaded zero wheel,
  interpreter-archive, checkpoint/model, transformer, or tokenizer artifact
  bodies; created or installed no runtime; imported or executed no scientific
  package; and ran no model, parity, feature, fit, prediction, or resource
  probe. It recorded six checkpoint/model HEAD requests and zero such body
  bytes; one 606-byte MolFeat metadata GET plus one HEAD; two interpreter
  archive/sidecar HEAD requests with zero body on those HEADs; 95
  distinct PyPI release-JSON resources; nine SPDX JSON resources; the PyTorch
  CPU simple-index resource; one 65-byte checksum-sidecar GET; and one
  1,495-byte build-license GET. Total public-source transactions and metadata
  bytes not instrumented during the audit remain unknown and are not inferred.
- Validation evidence: The focused static audit passes `15/15`. The exact
  bounded safe-suite command
  `PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v uv run --locked pytest -p no:cacheprovider --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`
  completed with `1449 passed, 14 skipped, 0 failed` in 349.72 pytest seconds /
  350.21 wall-seconds at 903,624 kB maximum RSS and exit status zero. Ruff over
  325 allowed Python files with the exact barred G2-7B runner, driver, and test
  excluded; format and temporary compilation of the D-148 audit; mypy over 78
  source files; offline isolated build; and a fresh Python 3.12.3 installed-
  wheel two-root audit/train/predict/report replay all pass. The two smoke roots
  are byte-identical at 9 files / 36,758 bytes each. The 11 package hashes and
  Git status are identical before and after validation. Incidental build and
  tree hashes are not frozen and confer no scientific or execution authority.
- Terminal meaning: A clean D-150 result
  `G3_3_EXP_G4_GIN300_CAPABILITY_ACCEPTED` is capability-only engineering
  evidence and explicitly not scientific `ACCEPTED`, model-quality evidence,
  official access, feature authority, development authority, or selection.
  Rights, notice, object, tensor, graph, parity, or nonredistribution defects
  map to
  `G3_G4_GIN300_INELIGIBLE_PRETRAINED_PROVENANCE_OR_PARITY_FAILED`; a complete
  prefit projection margin miss maps to
  `G3_G4_GIN300_RESOURCE_INFEASIBLE_PREFIT`; malformed, operational,
  incomplete-integrity, hard-ceiling, or supervision failures map to
  `G3_G4_GIN300_FAILED`. `G3_G4_GIN300_RESOURCE_ABORTED` remains reserved for
  a later claim-bound official feature/development attempt and cannot be
  emitted by D-148, D-149, or D-150.
- Authority boundary: D-148 changes only its contract, runtime manifest,
  notices, public static audit, six narrative surfaces, and ledger. It creates
  no checkpoint-fetch/load authority, runtime/execution authority, official or
  private-data read authority, scientific/model-quality evidence, claim,
  contender, selection, confirmatory/test/TDI, submission, validator,
  leaderboard, portal, credential, upload, or GPU authority. D-127/D-128 and
  every closed Global-v2 path remain barred.
- Alternatives: Let D-149 execute before its own reviewed integration; combine
  code creation and one-use claim consumption; fetch or install during D-148 or
  D-149; use a non-CPU runtime or unbound wheel; infer checkpoint structure;
  accept a head/wrapper/prefix mismatch; relax tensor, graph, or embedding
  parity after observing it; retry a fetch or claim; clean after publication;
  publish a partial/private payload; use official targets for a capability
  probe; reinterpret capability success as scientific acceptance; or emit
  `RESOURCE_ABORTED` before a later official claim-bound operation.
- Reversal condition: Any mismatch in integrated D-147 lineage, one of the four
  D-148 core identities, canonical bytes, CPU-runtime inventory, rights/notices,
  direct bare-GIN tensor map, graph/parity oracle, synthetic topology and
  operation counts, resource formulas, one-use chronology, cleanup-before-seal
  boundary, D-149-zero/D-150-run split, terminal taxonomy, zero-authority or
  public-network accounting, tracked scope, signed review, or exact-SHA CI
  blocks D-148 integration without opening any scientific or official lane.
  That signed fast-forward-only integration and green post-main CI completed.
  D-149 below supersedes only D-148's prospective later-milestone schedule;
  D-148 remains immutable contract-only history.

## D-149 — Close EXP-G4-GIN300 preclaim after terminal transition audit

- Date: 2026-08-30
- Status: terminal decision accepted and integrated at
  `G3_2_EXP_G4_GIN300_PRECLAIM_CLOSED` as signed commit
  `0bf9b253002399a61e3d8d4e37e1a957ebd198ec` through PR #186, with green
  exact-head PR CI run `33348758894` and green exact-SHA post-main push CI run
  `33349365347`. Integration preserved the signed commit without rewriting.
  No later defect can reopen G4.
- Decision: Permanently close `EXP-G4-GIN300` before claim consumption. Record
  the closure under schema
  `cypshift.openadmet_cyp_2026.global_v3_g4_gin300_transition_rejection.v1` in
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json`
  at SHA-256
  `10a7f783d73ae60c6da479ffbd8cd3e3443b3f8dace88e177fd9c17c44e1331c`
  (14,871 bytes / 276 LF). Its strict public test is
  `tests/test_openadmet_global_v3_g4_gin300_transition_rejection.py` at SHA-256
  `f033a7577dca4eafd3cec979938292fcb0d7b6ef80f0e86d6134fc8d9f4d944f`
  (43,378 bytes / 1,226 LF), focused result `4 passed`, and 76 independent
  fail-closed mutations. Ruff check/format, Python 3.10 AST parsing, temporary
  compilation, and exact-scope diff checks are green.
- Rejected prospective identities: The transition contract at SHA-256
  `2c11b90d08038a05efd01bd40cb92ac79bc74544cc67807d2dd9b09111fa94af`
  (72,296 bytes / 582 LF), its static test at SHA-256
  `0c685112421929b715912450e8eeb0e8e7ae5534806c19a7bee8fac6ecdada2d`
  (67,654 bytes / 1,905 LF), and the corrected contract at SHA-256
  `1def7c6c31a84508e8d50f67a817ff486c30fad3f502dbefcc094e7b6ea7615f`
  (79,319 bytes / 646 LF) are non-integrable, non-authoritative negative
  evidence. None was integrated, and none grants implementation, execution,
  claim, result, or scientific authority.
- Targeted failure: Independent terminal audit proved that the attempted
  transition's unqualified zero-accounting claims could not truthfully describe
  the repository validation already performed. Treating a green public suite,
  offline build/install, and public-fixture vertical slice as literal zero
  runtime/import/train/prediction/cache/network activity would manufacture
  evidence. The single/final prospective correction boundary therefore closes
  G4 rather than opening another contract chain.
- First-suite evidence: The first bounded safe suite passed `1452 passed,
  14 skipped, 0 failed` in 358.81 pytest seconds / 359.31 wall-seconds at
  900,212 KiB maximum RSS. The suite did not instrument or retain aggregate raw
  network transactions/bytes, downloads, package imports, internal scientific/
  model operations, or cache effects; every such total remains unknown. A
  passing count cannot convert those unknowns to zero.
- Explicit public-CI accounting: With `UV_OFFLINE=1` configured, one isolated
  build produced a 338,214-byte sdist and a 406,405-byte wheel. Their hashes are
  incidental and non-frozen. One temporary CPython 3.12.3 environment installed
  four cached distributions: `cypshift 0.2.0.dev0`, NumPy 2.5.2, Pillow 12.3.0,
  and RDKit 2026.3.5. No download was observed, but raw build/install network
  transaction and byte totals were not instrumented and remain unknown. Two
  successful explicit public-fixture audit/train/predict/report roots were
  byte-identical at 9 files / 36,758 bytes each. Each reported 7 accepted,
  1 quarantined, 7 warnings, 3 supported, 1 unsupported, and 21 predictions,
  for exactly 2 train, 2 predict, 2 report, and 42 prediction operations.
- Unknown and cleanup accounting: Internal library fit/metric/import totals,
  build-isolation environment/cache counts, and global cache mutation/access-
  time effects were not instrumented and remain unknown. One pre-audit failed
  closed on an already-existing path before reported work. The preexisting
  ignored `.mypy_cache/3.12/cache.3.db` was observed modified, but the exact
  mutating operation was not instrumented and remains unknown; the
  authoritative mypy rerun used temporary state. All explicit task temporary
  roots were deleted and are absent. Do not freeze incidental build or smoke-
  tree hashes.
- Pre-ledger validation: After record/test freeze and before ledger mutation,
  the exact eight pre-ledger identities were unchanged across command `PYTHONDONTWRITEBYTECODE=1 UV_OFFLINE=1 /usr/bin/time -v uv run --locked --offline --no-sync pytest -p no:cacheprovider --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`.
  It exited 0 with `1453 passed, 14 skipped, 0 failed` in 345.74 pytest seconds /
  346.19 wall-seconds at 904,176 KiB maximum RSS. These offline controls do not
  convert uninstrumented raw network, cache, or import totals into zero.
- Exact G4 zero boundary: The public CI operations above are not G4 execution.
  The fixed G4 vector is comprehensive zero: all seven restricted roots and
  seven future implementation paths stayed absent; no isolated runtime/wheel,
  checkpoint/model body or tensor, scientific import, parity process, graph,
  embedding, synthetic root, fit, prediction, official/private/confirmatory/
  blinded-test/TDI read, metric, bootstrap, selection token, contender,
  systemd unit, delegated cgroup, claim, result, submission, validator,
  leaderboard-selection observation, portal credential, upload, or GPU use
  occurred.
- Terminal meaning: D-147 and D-148 remain immutable integrated prospective
  contract history. Their implementation/run schedule never activated and is
  superseded by this preclaim closure. G4 has no retry, repair, replacement,
  alternate observer, relaxed accounting, new transition, or outcome-driven
  successor. No D-149 record defect or future implementation idea may reopen
  it.
- Package scope: D-149 changes exactly nine paths: the rejection record, its
  strict public test, `benchmarks/openadmet_cyp_2026/README.md`,
  `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`, `docs/phases/README.md`,
  `docs/strategy/DECISIONS.md`, `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`,
  `docs/strategy/PROJECT_STATE.md`, and `runs/experiment_ledger.csv`. It adds
  no implementation, project lock, scientific runtime, claim, or result.
- Ledger receipt: `runs/experiment_ledger.csv` is bound at SHA-256
  `515801a45120ea07fada9b3193a4f10614074b77674d0f3b0ea0c01dabaa26fa`
  (437,803 bytes / 200 LF). Its unchanged 431,853-byte prefix has SHA-256
  `53def734ac3bb96d83fb8af2f7c37d42504382caacc63f2e2395f115e0aace56`;
  the sole appended 18-field row has SHA-256
  `0bd57d22c25b5162ca811e0dde542c4a45abee27d4f21662bd2c21c1a2992baf`
  (5,950 bytes including LF). Its compact `config` and `metrics` JSON round-trip
  exactly, and visual audit is clean.
- Competitive backout: Historical receipts bind the accepted direct MapLight
  candidate's submission SHA-256
  `9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`
  and manifest SHA-256
  `96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6`.
  The immutable tracked handoff has SHA-256
  `6a9402ca3fdf02dbcad079cba82162132e5b149f6adf69f80ea05d177e1ecec4`
  (2,919 bytes / 55 LF). It records 750 ordered rows, 3,000 finite predictions,
  and a historically valid pinned-validator result with zero errors. Current
  private candidate existence and bytes are deliberately unknown and unopened;
  the candidate is not currently reauthenticated or upload-ready.
  Fixed MapLight remains the strongest validated internal baseline at
  component-macro MAE `0.5837812652150708`. Historical receipts establish an
  accepted deterministic direct deployment candidate, but it was neither
  selected nor robustness-accepted by G2-7G. The MAE is prior internal
  development evidence, not an official or leaderboard score, reselection, or
  robustness result. G2-8 remains closed.
  This backout preserves a competitive route without reinterpreting any failed
  experiment.
- Authority boundary: D-149 grants no new submission generation, validator,
  official metric, leaderboard, portal, credential, or upload authority. The
  exact next action is a separate nine-path contract-only milestone comprising
  `benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_handoff_contract.json`,
  `tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py`,
  these six narratives, and ledger. It permits zero private candidate reads,
  validator calls, portal/credential access, or uploads. A future one-use
  read-only reauthentication result is separate; any upload remains a later
  human-authorized operation.
- Alternatives: Integrate any rejected transition identity; underreport public
  CI operations; infer zero from `UV_OFFLINE=1` or a green suite; guess unknown
  network/cache/import/model totals; freeze incidental artifact hashes; build a
  second G4 correction; consume or replace the G4 claim; call MapLight selected
  or robustness-accepted; reopen G2-8; consult portal/leaderboard evidence; or
  upload before a separate reauthentication contract.
- Reversal condition: Any wrong rejected identity, false known/unknown
  accounting, nonzero G4 operation, missing preclaim/no-retry closure, tenth
  D-149 path, placeholder at integration, MapLight identity drift, selection or
  robustness overclaim, G2-8 reopening, or portal/upload authority blocks the
  D-149 record package. It cannot revive G4. The exact nine-path terminal
  package subsequently completed signed fast-forward-only review and green
  exact-SHA CI; D-150 below freezes the separate MapLight reauthentication
  contract.

## D-150 — Freeze the conditional direct MapLight reauthentication handoff

- Date: 2026-08-30
- Status: contract-only boundary accepted; final contract/test identities are
  frozen and independent review passed. SSH-signed integration and green exact-
  SHA pull-request/post-main CI remain pending. No private candidate, validator,
  portal, or upload authority is active.
- Integrated parent: D-149 is immutable signed commit
  `0bf9b253002399a61e3d8d4e37e1a957ebd198ec`, merged without rewriting through
  PR #186. Exact-head PR CI run `33348758894` and exact-SHA post-main push CI
  run `33349365347` are green across Python 3.11, 3.12.3, and 3.14. G4 remains
  permanently closed at `G3_2_EXP_G4_GIN300_PRECLAIM_CLOSED`.
- Numbering boundary: D-149 superseded D-148's unactivated prospective use of
  “D-150” for a G4 capability invocation. This current D-150 is the separate
  direct-baseline contract promised by D-149; it does not execute or revive
  any D-148 capability.
- Decision: Freeze only the prospective direct-baseline read-only
  reauthentication handoff under schema
  `cypshift.openadmet_cyp_2026.direct_baseline_reauthentication_handoff_contract.v1`
  and status `DIRECT_BASELINE_REAUTHENTICATION_HANDOFF_CONTRACT_FROZEN` in
  `benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_handoff_contract.json`
  at SHA-256 `589facbbe8b51aeee00abdcba756c9119262572954854f438c549cab7ff98fcd`
  (22,489 bytes / 431 LF), with strict public static
  test
  `tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py`
  at SHA-256
  `9b2d17eb878367a6d786d3fa4606c6b64ec8e518ae4fffeac8d086738ec4a53d`
  (89,220 bytes / 2,556 LF). Its focused result is `5 passed`, and exactly 196
  independent fail-closed mutations are rejected.
- Pre-propagation validation was executed once against the exact quiescent
  nine-path snapshot before this paragraph and the sole D-150 ledger row were
  updated: contract `589facbbe8b51aeee00abdcba756c9119262572954854f438c549cab7ff98fcd`,
  test `9b2d17eb878367a6d786d3fa4606c6b64ec8e518ae4fffeac8d086738ec4a53d`,
  benchmark README `6fa3fb503dc9fbe4cae53e39056ff43052ee097ddc15733d5d93fb3e1d78d318`,
  active phase `20c0886be11f9abe72cc5a8500691adc3e6b165a1be14b3421cbeee9a05972b7`,
  phases README `6211ab1251e486fe816982dd125f2d2b8e93757a3c879e1431354c7f668dbec1`,
  decisions `07685ffe1d6a5168db37aada2b78ddcce79dfdd6aed06ec4536aed079828288c`,
  next prompt `28c2ad685778cdd489517b2c987976f0776d5a3140a95e6c82c58981ab935036`,
  project state `c88afa585d2ad5ee2186382921d109358f6acea4a5beb7b171ebe8dcdd112195`,
  and ledger `a2eaad989ecc61e95012388ea6414c1356f6e8ede83660ace6ec163aaae9f094`.
  The focused D-150 plus D-149 pair passed 9/9 with zero fail or skip in
  0.42 pytest seconds / 0.67 wall-seconds at 43,432 KiB maximum RSS. Ruff passed
  on the exact 327 public Python paths with the barred trio excluded; the focused
  two-test format check passed; Python 3.10.13 AST parsing and temporary
  compilation passed 2/2; and mypy passed on 78 source files in 3.57 seconds at
  268,924 KiB maximum RSS. The safe suite passed 1,458 with 14 skipped and zero
  failed in 363.81 pytest seconds / 364.38 wall-seconds at 903,120 KiB maximum
  RSS. The offline native `uv build` passed. The forced PEP 517 offline route
  was unavailable only because `uv-build` was not cached and is not a blocker.
  Two Python 3.12.3 installed-wheel roots were byte-identical at 9 files / 36,758
  bytes each; each replay recorded 7 accepted, 1 quarantined, 7 warnings,
  3 supported, 1 unsupported, and 21 predictions. Uninstrumented suite/internal
  network, cache, import, fit, metric, and validator totals were not retained and
  remain unknown rather than guessed as zero. Scoped private, official,
  candidate-validator, portal, credential, upload, and GPU operations remained
  zero. Incidental build and tree hashes are not frozen. This is pre-propagation
  evidence; final focused and diff checks are rerun after narrative/ledger
  propagation.
- Historical evidence boundary: Bind the immutable tracked handoff SHA-256
  `6a9402ca3fdf02dbcad079cba82162132e5b149f6adf69f80ea05d177e1ecec4`
  (2,919 bytes / 55 LF), historical submission SHA-256
  `9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`,
  and historical manifest SHA-256
  `96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6`.
  The handoff records two byte-identical rehearsals, 750 ordered rows, 3,000
  finite predictions, and a pinned-validator valid/zero-error result. Those are
  immutable historical receipts, not a current private-byte or validator
  result.
- Latest-tracked public requirement snapshot: As of
  `2026-08-24T04:21:32Z`, bind dataset, Space, and tutorial heads
  `85f8b358d0a2056a98b990dd75d3b3ec9247862b`,
  `13c5057b37d1e72b3f036dd0d59718b1823f8fdd`, and
  `858ae63ce79934113bccdb7fc65467de5f7b1935`; `source_receipts.json` at
  SHA-256 `764e59d37cc12993babce64208117d47612a1551bdcf30d1a22d10eb60636974`;
  `challenge_contract.json` at
  `344d3414d03bb98e57def998e80ab4cf315c1bebe7c01cb9d7c1c32ba3cd6123`;
  and `submission_contract.json` at
  `4be9933cd5e9404603d8971e49847bb240eff99f09874696c769a4fafd0d9a3c`.
  They require 750 rows, the six ordered identifier/SMILES/direct-prediction
  columns, numeric predictions, and finite values.
  `live_public_rule_refresh_performed=false` and
  `live_current_rules_claimed=false`: this is not a live rules refresh or claim
  about current portal/backend behavior. Live-backend parity, row-order
  authority, duplicate-identifier behavior, and extra-column behavior remain
  unresolved. Hash-only reauthentication therefore cannot claim a current
  validator pass or upload readiness.
- Scientific meaning: Fixed MapLight remains the strongest prior internal
  baseline at development component-macro MAE `0.5837812652150708`. This is
  not an official or leaderboard score, fresh selection, or robustness result.
  G2-7G selected no contender and did not robustness-accept MapLight; G2-8
  remains closed. D-150 does not reinterpret any failed experiment or create a
  scientific successor.
- Conditional-go boundary: Current private candidate existence, readability,
  bytes, and schema remain deliberately unknown and unopened at D-150; the
  current validator result is unknown and uninvoked. Only after D-150 is
  independently reviewed, frozen,
  SSH-signed, fast-forward integrated, and green on exact-SHA post-main CI may
  a separate one-use read-only result milestone inspect the fixed candidate
  by opening and enumerating the root exactly once and opening each exact file
  exactly once on success, only to hash raw bytes in memory. On failure, each
  operation is attempted at most once, the first defect stops the protocol,
  and no later operation runs. It may authenticate only the exact historical
  candidate unchanged; it may not
  parse, validate, copy, retain, open official data, regenerate, refit,
  repredict, rewrite, reorder, reformat, patch, or replace any candidate or
  manifest.
- Backout rule: Candidate absence or unreadability, submission or manifest
  identity drift, latest-tracked public snapshot identity drift, any need for a
  parser or validator, unexpected mutable state, or incomplete accounting/
  cleanup stops the direct route. No
  retry, repair, resume, alternate path, new candidate, or fallback model is
  authorized. Because G4 and G2-8 are already closed, such a failure is the
  competition backout condition for this build rather than an invitation to
  improvise another submission lane.
- Result publication boundary: Publication is at most one no-replace write. A
  safely classified success or failure publishes one result only after closing
  every descriptor and discarding all in-memory candidate bytes, at
  `benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_result.json`
  under schema
  `cypshift.openadmet_cyp_2026.direct_baseline_reauthentication_result.v1`.
  It retains only expected public hashes and aggregate outcome accounting; it
  retains or publishes no private locator, stat metadata, or candidate bytes.
  A crash, ambiguous cleanup, or publication failure may leave the result
  absent, but durable evidence that private locator resolution began still
  consumes the sole invocation and withdraws the route without retry.
- Future taxonomy: A safely published success uses
  `DIRECT_BASELINE_REAUTHENTICATED_READ_ONLY` and route state
  `DIRECT_BASELINE_ROUTE_REAUTHENTICATED`; a safely published failure uses
  `DIRECT_BASELINE_REAUTHENTICATION_FAILED_CLOSED` and route state
  `DIRECT_BASELINE_ROUTE_WITHDRAWN` in the same immutable result. Every
  failure, ambiguity, or need for another attempt withdraws the route,
  including an absent or unauthenticatable result after durable evidence that
  the attempt began. Success leaves the route operationally eligible but
  preserves `upload_authority=false`. D-150 itself emits no result token.
- Milestone separation: A clean future reauthentication result grants only a
  human handoff; it does not upload and may not consult private portal or
  leaderboard evidence. Any live upload is a still-later, separate, candidate-
  specific human-authorized operation. Portal credentials, private portal
  state, and remote results remain outside D-150 and outside model selection.
- Current operation accounting: D-150 reads zero private candidate or official
  row, calls zero validator, and performs zero submission regeneration, fit,
  prediction, metric, leaderboard-selection, portal/credential access, upload,
  or GPU operation. It adds no runner, validator wrapper, credential or upload
  integration, model, prediction artifact, private root, or result.
- Package scope: D-150 changes exactly nine paths: the canonical contract, its
  strict public test, `benchmarks/openadmet_cyp_2026/README.md`,
  `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`, `docs/phases/README.md`, this
  file, `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`,
  `docs/strategy/PROJECT_STATE.md`, and `runs/experiment_ledger.csv`. No tenth
  path is allowed.
- Alternatives: Reopen G4 or G2-8; call MapLight G2-7-selected or robustness-
  accepted; treat historical validation as current; open a private candidate
  while drafting the contract; run the validator now; regenerate or repair a
  missing or drifting candidate; accept a self-consistent replacement; use
  portal/leaderboard evidence for selection; combine contract freeze,
  reauthentication result, and upload; automate credentials or upload; or
  continue competing after the sole direct route fails closed.
- Reversal condition: Any D-149 lineage/CI mismatch, historical receipt drift,
  current-private-state claim, public-requirement ambiguity, missing fail-
  closed/no-repair rule, MapLight selection or robustness overclaim, G2-8
  reopening, private/validator/portal/upload operation, tenth path, remaining
  placeholder at integration, unsigned or rewritten commit, or non-green
  exact-SHA CI blocks D-150 without opening the candidate. Otherwise integrate
  only the exact contract package, then begin the separate one-use read-only
  result milestone.

## D-151 — Recover the competition program and authorize regular releases

- Date: 2026-09-04 (America/New_York).
- Authority: The user approved the complete audit/recovery plan, autonomous
  execution, signed milestone commits/pushes, and ideally dozens of additional
  entries. The user will upload manually and asks to be notified when ready.
- Decision: Activate Phase 3. Its prospective recoverable-execution, small
  candidate-menu, nested-validation and release policy supersedes conflicting
  no-repair/no-new-candidate/backout instructions in D-084 through D-150 and the
  old kickoff. Existing contracts, consumed claims and scientific outcomes are
  unchanged; do not reuse a closed attempt or relabel it successful. TRACE's
  scientific NO_SIGNAL remains terminal. Scientifically untested algorithms,
  including GIN, may be evaluated under new Phase 3 experiments.
- Delivery: Target 3–4 evidence-backed ready-to-upload releases per week across
  direct and TDI; disclose challengers separately from promoted recommendations.
  No arbitrary perturbations or baseline recertifications count as new entries.
  Keep private portal activity out of model selection and never upload for the
  user. Preserve the final reserved comparison until contender freeze.
- Evidence: The audit found 72 Global-v2/v3 ledger entries but one new official
  development model-quality result; numerous infrastructure-only stops; current
  public validator changes; and 45 passing targeted synthetic tests. Historical
  main ac043aa contains D-150; the preexisting uncommitted kickoff is preserved
  byte-for-byte in the archive at SHA-256
  dcb9924b2d3b01e3b4c3b6171b423ced802ae5718c8f8ee1f891f29efb0e5c55.
- Implementation: The active plan states the exact menu, cross-fitting,
  calibration/blend/auxiliary controls, promotion criteria and compute ceiling.
  Meaningful Git/manifest identities replace self-referential control chains.
  Allow two bounded engineering repairs per failure class; scientific changes
  require a prospective new version. No private or scientific operation is
  performed by this documentation milestone.
- Validation: Focused and full repository checks plus source/diff review are
  required before signed fast-forward integration. Actual results are recorded
  in the PR rather than inventing future CI or independent-review evidence.
- Reversal: A data/assay/family leak, invalid release, unsupported claim or
  exceeded budget stops the affected candidate. Preserve the failure and keep
  other qualified candidates/fallback operational. No retrospective tuning on
  the reserved comparison and no leaderboard-based selection.

## D-152 — Current upload validation and complete public primary scoring

Date: 2026-09-04 (America/New_York).

Problem: the existing baseline validator predates new Space variation checks,
and historical challenge development results reported component MAE without
the full tutorial bootstrap primary metric.

Decision: add a small current direct/TDI CSV validator and public-source
reauthentication command; preserve every frozen historical validator. Direct
columns require sample STD >=0.01; the two released TDI columns require
canonical 0/1 and both classes. Local checks additionally require exact
blinded-test identity, column and row order. Source changes require review
before release but do not discard compatible research checkpoints.

Add the public ST-RAE bootstrap mean and separate paired-family uncertainty.
An independent agent executed the pinned full upstream wrapper on synthetic
unequal endpoint masks/asymmetric bounds/shuffled IDs; endpoint and macro
means agree within 1e-14. Golden macro: 0.2538326265004878. This is public
wrapper parity, not live-backend validation. Reviewer findings on invalid
dimensions and perfect-baseline division were fixed before integration.

The immutable prior submission and manifest match their exact hashes. The
750-row/3000-prediction baseline passes current rules; endpoint sample STDs
are 0.50791, 0.54207, 0.28715, 0.84242. This is zero additional entries.
No new model fit or reserved numeric target was consumed. A subsequent
no-fit intake check found RDKit 2023 cannot reproduce every RDKit 2026
standardized hash; the planned repair is original-runtime compilation and
a verified development-only bundle, not changed chemistry or ignored hashes.

Validation: 19 upload-boundary tests and 11 independent metric tests pass;
Ruff, strict core mypy, wheel build and installed fixture workflow pass.
Exact-commit PR CI remains required before integration.

## D-153 — Recoverable nested MapLight/calibration vertical slice

Date: 2026-09-04 (America/New_York), before Phase 3 model outcomes.

Freeze the first experiment at five outer/three inner whole-family folds, seed
20260905, and the exact legacy MapLight MAE recipe: 80 fits. Fit the bounded
affine interval-loss calibration solely on each outer training set's inner
OOF predictions; score outer OOF only after predictions are complete. Identity
wins optimization ties. Fit deployment calibration on pooled baseline OOF only
after unbiased outer assessment. The initial allocation is 100 CPU-core-hours
within the program's 1000-hour cap; profile the first real fit.

The count-corrected and binary feature helpers are tested and available for the
next prospective experiment, but do not enter this initial calibration result.
Each fit checkpoints exact feature/target/training/prediction/implementation/
runtime identity. Failures and incomplete starts remain accounted; another
active experiment sharing the Phase 3 root cannot acquire the compute lock.

A real no-fit check demonstrated the expected RDKit 2023/2026 structure identity
mismatch. Compile with core RDKit 2026 and load an immutable hash-bound bundle
without re-standardizing in the locked model runtime. This is engineering
repair 1 for that failure class; original sources and hashes remain unchanged.
The bundle retains 3,908 development molecules in 3,640 families, excludes 997
reserved molecules, and finds no extra quarantine. Training and metric counts
are 1,110/1,024/1,182/1,881; all bounds exist. Minimum inner training counts are
592/546/630/1,002. Core compilation took 19.50 seconds, with zero fits and zero
reserved numeric values parsed. Connectivity and tautomer unions happen before
target decoding.

Interim release eligibility is evaluated on paired primary/component metrics
as in Phase 3; a result satisfying only this gate is a challenger, not final
promotion. A qualifying affine release may transform the already authenticated
full-training baseline using development-only OOF calibration, preserving the
reserved selection barrier. Disclose this transfer from development-trained
OOF to the larger historical full-training predictor. Do not retrain on reserved
targets or count identity transformations as additional entries.

Independent reviews covered metric parity, compiler boundaries and checkpoint
recovery. Five compiler/bridge, five feature, and fifteen calibration/cache
tests pass; these exercise leakage, real count overflow, optimization, corrupt
receipts and interrupted publication rather than copying implementation.
No new scientific outcome is claimed by this prospective decision.

## D-154 — Immutable interim calibration release builder

Date: 2026-09-04 (America/New_York), before the first nested outcome.

Add one concrete release command from evaluated OOF evidence to a private
upload CSV. Authenticate the untouched baseline/test bytes and all experiment
receipts, verify finite matching-population scores and recompute non-domination
rather than trusting an eligibility flag. Reject identity/no-change transforms,
invalid calibration bounds, stale public sources and overwritten destinations.
Publish readonly prediction bytes and a completion manifest only after current
validation. The user performs manual uploads; no portal state enters selection.

This is an interim challenger, with the historical MapLight baseline remaining
the recommendation pending the stronger repeat/ablation promotion gates. The
manifest explicitly discloses calibration transfer from development OOF to the
existing 4,905-molecule full-training predictor. No reserved targets are opened.
Readiness does not establish an upload, and a latest valid upload replaces the
previous track entry; honor 12-hour per-track spacing.

Independent review found and repaired the stale-eligibility-flag gap. Eight
release tests cover dominated/malformed evidence, tampered OOF, identity output,
Git/overwrite rejection and immutable publication. All 63 Phase 3 tests pass
across source validation, metrics, features, compiler, runner and release files.
No scientific result or new upload is claimed by this implementation decision.

## D-155 — First qualified challenger and robustness follow-through

Date: 2026-09-04 (America/New_York).

The frozen 80-fit experiment improved public-wrapper macro ST-RAE from
0.7575254251 to 0.7371456380 (2.6903%). The paired-family 95% interval for
candidate minus baseline is [-0.026898, -0.013785]. Maximum endpoint
component-MAE harm of +0.017333 satisfies the +0.02 gate; macro component MAE
worsens slightly from 0.584596 to 0.587758. Preserve this tradeoff explicitly.
Runtime was 482.09 seconds and 1.29545 CPU-core-hours. The promotion metric gate
passes, but second-repeat evidence and the final comparison remain outstanding.

One new direct challenger CSV has been generated and current-rule validated,
SHA-256: `c66c5f3f898745a0132f200373ca1a2af94f148598c5424c270628887d17436f`.
It applies the OOF-fitted calibration to the authenticated historical full-
training baseline, with this transfer limitation stated in the private manifest.
No reserved numeric labels were opened. Manual upload is unconfirmed.

Run the already-frozen second seed 20260906 with unchanged scientific logic;
do not tune toward the first outcome. Audit found that orphaned fit-start
resource estimates would grow indefinitely. Freeze their conservative unknown
charges once after shared-lock acquisition; preserve completed attempts. This
repair does not alter the completed scientific result. Two clock/lock tests
verify the behavior.

Prepare the bounded SVR kernel/inner selection helper for the next planned
model. Select C in {1, 10} on pooled inner-OOF ST-RAE, with epsilon 0.1; ties
favor C=1.
Use float64 blocked binary Tanimoto to prevent uint8 dot overflow. Four
scientific tests and a six-fit synthetic locked-runtime smoke pass. No official
SVR fit has occurred. The count audit finds only 10 of 3,908 development molecules
affected in one count column; retain the correction ablation without assuming
a large gain. GIN readiness needs a Linux runtime and provenance/parity work,
estimated at 6–10 engineering hours within the two-working-day cap. Retained TDC
embeddings cannot be assumed to match challenge molecules.

## D-156 — Confirm the first submission and prepare the next comparison

Date: 2026-09-05 UTC.

The prespecified second 80-fit repeat improves primary ST-RAE from 0.749608
to 0.729011 (2.7477%); its paired-family interval is [-0.027209, -0.014027].
Maximum endpoint component-MAE harm is +0.018932, below +0.02, while macro
component MAE worsens by +0.003354. Independent recomputation authenticates
inputs, folds, family boundaries and affine predictions, and matches primary
metrics exactly. Runtime is 505.77 seconds / 1.32710 invocation CPU-core-hours.
Both repeats support the first released affine CSV as the interim recommendation.
Do not substitute second-repeat parameters or average them after seeing results.
Final promotion and the reserved comparison remain outstanding; the calibration
transfer to the historical larger training set remains a disclosed limitation.

The user confirmed manual upload under alias glhf. Public monitoring initially
showed the August 24 entry; a later refreshed observation identifies September 5
at 02:10 UTC, rank 107, MA-ST-RAE 0.9335 and MA-MAE 1.0383. Relative to the
saved previous scores 0.9366 / 1.0332, the primary gain is 0.33%, MAE worsens
0.0051 and rank is unchanged. Preserve this modest outcome without equating it
to the internal gain. Update the existing every-two-hour heartbeat rather than
creating a duplicate. Keep detailed timestamp/rank/score receipts private.
These observations are operational only and cannot affect model selection.

The user explicitly authorizes future strategy changes. The initial menu is
revisable using internal evidence, costs and research. Record a new hypothesis,
failure mode and acceptance criterion before outcomes; retain scientific
invariants and historical negative results. This avoids another infrastructure
program that cannot adapt or deliver entries.

The next runnable comparison is the frozen 140-fit Tanimoto SVR evaluation:
C in {1,10}, epsilon 0.1, same nested folds, raw and inner-OOF affine variants.
Authenticate exact same-fold MapLight OOF and compare with both calibrated
incumbent and raw promotion reference. Cache whole seven-fit endpoint/fold
cells with data/runtime identities; record unknown partial attempts and their
CPU charges. Linux limits and the shared compute lock bound execution. If a
variant qualifies, its prospective deployment uses 24 full-development inner
selection fits and four production fits; no reserved labels are opened.
No official SVR fit or additional CSV is claimed by this milestone.

Independent review found no remaining blocking issues. Ten SVR helper/runner
tests pass, including outer-target independence, family isolation, checkpoint
corruption, selection and accounting. Focused suite, lint/format, strict core
mypy and exact-commit PR CI are required before integration. Reversal: evidence
or provenance failure withdraws the affected claim/artifact, preserving the
baseline and unaffected candidates; no leaderboard-driven repair.

## D-157 — Deep audit changes the modeling and validation priorities

Date: 2026-09-05 UTC; user explicitly requested a substantial bug audit and a
strategy change if the pipeline held up. Candidate expansion paused for audit.

Independent raw-to-development comparison matches all 46,896 point/bound cells;
the actual tutorial full wrapper matches within 1.11e-16; independently rebuilt
training and inference feature hashes and the affine CSV match exactly. No
catastrophic mapping, units, scoring or deployment feature defect was found.
The original production estimators were deleted, so direct model reload remains
unverified. Sparse int8 Avalon overflow is genuine but not an established cause
of poor overall scores. No reserved numeric labels were opened by the audit.

The model beats training-fold medians with paired evidence, but compresses
predictions and misses every pIC50 >=6 example below its lower bound in both
repeats. Singleton-heavy families do not simulate a dense active-hit analog
panel. Historical selected-anchor episodes chose maximum selector potency from
the same pool as future queries, outcome-conditioning those selector queries.
Keep TRACE's observed failure and implementation retired; do not generalize it
to every possible new known-parent hypothesis. Any new episode protocol must
hide query outcomes during discovery/anchor selection and disclose its distinct
information setting. No retrospective fold change or hidden-label inference.

Change the next experiment to RMSE versus MAE with unchanged feature semantics
and shared learning rate 0.03, depth 6, 1,000 iterations, random strength 2 and
seed 1. Record native optimizer differences (Exact versus Newton leaves).
Evaluate raw and bounded inner-OOF affine variants on both original family
seeds: 80 fits each, capped at 10 CPU-core-hours each. Authenticate and compare
with each seed's original calibrated MAE incumbent. Recommendation requires
>=2% primary gain, paired upper95 <0 and endpoint component-MAE harm <=0.02
in each repeat. Separately test the potent-tail mechanism against fixed bands;
prediction variance alone is no success criterion. Details are frozen in
benchmarks/openadmet_cyp_2026/phase3_rmse_ablation_v1.json before model outcomes.

The RMSE runner's own raw-versus-affine comparison cannot authorize a release.
Its distinct candidate identity is rejected by the historical-MAE transformation
builder. New qualified model predictions must come from saved/reloaded fitted
estimators using development labels, with the smaller training size disclosed.
No new submission is claimed by this prospective milestone. Failed experiments
remain recorded and move priority to complementary similarity/auxiliary-data
hypotheses rather than arbitrary offsets or another infrastructure prerequisite.

Parallel data work audits the TDI file's extra 1,240 identities before numeric
intake. Existing development direct fields match exactly and add zero labels;
no additional usable targets are assumed. Model selection remains independent
of public outcomes, and the final reserved comparison remains closed.

Validation: independent audit evidence and focused objective/cache/release/
comparison tests plus full exact-commit CI before integration. A documentation
link to a private upload file failed clean-runner CI in D-156; retaining it as
a literal locator fixed the portability issue without changing scientific data
or weakening the existing test. Reversal: a failed objective hypothesis retires
that candidate, not the recovered pipeline or remaining validated hypotheses.

## D-158 — Retain negative model evidence and use the available hardware

Date: 2026-09-05 UTC.

The frozen 160-fit RMSE experiment fails its prespecified recommendation and
potent-tail mechanism criteria in both repeats. Raw RMSE is 3.74% / 3.61% worse
than the same-seed affine-MAE incumbent; affine RMSE is 1.26% / 0.93% worse.
The 140-fit Tanimoto SVR experiment is also negative: raw and affine variants
worsen primary ST-RAE by 12.04% and 9.63%, with wholly positive paired-family
intervals and endpoint component-MAE harm above +0.02. Independent audits
reconstruct scores, folds, parameter choices and exact SVR kernel bytes.
No candidate from these experiments warrants a production fit or upload. Retain
all negative records; do not change calibration bounds after seeing outcomes.
The first affine-MAE CSV remains the interim recommendation, reserve closed.

These experiments consumed approximately 2.63449 CPU-core-hours combined
(RMSE invocation CPU plus SVR accounted stages), excluding separate audits.
The quick SVR result is genuine execution evidence: 20 fresh seven-fit cells,
distinct C=1/C=10 outputs and independently reproduced selection. Estimators
were not retained by these OOF runners, so audit does not claim independent
estimator replay. Future production packages must retain and reload models.

Family-safe extra TDI-file intake adds zero direct labels on 1,237 eligible
extra identities; three reserved-connected extras were excluded before numeric
decoding. The expanded graph changes no old development boundaries. Do not
build a direct augmentation pipeline for this source. Completed support audits
verify all 3,908 standardized hashes and zero >=0.60 crossings. Approximately
72–84% of scored rows across both repeats lack a potent training neighbor at
similarity >=0.30. Descriptive strata are not new calibration instructions.

The user explicitly authorizes future CPU utilization up to 75% and local GPU
utilization up to 100%. Inventory confirms 32 logical / 16 physical CPU cores,
30.46 GiB RAM and an AMD gfx1100 GPU with about 20 GiB VRAM. Use a shared
24-CPU-equivalent / 20-GiB host-memory slice and cooperative affinity that leaves
four complete physical cores available. The slice's actual kernel CPU/memory
limits are verified; cpuset is not delegated. Retain the 1000 CPU-core-hour,
100-GB storage and no-paid-compute boundaries. This changes future resource
allocation, not the completed 16-thread scientific recipes.

The locked CatBoost environment cannot use this AMD GPU. Authorize a bounded
private userspace-only ROCm/PyTorch readiness preparation with pinned, hashed
artifacts, at most 2.5 GiB downloads / 12 GiB working storage and 20 minutes.
Review the resolved dependency closure before imports and run a separate
120-second synthetic GPU/backward/save-reload gate. No kernel, driver, global
Python, or historical environment changes. Installation alone is not readiness.

Next scientific priorities are the genuine sparse count-correction ablation
and a small fingerprint MLP with direct-only, real auxiliary-screen and shuffled
auxiliary controls. Primary-screen measurements stay a distinct assay task;
selection bias is a material caveat. Freeze intake, masks, stopping, calibration
and budget before official fitting. With honest inner stopping and refitting,
three arms require 105 network fits per repeat, not 60. A known-parent diagnostic
must freeze discovery/query membership before outcomes and cannot replace the
strict-family evaluation claim. Do not let GPU setup become an unbounded gate.

Validation: independent RMSE and SVR evidence audits, reviewed aggregate receipts,
existing documentation-link check, JSON/ledger integrity and full exact-commit
PR CI before local fast-forward integration. This milestone changes evidence and
prospective resource policy, not production logic; no new mirror tests are added.
Reversal: withdraw an affected claim if provenance fails; remove the private GPU
environment if readiness fails, preserving the CPU pipeline and accepted CSV.

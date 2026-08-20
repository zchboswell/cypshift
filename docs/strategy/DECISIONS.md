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

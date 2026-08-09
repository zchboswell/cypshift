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

## D-004 — Private, signed, milestone-based development

- Date: 2026-08-09
- Status: accepted
- Decision: Develop in a private personal repository using signed commits,
  short-lived branches, focused pull requests, and frequent passing milestone
  pushes.
- Evidence: This provides a clean timecourse without exposing provisional work
  or restricted data.
- Alternatives: Public-from-start development; direct pushes to `main`.
- Reversal condition: Make the repository public after Phase 0, data licensing,
  and disclosure checks pass.
- Implementation note: GitHub returned a plan restriction when branch
  protection was requested for the private personal repository. Until the
  repository becomes public or the account plan changes, every post-bootstrap
  change must still use a branch and pull request by procedure; force-pushes and
  unreviewed direct `main` updates remain prohibited by project policy.
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
- Reversal condition: Reverse before inference only if a pinned primary source
  contradicts the contract or the authoritative challenge release supersedes
  Phase 0.5. After inference begins, preserve the attempt and its outcome.

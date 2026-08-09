# Project state

Last updated: 2026-08-09

## Current phase

Phase 0.5 active — public-data benchmark and launch rehearsal.

## Active operating goal

By 2026-08-16, build and benchmark the smallest real-data version of
`cypshift`, producing apples-to-apples public CYP performance comparisons,
exercising the critical ETL, validation, out-of-fold prediction, and reporting
path, and polishing the user experience without freezing any provisional
competition-specific contract.

The 2026-08-17 authoritative freeze remains in force. Phase 0.5 may use named,
versioned public data to rehearse the scientific and product machinery, but it
must not guess the official challenge adapter, schema, metric, submission
contract, series definition, or external/transductive-use rules.

## Best validated system

Phase 0 `v0.1.0` is the best validated system. On the CC0 synthetic fixture,
`audit -> train -> predict -> report` produces canonical
data, a duplicate-safe fixture split, an endpoint-context median, 21
predictions, cards, a hashed manifest, and a static report. Independent
same-seed runs are byte-identical. The locked package passes 34 tests, Ruff,
strict mypy, distribution builds, Linux CI on Python 3.11/3.14, and a local
macOS installed-wheel run. Independent review findings are remediated and
re-verified.

The Phase 0.5 public-data and split foundation is independently validated and
merged at signed commit `58b0661`. The reviewer repeated the full empty-root
reconstruction, matched all 24 retained files and both aggregate receipts, and
found no remaining scientific, code, or documentation issues.
The exact Octant compound-level release maps deterministically into 1,340
accepted molecules and 1,084 numeric measurements; 256 rows without source
pIC50 values remain explicit molecule records and do not become fabricated
measurements. This establishes data-contract evidence, not model-performance
evidence, so Phase 0 `v0.1.0` remains the best validated predictive system.

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
  exclusion set is frozen separately. No public-test score has been computed.
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

## Active hypotheses

1. Parent-expansion validation will better predict blind performance than
   molecule-random validation.
2. Simple series residuals or shrinkage will improve predictions for close
   analog campaigns.
3. Local support and disagreement can predict expert error well enough to
   improve a simple cross-fitted stack.

None has been tested.

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

Phase 0.5 closes no later than 2026-08-16. It returns to the official launch
workflow when its required tracks, scorecard, report, clean reproduction,
independent review, and KB closeout are complete, or immediately when the
authoritative challenge release requires the launch-day freeze procedure.

## Exact next action

Implement the minimum native selection ladder in declared order: prior, ECFP
linear, similarity-weighted kNN, and one nonlinear fixed-feature estimator.
Keep benchmark-only dependencies isolated, predeclare at most 12 configurations
per family and task, and produce complete grouped out-of-fold predictions. Do
not evaluate any TDC public-test label until retained configurations and their
artifact hashes are frozen from `train_val` evidence alone.

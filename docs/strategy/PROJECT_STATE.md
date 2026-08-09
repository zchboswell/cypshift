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

No real-data Phase 0.5 result exists yet. Phase 0 `v0.1.0` remains the best
validated system until a public-data milestone passes its frozen checks.

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
and dated leaderboard anchors are deliberately not asserted here. Freezing
them is the first implementation milestone after this KB change merges.

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

Freeze the public benchmark sources and licenses, create immutable download
manifests, and implement the OpenADMET Octant compound-level ingestion path
without changing the four-command public CLI.

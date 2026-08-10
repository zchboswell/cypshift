# Publication claims and evidence bars

All claims below are provisional hypotheses. Do not state them as findings until
their evidence bars are satisfied on frozen blind-like validation.

## Primary claim — series-first prediction

Proposed claim:

> Series-first prediction improves over molecule-independent ensembles under
> analog-family distribution shift.

Required evidence:

- frozen parent-expansion or series-grouped splits;
- identical splits and paired comparisons across methods;
- family-level bootstrap intervals and directional consistency across repeats;
- controls for independent models, nearest neighbors, scaffold grouping, and
  shuffled or incorrect series assignments;
- activity-cliff and worst-series analysis;
- no meaningful global damage hidden by one large family.

Rejection condition: the improvement is inconsistent, confined to random
splits, or reproduced by shuffled series labels.

## Secondary claim — competence-aware fusion

Proposed claim:

> Predicting local expert failure improves fusion more reliably than adding
> another potency expert.

Required evidence:

- fully cross-fitted expert predictions and gate features;
- comparison with mean, median, nonnegative linear stacking,
  inverse-variance weighting, random gating, and shuffled gate features;
- repeated grouped-validation gain, calibration benefit, predefined subset
  gain, or improved worst-series behavior;
- stability and cost-versus-gain analysis.

Rejection condition: a simple nonnegative stack is equal or superior within
uncertainty.

## Optional claim — bounded scientific adjudication

Proposed claim:

> A bounded evidence-linked adjudicator identifies contradictions or valuable
> targeted checks beyond deterministic controls.

Required evidence:

- deterministic-only, explanation-only, uncertainty-only, and bounded-adjustment
  comparisons;
- shuffled dossiers, mechanistic-field removal, and deterministic heuristic
  controls;
- repeated-run stability;
- schema validation, evidence identifiers, hard adjustment bounds, and seamless
  deterministic fallback.

Rejection condition: controls perform equivalently, outputs are unstable, or
prediction adjustments do not improve blind-like validation. In that case the
component is limited to explanation or removed.

## Phase 0.5 public-benchmark evidence boundary

Phase 0.5 may support only claims tied to an immutable, named public benchmark.

Allowed when the supporting artifacts are available:

- exact performance on a named, hashed dataset revision and split;
- comparison with a public reference only when dataset, target, label, split,
  metric, preprocessing or disclosed difference, and evaluation population
  match;
- reproducibility, runtime, calibration, applicability, and error-stratification
  findings for the frozen run;
- a controlled keep/reject result for a series-aware residual on a frozen
  public simulation with supported sample counts;
- evidence that a simple model is competitive with a named complex baseline on
  the same benchmark contract.

Not allowed from Phase 0.5 evidence:

- expected challenge rank or blind challenge performance;
- direct-inhibition performance inferred from active-preincubation data;
- TDI performance inferred from substrate, turnover, depletion, or reactivity
  status;
- state-of-the-art claims across different datasets, splits, metrics, or
  evaluation populations;
- clean zero-shot claims when external-model training overlap is unknown;
- mechanistic or causal claims inferred from predictive correlations.

## Phase 0.75 comparator and representation claims

Phase 0.75 may support only claims tied to its frozen public sources, global
shadow benchmark, row-level predictions, and declared evaluation budget.

### Exact reproduction claim

Proposed claim:

> A locally reproduced MapLight comparator matches the pinned public method on
> identical TDC rows within the declared tolerance.

Required evidence:

- immutable source, paper, license, environment, feature, seed, and split
  records;
- fixture-level array parity for count fingerprints, ErG values, and the exact
  ordered descriptor block;
- identical TDC rows and label-free row-aligned predictions;
- five declared seeds with no post-result selection;
- preferred AUPRC agreement within 0.005 per task, with 0.010 as the maximum
  diagnostic tolerance;
- a precise version-drift record when tolerance is not met.

Rejection condition: agreement requires score-driven tuning, row changes,
unfrozen defaults, or unverifiable dependencies.

### Representation-value claim

Proposed claim:

> Richer complementary molecular representations improve CYP ranking beyond
> estimator diversity over binary ECFP under leakage-safe grouped validation.

Required evidence:

- one frozen global grouping assignment across all three CYP tasks;
- repeated scaffold-held-out and chemistry-community-held-out shadow results;
- predefined fixed-feature ablations on identical rows;
- complete paired OOF predictions and declared stochastic seeds;
- GIN shuffled-row and same-dimensional-noise controls when GIN is claimed;
- task-level, macro-average, worst-group, prevalence, runtime, and sample-count
  reporting;
- no architecture or dependency choice from public-test evidence.

Rejection condition: gain is absent on the shadow benchmark, isolated to one
group, reproduced by a control, or explained by a simpler feature block.

### Final public-comparator superiority claim

Proposed claim:

> The final locked `cypshift` contender improves on the locally reproduced
> MapLight + GIN comparator on identical frozen TDC rows.

Required evidence:

- the final contender is selected entirely from frozen shadow evidence;
- local comparator and contender predictions exist for identical molecules;
- paired bootstrap units are the frozen scaffold or chemistry-family groups;
- the 95% lower confidence bound for AUPRC improvement is positive on at least
  two of CYP2C9, CYP2D6, and CYP3A4;
- the remaining task loses no more than 0.005 absolute AUPRC;
- the paired macro-average improvement has a positive 95% lower confidence
  bound;
- every task is reported and any score at or above 0.95 passes the independent
  forensic gate.

Rejection condition: the claim relies on a published point estimate rather
than the local paired comparator, fails any task or aggregate rule, or follows
public-test-aware iteration.

### Conditional future claims

Cross-isoform panel claim:

> Cross-isoform panel supervision improves CYP prediction beyond molecule-only
> single-task learning under strict same-structure and family masking.

Parent-relative claim:

> Predicting an analog relative to an explicit measured parent improves
> parent-expansion performance beyond global, nearest-neighbor, parent-copy,
> shuffled-parent, and incorrect-anchor controls.

Neither claim is active Tier 1 work. The panel claim requires verified primary
field semantics, a strict union exclusion of every TDC public-test structure,
global cross-task folds, and independent firewall review. Call the method
assay-conditioned only when verified assay variables are retained and used.
The parent-relative claim requires a frozen topology audit with measured
parents, supported analog families, target spread, transformation controls, and
family-level uncertainty.

Phase 0.75 evidence does not permit:

- a challenge-performance or expected-rank claim;
- a clean zero-shot claim when GIN pretraining overlap is unknown;
- an assay-conditioned claim from isoform identity alone;
- an AID 1851 training claim before source and firewall review;
- a representation claim based only on the already observed public test;
- a state-of-the-art claim without the local paired comparator and confidence
  rule.

## Claims that are out of scope

Do not claim:

- an autonomous AI scientist;
- universal foundation-model superiority;
- mechanistic truth from model explanations;
- causal CYP mechanisms from predictive correlations;
- assay-independent CYP inhibition;
- competition superiority based only on a live leaderboard.

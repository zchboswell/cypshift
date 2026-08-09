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

## Claims that are out of scope

Do not claim:

- an autonomous AI scientist;
- universal foundation-model superiority;
- mechanistic truth from model explanations;
- causal CYP mechanisms from predictive correlations;
- assay-independent CYP inhibition;
- competition superiority based only on a live leaderboard.

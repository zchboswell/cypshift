# Public comparator intake

Status: pre-freeze research note; no execution authority

Captured: 2026-08-10T02:25:51Z

## Purpose and boundary

Identify the smallest reproducible reference that could support a future claim
against the strongest current public CYP predictor. This note does not select a
Phase 1 model, authorize a fit, or map a public CYP endpoint to the unreleased
challenge. The authoritative challenge data, assay semantics, metric, rules,
and validation groups must be frozen first.

## Current reference

The dated TDC leader is MapLight + GNN at AUPRC 0.859, 0.790, and 0.916 for
CYP2C9, CYP2D6, and CYP3A4 Veith. The exact pages and captured anchors are in
[`benchmarks/public_sources.json`](../../benchmarks/public_sources.json).

The public implementation is
[`maplightrx/MapLight-TDC`](https://github.com/maplightrx/MapLight-TDC). The
repository is MIT-licensed and contains six files at revision
`c249378c63232354d17083c83fe94fe728960a27`, committed on
2023-11-06T23:59:23Z.

| File | SHA-256 |
| --- | --- |
| `LICENSE` | `281afcf01d4df616e2f8065ca100f0de6b8740c2f5865008a538368ea75e4334` |
| `README.md` | `eb0e2fb544353153095bf2253b4b76d1d18309aa6082e6237de4df91cbd17315` |
| `maplight.py` | `6dcb40fa43d39221259e03406f34be554fc138782c099894004549f7a8c24863` |
| `maplight_gnn.py` | `74fbd1c98d9afa7fa4bda1add21efd429e20dee0a4b0fb8fa7e9b3825c21fe13` |
| `submission.ipynb` | `26393242dcc7bd5509a8836f36a270106a1484af2abd0e90497aadad1a1e7754` |
| `submission_gnn.ipynb` | `95dc471338e8ca69a85a0c3c162cca3f5a1b220f3cd6a8d14f726adf5f7e1546` |

The associated paper is
[Notwell and Wood, *ADMET property prediction through combinations of molecular
fingerprints*](https://arxiv.org/abs/2310.00174).

## Exact published method

The repository constructs one 2,863-value molecular representation:

- 1,024 hashed Morgan count values at radius 2;
- 1,024 Avalon count values;
- 315 ErG values;
- 200 named RDKit physicochemical descriptors;
- 300 GIN supervised-masking values from `molfeat`.

It trains five CatBoost classifiers per task, one for each seed from 1 through
5, with `loss_function=Logloss`, `random_strength=2`, and `verbose=0`.
Remaining CatBoost settings use library defaults. It fits on the complete TDC
`train_val` population and predicts the fixed test population. The published
paper attributes the main gain to richer fixed representations; the GIN output
is an added feature block, not an end-to-end predictor.

## Reproducibility limits

The source is sufficient to describe the method but not sufficient for an
auditor-grade comparison:

- dependencies are installed without versions or hashes;
- the notebook downloads source from the moving `main` branch;
- the checked-in active loop runs only the eighth configured task, VDss; its
  all-benchmark loop is commented out, so an unchanged run executes no CYP
  task;
- the repository has no lock file, release, or retained environment receipt;
- the GNN notebook documents an unresolved `molfeat` execution issue;
- the source commit is not GitHub-verified;
- no feature hashes, model receipts, per-row predictions, or result manifests
  are published;
- the reported five-seed mean and standard deviation do not permit a paired
  family-level significance test against a new system.

These gaps do not invalidate the leaderboard entry. They define the work needed
before it can serve as an apples-to-apples statistical comparator.

## Post-freeze eligibility gate

Use MapLight + GNN as the first comparator only if the authoritative release
shows that its endpoint, assay context, allowed training data, prediction unit,
and metric are relevant. Otherwise retain it as TDC context and select the
strongest reproducible predictor that matches the released task.

Before any comparator fit:

1. pin all source, model, and environment bytes;
2. reproduce the public method without importing its notebook architecture;
3. bind the exact training rows, validation groups, feature blocks, seeds,
   predictions, runtime, hardware, and outputs by hash;
4. isolate configuration selection from the final evaluation population;
5. audit exact and standardized-structure training overlap;
6. require a byte-identical repeat before using a score.

No MapLight result can authorize a `cypshift` candidate or ensemble component.
It is a comparator first.

## Significance contract

A future superiority claim requires more than a leaderboard point estimate:

- identical training and evaluation rows for comparator and candidate;
- the released primary metric with the same polarity and aggregation;
- predictions from every declared seed, with no post-result seed selection;
- paired resampling at the released analog-family or frozen scaffold-group
  level;
- a predeclared confidence interval and a strictly positive lower bound for the
  candidate-minus-comparator gain, with direction reversed for loss metrics;
- task-level results and declared failure conditions, not only a favorable
  macro average;
- a strict leakage companion and an applicability analysis.

Published means and standard deviations may provide context. They cannot prove
a paired gain when the underlying predictions are unavailable.

## Smallest useful lesson

Do not start with a larger neural network. First test whether representation
breadth explains the current gap. After the official freeze, the smallest
controlled ladder is:

1. reproduce the eligible strongest comparator exactly;
2. isolate its fixed multifingerprint and descriptor contribution;
3. isolate one pinned pretrained graph representation;
4. test assay-conditioned multitask learning only if the released matrix and
   validation groups support it;
5. combine components only from complete cross-fitted predictions.

Stop a branch that does not improve the frozen grouped validation target. Do
not preserve a dependency, feature block, or neural component that fails its
predeclared ablation.

# Public comparator intake

Status: Phase 0.75 source frozen; execution remains gated

Captured: 2026-08-10T02:25:51Z

Last extended: 2026-08-10T16:26:18Z

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

The authoritative Phase 0.75 source, paper, method, anchor, environment-gap,
and claim freeze is
[`benchmarks/maplight_source_contract.json`](../../benchmarks/maplight_source_contract.json).
It records zero features, fits, predictions, label parses, and evaluations.

## Exact published method

The repository constructs one 2,563-value fixed molecular representation:

- 1,024 hashed Morgan count values at radius 2;
- 1,024 Avalon count values;
- 315 ErG values;
- 200 named RDKit physicochemical descriptors;

The GNN variant appends 300 GIN supervised-masking values from `molfeat` for a
2,863-value representation.

It trains five CatBoost classifiers per task, one for each seed from 1 through
5, with `loss_function=Logloss`, `random_strength=2`, and `verbose=0`.
Remaining CatBoost settings use library defaults. It fits on the complete TDC
`train_val` population and predicts the fixed test population. The notebook
passes five seed-specific prediction dictionaries to TDC. The upstream code
does not average the five probability vectors. The historical PyTDC version is
not pinned; the frozen local PyTDC 1.1.15 rule scores each seed, rounds each
metric to three decimals, and reports the mean and population standard
deviation of those five rounded metrics. A local mean-probability comparator
must therefore be labeled as a separate five-seed ensemble result, and the
historical rounding gap must remain disclosed. The published paper attributes
the main gain to richer fixed representations; the GIN output is an added
feature block, not an end-to-end predictor.

## Reproducibility limits

The source is sufficient to describe the method but not sufficient for an
auditor-grade comparison:

- dependencies are installed without versions or hashes;
- the notebook downloads source from the moving `main` branch;
- the checked-in active loop runs only index 7, the eighth configured task,
  `ppbr_az`; `vdss_lombardo` is index 8, and the all-benchmark loop is
  commented out, so an unchanged run executes no CYP task;
- the repository has no lock file, release, or retained environment receipt;
- the GNN notebook documents an unresolved `molfeat` execution issue;
- the source commit is not GitHub-verified;
- no feature hashes, model receipts, per-row predictions, or result manifests
  are published;
- the reported five-seed mean and standard deviation do not permit a paired
  family-level significance test against a new system.

The README specifies Python 3.10. The paper cites RDKit 2023.03.3 and MolFeat
0.9.2. Neither source identifies CatBoost, PyTDC, NumPy, pandas, scikit-learn,
DGL, PyTorch, or the transitive environment. The exact historical environment
cannot be recovered from the pinned public evidence. Phase 0.75 must freeze a
new compatible reproduction environment and describe it as such.

The GIN alias resolves to a two-stage pretrained model: node masking on ZINC15
followed by supervised graph pretraining on ChEMBL assays. Direct overlap with
the TDC Veith structures and targets is unknown. Until an overlap audit passes,
use `pretrained representation transfer`, not `clean zero-shot`, in claims.
The artifact and pretraining-data licenses are also not disclosed or established
by the source-code licenses. Eligibility must pass before the GIN bytes are used.

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

## Transfer evidence from a prior blind challenge

OpenADMET's official
[ExpansionRx postmortem](https://doi.org/10.5281/zenodo.21784568) is a useful
method prior, but it is not a CYP comparator. The immutable CC-BY-4.0 Zenodo
record contains a 26,071-byte Markdown source with SHA-256
`c7c328a07e66933e2837de1add40c964e1fa0038675aa4148a484e5c3fe33220`.

The postmortem reports that:

- pretrained, multitask 2D graph models dominated the leading entries;
- the three highest-ranked entries that declared no proprietary data, ranks 5
  through 7, all used pretrained models and multitask learning;
- descriptors and fingerprints were common engineered features, including
  among leading hybrid entries;
- almost all leading entries used external public data;
- four of the top five entries used proprietary data.

These findings support the existing small ladder: broad fixed features, one
pretrained graph representation, assay-compatible multitask learning, and only
then a cross-fitted combination. They do not prove that any component will
improve a CYP endpoint. The ExpansionRx endpoints, data, splits, and metrics
are different, and the postmortem does not publish the row predictions needed
for a paired comparison. Do not copy its architecture, ranking, or validation
choices into Phase 1.

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

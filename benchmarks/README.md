# Public benchmark contracts

`public_sources.json` is the tracked source-of-truth for Phase 0.5 public data.
It pins source revisions, URLs, licenses, file sizes, SHA-256 digests, row
counts, fixed TDC splits, dated leaderboard anchors, and external-model files.
Raw public data and generated benchmark artifacts stay out of Git.

## Octant compound-level ingestion

The Octant adapter treats the 30-minute active-CYP3A4 preincubation assay as
its own endpoint. It does not relabel it as the challenge minus-NADPH direct
inhibition endpoint. The adapter preserves the source structure text, all
source values and QC fields in provenance, the DBOMF fluorescence context, and
the immutable dataset revision and file digest. The pinned protocol states that
100 uM NADP+ and a G6P/G6PD regeneration system are present during active
preincubation. This creates NADPH-generating metabolic conditions; it does not
mean that exogenous NADPH was directly added.

For component-level debugging after fetching the frozen inputs, reproduce the
retained Octant ingestion with:

```console
uv run python scripts/prepare_octant_benchmark.py \
  --source data/external/octant_cyp/96dc1cceaa545a22041d1e16a9c2524a658403f8/inhibition.tsv \
  --out artifacts/benchmarks/octant-source-freeze-v2
```

The frozen table has 1,340 unique molecule rows. All 1,340 pass the canonical
chemistry audit. Exactly 1,084 rows contain a numeric pIC50 and become canonical
measurements. The other 256 remain in the molecule table with an explicit
`missing_source_pIC50` provenance state; they are not fabricated as
measurements or silently discarded. Two clean runs produce byte-identical
adapter and audit artifacts.

This is an ingestion result, not a predictive-performance result. Model
selection and every TDC test evaluation remain pending.

## Empty-root reproduction

From the repository root, reproduce the complete source, ingestion, audit, and
validation freeze in one new output directory:

```console
uv run python scripts/reproduce_public_data_freeze.py \
  --out artifacts/benchmarks/public-data-reproduction-v1
```

The focused orchestrator fetches only the frozen Octant compound-level table,
its exact protocol, and the TDC ADMET archive; verifies every size and SHA-256
digest; prepares and audits both canonical datasets; freezes validation; and
writes a deterministic root receipt. It refuses an existing output directory.
On 2026-08-09, this command completed from an absent root in 61 seconds on a
local Apple CPU and reproduced the retained artifacts byte-for-byte. Its root
aggregate is
`0dc587c61b02f90df04e599deff771117ad52b5cfe16f10d606359bc8548d8d4`.
The receipt records zero model fits and zero public-test evaluations.

## Frozen public validation

For component-level debugging after preparing both canonical datasets, freeze
validation without fitting or scoring a model:

```console
uv run python scripts/freeze_public_validation.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --tdc-official-split artifacts/benchmarks/tdc-source-freeze-v2/adapter/official_split.csv \
  --tdc-adapter-manifest artifacts/benchmarks/tdc-source-freeze-v2/adapter/adapter_manifest.json \
  --out artifacts/benchmarks/public-validation-freeze-v2
```

The Octant contract assigns 1,340 rows in 937 Bemis-Murcko scaffold groups to
five exactly balanced 268-row folds. Fold 0 is the untouched outer validation
population; folds 1-4 are training and the four inner selection folds. Group
assignment does not use labels.

The TDC audit preserves all official train/test rows. Raw SMILES do not cross
train/test within any task, but canonical standardization reveals 3 structures
covering 4 test rows for CYP2C9, 2 covering 2 for CYP2D6, and 1 covering 1 for
CYP3A4.
Official scores will remain unchanged and will be accompanied by a separately
labeled strict score excluding those 7 hashed rows. The frozen audit records
zero public-test evaluations. TDC AUPRC is average precision and higher is
better; polarity tests guard against the contradictory lower-is-better footer.

Within each TDC `train_val`, scaffold groups are assigned without labels to
four row-balanced inner folds. All 30,038 `train_val` rows are assigned; no
public-test row, standardized duplicate, or scaffold group crosses an inner
fold. The audit validates every official split row against canonical task,
partition, source-row, source, and isoform provenance, and binds the split hash
to the adapter manifest.

`public_validation_manifest.json` hashes every retained split artifact and
records the exact aggregate-hash recipe. The frozen aggregate is
`b7f2d0f7d18bcc7d5815cdc3919a9681523ccf380246449c32e54b7c80465b12`.
The freeze performs zero model fits and zero public-test evaluations.

## Native selection contract

Native candidate selection is a separate benchmark-only workflow; it does not
add a public CLI command or a core runtime dependency. Install the locked
benchmark group, then run:

```console
uv sync --locked --all-groups
uv run python scripts/select_native_models.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --validation artifacts/benchmarks/public-validation-freeze-v2 \
  --out artifacts/benchmarks/native-selection-v1
```

The selection path verifies the complete validation receipt chain before any
fit. It parses only the 872 measured Octant inner-selection rows and the 30,038
TDC `train_val` rows. Octant outer labels and TDC public-test labels are not
parsed or evaluated.

The frozen four-family grid is deliberately small: one training prior; three
regularization values for a chiral 2,048-bit ECFP4 linear model; six
similarity-weighted Tanimoto kNN configurations; and three 128-tree ExtraTrees
leaf-size configurations. Classification uses pooled grouped-OOF average
precision; regression uses pooled grouped-OOF MAE. The retained stochastic
configuration is rerun with exactly three declared seeds. Generated selection
artifacts remain outside Git; their hashes and keep/reject decision enter the
experiment ledger after the first run.

Two real runs from signed commit `42ffaf1` are byte-identical. Each completes
240 grouped fits in about 216 seconds on a local Apple CPU and emits 401,830
candidate OOF rows, 123,640 retained OOF rows, and 92,730 stochastic-seed rows.
The retained linear configurations are Octant ridge alpha 10 and TDC logistic
`C=0.1`; all tasks retain Tanimoto kNN with `k=50`, power 2 and ExtraTrees leaf
size 3. Root aggregate
`33ba1f6481048c9f620223f9a0e6c85d2a40bece620ffe9b0c44117c0c7775fa`
binds the exact configuration and prediction artifacts. These grouped-inner
scores select candidates; they are not comparable to TDC public-test anchors.
The receipts still record zero held-out label parses and evaluations.

## Held-out prediction firewall

Held-out prediction and scoring are separate milestones. After the native
selection receipt is frozen, generate predictions without reading any held-out
measurement table:

```console
uv run python scripts/predict_native_heldout.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --tdc-official-split artifacts/benchmarks/tdc-source-freeze-v2/adapter/official_split.csv \
  --validation artifacts/benchmarks/public-validation-freeze-v2 \
  --selection artifacts/benchmarks/native-selection-v1 \
  --out artifacts/benchmarks/native-heldout-predictions-v1
```

The predictor verifies the validation, canonical-data, official-split, and
selection receipt chain; retrains only the frozen family configurations; and
writes label-free predictions plus three declared ExtraTrees seed predictions.
It records zero held-out labels parsed and zero evaluations. A later scorer may
consume the immutable prediction receipt exactly once.

## First held-out scorecard

Scoring attempt 1 parsed the 7,724 held-out labels but failed before calculating
or writing a score because of an incorrect leaderboard-manifest access path.
The failed attempt is retained in the experiment ledger. A signed, CI-verified
path-only remediation preceded attempt 2; no model, prediction, threshold,
population, or metric changed.

Attempt 2 produced the first scorecard with aggregate
`2cc47a1600b5809a4317b8c8ec719bc702e43d6e6f9b335d0f189c3546720a1a`:

| Task | Best native family | Native | Chemprop-RDKit | MapLight + GNN |
| --- | --- | ---: | ---: | ---: |
| TDC CYP2C9 AUPRC | ECFP logistic | 0.7340 | 0.777 | 0.859 |
| TDC CYP2D6 AUPRC | ExtraTrees | 0.6474 | 0.673 | 0.790 |
| TDC CYP3A4 AUPRC | ECFP logistic | 0.8431 | 0.876 | 0.916 |

The strict seven-row leakage companion changes native AUPRC by at most 0.0006.
The best Octant grouped-outer result is ExtraTrees MAE 0.5489. These results
validate the benchmark path and strong classical baselines; they do not support
a superiority claim. Public reference comparisons retain the disclosed
standardization and fingerprint differences.

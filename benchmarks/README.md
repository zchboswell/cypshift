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
the immutable dataset revision and file digest.

After downloading the exact `inhibition.tsv` URL from
`public_sources.json`, reproduce the retained ingestion with:

```console
uv run python scripts/prepare_octant_benchmark.py \
  --source data/external/octant_cyp/96dc1cceaa545a22041d1e16a9c2524a658403f8/inhibition.tsv \
  --out artifacts/benchmarks/octant-source-freeze-v1
```

The frozen table has 1,340 unique molecule rows. All 1,340 pass the canonical
chemistry audit. Exactly 1,084 rows contain a numeric pIC50 and become canonical
measurements. The other 256 remain in the molecule table with an explicit
`missing_source_pIC50` provenance state; they are not fabricated as
measurements or silently discarded. Two clean runs produce byte-identical
adapter and audit artifacts.

This is an ingestion result, not a predictive-performance result. Model
selection, grouped Octant validation, and every TDC evaluation remain pending.

## Required-source reconstruction

Reconstruct the two required inputs in an empty cache with:

```console
uv run python scripts/fetch_required_benchmarks.py \
  --out artifacts/benchmarks/clean-cache-v1
```

The downloader is deliberately concrete: it fetches only the frozen Octant
compound-level inhibition table and TDC ADMET archive, checks both sizes and
SHA-256 digests while streaming, refuses overwrite, and writes a deterministic
receipt. On 2026-08-09, a clean download reproduced byte-identical inputs and
adapter artifacts.

## Frozen public validation

After preparing both canonical datasets, freeze validation without fitting or
scoring a model:

```console
uv run python scripts/freeze_public_validation.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v1/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --tdc-official-split artifacts/benchmarks/tdc-source-freeze-v2/adapter/official_split.csv \
  --out artifacts/benchmarks/public-validation-freeze-v1
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

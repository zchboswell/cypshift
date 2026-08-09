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

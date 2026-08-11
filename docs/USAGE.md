# Usage

`cypshift` exposes one deliberately small workflow:

```text
audit -> train -> predict -> report
```

The current CLI is a fully reproducible reference implementation. Its model is
an endpoint-context median, intended to prove the data, artifact, and reporting
path. Research comparators use isolated scripts and dependencies and are not
silently substituted into the public commands.

## Requirements

- Python 3.11 or newer
- `uv` for the locked repository workflow
- CPU execution; no service, database, GPU, or model download is required

The installable package has one runtime dependency: RDKit.

## Install

```bash
git clone https://github.com/zchboswell/cypshift.git
cd cypshift
uv sync --locked --all-groups
```

Confirm the interface:

```bash
uv run cypshift --version
uv run cypshift --help
```

## Inputs

### Molecules

The molecule CSV has exactly five columns:

```text
molecule_id,structure,structure_format,source,provenance
```

`structure_format` is currently `smiles`. `structure` is preserved exactly as
provided; parsing and standardization produce separate derived fields. Use a
stable `molecule_id` and identify the origin in `source` and `provenance`.

### Measurements

The measurement CSV has exactly fifteen columns:

```text
measurement_id,molecule_id,endpoint,isoform,nadph_condition,probe,readout,
value,lower_bound,upper_bound,censoring,unit,quality,source,provenance
```

One physical CSV header contains those fields on a single line. Empty bounds
are permitted when the source truly does not provide them. Non-finite numeric
values, malformed rows, missing identities, and references to unknown
molecules fail closed.

Do not collapse assay context into the endpoint name. CYP measurements can
change with the isoform, probe, readout, preincubation condition, NADPH state,
censoring, and source.

The files in [`examples/synthetic/`](../examples/synthetic/) are invented and
redistributable. They demonstrate schema and failure behavior only.

## Run the workflow

Use a new output directory:

```bash
uv run cypshift audit examples/synthetic/molecules.csv \
  --measurements examples/synthetic/measurements.csv \
  --out results
```

The audit:

- validates exact CSV shape and identities;
- preserves the raw structure;
- parses and standardizes chemistry under a versioned policy;
- groups standardized duplicates;
- quarantines invalid structures;
- emits warnings for salts, fragments, and stereochemical ambiguity;
- records input and output hashes.

Train the reference model and deterministic split:

```bash
uv run cypshift train --data results --out results
```

Generate predictions and evidence cards:

```bash
uv run cypshift predict \
  --data results \
  --model results/model.json \
  --out results
```

Render the verified report:

```bash
uv run cypshift report --run results --out results
```

## Outputs

| File | Meaning |
| --- | --- |
| `molecules.csv` | Accepted and quarantined chemistry with raw and standardized identities |
| `measurements.csv` | Validated measurements with their complete context |
| `audit.json` | Chemistry warnings, counts, policies, and input/output hashes |
| `split.csv` | Deterministic duplicate-safe reference split |
| `model.json` | Endpoint-context median, fit summary, source hashes, and seed |
| `predictions.csv` | Row-aligned reference predictions |
| `prediction_cards.jsonl` | Per-row support, context, warnings, and evidence identifiers |
| `run_manifest.json` | Resolved configuration, versions, hashes, seed, and output inventory |
| `report.html` | Static summary generated only after artifact verification |

The same inputs, software, configuration, and seed produce byte-identical
machine-readable outputs. Commands refuse silent overwrite.

## Expected behavior

- Invalid molecules are quarantined rather than coerced into valid chemistry.
- Standardized duplicates receive the same reference split assignment.
- Unsupported endpoint contexts remain visible and do not receive fabricated
  support.
- Raw strings, measurement context, and provenance remain recoverable.
- A report is generated only when its upstream schemas and hashes validate.

The synthetic example produces 21 prediction rows. That count tests the
workflow; it is not a biological benchmark.

## Current limitations

- The public CLI model is a reference baseline, not the retained MapLight or
  GIN research comparator.
- Series-first measured-parent inference is not yet implemented in the public
  CLI.
- The package is not validated for clinical, regulatory, or safety decisions.
- Windows installation and browser-level visual regression remain untested.
- Heavy research environments are intentionally separate from the core
  package.

For benchmark results and scientific claim limits, read
[Validation](VALIDATION.md).

# cypshift

`cypshift` is a series-first, competence-aware system for predicting cytochrome
P450 inhibition under analog-family distribution shift.

The repository is public and pre-launch. Phase 0 is complete as signed release
`v0.1.0`; its synthetic vertical slice validates pipeline mechanics, not
biological performance. Phase 0.5 is also complete. It establishes a frozen
public CYP benchmark baseline with chemistry-aware validation and immutable
provenance. The official OpenADMET CYP inhibition challenge launches on
2026-08-17; its released data, schema, metric code, submission contract, and
rules supersede all provisional assumptions.

## Current objective

The exact MapLight reproduction attempt is closed. Fixture parity passed, but
real-row generation stopped before fitting on a frozen non-finite descriptor
boundary. Keep this public-benchmark evidence separate from the challenge. On
2026-08-17, freeze the official challenge release before adapting the proven
workflow:

```text
audit -> standardize -> split -> train -> predict -> report
```

The production interface will remain limited to `audit`, `train`, `predict`,
and `report`. Public-data reproduction uses focused research scripts documented
in [the benchmark record](benchmarks/README.md).

## Phase 0 quickstart

The current vertical slice uses only invented fixture data and demonstrates
pipeline mechanics, not biological performance. From a clone with `uv`
installed:

```bash
uv sync --locked --all-groups
uv run cypshift audit examples/synthetic/molecules.csv \
  --measurements examples/synthetic/measurements.csv --out results
uv run cypshift train --data results --out results
uv run cypshift predict --data results --model results/model.json --out results
uv run cypshift report --run results --out results
```

Open `results/report.html` in a browser. Each command refuses to overwrite its
own artifacts, so use a new output directory for a repeated run.

## License

The `cypshift` source code is available under the BSD-3-Clause license. The
invented fixture under `examples/synthetic/` is separately dedicated to the
public domain under CC0-1.0.

## Project record

- [Project charter](docs/strategy/PROJECT_CHARTER.md)
- [Current state](docs/strategy/PROJECT_STATE.md)
- [Decisions](docs/strategy/DECISIONS.md)
- [Failure taxonomy](docs/strategy/FAILURE_TAXONOMY.md)
- [Publication claims](docs/strategy/PUBLICATION_CLAIMS.md)
- [Phase 0 plan](docs/phases/PHASE_0.md)
- [Phase 0.5 directive](docs/phases/PHASE_0_5.md)
- [Public benchmark record](benchmarks/README.md)
- [Phase 0.5 benchmark report](benchmarks/PHASE_0_5_REPORT.md)
- [Phase 0.75 comparator report](benchmarks/PHASE_0_75_REPORT.md)
- [Experiment ledger](runs/experiment_ledger.csv)

## Authoritative challenge source

- [OpenADMET CYP inhibition challenge announcement](https://openadmet.ghost.io/announcing-openadmets-cyp-inhibition-blind-challenge/)

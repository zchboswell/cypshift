# Documentation

The documentation is organized by what a reader is trying to do. Current
guidance is kept short; completed plans and superseded intake notes live in the
archive. Benchmark contracts and reports remain in `benchmarks/` because they
are evidence, not user documentation.

## Start here

| Document | Use it for |
| --- | --- |
| [Usage](USAGE.md) | Install the package, prepare inputs, run the CLI, and understand the emitted artifacts |
| [Scientific rationale](SCIENCE.md) | Understand the series-first hypothesis and what would make it genuinely different from a global molecular model |
| [Validation](VALIDATION.md) | Review current benchmark results, leakage controls, limitations, and supported claims |
| [Current state](strategy/PROJECT_STATE.md) | See what is complete, what is retained, and the exact next scientific boundary |

## Scientific governance

These files define the rules under which results may be interpreted:

- [Project charter](strategy/PROJECT_CHARTER.md) — mission, thesis, success
  criteria, and non-negotiable constraints.
- [Publication claims](strategy/PUBLICATION_CLAIMS.md) — evidence required
  before a scientific statement can be promoted from hypothesis to result.
- [Failure taxonomy](strategy/FAILURE_TAXONOMY.md) — chemistry, measurement,
  validation, series, competence, and reproducibility failure classes.
- [Consequential decisions](strategy/DECISIONS.md) — dated decisions and their
  reversal conditions.
- [Release intake](strategy/LAUNCH_INTAKE.md) — the active external-data freeze
  boundary.

## Evidence

- [Benchmark contracts and reproduction guide](../benchmarks/README.md)
- [Phase 0.5 native benchmark report](../benchmarks/PHASE_0_5_REPORT.md)
- [Phase 0.75 representation report](../benchmarks/PHASE_0_75_REPORT.md)
- [Experiment ledger](../runs/experiment_ledger.csv)

The detailed reports retain exact data revisions, row populations, metrics,
hashes, negative results, and claim limits. Generated arrays, raw datasets,
predictions, model weights, and licensed artifacts remain outside Git.

## Archive

Completed execution plans are retained under [archive/phases](archive/phases/).
Superseded pre-execution research notes are retained under
[archive/intake](archive/intake/). Archived files explain how evidence was
produced; they do not define the current product or next action.

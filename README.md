# cypshift

`cypshift` is a series-first, competence-aware system for predicting cytochrome
P450 inhibition under analog-family distribution shift.

The repository is in private, pre-launch Phase 0 development. No validated
model or competition result exists yet. The official OpenADMET CYP inhibition
challenge launches on 2026-08-17; its released data, schema, metric code,
submission contract, and rules will supersede all provisional assumptions.

## Current objective

Build the smallest reproducible vertical slice on a synthetic fixture:

```text
audit -> standardize -> split -> train -> predict -> report
```

The production interface will remain limited to `audit`, `train`, `predict`,
and `report`.

## Project record

- [Project charter](docs/strategy/PROJECT_CHARTER.md)
- [Current state](docs/strategy/PROJECT_STATE.md)
- [Decisions](docs/strategy/DECISIONS.md)
- [Failure taxonomy](docs/strategy/FAILURE_TAXONOMY.md)
- [Publication claims](docs/strategy/PUBLICATION_CLAIMS.md)
- [Phase 0 plan](docs/phases/PHASE_0.md)
- [Experiment ledger](runs/experiment_ledger.csv)

## Authoritative challenge source

- [OpenADMET CYP inhibition challenge announcement](https://openadmet.ghost.io/announcing-openadmets-cyp-inhibition-blind-challenge/)

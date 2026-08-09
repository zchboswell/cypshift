# Phase 0 — ground truth and working vertical slice

Status: in progress

Plan frozen: 2026-08-09

## Objective

Establish the smallest correct, reproducible, CPU-capable path from chemistry
input to predictions and an audit report, using only a tiny synthetic fixture.

```text
audit -> standardize -> split -> train trivial model -> predict -> report
```

Phase 0 proves product and provenance mechanics. It does not attempt competitive
model performance.

## Required inputs

- the project charter and current state;
- the 2026-07-29 official challenge announcement;
- a hand-authored synthetic molecule and measurement fixture that is clearly
  labeled, redistributable, and small enough for CI;
- a supported local Python runtime and an audited minimal dependency set.

No official challenge data is required before 2026-08-17.

## Smallest viable implementation

1. Create a typed `src/cypshift` package and `cypshift` CLI.
2. Define canonical molecule and measurement schemas without assuming final
   launch-day column names.
3. Preserve raw structures and emit explicit standardization records and
   warnings.
4. Implement a deterministic fixture adapter.
5. Implement a deterministic split suitable for pipeline testing only.
6. Train one endpoint mean or median baseline.
7. Write predictions and a run manifest with configuration, versions, seeds,
   and input hashes.
8. Generate a minimal static report.
9. Expose exactly four public commands: `audit`, `train`, `predict`, `report`.
10. Add unit, integration, CLI smoke, reproducibility, and no-silent-change
    tests.

## Required output artifacts

- `predictions.csv`
- `prediction_cards.jsonl`
- `audit.json`
- `run_manifest.json`
- `report.html`

The Phase 0 prediction card may contain only fields supported by the trivial
baseline. Unsupported production diagnostics must be explicit nulls or omitted
according to the documented schema, never fabricated.

## Planned checks

### P0-C1 — installation and CLI contract

- Failure mode: P3/P4
- Test: build and install the core package in a clean environment, then invoke
  all four commands on the fixture.
- Success: all commands exit successfully with actionable, concise output.
- Immediate rejection: the core path requires a GPU, service, database, Codex,
  or an unlicensed asset.

### P0-C2 — deterministic reproduction

- Failure mode: P1/V4
- Test: repeat the fixture run with the same configuration and seed.
- Success: input hashes, split assignment, predictions, and machine-readable
  outputs are identical apart from documented timestamps or run identifiers.
- Immediate rejection: unexplained prediction or split drift.

### P0-C3 — chemical audit trail

- Failure mode: C1-C6
- Test: include valid, invalid, salt-containing, stereochemical, and duplicate
  synthetic examples.
- Success: raw input is preserved; every standardized value has a recorded
  status and warning; invalid inputs fail or remain quarantined explicitly.
- Immediate rejection: any silent chemistry change.

### P0-C4 — overwrite and provenance behavior

- Failure mode: P2/P5
- Test: rerun into an existing output path and inspect the manifest.
- Success: no file is silently overwritten; outputs identify the resolved
  configuration, versions, input hashes, seed, and whether adjudication was
  used.
- Immediate rejection: silent overwrite or missing critical provenance.

## Acceptance criteria

- A clean core installation succeeds on CPU.
- `cypshift audit`, `train`, `predict`, and `report` all work end to end.
- Tests pass locally and in GitHub Actions.
- The fixture is synthetic, documented, and redistributable.
- Raw chemistry is preserved and no standardization is silent.
- The complete run is reproducible from one resolved configuration.
- The repository remains small and contains no placeholder architecture.
- `PROJECT_STATE.md` and the experiment ledger reflect the completed phase.

## Likely failure modes

- Prematurely encoding announcement-derived field names or scoring behavior.
- Pulling in a large cheminformatics or configuration stack before it is needed.
- Confusing a fixture split with challenge-faithful validation.
- Designing production diagnostics that the baseline cannot support.
- Duplicating schema or configuration truth across files.
- Creating unused directories in anticipation of later phases.

## Explicit non-goals

- official data ingestion;
- official metric implementation;
- scaffold, series, parent-expansion, or cliff validation;
- graph models, multitask learning, stacking, gating, or uncertainty calibration;
- external-data training;
- microstates, conformers, docking, or metabolites;
- TDI factorization;
- LLM adjudication;
- dashboards, services, databases, or workflow frameworks.

## Order of implementation

1. Audit Python and packaging constraints; select the minimum dependencies.
2. Define the fixture and canonical schemas.
3. Implement `audit` and standardization with tests.
4. Implement deterministic splitting and the trivial baseline.
5. Implement prediction artifacts and manifest.
6. Implement the static report.
7. Wire the four CLI commands.
8. Run clean-environment and repeated-run checks.
9. Add the smallest CI workflow.
10. Update the ledger, phase results, and project state.

Each numbered milestone must pass its scoped checks before it is pushed.

## 2026-08-17 launch-day freeze checklist

This checklist is a Phase 1 input, not permission to expand Phase 0.

- capture authoritative source URLs, revisions, timestamps, and licenses;
- store immutable raw data outside Git and calculate hashes;
- freeze the official schema and endpoint mappings;
- port and reproduce official metric code with tests;
- freeze submission columns and validation behavior;
- record censoring, interval, quality, and TDI-label semantics;
- record external-data and transductive-use rules;
- audit family identifiers or infer series without using labels;
- design and freeze challenge-faithful splits before serious model selection.

## Phase completion record

To be appended at exit:

- what worked;
- what failed;
- what was removed;
- retained artifacts;
- exact Phase 1 handoff.

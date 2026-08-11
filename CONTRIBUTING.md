# Contributing

`cypshift` welcomes focused contributions that improve chemical correctness,
validation, reproducibility, documentation, or the series-first hypothesis.

## Development setup

```bash
git clone https://github.com/zchboswell/cypshift.git
cd cypshift
uv sync --locked --all-groups
```

Run the repository checks before opening a pull request:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv build
```

## Contribution standard

- Start from a concrete failure mode or scientific hypothesis.
- Preserve raw structures, assay context, censoring, quality, and provenance.
- Keep exact duplicates and analog families inside one evaluation partition
  when family holdout is claimed.
- Fit feature selection, calibration, thresholds, stacking, and error models
  only from cross-fitted predictions.
- Declare an acceptance criterion before an expensive experiment.
- Record negative results rather than repairing them after evaluation.
- Add no dependency or abstraction without an immediate use.
- Keep the four-command public CLI stable.

Small, typed, deterministic changes are preferred. A simpler component wins
when its evidence is indistinguishable from a more complex one.

## Data and artifacts

Do not commit raw public or licensed datasets, generated benchmark artifacts,
model caches, pretrained weights, credentials, or unrestricted predictions.
Fixtures must be synthetic or explicitly redistributable. Record source
revisions, licenses, and hashes for every external input.

## Pull requests

Explain:

1. why the change exists;
2. which failure mode or hypothesis it addresses;
3. how it was validated;
4. what would reverse or reject it.

Keep pull requests reviewable and avoid unrelated cleanup. If a result changes
the best validated system, supported claims, risks, or next action, update
[`PROJECT_STATE.md`](docs/strategy/PROJECT_STATE.md) and the
[experiment ledger](runs/experiment_ledger.csv).

See the [documentation index](docs/README.md) and
[scientific rationale](docs/SCIENCE.md) before proposing a new model family.

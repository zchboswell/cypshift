# Project state

Last updated: 2026-08-09

## Current phase

Phase 0 — vertical-slice implementation.

## Best validated system

The complete Phase 0 vertical slice is now the best validated system. On the
CC0 synthetic fixture, `audit -> train -> predict -> report` produces canonical
data, a duplicate-safe fixture split, an endpoint-context median, 21
predictions, cards, a hashed manifest, and a static report. Independent
same-seed runs are byte-identical. The locked package passes 26 tests, Ruff,
strict mypy, and distribution builds.

## Strongest evidence

- The official 2026-07-29 announcement confirms a 750-compound test set built
  as ten close analogs for each of 75 potent hits.
- The live and fully blinded leaderboard subsets are grouped by analog family.
- Direct inhibition covers CYP1A2, CYP2C9, CYP2D6, and CYP3A4; TDI scoring
  covers CYP3A4 and CYP2D6.
- The official schema, metric code, submission contract, data snapshot, and
  complete rules are not frozen until the 2026-08-17 launch.
- The locked Phase 0 toolchain builds with RDKit as the sole runtime dependency;
  pandas, Pydantic, and a CLI framework remain absent.
- The synthetic audit detects and records invalid chemistry, fragment-parent
  changes, assigned and unassigned stereochemistry, and standardized
  duplicates without using official challenge data.
- The deterministic fixture split keeps standardized duplicates together,
  excludes quarantined chemistry, and is explicitly labeled as a pipeline test
  rather than challenge-faithful validation.
- The trivial median model uses only uncensored numeric training measurements;
  its model and split hashes bind the 21 deterministic predictions and cards
  to the recorded inputs and resolved seed.
- The report verifies all manifest-listed artifact hashes before rendering and
  states that the fixture, split, and model do not support biological or
  competition-performance claims.

## Active hypotheses

1. Parent-expansion validation will better predict blind performance than
   molecule-random validation.
2. Simple series residuals or shrinkage will improve predictions for close
   analog campaigns.
3. Local support and disagreement can predict expert error well enough to
   improve a simple cross-fitted stack.

None has been tested.

## Unresolved risks

- Launch-day schema and scoring details may invalidate provisional assumptions.
- The provisional RDKit fragment-parent policy must be re-evaluated against
  official structure semantics before it is used on challenge data.
- Series inference may be ambiguous without explicit parent identifiers.
- Low-activity interval handling may dominate regression behavior.
- TDI labels may be unstable near potency and shift thresholds.
- The final project license remains deferred until retained dependencies and
  redistributed assets are frozen. RDKit's BSD-3-Clause license is compatible
  with the intended permissive release.
- GitHub cannot enforce branch protection while the personal repository is
  private on the current account plan; branch and pull-request discipline is
  procedural until publication or a plan change.

## Exact next action

Add the smallest CI workflow and run the installed four-command slice twice in
fresh environments to close Phase 0 reproducibility checks.

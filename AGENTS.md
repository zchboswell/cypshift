# Repository operating instructions

## Restore context first

Before changing the repository, read in order:

1. `docs/strategy/PROJECT_STATE.md`
2. the active file in `docs/phases/`
3. `docs/strategy/PROJECT_CHARTER.md`
4. relevant entries in `docs/strategy/DECISIONS.md`

Treat `PROJECT_STATE.md` as the concise current truth. Update it whenever a
milestone changes the phase, best validated system, evidence, risks, or next
action.

## Work contract

- Keep `main` installable and passing its available checks.
- Work in small, reviewable milestones and make atomic signed commits.
- Push passing milestones frequently. Do not manufacture commits without a
  coherent rationale.
- Open a pull request before integrating every post-bootstrap branch. After its
  checks and record are complete, integrate the reviewed signed commit locally
  with a fast-forward-only merge and push `main`. Do not use GitHub's hosted
  rebase merge because it rewrites SSH-signed commits without their signature.
- Explain why a change exists in its commit body or pull request, including
  validation evidence and reversal conditions when material.
- Never add Codex, OpenAI, an AI system, or an automated tool as an author or
  co-author. Do not add `Co-authored-by`, `Generated-by`, or equivalent AI
  attribution trailers. The Git author is `zchboswell`.
- Preserve user changes and inspect the working tree before editing.
- Use typed Python and deterministic seeds where practical.
- Keep notebooks out of production logic.
- Update the experiment ledger for every experiment, including negative
  results.
- Record only consequential decisions in `DECISIONS.md`.
- Do not add a dependency, abstraction, model, or directory without a current
  need.

## Scientific invariants

- Never permit a molecule, exact duplicate, or analog family to cross a split
  boundary where the evaluation requires family holdout.
- Fit feature selection, calibration, stacking, thresholds, and error models
  using cross-fitted predictions only.
- Preserve raw structures, assay context, censoring, intervals, quality, and
  provenance. Never silently modify chemistry.
- Treat CYP inhibition as assay- and condition-dependent.
- Keep leaderboard evidence secondary to frozen internal validation.
- State a targeted failure mode and acceptance criterion before an expensive
  experiment.
- Remove components that fail their predefined ablation.

## Pre-launch boundary

Until the 2026-08-17 release, do not hard-code final field names, interval
behavior, metric details, submission columns, or transductive permissions.
Phase 0 CI and examples must use a tiny synthetic redistributable fixture.

## Data and secrets

- Track only redistributable fixture data.
- Keep official, external, licensed, raw, and generated data out of Git.
- Record immutable source identifiers, licenses, and hashes for every dataset.
- Never commit credentials, private keys, tokens, model caches, or unrestricted
  run artifacts.
- Do not upload challenge data or predictions as CI artifacts unless the rules
  and license explicitly permit it.

## Complexity gate

Prefer a working vertical slice, stronger validation, transparent code, and
measured evidence. Do not build services, dashboards, orchestration platforms,
plugin systems, autonomous agent swarms, docking farms, or custom
cheminformatics frameworks.

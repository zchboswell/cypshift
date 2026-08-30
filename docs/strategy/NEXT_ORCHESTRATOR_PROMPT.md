# Next orchestrator kickoff — integrate D-147, then freeze D-148 contract-only

The current objective is the smallest scientifically defensible path to another
competitive OpenADMET CYP 2026 submission. Frozen challenge-family-held-out
validation outranks leaderboard evidence. The active branch is
`codex/global-v3-g4-gin300-contract`, based on signed D-146 `main` commit
`d029bb3b154f1721d094dae76e5587c0c927da2e`.

D-146 is complete and historical. PR #183 merged that exact signed commit; PR
CI run `33323263534` and exact-SHA post-main CI run `33323845649` are green.
Global-v2 remains closed. The sole G2-7G attempt is permanently UNDERPOWERED
before science, selected no candidate or runner-up, issued no token, and opens
no G2-8 or submission authority.

Under explicit 2026-08-30 user direction, D-147 freezes a genuinely distinct
contract-only Global-v3 hypothesis, `EXP-G4-GIN300`. It has a new identity and
requires future claims and roots. It is not a retry, repair, resume,
replacement, support relaxation, reinterpretation, or continuation of G2-7G,
EXP-G1, EXP-G2, EXP-G3, EXP-M1, EXP-X1, EXP-T2, TRACE, R5D, D-127, or D-128.
No prior claim, root, terminal, private capability, or one-use authority may
transfer into it. No time-based pause gate is active.

## Restore authoritative context first

Read completely, in order:

1. `AGENTS.md`;
2. `docs/strategy/PROJECT_STATE.md`;
3. `docs/phases/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/strategy/PROJECT_CHARTER.md`;
6. D-122 through D-147 in `docs/strategy/DECISIONS.md`;
7. the final relevant rows of `runs/experiment_ledger.csv`;
8. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_contract.json`;
9. `tests/test_openadmet_global_v3_g4_gin300_contract.py`;
10. the public parent contracts and aggregate receipts named by the D-147
    contract.

Treat the signed Git history, current exact worktree, canonical contract bytes,
public receipt hashes, and green exact-SHA checks as authoritative. Do not open
a protected path to refresh context. Never inspect, import, copy, execute,
patch, or derive code from a barred runner or driver. D-127/D-128 and the old
G2-7 paths remain closed.

## Exact D-147 core

The canonical contract is:

- path:
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_contract.json`;
- status: `G3_1_EXP_G4_GIN300_CONTRACT_FROZEN`;
- SHA-256:
  `b48dc0c39c12b06cdd99693539cca18b99c73d8b801e81a416e52a798df8fd4e`;
- size: 37,092 bytes / 485 lines;
- base commit: `d029bb3b154f1721d094dae76e5587c0c927da2e`.

The strict public static audit is:

- path: `tests/test_openadmet_global_v3_g4_gin300_contract.py`;
- SHA-256:
  `c32e8054da4c92f763c065c8d58d340993f6917c5c6a6d3580659febea69e3dc`;
- size: 31,371 bytes / 815 lines;
- focused result: `9/9 passed`.

The bounded safe repository command is:

`uv run --locked pytest --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`

It completed with `1434 passed, 14 skipped, 0 failed` in 347.99 pytest seconds /
348.42 wall-seconds at 901,484 KiB maximum RSS. Ruff, mypy, isolated build,
and installed-wheel two-root reproduction are green. Treat these as repository
and CI parity evidence only; they create no model-quality or downstream
authority and do not freeze incidental wheel or tree hashes.

The frozen current rules snapshot is Space revision
`4a87b2dcc800036b745e4c7bbb0023be817b5408`, config Git blob
`fd3a6aadf8938f0a142ef309768bf461aae7f802`, and config SHA-256
`342cd287e63a79c61b8e18fa46e81950ebb7333b6e91ee427af18426e04ca52f`.
It permits external data and pretrained models, requires accurate disclosure,
and grants no current portal or upload authority. A future submission milestone
must reauthenticate the then-current rules and method-report requirements.

## Frozen scientific design

The hypothesis is that a fixed supervised-masking GIN contributes useful
molecular context beyond handcrafted MapLight features, especially for CYP1A2
or CYP2D6. The exact candidate is:

- unchanged accepted MapLight columns `0:2563`;
- exact provenance-cleared 300-column `gin_supervised_masking` block at
  `2563:2863`;
- one fixed `CatBoostRegressor` with MAE loss, `random_strength=2`, model seed
  `1`, CPU, 16 threads, and no additional fit argument.

Two mandatory same-learner controls are fixed:

- `G4-MAPL2563-SHUFFLED-GIN300`, with whole 300-value donor vectors permuted
  only within each exact repeat/fold/train-or-validation partition; and
- `G4-MAPL2563-NOISE300`, with Gaussian vectors generated only within each
  exact repeat/fold/train-or-validation partition.

No donor, identity, feature vector, or noise assignment may cross the outer
training-validation boundary. Exact duplicate raw hashes remain identical
inside a partition. No alternative permutation, distribution, seed,
normalization, checkpoint, or post-outcome control is allowed.

A future development attempt, only after all intervening gates, is fixed at:

- three systems;
- three repeats, five outer challenge-family folds, and four endpoints;
- 60 fits per system and exactly 180 new fits total;
- 46,896 prediction rows per system and 140,688 new rows total;
- zero baseline refits and zero inner-selection fits;
- 48 tutorial calls;
- one synchronized 2,000-replicate component-bootstrap stream shared across
  five fixed contrasts, with at most 20,000 synchronized draw attempts total.

Candidate promotion requires every baseline member: at least 3% tutorial-
primary improvement, 0.015 absolute component-macro MAE improvement, paired
component-bootstrap upper 95% bound below zero, at least 8/15 favorable cells,
no endpoint degradation above 0.015, and at least one of CYP1A2/CYP2D6
improving by 0.010. Attribution additionally requires at least 1% tutorial-
primary and 0.005 component-macro improvement over each control, paired upper
bounds below zero, at least 8/15 favorable cells against each, and neither
control independently passing the baseline gate. Equality is insufficient for
the paired upper-bound and favorable-cell gates. A clean miss closes the lane.

No tuning, early stopping, calibration, stack, blend, seed bagging,
endpoint-specific recipe, external label, assay-context feature, residual
search, alternate checkpoint, support relaxation, control, runner-up, or
outcome-driven successor is authorized.

## Provenance, rights, and claims boundary

Historical fixed-plus-GIN evidence improved binary CYP2C9, CYP2D6, and CYP3A4
AUPRC under scaffold and chemistry-community holdouts. The shuffle and noise
controls did not reproduce those gains. This is supportive mechanism and
feasibility evidence only. It is not OpenADMET pIC50 evidence, contains no
historical CYP1A2 GIN result, and cannot satisfy development, robustness,
confirmatory, or submission gates.

The pretraining lineage contains approximately two million ZINC15 molecules
and approximately 456,000 ChEMBL molecules across 1,310 assays. OpenADMET
structure and assay overlap are unknown. This must be disclosed. Do not claim
clean zero-shot transfer, uncontaminated external validation, strict family
holdout from all pretraining, known absence of challenge-structure overlap, or
known absence of challenge-assay overlap.

Prospective eligibility requires exact SNAP, DGL-LifeSci, and MolFeat object
identity; rights and notices; complete tensor conversion coverage; identical
graph construction; exact 300-column finite float64 embeddings; Linux x86_64
parity; and strict nonredistribution. No checkpoint or pretraining data may
enter Git, CI artifacts, submission files, public terminals, documentation
bundles, or publication bundles.

Contract preparation performed a bounded public-source rights/hash audit:

- one public SNAP source archive downloaded to temporary non-Git storage;
- 33 public checkpoint files / 204,567,885 bytes temporarily persisted outside
  Git;
- one SNAP checkpoint / 7,452,448 bytes opened only for hashing;
- zero DGL checkpoint bytes downloaded;
- zero MolFeat checkpoint bytes downloaded;
- zero checkpoint tensors deserialized or executed;
- zero embeddings generated;
- zero checkpoint files added to Git or the workspace.

Do not summarize this as zero checkpoint download or zero checkpoint read.
Equally, do not call it model loading, checkpoint execution, feature generation,
or parity evidence. It creates no current checkpoint-fetch or model-load
authority.

## Exact D-147 package and authority

The coherent tracked package contains exactly nine files:

1. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_contract.json`;
2. `tests/test_openadmet_global_v3_g4_gin300_contract.py`;
3. `benchmarks/openadmet_cyp_2026/README.md`;
4. `docs/phases/README.md`;
5. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
6. `docs/strategy/PROJECT_STATE.md`;
7. `docs/strategy/DECISIONS.md`;
8. `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`;
9. `runs/experiment_ledger.csv`.

D-147 consists of one contract, one public static test, and the exactly
disclosed bounded public source-rights/hash audit above. It changes no
dependency or runtime and adds no implementation. Beyond that audit, it opens
zero pretraining row, official input,
official structure, target value, baseline prediction, feature row,
confirmatory truth, historical row-level artifact, blinded-test row, or TDI
row. It performs zero GIN feature build, model fit, prediction, development
metric, bootstrap, claim creation or consumption, selection token, contender
lock, full training, submission row, validator call, official metric,
leaderboard selection, portal or credential access, live upload, or GPU
operation. Its current authority is limited to the contract and public static
audit; the source-rights/hash audit grants no model or execution authority.

Do not modify a dependency, runtime, implementation, historical test, old
contract, driver, compiler, claim, terminal, D-143/D-146 evidence, protected
artifact, or barred path in D-147.

The ledger row must parse as exactly 18 columns and distinguish the temporary
public-source hash accounting from zero deserialization/execution. It must bind
the two core hashes, D-146 signed/green parent, current rules snapshot,
candidate/control identities, budgets, unknown-overlap disclosure,
D-148/D-149 separation, and every zero-authority counter. Its self-referential
commit field remains `not_applicable_self_referential_commit`.

## Exact next action

1. Authenticate the D-147 nine-file diff against signed base
   `d029bb3b154f1721d094dae76e5587c0c927da2e`. Reject any tenth file or any
   modification outside the package.
2. Recompute the contract and test hashes/sizes, parse the contract with
   duplicate-key and nonfinite rejection, and require the focused static audit
   to pass `9/9`.
3. Parse `runs/experiment_ledger.csv` as exactly 18 columns per row, parse every
   embedded JSON field, and confirm the D-147 row is the sole append.
4. Verify every narrative surface agrees on the distinct-lane boundary,
   temporary public-source audit accounting, exact design and gates,
   zero-authority facts, and D-148 contract-only then D-149 implementation
   sequence. Remove every stale current-tense instruction to integrate D-146 or
   stop all future prospective work.
5. Run the bounded relevant repository checks, Ruff, format, compilation,
   typing, isolated build, and installed-wheel parity required by the current
   workflow. Do not execute a GIN worker, checkpoint, model, official driver, or
   protected capability.
6. Create one coherent SSH-signed `zchboswell` commit with no AI attribution.
   Push the branch, open a pull request, and require all checks on the exact
   signed head.
7. Recheck clean mergeability and integrate the reviewed signed commit locally
   with fast-forward only. Do not use GitHub's hosted rebase merge. Push `main`
   without rewriting the commit and require green push-event exact-SHA
   post-main CI.
8. Only then begin D-148, and begin it as contract-only.

## D-148 contract-only and D-149 implementation

D-148 may freeze only the deterministic Linux x86_64 rights/provenance/runtime
and label-free synthetic-capability contract plus public static tests. It must
bind:

- the isolated Python 3.10.13 environment and every wheel, hash, license, and
  notice;
- the three exact SNAP, DGL-LifeSci, and MolFeat public checkpoint objects;
- temporary non-Git storage, no-network-after-fetch, and nonredistribution;
- complete SNAP-to-DGL state-dictionary conversion with no missing, extra,
  silently reshaped, or unaccounted tensor;
- three fresh CPU-process executions on the same existing eight-row
  redistributable fixture;
- identical graph construction, exact 300-column finite float64 output, and
  byte-identical pooled embeddings when serialization permits;
- any necessary numeric tolerance prospectively, before observing a
  difference, while retaining identical downstream fixture predictions;
- two opposite-order synthetic feature/model roots, deterministic terminals,
  cleanup, and 20% resource margin for the future 180-fit workload;
- a bounded real CatBoost API/timing probe using only contract-frozen
  redistributable synthetic labels and no official target;
- fail-closed ineligible and resource-infeasible prefit statuses.

D-148 itself may not fetch or load a checkpoint, create a runtime, implement a
feature builder, execute parity or a model, open an official row or target, or
create a claim.

Only after D-148 is independently reviewed, SSH-signed, fast-forward
integrated, and green on exact-SHA post-main CI may D-149:

- create the isolated Linux runtime and narrow public implementation;
- fetch only the three frozen public checkpoint objects into isolated non-Git
  storage;
- run redistributable fixture provenance/parity and synthetic mechanics under
  one frozen formal-attempt boundary; and
- publish only hashes, notices, aggregate parity/resource facts, cleanup, and a
  deterministic terminal.

Any rights, notice, object-hash, tensor-coverage, graph, embedding, shape,
finiteness, Linux-parity, nonredistribution, determinism, or resource defect
closes `EXP-G4-GIN300` before official access. There is no in-place repair,
fallback, alternate artifact, automatic successor, reduced design, second
probe, or enlarged ceiling.

A hard claim-bound feature or development wall, CPU, restricted-storage,
peak-RSS, GPU, or supervisor breach publishes
`G3_G4_GIN300_RESOURCE_ABORTED`. Partial scientific evidence from that attempt
has zero model-quality authority.

## Continuation and handoff

If the user says `continue` while D-147 is unfinished, authenticate the branch,
HEAD, worktree, exact nine-file diff, final two core hashes, focused result,
ledger integrity, and current PR/CI state. Resume only the earliest unfinished
D-147 validation, signed review, fast-forward integration, or exact-SHA
post-main-CI step.

If D-147 is integrated and post-main CI is green, continue only with D-148
contract drafting and static review. Do not combine D-148 with runtime creation,
checkpoint fetch, implementation, or execution.

If D-148 is also integrated and post-main CI is green, D-149 may proceed only
under its exact frozen single-use implementation/formal-attempt boundary. Do not
infer official structure, target, feature, fit, metric, confirmatory, test,
submission, portal, or upload authority from a capability pass.

Before any later handoff, record:

- exact branch, HEAD, base, and clean/dirty state;
- exact package files and hashes;
- focused, ledger, format, typing, build, and CI results;
- commit signature and author identity;
- branch push, PR, exact-head check state, integration SHA, and post-main run;
- any active process and all temporary non-Git roots;
- exact public checkpoint hash-only accounting versus model execution;
- every protected/official/claim/fit/metric/submission counter; and
- the earliest authorized next gate.

## Closed operations

- Never invoke or reinterpret G2-7G, G2-8, D-127, D-128, or another closed
  experiment.
- Never reuse or derive from an old claim, root, terminal, or one-use authority.
- Through D-148, do not fetch or load checkpoint model bytes, create the GIN
  runtime, implement a feature builder, or execute parity or a model.
- Do not open official structures, targets, baseline OOF rows, confirmatory
  truth, historical row-level evidence, blinded test, or TDI data.
- Do not fit a model, generate a prediction, evaluate a development or official
  metric, run a validator, generate a submission, or live-upload.
- Do not use leaderboard or portal evidence for selection.
- Do not expose a private identifier, score, rank, path, row value, credential,
  checkpoint, embedding row, pretraining molecule, or unrestricted log.
- Do not add a candidate, feature, seed, group, threshold, calibration, blend,
  retry, cache, concurrency change, framework, service, or outcome-driven
  successor.
- Do not call fixed MapLight retained or selected by the underpowered outcome.
- Do not claim clean zero-shot or uncontaminated external validation.

`EXP-G4-GIN300` may reach a submission artifact only after separate accepted
capability, official label-free feature, development, robustness/contender,
sealed confirmatory, full-training, and byte-identical 750-row submission
milestones. Portal credentials and upload remain separately human-armed.

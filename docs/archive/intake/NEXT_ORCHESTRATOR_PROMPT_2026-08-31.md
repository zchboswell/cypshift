# Next orchestrator kickoff — execute one-use direct MapLight reauthentication

The current objective is the strongest scientifically defensible route to a
competitive OpenADMET CYP 2026 submission. Global-v2 is closed: G2-7G is
permanently UNDERPOWERED before science, selected no candidate or runner-up,
and opens no G2-8 authority. The distinct Global-v3 `EXP-G4-GIN300` lane is
also permanently closed before claim consumption under D-149 status
`G3_2_EXP_G4_GIN300_PRECLAIM_CLOSED`. Do not implement, retry, repair,
replace, or redesign G4.

The active backout is the historically accepted direct MapLight candidate.
D-150 froze its conditional read-only reauthentication handoff and is now
signed, fast-forward integrated, and green on exact-SHA post-main CI. The
current private candidate remains unknown and unopened; D-150 performed no
validator call, portal or credential access, or upload. The next authorized
work is one separate, one-use read-only result milestone. Any later candidate-
specific human-authorized upload remains a distinct operation.

## Midnight hard-stop handoff — 2026-08-31 00:02 EDT

The 2026-08-31 midnight America/New_York hard stop is complete. No feature,
scientific, private-candidate, validator, portal, credential, or upload work
began after the cutoff. All subagents are collected. The one-shot
`cypshift-midnight-hard-stop` heartbeat is paused and must not recur.

D-150 completed before the cutoff:

- signed commit `ac043aaaf8dd3a7db1815859f7fa60f05c52277d`, sole parent
  `0bf9b253002399a61e3d8d4e37e1a957ebd198ec`, retains the expected good
  `zchboswell` SSH ED25519 signature;
- PR #187, `Freeze direct MapLight reauthentication handoff`, merged at
  `2026-08-31T03:27:47Z`; its base is the exact parent, its head and merge
  commit are the exact signed D-150 commit, and no synthetic or rewritten
  commit exists;
- exact-head pull-request CI run `33353183705` completed successfully on that
  SHA: Python 3.11 job `99370289169`, Python 3.12.3 job `99370289089`, and
  Python 3.14 job `99370289232` all passed formatting/types, tests, build, and
  installed-package reproduction;
- exact-SHA main push CI run `33353921881` also completed successfully:
  Python 3.11 job `99372351943`, Python 3.12.3 job `99372351812`, and Python
  3.14 job `99372351950` all passed the same complete lane;
- immediately before this required handoff-only edit, local `HEAD`, local
  `main`, `origin/main`, and live remote `main` all equaled the signed D-150
  commit and the worktree was clean.

The immutable D-150 core identities remain:

- contract SHA-256
  `589facbbe8b51aeee00abdcba756c9119262572954854f438c549cab7ff98fcd`,
  22,489 bytes / 431 LF;
- static test SHA-256
  `9b2d17eb878367a6d786d3fa4606c6b64ec8e518ae4fffeac8d086738ec4a53d`,
  89,220 bytes / 2,556 LF;
- ledger SHA-256
  `8fea9346f3a056c590dd7b4515acff9f02105fea26e1d7b71b402525141192ea`,
  448,688 bytes / 201 LF, with unchanged D-149 prefix
  `515801a45120ea07fada9b3193a4f10614074b77674d0f3b0ea0c01dabaa26fa`
  and sole D-150 row
  `079414a464135a3f702580433b6524fd003f78fd0f812e8f989b2a04547d0552`.

Validation remains exact: focused D-150 plus D-149 `9 passed`; 196 independent
fail-closed D-150 mutations; Ruff over the 327-path public allowlist and
focused formatting; Python 3.10.13 AST and temporary compilation; mypy over 78
source files; safe suite `1,458 passed, 14 skipped, 0 failed`; offline native
build; and two byte-identical installed-wheel public-fixture replays. PR and
post-main CI independently repeated the repository tests, build, and installed
slice on all three Python lanes.

There is no technical blocker to the contract-authorized one-use hash check,
but there is deliberately no evidence yet that the current private candidate
exists, is readable, or matches either historical hash. Live-current rules,
validator behavior, portal state, credentials, upload eligibility, and upload
authority also remain unknown or false. The competition objective is therefore
not complete. The only conditional go is the single hash-only attempt; any
failure, ambiguity, repair need, or second-attempt need withdraws the route.

This paragraph and the revised resume instructions below are the sole required
post-midnight, handoff-only worktree mutation. They are not integrated evidence
and must not be committed or pushed alone as a new milestone. On resume,
`git status --short --branch` must show clean `main` plus only this modified
handoff file. Any other path or ref drift is a blocker. Preserve and review this
handoff change as part of the later result milestone rather than rewriting the
signed D-150 commit.

## Restore authoritative context first

Read completely, in order:

1. `AGENTS.md`;
2. `docs/strategy/PROJECT_STATE.md`;
3. `docs/phases/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/strategy/PROJECT_CHARTER.md`;
6. D-076, D-147, D-148, D-149, and D-150 in
   `docs/strategy/DECISIONS.md`;
7. the final relevant rows of `runs/experiment_ledger.csv`;
8. `benchmarks/openadmet_cyp_2026/DIRECT_BASELINE_HANDOFF.md`;
9. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json`;
10. `benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_handoff_contract.json`;
11. `tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py`.

Treat signed Git history, canonical tracked bytes, and exact public receipts as
authority. Do not open a protected/private path merely to refresh context. Do
not inspect, import, copy, execute, patch, or derive code from a barred G2-7
runner or driver. D-127/D-128 and every closed Global-v2 path remain barred.

## Integrated D-149 boundary

D-147 is immutable integrated scientific-contract history at signed commit
`b5cf47c6bc8ccc2dc29c7167b1a436d792338509`; PR #184 CI run `33327853790`
and exact-SHA post-main CI run `33328374514` are green. D-148 is immutable
integrated capability-contract history at signed commit
`f0f3b6f9380eebef0b03d87f29eb659ffc84f8d5`; PR #185 CI run `33337794223`
and exact-SHA post-main CI run `33338342415` are green. Their prospective
implementation/run schedule never activated.

D-149 is immutable integrated terminal history at signed commit
`0bf9b253002399a61e3d8d4e37e1a957ebd198ec`, merged without rewriting through
PR #186. Exact-head PR CI run `33348758894` and exact-SHA post-main push CI run
`33349365347` are green across Python 3.11, 3.12.3, and 3.14. Its canonical
rejection record and strict test remain:

- `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_transition_rejection.json`,
  SHA-256
  `10a7f783d73ae60c6da479ffbd8cd3e3443b3f8dace88e177fd9c17c44e1331c`;
- `tests/test_openadmet_global_v3_g4_gin300_transition_rejection.py`, SHA-256
  `f033a7577dca4eafd3cec979938292fcb0d7b6ef80f0e86d6134fc8d9f4d944f`.

No G4 implementation, runtime, claim, result, model, fit, prediction, metric,
submission, validator call, portal access, upload, or GPU operation occurred.
No defect in D-150 or later work can reopen G4.

D-149 also superseded D-148's unactivated prospective use of “D-150” for a G4
capability invocation. The current D-150 is the separate direct-baseline
contract promised by D-149, not a revival or execution of D-148.

## Historical direct MapLight evidence

The competitive backout has three immutable public identities:

- submission SHA-256
  `9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`;
- manifest SHA-256
  `96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6`;
- tracked handoff SHA-256
  `6a9402ca3fdf02dbcad079cba82162132e5b149f6adf69f80ea05d177e1ecec4`,
  2,919 bytes / 55 LF.

The handoff records two independent byte-identical rehearsals, 750 ordered
rows, 3,000 finite predictions, and a historically valid pinned-validator
result with zero errors. Fixed MapLight remains the strongest prior internal
baseline at development component-macro MAE `0.5837812652150708`.

These are meaningful historical receipts, not current reauthentication. The
MAE is not an official or leaderboard score, fresh selection, or robustness
result. G2-7G did not select or robustness-accept MapLight, and G2-8 remains
closed. Current private candidate existence, bytes, and readability are
deliberately unknown and unopened; the current validator result is unknown and
uninvoked.

## Exact D-150 contract-only package

D-150 freezes:

- contract
  `benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_handoff_contract.json`,
  schema
  `cypshift.openadmet_cyp_2026.direct_baseline_reauthentication_handoff_contract.v1`,
  status `DIRECT_BASELINE_REAUTHENTICATION_HANDOFF_CONTRACT_FROZEN`, SHA-256
  `589facbbe8b51aeee00abdcba756c9119262572954854f438c549cab7ff98fcd`
  (22,489 bytes / 431 LF);
- strict public static test
  `tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py`,
  SHA-256
  `9b2d17eb878367a6d786d3fa4606c6b64ec8e518ae4fffeac8d086738ec4a53d`,
  89,220 bytes / 2,556 LF, focused `5 passed`, and exactly 196 independent
  fail-closed mutations rejected.

Both contract and test identities are independently frozen and integrated.
Recompute them before any future result work and reject any drift.

Pre-propagation validation was executed once against the exact quiescent
nine-path snapshot before this paragraph and the sole D-150 ledger row were
updated: contract `589facbbe8b51aeee00abdcba756c9119262572954854f438c549cab7ff98fcd`,
test `9b2d17eb878367a6d786d3fa4606c6b64ec8e518ae4fffeac8d086738ec4a53d`,
benchmark README `6fa3fb503dc9fbe4cae53e39056ff43052ee097ddc15733d5d93fb3e1d78d318`,
active phase `20c0886be11f9abe72cc5a8500691adc3e6b165a1be14b3421cbeee9a05972b7`,
phases README `6211ab1251e486fe816982dd125f2d2b8e93757a3c879e1431354c7f668dbec1`,
decisions `07685ffe1d6a5168db37aada2b78ddcce79dfdd6aed06ec4536aed079828288c`,
next prompt `28c2ad685778cdd489517b2c987976f0776d5a3140a95e6c82c58981ab935036`,
project state `c88afa585d2ad5ee2186382921d109358f6acea4a5beb7b171ebe8dcdd112195`,
and ledger `a2eaad989ecc61e95012388ea6414c1356f6e8ede83660ace6ec163aaae9f094`.
The focused D-150 plus D-149 pair passed 9/9 with zero fail or skip in
0.42 pytest seconds / 0.67 wall-seconds at 43,432 KiB maximum RSS. Ruff passed
on the exact 327 public Python paths with the barred trio excluded; the focused
two-test format check passed; Python 3.10.13 AST parsing and temporary
compilation passed 2/2; and mypy passed on 78 source files in 3.57 seconds at
268,924 KiB maximum RSS. The safe suite passed 1,458 with 14 skipped and zero
failed in 363.81 pytest seconds / 364.38 wall-seconds at 903,120 KiB maximum
RSS. The offline native `uv build` passed. The forced PEP 517 offline route
was unavailable only because `uv-build` was not cached and is not a blocker.
Two Python 3.12.3 installed-wheel roots were byte-identical at 9 files / 36,758
bytes each; each replay recorded 7 accepted, 1 quarantined, 7 warnings,
3 supported, 1 unsupported, and 21 predictions. Uninstrumented suite/internal
network, cache, import, fit, metric, and validator totals were not retained and
remain unknown rather than guessed as zero. Scoped private, official,
candidate-validator, portal, credential, upload, and GPU operations remained
zero. Incidental build and tree hashes are not frozen. This is pre-propagation
evidence; final focused and diff checks are rerun after narrative/ledger
propagation.

The complete D-150 package changes exactly nine paths:

1. `benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_handoff_contract.json`;
2. `tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py`;
3. `benchmarks/openadmet_cyp_2026/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/phases/README.md`;
6. `docs/strategy/DECISIONS.md`;
7. `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`;
8. `docs/strategy/PROJECT_STATE.md`;
9. `runs/experiment_ledger.csv`.

No tenth path belongs in D-150. It adds no runner, validator wrapper, upload
integration, model, prediction artifact, private root, or result.

The latest-tracked public requirement snapshot as of
`2026-08-24T04:21:32Z` binds dataset, Space, and tutorial heads
`85f8b358d0a2056a98b990dd75d3b3ec9247862b`,
`13c5057b37d1e72b3f036dd0d59718b1823f8fdd`, and
`858ae63ce79934113bccdb7fc65467de5f7b1935`, plus
`source_receipts.json`/`764e59d3...36974`,
`challenge_contract.json`/`344d3414...6123`, and
`submission_contract.json`/`4be9933c...9a3c`. It requires 750 rows, six
ordered identifier/SMILES/direct-prediction columns, numeric predictions, and
finite values. `live_public_rule_refresh_performed=false` and
`live_current_rules_claimed=false`: this is not a live rules refresh or claim
about current portal/backend behavior. Live-backend parity, row order,
duplicate-identifier behavior, and extra-column behavior remain unresolved.
Do not turn a raw-byte hash match into a current validator or upload-readiness
claim.

## D-150 authority and accounting

The contract may bind the immutable handoff and historical candidate receipts
against that latest-tracked public snapshot. It may preregister the later one-
use, read-only checks and the strict no-repair terminal rule. It cannot establish
that the current private candidate exists or passes those checks.

D-150 itself performs exactly zero:

- private candidate or official-row reads;
- candidate or manifest mutation;
- validator calls;
- submission regeneration, model fits, predictions, or metrics;
- portal, credential, or private leaderboard access;
- leaderboard use for selection;
- uploads or GPU work.

Do not infer private candidate state from a historical path, handoff prose,
prior validator result, or portal history. Do not use private portal evidence
to select, rank, tune, repair, or replace any candidate.

## Conditional go and competition backout

The exact D-150 package has now completed independent review, final-identity
freeze, SSH-signed fast-forward integration without rewriting, and green
exact-SHA post-main CI. A separate result milestone may therefore make one
read-only reauthentication attempt after the public implementation and exact
command are independently frozen and reviewed. That attempt may authenticate
only the unchanged historical candidate. On success it opens and enumerates
the root exactly once and opens each exact file exactly once only to hash raw
bytes in memory. On failure each operation is attempted at most once, the first
defect stops the protocol, and no later operation runs. It may not parse or
validate either file, open official data, write or retain candidate bytes, or
invoke a validator.

Any of the following stops the direct route:

- the fixed candidate is absent, unreadable, mutable, or not a regular bounded
  artifact;
- submission or manifest bytes differ from the historical identities;
- the latest-tracked public snapshot identity drifts or a parser, validator,
  official-data read, or second file open would be needed;
- required receipt, authority, one-use, accounting, or cleanup evidence is
  incomplete.

On a stop, do not regenerate, refit, repredict, rewrite, reorder, reformat,
patch, repair, resume, retry, replace, choose an alternate candidate, or open a
new model lane. G4 and G2-8 are already closed; therefore a failed one-use
reauthentication is the competition backout condition for this build.

Result publication is at most one no-replace write. A safely classified
success or failure publishes one result only after closing all descriptors and
discarding all in-memory candidate bytes, at
`benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_result.json`,
under schema
`cypshift.openadmet_cyp_2026.direct_baseline_reauthentication_result.v1`.
It retains only expected public hashes and aggregate outcome accounting and
retains or publishes no private locator, stat metadata, or candidate bytes.
A crash, ambiguous cleanup, or publication failure may leave the result absent,
but durable evidence that private locator resolution began still consumes the
sole invocation and withdraws the route without retry.

The exact future taxonomy is:

- clean read-only success: `DIRECT_BASELINE_REAUTHENTICATED_READ_ONLY`, route
  state `DIRECT_BASELINE_ROUTE_REAUTHENTICATED`;
- safely published failed-closed reauthentication:
  `DIRECT_BASELINE_REAUTHENTICATION_FAILED_CLOSED`;
- deterministic route state for any failure, ambiguity, or need for retry:
  `DIRECT_BASELINE_ROUTE_WITHDRAWN`.

D-150 emits none of these result tokens; it freezes them prospectively. A
safely published immutable result uses success or failure as its outcome, and
failure sets the withdrawal state in that same result. Every failure,
ambiguity, or need for another attempt withdraws the route, including an absent
or unauthenticatable result after durable evidence that the attempt began.
Success leaves the route operationally eligible but keeps
`upload_authority=false`.

A clean future result grants only a candidate-specific human handoff. It does
not itself open a portal, inspect a remote result, or upload. Any live upload
remains a later, separate operation that requires explicit human authorization
for those exact reauthenticated bytes.

## Exact next action

1. Reauthenticate the stopping state without opening any private path:

   ```text
   git status --short --branch
   git rev-parse HEAD refs/heads/main refs/remotes/origin/main
   git verify-commit ac043aaaf8dd3a7db1815859f7fa60f05c52277d
   git ls-remote origin refs/heads/main
   gh pr view 187 --json state,mergedAt,mergeCommit,baseRefOid,headRefOid,title,url
   gh run view 33353921881 --json status,conclusion,headSha,event,jobs
   sha256sum benchmarks/openadmet_cyp_2026/direct_baseline_reauthentication_handoff_contract.json tests/test_openadmet_direct_baseline_reauthentication_handoff_contract.py runs/experiment_ledger.csv
   git diff --check
   git diff -- docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md
   ```

   Require signed `HEAD`/local `main`/`origin/main`/remote `main` all exact
   `ac043aaaf8dd3a7db1815859f7fa60f05c52277d`, PR #187 merged with that same
   merge commit, push run `33353921881` successful on that exact SHA, the three
   frozen file hashes above exact, and no worktree change except this midnight
   handoff. Do not append a second D-150 ledger row or refreeze D-150.
2. After explicit user resumption, create a fresh result branch from exact
   `main` with
   `git switch -c codex/direct-baseline-reauthentication-result`. Preserve this
   handoff diff for review; do not amend or rewrite D-150.
3. Before resolving the private locator or consuming the sole invocation,
   derive the exact result JSON keys, no-replace publication mechanics, bounded
   byte-read implementation or command, failure mapping, cleanup proof, changed-
   path allowlist, accounting, and static adversarial tests directly from the
   frozen D-150 contract. Review those public bytes independently while all
   private-attempt counters remain zero. A required contract change, unsafe
   implementation, or unresolved semantic ambiguity withdraws the route; do
   not create another correction chain.
4. Freeze and independently authenticate the exact one-use command and its
   pre-attempt state. The command must resolve the sole locator only from the
   authenticated tracked handoff, open/enumerate the root at most once, open
   each exact file at most once, hash raw bytes only, close every descriptor,
   discard in-memory candidate bytes, and publish at most one no-replace result
   only after cleanup. It must perform no parse, validator, official-data,
   model, network, portal, credential, leaderboard, or upload operation.
5. Execute that frozen private operation once and only once. On exact success,
   publish `DIRECT_BASELINE_REAUTHENTICATED_READ_ONLY` with route state
   `DIRECT_BASELINE_ROUTE_REAUTHENTICATED` and `upload_authority=false`. On the
   first defect, ambiguity, cleanup/publication uncertainty, or need for
   another attempt, stop and set the effective route state to
   `DIRECT_BASELINE_ROUTE_WITHDRAWN`; do not retry, repair, regenerate,
   substitute, validate, or search elsewhere.
6. Validate and integrate the immutable result milestone through the normal
   focused/static/safe gates, independent audit, one signed `zchboswell`
   commit, exact-head PR CI, local fast-forward-only integration, and exact-SHA
   post-main CI. Never write private locator, stat metadata, or candidate bytes
   into Git or logs.
7. Even after a clean hash result, stop. A current-rule refresh, validator or
   portal interaction, credential use, and upload remain a separate candidate-
   specific human-authorized operation. Do not call the candidate selected,
   robustness-accepted, officially scored, leaderboard-proven, or upload-ready.

## Midnight handoff state

The midnight hard stop ran once and is now paused. D-150 review, exact-head CI,
fast-forward integration, non-rewriting main push, and exact-SHA post-main CI
all completed before the cutoff. No private-candidate attempt began. The first
incomplete action is numbered step 1 above, followed by public-only design and
independent review of the separate result milestone before any one-use locator
resolution. The handoff grants no result, private-candidate, validator, portal,
credential, current-rule, upload, or new-model authority.

Throughout D-150, do not access official structures or targets, baseline OOF
rows, confirmatory truth, historical row-level artifacts, blinded-test bytes,
TDI, the current private candidate, private portal state, credentials,
leaderboard observations, or upload capabilities. Do not call MapLight
selected, retained by G2-7G, or robustness-accepted. Do not reopen G2-8.
`global_TDI` remains only the frozen TDI fallback.

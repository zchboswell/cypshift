# Next orchestrator kickoff — integrate D-146 evidence closure, then stop

This handoff is active on branch
`codex/g2-7g-post-attempt-transition-evidence`. D-145 is integrated as signed
commit `ce289b5fccaaf1d63343553961ad41309db19d04`; PR #182 CI run `33125925508`
and exact-SHA post-main CI run `33126546606` are green.

After a fresh green read-only preflight, the sole fixed no-argument G2-7G
official driver ran exactly once under cumulative supervision. It consumed the
sole private derived claim, exited zero, completed cleanup, and published the
contracted terminal:

`G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED`

The attempt is permanently consumed. It may not be retried, resumed, moved,
repaired, overwritten, replaced, reduced, reordered, or reinterpreted.

The objective remains the smallest scientifically defensible path to a
materially better OpenADMET CYP 2026 submission. Frozen family-safe validation
outranks leaderboard evidence. That path has now reached a frozen clean
pre-science support stop: no G2-7 contender was selected, so G2-8, G2-9, and
submission preparation are not authorized. Fixed MapLight remains the best
*previously validated* internal system at component-macro MAE
`0.5837812652`; D-143 does not robustness-validate, reselect, improve, or
reject it.

## Restore authoritative context first

Read completely, in order:

1. `AGENTS.md`;
2. `docs/strategy/PROJECT_STATE.md`;
3. `docs/phases/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/strategy/PROJECT_CHARTER.md`;
6. D-122 through D-146 in `docs/strategy/DECISIONS.md`;
7. the final relevant rows of `runs/experiment_ledger.csv`;
8. the public G2-7 contracts, D-135 acceptance, D-136 bridge, D-137/D-138
   mechanics, D-139/D-140 transitions, D-141 implementation hashes, D-142
   receipt, and D-143 public underpowered record and audit test.

Treat the current worktree, signed Git history, GitHub checks, the immutable
private aggregate hashes recorded in the public projection, and exact fixed-root
metadata as authoritative. Do not inspect a protected path to refresh context.
Never inspect, import, copy, execute, patch, or derive code from the rejected
G2-7B runner or driver. D-127/D-128 remain permanently barred.

If the user says only “continue,” resume only the earliest unfinished D-146
knowledgebase review, signed integration, or exact-SHA post-main CI step below.
If D-146 is already integrated and green, audit and report the terminal stop;
do not infer authority to run another scientific gate.

## Verified parent lineage

- D-122 robustness contract:
  `ad9aef871ab06e5082568f20a9a6d293897924bdfeda2fb341685cffaa7a45af`
- corrected D-133 execution contract:
  `9464b0947255298a8de8836af6178857841bb2a55bc5c0f4897be2ba91151bcf`
- tracked immutable public claim template:
  `d7e68837a9df0b392eab7d03282ec84d21b8787f4b2ac14b1fc79fec44df6f9f`
- D-135 formal science-kernel acceptance:
  `4c886d0dd51bfb48095ac2a8f88b202e78cb85f840f8f7bd474c2982ffedf390`
- D-136 provenance bridge:
  `2820c30f387d138d115b36f621b038dc75a1f5af43a7fa9f97b3b837a33a0dc3`
- D-137 repair contract:
  `f6576d61147731066dd09577338ab236b5ee0054eb4380377fa3bf6f0534b967`
- D-138 seal-order erratum:
  `a3e1bd653f28297357380ad14da3fcd640d89d3476954830c8fd63c2f3faeb33`
- D-139 test-transition contract:
  `6703ad308d5a4188e5b42aa325cf59d9d10729e08ba0ed2c0dce44d445709c2c`
- D-140 source-shape transition contract:
  `d4ff0e57b4c5d8b6bae808d0749f5b8e116965f18f2df3fee6e04e58dd727417`
- D-141 corrected official driver:
  `feab960a54dd5ff818e29d062ad8eba48538658fe38a75d01f7c76f3d2daf103`
- D-141 composite acceptance driver:
  `3e209b88df7634f47884ce45653673a5407310575146392a77811fb4ed67ba9f`
- D-141 focused orchestration tests:
  `f17b5b2f39b92892b046f289d6ebdb1888d705ea7a27ea24b3ca3013d39289b0`
- D-141 exact six-marker conftest:
  `03d92bf3a2890a61190a6a4fc7a6bc59fa900ed6ea4b904223b1f2f991699d95`
- D-142 composite acceptance:
  `92a18f0e6837d70d4bb39560d42a22cfb23acac8ea72a955b9656b392d954596`
- D-142 signed integrated commit:
  `d70d817dd2d7e30f63f6066dfbfdc4cef7e02bd3`
- D-142 PR/post-main CI:
  `33116144405` / `33116954304`, both `success`
- D-143 public underpowered record:
  `benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_official_underpowered.json`,
  SHA-256 `d52bee5e4ed4669c6db7e3061fc8aed8f55e81a0e4d3d17aca73e326df184a2d`,
  size 9,945 bytes
- D-143 standalone public audit:
  `tests/test_openadmet_global_v2_maplight_robustness_official_underpowered.py`,
  SHA-256 `e5d65bf32a9185ea3c3c63bb658d5418e8393ec534488f50cbeb4dad1a8354ce`,
  size 21,081 bytes, `1/1 passed`
- D-143 signed integrated commit:
  `d630702074bfefa4bda4730ba7c1b7519c3c6f1a`
- D-143 PR/post-main CI:
  `33121287357` / `33122070763`, both `success`
- D-144 post-attempt transition contract:
  `benchmarks/openadmet_cyp_2026/global_v2_maplight_robustness_post_attempt_test_transition_contract.json`,
  SHA-256 `d5eb773fc2584deaf31c5f3a3a283e365b6540d0c714fd08cb70ec02937b735f`,
  18,216 bytes / 263 lines
- D-144 public contract test:
  `tests/test_openadmet_global_v2_maplight_robustness_post_attempt_test_transition_contract.py`,
  SHA-256 `a654075771d9f42ac3a7dcbf058e8ca4dba879660888c2aa4262d1e4ea60a1fa`,
  29,788 bytes / 732 lines, `1/1 passed`
- D-144 signed integrated commit / PR:
  `5d7ed5db76ec0928ba34e19e72ab839ee556d51e` / #181
- D-144 PR/post-main CI:
  `33123874692` / `33124525495`, both `success`
- D-145 exact ten-marker conftest:
  `tests/conftest.py`, SHA-256
  `e92e9114ff874e71e8468320595489bc5d294653d6ff93b347cc3be27f9a01d9`,
  4,452 bytes / 110 lines
- D-145 sole comprehensive public audit:
  `tests/test_openadmet_global_v2_maplight_robustness_post_attempt_test_transition.py`,
  SHA-256 `2a58d9423aa99f6b441b9d173b9e2c9e263117ced46343e7e90acf90bad7eac3`,
  23,826 bytes / 603 lines
- D-145 focused/safe evidence:
  `2/2 passed`; bounded safe suite `1425 passed, 14 skipped, 0 failed` in
  341.76 seconds
- D-145 signed integrated commit / PR:
  `ce289b5fccaaf1d63343553961ad41309db19d04` / #182
- D-145 PR/post-main CI:
  `33125925508` / `33126546606`, both `success`

Before advancing PR #183, prove these exact stable values and that no pending
marker or stale progression instruction remains in the seven-file package.

## Exact official outcome

The private aggregate terminal is authoritative, but it remains private. The
public D-143 projection must establish only the following allowlisted facts:

- official driver invocations: exactly one;
- claim consumptions: exactly one;
- terminal status:
  `G2_7_MAPLIGHT_ROBUSTNESS_UNDERPOWERED`;
- process return code: integer zero;
- accounting complete: true;
- selected candidate: null;
- selection tokens: zero;
- runner-ups: zero;
- Stage A/B/C fits: all zero;
- Stage A/B/C predictions: all zero;
- tutorial and development metric calls: zero;
- official baseline rows opened: zero;
- official scoring-truth values opened: zero;
- official training-target values opened: zero;
- row-level values and model binaries retained: zero;
- confirmatory, historical-row, blinded-test, TDI, external, submission,
  official-metric, leaderboard-selection, portal, and upload counters: zero.

The allowed compiler-side source crossings after private claim consumption are:

- direct endpoint rows: 19,620;
- group-fold rows: 73,575;
- finite central point values: 5,197;
- feature-identity rows: 4,905;
- feature-matrix rows: 19,620;
- total feature rows: 24,525.

Those are real official preflight operations. Do not describe D-143 as
“zero official operations.” The receipt's all-false authority map denies future
capabilities; it does not erase the allowed reads already counted.

All frozen numeric minima passed across 240 support cells. The one failure has
exact reason `TAUTOMER_MERGED:confirmatory_touch_not_exercised`. The frozen
predicate requires confirmatory-touch exercise before fitting; the public
record intentionally omits observed support and exclusion values. This is a
label-free preflight mechanics failure and carries no endpoint or model-quality
meaning.

The cumulative supervisor evidence must retain exactly the accepted 13 fields:
wall seconds, CPU seconds, peak storage, peak simultaneous RSS, GPU hours,
checkpoints acknowledged, descendant processes observed, return code, cleanup,
network isolation, GPU-environment hiding, detached children, and warnings.
The successful underpowered boundary requires integer-zero return; positive
checkpoint and descendant counts; cleanup/network/GPU booleans true; zero GPU,
detached children, and warnings; and all four non-GPU resource values within
the frozen hard maxima.

The observed values are 33.09143570300148 wall-seconds,
33.194318974000005 CPU-seconds, 8,192 peak storage bytes, 289,660,928 peak
simultaneous RSS bytes, zero GPU-hours, three checkpoints, two descendants,
return code zero, cleanup/network/GPU booleans true, and zero detached children
or warnings. Seal attempts equal one and no fallback was used.

Cleanup must show the restricted work root, publication staging, and claim
staging absent. The fixed private attempt root is intentionally retained as
immutable evidence with exactly:

- `attempt_claim.json`
- `terminal`

The terminal contains exactly:

- `attempt_receipt.json`
- `manifest.json`
- `preflight.json`

Do not call that final two-entry attempt root a cleanup defect. No target,
feature, truth, baseline, model, prediction, scorer, CatBoost, or writable work
capability remains.

## Privacy and canonicalization boundary

Do not copy the private terminal files into Git. The public record may contain:

- exact public lineage hashes;
- hashes, sizes, and observed modes for the private aggregate claim/receipt/
  manifest/preflight evidence;
- the contracted aggregate accounting above;
- the exact bounded resource observation and limits;
- cleanup and terminal-shape evidence;
- a redacted support-stop summary; and
- denied future authority and scientific disposition.

It may not contain:

- an absolute or private path;
- a full support table or observed cell-support values;
- a molecule or row identity;
- a SMILES or structure;
- a target, interval, prediction, or residual;
- a component membership or feature matrix;
- a model binary or cache;
- a PID or unrestricted log;
- a portal identifier, score, rank, credential, or submission.

Parse with duplicate-key and nonfinite rejection. Canonical public bytes are
`json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
allow_nan=False) + "\\n"`. Atomic no-replace publication and observed
`0444` mode are local evidence; Git does not preserve owner-write bits, so
the portable identity is the canonical SHA-256.

The standalone test must read only public repository files. It must not import
or execute the official driver and must never resolve a private path. It should
bind the exact public record hash and live public lineage; strict schema/key
sets; canonical JSON; underpowered status/accounting/resource/cleanup shape;
null candidate, zero token/no runner-up/zero science; one-use prohibition;
privacy allowlist; and zero future authority.

## Scientific interpretation

UNDERPOWERED is a clean pre-science support stop. It is not:

- a completed 720- or 1,020-fit robustness battery;
- `G2_7_PRIMARY_CONTENDER_FROZEN`;
- a robustness pass for fixed MapLight;
- a selection or retention token;
- a scientific rejection of fixed MapLight;
- a model-quality improvement or degradation;
- authority to open confirmatory truth.

D-122's `full_is_default` and “retain full if no deletion qualifies” rule is
inside completed Stage-A candidate selection. That branch produces exactly one
selection token. The contracted underpowered branch occurs before every fit,
prediction, baseline open, selection token, and development metric and requires
`selected_candidate=null` plus zero selection tokens. Applying the
full-default clause after this outcome would be post-outcome reinterpretation.

The frozen confirmatory boundary opens only after an accepted G2-7 terminal
binds a selected contender. Even a legitimate full-selected terminal would
need a later contract resolving the identical-contender/control boundary.
That hypothetical clause creates no current contract or execution authority.
D-143 has no contender lock at all. Therefore G2-8 and G2-9 remain closed.

## Exact D-146 package

The coherent tracked package contains exactly seven files:

1. `benchmarks/openadmet_cyp_2026/README.md`;
2. `docs/phases/README.md`;
3. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
4. `docs/strategy/PROJECT_STATE.md`;
5. `docs/strategy/DECISIONS.md`;
6. `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`;
7. `runs/experiment_ledger.csv`.

Do not modify conftest, the D-145 audit, a historical test, contract, driver,
compiler, claim, D-143 record/audit, science file, private artifact, or barred
path. D-146 is knowledgebase/ledger closure only.

The ledger row must have exactly 18 columns and distinguish:

- D-144 and D-145 signed/green parent lineage;
- exact conftest/audit hashes, six prior plus four added markers for ten total,
  and one active comprehensive audit;
- focused `2/2` and bounded safe-suite `1425/14/0` evidence;
- unchanged historical tests and D-143 evidence; and
- zero official, claim, protected-data, development-robustness/official
  fit/prediction/metric, token, contender, science, model-quality, G2-8,
  confirmatory, submission, validator, leaderboard, portal, credential, upload,
  or downstream authority; routine public synthetic CI parity stays explicitly
  separate.

## Completed D-145 validator-hygiene evidence

The exact safe repository boundary, with the permanently barred
`tests/test_openadmet_global_v2_maplight_robustness_synthetic.py` explicitly
ignored, completed with `1425 passed, 14 skipped, 0 failed` in 341.76 seconds.
The D-144/D-145 focused pair passed `2/2`. D-145 preserves the six prior exact
markers, adds only the four frozen D-144 markers for ten total, keeps its sole
comprehensive audit and unrelated nodes active, and keeps every prior
replacement active except the exact transitioned D-141 supervisor node.

The public audit owns live collection/hash state while preserving every frozen
D-133/D-141/D-142 responsibility and the D-143 aggregate UNDERPOWERED
boundary. It imports no driver, opens no tracked claim, and probes no protected
root. Historical tests and D-143 evidence remain unchanged. This is
validator-hygiene evidence only; it does not select a contender, validate full
MapLight, alter model quality, or open G2-8. The terminal scientific stop is
unchanged.

## Continuation and restart handoff

The user explicitly canceled the prior 2026-08-27 21:00 ET pause gate at
20:04 ET. Continue the authorized D-146 review/integration objective without a
time-based stop. This cancellation changes only the workstation-availability
boundary: it grants no scientific, official, private-data, claim, G2-8,
confirmatory, submission, or upload authority.

Before yielding or handing off for any other reason, update this section or the
active task report with:

- exact branch and HEAD;
- exact D-146 seven-file package status and whether the worktree is clean;
- final D-145 conftest/audit hashes, focused count, and bounded safe-suite
  result;
- CSV 18-column/embedded-JSON and diff-check state;
- commit signature/identity if committed;
- branch push and PR number/check state if opened;
- main integration SHA and post-main CI run/conclusion if integrated; and
- heartbeat automation state and confirmation that it remains paused; and
- confirmation that no process is active and no protected capability opened.

If D-146 is unfinished when the user says `continue`, first authenticate Git
branch, HEAD, complete status/diff, the exact D-145 hashes and signed/CI
lineage, relevant processes, and current PR/CI state. Resume only the
unfinished seven-file D-146 review, signed integration, or exact-SHA
post-main-CI step. Do not modify D-145 behavior, a test, contract, record,
driver, claim, or science file.

If D-146 is integrated and post-main CI is green when the user says `continue`,
audit and report the terminal scientific stop. Do not infer G2-8,
full-MapLight retention, confirmatory, submission, or private-data authority.
New science requires explicit prospective user direction and a genuinely new
hypothesis; it cannot be a retry, repair, replacement, support relaxation, or
reinterpretation of G2-7G.

Across every resume case: no retry or claim derivation; no official/private root
listing, opening, hashing, copying, or mutation; no barred-file access; no
confirmatory, historical-row, blinded-test, TDI, submission, validator,
leaderboard, portal, credential, or upload capability. Do not reactivate the
heartbeat automation unless the user explicitly asks.

Restart snapshot captured after the 2026-08-27 pause cancellation:

- branch: `codex/g2-7g-post-attempt-transition-evidence`;
- base: signed D-145 main commit
  `ce289b5fccaaf1d63343553961ad41309db19d04`;
- D-144 review/CI: signed commit
  `5d7ed5db76ec0928ba34e19e72ab839ee556d51e`, PR #181 CI `33123874692`,
  and exact-SHA post-main CI `33124525495` succeeded;
- D-145 review/CI: PR #182 CI `33125925508` and exact-SHA post-main CI
  `33126546606` succeeded for the signed D-145 commit;
- D-146 branch/PR: the seven-file signed closure is pushed on
  `codex/g2-7g-post-attempt-transition-evidence` in PR #183; authenticate the
  exact signed head after this user-directed handoff update and require all
  three CI lanes before local fast-forward-only integration;
- active official/composite driver processes: none;
- long-running test, build, shell, or monitor processes: none observed at
  snapshot capture;
- heartbeat automation `monitor-official-trace-recovery`: `PAUSED` as of
  2026-08-27 18:00 EDT; its native update hung without mutation, after which
  only the exact local automation status field was changed from `ACTIVE` to
  `PAUSED` and verified; do not reactivate it on `continue` without explicit
  user direction;
- protected or barred access during packaging: none.

## Exact next action

1. Authenticate PR #183's current exact SSH-signed head against the D-145 base,
   seven-file scope, ledger integrity, hashes, and terminal authority boundary.
   Treat any superseded pre-amend CI run as non-authoritative.
2. Require all three replacement PR CI lanes to pass on that exact head.
3. Recheck that PR #183 is open, non-draft, mergeable and clean; that its head
   is one signed `zchboswell` commit over D-145; and that the local branch,
   index, and worktree are synchronized and clean.
4. Integrate the reviewed signed commit locally with fast-forward only; do not
   use GitHub's hosted rebase merge. Push `main` without rewriting the commit.
5. Require green push-event post-main CI on the exact integrated SHA and confirm
   that PR #183's merge OID equals its signed head.
6. Report the frozen scientific stop and request user direction only for a
   genuinely new prospective plan.

Never continue into G2-8. After step 5, stop the active scientific path: the
frozen one-use gate ended underpowered and the frozen plan contains no
authorized scientific fallback.

## Closed operations

- Do not invoke the official driver, formal acceptance, or any replacement
  gate again.
- Do not create or derive another claim.
- Do not open, list, hash, copy, or modify private official roots or their
  contents.
- Do not open confirmatory truth, historical row-level evidence, blinded test,
  or TDI data.
- Do not fit a model, generate a prediction, evaluate a development or official
  metric, run the validator, or generate a submission.
- Do not use leaderboard or portal evidence for selection.
- Do not expose a private identifier, score, rank, path, or row value.
- Do not add a candidate, feature, seed, group, threshold, calibration, blend,
  retry, cache, concurrency change, framework, or service.
- Do not live-upload.
- Do not reactivate `monitor-official-trace-recovery` without explicit user
  direction. Do not abandon an unowned long-running process when yielding for
  any other reason.

Any future lane requires separate explicit user authorization and a materially
new prospective hypothesis, contract, claim, and root. It cannot repair,
replace, reinterpret, or relax G2-7G, and it cannot use the observed support
stop to tune a candidate. EXP-G3, G1/G2/M1/X1/T2, D-127/D-128, and immutable
R5D/I0 remain closed; `global_TDI` remains only the frozen TDI fallback.

# Next orchestrator kickoff — integrate D-148, then implement D-149 without execution

The current objective remains the smallest scientifically defensible path to a
competitive OpenADMET CYP 2026 submission. Frozen challenge-family-held-out
validation outranks leaderboard evidence. Global-v2 is closed: G2-7G is
permanently UNDERPOWERED before science, selected no candidate or runner-up,
and opens no G2-8 or submission authority.

The genuinely distinct Global-v3 `EXP-G4-GIN300` scientific contract is
integrated as signed D-147 commit
`b5cf47c6bc8ccc2dc29c7167b1a436d792338509`; PR #184 CI run `33327853790`
and exact-SHA post-main CI run `33328374514` are green. D-148 now freezes only
its Linux x86_64 rights, provenance, CPU-runtime, tensor/graph/parity,
label-free synthetic-capability, prefit-resource, one-use supervision, cleanup,
and terminal-publication contract. No time-based pause gate is active.

## Restore authoritative context first

Read completely, in order:

1. `AGENTS.md`;
2. `docs/strategy/PROJECT_STATE.md`;
3. `docs/phases/README.md`;
4. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
5. `docs/strategy/PROJECT_CHARTER.md`;
6. D-147 and D-148 in `docs/strategy/DECISIONS.md`;
7. the final relevant rows of `runs/experiment_ledger.csv`;
8. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_contract.json`;
9. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_capability_contract.json`;
10. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_linux_x86_64_runtime_manifest.json`;
11. `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_third_party_notices.md`;
12. `tests/test_openadmet_global_v3_g4_gin300_capability_contract.py`.

Treat signed Git history, canonical tracked bytes, public source receipts, and
green exact-SHA checks as authority. Do not open a protected path to refresh
context. Never inspect, import, copy, execute, patch, or derive code from a
barred runner or driver. D-127/D-128 and every closed G2-7 path remain barred.

## Exact D-148 package

The current status is
`G3_2_EXP_G4_GIN300_CAPABILITY_CONTRACT_FROZEN`.

- Capability contract:
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_capability_contract.json`,
  SHA-256
  `df8796575c3d6093dd4038f4268417a979b8edca14245a7acff26e3db18eaa44`,
  184,100 bytes / 1,687 lines.
- CPU-runtime manifest:
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_linux_x86_64_runtime_manifest.json`,
  SHA-256
  `67b58fc5eb9d1d3c0652bad9fa85eb1e688ed4bfb93d9ee107cad4db3e0ace01`,
  166,425 bytes / 4,008 lines.
- Third-party notices:
  `benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_third_party_notices.md`,
  SHA-256
  `b76b026a7ed61c0c33cc9f78d66ca235e01e9d2c504126238e0f6e0f58e18deb`,
  12,456 bytes / 241 lines.
- Strict public static audit:
  `tests/test_openadmet_global_v3_g4_gin300_capability_contract.py`, SHA-256
  `d9318267ff607703b9d957fc2fa13b79af61740b486471ab0556c06f3205bb12`,
  97,426 bytes / 2,509 lines, focused result `15/15 passed`.

Recompute these identities from the exact worktree; do not trust prose alone.
Parse both JSON contracts and the runtime manifest with duplicate-key and
nonfinite rejection, require their exact two-space-indented UTF-8 canonical
serialization plus terminal LF, and run the strict focused audit plus the
bounded public repository checks authorized by the current workflow. None of
those checks may fetch an artifact, create the runtime, or execute scientific
code.

The exact bounded safe-suite command
`PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v uv run --locked pytest -p no:cacheprovider --ignore=tests/test_openadmet_global_v2_maplight_robustness_synthetic.py`
completed with `1449 passed, 14 skipped, 0 failed` in 349.72 pytest seconds /
350.21 wall-seconds at 903,624 kB maximum RSS and exit status zero. Ruff over
325 allowed Python files with the exact barred G2-7B runner/driver/test
excluded, format and temporary compilation of the D-148 audit, mypy over 78
source files, offline isolated build, and a fresh Python 3.12.3 installed-wheel
two-root audit/train/predict/report replay are green. The two roots are
byte-identical at 9 files / 36,758 bytes each. The 11 package hashes and Git
status remained identical; incidental build and tree hashes are not frozen.

## Frozen capability and runtime oracle

The runtime manifest binds install-only CPython 3.10.13 and exactly 96 CPU
wheels, 185 dependency edges, 539,395,366 wheel bytes, and 97 distribution
artifacts totaling 566,804,656 bytes. It includes the complete
`molfeat[dgl,transformer]` closure and no CUDA, NCCL, or Triton. The one
post-cutoff package-wheel exception is `future==1.0.0`; the frozen 20240224
interpreter is separately disclosed infrastructure. A future successful fetch
authenticates 98 runtime network files including the checksum sidecar
(566,804,721 bytes), three model/checkpoint objects (22,374,079 bytes), one
606-byte MolFeat metadata object, and exactly two redirects.

The parity oracle uses three isolated CPU processes on the same fixed eight-row
redistributable fixture. The SNAP conversion, native DGL loader, and MolFeat
public local-store path must all yield the direct bare
`dgllife.model.gnn.gin.GIN` with exactly 57 unprefixed state keys and no head,
readout, wrapper, prefix, or extra. Tensor and graph manifests must match
exactly. The 8x300 embeddings must either match byte-for-byte or enter only the
predeclared `max_abs <= 1e-7`, `rtol=0` branch and then produce 48 exact
fallback predictions from the two candidate models.

The resource oracle includes two uncached 3,908-row GIN passes, an
official-shaped 3,908-molecule / 3,640-component synthetic topology, 180
model-double fits and 140,688 predictions per root, six real CatBoost fits with
4,692 validation predictions, and 20% projected wall, CPU, storage, and
simultaneous-RSS margin. GPU visibility and use are zero.

## D-148 authority and evidence accounting

D-148 is contract and public evidence only. It created no runtime, wheel cache,
private object root, claim, or result. It downloaded no wheel,
interpreter-archive, checkpoint, model, transformer, or tokenizer artifact
body; deserialized or executed no checkpoint; imported or ran no scientific
stack; performed no parity, GIN, CatBoost, feature, fit, prediction, or
resource-probe operation; and opened no official/private scientific input.

The public audit recorded six checkpoint/model HEAD requests with zero body
bytes; one 606-byte MolFeat metadata GET plus one HEAD; two interpreter
archive/sidecar HEAD requests with zero body on those HEADs; 95 distinct PyPI
release-JSON resources; nine distinct SPDX JSON resources; the PyTorch CPU
simple-index resource; one 65-byte checksum-sidecar GET; and one 1,495-byte
build-project-license GET. Raw retries, total public metadata transactions, and
aggregate metadata bytes were not instrumented and must remain unknown rather
than inferred.

## Exact D-149 scope: code and static validation only

D-149 may change exactly 14 paths:

1. `research/maplight-gin-openadmet/.python-version`;
2. `research/maplight-gin-openadmet/pyproject.toml`;
3. `research/maplight-gin-openadmet/uv.lock`;
4. `research/maplight-gin-openadmet/build_global_v3_g4_gin300_capability.py`;
5. `research/maplight-gin-openadmet/run_global_v3_g4_gin300_capability.py`;
6. `tests/test_openadmet_global_v3_g4_gin300_capability.py`;
7. `tests/test_openadmet_global_v3_g4_gin300_capability_result.py`;
8. `benchmarks/openadmet_cyp_2026/README.md`;
9. `docs/phases/README.md`;
10. `docs/phases/PHASE_2_OPENADMET_GLOBAL_V2.md`;
11. `docs/strategy/PROJECT_STATE.md`;
12. `docs/strategy/DECISIONS.md`;
13. `docs/strategy/NEXT_ORCHESTRATOR_PROMPT.md`;
14. `runs/experiment_ledger.csv`.

The root `pyproject.toml` and `uv.lock` remain unchanged. The isolated lock is a
Linux-targeted evidence mirror of the manifest, not install authority or a
universal-resolution claim. D-149 must freeze/test one explicit implementation
of every delegated bounded internal choice, including the public DGL/MolFeat
call sequence, bounded control-frame enum, descendant stdio routing, and exact
result dual-state validator. It must remain deterministic and fail closed.

D-149 must perform zero artifact body fetch, runtime creation or install,
private-root creation, scientific import, checkpoint load or deserialization,
tensor/graph/embedding operation, parity process, scaled GIN pass, synthetic
construction, CatBoost fit or prediction, claim construction or consumption,
result publication, official/private read, or GPU operation. Do not run the
formal launcher while creating or reviewing D-149. The public result must stay
absent and untracked.

## Future D-150 boundary — not current authority

Only after D-149 is independently reviewed, SSH-signed, integrated locally by
fast-forward only, pushed without rewriting, and green on exact-SHA post-main
CI may D-150 perform one formal invocation. D-150 changes exactly the aggregate
result, these six narrative surfaces, and the ledger; it does not change the
runner, builder, lock, or tests.

The frozen launcher is direct system Python with an empty operator environment,
no arguments, and no root-environment sync. The outer authenticates lineage,
tools, roots, and result absence before spawn. A child reaches the acknowledged
ready checkpoint and then atomically consumes and permanently tombstones the
sole claim before any private-root creation or network operation. Fetch is
sequential, exact, bounded, and nonresumable. Every checkpoint deserialize,
tensor/graph/embedding operation, and CatBoost worker runs offline inside the
frozen CPU-only sandbox. The child emits only a bounded aggregate payload. The
outer authoritatively cleans and verifies all mutable roots while retaining
only the contract-authorized runtime and SNAP object on a proposed success;
only then may common seal publish one no-replace canonical aggregate terminal.
No retry, resume, replacement claim, alternate artifact, or post-publication
cleanup exists.

A clean result `G3_3_EXP_G4_GIN300_CAPABILITY_ACCEPTED` is engineering
capability evidence only. It is not scientific `ACCEPTED`, model-quality
evidence, official access, feature generation authority, development authority,
or a selection token. Rights/object/tensor/graph/parity/nonredistribution defects
map exactly to
`G3_G4_GIN300_INELIGIBLE_PRETRAINED_PROVENANCE_OR_PARITY_FAILED`; a complete
prefit resource-margin miss maps to
`G3_G4_GIN300_RESOURCE_INFEASIBLE_PREFIT`; malformed, operational,
incomplete-integrity, hard-ceiling, or supervision failures map to
`G3_G4_GIN300_FAILED`. `G3_G4_GIN300_RESOURCE_ABORTED` remains reserved for a
later claim-bound official feature/development attempt and cannot be emitted by
D-148, D-149, or D-150.

## Exact next action

1. Authenticate the D-148 package and all four core identities against signed
   D-147 commit `b5cf47c6bc8ccc2dc29c7167b1a436d792338509`.
2. Require the final focused D-148 public audit, canonical JSON checks,
   narrative/ledger consistency, Ruff/format/compile checks, and diff check to
   pass without artifact fetch or scientific execution.
3. Create one coherent SSH-signed `zchboswell` D-148 commit with no AI
   attribution. Push it, open a pull request, and require all checks on the
   exact signed head.
4. Recheck mergeability and integrate locally with fast-forward only. Do not
   use GitHub's hosted rebase merge. Push `main` without rewriting the commit
   and require green exact-SHA post-main CI.
5. Only then create D-149's exact 14-path implementation/static-test package.
   Do not invoke it, fetch any frozen body, create any private runtime/root, or
   consume the formal attempt.
6. Review, sign, integrate, and require exact-SHA-green D-149 before considering
   the separate D-150 formal invocation. D-150 is not authorized from an
   unreviewed D-149 branch.

Throughout D-148 and D-149, do not access official structures or targets,
baseline OOF rows, confirmatory truth, historical row-level artifacts, blinded
test, TDI, submission generation, validator, official metric, leaderboard,
private portal, credentials, or upload capabilities. Do not call full MapLight
retained, promote a runner-up, relax the failed G2-7G support outcome, or use it
to tune this lane. D-127/D-128, EXP-G3, G1/G2/M1/X1/T2, TRACE, R5D, and I0
remain closed; `global_TDI` remains only the frozen TDI fallback.

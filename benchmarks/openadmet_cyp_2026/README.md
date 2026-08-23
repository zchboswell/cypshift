# OpenADMET CYP 2026 — TRACE contract receipts

This directory is the tracked launch receipt for the 2026-08-17 OpenADMET CYP
release: immutable revisions and metadata only; no challenge CSV, prediction,
model cache, or upstream source tree is copied here.

The official training-only TRACE oracle is complete with authenticated
`R5_ORACLE_NO_SIGNAL`; see
[`TRACE_OFFICIAL_OUTCOME.md`](TRACE_OFFICIAL_OUTCOME.md) for the immutable
receipt chain, negative scientific result, and deployment stop. The exact
competition-validated direct MapLight upload is documented separately in
[`DIRECT_BASELINE_HANDOFF.md`](DIRECT_BASELINE_HANDOFF.md). No prediction CSV is
tracked in Git.

The pinned read-only source clones were verified at:

- dataset `85f8b358d0a2056a98b990dd75d3b3ec9247862b` (Apache-2.0); tutorial
  `9d4925eb4a0fb914256da1b27d110593bcbe3cf0` (Apache-2.0); Space
  `13c5057b37d1e72b3f036dd0d59718b1823f8fdd` (license unresolved).

[`source_receipts.json`](source_receipts.json) has exact sizes, SHA-256, rows,
headers, and TDI order discrepancy; [`challenge_contract.json`](challenge_contract.json)
has the R0 gate, endpoint states, validation, claims, and V6/P6 items; see
[`submission_contract.json`](submission_contract.json) for required columns.
[`validation_contract.json`](validation_contract.json) freezes the corrected R2 v4
label-aware topology-viability, campaign-episode, firewall, and fold contract.
V3 was rejected before R2B after a post-merge Sol audit found incomplete
episode policy/hash output, incomplete public query-field typing, and an
incomplete topology-viability schema/acceptance contract; zero R2B artifacts
were created. PR89's claimed independent audit is separately recorded as
unsupported because its assigned read-only auditor self-integrated; that
governance breach does not invalidate valid R2A evidence. It is not
`VALIDATION_FROZEN`. R2A emits direct observations and component folds. R2B now
emits the three episode projections, restricted anchor masks, and recomputed
topology viability under v4. Fold, episode, episode-label, and viability
artifact authority is accepted; models, validation, metrics, submissions, TDI,
predictions, and transductive use remain unauthorized.
[`global_experiment_contract.json`](global_experiment_contract.json) now freezes
the corrected R3 v3 global-only direct fallback: endpoint median, Morgan 1-NN, Morgan
CatBoost, and fixed MapLight under `GLOBAL_FAMILY_HOLDOUT` with provisional
component-macro MAE only. It explicitly separates the mandatory global fallback
from later oracle/transformation work. The Linux MapLight overlay is mandatory;
failure stops R3 before scientific fitting. R3A permits only fixture parity and
two label-free feature roots, R3B is synthetic runner/firewall acceptance, and
R3C alone may run the frozen experiment. V1 was rejected before execution for
five mechanical blockers after its assigned read-only auditor improperly
pushed it directly to main; v2 preserves that history and corrects the boundary.
V2 was then rejected before R3A because it did not authorize any source from
which the direct-only raw-SMILES population could truthfully be projected. V3
adds one receipt-bound chemistry prefix process that parses or retains zero
target values and opens no blinded-test artifact; the feature process sees only
its 4,905-row label-free CSV and manifest. The projector also verifies the
train-only topology receipt and frozen standardization: exact raw SMILES feed
MapLight, while standardized SMILES feed D-032 Morgan.
R3 still grants no official metric, TDI, submission, or transductive authority.

[`global_experiment_contract_v4.json`](global_experiment_contract_v4.json) is
the additive R3B implementation contract; v3 remains immutable because accepted
R3A manifests bind its bytes. V4 removes evaluation-driven candidate selection
by fixing MapLight before target access, keeps Morgan/median/1-NN as controls,
splits model-public targets from scorer-sealed truth, and freezes preflight,
cell, freezer, scoring, terminal-publication, and authority schemas. Both final
independent audits pass.

[`global_experiment_contract_v5.json`](global_experiment_contract_v5.json)
supersedes only v4's implementation mechanics. It repairs target-file
cardinality, truthful preflight accounting, accounting-schema completeness,
artifact/source binding, and freezer parameter receipts. It preserves v4's
scientific choices and remains synthetic-only; no target, model, prediction,
metric, or validation authority is granted.

The complete v5 runner has now passed its synthetic gate. Two fresh roots ran
all 60 outer and 240 inner contexts in separate processes, totaling 600 cell
processes and 720 real CatBoost fits. Both reached `GLOBAL_EXPERT_FROZEN` with
deterministic artifacts, and independent adversarial review passed. This
accepts implementation mechanics only; R3C remains the sole authority for one
frozen official global experiment and no submission authority is granted.

The single frozen official R3C experiment subsequently reached
`GLOBAL_EXPERT_FROZEN`. Fixed MapLight beat Morgan CatBoost, the endpoint
median, and Morgan 1-NN by 0.0646, 0.1411, and 0.4389 component-macro MAE,
respectively; all three 2,000-replicate bootstrap intervals have positive lower
bounds. The exact outside-Git terminal manifest and result SHA-256 are
`a2029e12231a22415900c55303ec5413b395aedc15d565ef7b4e650196b3277c` and
`d9aff555db3c985ca834a11f5d1f198a9c8c5bafcaced6e7719a88bab09c2f94`.
This is internal surrogate evidence only: official ST-RAE, a deployable model,
submission, TDI, anchors, transformations, and transduction remain outside its
authority.

[`transformation_coverage_contract_v5.json`](transformation_coverage_contract_v5.json)
plus the exact additive
[`transformation_coverage_contract_v6.json`](transformation_coverage_contract_v6.json)
clarification are the implementation authority for R4 before any transformation
fit or score.
Its SHA-256 is
`63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954`
and its extraction-spec receipt is
`59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950`.
It preserves the v1 (`d4c999e6...`), v2 (`a13adee5...`), v3
(`f5e18626...`), and v4 (`cacd1f77...`) contracts as
immutable history. V2 repaired the unreachable double-cut path and pair-
specific exact IDs; v3 closes the remaining stereo-discovery, CIP,
automorphism, implicit-hydrogen, atom-map, and directed-bond ambiguity. V4
resolves the narrow reference-H, embedding-cap, graph-first unsupported-stereo,
bond-stereo reconstruction, query-rank, and publication mechanics found during
synthetic implementation. V5 leaves the extraction receipt unchanged and
repairs only the zero-valid distribution, pre-input runtime/checkout refusal,
and canonical histogram serialization versus exact rational arithmetic.
The contract binds the accepted R2/R3 receipts, parses only direct availability
state, uses public episode membership plus the mask anchor prefix, and keeps
campaign truth, selectors, query availability, target magnitudes, blinded test,
TDI, predictions, and metrics closed. It specifies deterministic RDKit
single/double-cut extraction, ambiguity and invariance policy, structural-only
outputs, and valid-only CYP3A4/local and selected-episode structural support.
Supported coverage may authorize a separate oracle contract only; R4 itself
authorizes no fit. Forty-three focused v1-v5 contract tests pass with
independent scientific review.

[`oracle_experiment_contract_v1.json`](oracle_experiment_contract_v1.json) is
the independently accepted R5 CYP3A4 oracle contract. Its SHA-256 is
`c1d7a66c4f479339b30c2006e4250381cb213d665d4902c71d4c4edbd347e8bf`.
It freezes the selected-anchor CYP3A4 population, episode-specific inherited
MapLight baseline, generic signed-Morgan ridge, compact MMP hierarchy, all
required anchor/grammar falsifications and ablations, nested component
cross-fitting, label-safe prediction superset, separate all-row safety
bootstrap, status-specific terminals, and hard stopping logic. Independent Sol
review passes after closing measured-anchor leakage in the no-potency control,
inner-support impossibility, selector membership leakage, cross-fit scope,
fallback-only control ambiguity, and runtime/schema gaps. R5 remains contract
only: no numeric target, fit, prediction, internal score, test, TDI, official
metric, or submission is authorized until implementation passes its separate
synthetic gate.

[`oracle_experiment_contract_v2.json`](oracle_experiment_contract_v2.json) is
the additive effective R5 contract at SHA-256
`bfa00b7f1e9ec8ed8d450b5499011e165b50bbf633b897d24177aee6066ea623`.
It adds exactly one absent member: selected-anchor episodes alone may enter
inner selection, while deterministic-random-anchor stress is outer-diagnostic
only and cannot tune, select, rescue, or change status. The trusted synthetic
source compiler and manifest-bound splitter now implement that boundary and
publish 226 disjoint capability roots. Compiler-to-splitter replay, 68 focused
tests, the full suite, typing, and independent adversarial review pass. This
grants synthetic firewall evidence only; official targets, fits, predictions,
metrics, and TRACE performance remain unopened.

The synthetic least-privilege projection implementation is accepted for its
boundary only. It verifies five source receipts before parse, retains exactly
the permitted direct and mask-prefix fields, validates the complete fold and
episode joins, and atomically publishes six canonical read-only files. Its I/O
and projector source SHA-256 values are `820a83b3...` and `0e094712...`;
thirty-seven focused tests plus independent correctness and minimality reviews
pass. No official input was opened. Production use remains blocked until a
separate gate binds R4 v5, the accepted R2B/R3A manifests and leaf receipts,
and the exact implementation sources.

The pure v4 transformation-pair extractor is also synthetically accepted. It
implements joint single/double-cut MMPs, virtual-H changes, exact stereo-only
changes, full bond-stereo reconstruction, reusable and directional IDs,
ambiguity sentinels, and reversal/atom-order invariance without I/O or label
capability. Independent review found and closed E/Z reconstruction loss and
over-broad unsupported-stereo C3 precedence before acceptance. Sixty-nine
focused contract/extractor tests and the full 490-test suite pass with three
expected skips. This grants no coverage, support, model, metric, or official-
input authority; production binding and the coverage compiler/publisher remain
the next gate.

The v5 projection consumer is synthetically accepted as a separate bounded
slice. It hashes all six projected files before parse, replays exact manifests,
receipts, standardization, direct/fold/public/mask joins, and emits immutable
label-safe records. Eleven focused and 48 combined projection/consumer tests
plus independent adversarial review pass. Production source identities and
official cardinalities remain deferred; the next slice is structural-union and
support arithmetic, not official execution.

The synthetic structural-geometry compiler now also passes independent
adversarial review. It forms the exact local-plus-episode union, invokes the
accepted extractor once per unique structural pair, preserves canonical and
episode direction, and emits the frozen 47-column pair CSV bytes. Fifty-three
focused tests, Ruff, and strict mypy pass. This slice has no endpoint-support,
status, production, official-input, model, prediction, metric, or publication
authority; exact coverage serialization remains the next bounded block.

The additive v6 clarification at `a0743c43...` binds the valid changed-fraction
distribution to unique union structural-pair rows and requires its count to
equal `counts.union.valid_rows`. It is a two-member exact overlay on the pinned
v5 parent, changes no science or authority, and passes independent review.

The pure synthetic support compiler at `9d08b5c0...` now passes independent
adversarial review. It implements complete-state endpoint partitions, exact
15-cell held-out counts, valid-only local/selected gates, component-deduplicated
exact/class and cross-CYP support, held-out episode training support, and exact
rational distributions. It carries no serialization, production, official-
input, oracle, model, prediction, metric, or publication authority.

The July 29 announcement and August 17 launch post are official prose receipts
(URL, DOI, retrieval digest, CC BY 4.0 footer). They confirm two tracks, 750
compounds, live-half/full-final leaderboard, external/pretrained use with
proprietary disclosure, and TDI label caution; they do not replace executable
metric/validator evidence.

R0 leaves exact live ST-RAE implementation, denominator, masks, interval bounds,
TDI derivation, backend parity, and transductive permission unresolved. No
metric-specific optimization or leaderboard iteration is authorized. R2 keeps
the direct compiler restricted to `TRAIN_inhibition`, preserves all four
measurement states, and keeps TDI labels and the blinded test outside the
direct validation chain. The checker is
read-only and does not download sources or write artifacts. With the three
read-only clones and two HTML files fetched outside Git, run:

```console
uv run python scripts/check_openadmet_cyp_contract.py \
  --dataset-root /path/to/dataset \
  --tutorial-root /path/to/tutorial \
  --space-root /path/to/space \
  --announcement-html /tmp/announcement.html \
  --launch-post-html /tmp/launch_post.html
```

Exit 0 means all receipt and internal-contract checks pass; exit 1 means
source, prose, schema, row-count, or hash drift; malformed invocation or
tracked contract JSON exits 2.

After accepted R1 and topology outputs exist outside Git, build the R2A slice
into another untracked directory with:

```console
uv run python scripts/build_openadmet_validation_inputs.py \
  --validation-contract benchmarks/openadmet_cyp_2026/validation_contract.json \
  --direct-source /path/to/cyp-challenge-TRAIN_inhibition.csv \
  --r1-directory /path/to/r1-output \
  --topology-directory /path/to/topology-output \
  --output-directory /path/to/r2a-output \
  --source-revision 85f8b358d0a2056a98b990dd75d3b3ec9247862b
```

The command opens only the direct-training CSV and receipt-bound R1/topology
artifacts. It does not create episodes, decide endpoint viability, fit or score
a model, read TDI or blinded test data, or authorize its fold records as a
validated split. R2B consumes only these receipt-bound outputs.

Build the accepted R2B slice from that directory with:

```console
uv run python scripts/build_openadmet_campaign_artifacts.py \
  --validation-contract benchmarks/openadmet_cyp_2026/validation_contract.json \
  --r2a-directory /path/to/r2a-output \
  --output-directory /path/to/r2b-output \
  --source-revision 85f8b358d0a2056a98b990dd75d3b3ec9247862b
```

V4 freezes the R2B semantic episode CSV types, lowercase SHA256 episode
and component IDs, selected/stress policy tokens, unique-ID and join counts, and
the exact receipt-bound `topology_viability.v1` schema. Its topology artifact
must contain all four endpoint global counts and fifteen sorted fold-support
cells per endpoint, with no predictions, learned/fitted weights, metrics, TDI,
blinded-test, or transductive content. Root review and independent replay now
accept the implementation. Two official R2B builds were
byte-identical for all seven files. The accepted manifest is `08dcf61c...`;
public/truth/mask hashes are `47180477...`, `f2ec3ca6...`, and `0b437aa5...`,
and topology viability is `6c4e66ec...`. Independent scientific/code review
passed.

Released TDI labels conflict with launch prose. Among non-null labels, all
arm-missing rows are `False` (CYP2D6: 4; CYP3A4: 1,250), including 1,055
CYP3A4 rows lacking direct pIC50 but having TDI pIC50 at least 4.301. Preserve
this M2/M6/P6 conflict as unresolved label origin/derivation; do not
extrapolate the observed relation to hidden labels.

Status values: `verified`, `organizer_confirmed`, `provisional`, `unresolved`,
and `not_applicable`.

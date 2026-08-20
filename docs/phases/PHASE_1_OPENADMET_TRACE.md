# Phase 1 — OpenADMET TRACE

Status: active; official transformation coverage supported; gate
`R4_TRANSFORMATION_COVERAGE_SUPPORTED`; date 2026-08-20.

## Context capsule

Active hypothesis: a series-first, competence-aware predictor can improve
blind-like analog-family performance over a strong global comparator when parent
evidence, assay state, intervals, and family boundaries remain auditable. Hypothesis only.

Frozen identifiers are recorded in [`source_receipts.json`](../../benchmarks/openadmet_cyp_2026/source_receipts.json):

- dataset `85f8b358d0a2056a98b990dd75d3b3ec9247862b`; tutorial `9d4925eb4a0fb914256da1b27d110593bcbe3cf0`; Space `13c5057b37d1e72b3f036dd0d59718b1823f8fdd`.

The public test has 750 compounds. Direct requires `SMILES`, `Molecule_Name`,
and four direct pIC50 values. TDI requires those identifiers plus
`CYP2D6_is_TDI` and `CYP3A4_is_TDI`; official source order disagrees. Direct is
continuous and TDI is binary. Preserve raw structures, available bounds,
standard deviations, and missingness. Raw curves, censor qualifiers, per-row
assay/probe state, QC, and label origin are not released and must not be
invented.

## Validation protocols

1. **GLOBAL_FAMILY_HOLDOUT:** evaluate global direct and TDI baselines with no
   molecule, duplicate, or reconstructed family crossing a boundary.
2. **ANCHOR_EXPANSION_HOLDOUT:** expose exactly one measured anchor in a held-
   out family; exclude every other family member from global labels, delta
   support, and candidate pools. All learned choices remain cross-fitted.

For R2 these protocol names use the unchanged D-032 similarity components as a
conservative reconstructed-family proxy. D-034 grants only grouping, fold, and
episode authority; it does not establish semantic lineage, mechanism, or
complete analog-family recovery.

`TDI-TRACE` is deferred/optional after `direct_TRACE` and `global_TDI` are frozen;
`global_TDI` remains the permanent fallback.

Direct endpoint outcomes are `LOCAL_SUPPORTED`, `LOCAL_FAILED`, or
`LOCAL_UNDERPOWERED`; local fusion weight is zero for the latter two.
`ORACLE_SIGNAL_PASS` is evidence that true-anchor structural reasoning works,
not permission to claim `DEPLOYMENT_PASS` for inferred anchors.

## Endpoint-state semantics

- Direct inhibition is direct-arm pIC50 for CYP1A2/2C9/2D6/3A4; rows carry
  fitted bounds and/or standard deviations. Do not collapse bounds or missing
  values into guessed points.
- TDI is an operational +NADPH versus -NADPH IC50-shift state, not proof of
  irreversible inhibition. The public two-fold/inferred rule is unresolved:
  among non-null labels, all arm-missing rows are `False` (CYP2D6: 4;
  CYP3A4: 1,250), including 1,055 direct-missing rows with TDI pIC50 at least
  4.301. Preserve the M2/M6/P6 conflict and do not derive hidden labels.
- Public prose names MA-ST-RAE and MCC; implementation, denominator, masks,
  bounds, and backend parity remain unresolved (`V6`).

## Paths and gates

Accepted: source receipts, submission names/types, launch prose, raw-state
preservation, family-safe intent, and global TDI fallback.

Killed: guessed schema/metric/rules; public-test optimization; interval/state
collapse; TDI proxy labels; copying official raw data/source code.

Blocked: exact metrics, masks/denominators, backend parity, validator identity/
order, family assignment, and transductive permission (`V6/P6`).

Targeted failure: a stale/contradictory contract causes metric mismatch, family
leakage, or unsupported claims (`V2`, `V6`, `P6`).

Acceptance: receipts verify; source names/types and order discrepancies are
recorded; unresolved items are named; no raw source is tracked; the checker
fails closed and any later adapter must do the same.

Gate evidence: `scripts/check_openadmet_cyp_contract.py` passes the current
official roots and freshly fetched launch HTML, while focused synthetic tests
cover exact pass, hash, CSV header/row, revision, prose, and submission
contract drift. The canonical source-row adapter additionally validates all
five CSV receipts before writing deterministic molecule and row artifacts;
focused synthetic tests cover byte determinism, missing strings, repeated
rows, output refusal, receipt drift, exact-SMILES conflicts, and test/training
name overlap. Its official-source acceptance run preserved all 35,450 rows and
6,897 unique molecule names, and a repeated run produced byte-identical outputs.

The label-free topology audit verifies both R1 output receipts without parsing
`source_rows.csv`, audits every molecule with the existing chemistry path, and
computes candidate training connected components from inclusive Morgan/Tanimoto
0.60 edges plus separate Bemis-Murcko groups. Test chemistry is excluded from
all topology construction. Synthetic repeat, drift, quarantine, overlap,
partition, duplicate, transitivity, and test-exclusion checks pass. This is a
candidate topology diagnostic, not a family assignment or validation split.
The official run audited all 6,897 molecules with zero quarantine and zero
standardized train/test overlap. Its 6,147 training molecules form 5,232
candidate similarity components; 1,241 molecules occur in multi-member
components, the largest has 21 members, and 146 components contain at least two
direct-training source identities. A repeated run was byte-identical.

Kill: source digest/revision mismatch, unresolvable schema disagreement,
interval/state loss, family leakage, or metric-specific optimization. Preserve a
blocker receipt and do not model.

The corrected R2 v4 label-aware topology-viability and campaign-episode contract is frozen in
[`validation_contract.json`](../../benchmarks/openadmet_cyp_2026/validation_contract.json).
It keeps D-032 topology bytes unchanged while using its components only as the
declared reconstructed-family proxy; restricts direct compilation to the four
direct endpoints; requires complete observations for anchors and local pairs;
freezes selector/query rules, separate oracle-runner and scorer projections,
anchor exposure, exact-column/value firewall privilege separation, deterministic
episode IDs, threefold episode expansion, component-grouped repeats and inner
folds, scorecard slices, and strict activity-cliff disjointness. A post-merge
Sol audit rejected v3 before R2B for incomplete episode policy/hash output,
incomplete public query-field typing, and an incomplete topology-viability
schema/acceptance contract; zero R2B artifacts were created. PR89's claimed
independent audit is separately recorded as unsupported because its assigned
read-only auditor self-integrated; that governance breach does not invalidate
the valid R2A evidence or independent R2A review. Insufficient evidence is
`LOCAL_UNDERPOWERED`, never `LOCAL_FAILED`. R2 is not `VALIDATION_FROZEN` and
does not authorize modeling, scoring, submissions, TDI, or transductive test
relationships.

R2A implements only `direct_observations.csv`, `group_folds.csv`, and a
scope-limiting manifest. Ten focused synthetic tests cover all four observation
states, invalid numerics and bounds, receipt and policy drift, no partial output
on rejected input, byte determinism, label-independent folds, and component
containment. Two official runs outside Git were byte-identical: 4,905 direct
rows produced 19,620
observations (6,525 complete; 13,095 missing; zero partial/orphan) and 73,575
fold rows. Independent review passed after receipt-before-parse, same-byte parse,
contract-authority, and component-containment hardening. These are deterministic
inputs, not accepted validation assignments or prediction evidence.

R2B implements the three episode projections, manifest-bound oracle loader,
episode label masks, and topology viability without fitting or scoring. Five
focused synthetic tests and all 229 repository tests pass. Two official builds
outside Git were byte-identical: 1,122 rows per episode CSV, 1,818 expanded
queries, 4,488 anchor references, and 7,272 query references. The manifest is
`08dcf61c...`; direct-observation and fold hashes are unchanged. Independent
review passed after the loader was bound to artifact receipts, out-of-component
anchors were rejected, and fold scopes were made explicit. CYP3A4 is supported
at 95 components/473 pairs; 1A2, 2C9, and 2D6 are underpowered with zero local
weight. This is artifact authority, not validation or prediction evidence.

Corrected R3 v3 now freezes the global-only direct fallback contract in
[`global_experiment_contract.json`](../../benchmarks/openadmet_cyp_2026/global_experiment_contract.json).
It preserves the R2B exclusions and family proxy, limits targets to finite
reported central direct points, freezes endpoint median, Morgan 1-NN, Morgan
CatBoost, and fixed MapLight, and uses provisional component-macro MAE only for
internal global selection. Oracle anchors, transformations, inferred anchors,
TDI, submissions, and official ST-RAE remain outside R3 authority. If the
Linux MapLight overlay cannot reproduce the pinned signed-int8 and four-column
NaN behavior without semantic drift, R3 stops before scientific fitting.
V1 is rejected before execution after independent review found five mechanical
blockers; its assigned read-only auditor also bypassed the required branch/PR
workflow and pushed it directly to main. V2 preserves that history and fixes
the boundary before any feature or prediction evidence exists.

V2 is rejected before R3A because its firewall required direct-only raw SMILES
while forbidding both target-bearing direct inputs and mixed inputs containing
blinded-test chemistry. V3 adds only a chemistry prefix projector over the
accepted direct-observation bytes: it decodes eight identity/endpoint/
raw-SMILES fields, treats the remaining record bytes as opaque, parses and
retains zero target values, and joins only the train-only topology and
label-free fold artifacts. It recomputes and receipt-checks the frozen
standardized structure so MapLight uses exact raw SMILES and D-032 Morgan uses
standardized SMILES. The feature process can open only the projected CSV and
its manifest, not the source observations, topology, folds, or any test
artifact.

R3A is accepted for label-free feature payloads only. The official projector
emitted 4,905 rows with zero target parsing and no blinded-test access. Two
fresh roots are byte-identical for feature rows and all five arrays; independent
full Morgan and MapLight recomputation found zero mismatches. Model, prediction,
validation, metric, TDI, submission, official-score, and transductive authority
remain denied.

Additive R3B v4 preserves the immutable v3/R3A receipt chain and repairs the
runner boundary before implementation. Fixed MapLight is chosen before target
access; Morgan, median, and 1-NN are nonselecting falsification controls.
Model-public targets and scorer-sealed truth are separate capabilities, all
support is preflighted before fitting, inner cells receive no outer scores, and
all intermediate work stays in one unpublished run root until a single exact
terminal result is promoted. Independent scientific and mechanical audits pass.

Additive R3B v5 supersedes only the v4 implementation mechanics after code
review found contradictions before official execution. It requires all 60
outer and 240 inner target projections, including header-only zero-row files;
truthful 300-file preflight accounting; exact accounting schemas; explicit
V5/V4/V3 artifact and identifier bindings; composite source receipts; and
recoverable freezer parameter records. The frozen systems, folds, metrics,
budgets, terminal decisions, and authority denials do not change. V5 is still a
contract-only synthetic gate and its SHA-256 is
`596d9a246b130c00f07abfcaf73b369038b874ce556be5e6354df10e1d5ad6e2`.

The v5 target projector/preflight implementation is synthetically accepted. It
emits and staged-reopens all 300 target cells and both sealed truth files,
enforces canonical shared fold/component semantics, exact receipt/accounting
schemas, V5→V4→V3 and accepted composite source gates, strict capability
separation, and atomic read-only no-overwrite publication. Independent audit
passed after five substantive repairs and one final staged-authority byte check.
This is an implementation slice only; no official target was projected and no
fit, prediction, or metric authority is granted.

The complete v5 model-cell, freezer, bounded scorer, and terminal path is also
synthetically accepted. Two fresh roots each executed 60 outer and 240 inner
cells in separate processes, totaling 600 processes and 720 real CatBoost fits.
Both reached `GLOBAL_EXPERT_FROZEN`; deterministic artifacts matched after
normalizing only validated runtime and peak-memory fields. The locked Linux
runtime was checked before every fit. Independent adversarial review passes.
No official target, predictive metric, or leaderboard evidence was opened.

R3C now has one accepted production-only state machine. It verifies immutable
inputs, contracts, implementation bundles, both locked runtimes, and the R3A
feature receipt before target access; gives each fresh cell only its one target
projection; gives freezers no target payload; and enforces the exact causal
60-outer then conditional-240-inner path. It removes all private artifacts
before atomically publishing one exact read-only terminal. A second full
two-root synthetic replay after these repairs again passed 600 isolated cell
processes, 720 CatBoost fits, deterministic comparison, the full test suite,
and independent adversarial review. At that readiness gate no official target
or score had been opened; the later official result is recorded below.

The single authorized official R3C run is complete. Its read-only 15-file
terminal is `GLOBAL_EXPERT_FROZEN`: MapLight's overall endpoint-macro
component-MAE point estimate is 0.571 and its paired loss advantages are 0.0646
over Morgan CatBoost (95%
bootstrap interval 0.0569 to 0.0722), 0.1411 over the endpoint median (0.1306 to
0.1522), and 0.4389 over Morgan 1-NN (0.4222 to 0.4555). Every CYP improves over
the median; MapLight beats Morgan in 56/60 outer cells. All endpoint caps,
influence checks, uncertainty contexts, and completion checks pass. Independent
receipt and arithmetic audits pass. This is internal surrogate evidence only,
not official ST-RAE, a full-training model, a submission, or local TRACE
evidence.

Additive R4 v5 now freezes the pre-fit transformation-coverage boundary in
[`transformation_coverage_contract_v5.json`](../../benchmarks/openadmet_cyp_2026/transformation_coverage_contract_v5.json).
Its exact SHA-256 is
`63d12cb376760c65eabd3d94d3f3939b0591e4019e1332075df0a4c10a4b4954`;
v1 through v4 remain immutable history but are superseded for implementation. V2
jointly ranked single and double cuts and made exact transformation IDs reusable
across families. V3 additionally freezes executable potential-stereo discovery,
CIP records, enhanced/unsupported-stereo rejection, exact automorphism-aware
full-graph maps, isotope and atom-map preservation, implicit hydrogens, and
directional dative bonds. V4 closes implementation-found tetrahedral reference-H
partitioning, embedding-cap serialization, graph-first unsupported-stereo,
bond-stereo reconstruction, query-rank, and publication-receipt gaps. Its
extraction-spec receipt is
`59e3bd3390658bab854be52f88ef7de0164aae6e99ad48b0b0feb04c68669950`.
V5 leaves that extraction receipt unchanged and repairs only the zero-valid
distribution sentinel, pre-input runtime/checkout refusal, and the distinction
between lexicographic JSON key serialization and numeric rational evaluation.
The additive v6 overlay (`a0743c43...`) resolves the only support-implementation
ambiguity by assigning that distribution to unique valid union pair rows and
requiring its count to equal `counts.union.valid_rows`; everything else remains
v5-exact.
It uses only receipt-bound structures, direct measurement availability state,
public episode membership, and a mask prefix containing anchor identity. It
never opens campaign truth or selector/scorable fields and parses or retains
zero target magnitudes. Exact RDKit single/double-cut behavior, virtual-H and
stereo handling, ambiguity, self-versioned IDs, structural-only terminal rows,
valid-only support arithmetic, and status-conditioned authority are frozen.
Independent scientific review passes. No extraction code, coverage artifact,
model, prediction, or metric is accepted by this milestone.

The synthetic trusted-projection slice is accepted separately. It verifies the
five supplied receipts before parsing, never decodes direct numeric/eligibility
fields or the mask suffix, validates exact direct/fold/public/mask/structure
joins, and emits one canonical six-file read-only directory through Linux
atomic no-replace promotion. Thirty-seven focused tests cover poisoned opaque
bytes, malformed CSV, receipt precedence, row-order invariance, every join
family, exact modes/file set, symlinks, mid-stage failure, and destination
races. Independent correctness and minimality audits pass. This status is
synthetic only; a production gate must still bind the v5 contract, accepted
R2B/R3A manifests and leaf receipts, and exact implementation sources before
official input access or extractor consumption.

The synthetic projection consumer is also accepted as a bounded implementation
slice. It hashes all six projected files before parsing and revalidates exact
bytes, manifests, zero authority, molecule standardization, full direct/fold/
episode/mask joins, symlink ancestry, and nonempty cardinality before returning
immutable records. Eleven focused and 48 combined tests plus independent
adversarial review pass. Production receipt identities and official
cardinalities remain deferred to the production runner; this grants no
extraction, support, model, metric, official-input, or publishing authority.

The pure v4 pair extractor is synthetically accepted separately. It has no
file, endpoint, fold, target, or model capability and deterministically emits
ordinary single/double-cut, virtual-H, or exact stereo-only records with both
directions, self-versioned IDs, ambiguity sentinels, and reversal/atom-order
invariance. Independent review rejected two initial defects before acceptance:
E/Z state was lost while reconstructing a variable fragment, and unsupported
stereo incorrectly blocked graph-changing ordinary MMPs. Both now have exact
regression witnesses. Sixty-nine focused contract/extractor tests and the full
490-test suite pass with three expected skips. No official R4 input was opened.

The structural-union and extraction-once slice is now accepted independently.
It includes every same-component pair at inclusive Morgan similarity 0.60 and
every public episode pair, extracts each union identity once, retains exact
anchor-to-query direction, and emits the frozen 47-column pair bytes. It has no
direct-availability, fold, target, model, or metric capability.

The pure support slice is also accepted. It freezes all endpoint, fold,
selected/stress, frequency, independent-family, cross-CYP, episode-training,
rational-distribution, and final status arithmetic without serializing or
publishing an artifact.

The pure serialization slice is now accepted. It emits the exact 25-column
episode CSV and complete v5 coverage JSON with the v6 union-distribution
invariant, zero accounting, conditional authority, canonical bytes, and no
official-input or publication capability. Independent review passes.

The atomic publisher is now accepted. It regenerates outputs from typed
geometry and independently recomputed support, reopens exact bytes against
manifest receipts, publishes only the four-file success or one-file failure
terminal read-only through Linux no-replace, and cleans every rejected stage.

The production-only R4 runner passed pre-execution acceptance. It binds the exact R2B/R3A
manifests and official leaf receipts, contract and source receipts, Linux/RDKit
runtime, clean checkout, and fresh outside-Git destination before opening any
official source. Post-gate failures preserve all applicable failure codes;
cleanup failure refuses terminal publication. Nine focused tests, the full
suite, Ruff, strict mypy, and independent review pass. No official R4 input has
yet been opened.

The first official coverage attempt produced only the frozen V4 failure
terminal (`1d232bc4...`). An unrepresentable crossing-bond stereo reference
raised inside RDKit during MMP embedding recovery; no geometry, coverage,
model, prediction, metric, or TRACE score was produced. The v5 contract already
requires that embedding to be rejected. Preserve the failed terminal unchanged
and revoke extractor/runner acceptance until the narrow implementation repair
passes synthetic replay and independent review.

The repaired embedding path is now reaccepted under new source receipts. It
preserves crossing-bond begin/end order and rejects only stereo references that
cannot remain attached to the corresponding rebuilt endpoints. Synthetic tests
cover both the impossible and representable cases; the full suite, Ruff,
strict mypy, and independent scientific review pass. No contract, input,
population, threshold, or support rule changed.

The repaired official terminal is `R4_TRANSFORMATION_COVERAGE_SUPPORTED`.
CYP3A4 retains 384/473 valid local transformations in 86 families; every local
fold cell exceeds the frozen 20-pair/5-family minima. Selected-anchor coverage
retains 738/903 rows across 118 families, and every selected cell exceeds five
families. Manifest and coverage receipts are `8166a89a...` and `b134d11c...`.
This grants geometry/coverage authority and eligibility to freeze a separate
oracle contract, not model or metric authority.

The separate CYP3A4 oracle contract is now frozen at `c1d7a66c...` after
independent review. It predeclares one primary TRACE system, the complete
blueprint control/ablation set, nested component cross-fitting, label-safe
prediction supersets, pure-OOF no-anchor-potency capability isolation, exact
support gates, paired component bootstrap, influence checks, and fixed 0.5
all-row safety fusion. A clean miss is permanent `R5_ORACLE_NO_SIGNAL`; only a
full pass may authorize a separate inferred-anchor contract.

Exact next action: implement R5's disjoint model-public, measured-target,
no-potency, and sealed-scorer projections plus the compact signed-Morgan/MMP
feature cells. Pass synthetic firewall and two-root determinism acceptance
before opening official numeric targets. Keep inferred anchors, learned
competence, TDI, submissions, official scoring, and transduction deferred;
`global_TDI` remains the permanent TDI fallback.

R3A non-goals: target access, modeling, metric implementation, redistribution,
submissions, transductive use, held-out tuning, broad adapters, services, or
new dependencies.

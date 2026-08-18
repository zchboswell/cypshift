# Phase 1 — OpenADMET TRACE

Status: active; R3B synthetic runner repair contract frozen; gate `R3B_GLOBAL_RUNNER_CONTRACT_V5_REPAIR_FROZEN`; freeze date 2026-08-18.

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

Exact next action: implement and independently review v5's model-cell runner,
prediction freezers, bounded surrogate
scorers, and synthetic determinism/leakage tests. No official scientific fit
may run. R3C alone may execute the frozen official fits and internal surrogate-score
diagnostics after R3B passes as a signed milestone. Preserve
unresolved scorer, TDI-order, interval, and permission behavior; `global_TDI`
remains the permanent fallback and R4 must separately freeze the
oracle/transformation controls.

R3A non-goals: target access, modeling, metric implementation, redistribution,
submissions, transductive use, held-out tuning, broad adapters, services, or
new dependencies.

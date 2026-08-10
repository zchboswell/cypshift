# Phase 0.75 — exact comparator reproduction and representation breakthrough

Status: active — shadow benchmark frozen; Stage A next

Authorized: 2026-08-10

Close no later than: 2026-08-17

## Objective

Complete a tightly scoped public benchmark breakthrough sprint: reproduce the
strongest available CYP comparator, identify the true representation gap, and
establish whether richer molecular representations can produce reproducible
gains under leakage-safe validation without compromising `cypshift`'s
scientific rigor.

Phase 0.75 is public-benchmark research. It does not reverse D-024, weaken the
authoritative challenge freeze, or authorize a guessed challenge adapter,
metric, schema, model, or validation rule. No Phase 0.75 result automatically
becomes a challenge model.

## Governing interpretation of Phase 0.5

Phase 0.5 remains immutable. Its retained mean, scorecards, public-test
evaluations, negative results, receipts, and conclusions must not be changed or
rescored.

Phase 0.5 tested a prior plus three learned families that all used one binary,
chiral, radius-2 Morgan representation. The fixed mean improved those
correlated estimators modestly. The NNLS stack and one fit-free correction
toward the same-representation kNN prediction failed. Those results close their
exact paths. They do not establish that richer molecular representations or
cross-isoform information have been exhausted.

Do not reopen:

- the Phase 0.5 NNLS stack;
- the rejected similarity residual;
- the CheMeleon container attempt;
- handcrafted TDI alerts;
- random-split model selection;
- any Phase 0.5 held-out score or artifact.

## Required Tier 1 scope

Complete these items before the August 17 handoff:

1. freeze the exact MapLight source, paper, method, licenses, and environment;
2. freeze a new public-test evaluation budget;
3. create a leakage-safe shadow benchmark from TDC `train_val` only;
4. reproduce the fixed MapLight representation or diagnose version drift;
5. attempt one exact MapLight + GIN reproduction under an isolated environment;
6. run representation ablations only on the shadow benchmark;
7. publish an honest scorecard and reproduction record;
8. correct the public README and focused benchmark documentation;
9. close Phase 0.75 and hand off to the authoritative launch freeze.

No score threshold is required for Phase 0.75 completion. A precise blocker is
a valid result when a pinned public method cannot be reproduced.

## Conditional Tier 2 scope

Proceed only if Tier 1 completes early and cleanly:

- audit PubChem BioAssay AID 1851 as a possible five-isoform source;
- assess whether its verified fields support cross-isoform panel learning;
- audit public parent/analog topology for a future parent-relative experiment.

Do not train from AID 1851 before its provenance and field meanings are
verified and an independent reviewer passes the cross-task structure firewall.
Do not implement a parent-relative model before a frozen topology audit shows
measured parents, supported analog families, useful target spread, and a task
that resembles parent expansion.

Chemprop, additional encoders, full multitask development, parent-relative
modeling, and LLM adjudication are deferred beyond launch unless a task is
trivial, separately authorized, and does not endanger Tier 1.

## Exact comparator

The first comparator candidate is the public `maplightrx/MapLight-TDC`
repository. Its source, notebooks, paper, license, dependency behavior, file
hashes, and exact revision must be frozen before implementation.

The published method appears to use:

- 1,024 hashed radius-2 Morgan count values;
- 1,024 Avalon count values;
- 315 ErG values;
- 200 ordered RDKit descriptors;
- an optional 300-value pretrained GIN representation;
- five CatBoost classifiers with seeds 1 through 5, `Logloss`, and
  `random_strength=2`.

The fixed representation contains 2,563 declared values. The GIN variant
contains 2,863. Runtime fixture parity must still verify the generated arrays
under the new compatible environment.

The exact source freeze verifies those dimensions and corrects two intake
details. The checked-in notebook's active index is `ppbr_az`, so it runs no CYP
task unchanged. It also reports the mean and population standard deviation of
five seed-specific metrics; it does not score an averaged prediction vector.
Retain all five prediction columns. Use their metric distribution for exact
reproduction, and label the predeclared arithmetic probability mean as a
separate local five-seed ensemble comparator.

The dated fixed-feature AUPRC anchors to verify are approximately 0.783,
0.723, and 0.881 for CYP2C9, CYP2D6, and CYP3A4. The dated MapLight + GNN
anchors remain 0.859, 0.790, and 0.916. If a local result differs by more than
0.010 AUPRC from a matching fixed-feature anchor, stop and diagnose version,
split, feature, default, invalid-row, and averaging drift. Do not tune toward
the public score. The preferred reproduction tolerance is 0.005 AUPRC.

## Public-test evaluation budget

Authorize exactly three new TDC public-test prediction families per task:

1. MapLight fixed representation;
2. MapLight + GIN representation;
3. one final locked `cypshift` contender.

A family is one frozen prediction artifact per task generated from one frozen
code, environment, and configuration state. All declared seeds belong to that
one family and must be retained without post-result selection.

Before each prediction family:

- freeze the signed source commit;
- freeze the environment and configuration;
- verify exact row alignment;
- generate and hash predictions without opening public-test labels;
- obtain independent review approval before scoring.

A failed infrastructure run consumes no family only when it produces no
prediction and accesses no public-test label. It must still be recorded.
Generating a prediction artifact after public-test labels are accessed consumes
the corresponding family. There is no repair cycle after a public-test score is
visible. Do not score an intermediate ablation or use a public result for
feature, model, dependency, or hyperparameter selection.

## Shadow benchmark

All new choices use TDC `train_val` only. Freeze `TDC-CYP-shadow-v1` before a
feature or model result is inspected.

Construct one global, label-independent molecule grouping table across all
three CYP tasks. It must bind:

- standardized structure hash;
- Bemis-Murcko scaffold;
- one frozen chemistry cluster or community assignment;
- task membership and source row identity;
- deterministic split and repeat assignments.

The same standardized structure must always receive the same assignment across
all tasks. Scaffold groups are indivisible in the scaffold protocol. Chemistry
communities are indivisible in the community protocol. Do not union both group
systems, because that would collapse two intended stress tests into one
coarsened protocol. The global assignments are reused across all CYP tasks. No
task-specific regrouping is allowed. Report molecule counts, group counts,
class prevalence, and empty or degenerate fold conditions by task.

The canonical TDC molecule provenance embeds source labels. A trusted
preparation step must first emit and receipt-bind a train_val-only projection
containing identities and structures but no target or provenance. The split and
feature processes may resolve only that stripped projection. A separate summary
process may resolve only the frozen train_val measurement projection after the
label-independent assignment bytes are hashed; it may not resolve canonical or
public-test measurement roots.

Freeze one scaffold-held-out protocol and one chemistry-community-held-out
protocol. Use three deterministic outer repeats where task populations permit
them, with grouped inner selection inside each outer training population. The
exact grouping, balancing, tie, seed, nesting, and failure rules must be
receipt-bound before execution. Random splits remain diagnostic only and cannot
select a candidate. The exact pre-result split contract is
[`tdc_cyp_shadow_v1_contract.json`](../../benchmarks/tdc_cyp_shadow_v1_contract.json).
The companion
[`tdc_cyp_shadow_v1_implementation_contract.json`](../../benchmarks/tdc_cyp_shadow_v1_implementation_contract.json)
freezes the exact join, numeric ordering, provenance-access boundary, artifact
schemas, serialization, runtime environment, and synthetic mechanics fixtures.
It permits no real generation until the implementation passes independent
review.

Use separate entrypoints for the trusted projection, label-free assignment,
and train-only summary. The assignment process accepts only the stripped input,
its receipt, the parent and implementation contracts, and the pinned lock. The
assignment runs below an active wall-time and RSS watchdog and is promoted from
a staging root only after completion. The summary resolves the original
stripped input chain and fully verifies the hashed assignment, environment,
population, grouping counts, resource observations, and zero-use accounting.
It then validates the complete train-only identity set before reading any target
value. Resource and summary-validation failures preserve compact blocker
receipts. All real inputs must be stable read-only files for the process
lifetime.

### Frozen shadow outcome

The implementation passed independent review and generated the real benchmark
from signed source revision `8a2e227`. Two trusted projections are
byte-identical. Two label-free assignments are byte-identical. The canonical
assignment contains 30,038 rows, 15,354 standardized structures, 9,114 scaffold
groups, and 9,902 chemistry communities. Its `shadow_rows.csv` SHA-256 is
`b633af0cbd5aa98a03ae77eb3e021eb32b441ae8133e24a2c9eb85394e41bc5f`.

The separate summary parsed 30,038 frozen `train_val` labels and zero
public-test labels after verifying the assignment bytes. All task, protocol,
repeat, outer, inner, and training populations contain both classes. The final
manifest SHA-256 is
`3eb972713d88e08420134e7776755d4e62510a5250edf99edc2021272c112656`.
It records zero feature matrices, fits, predictions, and metric evaluations.
Three independent reviews passed the artifacts and arithmetic. Generated roots
remain outside Git and read-only.

## Minimal research-code boundary

Do not rewrite the frozen Phase 0.5 modules and do not add a registry, plugin
system, benchmark framework, or second public CLI path. Add only the smallest
internal seam needed to construct, bind, align, and consume more than one
feature block.

Every feature artifact must record its name, version, dimensions, dtype,
feature names or ordering, standardized-structure row hashes, generator source,
encoder source when applicable, artifact hash, and non-finite or failed-row
policy. Feature generation must be label-free. Training and prediction must use
the same frozen generator. OOF rows must identify the representation and
encoder versions.

Heavy research dependencies remain outside the core install and ordinary CI.
CatBoost, PyTorch, DGL, MolFeat, and model weights must use separately locked
research environments or digest-pinned containers. Do not add them to the
normal `pip install cypshift` path or the existing all-groups CI environment.
The public CLI remains exactly `audit`, `train`, `predict`, and `report`.

## Stage A — fixed MapLight reproduction

The pre-result Stage A contract is
[`maplight_fixed_stage_a_contract.json`](../../benchmarks/maplight_fixed_stage_a_contract.json).
It freezes a result-blind compatible environment under
`research/maplight-fixed/`: Python 3.10.13, RDKit 2023.03.3, CatBoost 1.2.1,
NumPy 1.25.2, pandas 2.0.3, scikit-learn 1.3.0, and SciPy 1.11.2. All
transitive releases are restricted to no later than 2023-08-29 UTC. This is
not the unrecoverable historical MapLight environment.

Implement the exact four MapLight feature blocks only after the contract
passes independent review. Compare
fixture arrays directly with the pinned public implementation and verify count
versus binary behavior, descriptor order, dimensions, dtype, failed structures,
non-finite handling, and RDKit drift.

Reproduce the five-seed CatBoost method on exact raw TDC strings without
tuning. On the shadow benchmark only, compare six unique candidates:

1. binary chiral Morgan plus CatBoost seed 1;
2. Morgan counts plus CatBoost seed 1;
3. Morgan plus Avalon counts plus CatBoost seed 1;
4. Morgan plus Avalon plus ErG plus CatBoost seed 1;
5. the complete fixed representation plus CatBoost seeds 1 through 5;
6. the complete fixed representation plus the frozen ExtraTrees diagnostic.

The complete fixed CatBoost entry is one artifact, not two candidates. Use
three tasks, two protocols, and three repeats with outer fold 0 held out. No
inner fit is needed because no choice remains. The exact budget is 162
CatBoost fits plus 18 ExtraTrees fits, for 180 total. Retain all seed
predictions. Use paired synchronized scaffold and community bootstraps only for
the complete-representation effect and the CatBoost-versus-ExtraTrees effect.
Incremental block deltas are descriptive.

R1 shares the raw-input policy needed for a fair representation contrast. It
has Phase 0.5 binary-Morgan feature semantics, but it is not a rescore of the
standardized Phase 0.5 pipeline. Stage A consumes no public-test budget.

Gate 1 must pass before public scoring: representation parity, frozen
environment, complete row alignment, label-free predictions, accurate fit and
prediction counts, and independent review.

## Stage B — MapLight + GIN reproduction

Begin only after Stage A passes or has a precise accepted blocker. Freeze the
exact pretrained encoder identifier, package versions, weight bytes and hashes,
embedding dimension, device behavior, and failed-structure policy. Precompute
label-free embeddings keyed by standardized structure hash. The predictor may
consume only the cached, receipt-bound matrix.

Record the available pretraining corpus and audit structure overlap against TDC
and the Veith/PubChem source when possible. Classify contamination as known
clean, known overlap, or unknown. Unknown provenance permits an engineering
transfer benchmark, not a clean zero-shot claim. Challenge overlap must be
revisited after the official release.

On shadow validation only, compare fixed features, GIN alone, fixed plus GIN,
fixed plus deterministically shuffled GIN rows, and fixed plus same-dimensional
random noise. Controls must not reproduce a claimed GIN gain.

Gate 2 must pass before public scoring: embeddings and environment frozen,
contamination status recorded, alignment and finiteness verified, label-free
predictions hashed, and independent review.

If dependency or pretrained-weight drift prevents exact reproduction, retain a
precise blocker. If a local implementation is reproducible but does not match
the dated point result, it becomes the frozen local comparator with the drift
stated explicitly.

## Conditional public-source audits

AID 1851 is not authorized training data by name alone. Before any target field
is parsed for training, freeze and audit the primary PubChem record, original
paper, assay fields, outcomes, potency and efficacy fields, qualifier and
missing-value semantics, source dates, depositor, terms, structures, and
hashes. Do not treat inconclusive or unresolved values as inactive.

Create one strict union exclusion containing every structure that appears in
any TDC public-test task. A structure in that union may contribute no AID 1851
label for any isoform. Shadow validation must apply the same cross-isoform rule
to each held-out molecule and family. Gate 3 requires independent review of the
source semantics and firewall before labels enter training.

Use the term `cross-isoform panel learning` until verified assay variables are
actually retained. Do not call an isoform-only model assay-conditioned.

## Statistical standard

Use identical molecules, paired predictions, declared seeds, and bootstrap
resampling by the frozen scaffold or analog-family unit. Report every task,
population, prevalence, sample count, point difference, 95% interval, and worst
groups. Freeze the resampling seed, replicate count, percentile method,
degenerate-resample handling, task aggregation, and direction before the final
contender result exists.

Relative to the locally reproduced MapLight + GIN comparator, a final contender
is a credible improvement only when:

1. the paired 95% lower confidence bound for AUPRC improvement is positive on
   at least two of CYP2C9, CYP2D6, and CYP3A4;
2. the remaining task does not lose more than 0.005 absolute AUPRC; and
3. the paired macro-average improvement has a positive 95% lower confidence
   bound.

Beating only a published point estimate is not superiority. A score at or above
0.95 AUPRC triggers an immediate independent forensic audit of duplicates,
cross-isoform labels, PubChem identities, external and pretrained overlap,
folds, row alignment, provenance fields, chronology, scaffold concentration,
label polarity, and metric code before the score is communicated as evidence.

Gate 4 must pass before the final public-test family: all selection complete on
shadow evidence, source and environment frozen, prediction path label-free,
artifact hashes fixed, budget available, and independent review complete.

## Product and documentation boundary

The repository is intentionally public. Update its public documentation after
the scientific contracts exist:

- remove the stale private-repository statement;
- state benchmark status and assay limitations accurately;
- add a concise scorecard and one focused reproduction guide;
- explain isolated research environments without burdening core installation;
- update contribution and citation guidance when supported by current files.

Do not expose credentials, restricted data, private planning material, or
unpublished challenge strategy. Add no dashboard.

## Acceptance criteria

Phase 0.75 passes when:

1. the signed Phase 0.75 authorization merges before modeling work;
2. Phase 0.5 remains byte-for-byte immutable;
3. MapLight source, method, license, and environment are pinned;
4. the public-test budget and shadow benchmark are frozen;
5. fixed-feature arrays pass fixture parity or have a precise blocker;
6. fixed MapLight is reproduced once on the official test or version drift is
   diagnosed without score-driven repair;
7. GIN reproduction completes once or has a precise blocker;
8. row-level local comparator predictions exist for each completed family;
9. all ablations and choices use shadow evidence only;
10. new public-test use stays within the three-family budget;
11. dependencies remain isolated and the core installation stays lightweight;
12. the four-command public CLI remains unchanged;
13. the scorecard and public documentation are accurate;
14. independent review passes each reached irreversible boundary;
15. the August 17 handoff states exactly what transfers and what does not.

Tier 2 is not required for closeout. A final `cypshift` contender is not
required if shadow evidence does not justify one.

## Stopping rules and non-goals

Stop an experiment when it requires public-test iteration, cannot compare
identical rows, lacks source provenance, uses target information during feature
generation, cannot demonstrate the global cross-task firewall, depends on
disproportionate infrastructure, shows no shadow gain, concentrates its gain in
one group, or is explained by a simpler representation.

Do not add docking, molecular dynamics, LLM adjudication, mechanistic alerts,
large conformer workflows, a web UI, a database, an orchestration framework, a
foundation-model zoo, challenge-specific code, or guessed launch fields.

## Implementation order

1. Merge the signed Phase 0.75 authorization. **Complete.**
2. Freeze the MapLight source, paper, method, license, and environment.
   **Complete for the available public evidence.**
3. Freeze the public-test budget and exact shadow-split contract. **Complete.**
4. Create the global shadow grouping and validate it before model work.
   **Complete.**
5. Freeze the Stage A environment, parity, ablation, accounting, and stopping
   contract. **Complete.**
6. Add the smallest feature-block seam.
7. Implement and parity-test the four fixed feature blocks.
8. Run the shadow representation ablation.
9. Pass Gate 1 and consume the fixed-MapLight public-test family once.
10. Build the isolated GIN embedding path and shadow controls.
11. Pass Gate 2 and consume the GIN public-test family once.
12. Freeze row-level comparator predictions and the honest scorecard.
13. Perform Tier 2 audits only if Tier 1 is early and clean.
14. Lock and evaluate one final contender only if shadow evidence and Gate 4
    support it.
15. Update public documentation, obtain closeout review, and hand off on
    August 17.

The first scientific milestone is a locally reproduced row-level MapLight
comparator. The first possible breakthrough is evidence that richer molecular
representation improves the sealed shadow benchmark. Neither result is a
challenge-performance claim.

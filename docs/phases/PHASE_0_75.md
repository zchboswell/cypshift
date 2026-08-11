# Phase 0.75 — exact comparator reproduction and representation breakthrough

Status: missing-value compatibility addendum active under D-027; prior
experiments remain closed negative

Authorized: 2026-08-10

Close no later than: 2026-08-17

## Objective

Complete a tightly scoped public benchmark breakthrough sprint: reproduce the
strongest available CYP comparator, identify the true representation gap, and
establish whether richer molecular representations can produce reproducible
gains under chemistry-aware grouped validation without compromising `cypshift`'s
scientific rigor.

The active question is narrower: can the fixed MapLight and pretrained GIN
representations materially improve CYP ranking on the frozen
chemistry-cluster-held-out shadow benchmark? TDC AUPRC is a representation
benchmark only. It is not the OpenADMET direct-inhibition regression metric,
the TDI MCC metric, or a challenge-performance proxy.

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

1. freeze the exact MapLight source, paper, method, and licenses, plus one
   hash-locked compatible environment;
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

Before any new public-test label is inspected, complete every permitted
label-free prediction family that will be used. The third family may be left
unused. Freeze all completed families together, then score them together. Do
not score fixed MapLight and continue developing GIN afterward.

For every completed prediction family:

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

All new choices use TDC `train_val` only. `TDC-CYP-shadow-v1` is frozen. It is
currently a chemistry-cluster-held-out benchmark, not a demonstrated strict
analog firewall. Do not rebuild, tune, or reseed it.

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

### Evidence-execution topology audit

Measure the frozen assignment before interpreting a representation result. Do
not change its groups or folds. For every validation structure, report the
maximum train-validation binary-Morgan Tanimoto similarity and the count and
proportion at or above 0.60, 0.70, 0.80, and 0.90. Also verify exact and
standardized duplicate crossing, scaffold and community group sizes, fold
sizes and prevalence, raw-SMILES multiplicity per standardized hash, duplicate
structure-task cells, and conflicting structure-task cells.

Prepare fixed reporting populations for the Stage A result: official
row-weighted rows, unique structure-task cells, conflict-isolated rows,
validation rows with no training neighbor at or above 0.60, and
leave-one-scaffold-or-community-out influence. These are sensitivity analyses,
not new candidates or split-selection inputs. Until this report supports
stronger language, describe the artifact as a chemistry-cluster-held-out
shadow benchmark.

## Minimal research-code boundary

Do not rewrite the frozen Phase 0.5 modules and do not add a registry, plugin
system, benchmark framework, source adapter, feature store, workflow engine, or
second public CLI path. Use direct Stage A research scripts and the already
frozen contracts. No new research layer may precede comparator evidence.

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

The next durable scientific milestone must contain exact fixture parity, two
independently generated and byte-identical feature roots, row-alignment and
environment receipts, all frozen shadow predictions, fold and aggregate
metrics, topology-stratified metrics, runtime and hardware evidence, or one
precise reproducible blocker. Another contract without those results is not a
milestone.

Call the complete fixed representation meaningful beyond binary Morgan only
when its paired macro-AUPRC lower confidence bound is above zero in both shadow
protocols, at least two of three CYP tasks improve, and the remaining task
loses no more than 0.005 AUPRC. The direction must also survive unique-cell
weighting, conflict isolation, the below-0.60-neighbor population, and removal
of the most influential group. If a simpler frozen block explains the gain,
retain the simpler block. A failed gate still leaves fixed MapLight as the
required comparator.

Gate 1 must pass before public scoring: representation parity, frozen
environment, complete row alignment, label-free predictions, accurate fit and
prediction counts, and independent review.

## Stage B — MapLight + GIN reproduction

Begin only after fixed-MapLight parity and shadow predictions exist. Freeze the
exact pretrained encoder identifier, package versions, weight bytes and hashes,
embedding dimension, device behavior, and failed-structure policy. For exact
reproduction, key label-free embeddings by exact raw-row identity. Do not cache
solely by standardized structure hash unless numerical invariance is
demonstrated for every standardized hash with multiple raw SMILES. The fixed
and GIN blocks for a row must use the same raw-molecule interpretation. The
predictor may consume only the cached, receipt-bound matrix.

Record the available pretraining corpus and audit structure overlap against TDC
and the Veith/PubChem source when possible. Classify contamination as known
clean, known overlap, or unknown. Unknown provenance permits an engineering
transfer benchmark, not a clean zero-shot claim. Challenge overlap must be
revisited after the official release.

On shadow validation only, compare fixed features, GIN alone, fixed plus GIN,
fixed plus deterministically shuffled GIN rows, and fixed plus same-dimensional
random noise. Controls must not reproduce a claimed GIN gain.

Retain GIN as a scientific ingredient only when embeddings reproduce, row
alignment is exact, shuffled and random controls do not reproduce the gain,
the paired macro lower bound is positive, at least two tasks improve, and the
remaining task loses no more than 0.005 AUPRC. The direction must survive the
unique-cell, conflict-isolated, below-0.60-neighbor, and most-influential-group
analyses. Otherwise retain only the exact engineering comparator or blocker.

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
10. all completed public prediction families were frozen together before new
    public-label inspection, and use stays within the three-family budget;
11. dependencies remain isolated and the core installation stays lightweight;
12. the four-command public CLI remains unchanged;
13. the scorecard and public documentation are accurate;
14. independent review passes each reached irreversible boundary;
15. the August 17 handoff states exactly what transfers and what does not.

Tier 2 is not required for closeout. A final `cypshift` contender is not
required if shadow evidence does not justify one.

The original closeout remains a stopped negative under D-025 and D-026, not a
pass of every acceptance criterion. Criteria 6 through 10 were not reached:
no official fixed score, GIN result, row-level prediction, representation
ablation, or public prediction family exists. Fixture parity satisfies
criterion 5. The project owner later authorized D-027 as a separate,
result-blind compatibility addendum after a label-free causal diagnosis. D-027
does not repair either prior experiment and does not erase the stopped-negative
record.

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
6. Measure the frozen shadow topology without changing an assignment.
   **Complete. The result supports chemistry-cluster-held-out language, not a
   strict analog-firewall claim.**
7. Implement and parity-test the four fixed feature blocks with direct research
   code; generate two matching label-free feature roots. **Parity passed. The
   first real build stopped before retaining a matrix because one Avalon sparse
   count is 144 and the frozen safe maximum is 127. A separately authorized
   exact signed-`int8` parity then passed, but its first real build stopped on a
   RDKit descriptor matrix containing at least one non-finite value; the first
   affected exact-raw row was index 1,563. Build 2 is authorized under neither
   prior contract. D-027 now authorizes two fresh roots under the exact
   four-column `NaN` rule; neither has run.**
8. Run the frozen Stage A shadow candidates and sensitivity analyses once.
   **Not reached; D-027 feature parity is the prerequisite.**
9. Pass Gate 1 and freeze the label-free fixed-MapLight public predictions, but
   do not score them yet. **Not reached.**
10. Build the isolated GIN embedding path and shadow controls. **Not started;
    fixed-MapLight shadow predictions are a prerequisite.**
11. Pass Gate 2 and freeze the label-free GIN public predictions, but do not
    score them yet. **Not reached.**
12. Lock a final contender only if the complete shadow gate supports it;
    otherwise record that its public family remains unused. **Not reached; the
    final-contender public family remains unused.**
13. Independently review and freeze all completed public prediction families
    together, then score them together once. **Not reached; no public prediction
    family was produced or scored.**
14. Freeze row-level comparator evidence and the honest scorecard. **Not
    reached; the blocker report replaces a predictive scorecard.**
15. Perform Tier 2 audits only if Tier 1 is early and clean. **Not started.**
16. Update public documentation, obtain closeout review, and hand off on
    August 17. **Closeout documentation is complete; authoritative release
    intake remains pending under D-024.**

The first scientific milestone produced exact parity and a precise real-row
blocker rather than a comparator. The safe contract cannot reach Stage A
predictions without violating its count-safety rule. The separately authorized
exact-upstream signed-`int8` experiment reproduced the overflow bytes exactly,
then stopped on a second frozen boundary: the RDKit descriptor matrix contained
at least one non-finite value after all five blocks were computed in memory;
the first affected exact-raw row was index 1,563. It retained no feature
matrix. D-026
forbids another scientific change, retry, build 2, fitting, GIN, or public
scoring. No result is a challenge-performance claim.

### D-027 missing-value compatibility addendum

The post-blocker diagnostic examined only the frozen label-free shadow rows in
the pinned research environment. Exactly 41 of 15,399 unique exact-raw
structures, expanding to 82 of 30,038 rows, contain `NaN` in all four and only
the four frozen Gasteiger charge-extrema descriptors. The affected rare
elements are As, Hg, Sb, Se, and Sn. No infinity or non-finite value in another
frozen descriptor was observed. The first affected exact-raw row is index
1,563, hash `6911fe92...`. Its molecule parses normally; phosphorus controls
make the same charge descriptors finite. RDKit 2026.03.5 reproduces the first
failure, so ordinary version drift is not the best explanation.

The exact pinned MapLight source does not reject, impute, filter, or delete
these values before CatBoost. A synthetic probe in pinned CatBoost 1.2.1
accepts float64 `NaN`, produces finite probabilities, and resolves the default
`nan_mode` to `Min`. The frozen scikit-learn 1.3.0 ExtraTrees diagnostic rejects
the same input.

D-027 therefore permits one rule only: preserve `NaN` unchanged in descriptor
indices 39, 41, 43, and 45, while rejecting every infinity and every `NaN`
outside those columns. Imputation, row deletion, descriptor deletion,
missingness indicators, structure edits, and custom rare-element charge
parameters remain forbidden. Two independent full feature roots must be
byte-identical before the existing CatBoost R1-through-R5 ladder can fit.
ExtraTrees E1 is not authorized on the exact missing-value matrix and supports
no estimator-effect claim.

The tracked diagnostic receipt is
[`maplight_fixed_nan_diagnosis.json`](../../benchmarks/receipts/maplight_fixed_nan_diagnosis.json).
The result-blind execution contract is
[`maplight_fixed_nan_compat_contract.json`](../../benchmarks/maplight_fixed_nan_compat_contract.json).

The D-027 feature gate passed at signed source `9d6b719`. Two fresh builds
processed all 30,038 rows from 15,399 exact raw inputs and retained five arrays
each. `feature_rows.csv` and every corresponding NPY payload are byte-identical
across builds. The descriptor matrix contains exactly the predeclared 328
expanded `NaN` cells across 82 rows and only the four permitted columns; no
infinity or other non-finite value is present. Manifest SHA-256 values are
`5a3b038e...` and `0afd641c...`. The synthetic CatBoost probe passed with
finite probabilities and resolved `nan_mode=Min`. No target, scientific fit,
prediction, metric, GIN, challenge, or public-test operation occurred. This
passes only the label-free feature gate and makes no predictive-value claim.

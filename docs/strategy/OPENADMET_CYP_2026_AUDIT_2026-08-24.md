# cypshift / OpenADMET CYP 2026 audit report

**Audit snapshot:** current `main` and the requested pinned revision both resolve to `8da243e5d8cd8556c3a7333fafe7f9ec3830ab73`. No submission was made, no credential was requested or accessed, and no blinded-test prediction was inspected or generated. The final leaderboard check was made at **2026-08-24 02:10:19 UTC**. 

---

## 1. Executive verdict

### The decision

**Build a stronger global ensemble first. Do not make TRACE the primary competition strategy.**

The most defensible path to a significant gain over the prior private submission is:

1. A family-safe, cross-fitted heterogeneous global ensemble using tuned MapLight variants, LightGBM/XGBoost, alternative fingerprints and descriptors, and one or two pretrained molecular representations.
2. A masked four-isoform multitask model with an objective aligned to the challenge’s credible intervals and MA-ST-RAE metric.
3. Provenance-controlled external CYP transfer learning, with aggressive duplicate and analog-family exclusion.
4. Only after those: a new TRACE v2 implemented as a **small, abstaining residual expert** that defaults to the global prediction.

The original TRACE experiment is not borderline. It is a clean, decisive negative result:

- G0 component-macro MAE: **0.432732**
- T0 component-macro MAE: **0.715892**
- G0-minus-T0: **−0.283160**
- 95% interval: **[−0.398336, −0.167401]**
- T0 wins: **1 of 15** repeat-fold cells

The result does not imply that all local methods are useless. It does show that this particular “measured anchor + predicted delta + hierarchy” system should not be repaired by incremental complexity or deployed under a large fusion weight. 

### Why TRACE failed

The dominant pattern is:

- On **non-activity-cliff** rows, T0 is approximately neutral but still worse than G0.
- On **activity cliffs**, T0 is catastrophically worse.
- Higher structural similarity does not identify safer local predictions.
- Exact transformation support is somewhat better than class-only support, but not sufficiently reliable.
- The selected anchor policy was not clearly superior to the random-anchor stress policy.
- Inner-selection performance was inversely associated with outer performance.
- The frozen 50% G0/T0 fusion materially worsened G0.

This points to an inability to identify when the local expert is competent, combined with unstable delta prediction and insufficient shrinkage—not primarily an extraction or fallback defect.

### Automation verdict

The scientific workflow can be automated now. **Live uploading should remain disabled.**

The challenge contract establishes a 12-hour upload interval and one ranked account per team/lab, while the official materials state that the live leaderboard uses half the test set and the final ranking uses the full set. Public Hugging Face documentation establishes that Gradio Spaces can expose APIs, but I did not find an organizer statement explicitly permitting unattended automated competition uploads or a documented challenge-specific submission endpoint. Generic API availability is not equivalent to competition permission. 

---

## 2. Evidence independently reproduced

### Repository and governance state

The requested commit is the current `main` revision and is the commit that publishes the training-only TRACE audit bundle. The repository governance requires state/phase/decision review before implementation, small signed commits, PR-based integration, full tests and static checks, immutable experiment records, retention of negative results, and exclusion of credentials, raw competition data, predictions, and unrestricted artifacts from Git. 

### Public audit material inspected

I independently parsed and reduced the public scientific CSVs:

| Artifact | Rows excluding header | Independently matched SHA-256 |
|---|---:|---|
| `oracle_scored_rows.csv` | 11,346 | `4cb09e93e8920217558256b2bebb54e8c6a3475458479746c60ef9505c3e2bc1` |
| `oracle_cell_metrics.csv` | 180 | `8e2aa085d3bd4378068e65897dd1b3b539ba7674ce32988445f92df980f0ca15` |
| `oracle_bootstrap_summary.csv` | 10 | `7684090b4e493ac5aeaaf941fd75f37da7b82bff9d6b33f232f2ce2b347dbb66` |
| `oracle_influence_checks.csv` | 10 | `6fc5a498e9a8e9cd16790eb4574adface8109dd3295f64734f8c3e38f755a6b7` |
| `oracle_ablation_scorecard.csv` | 12 | `4f9e60bd91e9865ac356037e1786f0e17af0a2917ed433dc9a0a93bd36c6c986` |
| `oracle_inner_selection.csv` | 240 | `dc5d6f32f4618acb0d1d1e97d57581e9bc6b0ee7bf521b1c79980288d6c90a8d` |

These hashes match the published `SHA256SUMS`. The scored-row schema exposes identifiers, metadata, weights, and absolute errors, but not predictions, targets, SMILES, anchor values, or blinded-test information. 

### Command-level limitation

I could **not honestly report a complete pass** for the two requested shell commands. The audit runtime could not clone the repository through Git, and its file-materialization boundary blocked some raw JSON and Python objects. Consequently:

- I verified the six scientific CSV hashes individually.
- I inspected the public test source and its expected checks.
- I independently recomputed the scientific terminal.
- I did **not** execute the complete `sha256sum -c .../SHA256SUMS` over every JSON/receipt artifact.
- I did **not** execute `uv run pytest -q tests/test_openadmet_r5d_public_audit_bundle.py`.

The public test requires the exact 7,985-process accounting, zero-exit sequence, forbidden-column checks, source-revision checks, receipt hashes, and terminal values. Its expected accounting is internally consistent with the public receipt and manifest. 

### Independently reproduced terminal

| Quantity | Recomputed value |
|---|---:|
| Primary G0 component-macro MAE | 0.4327321629632583 |
| Primary T0 component-macro MAE | 0.7158918736591554 |
| G0-minus-T0 | −0.2831597106958972 |
| Bootstrap 95% interval | [−0.3983355613565951, −0.16740067252975555] |
| Accepted bootstrap replicates | 2,000 |
| T0-favorable cells | 1/15 |
| T0-favorable cells by repeat | 1/5, 0/5, 0/5 |
| Primary components | 82 |
| Primary paired query rows per system | 420 |
| Components favoring T0 | 21 |
| Components favoring G0 | 61 |

Recomputed cell metrics agree with the published cell table to floating-point precision, with a maximum absolute discrepancy below `5e-16`. All ten leave-one-component-out G0-minus-T0 contrasts remain negative, so the conclusion is not driven by one extreme family. 

---

## 3. Current baseline strengths and weaknesses

### Baseline strengths

The fixed MapLight implementation is scientifically stronger than a typical competition starter:

- Structural identity and targets are capability-separated.
- Test feature construction is explicitly label-blind.
- The feature and deployment contracts are immutable.
- Family/component holdout is used instead of random molecule splitting.
- Missing endpoint values are not imputed into targets.
- Submission bytes are validated for schema, row order, finiteness, endpoint completeness, and exact reproducibility.
- Two independent rehearsals must be byte-identical.
- Model artifacts and predictions remain outside Git.

The accepted global validation reported an overall family-held-out component MAE of **0.571053**, with endpoint results:

| Endpoint | Fixed MapLight family-held-out MAE |
|---|---:|
| CYP1A2 | 0.657310 |
| CYP2C9 | 0.474675 |
| CYP2D6 | 0.583530 |
| CYP3A4 | 0.568697 |

It beat the accepted Morgan comparator by approximately 0.0646 MAE and won 56 of 60 endpoint/repeat/fold cells against that comparator. 

### Current representation and learner

The deployment contract concatenates:

- 1,024 signed Morgan-count dimensions
- 1,024 signed Avalon-count dimensions
- 315 ErG dimensions
- 200 RDKit descriptors

for **2,563 features**. One `CatBoostRegressor` is trained independently for each endpoint with MAE loss, `random_strength=2`, one fixed seed, CPU execution, and otherwise largely default behavior. There is no validation set, early stopping, seed bagging, model ensemble, target sharing, interval-aware objective, post-fit calibration, or use of external data. 

The finite direct-inhibition target counts are uneven:

- CYP1A2: 1,412
- CYP2C9: 1,285
- CYP2D6: 1,493
- CYP3A4: 2,335

The remaining endpoint cells are discarded for that endpoint’s fit rather than contributing through multitask representation learning. 

### Highest-impact baseline limitations

#### B1 — Single-seed, lightly configured CatBoost

**Targeted failure:** model variance and underexplored capacity.

**Change:** train a small nested-CV grid over depth, learning rate, iterations, L2 regularization, random strength, row/feature subsampling, and loss variants; retain 3–5 independently seeded models per selected configuration.

**Exact data:** current direct-inhibition training points and current MapLight features only.

**Leakage-safe split:** the existing repeated family/component outer folds, with hyperparameters and iteration counts selected exclusively inside outer training components.

**Metrics:** primary organizer-matched training MA-ST-RAE proxy; secondary component-macro MAE and per-endpoint Spearman correlation.

**Acceptance:** at least 3% relative primary-metric improvement and at least 0.015 absolute component-MAE improvement, with a paired component-bootstrap upper 95% bound below zero; no endpoint worsens by more than 0.015.

**Compute:** approximately 300–1,200 CPU core-hours.

**Expected uplift:** 0.005–0.020 absolute component MAE.

**Overfitting risk:** medium if a broad grid is repeatedly inspected; low with one frozen grid and nested selection.

**Simplest falsifier:** a 12-configuration, three-seed screen fails to beat fixed MapLight in at least 8 of 15 outer cells.

#### B2 — Heterogeneous feature/model ensemble

**Targeted failure:** one feature concatenation and one learner create strongly correlated errors.

**Change:** cross-fit CatBoost, LightGBM, and XGBoost experts over deliberately different representations:

- Morgan bit and count fingerprints at radii 2 and 3
- Avalon
- AtomPair and TopologicalTorsion
- ErG and pharmacophore fingerprints
- RDKit descriptors
- a controlled Mordred subset
- one or two frozen pretrained embeddings

Use an inner-fold non-negative or ridge stack. Scaling and dimensionality reduction must be fitted inside each inner training partition; tree models should receive raw block values.

**Exact data:** direct-inhibition training table, current structural projection, deterministic fingerprints/descriptors, frozen public embedding model receipts.

**Split:** repeated outer family/component folds; all representation selection, PCA, stack weights, and clipping chosen inside the outer training set.

**Metrics:** macro endpoint MA-ST-RAE proxy first; component MAE, rank correlations, and calibration second.

**Acceptance:** at least 5% primary improvement, at least 0.025 absolute component-MAE reduction, 10/15 favorable cells, and no endpoint loss above 0.015.

**Compute:** 1,000–4,000 CPU core-hours plus 10–30 GPU-hours for embedding extraction.

**Expected uplift:** 0.020–0.050 absolute MAE.

**Overfitting risk:** medium; the major risk is selecting among many nearly identical stacks.

**Simplest falsifier:** the best two-model OOF blend fails to improve either primary metric or MAE over the better constituent.

#### B3 — Masked four-isoform multitask learning

**Targeted failure:** separate models discard the strong shared CYP representation and waste missing-label rows.

**Change:** a shared molecular encoder with four endpoint heads, a missing-target mask, endpoint embeddings, and optional assay-context auxiliary heads. Compare a multitask Chemprop-style message-passing network with a smaller shared MLP over fingerprints/embeddings.

**Exact data:** all finite four-CYP central values, missingness masks, confidence intervals and standard deviations; optionally the official single-concentration and Emax tables as auxiliary tasks. TDI classification may be an auxiliary representation task but must not be mixed into the direct loss without a distinct head.

**Split:** structures grouped before any task is opened; an entire chemical family is assigned to one outer fold across every assay table.

**Metrics:** endpoint-macro MA-ST-RAE proxy; component MAE; each endpoint separately.

**Acceptance:** at least 0.020 macro MAE improvement, at least two endpoints improve materially, and no endpoint worsens by more than 0.020.

**Compute:** 30–100 GPU-hours.

**Expected uplift:** 0.010–0.035 absolute MAE.

**Overfitting risk:** medium, particularly for CYP2C9 and CYP1A2.

**Simplest falsifier:** the shared encoder cannot outperform four independent heads when trained on exactly the same representation and folds.

#### B4 — Interval-aware objective and calibration

**Targeted failure:** training against central values with plain MAE is mismatched to MA-ST-RAE, which assigns zero error inside the assay credible interval.

**Change:** compare:

- interval dead-zone loss;
- heteroscedastic location/scale prediction;
- interval-censored likelihood;
- central-value model followed by cross-fitted interval-aware linear shrinkage and clipping.

Do not optimize thresholds using leaderboard feedback.

**Exact data:** central pIC50, lower and upper credible bounds, standard deviations, and endpoint assay metadata from the official training table.

**Split:** all loss parameters and calibration maps fitted inside inner family folds.

**Metrics:** primary MA-ST-RAE proxy; secondary central-value MAE, interval coverage, calibration error, and rank correlations.

**Acceptance:** at least 5% primary improvement with no more than 0.005 MAE degradation.

**Compute:** 100–400 CPU core-hours or 10–30 GPU-hours.

**Expected uplift:** 3–10% in the primary metric; usually 0–0.010 central-value MAE.

**Overfitting risk:** low to medium.

**Simplest falsifier:** interval-aware predictions improve neither the proxy metric nor empirical interval coverage on any endpoint.

#### B5 — Public external CYP transfer

**Targeted failure:** challenge training data are small relative to the chemical and assay complexity.

**Change:** pretrain or warm-start on public CYP assay data, then fine-tune on challenge data. Use assay identifiers, organism, endpoint type, concentration protocol, and confidence/quality fields. External examples should be down-weighted or represented by assay-specific heads rather than pooled as if they were homogeneous measurements.

OpenADMET currently publishes a 51,400-row CYP inhibition/reactivity dataset and a public four-isoform CheMeleon model; its own model-development report notes material assay heterogeneity and much harder cluster-split performance. 

**Exact data:** public OpenADMET CYP data, curated ChEMBL CYP1A2/2C9/2D6/3A4 records, optional PubChem confirmatory assays, exact licenses, assay provenance, dates, units, organism and assay-format fields.

**Split:** canonicalize and componentize the union of challenge and external structures. For every outer challenge fold, remove external exact duplicates, salts/tautomers/stereochemical equivalents, and analog-family members of held-out challenge components. Conservatively exclude external records first released after the challenge launch and exact matches to blinded-test structures.

**Metrics:** challenge-only family-held-out MA-ST-RAE and MAE. External validation is diagnostic, not an acceptance metric.

**Acceptance:** at least 0.025 macro MAE improvement, primary metric improvement of at least 5%, no endpoint harm above 0.020, and the effect survives an external-data ablation.

**Compute:** 80–250 GPU-hours plus substantial curation time.

**Expected uplift:** 0.015–0.060 absolute MAE, with high endpoint variability.

**Overfitting/leakage risk:** medium to high unless provenance and analog exclusion are exact.

**Simplest falsifier:** external pretraining improves random splits but not challenge family-held-out evaluation.

#### B6 — Similarity-aware global residual expert

**Targeted failure:** a purely global learner may leave locally smooth residual structure without justifying full local replacement.

**Change:** train a Tanimoto/kernel or nearest-neighbor model on **cross-fitted G0 residuals**, then add a heavily shrunk correction. This is distinct from TRACE because the target is the residual of a competent global model, not the entire anchor-to-query delta.

**Exact data:** family-safe OOF G0 predictions, training targets, fingerprints, similarity, neighbor dispersion, endpoint identity and global-ensemble uncertainty.

**Split:** residual targets must be generated OOF; no query component contributes to its own neighbors or gate calibration.

**Metrics:** paired component MAE and primary-metric improvement, with separate activity-cliff and low-support guardrails.

**Acceptance:** at least 0.015 component-MAE improvement, upper 95% paired bound below zero, and no cliff degradation above 0.010.

**Compute:** 50–300 CPU core-hours.

**Expected uplift:** 0.005–0.020 absolute MAE.

**Overfitting risk:** medium.

**Simplest falsifier:** no positive improvement-versus-coverage region exists when corrections are ranked by cross-fitted uncertainty.

---

## 4. TRACE failure diagnosis

### What the controls mean

The frozen experiment defines:

- **G0:** episode-specific MapLight refit with the one exposed measured anchor.
- **C0:** copy the measured anchor value.
- **C1:** copy the nearest complete training molecule’s value.
- **C2:** generic signed-Morgan ridge delta plus the measured anchor.
- **C3:** full structural TRACE features without measured anchor potency, added to a pure OOF global anchor estimate.
- **T0:** contextual ridge delta plus a class/exact/environment hierarchy, added to the measured anchor.
- **F0:** apply T0 to a deterministically shuffled valid training anchor.
- **F1:** apply T0 to the most structurally similar valid training anchor.
- **F2:** T0 with the categorical transformation hierarchy deterministically permuted.
- **A0:** transformation-class hierarchy only.
- **A1:** full hierarchy without contextual ridge.
- **A2:** contextual ridge without hierarchy.

Unavailable local predictions correctly fall back to G0. 

### Every frozen system

Lower is better.

| System | Component MAE | Worst-G0-decile MAE | Activity-cliff MAE | Interpretation |
|---|---:|---:|---:|---|
| **G0** | **0.432732** | 1.220224 | **0.515641** | Dominant overall baseline |
| T0 | 0.715892 | 1.049119 | 1.362892 | Some rescue where G0 is worst, catastrophic on cliffs |
| C0 | 0.816642 | 1.288206 | 1.735199 | Anchor value alone is poor |
| C1 | 1.024642 | **0.895843** | 1.244935 | Helps selected hard families but unusable globally |
| C2 | 0.712005 | 1.038078 | 1.375621 | Essentially tied with T0 |
| C3 | **0.684344** | 0.984104 | **0.982705** | Best local/control system, still far behind G0 |
| F0 | 0.994067 | 1.320516 | 1.106068 | Random wrong-anchor behavior is poor |
| F1 | 0.849322 | 1.206394 | 1.016965 | Similar valid anchor remains poor |
| F2 | 0.720401 | 1.041333 | 1.382996 | Permuting categorical hierarchy barely changes T0 |
| A0 | 0.818963 | 1.288206 | 1.703059 | Class hierarchy alone fails |
| A1 | 0.822376 | 1.288206 | 1.701652 | Full hierarchy alone fails |
| A2 | 0.714543 | 1.046464 | 1.368760 | Ridge-only result almost identical to T0 |

The near-equivalence of T0, C2, F2 and A2 is highly informative: the added hierarchy and exact/class semantics contributed little reliable out-of-family signal. C3’s improvement over T0 suggests that measured-anchor noise or anchor addition contributes to failure, but C3 remains 0.252 MAE worse than G0, so anchor noise is not the whole explanation. 

### Repeat and outer-fold behavior

Entries are **G0-minus-T0**; positive favors T0.

| Repeat | Fold 0 | Fold 1 | Fold 2 | Fold 3 | Fold 4 |
|---|---:|---:|---:|---:|---:|
| 0 | −0.503 | −0.300 | −0.206 | **+0.046** | −0.351 |
| 1 | −0.234 | −0.354 | −0.372 | −0.280 | −0.130 |
| 2 | −0.512 | −0.150 | −0.170 | −0.217 | −0.287 |

The sole T0-favorable cell is repeat 0, fold 3. There is no repeat-level reversal or evidence that one unlucky split caused the negative result. 

### Component behavior

Across 82 primary components:

- T0 is better in 21.
- G0 is better in 61.
- The top ten leave-one-component-out contrasts remain unfavorable to T0.
- The largest harmful components combine high local error with a high prevalence of activity cliffs.

Examples of the largest component-level degradations:

| Component prefix | Rows | G0 MAE | T0 MAE | T0−G0 | Cliff fraction |
|---|---:|---:|---:|---:|---:|
| `61b1a279…` | 8 | 0.526 | 2.928 | +2.402 | 0.938 |
| `2e2fd40f…` | 6 | 0.220 | 2.053 | +1.833 | 0.833 |
| `b51e2c18…` | 13 | 0.220 | 1.434 | +1.214 | 0.821 |
| `913a4108…` | 13 | 0.371 | 1.543 | +1.171 | 0.654 |

Examples of genuine local wins exist, including component improvements of approximately 0.55 and 0.49 MAE. This is why a competence-gated residual expert remains scientifically plausible. The favorable region is simply too sparse and poorly identified for unconditional local prediction.

### Activity cliffs are the dominant failure regime

| Stratum | Rows | G0 component MAE | T0 component MAE | T0−G0 |
|---|---:|---:|---:|---:|
| Activity cliff | 120 | 0.515641 | 1.362892 | **+0.847251** |
| Not a cliff | 300 | 0.413204 | 0.439688 | +0.026484 |

T0 wins only about 4.6% of weighted cliff rows, versus about 39.5% of non-cliff rows. On non-cliffs, local prediction is close enough to justify a tightly controlled residual experiment. On cliffs, the current local delta is not merely noisy; it is directionally dangerous.

### Similarity does not supply a usable competence rule

| Similarity bin | Rows | G0 MAE | T0 MAE | T0−G0 |
|---|---:|---:|---:|---:|
| 0.60–0.70 | 312 | 0.470404 | 0.759744 | +0.289340 |
| 0.70–0.80 | 84 | 0.375205 | 0.577894 | +0.202689 |
| ≥0.80 | 24 | 0.180090 | 0.569263 | **+0.389173** |

The highest-similarity group is the least favorable relative to G0. A simple Tanimoto threshold would therefore be scientifically unsupported.

### Support helps, but not enough

| Support | Rows | G0 MAE | T0 MAE | T0−G0 |
|---|---:|---:|---:|---:|
| Class-only | 383 | 0.430195 | 0.733689 | +0.303494 |
| Exact | 37 | 0.414341 | 0.517253 | +0.102912 |

Exact transformation support narrows the deficit but does not reverse it. Support counts are weak proxies for reliability because they count structurally matched components, not target consistency, assay precision, delta variance or cliff probability.

### Extraction and query rank

`VALID_SINGLE` and `VALID_DOUBLE` rows both show substantial degradation. There is no evidence that double-cut extraction alone explains failure:

- `VALID_SINGLE`: approximately +0.261 T0-minus-G0
- `VALID_DOUBLE`: approximately +0.244

Query rank is sparse and non-monotonic; later ranks are often worse, but there is no stable cutoff that can be preregistered from this result.

### Selected versus random anchors

In the deterministic random-anchor stress population:

- G0: 0.426711
- T0: 0.684498
- C3: 0.644715

Random-anchor T0 was actually better than selected-anchor T0, although still much worse than G0. This rejects “the selected anchor was simply the wrong one” as the primary diagnosis. It also undermines learned anchor selection as a standalone repair.

### Inner selection instability

For T0, the association between inner selected-candidate performance and outer performance was strongly negative:

- Pearson: approximately **−0.795**
- Spearman: approximately **−0.804**

The selected alpha/lambda combination with apparently better inner evidence often performed worse outside. That is consistent with a small, highly correlated family sample and an unstable selection objective. It argues against expanding the hyperparameter grid before improving the model target and competence boundary. 

### Safety fusion

The frozen 50/50 safety fusion did not make TRACE safe:

- all-row G0: 0.437195
- all-row fusion: 0.485796
- primary-eligible G0: 0.432732
- primary-eligible fusion: 0.486985

Fallback was functioning correctly: ineligible rows were exactly G0. The defect is the **0.5 weight on eligible rows**, which is far too large for a weak and heavy-tailed local expert.

### Causal assessment

| Proposed cause | Assessment |
|---|---|
| Noisy measured anchors | **Material contributor**, supported by C3 outperforming T0 |
| Bad selected anchor | **Not primary**; random-anchor stress was no worse |
| Local deltas less stable than absolute predictions | **Primary cause** |
| Insufficient shrinkage | **Primary cause** |
| Ridge representation mismatch | **Likely material** |
| Hierarchy overfit | **Secondary; hierarchy adds almost no outer signal** |
| Transformation extraction defect | **Not supported by current evidence** |
| Weak support estimates | **Primary gating defect** |
| Analog-family reconstruction defect | **No decisive evidence** |
| Fallback behavior | **Correct** |
| Local/global fusion | **Defective weight, not defective fallback** |
| Failure to identify competence | **Central deployment failure** |

---

## 5. Ranked TRACE v2 proposals

All existing R5D rows must be treated as development evidence. No TRACE v2 candidate should be called confirmatory until it is evaluated once on a newly sealed family/component holdout that was unavailable during candidate development.

### 1. Cross-fitted, default-to-global residual gate

**Model:** retain G0. Train a local model to predict only the cross-fitted G0 residual. Train a separate competence model to estimate whether applying that residual is likely to reduce absolute error. Limit the correction weight initially to `[0, 0.25]`; permit exactly zero.

Useful score-free gate inputs include:

- global-ensemble disagreement;
- local-model variance;
- neighbor residual dispersion;
- anchor CI width or assay uncertainty;
- exact/class support;
- transformation type;
- distance to the training representation;
- disagreement among multiple anchors;
- a cross-fitted activity-cliff probability.

**Why it addresses the failure:** it preserves G0 for most molecules and prevents the local system from replacing a much stronger global estimate.

**Falsifier:** no positive benefit-versus-coverage region on development folds, gate AUROC below 0.60 for local benefit, or the best 10–25% coverage region still worsens G0.

**Leakage control:** all residual labels and competence labels must come from OOF predictions. No held-out family member except the explicitly preregistered available anchor may contribute a target, scaler, support statistic, calibration map or neighbor residual.

**Selection isolation:** tune gate threshold and maximum weight in nested development folds; evaluate once on the sealed confirmatory family holdout.

**Deployment threshold:** at least 0.020 component-MAE improvement, paired upper 95% bound below zero, at least 10/15 favorable cells, no cliff degradation above 0.010, and no endpoint degradation above 0.015.

**Other endpoints:** use endpoint-specific gates. A CYP3A4-only gate cannot alter the other three endpoint columns until separately accepted.

### 2. Robust multi-anchor empirical-Bayes residual

**Model:** use 3–8 eligible training anchors rather than one. Each anchor produces a local residual estimate; combine them with a weighted median or Huber location. Weight by anchor measurement uncertainty, pair support, cross-fitted delta variance and local-model uncertainty. Shrink the aggregate toward zero:

\[
\hat y = G0 + w\,\hat r_{\text{local}},\qquad
w = \min(w_{\max}, \tau^2/(\tau^2+\hat\sigma^2)).
\]

Start with `w_max ≤ 0.25`.

**Why:** directly addresses noisy anchors, unstable single-anchor deltas and heavy tails.

**Falsifier:** even an oracle reliability weighting constructed strictly inside development folds cannot beat G0 on the sealed holdout.

**Leakage control:** anchor selection uses structure and training-only uncertainty estimates; no query outcome or same-family unexposed measurement is available.

**Selection isolation:** K, robust aggregation and shrinkage are inner-fold choices.

**Required improvement:** same threshold as proposal 1, with an additional requirement that gains survive removal of the single most influential anchor.

**Other endpoints:** deploy per endpoint only; no assumption that CYP3A4 anchor reliability transfers.

### 3. Conformal abstention with activity-cliff routing

**Model:** cross-conformally estimate an upper bound on the error difference between local and global experts. Use the local correction only when the upper bound is below a preregistered negative margin. A separately cross-fitted cliff-risk model can force abstention.

**Why:** the observed failure is concentrated in a high-risk regime and cannot be detected by similarity alone.

**Falsifier:** conformal confidence does not order actual local benefit, or empirical error control fails under family holdout.

**Leakage control:** calibration components are disjoint from model-fitting and final scoring components.

**Selection isolation:** target coverage and margin are fixed before the confirmatory fold is opened.

**Required improvement:** a positive net gain at at least 10% coverage, with no statistically detectable cliff harm.

**Other endpoints:** likely safe because abstention yields exact G0; recalibration is endpoint-specific.

### 4. Antisymmetric pair/Siamese residual model

**Model:** train a pair model with an enforced antisymmetry constraint:

\[
f(a,q)=-f(q,a),
\]

component-balanced pair sampling, transformation-specific regularization, and a target equal to the difference between cross-fitted global residuals rather than the full potency delta.

**Why:** the fixed ridge may be too restrictive, while direct delta learning without antisymmetry can learn inconsistent directions.

**Falsifier:** it cannot outperform kernel ridge or generic signed-Morgan residuals on nested family folds.

**Leakage control:** pairs are generated only within the current training partition; no pair crosses into a held-out component except the explicitly exposed prediction-time anchor/query relation.

**Required improvement:** at least 0.020 component MAE with a stable gain in at least two seeds and no cliff harm.

**Other endpoints:** feasible as a shared pair encoder with endpoint heads, but this is higher risk than proposals 1–3.

### 5. Local kernel or Gaussian-process residual expert

**Model:** Tanimoto or learned-embedding kernel over OOF global residuals, with predictive variance. Correct G0 only in low-variance neighborhoods.

**Why:** gives a simpler and more naturally uncertainty-aware local model than the current hierarchy.

**Falsifier:** low predictive variance does not identify a positive-benefit region.

**Leakage control:** all kernels, residuals and variance calibration are fold-local.

**Required improvement:** 0.015 absolute component MAE and no endpoint guardrail breach.

### Not recommended as a standalone TRACE v2

A more elaborate learned anchor selector should **not** be the first repair. The random-anchor stress result and negative inner/outer association show that anchor selection alone is unlikely to solve the instability.

---

## 6. Ranked non-TRACE methods

The gain and probability columns below are audit judgments, not measured results. “Gain” means expected reduction in honest family-held-out component MAE.

| Rank | Method | Likely gain | Evidence | Implementation | Compute | Provenance risk | Leakage risk | P(beat baseline) | P(survive family holdout) |
|---:|---|---:|---|---|---|---|---|---:|---:|
| 1 | Cross-fitted heterogeneous global stack | 0.020–0.050 | High | 2–4 days | CPU-heavy; 10–30 GPU h | Low | Low–medium | 0.70 | 0.65 |
| 2 | Public external CYP transfer with assay-aware fine-tuning | 0.015–0.060 | Medium-high | 4–8 days | 80–250 GPU h | Medium | Medium-high | 0.65 | 0.50 |
| 3 | Masked four-isoform multitask model | 0.010–0.035 | High | 3–5 days | 30–100 GPU h | Low | Low–medium | 0.60 | 0.55 |
| 4 | Interval-distribution / MA-ST-RAE-aware model | 0–0.010 MAE; 3–10% metric | Medium-high | 1–3 days | Low–moderate | Low | Low | 0.55 | 0.60 |
| 5 | Frozen CheMeleon/MiniMol/MolFormer embedding stack | 0.010–0.035 | Medium | 2–4 days | 10–40 GPU h | Low–medium | Low | 0.52 | 0.47 |
| 6 | Chemical-domain mixture of experts | 0.010–0.035 | Medium | 5–8 days | Moderate | Low | Medium | 0.45 | 0.40 |
| 7 | Kernel/retrieval residual expert | 0.005–0.020 | Medium | 1–3 days | CPU | Low | Medium | 0.42 | 0.42 |
| 8 | 3D Uni-Mol or conformer ensemble | 0–0.030 | Medium-low | 5–10 days | GPU-heavy | Low–medium | Medium | 0.35 | 0.32 |
| 9 | Protein-aware docking or CYP-pocket features | 0–0.025 | Low–medium | 1–2 weeks | High | Medium | Medium | 0.28 | 0.25 |
| 10 | Analog-campaign reconstruction or generative pretraining | 0–0.020 | Low | 1–2 weeks | High | Medium | **High** | 0.25 | 0.20 |

OpenADMET’s recent foundation-model work is a useful caution: broad molecular pretraining did not produce an across-the-board statistically significant improvement, while targeted dense pretraining and selected embedding/surrogate representations produced modest gains on some endpoints. Foundation representations should therefore enter as ensemble features, not as an assumed replacement for strong fingerprints and trees. 

---

## 7. Three highest-value immediate experiments

### 1. EXP-G2 — Heterogeneous cross-fitted global stack

This dominates because it attacks model variance, representation limitations, parameter underexploration and calibration simultaneously without requiring external provenance work. It is also likely to produce useful OOF uncertainties for every later gate.

### 2. EXP-M1 — Masked four-isoform multitask interval model

This dominates because the current approach discards most missing endpoint cells, the four targets share CYP-inhibition chemistry, and the official metric directly incorporates credible intervals. It supplies an orthogonal neural/shared-representation expert for the stack.

### 3. EXP-X1 — Provenance-first external transfer

This has the largest plausible upside. It is ranked third for execution—not scientific value—because assay harmonization, duplicate exclusion and provenance auditing are substantial and can easily create a misleading random-split gain.

TRACE v2 is experiment number four. That ordering is a consequence of the evidence, not a lack of interest in local methods.

### Shared preregistration boundary

- **Development componentization seed:** `2026082401`.
- **Model seed set:** `2026082411` through `2026082415`.
- **Bootstrap seed:** `2026082499`; 2,000 accepted component replicates.
- **Confirmatory split:** generated from a 256-bit seed whose SHA-256 commitment is committed before implementation. The seed remains in a protected CI/reviewer capability until the candidate code, hyperparameters and model receipts are frozen. It is revealed once, used once, and archived.
- **Primary metric:** endpoint-macro, family/component-macro training proxy of MA-ST-RAE.
- **Secondary:** component MAE, endpoint MAE, Spearman, Kendall, calibration and interval coverage.
- **Generic rejection:** paired upper 95% bound includes zero or an endpoint guardrail is breached.
- **Generic reversal:** later independent evidence shows degradation above 0.015 MAE or validator/metric semantics drift.

### Compact preregistration register

| ID | Hypothesis | Frozen inputs and split | Comparator and budget | Acceptance / rejection / stop |
|---|---|---|---|---|
| **EXP-G1** | Tuned, bagged CatBoost improves fixed MapLight | Current direct data/features; nested component folds | G0; 300–1,200 CPU core-h | Accept ≥0.015 MAE and ≥3% primary gain; reject otherwise; stop on outer-fold tuning access |
| **EXP-G2** | Diverse models/features yield complementary errors | Direct data plus frozen deterministic feature blocks/embeddings | G0 and EXP-G1; 1,000–4,000 CPU core-h, 30 GPU-h | Accept ≥0.025 MAE, ≥5% primary, 10/15 cells; reject if best blend cannot beat best constituent |
| **EXP-M1** | Shared four-CYP encoder exploits masked labels | Four direct endpoints, intervals, masks; union-family split | Independent endpoint models; 30–100 GPU-h | Accept ≥0.020 macro MAE, two endpoints improve, no endpoint >0.020 worse |
| **EXP-I1** | Interval-aware loss better matches official metric | Central, lower, upper, std; nested calibration | Same architecture with central MAE; 10–30 GPU-h | Accept ≥5% primary gain, MAE degradation ≤0.005 |
| **EXP-X1** | Public external transfer adds domain coverage | Pre-launch public CYP records with assay metadata; per-fold analog exclusion | EXP-G2/M1 without external data; 80–250 GPU-h | Accept ≥0.025 MAE and gain survives external ablation; stop on unresolved provenance |
| **EXP-R1** | OOF residual retrieval corrects smooth global errors | OOF global residuals and fingerprints | EXP-G2; 50–300 CPU core-h | Accept ≥0.015 MAE, no cliff harm; reject if no positive coverage region |
| **EXP-T1** | An abstaining local residual gate improves a small subset | New TRACE v2 contract and sealed holdout | Accepted global model; 100–500 CPU core-h | Accept ≥0.020 MAE, upper CI <0, 10/15 cells, no cliff harm |
| **EXP-T2** | Robust multi-anchor EB shrinkage controls anchor noise | Same as T1 plus training-only anchor CI/reliability | T1 and global; 100–300 CPU core-h | Accept only if gain survives anchor influence checks |
| **EXP-T3** | Antisymmetric pair model learns more stable residual deltas | Component-balanced training pairs, OOF global residuals | C2-style ridge, T1 and global; 30–100 GPU-h | Accept ≥0.020 MAE in two seeds; stop if pair reversal or cliff guardrails fail |

---

## 8. Private live leaderboard assessment

The official Space was still marked **Running** at the final check. Its leaderboard is rendered inside an iframe whose dynamic table was not exposed through the browser-accessible text representation used for this audit. Direct searches also did not expose an indexed prior-submission row. 

I checked at the beginning of the audit on August 23 and again at **2026-08-24 02:10:19 UTC**, more than eight hours later. I could not verify the row through the accessible representation. I am therefore reporting it as **unobserved**, not absent. 

| Requested field | Audit result |
|---|---|
| Exact leaderboard | Official CYP challenge Space  |
| Final check | 2026-08-24 02:10:19 UTC |
| Requested track | Direct inhibition |
| Prior submission visible | Not independently observable in accessible iframe text |
| Displayed score | Unverified |
| Rank | Unverified |
| Total ranked entries | Unverified |
| Percentile | Cannot calculate |
| Gap to first | Cannot calculate |
| Gaps to nearby competitors | Cannot calculate |
| Tie behavior | Not observable |
| Consistency with internal validation | Cannot assess without a score |
| Submission made during audit | No |

The official challenge design states that half of the test set is used for the live leaderboard, grouped by chemical series, while final evaluation uses the full blinded set; there is also a one-time intermediate full-set release after the September 24 deadline. Thus even a visible live score would remain secondary distribution-shift evidence, not a valid target for blend optimization. 

The requested 15–30-minute visual refresh cadence could not be reproduced through this interface because the table itself was inaccessible, although the final recheck occurred well beyond the requested two-hour observation window.

---

## 9. Autonomous workflow architecture

### Design principle

Use one deterministic Python state machine, not an agent swarm.

A minimal package layout would be:

```text
src/cypshift/workflow/
    model.py            # typed state, event and receipt objects
    state_machine.py    # transition reducer and invariants
    hypotheses.py       # experiment-spec validation
    execute.py          # deterministic experiment runner
    evidence.py         # aggregation, bootstrap, acceptance
    candidate.py        # candidate freeze and rehearsal
    competition.py      # rule/validator snapshot
    submit.py           # disabled uploader
    scheduler.py        # 12.5-hour wake loop
    ledger.py           # append-only hash-chained events
```

Use the existing typing and validation toolchain where available; otherwise prefer `dataclasses`, enums, `pathlib`, canonical JSON and standard-library SQLite over a new orchestration dependency or service.

### State machine

The only accepted forward path is:

```text
HYPOTHESIS_DRAFTED
→ PREREGISTERED
→ IMPLEMENTED
→ SYNTHETIC_VALIDATED
→ INTERNAL_EXPERIMENT_RUNNING
→ INTERNAL_EVIDENCE_COMPLETE
→ CANDIDATE_REJECTED | CANDIDATE_ACCEPTED
→ REHEARSAL_1
→ REHEARSAL_2
→ SUBMISSION_VALIDATED
→ SUBMISSION_ELIGIBLE
→ SUBMITTED
→ LEADERBOARD_OBSERVED
→ ARCHIVED
```

Every transition consumes an immutable receipt and emits a new immutable receipt. No command directly edits the current state; the current state is reduced from the append-only event log.

### Core receipt types

**ExperimentSpec**

- experiment ID and hypothesis;
- source revision;
- exact input hashes;
- split and model seeds;
- candidate grid;
- metrics and aggregation;
- acceptance, rejection and reversal criteria;
- resource ceiling;
- prohibited capabilities;
- external data provenance.

**RunReceipt**

- experiment-spec hash;
- source revision and dirty-state assertion;
- environment/lockfile hash;
- input and output hashes;
- process exit status;
- seeds;
- resource consumption;
- warnings and guardrail outcomes.

**EvidenceReceipt**

- exact scored-population hash;
- comparator and candidate;
- paired estimates and intervals;
- per-cell outcomes;
- guardrails;
- accepted/rejected state;
- no raw predictions or targets in the Git-tracked form.

**CandidateManifest**

- model and code receipts;
- training-data receipts;
- candidate CSV SHA-256;
- validator version and result;
- two rehearsal receipt hashes;
- byte-identity assertion;
- prior-candidate inequality assertion.

**SubmissionReceipt**

- candidate hash;
- validator hash/result;
- API contract revision;
- accepted-upload timestamp;
- remote identifier and response hash;
- processing state;
- redacted authentication result.

### Capability separation

1. **Research capability:** can read training labels and public structures, fit models, and write candidate artifacts outside the worktree. It cannot read an HF token.
2. **Confirmatory scorer:** can open the sealed holdout only after candidate lock. It returns aggregated evidence, not row-level errors, to the development process.
3. **Submission validator:** reads frozen candidate bytes and the official test schema. It cannot fit a model.
4. **Uploader capability:** reads exactly one eligible CSV and manifest plus the runtime token. It cannot read training targets, development artifacts or arbitrary filesystem paths.
5. **Leaderboard observer:** records coarse ranking information but cannot write candidate-selection state.

### Determinism and no-replace publication

- Canonical JSON with sorted keys, finite numbers and one trailing newline.
- Exact environment and source revision receipts.
- All RNGs explicitly seeded.
- Output written to a temporary directory, hashed and atomically renamed.
- Destination must not exist.
- Symlinks and paths outside an approved root are rejected.
- Two rehearsals run in independent roots and must produce byte-identical CSVs.
- Predictions, external data and model weights stay outside Git; Git receives only contracts, code, aggregate evidence and hashes.

### Leaderboard firewall

Leaderboard observations can trigger:

- a catastrophic-failure stop;
- review of a previously preregistered distribution-shift hypothesis;
- prioritization among experiment **classes** that were already preregistered.

They cannot:

- choose blend weights;
- select per-molecule corrections;
- infer labels;
- generate pseudo-targets;
- reactivate rejected TRACE v1;
- rank a collection of arbitrary uploaded variants.

---

## 10. Submission automation threat model

### Scheduler behavior

The scheduler wakes every 12.5 hours, but the clock alone never authorizes an upload.

A wake cycle must:

1. Acquire an exclusive scheduler lock.
2. Verify the workflow is explicitly armed.
3. Fetch and hash the current official rules, validator and Space/API contract.
4. Confirm one-account/team limits and upload cadence have not changed.
5. Confirm an organizer-approved API or Space mechanism exists.
6. Confirm no earlier upload remains in an indeterminate or processing state.
7. Confirm `SUBMISSION_ELIGIBLE`.
8. Confirm candidate bytes differ from every prior submitted hash.
9. Re-run the frozen validator.
10. Verify the two rehearsal hashes equal the candidate hash.
11. Verify at least **12 hours 30 minutes** have elapsed since the previous accepted upload.
12. Retrieve a least-privilege token from the runtime secret store.
13. Upload exactly once.
14. Save the redacted remote receipt and response hash.
15. Stop on any ambiguity.

Default behavior is `--dry-run`. Live upload requires one explicit protected action such as a reviewed, signed `ArmReceipt`. The arm receipt should be candidate-specific or expire after one accepted upload.

### Threats and controls

| Threat | Consequence | Required mitigation |
|---|---|---|
| Token printed, logged or committed | Account compromise | Fine-grained token; secret store only; redaction tests; never pass token on CLI |
| Prompt/model-output exfiltration | Credential disclosure | Uploader has no LLM/model interface; token never enters prompts |
| UI scraping/password automation | Rule/TOS breach | Prohibited; refuse live mode without approved API |
| Rule drift | Ineligible submission | Hash current rules every wake; stop on change |
| Validator drift | Invalid candidate | Pin and re-run current official validator; stop on hash change pending review |
| Duplicate candidate | Wasted upload/leaderboard probing | Global hash index; reject any prior candidate hash |
| Race between schedulers | Double upload | OS/file lock plus transactional SQLite state |
| Clock skew | Cadence violation | Use server/remote accepted timestamp and monotonic local timing |
| Ambiguous API response | Unknown duplicate or state | Record response; set `STOPPED_AMBIGUOUS`; no retry |
| Prior submission processing | Overlapping submissions | Require explicit terminal remote state |
| Partial/corrupt candidate | Wrong predictions | Hash after durable write; immutable file descriptor; size/schema checks |
| Symlink/path substitution | Arbitrary file upload | Resolve and validate regular file under candidate root |
| Test-label capability leakage | Scientific invalidity | Uploader and feature builder cannot read labels; capability tests |
| Leaderboard overfitting | Hidden-test exploitation | Observer cannot alter candidate or stack-weight state |
| External-data hidden overlap | Leakage | Fold-specific union componentization and provenance receipts |
| Dependency compromise | Reproducibility/security failure | Lock hashes, trusted index, CI provenance, no unreviewed dependency |
| CI artifact exposure | Prediction/token leak | Private restricted artifacts, short retention, no fork-secret access |
| One-team/account violation | Disqualification | Account/team identity frozen in competition contract |
| Remote receipt mismatch | Wrong candidate attributed | Compare local candidate hash, remote ID, timestamp and response hash |
| Unauthorized go-live | Accidental submission | Disabled build default plus protected one-shot arm action |

Hugging Face recommends fine-grained tokens and secret storage rather than exposing tokens in shell commands or public variables. Those controls are necessary but not sufficient; organizer approval of the challenge-specific upload mechanism remains the go-live prerequisite. 

---

## 11. Proposed repository milestones and PR sequence

### PR 0 — Audit and contract refresh

- Add this audit as a dated strategy record.
- Record the independent TRACE reductions and command-level limitations.
- Update `PROJECT_STATE.md`.
- Record the decision that TRACE v1 remains rejected.
- Record that automation is disabled pending API/rule approval.
- No model changes.

### PR 1 — Experiment/evidence state machine

- Typed state and receipt objects.
- Canonical JSON and hash-chain ledger.
- Transition tests.
- Synthetic fixtures.
- Capability-root and no-replace tests.
- No uploader.

### PR 2 — New family-safe experiment harness

- Union componentization.
- Nested and sealed confirmatory split support.
- MA-ST-RAE training proxy.
- Paired component bootstrap.
- Per-endpoint guardrails.
- Experiment-ledger integration.

### PR 3 — Global v2 tree and feature ensemble

- Tuned CatBoost bagging.
- LightGBM/XGBoost experts.
- Alternative fingerprint blocks.
- OOF prediction and uncertainty receipts.
- Frozen stacker.

### PR 4 — Multitask and interval-aware models

- Masked four-endpoint loss.
- Credible-interval loss.
- Auxiliary assay heads.
- Deterministic neural training.
- Embedding provenance.

### PR 5 — External-data transfer lane

- External manifest and license checks.
- Standardization and assay-context schema.
- Fold-specific duplicate/analog exclusion.
- External ablation.
- No raw external data committed.

### PR 6 — TRACE v2 as a new hypothesis

- New name and contract; do not mutate R5D.
- Gated OOF residual model.
- Cliff abstention.
- Robust multi-anchor option.
- Separate CYP3A4 acceptance.

### PR 7 — Candidate freeze and rehearsals

- Candidate manifest.
- Independent two-root rehearsal.
- Official validator wrapper.
- Exact hash and byte comparison.
- Submission remains disabled.

### PR 8 — Disabled uploader and scheduler

- Dry-run only in CI.
- Mock approved API.
- Rule/validator drift tests.
- Secret-redaction tests.
- Duplicate/race/ambiguous-response tests.

### PR 9 — Go-live arming

Only after:

- organizer-approved automation mechanism is documented;
- rules are revalidated;
- one candidate has passed all gates;
- security review is complete;
- the arm action receives explicit human review.

Each PR should consist of small signed commits and update the experiment ledger and material decisions. Negative experiments remain first-class archived results.

---

## 12. Compute, time and resource estimates

| Workstream | CPU | GPU | Working storage | Typical execution |
|---|---:|---:|---:|---|
| Reproduction, splits, metric harness | 50–150 core-h | none | 10–20 GB | <1 day |
| Tuned/bagged MapLight | 300–1,200 core-h | none | 20–40 GB | 0.5–2 days |
| Heterogeneous global stack | 1,000–4,000 core-h | 10–30 h | 40–100 GB | 2–4 days |
| Masked multitask model | 100–300 core-h | 30–100 h | 30–80 GB | 2–5 days |
| Interval-aware objectives | 100–400 core-h | 10–30 h | 20–40 GB | 1–3 days |
| External-data curation and transfer | 300–1,000 core-h | 80–250 h | 100–250 GB | 4–8 days |
| Retrieval residual | 50–300 core-h | optional | 20–40 GB | 1–3 days |
| TRACE v2 gated residual | 100–500 core-h | 0–50 h | 20–50 GB | 2–4 days |
| Final robustness/rehearsals | 100–300 core-h | none | 20–50 GB | 1–2 days |

A credible two-week campaign budget is approximately:

- **5,000–15,000 CPU core-hours**
- **150–400 GPU-hours**
- **150–300 GB** temporary restricted storage
- one senior modeling owner and one reproducibility/software owner, even if those roles are held by the same person at different review gates.

The dataset is small enough that exhaustive neural architecture search is not warranted. Spend compute on repeated family-safe evaluation, representation diversity, external-data ablations and uncertainty calibration.

---

## 13. Explicit unknowns and blockers

1. **Private leaderboard row:** not observable through the dynamic iframe representation available to this audit.
2. **Challenge-specific automation permission:** generic Gradio API support exists, but unattended competition uploads were not explicitly authorized in the sources inspected.
3. **Approved submission endpoint:** endpoint name, request schema, authentication scope, processing-state semantics and remote receipt behavior remain unverified.
4. **Full local audit commands:** exact all-file `sha256sum -c` and the public audit pytest were not executed in this runtime.
5. **Confirmatory holdout:** a genuinely unknown TRACE v2/global-v2 holdout has not yet been created and sealed.
6. **Official metric parity:** the new internal metric implementation must be tested against organizer-provided examples or validator behavior before it becomes an acceptance authority.
7. **External-data provenance:** ChEMBL/PubChem assays require record-level assay and date decisions; “public” alone is not adequate provenance.
8. **External analog overlap:** a union chemical-component analysis has not yet quantified how much usable external data remains after conservative fold-specific exclusion.
9. **Prediction-time anchor policy:** any deployed multi-anchor TRACE v2 contract must state exactly which public training anchors are genuinely available for every blind-test query.
10. **Assay-context transfer:** the mapping between public assay formats and the Octant challenge assay may be the main external-transfer bottleneck.
11. **Current Space source revision:** it should be frozen immediately before any future submission rehearsal because the Space may change during the competition.

None of these block internal model development. Items 2 and 3 are hard blockers for live automation.

---

## 14. A 72-hour action plan

### Hours 0–6: freeze the new scientific boundary

- Record TRACE v1 as permanently rejected.
- Draft and commit the global-v2 and TRACE-v2 contracts.
- Freeze componentization logic, development split and confirmatory-seed commitment.
- Freeze the MA-ST-RAE training proxy and paired-bootstrap implementation.
- Add synthetic leakage and metric tests.

### Hours 6–18: generate reusable OOF evidence

- Reproduce fixed MapLight under the new harness.
- Generate family-safe OOF predictions for all four endpoints.
- Record per-endpoint calibration, ensemble uncertainty and residuals.
- Verify current results agree with accepted global receipts.

### Hours 18–36: run EXP-G1 and the first half of EXP-G2

- Tuned three-seed CatBoost screen.
- LightGBM and XGBoost over current features.
- Morgan radius/count alternatives and AtomPair/Torsion blocks.
- Compute model-error correlations.
- Reject redundant feature/model variants early.

### Hours 36–54: run EXP-M1

- Small masked multitask MLP over fingerprints/embeddings.
- Chemprop-style multitask model if the existing environment supports it cleanly.
- Central-MAE and interval-aware losses.
- Produce OOF predictions only; no stack selection from outer scores.

### Hours 54–66: cross-fitted stack

- Freeze the constituent set.
- Fit non-negative and ridge stackers inside nested folds.
- Evaluate per endpoint and by component, support, similarity and uncertainty.
- Run paired component bootstrap and seed sensitivity.

### Hours 66–72: decision and external-data manifest

- Accept or reject EXP-G1/G2/M1 under their contracts.
- Freeze the external-data source manifest and exclusion policy.
- Draft TRACE v2 T1 only if global OOF residuals show a positive local-benefit/coverage curve.
- Update project state, decisions and experiment ledger.
- Make no live submission.

---

## 15. A two-week competition strategy

### Days 1–3 — Global ensemble foundation

Complete the experiment harness, tuned tree experts, feature diversity, OOF uncertainty and cross-fitted stack. This should produce the first candidate plausibly superior to the prior private submission.

### Days 3–5 — Multitask and interval alignment

Train masked four-isoform models and interval-aware variants. Add them only if their OOF errors are sufficiently decorrelated and they improve the organizer-matched proxy.

### Days 4–8 — External transfer

In parallel:

- curate OpenADMET and ChEMBL CYP records;
- standardize units and endpoint semantics;
- assign assay contexts;
- componentize the union;
- implement fold-specific analog exclusion;
- run external/no-external paired ablations.

Do not allow an external random-split win to influence candidate acceptance.

### Days 8–10 — Global candidate consolidation

Freeze a small constituent set. Avoid dozens of arbitrary blends. Compare:

- best single tree ensemble;
- best multitask model;
- cross-fitted stack;
- stack plus external-transfer expert;
- interval-calibrated form.

### Days 10–11 — TRACE v2

Run only the default-to-global residual gate and perhaps robust multi-anchor shrinkage. Do not reopen the original T0 experiment, expand its hierarchy grid or tune on the published R5D rows.

### Days 11–12 — Robustness

- seed perturbation;
- component threshold perturbation;
- duplicate and tautomer policy perturbation;
- removal of influential families;
- assay-source ablations;
- endpoint-specific harm checks;
- metric and clipping sensitivity.

### Days 12–13 — Confirmatory evaluation

Freeze code and hyperparameters, reveal the protected confirmatory split seed, score once, and accept or reject exactly according to the contract. Do not return to model selection after the holdout is opened.

### Days 13–14 — Candidate freeze

- train the accepted model on all permitted training data;
- produce two byte-identical rehearsals;
- run the current official validator;
- freeze the SHA-256;
- review source revision, external disclosure and publication flags;
- update project state, decision records and ledger.

A live upload should occur only after the separate automation-permission/API blocker is resolved and the one-shot go-live action is approved. The 12.5-hour scheduler should not create a policy of submitting every 12.5 hours. A small number of substantively different, preregistered candidates is preferable.

---

## 16. Clear recommendation: what should be built first and why

### Build first

**Implement the family-safe OOF global-v2 ensemble harness and EXP-G2.**

Concretely:

1. Reproduce G0 in a new nested evaluation harness.
2. Add tuned, multi-seed CatBoost.
3. Add LightGBM and XGBoost over deliberately different fingerprint blocks.
4. Add one masked multitask model and one frozen public molecular embedding representation.
5. Select a small cross-fitted stack using the organizer-matched interval metric.
6. Produce calibrated OOF uncertainty and residuals for later routing.

This is the best first investment because it:

- targets several demonstrated baseline limitations at once;
- does not depend on speculative anchor competence;
- has high evidence strength in small molecular datasets;
- is comparatively fast;
- creates the OOF predictions required by every defensible TRACE v2 gate;
- remains useful even if external transfer and TRACE v2 fail.

### Build second

Add the masked four-CYP interval-aware model and public external-transfer expert. The external lane has the greatest potential winning upside, but it should not block the faster global ensemble.

### Build third

Build TRACE v2 as:

> **G0 plus a cross-fitted, uncertainty-gated, activity-cliff-abstaining residual correction, with a maximum initial local weight of 0.25 and exact G0 fallback for most molecules.**

Do not build another full local replacement, do not start with a richer hierarchy, and do not promote learned anchor selection ahead of competence estimation.

### Final competition stance

The repository’s scientific and deployment governance is already unusually strong. The principal weakness is not rigor; it is that the rigor has so far been applied to a relatively narrow global learner and an overambitious local replacement.

The simplest defensible winning strategy is therefore:

> **Preserve the governance, broaden the global model, exploit shared and external CYP information, align training with assay intervals, and permit local chemistry to contribute only where cross-fitted evidence shows that it can safely improve the global expert.**

# `cypshift` Phase 0.5 benchmark report

Status: final candidate for independent closeout review  
Evidence date: 2026-08-10  
Software version: `0.2.0.dev0`

## Executive summary

Phase 0.5 produced a reproducible public CYP benchmark without changing the
four-command product or adding deep-learning infrastructure.

The retained native system is the unweighted mean of four frozen CPU model
families: prior, ECFP linear, similarity kNN, and ExtraTrees. It improves on the
best single native family on all four held-out tasks. On the TDC fixed public
tests it reaches AUPRC 0.7484, 0.6547, and 0.8500 for CYP2C9, CYP2D6, and
CYP3A4. It remains 0.0286, 0.0183, and 0.0260 below the dated matching
Chemprop-RDKit anchors. No superiority claim is supported.

The one permitted series-residual test failed. It worsened full and
analog-supported performance on every task. The implementation was removed.
The one permitted CheMeleon transfer attempt failed inside the exact upstream
container before prediction. It was not patched or retried.

The main conclusion is practical: retain the simple native mean, retain the
data, split, metric, and reporting machinery, and carry no provisional series
or external-model component into the August 17 challenge freeze.

## Assay context

The two required tracks answer different questions and must remain separate.

| Track | Endpoint | Primary metric | Assay warning |
| --- | --- | --- | --- |
| OpenADMET Octant | CYP3A4 pIC50 regression | MAE | Active CYP3A4 preincubation used NADP+ with G6P/G6PD regeneration. This creates NADPH-generating metabolic conditions and is not the challenge minus-NADPH direct-inhibition endpoint. |
| TDC ADMET group | CYP2C9, CYP2D6, CYP3A4 Veith classification | Average precision | Fixed public benchmark labels and splits; results do not establish challenge performance. |

Regression and classification metrics are never combined. Octant and TDC
results are not ranked against each other.

## Data card

### Octant CYP3A4

- Source: `openadmet/Octant_CYP_inhibition_reactivity_blog_release`.
- Frozen revision: `96dc1cceaa545a22041d1e16a9c2524a658403f8`.
- Compound-table SHA-256: `19e537166a17a42dd50cc262dd6eb0a963c181830fdc52db0fba98533e01c9c6`.
- Canonical result: 1,340 molecule rows, 1,084 numeric pIC50 measurements,
  and 256 explicit missing-pIC50 omissions.
- Chemistry audit: 1,340 accepted, 0 quarantined, and 424
  unspecified-stereochemistry warnings.
- Split: 937 Bemis-Murcko groups in five 268-row folds. Fold 0 is the 212-row
  measured outer evaluation population; the other folds provide grouped
  training and inner validation.
- License policy: apply conservative CC-BY-4.0 attribution because the dataset
  metadata and body disagree.

### TDC Veith CYP tasks

- Source: Harvard Dataverse DOI `10.7910/DVN/21LKWG`, version 105.0.
- Archive SHA-256: `bd0005246cb6f1672333c28ad202112a8bf071ab65d847848715030308faf1f1`.
- Canonical result: 37,550 accepted rows across the three required tasks.
- Official split: 30,038 `train_val` rows and 7,512 public-test rows.
- Inner validation: four deterministic scaffold folds per task. No
  standardized structure or scaffold group crosses an inner fold.
- Leakage audit: standardization exposes 4 CYP2C9, 2 CYP2D6, and 1 CYP3A4
  official-test overlaps with `train_val`. Official populations are preserved;
  a separate strict companion excludes those seven rows.
- License policy: retain conservative CC-BY-4.0 attribution while disclosing
  that Dataverse version 105.0 declares CC0-1.0.

Exact sources, discrepancies, licenses, URLs, and hashes are in
[`public_sources.json`](public_sources.json).

## Split and evaluation policy

All candidate selection used grouped inner validation. The fixed TDC public
tests and the Octant outer fold were not used to choose configurations,
families, stack weights, or thresholds. Public-test evaluations are counted in
the experiment ledger. Official and strict TDC populations are reported
separately.

The exact-structure-grouped random companion made every learned family look
better. Octant MAE optimism was 0.0247 to 0.0347. TDC AUPRC optimism was 0.0100
to 0.0376. These values show why random validation was not used for selection.

## Model card

### Retained native model

The retained model is a fixed unweighted mean of four families:

1. prevalence or training-median prior;
2. ECFP logistic regression or ridge;
3. Tanimoto-weighted kNN;
4. ExtraTrees on fixed ECFP features.

All configurations were frozen using grouped out-of-fold predictions. The
nonnegative linear stack was rejected because it trailed the mean on all four
tasks. The retained system adds no learned fusion, calibration layer, deep
model, GPU dependency, service, or database.

Applicability fields in the research artifacts include nearest-neighbor
similarity, local support, local label variance, scaffold support, measurement
quality, uncertainty when available, and data/configuration/split hashes.

### Intended use

This system supports public benchmark rehearsal and experimental CYP prediction
research. It is not validated for clinical, regulatory, or safety decisions.
The Octant model result is specific to its active-preincubation assay context.
The TDC classification results are not direct-inhibition pIC50 predictions.

## Held-out scorecard

### Retained mean

| Task and population | Rows | Metric | Native | Chemprop-RDKit | Delta |
| --- | ---: | --- | ---: | ---: | ---: |
| Octant CYP3A4 outer | 212 | MAE | 0.5434 | not available | not comparable |
| TDC CYP2C9 official | 2,419 | AUPRC | 0.7484 | 0.7770 | -0.0286 |
| TDC CYP2D6 official | 2,626 | AUPRC | 0.6547 | 0.6730 | -0.0183 |
| TDC CYP3A4 official | 2,467 | AUPRC | 0.8500 | 0.8760 | -0.0260 |

The dated MapLight + GNN anchors are 0.859, 0.790, and 0.916. Native deltas are
-0.1106, -0.1353, and -0.0660. These are exact-split comparisons, not ranks
across different revisions.

### Strict overlap companion

| Task | Official AUPRC | Strict AUPRC | Rows removed |
| --- | ---: | ---: | ---: |
| CYP2C9 | 0.748408 | 0.748444 | 4 |
| CYP2D6 | 0.654672 | 0.654785 | 2 |
| CYP3A4 | 0.849966 | 0.849966 | 1 |

Removing the seven standardized overlaps changes no conclusion.

### Classification diagnostics

| Task | AUROC | MCC | Brier | ECE, 10 bins |
| --- | ---: | ---: | ---: | ---: |
| CYP2C9 official | 0.8748 | 0.5754 | 0.1471 | 0.1187 |
| CYP2D6 official | 0.8651 | 0.5273 | 0.1018 | 0.0952 |
| CYP3A4 official | 0.8747 | 0.5659 | 0.1603 | 0.1163 |

The thresholds were selected from grouped OOF predictions. Calibration is not
claimed to be production-ready.

### Octant diagnostics

The retained mean has median absolute error 0.3560, RMSE 0.8009, Spearman
correlation 0.6682, interval-aware MAE 0.4287, and potent-subset MAE 0.7520 on
37 potent compounds. This is an internal same-split comparison because no
matching public Octant reference is available.

## Series-support experiment

The only permitted fit-free residual moved the retained mean toward the
cross-fitted kNN estimate above nearest-neighbor Tanimoto 0.50.

| Task | Full gain | Supported gain | Supported 95% CI | Positive folds |
| --- | ---: | ---: | ---: | ---: |
| Octant CYP3A4 MAE | -0.003413 | -0.007895 | [-0.013694, -0.002567] | 0/4 |
| TDC CYP2C9 AUPRC | -0.005058 | -0.011519 | [-0.017135, -0.006226] | 0/4 |
| TDC CYP2D6 AUPRC | -0.007165 | -0.012577 | [-0.018014, -0.007804] | 0/4 |
| TDC CYP3A4 AUPRC | -0.005982 | -0.006895 | [-0.010489, -0.003895] | 0/4 |

All 17,561 remote rows abstained exactly. Both negative-control requirements
failed. Independent audit reproduced all 30,910 rows, 300 point evaluations,
80,000 bootstrap evaluations, and 32 intervals. The candidate is rejected and
its implementation is removed. No retry or replacement is permitted in Phase
0.5. The compact receipt is
[`series_residual_v1_rejection.json`](receipts/series_residual_v1_rejection.json).

## External-model attempt

The one pinned CheMeleon attempt verified all nine model files, audited 8,068
published training structures, and pulled the exact 7.72 GB linux/amd64 image.
Exact benchmark-structure overlaps were 8 CYP2C9, 13 CYP2D6, 8 TDC CYP3A4, and
4 Octant rows.

The four-row smoke failed before prediction because the upstream image imports
`DocumentModifiedShape` from an incompatible installed `botocore`. No smoke or
full prediction, label access, fit, evaluation, or score occurred. The attempt
was not patched or retried. The failure receipt is
[`chemeleon_attempt_v1_failure.json`](receipts/chemeleon_attempt_v1_failure.json).

## What worked, failed, and was removed

| Component | Outcome | Disposition |
| --- | --- | --- |
| Public source adapters and audit | Exact clean reconstruction passed | Retain |
| Grouped/scaffold validation | Leakage-safe inner folds and strict companion passed | Retain |
| Four-family native ladder | Reproducible public results | Retain |
| Unweighted mean | Best simple native combination on all tasks | Retain |
| Nonnegative stack | Trailed the mean | Reject; no learned stack retained |
| Random validation | Optimistic for every learned family | Diagnostic only |
| Series residual | Worsened all four tasks | Reject; implementation removed |
| CheMeleon transfer | Upstream environment failed before prediction | Reject; no retry |

## Limitations

- The challenge schema, metrics, data, and rules are not authoritative until
  August 17.
- Public TDC test labels are accessible. Evaluation counts and one-shot gates
  reduce, but cannot erase, test-overfitting risk.
- Public predictors may have training overlap. CheMeleon overlap was measured,
  but no external score was produced.
- Octant active preincubation is not the challenge direct-inhibition assay.
- The public benchmarks do not simulate every hidden analog campaign or future
  challenge endpoint.
- Windows and browser-rendered report presentation remain untested. Core CI
  covers Linux Python 3.11 and 3.14; the local wheel path was tested on macOS.

## Reproducibility and provenance

The source freeze has a one-command empty-root reconstruction documented in
[`README.md`](README.md). An independent live rerun reproduced 24 of 24 files,
source aggregate `0dc587c6`, and validation aggregate `b7f2d0f7`, with zero
model fits or public-test evaluations.

The final retained-mean scorecard has seven rows, 51 columns, and aggregate
`d07d52e6`. Its manifest SHA-256 is `f2478f59`. The family scorecard aggregate
is `03a3ee6c`; its manifest SHA-256 is `9f3ea56f`. Both scorecard roots have
byte-identical repeats. The tracked experiment ledger records every public-test
analysis, failed attempt, remediation, and negative result.

The report contains no raw structures, labels, predictions, or licensed source
rows. It can be reviewed from a clean clone using tracked records and hashes.

## Next decision

Stop Phase 0.5 modeling. Preserve the retained mean and the validated ingestion,
split, metric, artifact, and reporting components. On August 17, freeze the
official challenge release before adapting any schema or metric. Re-evaluate
assay semantics, external-data permissions, series definitions, and validation
groups from the authoritative release. Do not carry the rejected residual,
learned stack, or CheMeleon environment into Phase 1 automatically.

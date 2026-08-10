# Public benchmark contracts

`public_sources.json` is the tracked source-of-truth for Phase 0.5 public data.
It pins source revisions, URLs, licenses, file sizes, SHA-256 digests, row
counts, fixed TDC splits, dated leaderboard anchors, and external-model files.
Raw public data and generated benchmark artifacts stay out of Git.

`chemeleon_inference_contract.json` freezes the single allowed external-model
attempt. It binds the checkpoint, all required model files, the resolved
container digest, a stripped five-column model-facing projection, task
mappings, overlap audit, two-run reproducibility rule, eight declared scoring
analyses, budgets, and failure boundary before inference. The broader native
prediction-input molecule tables contain original outcomes inside provenance;
they are preparation inputs only and must never be mounted into the container.
The container receives only the audited stripped CSV. It stays isolated and
adds no core dependency or public CLI command.

Prepare that model-facing file before any checkpoint download or inference:

```console
uv run python scripts/prepare_chemeleon_inference.py \
  --prediction-inputs artifacts/benchmarks/native-prediction-inputs-v1 \
  --population-keys artifacts/benchmarks/native-retained-mean-predictions-v1 \
  --contract benchmarks/chemeleon_inference_contract.json \
  --out artifacts/benchmarks/chemeleon-input-v4 \
  --source-revision fc0bc842dd4bd75cb725bef4810431eb16a89edb
```

Two runs produce byte-identical five-column files with 7,724 rows. The CSV
SHA-256 is `9829a8adaa667419cccba78a9201dea3d08d0b68af3b0e4c08129d5a037dc7e4`;
the population-key SHA-256 is
`ebdc065fad80ec319799bff61837490af192297e7b039d7939e4d8f8a8d4c7e7`;
and the output aggregate is
`18332ea6c4a510c46ef393f865515d2111edf9fbe36572f8848b2c61a6d8a1a2`.
The receipt records zero measurement tables opened, outcome values parsed,
held-out labels parsed, native predictions consumed, model fits, or model
evaluations. Only `chemeleon_inference_input.csv` may be mounted read-only.
V2 remains a valid firewall artifact but is not inference-authorized because
contract v1 used prefixed task-mapping keys that did not match its exact task
values. Input v3 corrected that mapping, but its runner still trusted
unverified overlap provenance and caller-selected attempt paths. Contract v3
and input v4 bind one fixed input, output, start sentinel, clean Git revision,
and full overlap provenance. All five columns, 7,724 rows, task counts, key
hash, CSV hash, and aggregate remain unchanged. V4 contract SHA-256 is
`029d8f13135845629009bceffe365fd0d162f11c92a792b72b61def97712b472`.

The single contract-v3 attempt ran on 2026-08-09/10. The exact image pull and
all model hashes completed, but the four-row smoke failed before prediction.
The upstream CLI imports `boto3`, whose installed dependency imports a missing
`DocumentModifiedShape` symbol from `botocore`. No smoke or full prediction,
label access, fit, model evaluation, or score occurred. D-021 forbids a patch
or retry. The tracked failure record is
`benchmarks/receipts/chemeleon_attempt_v1_failure.json`; the complete local
root remains `artifacts/benchmarks/chemeleon-attempt-v1`.

`series_residual_contract.json` v2 freezes the final Phase 0.5 native experiment
before any candidate score exists. It permits one fit-free grouped-OOF
correction from the retained unweighted mean toward the retained kNN estimate
when nearest-neighbor Tanimoto is at least 0.50. It also fixes exact abstention,
negative controls, uncertainty, and an all-or-nothing keep/reject rule. It does
not authorize held-out access or a second residual design. V1 was rejected
before scoring because join, control, bootstrap, and strict tie semantics were
not fully specified; v2 closes those choices without changing the formula.

## Octant compound-level ingestion

The Octant adapter treats the 30-minute active-CYP3A4 preincubation assay as
its own endpoint. It does not relabel it as the challenge minus-NADPH direct
inhibition endpoint. The adapter preserves the source structure text, all
source values and QC fields in provenance, the DBOMF fluorescence context, and
the immutable dataset revision and file digest. The pinned protocol states that
100 uM NADP+ and a G6P/G6PD regeneration system are present during active
preincubation. This creates NADPH-generating metabolic conditions; it does not
mean that exogenous NADPH was directly added.

For component-level debugging after fetching the frozen inputs, reproduce the
retained Octant ingestion with:

```console
uv run python scripts/prepare_octant_benchmark.py \
  --source data/external/octant_cyp/96dc1cceaa545a22041d1e16a9c2524a658403f8/inhibition.tsv \
  --out artifacts/benchmarks/octant-source-freeze-v2
```

The frozen table has 1,340 unique molecule rows. All 1,340 pass the canonical
chemistry audit. Exactly 1,084 rows contain a numeric pIC50 and become canonical
measurements. The other 256 remain in the molecule table with an explicit
`missing_source_pIC50` provenance state; they are not fabricated as
measurements or silently discarded. Two clean runs produce byte-identical
adapter and audit artifacts.

This is an ingestion result, not a predictive-performance result. Model
selection and every TDC test evaluation remain pending.

## Empty-root reproduction

From the repository root, reproduce the complete source, ingestion, audit, and
validation freeze in one new output directory:

```console
uv run python scripts/reproduce_public_data_freeze.py \
  --out artifacts/benchmarks/public-data-reproduction-v1
```

The focused orchestrator fetches only the frozen Octant compound-level table,
its exact protocol, and the TDC ADMET archive; verifies every size and SHA-256
digest; prepares and audits both canonical datasets; freezes validation; and
writes a deterministic root receipt. It refuses an existing output directory.
On 2026-08-09, this command completed from an absent root in 61 seconds on a
local Apple CPU and reproduced the retained artifacts byte-for-byte. Its root
aggregate is
`0dc587c61b02f90df04e599deff771117ad52b5cfe16f10d606359bc8548d8d4`.
The receipt records zero model fits and zero public-test evaluations.

## Frozen public validation

For component-level debugging after preparing both canonical datasets, freeze
validation without fitting or scoring a model:

```console
uv run python scripts/freeze_public_validation.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --tdc-official-split artifacts/benchmarks/tdc-source-freeze-v2/adapter/official_split.csv \
  --tdc-adapter-manifest artifacts/benchmarks/tdc-source-freeze-v2/adapter/adapter_manifest.json \
  --out artifacts/benchmarks/public-validation-freeze-v2
```

The Octant contract assigns 1,340 rows in 937 Bemis-Murcko scaffold groups to
five exactly balanced 268-row folds. Fold 0 is the untouched outer validation
population; folds 1-4 are training and the four inner selection folds. Group
assignment does not use labels.

The TDC audit preserves all official train/test rows. Raw SMILES do not cross
train/test within any task, but canonical standardization reveals 3 structures
covering 4 test rows for CYP2C9, 2 covering 2 for CYP2D6, and 1 covering 1 for
CYP3A4.
Official scores will remain unchanged and will be accompanied by a separately
labeled strict score excluding those 7 hashed rows. The frozen audit records
zero public-test evaluations. TDC AUPRC is average precision and higher is
better; polarity tests guard against the contradictory lower-is-better footer.

Within each TDC `train_val`, scaffold groups are assigned without labels to
four row-balanced inner folds. All 30,038 `train_val` rows are assigned; no
public-test row, standardized duplicate, or scaffold group crosses an inner
fold. The audit validates every official split row against canonical task,
partition, source-row, source, and isoform provenance, and binds the split hash
to the adapter manifest.

`public_validation_manifest.json` hashes every retained split artifact and
records the exact aggregate-hash recipe. The frozen aggregate is
`b7f2d0f7d18bcc7d5815cdc3919a9681523ccf380246449c32e54b7c80465b12`.
The freeze performs zero model fits and zero public-test evaluations.

## Native selection contract

Native candidate selection is a separate benchmark-only workflow; it does not
add a public CLI command or a core runtime dependency. Install the locked
benchmark group, then run:

```console
uv sync --locked --all-groups
uv run python scripts/select_native_models.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --validation artifacts/benchmarks/public-validation-freeze-v2 \
  --out artifacts/benchmarks/native-selection-v1
```

The selection path verifies the complete validation receipt chain before any
fit. It parses only the 872 measured Octant inner-selection rows and the 30,038
TDC `train_val` rows. Octant outer labels and TDC public-test labels are not
parsed or evaluated.

The frozen four-family grid is deliberately small: one training prior; three
regularization values for a chiral 2,048-bit ECFP4 linear model; six
similarity-weighted Tanimoto kNN configurations; and three 128-tree ExtraTrees
leaf-size configurations. Classification uses pooled grouped-OOF average
precision; regression uses pooled grouped-OOF MAE. The retained stochastic
configuration is rerun with exactly three declared seeds. Generated selection
artifacts remain outside Git; their hashes and keep/reject decision enter the
experiment ledger after the first run.

Two real runs from signed commit `42ffaf1` are byte-identical. Each completes
240 grouped fits in about 216 seconds on a local Apple CPU and emits 401,830
candidate OOF rows, 123,640 retained OOF rows, and 92,730 stochastic-seed rows.
The retained linear configurations are Octant ridge alpha 10 and TDC logistic
`C=0.1`; all tasks retain Tanimoto kNN with `k=50`, power 2 and ExtraTrees leaf
size 3. Root aggregate
`33ba1f6481048c9f620223f9a0e6c85d2a40bece620ffe9b0c44117c0c7775fa`
binds the exact configuration and prediction artifacts. These grouped-inner
scores select candidates; they are not comparable to TDC public-test anchors.
The receipts still record zero held-out label parses and evaluations.

## Held-out prediction firewall

Held-out prediction and scoring are separate milestones. Independent review
found that prediction v1 never parsed or used a held-out numeric value but did
open and hash the complete canonical measurement tables before row filtering.
That interface did not satisfy the stronger structural claim. Preserve v1 as
rejected evidence; first materialize the source/split-authorized view:

```console
uv run python scripts/prepare_native_prediction_inputs.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --tdc-official-split artifacts/benchmarks/tdc-source-freeze-v2/adapter/official_split.csv \
  --validation artifacts/benchmarks/public-validation-freeze-v2 \
  --out artifacts/benchmarks/native-prediction-inputs-v1

uv run python scripts/predict_native_heldout.py \
  --prediction-inputs artifacts/benchmarks/native-prediction-inputs-v1 \
  --selection artifacts/benchmarks/native-selection-v1 \
  --out artifacts/benchmarks/native-heldout-predictions-v2
```

The preparation stage transparently scans 38,634 canonical measurement rows
and materializes exactly 30,910 authorized training rows plus all required
structures; it materializes zero held-out measurements. The model-facing
predictor accepts only that view and the frozen selection receipt. Prediction
v2 reproduces both v1 prediction CSVs byte-for-byte, including aggregate
`d9ca7e6d236a11fa031f485d68d05af5521b3a91e439ca154b9d08d9e4168b0d`.

## First held-out scorecard

Scoring attempt 1 parsed the 7,724 held-out labels but failed before calculating
or writing a score because of an incorrect leaderboard-manifest access path.
The ledger and
`benchmarks/receipts/heldout_scoring_attempt_1.json` retain the supported facts.
The latter is explicitly retrospective: the exact raw traceback was not
durably retained. A signed, CI-verified path-only remediation preceded attempt
2; no model, prediction, threshold, population, or metric changed.

Attempt 2 produced the first scorecard with aggregate
`2cc47a1600b5809a4317b8c8ec719bc702e43d6e6f9b335d0f189c3546720a1a`:

| Task | Best native family | Native | Chemprop-RDKit | MapLight + GNN |
| --- | --- | ---: | ---: | ---: |
| TDC CYP2C9 AUPRC | ECFP logistic | 0.7340 | 0.777 | 0.859 |
| TDC CYP2D6 AUPRC | ExtraTrees | 0.6474 | 0.673 | 0.790 |
| TDC CYP3A4 AUPRC | ECFP logistic | 0.8431 | 0.876 | 0.916 |

The strict seven-row leakage companion changes native AUPRC by at most 0.0006.
The best Octant grouped-outer result is ExtraTrees MAE 0.5489. These results
validate the benchmark path and strong classical baselines; they do not support
a superiority claim. Public reference comparisons retain the disclosed
standardization and fingerprint differences.

Independent review reproduced every point estimate but found scorecard v1 and
the retained OOF rows incomplete against the Phase 0.5 research-artifact
contract. Complete them without rerunning point scoring:

```console
uv run python scripts/complete_native_research_artifacts.py \
  --selection artifacts/benchmarks/native-selection-v1 \
  --predictions-v2 artifacts/benchmarks/native-heldout-predictions-v2 \
  --scores-v1 artifacts/benchmarks/native-heldout-scores-v1 \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --validation artifacts/benchmarks/public-validation-freeze-v2 \
  --public-sources benchmarks/public_sources.json \
  --oof-out artifacts/benchmarks/native-oof-research-v1 \
  --scorecard-out artifacts/benchmarks/native-heldout-scorecard-v4 \
  --source-revision bb4527c6f4d85363b26996b18d9386f0cfa16df7 \
  --selection-runtime-seconds 215 \
  --prediction-runtime-seconds 62 \
  --scoring-runtime-seconds 3.29 \
  --hardware "local Apple CPU (model unspecified)"
```

Scorecard v4 preserves all 28 v1 point rows and fields exactly. It adds dataset
revision, split and population hashes, runtime/hardware, explicit comparison
status, all public-reference standard deviations and deltas, and aggregation
warnings. Its allowed-seed ranges add 21 declared label-dependent analyses of
the already frozen three ExtraTrees seeds; they select no seed or model. The
scorecard aggregate is
`03a3ee6c1dc14b57c1c6cff47abf1d3e2f1b093e6aed7783b03cf984deb436bc`.
Scorecard v2 remains a rejected local candidate because its row-level warning
used the seven-row cross-task total on every task. V3 corrected the counts but
pluralized the one-row CYP3A4 case; v4 is the first accurate canonical
candidate and states both the task count (4/2/1) and seven-row total.
The 123,640-row OOF research artifact has aggregate
`5b9262fa2e178c1ea08d0660904f08f211dc297b72ef8b9f4eb95e79272844e6`.

## OOF-only combinations and random optimism

D-019 freezes the formulas, nested-fit isolation, stack complexity margin,
random-fold assignment, and later evaluation budget before this command runs:

```console
uv run python scripts/select_native_combinations.py \
  --prediction-inputs artifacts/benchmarks/native-prediction-inputs-v1 \
  --selection artifacts/benchmarks/native-selection-v1 \
  --out artifacts/benchmarks/native-combinations-v3 \
  --source-revision 06884441411c0eb274c47ec2688799b573dc24ba
```

Independent review rejected v1 because it opened complete canonical measurement
tables before row filtering. V2 fixed that interface but omitted the 20 NNLS
solves from its fit count. Both remain immutable rejected evidence. V3 accepts
only the label-absent prediction-input view and reports 384 base-model fits, 16
nested NNLS fits, 4 final NNLS fits, and 404 total operations. Its aggregate is
`c63b40b2c80981a437fdc2baa48d4ece5ecdc8b7e50594e75578cf04e8503b12`.
Two v3 roots are byte-identical across all eight files. Each contains 123,640
candidate OOF rows, 30,910 random assignments, and 123,640 random OOF rows,
while recording zero held-out label access or evaluations.

The unweighted mean is retained on all four tasks. Grouped OOF performance
changes from the best single family as follows:

| Task | Best single | Unweighted mean | Directional gain |
| --- | ---: | ---: | ---: |
| Octant CYP3A4 MAE | 0.6496 | 0.6344 | 0.0151 lower |
| TDC CYP2C9 AUPRC | 0.7527 | 0.7665 | +0.0137 |
| TDC CYP2D6 AUPRC | 0.6607 | 0.6723 | +0.0116 |
| TDC CYP3A4 AUPRC | 0.8293 | 0.8370 | +0.0078 |

The nested nonnegative stack is rejected on every task because it trails the
unweighted mean and therefore cannot clear the predeclared complexity margin.
The exact-structure-grouped random companion looks better for every learned
family: 0.0247-0.0347 lower MAE on Octant and 0.0100-0.0376 higher AUPRC on
TDC. These are validation-optimism diagnostics, not selection evidence or
public-test results.

The retained mean is applied in a separate label-free step:

```console
uv run python scripts/predict_retained_mean_heldout.py \
  --combinations artifacts/benchmarks/native-combinations-v3 \
  --base-predictions artifacts/benchmarks/native-heldout-predictions-v2 \
  --out artifacts/benchmarks/native-retained-mean-predictions-v1 \
  --source-revision 8b6bb9af0dad0e647f1dad4adb836e5c0b726bfa
```

Two runs produce byte-identical roots. Each root contains one prediction for
each of 7,724 held-out molecules and has aggregate
`b6e6db44f7436655cd978f181b326ef445fe39057430dae68ccb51afb2c5c873`.
The receipt binds combination v3 and held-out prediction v2. It records 30,896
base predictions averaged, zero fits, zero measurement tables opened, zero
labels parsed, and zero evaluations. These predictions remain unscored until
independent review passes.

After independent scorer review, the one authorized real scoring attempt used
the audited source split explicitly:

```console
uv run python scripts/score_retained_mean_heldout.py \
  --octant-canonical artifacts/benchmarks/octant-source-freeze-v2/canonical \
  --tdc-canonical artifacts/benchmarks/tdc-source-freeze-v2/canonical \
  --tdc-official-split artifacts/benchmarks/tdc-source-freeze-v2/adapter/official_split.csv \
  --validation artifacts/benchmarks/public-validation-freeze-v2 \
  --combinations artifacts/benchmarks/native-combinations-v3 \
  --predictions artifacts/benchmarks/native-retained-mean-predictions-v1 \
  --public-sources benchmarks/public_sources.json \
  --out artifacts/benchmarks/native-retained-mean-scores-v1 \
  --source-revision 925dccfa0f1c4966886a68af7c5c80a069ca6ca4 \
  --attempt 1
```

The raw score aggregate is
`e91329cca76159b42d9f539850420ecf1b960aafe66592148788001864064db0`.
The mean improves every prior native best: Octant MAE falls from 0.5489 to
0.5434; TDC AUPRC rises from 0.7340/0.6474/0.8431 to
0.7484/0.6547/0.8500. It still trails the Chemprop-RDKit public anchors by
0.0286/0.0183/0.0260 AUPRC. No superiority claim is made.

Canonical completion uses only the frozen scored receipt:

```console
uv run python scripts/complete_retained_mean_scorecard.py \
  --scores artifacts/benchmarks/native-retained-mean-scores-v1 \
  --validation artifacts/benchmarks/public-validation-freeze-v2 \
  --public-sources benchmarks/public_sources.json \
  --out artifacts/benchmarks/native-retained-mean-scorecard-v4 \
  --source-revision bd8024c202f6d14fb3cadca565641839cb1ad4f0 \
  --selection-runtime-seconds 215 \
  --combination-runtime-seconds 470.2 \
  --prediction-runtime-seconds 62 \
  --mean-prediction-runtime-upper-bound-seconds 1 \
  --scoring-runtime-seconds 2.94 \
  --hardware "local Apple CPU (model unspecified)"
```

V1-V3 remain rejected candidates for runtime and receipt-provenance clarity.
V4 has seven rows and 51 columns. Its two roots are byte-identical with
aggregate `d07d52e6b826c0f01e498c60330d163d747a09b4f4c5ba6a0e507b53bbd58afa`.
Completion records zero additional label access, evaluations, point changes,
or selection changes.

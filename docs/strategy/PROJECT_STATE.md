# Project state

Updated: 2026-09-05 UTC. Current integrated main: signed `dbb764b` (D-159),
locally fast-forwarded and pushed after all three PR #196 Python CI jobs passed.

## Active contract

[Phase 3 competition recovery](../phases/PHASE_3_COMPETITION_RECOVERY.md) is active.
The user authorizes autonomous implementation, strategy changes, useful agent
delegation, signed milestone commits/PRs/pushes and actual stronger submission
files. The user uploads manually. Target 3–4 qualified releases per week across
direct and TDI, approximately 24–32 additional entries before November 3.
Quality evidence and an actual validated CSV are required; arbitrary prediction
perturbations or revalidating an old baseline do not count as new entries.

D-151 supersedes former blanket no-repair/no-new-candidate backouts prospectively.
Completed contracts remain historical evidence. Read the phase, charter and
relevant [decisions](DECISIONS.md); do not execute archived one-use plans as the
active workflow. The user's earlier handoff edit remains byte-identical in
[the archived midnight handoff](../archive/intake/NEXT_ORCHESTRATOR_PROMPT_2026-08-31.md),
SHA `dcb9924b2d3b01e3b4c3b6171b423ced802ae5718c8f8ee1f891f29efb0e5c55`.

## Current recommendation and public observation

The interim recommendation is the affine-MAE direct release:
`/home/zbos/cypshift-private/openadmet-2026/submissions/direct-maplight-affine-20260905-v1/submission.csv`
SHA `c66c5f3f898745a0132f200373ca1a2af94f148598c5424c270628887d17436f`.
It has 750 rows / 3000 finite predictions and passes current checks. The user
confirmed its upload under **glhf**. No later upload file is ready.

Refreshed public observation: September 5 at 02:10 UTC, rank 107,
MA-ST-RAE **0.9335**, MA-MAE **1.0383**, R² **−0.0086**, Spearman **0.6302**,
Kendall **0.4533**. The saved August 24 entry had rank 107, primary 0.9366 and
MAE 1.0332: primary improves 0.33%, MAE worsens 0.0051, rank unchanged. This is a
modest improvement, not competitiveness. Public metadata does not expose the
uploaded CSV hash; association uses user confirmation and timestamp.

Two complete 80-fit grouped development repeats support affine calibration:
primary **0.7371456380 / 0.7290110589**, improving **2.6903% / 2.7477%** over
same-seed raw MAE. Paired-family difference intervals are entirely negative;
maximum endpoint component-MAE harms **+0.01733 / +0.01893** meet the +0.02 gate.
Macro component MAE worsens slightly. These are public-wrapper internal results,
not official scores. Total invocation CPU cost: 2.62255 core-hours.
See [handoff](../../benchmarks/openadmet_cyp_2026/PHASE3_RELEASE_HANDOFF.md) and
[repeat audit](../../benchmarks/openadmet_cyp_2026/phase3_maplight_affine_repeat2_audit.json).
Keep the first CSV and immutable historical manifests; do not average in the
second repeat's calibration. Production uses historical full-training predictions
with development-only calibration; training-size transfer is a disclosed limit.

The unchanged raw-MAE accepted CSV remains fallback, SHA
`9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`.
Historical fixed MapLight component-macro MAE 0.5837812652 is a different metric.
Final recommendation/promotion and the reserved comparison remain outstanding.

## Audit outcome and completed experiments

The [deep audit](../../benchmarks/openadmet_cyp_2026/PHASE3_DEEP_AUDIT.md) found no
catastrophic label/unit/endpoint/row-order/scoring/calibration bug: 46,896 raw
point/bound cells match; the real public wrapper agrees within 1.11e-16;
all 4905 historical train and 750 test feature rows reproduce hashes; affine CSV
bytes reproduce exactly. No reserved labels were decoded. Historical production
estimators were deleted, so their fresh reload cannot be claimed. Future models
must retain and freshly reload checkpoints.

Real weaknesses are compressed potent-tail predictions, sparse potent neighbors,
and validation that does not reproduce active-hit analog acquisition. All pIC50
>=6 OOF examples fall below their lower bounds in both MAE repeats. The 3908-row
development population has 3640 families and 90.28% singleton molecules. Support
audits find zero forbidden >=0.60 similarity crossings; roughly 72–84% of scored
rows lack a potent training neighbor at similarity>=0.30. These are descriptive
diagnostics, not instructions for prediction offsets or hidden-label inference.

Completed negative recipes; **do not rerun or create production CSVs**:

- RMSE:160 fits /2.63144 invocation CPU-core-hours. Raw is 3.74%/3.61% worse;
  affine 1.26%/0.93% worse than calibrated MAE. Recommendation and tail gates fail.
  [Results](../../benchmarks/openadmet_cyp_2026/phase3_rmse_ablation_v1_result.json).
- Tanimoto SVR:140 fits /0.00304 CPU-core-hours. Raw/affine 12.04%/9.63% worse
  on first repeat, positive paired difference intervals; retire without repeat 2.
  [Results](../../benchmarks/openadmet_cyp_2026/phase3_tanimoto_svr_v1_result.json).
- Corrected counts:160 fits /2.82403 invocation CPU-core-hours. Ten development
  Avalon cells really overflowed int8; full corrected-count/legacy-wrap/other-
  feature parity and all fit/inner-calibration receipts authenticate. Corrected
  affine is 0.39%/0.87% worse; raw 3.13%/3.47% worse. Neither variant qualifies.
  [Results](../../benchmarks/openadmet_cyp_2026/phase3_corrected_counts_v1_result.json).

TRACE R5D remains retired (G0 MAE 0.43273 versus T0 0.71589;1/15 favorable cells).
Historical maximum-potency parent selection also conditions query outcomes;
its negative result does not disprove every honest known-parent hypothesis.
A new identity assignment frozen before availability masks supports only a narrow
CYP3A4 diagnostic: 73 families/157 queries, at least 14 families per fold. Other
heads have 4/2/1 guaranteed same-endpoint-parent queries. No potency/parent was
selected. This is feasibility, not power or blinded-distribution validation.
[Receipt](../../benchmarks/openadmet_cyp_2026/phase3_known_parent_feasibility_v1.json).

## Ready data and hardware

Private root: `/home/zbos/cypshift-private/openadmet-2026/phase3`.
Development bundle `development-v1`, manifest SHA
`8fc2a8efbccf8aa185d6959eccd4190181e6eadad675e4e4a3e0a97bd34379bf`:
3908 molecules, 5197 finite direct labels. Seeds 20260905/20260906 and original
five outer/three inner family folds remain fixed.

Primary-screen preflight verifies 3493 development molecules ×4 enzymes =13972
finite log2fc estimates; 415 lack records. Preserve actual 49.5049505-µM context,
quote-aware prefixes and one row per molecule/enzyme; no aggregation or filtering
by response. All 3528 reserved rows plus 4 other rows were excluded before assay
response decoding. These are distinct auxiliary outcomes, not pIC50 labels.
[Coverage](../../benchmarks/openadmet_cyp_2026/phase3_primary_screen_coverage_v1.json).

Expanded family audit excludes 3 reserved-connected extra TDI molecules; 1237
eligible extras add **zero direct labels**. Existing development TDI labels have
267/622 positives across 265/566 families for CYP2D6/CYP3A4. Extras supply only
2/1235 negatives, respectively; other cells are missing. Freeze the TDI population
and extra-negative policy before classifier/threshold fitting; do not silently
pool them. [TDI coverage](../../benchmarks/openadmet_cyp_2026/phase3_tdi_class_coverage_v1.json).

Hardware: Ryzen 7950X, 16 physical/32 logical CPUs, 30.46 GiB host RAM;
Radeon RX 7900 XT/gfx1100, about 20 GiB VRAM. User authorizes 75% CPU and full GPU
compute. Shared `cypshift.slice` is verified at 24 CPU equivalents (`cpu.max`
2400000/100000) and 20 GiB host RAM (`memory.max`21474836480). Use cooperative
`taskset` CPUs 0–11, 16–27; cpuset is not delegated. Recheck after manager restart.
Retain 1000 CPU-core-hours/100GB private storage/no paid compute. Earlier frozen
CatBoost recipes stay 16-thread CPU-only; they cannot use the AMD GPU.

Verified private GPU interpreter: `gpu-readiness-v1/venv/bin/python`,
Python 3.12.3 / PyTorch 2.12.0+rocm7.14.0 / HIP 7.14.60850 / NumPy 1.26.4.
All 19 packages are pinned/hashed; matrix/backward/training/reload checks passed.
Final runtime storage 7.32 GiB after a recorded duplicate-cache repair. Do not
reinstall or rerun completed readiness/profile checks. No system driver changes.
[Readiness](../../benchmarks/openadmet_cyp_2026/phase3_gpu_readiness_v1.json) and
[throughput](../../benchmarks/openadmet_cyp_2026/phase3_mlp_synthetic_throughput_v2.json).

## Immediate execution

D-160 implements the [frozen three-arm GPU MLP](../../benchmarks/openadmet_cyp_2026/phase3_mlp_auxiliary_v1.json):
direct-only, genuine primary-screen auxiliary and shuffled auxiliary controls.
Same 4296→256→128→8 architecture, training-only transforms, matched randomness,
honest grouped stopping/fresh refits, inner-only affine; 105 joint fits per seed.
Each seed has one occupied hour/ten CPU-core-hours, including failed attempts.
Worker uses one CPU thread and a 2-GiB GPU allocator cap within the shared slice.

Five actual GPU synthetic fits and two CPU-to-GPU integration fits passed;
independent review authenticated all seven checkpoint/prediction pairs. Preserve
the failed initial optimizer-device reload test and its verified repair. Focused
tests cover family isolation, payload tampering, stopping/calibration lineage,
timeout cleanup and conservative accounting for unreaped descendant CPU.
[Verification](../../benchmarks/openadmet_cyp_2026/phase3_mlp_implementation_verification_v1.json).

Sign reviewed implementation, then run both frozen repeats while full PR CI runs.
Check private `active-compute.json`, result files and live processes first to avoid
duplicate work. Authenticate/recompute both-seed incumbent and auxiliary-control
gates with the comparator; independently replay retained checkpoint inference.
A qualified candidate needs separate production fitting and an actual validated
CSV. No new production model or upload is claimed by this prospective milestone.
All exact-head PR checks must pass before local fast-forward integration/release.

## Continuing boundaries

Keep all families together across direct/auxiliary/stop/assessment populations;
fit transformations, stopping, calibration and selection inside cross-fitting.
Preserve raw chemistry, assay context, censoring, missingness and provenance.
The 997-molecule reserved partition stays closed until one frozen final comparison
per track; disclose historical R3C/R5 reuse. No blinded-test geometry or public/
private leaderboard selection. Keep official/generated data, checkpoints and
predictions outside Git. Core CLI remains RDKit-only with its synthetic fixture.

Refresh source receipts before any release: latest observed dataset 3ac9c5d,
Space 453a39a, tutorial 858ae63. Direct columns require sample STD>=0.01; TDI
requires binary predictions containing both classes. User uploads manually;
respect 12-hour per-track spacing and distinguish readiness from submission.
The existing two-hour heartbeat reloads the public page, checks **glhf**, avoids
completed work and stays quiet on unchanged/non-actionable results. Notify for
actual files, meaningful changes, failures or required action.

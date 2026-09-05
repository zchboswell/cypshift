# Phase 3 — First calibrated direct submission

**Status:** generated, validated, implementation integrated after passing CI,
and manually submitted by the user under alias **glhf**. The refreshed public
leaderboard identifies the new entry as September 5 at 02:10 UTC.

## Manual upload file

Track: **direct inhibition**. Candidate: **MapLight with OOF-fitted affine
calibration**, now the recommended interim artifact after two frozen internal
repeats. The authenticated fixed MapLight baseline remains fallback.

[submission.csv](/home/zbos/cypshift-private/openadmet-2026/submissions/direct-maplight-affine-20260905-v1/submission.csv)

- SHA-256: `c66c5f3f898745a0132f200373ca1a2af94f148598c5424c270628887d17436f`.
- Verified readonly output: 750 rows and 3,000 finite predictions, with exact
  test identities and passing current variation checks.
- The adjacent `manifest.json` records input/output hashes, source refresh,
  validation, calibration parameters, evidence, and the transfer limitation.

The user submits manually. Honor the **12-hour interval per track**. The latest
valid direct entry replaces the previous direct entry. Final promotion remains
outstanding. Upload confirmation comes from the user; the newly displayed
timestamp confirms a refreshed entry, while the public page exposes no CSV hash.

## Internal evidence

These are **internal development results, not official competition scores**.
The frozen experiment used 3,908 molecules in 3,640 families, five outer and
three inner folds, and 80 MapLight fits. Calibration used inner OOF predictions;
evaluation used outer OOF predictions. All four endpoints improved on the
public-wrapper primary metric.

| Metric | Fixed MapLight | Calibrated challenger | Change |
| --- | ---: | ---: | ---: |
| Macro bootstrap-mean ST-RAE, lower is better | 0.757525 | 0.737146 | **2.6903% improvement** |
| Macro component MAE, lower is better | 0.584596 | 0.587758 | **+0.003162 worse** |

The separate 2,000-replicate paired-family bootstrap gives a 95% interval of
**[-0.026898, -0.013785]** for candidate-minus-baseline macro ST-RAE. Maximum
endpoint component-MAE harm is **+0.017333 pIC50**, on CYP3A4, within the
predefined +0.02 limit. Preserve the MAE tradeoff when interpreting the primary
metric gain. The first-repeat metric gate passes; final promotion is false.

The experiment completed in 482.09 seconds and used 1.29545 CPU-core-hours.
See the [aggregate result](phase3_maplight_affine_v1_result.json) for full values,
endpoint metrics, hashes, and accounting.

## Limits and follow-through

Deployment applies calibration fitted on development OOF predictions to the
authenticated historical baseline trained on all 4,905 training molecules.
The change in training size is a transfer limitation that this nested experiment
does not directly test. No reserved targets were opened for Phase 3 calibration
or selection; the 997-molecule reserved comparison remains closed.

The frozen second repeat confirms a **2.7477%** primary gain (0.749608 to
0.729011), paired-family 95% interval **[-0.027209, -0.014027]**, and maximum
endpoint component-MAE harm **+0.018932**. Macro component MAE worsens from
0.580383 to 0.583737. It used 80 fits, 505.77 seconds and 1.32710 CPU-core-hours.
An [independent audit](phase3_maplight_affine_repeat2_audit.json) reproduced
folds, boundaries, affine predictions and primary scores. This supports the
first release; no second-repeat parameters or post hoc averaging replace it.
The immutable creation manifest predates this confirmation and retains its
original challenger status. The active recommendation is recorded here.

Further component ablations and the final comparison remain outstanding.
Continue the planned count ablation and SVR evaluation without
using upload feedback for model selection. GIN readiness is a separate bounded
runtime/provenance milestone; historical TDC embeddings are not challenge data.

## Public monitoring

The saved previous entry was August 24 at 00:06 UTC: rank 107, MA-ST-RAE
0.9366, MA-MAE 1.0332. A page reload now shows **September 5 at 02:10 UTC**:

| Public metric | Previous | New |
| --- | ---: | ---: |
| Rank | 107 | 107 |
| MA-ST-RAE | 0.9366 | 0.9335 |
| MA-MAE | 1.0332 | 1.0383 |
| MA-R² | 0.0045 | -0.0086 |
| MA-Spearman | 0.6302 | 0.6302 |
| MA-Kendall | 0.4533 | 0.4533 |

The primary score improves approximately **0.33%** using displayed rounded
values; MAE worsens by 0.0051 and rank does not improve. This is a modest public
improvement, much smaller than internal validation. The existing heartbeat
checks every two hours and reports meaningful changes. Operational receipts
stay private under `phase3/monitoring`; public results never select parameters
or candidates. Source: [live leaderboard](https://huggingface.co/spaces/openadmet/cyp-challenge).

# Project state

Updated: 2026-09-04 (America/New_York).

## Active work

Phase 3 competition recovery is authorized by the user's approval of the audit
and plan, including autonomous implementation, signed milestone commits/pushes,
and regular ready-to-upload entries. The user performs manual submissions.
D-151 prospectively replaces the former blanket no-repair/no-new-candidate
backout rules. Historical scientific results and consumed attempts are unchanged.

Read [Phase 3](../phases/PHASE_3_COMPETITION_RECOVERY.md) for the complete
candidate menu, nested validation, resource budget and acceptance rules.
Target 3–4 qualified releases per week across direct and TDI, approximately
24–32 additional entries before the November 3 deadline. Every release needs
internal evidence and an actual validated private upload file. A repeated
baseline or arbitrary prediction perturbation does not count.

## Best evidence and current artifacts

- Fixed MapLight: development component-macro MAE **0.5837812652150708**;
  endpoint means 1A2 0.66733, 2C9 0.48997, 2D6 0.59855, 3A4 0.57927.
  Two complete development replays matched. This is not an official score.
- Historical direct candidate: 750 rows/3000 finite predictions; submission
  SHA-256 `9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`.
  Authenticated September 5 UTC; passes current identity, finiteness and
  sample-STD checks. Revalidation is not an additional entry.
- TRACE R5D: G0 MAE 0.43273 versus T0 0.71589, 1/15 favorable cells. Retired.
- G1/M1/X1/G3/G4 did not produce challenger model-quality evidence. G2-7G
  was a pre-fit support-predicate stop, not a scientific rejection of MapLight.
- Public GIN transfer results remain encouraging historical CYP benchmark
  evidence with disclosed overlap limitations, not challenge validation.

The source audit observed dataset head `3ac9c5d`, Space `453a39a`, tutorial
`858ae63`; only Emax dataset bytes changed relative to the former snapshot.
The Space now rejects near-constant direct columns (sample STD <0.01) and
single-class TDI columns. Current source receipts and production validation
are the first implementation milestone.

## Execution status

Base main: signed `ac043aaaf8dd3a7db1815859f7fa60f05c52277d` (D-150).
D-151 signed `3887805` integrated locally by fast-forward after PR #188 passed
all three Python CI jobs; pushed main. Full local historical suite: 1489 passed,
14 existing skips. D-152 signed `5bdf897` also integrated and pushed after all
PR #189 CI jobs passed.

D-153 through D-155 are integrated and pushed after all three Python PR CI
jobs passed (PRs #190–#192; main `8bffec2`). Two frozen 80-fit grouped repeats
support affine calibration: primary ST-RAE improvements **2.6903%** and
**2.7477%**, with paired-family difference intervals entirely below zero.
The maximum endpoint component-MAE harms are +0.01733 and +0.01893, within
the +0.02 gate. Macro component MAE worsens slightly in both repeats. These
are internal public-wrapper results, not official scores. Both runs together
used 2.62255 invocation CPU-core-hours; this excludes compilation and audits.
Independent aggregate, fold and calibration audits passed.

The recommended **interim** direct artifact is the first affine release:
`/home/zbos/cypshift-private/openadmet-2026/submissions/direct-maplight-affine-20260905-v1/submission.csv`
SHA-256: `c66c5f3f898745a0132f200373ca1a2af94f148598c5424c270628887d17436f`.
It has 750 rows / 3,000 finite predictions and passes current checks. The user
confirmed upload under **glhf**. A refreshed public observation now shows
September 5 at 02:10 UTC: rank **107**, MA-ST-RAE **0.9335**, MA-MAE **1.0383**.
The saved August 24 entry had rank 107, primary 0.9366 and MAE 1.0332: primary
improves 0.33%, MAE worsens 0.0051, rank unchanged. This is a modest public
improvement, not evidence of competitiveness or the internal 2.7% gain.
Private operational receipts and the existing every-two-hour heartbeat retain
comparisons. No leaderboard selection.
See the [release handoff](../../benchmarks/openadmet_cyp_2026/PHASE3_RELEASE_HANDOFF.md)
and [repeat audit](../../benchmarks/openadmet_cyp_2026/phase3_maplight_affine_repeat2_audit.json).
The unchanged fixed baseline remains fallback; final promotion is outstanding.
Do not replace the first CSV with second-repeat calibration parameters.

The preexisting user handoff edit is preserved exactly in
[the archived midnight handoff](../archive/intake/NEXT_ORCHESTRATOR_PROMPT_2026-08-31.md),
SHA-256 `dcb9924b2d3b01e3b4c3b6171b423ced802ae5718c8f8ee1f891f29efb0e5c55`.
Prior detailed state is available in Git at the base commit; completed Phase 2
chronology remains [historical reference](../phases/PHASE_2_OPENADMET_GLOBAL_V2.md).

## Boundaries

Preserve raw chemistry, assay context, missingness and provenance. Keep whole
families together across all tasks; learn calibration/stopping/stacking only
inside cross-fitting. The 997-molecule reserved partition stays closed until
one frozen final comparison per track; disclose its historical R3C/R5 reuse.
Private portal activity and results remain outside model selection. The user
uploads manually; readiness is not proof of submission. Prediction files,
features, models, raw data and credentials remain outside Git.

The public CLI remains audit/train/predict/report with RDKit-only runtime;
its median model is a product fixture baseline, not the competition model.
Use existing locked research environments. Budget: 1000 CPU-core-hours,
16 active threads, 20 GiB working memory, 100 GB private storage, no paid GPU.

## Next action

Integrate the repeat-confirmation and SVR evaluation milestone after review and
exact-commit CI. Then run the frozen 140-fit SVR comparison, first checking for
an existing process/result; profile its first real cell. If qualified, complete
its 28-fit development-only deployment and actual validated CSV. Finish the
small corrected-count ablation and bounded GIN provenance/runtime readiness.

The user explicitly authorizes a different strategy when evidence warrants it.
Revise prospective hypotheses, priorities and budgets using internal evidence,
resource costs and research; record consequential changes before new outcomes.
Do not treat the initial menu as a permanent restriction or reset historical
failures. Preserve family isolation, cross-fitting, the reserved barrier and
leaderboard-independent selection. Continue every two hours; notify for actual
new files, newly visible leaderboard results or meaningful issues.

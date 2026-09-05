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
  Authenticated September 5 UTC; passes current identity, finite and sample-STD checks. Revalidation is not an additional entry.
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
14 existing skips. D-152 signed `5bdf897` also integrated/pushed after all PR #189 CI jobs passed.
D-153 signed `3dd5509` completed80 fits in482.09s/1.29545CPU-core-hours.
First grouped repeat: baseline primary0.757525 -> affine0.737146 (2.6903%gain),
paired-family95% difference[-0.026898,-0.013785], maximum endpointMAEharm0.01733.
Macro componentMAE slightly worsens0.584596 ->0.587758. This is internal
public-wrapper evidence, not an official score. Second repeat remains pending.

New private upload file:
`/home/zbos/cypshift-private/openadmet-2026/submissions/direct-maplight-affine-20260905-v1/submission.csv`
SHA256 `c66c5f3f898745a0132f200373ca1a2af94f148598c5424c270628887d17436f`.
750 rows/3000 finite predictions pass current checks. Interim challenger;
first handoff waits for implementation CI/integration. Manual upload unconfirmed.
Frozen historical baseline remains recommendation pending stronger evidence.


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

Finish PRs #190/#191 and evidence milestone checks/integration. Run the frozen
second repeat at private `phase3/maplight-affine-repeat2` (seed20260906), checking
existing progress before starting a job. Then complete the count ablation and
SVR outer runner, retain successful OOF for blends, and prepare GIN readiness.
Notify the user with the actual CSV once the handoff gates are complete. Keep
manual upload feedback out of model selection. Continued work is scheduled every
two hours in this task; stay quiet unless a new file or meaningful issue is ready.

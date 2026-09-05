# Project state

Updated: 2026-09-05 UTC.

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
jobs passed (PRs #190–#192). D-156 is also integrated after PR #193 passed
all three jobs; main `0787661`. Two frozen 80-fit grouped repeats
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
Preserve existing locked research environments. The user now authorizes 75%
CPU usage (24 of 32 logical-CPU equivalents) and full local GPU compute for
future work. Keep 20 GiB aggregate host memory, 100 GB private storage and
1000 CPU-core-hours; no paid compute. Frozen RMSE/SVR recipes retain 16 threads.
The AMD gfx1100 GPU has about 20 GiB VRAM, but needs a separate verified
ROCm/PyTorch runtime. GPU preparation is distinct from official model training.

## Deep audit and revised priority

The user requested a substantial audit after the poor public result. The audit
found no catastrophic target, unit, endpoint, feature, row-order or scoring bug:
46,896 raw development point/bound cells match exactly; the real public wrapper
matches within 1.11e-16; all 4,905 training and 750 test feature rows reproduce
historical hashes; the affine CSV reproduces byte-for-byte. Reserved labels
remained closed. See [the deep audit](../../benchmarks/openadmet_cyp_2026/PHASE3_DEEP_AUDIT.md).

Real weaknesses: severely compressed OOF predictions, all pIC50 >=6 examples
below their lower bounds in both repeats, singleton-heavy validation that does
not reproduce analog acquisition, and deleted historical production estimators.
Historical maximum-potency anchor selection also conditions selector queries
to be weaker; retain that negative result without claiming all known-parent
hypotheses are disproved. Sparse signed-int8 Avalon overflow remains a real
separate ablation. TDI adds no direct labels on existing development identities.
Family-safe extra intake is now complete: 1,237 eligible extras have zero direct
labels; three reserved-connected extras were excluded before numeric decoding.
The independently rebuilt graph preserves all old development fold boundaries.
Support diagnostics verify all 3,908 standardized hashes and zero >=0.60
crossings. Approximately 72–84% of scored rows across both repeats lack a potent
training neighbor at similarity >=0.30. These descriptive findings do not
authorize prediction adjustments. See [the follow-up evidence](../../benchmarks/openadmet_cyp_2026/phase3_audit_followup_v1.json).

The signed D-157 audit and objective-ablation implementation (`cb4adda`) passed
all three PR #194 Python jobs, was integrated locally by fast-forward, and is
pushed to main. Both frozen RMSE repeats completed: 160 new fits / 2.63144
invocation CPU-core-hours. Raw RMSE is 3.74% / 3.61% worse than the calibrated
MAE incumbent; affine RMSE is 1.26% / 0.93% worse. Neither variant passes the
recommendation or potent-tail mechanism gates. Independent recomputation agrees.
No RMSE production fit or submission is warranted by these outcomes. See
[the matched results](../../benchmarks/openadmet_cyp_2026/phase3_rmse_ablation_v1_result.json).

The frozen Tanimoto SVR experiment also completed: 140 fits / 16.65 seconds /
0.00304 accounted CPU-core-hours. Raw and affine variants are 12.04% and 9.63%
worse than the first-repeat calibrated incumbent, with positive paired-family
intervals and endpoint harm above +0.02. Independent reconstruction verifies all
15,272,464 kernel entries exactly and reproduces inner C choices and metrics.
Retire this standalone recipe; no second repeat or production fit is justified.
See [SVR results](../../benchmarks/openadmet_cyp_2026/phase3_tanimoto_svr_v1_result.json).

## Next action

Signed D-158 (`d292c69`) passed all PR #195 CI jobs, was integrated locally by
fast-forward and pushed to main. Both independent experiment audits passed.
Do not repeat finished RMSE/SVR fits or spend another cycle on offsets alone.
The genuine sparse count overflow is the next isolated ablation; preserve the
legacy comparator. Its implementation and independent review are complete,
including proof that the reported affine coefficients come from authenticated
inner OOF predictions. The [frozen recipe](../../benchmarks/openadmet_cyp_2026/phase3_corrected_counts_ablation_v1.json)
uses the same MAE learner, two seeds and 80 fits per seed, capped at five
CPU-core-hours per seed. Run from the signed reviewed D-159 implementation after
focused checks, while full PR CI runs. Any release requires CI/integration,
both-seed incumbent gates and new saved/reloaded production estimators. No
corrected-count official fits or new CSVs are claimed by this prospective record.

GPU readiness is now verified in private `phase3/gpu-readiness-v1/venv`:
Radeon RX 7900 XT / gfx1100, PyTorch 2.12.0 + ROCm 7.14.0, Python 3.12.3.
All 19 packages have reviewed source/size/SHA receipts. The frozen synthetic
test passed matrix/backward checks, 20 masked Adam steps and exact prediction
parity after a fresh checkpoint reload; peak reserved GPU memory was 164 MiB.
No official GPU training has occurred. A duplicated package cache exceeded the
12-GiB storage cap before GPU import; a recorded cache-only repair restored
7.32 GiB usage without changing versions or criteria. No system driver or
historical environment changes. See [GPU readiness evidence](../../benchmarks/openadmet_cyp_2026/phase3_gpu_readiness_v1.json).
Do not reinstall or rerun completed readiness checks. The shared user
`cypshift.slice` CPU/RAM limits are verified at 24 CPU equivalents / 20 GiB;
use that slice and inherited CPU affinity for future jobs. cpuset delegation is
unavailable, so affinity is cooperative rather than a hard cpuset boundary.
Freeze a compact direct-only / genuine-primary-screen auxiliary / shuffled-
auxiliary MLP protocol. Initial auxiliary intake stays on established development
identities with family-safe masks and explicit assay/replicate semantics.
The source metadata audit finds 3,493 development molecules with screen records,
415 without, and exactly one published row per molecule/enzyme. Use no
aggregation. Preserve the actual 49.5049505-uM concentration and quote-aware
six-field prefix parsing; an exact 50-uM filter or naive comma split is wrong.
Finite response availability remains unverified: no screen response has yet
been decoded. See [intake metadata](../../benchmarks/openadmet_cyp_2026/phase3_primary_screen_metadata_v1.json).
Honest grouped stopping plus inner refitting requires 105 network fits per
repeat across all three arms, not 60. Freeze budgets after representative
synthetic timing, before official outcomes. The matching 4,296→256→128→8 shape
now profiles at 24.375 ms per full-size synthetic epoch / 260 MiB peak reserved
GPU memory. Charging 105 fits × 200 epochs projects about 8.85 minutes of
training per repeat using the slowest observed epoch, excluding startup,
validation, scoring and I/O; this is not a guaranteed runtime bound. The initial
profiling filename collision failed before optimizer execution and is preserved.
See [throughput evidence](../../benchmarks/openadmet_cyp_2026/phase3_mlp_synthetic_throughput_v2.json).
Keep discovery/query episode design
as a distinct diagnostic with query membership fixed before outcomes.

The first affine-MAE CSV remains the interim recommendation; final reserve
stays closed. Future qualified models need their own saved/reloaded estimators
and actual validated files. The existing two-hour heartbeat resumes from this
state, avoids duplicate work and only notifies for actual files or meaningful
changes. GPU setup must not become another unbounded prerequisite for releases.

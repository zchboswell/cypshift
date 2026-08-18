# OpenADMET CYP 2026 — TRACE contract receipts

This directory is the tracked launch receipt for the 2026-08-17 OpenADMET CYP
release: immutable revisions and metadata only; no challenge CSV, prediction,
model cache, or upstream source tree is copied here.

The pinned read-only source clones were verified at:

- dataset `85f8b358d0a2056a98b990dd75d3b3ec9247862b` (Apache-2.0); tutorial
  `9d4925eb4a0fb914256da1b27d110593bcbe3cf0` (Apache-2.0); Space
  `13c5057b37d1e72b3f036dd0d59718b1823f8fdd` (license unresolved).

[`source_receipts.json`](source_receipts.json) has exact sizes, SHA-256, rows,
headers, and TDI order discrepancy; [`challenge_contract.json`](challenge_contract.json)
has the R0 gate, endpoint states, validation, claims, and V6/P6 items; see
[`submission_contract.json`](submission_contract.json) for required columns.
[`validation_contract.json`](validation_contract.json) freezes the corrected R2 v4
label-aware topology-viability, campaign-episode, firewall, and fold contract.
V3 was rejected before R2B after a post-merge Sol audit found incomplete
episode policy/hash output, incomplete public query-field typing, and an
incomplete topology-viability schema/acceptance contract; zero R2B artifacts
were created. PR89's claimed independent audit is separately recorded as
unsupported because its assigned read-only auditor self-integrated; that
governance breach does not invalidate valid R2A evidence. It is not
`VALIDATION_FROZEN`. R2A emits direct observations and component folds. R2B now
emits the three episode projections, restricted anchor masks, and recomputed
topology viability under v4. Fold, episode, episode-label, and viability
artifact authority is accepted; models, validation, metrics, submissions, TDI,
predictions, and transductive use remain unauthorized.
[`global_experiment_contract.json`](global_experiment_contract.json) now freezes
the corrected R3 v3 global-only direct fallback: endpoint median, Morgan 1-NN, Morgan
CatBoost, and fixed MapLight under `GLOBAL_FAMILY_HOLDOUT` with provisional
component-macro MAE only. It explicitly separates the mandatory global fallback
from later oracle/transformation work. The Linux MapLight overlay is mandatory;
failure stops R3 before scientific fitting. R3A permits only fixture parity and
two label-free feature roots, R3B is synthetic runner/firewall acceptance, and
R3C alone may run the frozen experiment. V1 was rejected before execution for
five mechanical blockers after its assigned read-only auditor improperly
pushed it directly to main; v2 preserves that history and corrects the boundary.
V2 was then rejected before R3A because it did not authorize any source from
which the direct-only raw-SMILES population could truthfully be projected. V3
adds one receipt-bound chemistry prefix process that parses or retains zero
target values and opens no blinded-test artifact; the feature process sees only
its 4,905-row label-free CSV and manifest. The projector also verifies the
train-only topology receipt and frozen standardization: exact raw SMILES feed
MapLight, while standardized SMILES feed D-032 Morgan.
R3 still grants no official metric, TDI, submission, or transductive authority.

The July 29 announcement and August 17 launch post are official prose receipts
(URL, DOI, retrieval digest, CC BY 4.0 footer). They confirm two tracks, 750
compounds, live-half/full-final leaderboard, external/pretrained use with
proprietary disclosure, and TDI label caution; they do not replace executable
metric/validator evidence.

R0 leaves exact live ST-RAE implementation, denominator, masks, interval bounds,
TDI derivation, backend parity, and transductive permission unresolved. No
metric-specific optimization or leaderboard iteration is authorized. R2 keeps
the direct compiler restricted to `TRAIN_inhibition`, preserves all four
measurement states, and keeps TDI labels and the blinded test outside the
direct validation chain. The checker is
read-only and does not download sources or write artifacts. With the three
read-only clones and two HTML files fetched outside Git, run:

```console
uv run python scripts/check_openadmet_cyp_contract.py \
  --dataset-root /path/to/dataset \
  --tutorial-root /path/to/tutorial \
  --space-root /path/to/space \
  --announcement-html /tmp/announcement.html \
  --launch-post-html /tmp/launch_post.html
```

Exit 0 means all receipt and internal-contract checks pass; exit 1 means
source, prose, schema, row-count, or hash drift; malformed invocation or
tracked contract JSON exits 2.

After accepted R1 and topology outputs exist outside Git, build the R2A slice
into another untracked directory with:

```console
uv run python scripts/build_openadmet_validation_inputs.py \
  --validation-contract benchmarks/openadmet_cyp_2026/validation_contract.json \
  --direct-source /path/to/cyp-challenge-TRAIN_inhibition.csv \
  --r1-directory /path/to/r1-output \
  --topology-directory /path/to/topology-output \
  --output-directory /path/to/r2a-output \
  --source-revision 85f8b358d0a2056a98b990dd75d3b3ec9247862b
```

The command opens only the direct-training CSV and receipt-bound R1/topology
artifacts. It does not create episodes, decide endpoint viability, fit or score
a model, read TDI or blinded test data, or authorize its fold records as a
validated split. R2B consumes only these receipt-bound outputs.

Build the accepted R2B slice from that directory with:

```console
uv run python scripts/build_openadmet_campaign_artifacts.py \
  --validation-contract benchmarks/openadmet_cyp_2026/validation_contract.json \
  --r2a-directory /path/to/r2a-output \
  --output-directory /path/to/r2b-output \
  --source-revision 85f8b358d0a2056a98b990dd75d3b3ec9247862b
```

V4 freezes the R2B semantic episode CSV types, lowercase SHA256 episode
and component IDs, selected/stress policy tokens, unique-ID and join counts, and
the exact receipt-bound `topology_viability.v1` schema. Its topology artifact
must contain all four endpoint global counts and fifteen sorted fold-support
cells per endpoint, with no predictions, learned/fitted weights, metrics, TDI,
blinded-test, or transductive content. Root review and independent replay now
accept the implementation. Two official R2B builds were
byte-identical for all seven files. The accepted manifest is `08dcf61c...`;
public/truth/mask hashes are `47180477...`, `f2ec3ca6...`, and `0b437aa5...`,
and topology viability is `6c4e66ec...`. Independent scientific/code review
passed.

Released TDI labels conflict with launch prose. Among non-null labels, all
arm-missing rows are `False` (CYP2D6: 4; CYP3A4: 1,250), including 1,055
CYP3A4 rows lacking direct pIC50 but having TDI pIC50 at least 4.301. Preserve
this M2/M6/P6 conflict as unresolved label origin/derivation; do not
extrapolate the observed relation to hidden labels.

Status values: `verified`, `organizer_confirmed`, `provisional`, `unresolved`,
and `not_applicable`.

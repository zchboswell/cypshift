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
[`validation_contract.json`](validation_contract.json) freezes the corrected R2 v2
label-aware topology-viability, campaign-episode, firewall, and fold contract.
It is not `VALIDATION_FROZEN`. The R2A implementation now emits only direct
observations, deterministic component-fold records, and a scope-limiting
manifest; those fold records are inputs without validation authority. Episodes,
topology viability, models, metrics, submissions, TDI, and transductive use
remain unimplemented and unauthorized.
V2 supersedes the pre-implementation v1 after independent review found selector
leakage and ambiguous authority, oracle, support-status, and determinism rules.

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
validated split. The next gate is the episode/firewall/viability slice.

Released TDI labels conflict with launch prose. Among non-null labels, all
arm-missing rows are `False` (CYP2D6: 4; CYP3A4: 1,250), including 1,055
CYP3A4 rows lacking direct pIC50 but having TDI pIC50 at least 4.301. Preserve
this M2/M6/P6 conflict as unresolved label origin/derivation; do not
extrapolate the observed relation to hidden labels.

Status values: `verified`, `organizer_confirmed`, `provisional`, `unresolved`,
and `not_applicable`.

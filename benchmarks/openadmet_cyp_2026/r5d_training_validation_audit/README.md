# R5D training-validation audit bundle

This directory publishes the exact, immutable evidence from the sole official
TRACE CYP3A4 **training-only validation** run. It lets an external auditor
recompute the reported metrics and decision without repeating the 19.55-hour
model run.

The run ended with `R5_ORACLE_NO_SIGNAL`. It evaluated whether TRACE improved
over the fixed MapLight global comparator under repeated component-held-out
validation. It did not generate or evaluate a competition submission.

## Privacy and competition boundary

This bundle contains no:

- blinded-test molecule access, labels, or predictions;
- submission rows or values;
- raw model predictions;
- raw training target values; or
- SMILES strings.

`terminal/oracle_scored_rows.csv` contains public training molecule identifiers,
held-out absolute errors, structural-support metadata, and validation weights.
Those rows are sufficient to independently recompute the published aggregate,
bootstrap, cell, influence, safety, and ablation evidence. The manifest and
receipt record zero blinded-test opens, zero submissions, zero official-metric
calls, and no authority to publish predictions.

A prepublication membership check found 243 unique query identifiers in the
scored rows: all 243 occur in the pinned 4,905-molecule training projection and
none occur in the pinned 750-molecule blinded-test set.

The source training dataset is published by OpenADMET under Apache-2.0 at
<https://huggingface.co/datasets/openadmet/cyp-challenge-train-test>. This
bundle derives only from its public training split at revision
`85f8b358d0a2056a98b990dd75d3b3ec9247862b`.

## Contents

- `attempt_claim.json`: immutable attempt identity and frozen source bindings.
- `official_attempt_receipt.json`: all 7,985 zero-exit process records, source
  and parent receipts, operation accounting, terminal receipts, and authority.
- `terminal/`: the exact eight-file status terminal containing scored
  training-validation errors and their deterministic reductions.
- `SHA256SUMS`: independent file digests for the copied evidence.

Core receipts:

- claim SHA-256: `0036a70e65dca643d56d8cbeca5b1758f6f52ac00c9ba9d99e268b76d54a0bc4`
- attempt receipt SHA-256: `a5e61aaa91f37db1e4295a7cbf28485feadea2c94bec0d8b8e5ca785c7cd6158`
- terminal manifest SHA-256: `dd93d2f7760394ee1703d27236149db643bcf7a1cc6a319b85561c5d20eb810c`
- oracle result SHA-256: `4b06a96ad5742d85809b40932b380d8ea1f4ea4202abd96376b0c5bc11b43b0f`
- signed execution commit: `ee189abe6b2f480b0659a4f685ce280cefcb9fd0`

## Verification

From the repository root:

```console
(cd benchmarks/openadmet_cyp_2026/r5d_training_validation_audit && sha256sum -c SHA256SUMS)
uv run pytest -q tests/test_openadmet_r5d_public_audit_bundle.py
```

The test checks the exact file set and hashes, complete process topology,
forbidden-operation counters, authority, absence of raw prediction/target
columns, and deterministic scientific revalidation of the full terminal.

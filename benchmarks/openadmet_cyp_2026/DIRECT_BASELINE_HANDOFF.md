# Direct MapLight baseline handoff

This is the immutable direct submission for the OpenADMET CYP challenge. It is
a fixed MapLight prediction over all four challenge CYP endpoints; it is not
TRACE evidence. Private portal activity and results are intentionally outside
this repository record and cannot alter scientific or candidate selection. The
sole official TRACE oracle returned authenticated `R5_ORACLE_NO_SIGNAL`, so the
frozen inferred-anchor gate cannot activate and this baseline remains the only
contract-authorized direct submission candidate. The official negative result
is recorded in [`TRACE_OFFICIAL_OUTCOME.md`](TRACE_OFFICIAL_OUTCOME.md).

## Exact accepted artifact

- Accepted root: `/home/zbos/cypshift-private/openadmet-2026/submissions/direct-maplight-v1/accepted`
- Upload file: `submission.csv`
- `submission.csv` SHA-256: `9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`
- `manifest.json` SHA-256: `96ee587c4483b3ebab274b071c0c8108e35e0abc3bc2434ac0a5f0661dcb63d6`
- Shape: 750 test rows, four CYP prediction columns, 3,000 finite predictions
- Frozen system: `TRACE-G0-MAPL-FIXED`

The accepted directory is read-only (`0555`) and both files are read-only
(`0444`). Upload the exact `submission.csv` bytes; do not edit, reorder, or
re-serialize the CSV. If it must be copied, verify the SHA-256 above before
uploading. The accompanying manifest is the provenance record and is not the
competition upload.

## Competition-validator result

The exact accepted CSV passes the competition tutorial's own
`validate_activity_submission` function with `valid=True` and no errors. The
validation was rerun after the final TRACE result on 2026-08-23 and used:

- tutorial repository commit: `858ae63ce79934113bccdb7fc65467de5f7b1935`
- `validation/activity_validation.py` SHA-256:
  `276a53d7f22ff973aaf567e64d977202995e91ba3cef2bbdc4de71c13bdebcb2`
- official blinded-test dataset revision:
  `85f8b358d0a2056a98b990dd75d3b3ec9247862b`
- official blinded-test CSV SHA-256:
  `a342f8444a8dcb531ca12f3685293f0bd6c36ae9073f491e44a9bc1cc4b741f9`
- expected and submitted `Molecule_Name` cardinality: 750, with no missing or
  extra IDs

The validator confirmed all required identifier and four regression columns,
750 rows, unique molecule names, numeric finite predictions, and the exact
official molecule-ID set. The submission SHA-256 was checked before and after
and remained `9d3ed5ff...db504b`.

## Interpretation

This artifact is the frozen direct-track result. TRACE did not pass its
training-only evidence gate, so no TRACE-enabled CYP3A4 test prediction was
created. The artifact uses no blinded-test labels, TDI data, official metric
calls, calibration, clipping, ensemble, or transduction. A manual competition
upload and any returned leaderboard result remain private operational evidence;
this public handoff intentionally makes no claim about whether either occurred.

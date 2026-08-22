# Direct MapLight baseline handoff

This is the immutable starting submission for the OpenADMET CYP challenge. It
is a direct, fixed MapLight prediction over all four challenge CYP endpoints;
it is not TRACE evidence and it has not yet been uploaded to the competition.

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

## Interpretation

This artifact is the regression baseline against which a later TRACE-enabled
CYP3A4 submission will be compared. It uses no blinded-test labels, TDI data,
official metric calls, calibration, clipping, ensemble, or transduction. A
manual competition upload and any returned leaderboard result must be recorded
separately; neither has occurred at the time of this handoff.

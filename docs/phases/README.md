# Active phase

Phase 1 TRACE is active at the records-only gate
`R1_SOURCE_ROWS_PREPARED`. The launch-day OpenADMET source revisions, file
receipts, submission names/types, endpoint-state notes, and unresolved
metric/permission items are frozen in
[`PHASE_1_OPENADMET_TRACE.md`](PHASE_1_OPENADMET_TRACE.md) and
[`benchmarks/openadmet_cyp_2026/`](../../benchmarks/openadmet_cyp_2026/).

No modeling or scoring is authorized. The receipt-bound checker and canonical
source-row adapter have passed their synthetic gates. The exact next action is
family-topology auditing from the prepared source rows, while unresolved
schema, metric, TDI-order, interval, and permission behavior remains frozen.
`TDI-TRACE` is deferred; `global_TDI` is the permanent fallback.

Completed plans are historical evidence and live under
[`docs/archive/phases/`](../archive/phases/).

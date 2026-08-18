# Active phase

Phase 1 TRACE is active at the records-only gate
`R0_CONTRACT_FROZEN`. The launch-day OpenADMET source revisions, file receipts,
submission names/types, endpoint-state notes, and unresolved metric/permission
items are frozen in
[`PHASE_1_OPENADMET_TRACE.md`](PHASE_1_OPENADMET_TRACE.md) and
[`benchmarks/openadmet_cyp_2026/`](../../benchmarks/openadmet_cyp_2026/).

No modeling or scoring is authorized. The exact next action is a thin
receipt-bound drift checker/canonical adapter; it must fail closed on source,
schema, row-count, or hash drift. `TDI-TRACE` is deferred; `global_TDI` is the
permanent fallback after the direct and global contracts are frozen.

Completed plans are historical evidence and live under
[`docs/archive/phases/`](../archive/phases/).

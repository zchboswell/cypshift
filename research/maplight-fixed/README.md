# MapLight fixed-feature environment

This directory locks the compatible Stage A reproduction environment. It is
not the unrecoverable historical MapLight environment.

The dependency cutoff is 2023-08-29 UTC. Direct versions are fixed before any
feature or model result. The environment stays separate from the `cypshift`
core install and ordinary CI environment.

Create it only through the reviewed Stage A contract. Do not add GIN, PyTDC,
notebook, development, or core-package dependencies here.

`maplight_fixed_features.py` implements the one frozen fixed representation.
`verify_parity.py` compares it with the pinned MapLight source in three fresh
synthetic-only processes. The verifier has no model or benchmark-label path.
It does not read, and is not authorized to read, shadow rows, measurements,
public-test data, GIN weights, predictions, or scores.

The completed verifier wrote one immutable parity receipt on attempt 2. Attempt
1 remains as an immutable infrastructure blocker. Do not rerun either attempt.
The operation downloaded no data or dependencies.

The frozen plan allowed two independent label-free feature roots. Build 1
stopped before retaining a matrix because one Avalon sparse count exceeded the
predeclared safe range. Do not rerun build 1 or start build 2. The builder now
enforces that stop before build 2 can resolve any scientific input. It has no
measurement, target, model, prediction, or public-test argument.

The project owner separately authorized an exact-upstream signed-`int8`
compatibility experiment. Its contract is
`benchmarks/maplight_fixed_int8_compat_contract.json`. This did not reopen the
safe build. Fresh compatibility parity passed, including the exact 127, 128,
and 144 boundaries. Real build 1 then stopped before persistence because the
frozen validator found a non-finite RDKit descriptor at exact-raw index 1,563.
Its blocker is immutable under
`artifacts/blockers/maplight-fixed-upstream-int8-features-v1-build-1-blocker`.
Do not rerun parity or build 1. Do not start build 2, fit a model, start GIN, or
inspect a public-test label under this contract.

D-027 authorizes one separate missing-value compatibility path without changing
either prior result. `run_nan_compat.py` reuses the signed-`int8` runner's
source, environment, row, and serialization checks. It permits `NaN` only in
descriptor columns 39, 41, 43, and 45, rejects every infinity and every other
`NaN`, and preserves the permitted float64 bytes unchanged. It also runs the
contracted synthetic CatBoost capability probe; this is not a scientific fit.

After the implementation commit is reviewed and integrated, generate build 1
with `python run_nan_compat.py --build-id 1` in the exact locked environment.
Build 2 remains forbidden until build 1 is immutable and independently
reviewed. Neither build accepts a target, measurement, prediction, metric,
GIN, or public-test path.

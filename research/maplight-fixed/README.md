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

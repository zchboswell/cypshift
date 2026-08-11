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

Run the reviewed verifier only with the exact isolated Python 3.10 environment:

```text
artifacts/environments/maplight-fixed-stage-a-v1/venv/bin/python \
  research/maplight-fixed/verify_parity.py --attempt 1
```

The command writes one immutable success receipt or one immutable blocker. It
does not download data or dependencies.

After parity passes, `build_features.py --build-id 1` and `--build-id 2`
create two independent label-free feature roots. The builder caches only exact
raw strings, expands the five blocks back to all frozen shadow row identities,
and has no measurement, target, model, prediction, or public-test argument.

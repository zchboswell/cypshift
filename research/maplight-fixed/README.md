# MapLight fixed-feature environment

This directory locks the compatible Stage A reproduction environment. It is
not the unrecoverable historical MapLight environment.

The dependency cutoff is 2023-08-29 UTC. Direct versions are fixed before any
feature or model result. The environment stays separate from the `cypshift`
core install and ordinary CI environment.

Create it only through the reviewed Stage A contract. Do not add GIN, PyTDC,
notebook, development, or core-package dependencies here.

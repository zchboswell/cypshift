# Global-v3 G4 GIN300 third-party notices

Frozen: 2026-08-30

This notice covers only the prospective, local, nonredistributed
`EXP-G4-GIN300` capability and any later use that is separately authorized by
the repository's contract sequence. It is not a license grant, a representation
that upstream artifact-specific terms are broader than stated below, or
permission to redistribute model weights or pretraining data.

The authoritative runtime inventory, including the exact interpreter
distribution and every Linux x86_64 wheel version, filename, SHA-256 digest,
source project, and license identifier, is
`benchmarks/openadmet_cyp_2026/global_v3_g4_gin300_linux_x86_64_runtime_manifest.json`.
That manifest and this notice must remain byte-bound by the D148 capability
contract. Upstream license and notice texts control if this summary differs.

## Pretrained checkpoint chain

### SNAP `pretrain-gnns`

- Project: `snap-stanford/pretrain-gnns`
- Revision: `8b20528a83b8869ce16451305b32c827258d19a3`
- Source license: MIT
- License object: Git blob
  `4ec60e59108c68fc9a8d507920c393d7a1cda23b`
- Model source: `chem/model.py`, Git blob
  `a7195ed96482adc2b9fdce95d187893ba22a4f6e`
- Checkpoint: `chem/model_gin/supervised_masking.pth`, Git blob
  `1f8de843feb5b51e73488a95096283028820583e`
- Checkpoint SHA-256:
  `375cd40af9f21d2a92ed1acbdea9efad14254c36703bb0e3a7e433e09e624ce1`
- Checkpoint size: 7,452,448 bytes
- Upstream: <https://github.com/snap-stanford/pretrain-gnns>
- Pinned license: <https://github.com/snap-stanford/pretrain-gnns/blob/8b20528a83b8869ce16451305b32c827258d19a3/LICENSE>

The frozen capability may use this checkpoint only for local CPU inference
after exact hash verification, complete SNAP-to-DGL tensor mapping, and
three-path parity. It is the sole prospective feature-weight source. The
checkpoint may not be committed, attached to CI, placed in a public bundle, or
included with a submission or report.

### DGL-LifeSci

- Project: `awslabs/dgl-lifesci`
- Version: 0.3.2
- Revision: `20cee8f3a2be314e34c0e696e797884630d0863e`
- Source license: Apache-2.0
- License object: Git blob
  `67db8588217f266eb561f75fae738656325deac9`
- Pretrained mapping source:
  `python/dgllife/model/pretrain/property_prediction.py`, Git blob
  `b5ab80f6123f3c393659e6accdce375c114121f8`
- GIN source: `python/dgllife/model/gnn/gin.py`, Git blob
  `300fda49f1489c7a3f00f3b6a2c9a39325754756`
- Remote checkpoint:
  <https://data.dgl.ai/dgllife/pre_trained/gin_supervised_masking.pth>
- Frozen expected size: 7,454,321 bytes
- Frozen expected ETag: `98fae61c9c23ce19ce4e57614f0f9450`
- SHA-256 at D148 freeze: not yet known
- Upstream: <https://github.com/awslabs/dgl-lifesci>
- Pinned license: <https://github.com/awslabs/dgl-lifesci/blob/20cee8f3a2be314e34c0e696e797884630d0863e/LICENSE>

The missing D148 SHA-256 is not filled by assumption. Under the sole future
D150 formal attempt, the object must be fetched once into isolated storage,
checked against the exact URL, host, size, and ETag, hashed and immutably
receipted before any deserialization, and never downloaded a second time. It
is a local parity reference only and must be deleted, with absence verified by
outer cleanup, before the aggregate terminal is sealed. No later official
feature may use it.

### MolFeat

- Project: `datamol-io/molfeat`
- Version: 0.9.2
- Revision: `4390f9fce25fa2da94338227f7c8f33a23e25b2a`
- Source license: Apache-2.0
- License object: Git blob
  `b751c103f21bdb8962d43b87a5429dbdb24fcfcf`
- Loader source: `molfeat/trans/pretrained/dgl_pretrained.py`, Git blob
  `02ca594664d20b2ad627010d4b615d7eedd03611`
- Metadata:
  <https://fs.molfeat.datamol.io/artifacts/dgllife/gin_supervised_masking/0/metadata.json>
- Metadata SHA-256:
  `75ea305d643d800b8b272819a78b842d5aca1c4ad55d47207321ab9b81d44d02`
- Artifact:
  <https://fs.molfeat.datamol.io/artifacts/dgllife/gin_supervised_masking/0/model.save>
- Artifact SHA-256:
  `6d0f8febad73e437772ebffc2ac32253d79f86ee138cfc233590ae50fb1cfeb9`
- Artifact size: 7,467,310 bytes
- Artifact-specific license field in the pinned metadata: absent (`null`)
- `model_usage` field in the pinned metadata: absent (`null`)
- Upstream: <https://github.com/datamol-io/molfeat>
- Pinned license: <https://github.com/datamol-io/molfeat/blob/4390f9fce25fa2da94338227f7c8f33a23e25b2a/LICENSE>

The Apache-2.0 identifier above describes MolFeat source code. It does not
invent an artifact-specific license where the pinned metadata provides none.
The artifact is limited to isolated local parity against the historical
MolFeat API, may not be redistributed, and must be deleted, with absence
verified by outer cleanup, before the aggregate terminal is sealed. No later
official feature may use it.

## Principal runtime projects

The D148 runtime manifest contains the complete 96-wheel CPU-only closure plus
one separately frozen interpreter distribution: 97 runtime artifacts totaling
566,804,656 bytes. It is the authority for exact artifact identities, package
versions, hashes, and license assignments. Principal scientific runtime
projects include:

- CPython 3.10.13 — Python Software Foundation License.
- PyTorch 2.0.1+cpu — BSD-style license; CPU wheel only.
- DGL 1.1.2 — Apache-2.0.
- DGL-LifeSci 0.3.2 — Apache-2.0.
- MolFeat 0.9.2 — Apache-2.0.
- RDKit 2023.3.3 — BSD-3-Clause.
- CatBoost 1.2.1 — Apache-2.0.
- NumPy 1.25.2 — BSD-3-Clause.
- pandas 2.0.3 — BSD-3-Clause.
- SciPy 1.11.2 — BSD-3-Clause.
- scikit-learn 1.3.0 — BSD-3-Clause.

No CUDA, ROCm, NCCL, Triton, GPU runtime, source distribution, editable
install, or VCS dependency is authorized. The manifest records the transitive
projects and license identifiers that are not repeated here.

MolFeat is frozen with its `dgl` and `transformer` extras because MolFeat 0.9.2
initialization statically imports its optional Hugging Face module on the DGL
path. The resulting `huggingface-hub`, `regex`, `safetensors`, `sentencepiece`,
`tokenizers`, and `transformers` packages are import-compatibility dependencies
only. They grant no transformer model, tokenizer model, remote repository,
cache-population, feature, checkpoint, or network authority.

One Python-package-wheel cutoff exception is disclosed. Historical
`future==0.18.3` is sdist-only for the frozen Linux closure; D148 therefore
pins wheel-available `future==1.0.0`, the sole Python package wheel uploaded
after the historical package-wheel cutoff. No scientific equivalence is
assumed. The exact Linux three-path parity gate must pass, or the experiment
closes.

The interpreter is the exact python-build-standalone release `20240224`, tag
commit `61ace30326ba7c32325c6633665cc571ac56b82a`, install-only archive
`cpython-3.10.13+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz`
(27,409,290 bytes; SHA-256
`d995d032ca702afd2fc3a689c1f84a6c64972ecd82bba76a61d525f08eb0e195`).
Its 65-byte checksum sidecar has SHA-256
`9e57b23cb72164f981d9c6a52bdb555557639de897631f54fe1255181464e4b3`.
This separately frozen 2024 interpreter infrastructure distribution is not a
Python package wheel and is not governed by that wheel-upload cutoff. The
python-build-standalone project license is BSD-3-Clause; its pinned 1,495-byte
license has SHA-256
`02e7aaf3645b50fb9056b18528e2ca3474a6628fe3396ae4dd326f6618e0aad7`.
CPython is PSF-2.0. D150 must inspect and retain the archive's `PYTHON.json`
inventory and every bundled notice. The installed executable hash is honestly
unknown in D148 because determining it requires the forbidden archive fetch
and authenticated extraction; D150 must bind that hash before any import or
execution and fail closed on mismatch.

## Pretraining lineage and claim limits

The checkpoint lineage is attribute masking on approximately two million
ZINC15 molecules followed by supervised graph-level pretraining on
approximately 456,000 ChEMBL molecules across 1,310 assays. OpenADMET structure
overlap and assay overlap are both unknown.

The supported description is **public pretrained-representation transfer**.
The following descriptions are not supported:

- clean zero-shot transfer;
- uncontaminated external validation;
- strict family holdout from all pretraining;
- known absence of OpenADMET structure overlap;
- known absence of OpenADMET assay overlap.

Any method report must identify the exact SNAP checkpoint chain, DGL-LifeSci
and MolFeat versions, ZINC15 and ChEMBL lineage, unknown overlap, local-only
weight handling, and the fact that neither the DGL nor MolFeat reference object
is the later official feature source.

## Nonredistribution and retention

No checkpoint, tensor payload, embedding row, raw pretraining molecule,
runtime cache, unrestricted log, credential, or protected path may enter Git,
CI artifacts, documentation bundles, publication bundles, method-report
attachments, submission files, or public terminals.

Public capability evidence is limited to object hashes and sizes, source and
license identities, aggregate tensor/graph/parity facts, resource summaries,
cleanup facts, counters, and a deterministic terminal. On capability success,
only the verified SNAP object and exact manifest-bound CPU runtime may remain
in an isolated read-only private store for a later separately contracted and
claimed label-free feature build. The interpreter archive, checksum sidecar,
wheel cache, and DGL and MolFeat reference objects are deleted.
On any capability failure, all three objects, the runtime, wheel cache, and
mutable work are deleted and their absence is verified before the aggregate
failure terminal is sealed. The permanent consumed-claim tombstone is retained
read-only after every post-consumption outcome.

## D148 public evidence-resource accounting

D148 downloaded no wheel body, interpreter-archive body, SNAP, DGL-LifeSci, or
MolFeat model body, transformer/tokenizer model body, and created, installed,
imported, or executed no runtime. Its checkpoint/model transport evidence was
six exact HEAD requests with zero response-body bytes: two independent checks
of each of the three public checkpoint/model endpoints. One separate MolFeat
metadata HEAD returned 405, and one 606-byte metadata GET was read only as
public provenance evidence with SHA-256
`75ea305d643d800b8b272819a78b842d5aca1c4ad55d47207321ab9b81d44d02`.
Two HEAD-only checks of the interpreter archive and checksum-sidecar initial
URLs confirmed their GitHub release-asset redirect family and returned no
artifact body.

Runtime-manifest research read public metadata from 95 distinct exact PyPI
release-JSON resources, nine distinct SPDX license-JSON resources, the public
PyTorch CPU simple-index page, and GitHub release/tag metadata for the frozen
interpreter. It also read the 65-byte interpreter checksum sidecar and the
1,495-byte python-build-standalone BSD-3-Clause license. The exact Torch CPU
wheel URL was checked by HEAD, including a repeated audit check, but its wheel
body was not fetched. Raw HTTP transaction/retry/cache counts and aggregate
metadata-response bytes were not instrumented, so no exact totals are claimed.
At least 15 additional pinned public-source/API reads supported the source
contract; their exact total and aggregate bytes were not retained. These are
public contract-research facts, not runtime or scientific execution.

## No current execution authority

D148 creates contract, runtime-manifest, notice, and static-audit evidence only.
Apart from the public metadata/source/HEAD evidence disclosed above, it
downloads, extracts, or installs no interpreter archive or runtime wheel,
fetches or loads no checkpoint/model body, deserializes or executes no tensor,
creates no implementation or claim, builds no graph or embedding, opens no
official row or target, and runs no fit, prediction, metric, submission,
validator, leaderboard, portal, credential, or upload operation.
These are incremental D148 facts and do not revise D147's separately disclosed
temporary public-source/hash-audit checkpoint accounting.
Only a reviewed, SSH-signed, fast-forward-integrated, exact-SHA-green D148 may
permit D149 to create and statically validate the exact implementation/lock/test
package with zero artifact, runtime, claim, or scientific execution. Only after
that D149 package is separately reviewed, SSH-signed, fast-forward-integrated,
pushed, and exact-SHA post-main green may D150 consume the sole one-use claim
and perform the formal capability attempt frozen by the contract.

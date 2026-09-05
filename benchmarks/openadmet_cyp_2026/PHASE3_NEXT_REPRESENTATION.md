# Next representation hypothesis

Both small fingerprint MLP recipes failed. Simply increasing their GPU usage is
not a scientific strategy. Keep the useful classical models and investigate a
pretrained molecular graph representation with broader chemical supervision.

CheMeleon is a descriptor-pretrained directed message-passing model. Its revised
paper reports stronger performance across small-data benchmarks, but those
results do not establish CYP-challenge performance. This motivates an experiment,
not adoption. [Primary paper, version2](https://arxiv.org/abs/2506.15792v2).

The authors provide both frozen embeddings and fine-tuning through Chemprop.
Start by establishing inference correctness and resource feasibility; then freeze
a comparison using our original family splits, incumbent and control gates.
[Official usage](https://chemprop.readthedocs.io/en/main/chemeleon_foundation_finetuning.html)
and [pinned fingerprint example](https://github.com/JacksonBurns/chemeleon/blob/b5e5bd88a7070c3f278e7e65e85b792617bf125c/chemeleon_fingerprint.py).

The35MBgeneric checkpoint from [Zenodo15460715](https://zenodo.org/records/15460715)
is downloaded with matching publisherMD5 and recordedSHA256. ZenodoAPI and source
repository declareMIT. Subsequent CPU-only weights-only loading confirms8,714,240finite parameters,
72atom/14bondfeatures,2048hiddenwidth and depth6. No official structures were read,
embeddings generated or model scored. [Asset receipt](phase3_foundation_asset_intake_v1.json).

This differs from D021's CYP-finetuned OpenADMET checkpoint and incompatible
CPUcontainer. Preserve that historical failure. The next runtime should use the
existing validated ROCmTorch in an isolated environment; do not mutate the
current GPU or legacy chemistry runtime. Chemprop2.2.1 supports this foundation
interface without2.3.1's newly added cuik_molmaker_pin/myerson dependencies.
Resolve and hash a minimal compatible closure before installation, retain licenses,
and verify raw-structure handling, CPU/GPU embedding parity, fresh reload, finite
outputs and throughput on synthetic molecules. No systemdriver changes.

A frozen-encoder plus classical readout is the inexpensive first candidate;
fine-tuning may follow with a proper paired ablation. Any downstream calibration,
feature selection or blending belongs inside family cross-fitting. External
pretraining corpus/rights/possible structure overlap must be disclosed; do not
claim challenge-family exclusion for generic external pretraining. Reserved
labels and blinded-test geometry remain outside candidate selection. A concrete
scientific recipe, budgets and acceptance criteria are still required before
any official development experiment.

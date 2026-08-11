# MapLight GIN reproduction

This isolated research environment reproduces MapLight's one declared
pretrained graph representation: MolFeat 0.9.2
`PretrainedDGLTransformer(kind="gin_supervised_masking", dtype=float)`.

It is not part of the `cypshift` package or public CLI. Its PyTorch, DGL,
DGL-LifeSci, MolFeat, and CatBoost dependencies never enter the core install.
The model artifact remains outside Git and is used only for local benchmark
reproduction; it is not redistributed.

The artifact and pretraining overlap status remain unknown. Results from this
path may be described only as pretrained-representation transfer, not clean
zero-shot generalization or automatic OpenADMET eligibility.

The first fixture attempt is preserved as a pre-embedding blocker: MolFeat
0.9.2 imports `python-dotenv` but omits it from its published runtime
dependencies. The v2 environment adds pinned `python-dotenv==1.0.0`; this is
an infrastructure repair only and changes no representation rule.

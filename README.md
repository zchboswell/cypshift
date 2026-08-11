# cypshift

**Auditable CYP inhibition prediction for molecular series.**

[![CI](https://github.com/zchboswell/cypshift/actions/workflows/ci.yml/badge.svg)](https://github.com/zchboswell/cypshift/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: BSD--3--Clause](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)

Most molecular models score a compound as though it appeared alone. Medicinal
chemistry does not work that way: compounds emerge as branching families, and
the meaning of a structural change depends on the parent, the local SAR, the
assay, and how far the new analog has moved through chemical space.

`cypshift` is built around a series-first hypothesis: a CYP prediction should
combine a strong global molecular model with measured-parent context, a
parent-to-analog change, and an explicit estimate of when that local evidence
is trustworthy. The aim is not merely to rank molecules, but to help a chemist
choose the next branch of a series with a prediction that states its evidence
and its limits.

The current release provides the audited foundation for that system:

- exact preservation of raw structures and assay context;
- deterministic chemistry standardization with explicit warnings;
- duplicate- and chemistry-group-aware validation;
- reproducible prediction artifacts, manifests, and static reports;
- a lightweight CPU core with RDKit as its only runtime dependency;
- a locally reproduced MapLight and pretrained-GIN comparator, isolated from
  the core installation.

The parent-relative predictor is the next scientific layer. Until it passes
family-held-out controls, `cypshift` should be treated as a rigorous CYP model
development and evaluation tool—not as a clinically validated predictor.

## Why use it?

Use `cypshift` when the provenance of a prediction matters as much as the
number itself.

| Common workflow | `cypshift` |
| --- | --- |
| Molecules are silently cleaned before modeling | Raw text is retained; every derived structure has a status and warning trail |
| Random splits make close analogs look easier than they are | Exact duplicates and declared chemistry groups remain on one side of a split |
| Assay labels are treated as interchangeable | Endpoint, isoform, NADPH condition, probe, readout, censoring, bounds, quality, and source remain explicit |
| A notebook produces a score | A run produces predictions, cards, hashes, configuration, software versions, and a report |
| Confidence is implied by model probability | Applicability and unsupported contexts are reported rather than hidden |
| Heavy research dependencies enter the product | CatBoost, MolFeat, DGL, and pretrained weights remain in isolated research environments |

`cypshift` does not reimplement RDKit, CatBoost, or graph encoders. It uses
well-established components where they are appropriate and concentrates its
original work on chemical lineage, validation, competence, and evidence.

## Quick start

Clone the repository and install the locked development environment:

```bash
git clone https://github.com/zchboswell/cypshift.git
cd cypshift
uv sync --locked --all-groups
```

Run the complete workflow on the redistributable synthetic fixture:

```bash
uv run cypshift audit examples/synthetic/molecules.csv \
  --measurements examples/synthetic/measurements.csv \
  --out results

uv run cypshift train --data results --out results

uv run cypshift predict \
  --data results \
  --model results/model.json \
  --out results

uv run cypshift report --run results --out results
```

Open `results/report.html` in a browser. Commands refuse to overwrite their own
artifacts; use a new output directory for an independent repeat.

The four-command interface is deliberately small:

```text
audit  -> validate chemistry and measurements
train  -> fit the current reference baseline
predict -> emit predictions, evidence cards, and a run manifest
report -> render a verified static report
```

See the [usage guide](docs/USAGE.md) for input schemas, output files, and
failure behavior.

## What to expect

The public CLI currently trains an endpoint-context median. It is a reference
baseline that proves the data and evidence path; it is not the research
comparator and should not be interpreted as a competitive biological model.

A successful example run creates:

```text
results/
├── audit.json
├── measurements.csv
├── model.json
├── molecules.csv
├── prediction_cards.jsonl
├── predictions.csv
├── report.html
├── run_manifest.json
└── split.csv
```

Invalid chemistry is quarantined. Unsupported assay contexts remain visible.
Every retained artifact is deterministic under the same inputs, configuration,
software, and seed.

## Validated evidence

The research path reproduced the published MapLight TDC comparator on identical
public rows. Five-seed AUPRC is shown below; each local result is within 0.003
of its dated published anchor.

| Representation | CYP2C9 | CYP2D6 | CYP3A4 |
| --- | ---: | ---: | ---: |
| MapLight fixed features | 0.786 | 0.720 | 0.881 |
| MapLight fixed + GIN | **0.858** | **0.791** | **0.916** |

On the frozen chemistry-group-held-out shadow benchmark, the fixed MapLight
representation improves macro AUPRC over binary Morgan by 0.0481 on scaffold
holdout and 0.0443 on chemistry-community holdout. Adding the pinned GIN
representation contributes another 0.0614 and 0.0574. Paired lower confidence
bounds remain positive, while shuffled-GIN and random-noise controls do not
reproduce the gain.

These results establish reproducible representation transfer on the named
benchmark. They do not establish clean zero-shot generalization, clinical
utility, or superiority of the not-yet-tested series-first model. The
[validation summary](docs/VALIDATION.md) states the exact claim boundary; the
[complete report](benchmarks/PHASE_0_75_REPORT.md) preserves the evidence.

## Scientific direction

The intended prediction is deliberately simple:

```text
analog potency
= measured parent potency
+ learned effect of the structural change
```

A global molecular model supplies the prior. A parent-relative model estimates
the local shift. A competence rule then decides how strongly to trust the
local path based on similarity, transformation support, measurement quality,
and expert disagreement. When local evidence is weak, the result should shrink
toward the global model rather than fabricate certainty.

This direction will be retained only if it improves family-held-out evidence
against global, nearest-neighbor, copy-parent, shuffled-parent, and
incorrect-parent controls. If a simpler rule performs equally well, the simpler
rule wins.

Read [the scientific rationale](docs/SCIENCE.md) for the hypothesis, proposed
model, and rejection criteria.

## Scope and safety

`cypshift` is intended for reproducible research and early drug-discovery model
development. It is not validated for clinical, regulatory, toxicological, or
patient-level decisions. CYP inhibition is assay- and condition-dependent;
predictions must not be detached from their endpoint and measurement context.

Public benchmark data, generated artifacts, pretrained weights, and licensed
inputs are intentionally kept out of Git. The repository contains only source,
contracts, compact receipts, aggregate reports, and a synthetic CC0 fixture.

## Documentation

- [Documentation index](docs/README.md)
- [Usage and artifact guide](docs/USAGE.md)
- [Scientific rationale](docs/SCIENCE.md)
- [Validation and benchmark summary](docs/VALIDATION.md)
- [Current project state](docs/strategy/PROJECT_STATE.md)
- [Contribution guide](CONTRIBUTING.md)

## Credits

`cypshift` builds on the work of the open cheminformatics community:

- [RDKit](https://www.rdkit.org/) provides molecular parsing,
  standardization, fingerprints, descriptors, and scaffold operations.
- [MapLight](https://github.com/maplightrx/MapLight-TDC) and Notwell & Wood's
  [multifingerprint ADMET study](https://arxiv.org/abs/2310.00174) define the
  fixed-feature and GIN comparator reproduced here.
- [Therapeutics Data Commons](https://tdcommons.ai/) provides the public CYP
  benchmark tasks and evaluation interface.
- [CatBoost](https://catboost.ai/),
  [MolFeat](https://molfeat.datamol.io/), and
  [DGL-LifeSci](https://github.com/awslabs/dgl-lifesci) support the isolated
  research comparator.
- [OpenADMET](https://openadmet.org/) and Octant have released public CYP data
  used in the assay-aware benchmark record.

Upstream licenses, revisions, and artifact limitations are recorded in
[`benchmarks/`](benchmarks/README.md). Third-party model weights are not
redistributed by this repository.

## License

The `cypshift` source code is available under the
[BSD-3-Clause license](LICENSE). The invented fixture under
`examples/synthetic/` is separately dedicated to the public domain under
CC0-1.0.

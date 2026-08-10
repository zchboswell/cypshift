# August 17 launch intake

Status: pre-launch entry-point receipt; no released challenge contract

Captured: 2026-08-10T02:34:21Z

## Purpose

Identify the official surfaces that must be captured on launch day, and prevent
the current public placeholder from being mistaken for the authoritative
release. This note freezes no field name, metric code, dataset byte, submission
rule, or model choice.

## Official entry points

- Announcement:
  [OpenADMET CYP inhibition blind challenge](https://openadmet.ghost.io/announcing-openadmets-cyp-inhibition-blind-challenge/)
  with DOI `10.5281/zenodo.21789716`.
- Challenge Space:
  [`openadmet/cyp-challenge`](https://huggingface.co/spaces/openadmet/cyp-challenge),
  linked directly from the announcement.
- OpenADMET datasets:
  [`openadmet` on Hugging Face](https://huggingface.co/openadmet/datasets).
- Support channel: the `#cyp-challenge` Discord channel linked from the
  announcement. Use it to resolve ambiguity; retain published artifacts as the
  source of truth.

## Current public state

The Challenge Space is public, ungated, and running at revision
`f281a4d246203e75248dd4348a72888853b2cbf9`, last modified
2026-08-05T03:52:31Z. The revision is browsable at
[`f281a4d`](https://huggingface.co/spaces/openadmet/cyp-challenge/tree/f281a4d246203e75248dd4348a72888853b2cbf9).

Its `config.py` is 26,406 bytes with SHA-256
`13c1bebe69ea900f1b5e927004bfb739dd7f7387d86589300505431c841ec911`.
At this revision:

- `CURRENT_PHASE` is `0`, defined as pre-challenge;
- the dataset and tutorial links are both `False` with launch TODOs;
- the submission portal displays an August 17 placeholder;
- activity and structure dataset sizes carry TODO comments;
- the Space includes a provisional structure track that the announcement does
  not define as a challenge track;
- the OpenADMET organization lists seven datasets, none named as the CYP
  challenge training or blinded test release.

Therefore the current Space is an official entry point but not an authoritative
schema, metric, dataset, or submission contract. Do not implement its current
configuration.

## Release-detection gate

On or after 2026-08-17, do not begin the Phase 1 freeze until the official
surfaces provide all of the following:

1. immutable or revision-addressable training and blinded-test files;
2. dataset cards with license, citation, task, assay, and provenance details;
3. released metric and TDI-label implementations, not only prose;
4. a local submission validator or exact executable validation behavior;
5. final submission columns, types, row identity, and row-order rules;
6. final external-data, proprietary-data, pretraining, and transductive-use
   permissions;
7. final submission frequency and leaderboard disclosure rules;
8. a tutorial or worked official example that agrees with released code.

A changed Space phase or a populated dataset link is necessary evidence, but it
is not sufficient by itself. Resolve conflicts among the announcement, Space,
dataset cards, tutorial, metric code, and validator before fitting.

## Capture order

When the gate opens:

1. record the UTC acquisition time and every official URL;
2. resolve and record repository and dataset revisions before downloading;
3. preserve original bytes outside Git and compute size and SHA-256;
4. capture cards, licenses, citations, rules, tutorial, validator, and metric
   source at their exact revisions;
5. inventory observed schemas without renaming or standardizing a field;
6. compare all released sources and record every discrepancy;
7. only then write the Phase 1 adapter and metric contracts;
8. freeze label-independent duplicate and analog-family groups before a model
   result is inspected.

The Phase 0.5 Octant and TDC contracts are comparison evidence only. They must
not fill a missing launch-day field or resolve a release discrepancy by
assumption.

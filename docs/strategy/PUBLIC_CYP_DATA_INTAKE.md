# Public CYP data intake

Status: pre-freeze source receipt; no training-data authority

Captured: 2026-08-10T02:51:06Z

## Purpose and boundary

Identify one public source that could add assay-relevant supervision after the
official challenge release is frozen. This note does not authorize download
into a model root, label conversion, fitting, or automatic mapping to a
challenge endpoint.

## FDA-led reversible-inhibition and TDI source

Faramarzi et al.,
[*Novel (Q)SAR models for prediction of reversible and time-dependent
inhibition of cytochrome P450 enzymes*](https://doi.org/10.3389/fphar.2024.1451164),
is an open-access 2025 article with PMCID
[`PMC11860084`](https://pmc.ncbi.nlm.nih.gov/articles/PMC11860084/). The article
is marked CC BY and publishes its database as Supplementary Table S1.

The PMC full-text XML identifies `DataSheet1.zip` as a 3,331,650-byte
supplement with MD5 `995f8effde82473e0c5625df1ebe9420`. Independent capture
gave SHA-256
`1ef874bc69c3ab702fb8ec9c4bffa59ce8fdb1f4d37f50b4a3bfb6320d8290f7`.
The archive contains:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `Supplementary_TableS1_Full_Database.sdf` | 36,424,439 | `ff0f0ee982b8771160b32b49a81bdaa21d6a0347199096e21e98ea2fa002d715` |
| `Supplementary_TableS2.DOCX` | 132,893 | `2ceb36fc338ee6770ffadf73fafdedda33199c7e41f4713426a638702c3f41bc` |

The SDF contains 10,129 structure records. Its endpoint fields have the
following non-missing binary labels:

| Field | Negative | Positive | Total |
| --- | ---: | ---: | ---: |
| `CYP3A4 TDI` | 317 | 306 | 623 |
| `CYP3A4 RI` | 4,352 | 2,658 | 7,010 |
| `CYP2D6 RI` | 3,358 | 1,592 | 4,950 |
| `CYP2C9 RI` | 2,665 | 1,384 | 4,049 |
| `CYP2C19 RI` | 2,040 | 787 | 2,827 |

The SDF also preserves identifiers and source references. It reports 7,782
records sourced only as ChEMBL, 1,107 sourced only as US patents, smaller
BindingDB groups, and several combined-source strings.

## Assay and label limitations

The source is scientifically relevant but not challenge-matched by default:

- reversible inhibition combines IC50, Ki, and R1 evidence into one binary
  label;
- TDI combines IC50 fold shift, change in inhibition, kobs, and R2 evidence;
- its frozen thresholds are 10 micromolar for reversible IC50 or Ki, 1.02 for
  R1, 1.5 for TDI IC50 fold shift, 20 percent for change in inhibition, 0.01
  per minute for kobs, and 1.25 for R2;
- only CYP3A4 has a released TDI field;
- assay system, probe substrate, preincubation, and source quality vary across
  the collected literature, approval packages, patents, ChEMBL, and BindingDB;
- the released SDF does not identify each row's measurement type and contains
  no assay, probe-substrate, preincubation, or continuous-result field;
- article-level CC BY does not remove the need to audit upstream source terms,
  attribution, and redistribution conditions.

Do not treat a `1` as the unreleased challenge TDI label. Do not convert this
database to pIC50 or merge its records with challenge measurements by endpoint
name alone.

## Post-freeze eligibility gate

Use this source only if the released rules permit external public data and an
independent source audit establishes all of the following:

1. the exact supplement and every retained source reference are preserved;
2. license and attribution terms permit the intended use and redistribution;
3. external-source copies of challenge structures are removed before auxiliary
   source selection, and overlap is reported separately;
4. cited originals reconstruct each retained row's measurement type and assay
   provenance; reject the source if this cannot be established;
5. no mixed-source label replaces a challenge measurement;
6. inclusion is decided from reconstructed assay evidence and frozen validation
   only, before any challenge test or leaderboard result;
7. the same grouped validation rows compare the model with and without this
   source;
8. the source is removed if its predeclared ablation does not improve the
   primary validation target.

The smallest valid use is auxiliary multitask supervision. It is not a new
model family, a comparator, or evidence of a gain.

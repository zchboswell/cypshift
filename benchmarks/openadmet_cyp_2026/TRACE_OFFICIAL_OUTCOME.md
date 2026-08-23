# Official TRACE outcome and submission decision

The sole authenticated crash-replacement R5D CYP3A4 oracle run completed on
2026-08-23 with status **`R5_ORACLE_NO_SIGNAL`**. This is a clean scientific
negative result, not an execution failure. Under the frozen I0
preregistration, it permanently stops inferred-anchor TRACE deployment for
this challenge version. The immutable four-endpoint MapLight candidate remains
the submission to upload.

## Authenticated official run

- Attempt root:
  `/home/zbos/cypshift-private/openadmet-2026/r5d-cyp3a4-official-crash-replacement-1`
- Signed source commit: `ee189abe6b2f480b0659a4f685ce280cefcb9fd0`
- Execution contract SHA-256:
  `ee135e7fa450ab05b68f92a46085213f7be574ce218ab9fda01df833e46125cf`
- Attempt claim SHA-256:
  `0036a70e65dca643d56d8cbeca5b1758f6f52ac00c9ba9d99e268b76d54a0bc4`
- Attempt receipt SHA-256:
  `a5e61aaa91f37db1e4295a7cbf28485feadea2c94bec0d8b8e5ca785c7cd6158`
- Terminal manifest SHA-256:
  `dd93d2f7760394ee1703d27236149db643bcf7a1cc6a319b85561c5d20eb810c`
- Oracle result SHA-256:
  `4b06a96ad5742d85809b40932b380d8ea1f4ea4202abd96376b0c5bc11b43b0f`
- Durable wrapper log SHA-256:
  `ffa36aaf2de9169c3d8e61b2482b52791c00394efafa48c2cc1ec26f2d3d9e9d`
- Wall time from claim through immutable receipt: 70,381 seconds
  (19.55 hours).

Independent reopening passed the exact terminal schema, all terminal and
parent receipts, four accepted official parents, all 17 source leaves, both
locked runtimes, and the complete process transcript. All 7,985 child
processes exited zero with the exact frozen verb counts: 3,366 G0 fits and
views, 960 inner pair cells, 75 migrations and episode enumerations, 120
ordinary outer pair cells, 15 shared outer cells, and one each of source,
projection, support, inner selection, freezer, accounting, cleanup, and outer
scoring. The final root contains only the read-only claim, eight-file terminal,
and receipt. Private and control roots are absent.

Forbidden counters are exactly zero: blinded-test files, TDI files, official
metric calls, submissions, transductive relationships, and inferred-anchor
candidate pools. The run therefore did not inspect the challenge test set or
create a submission.

## Why TRACE did not pass

The frozen question was whether measured-anchor TRACE (`T0`) robustly improves
over the episode-specific fixed MapLight global model (`G0`) and all mandated
controls under component-held-out evaluation. It did not.

- G0 component-macro MAE: `0.4327321629632583`
- T0 component-macro MAE: `0.7158918736591554`
- G0-minus-T0 point contrast: `-0.2831597106958972`
- 95% bootstrap interval: `[-0.3983355613565951,
  -0.16740067252975555]`
- Positive G0-minus-T0 cells: `1/15`, distributed `1/5`, `0/5`, `0/5`
  across the three repeats

The result also missed the predeclared all-contrast bootstrap, top-ten
leave-one-component-out, cell-direction, and safety-upper-bound gates. Support
and the worst-decile point-degradation gate passed, so this is not an
underpowered result. The global comparator was simply much stronger than the
tested anchor-delta systems. No threshold, model, anchor selector, or fallback
may be tuned after this outcome, and the dormant I0/F1 bridge cannot activate
because its required parent status is `R5_ORACLE_SIGNAL_PASS`.

## Submission handoff

Upload the exact immutable direct MapLight baseline documented in
[`DIRECT_BASELINE_HANDOFF.md`](DIRECT_BASELINE_HANDOFF.md):

`/home/zbos/cypshift-private/openadmet-2026/submissions/direct-maplight-v1/accepted/submission.csv`

Its SHA-256 is
`9d3ed5ff2ba08233caf99e46d4a0e69e59ab35a337521258a92ad21488db504b`.
Do not edit or reserialize it. On 2026-08-23 the exact bytes were revalidated
against the pinned official 750-row blinded-test file using OpenADMET tutorial
commit `858ae63ce79934113bccdb7fc65467de5f7b1935`; the validator source SHA-256
was `276a53d7f22ff973aaf567e64d977202995e91ba3cef2bbdc4de71c13bdebcb2`.
The result was `valid=True`, zero errors, exact molecule and SMILES order, six
exact columns, and 3,000 finite predictions.

This is the direct-activity submission only. It has not been uploaded or
scored, and no TDI submission is claimed here.

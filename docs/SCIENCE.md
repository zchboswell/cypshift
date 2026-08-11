# Scientific rationale

## Molecules have lineages

Most molecular prediction systems learn a function from one structure to one
property. That is useful, but it discards how medicinal chemistry is actually
performed.

A lead series grows through substitutions, ring changes, stereochemical
decisions, and scaffold branches. Each analog inherits information from its
parents. Some branches move smoothly through chemical space; others cross an
activity cliff. A measured parent therefore carries local information that a
global structure-only model may not recover.

`cypshift` is built around the hypothesis that CYP prediction improves when the
model treats this lineage as evidence.

## Intended predictor

The smallest series-first system contains three parts.

### Global expert

A strong molecular representation predicts the analog directly. This expert
captures broad chemical patterns and provides a stable prior when local series
evidence is weak.

The current reference for this role is the reproduced MapLight fixed-plus-GIN
representation. It is a comparator and a possible component, not an original
`cypshift` invention.

### Parent-relative expert

Given a measured parent, predict the effect of the change:

```text
analog potency
= measured parent potency
+ predicted parent-to-analog delta
```

The minimal input is expected to include:

- parent and analog representations;
- their representation difference;
- similarity and changed atom environment;
- the measured parent value and its quality;
- CYP isoform and retained assay context.

The model should learn local changes rather than relearn absolute potency from
scratch.

### Competence rule

The local expert should not always win. Its weight should fall when:

- the proposed parent is chemically distant;
- the transformation is unsupported;
- the parent measurement is uncertain or assay-mismatched;
- the global and local experts disagree sharply;
- the analog lies outside both experts' observed chemical support.

The simplest defensible prediction is a shrinkage between global and local
estimates. A learned gate is justified only if it improves family-held-out
evidence over a fixed rule.

## What is novel

The novelty is not a new fingerprint, graph convolution, or boosting
algorithm. It is the prediction unit and the decision rule:

1. represent a molecule in the context of a measured chemical lineage;
2. predict a parent-relative change;
3. estimate which expert is competent for that analog;
4. expose the evidence and abstention boundary to the chemist.

This is intended to make the output actionable in lead optimization: not only
which analog is preferred, but which branch is supported and where the model is
extrapolating.

## Evidence required

The parent-relative hypothesis is retained only if it beats all of the
following on identical family-held-out rows:

- the global molecular model;
- copy-parent prediction;
- nearest neighbor;
- a delta model without measured parent potency;
- shuffled parent assignment;
- an intentionally incorrect parent.

The paired family-bootstrap lower bound must improve the relevant metric, the
direction must not depend on one family, and global performance must not be
materially damaged. Activity cliffs and worst-family behavior are reported
explicitly.

Only after the local expert passes may a competence model be tested against:

- fixed shrinkage;
- an unweighted mean;
- nonnegative stacking;
- inverse-variance weighting;
- random or shuffled competence features.

When two approaches are statistically indistinguishable, `cypshift` retains
the simpler one.

## What has already been learned

Three results shape the next experiment:

1. Estimator diversity over one binary Morgan representation did not close the
   public benchmark gap. A nonnegative stack also trailed a simple mean.
2. A similarity-only residual worsened every evaluated task. It did not use a
   measured parent or transformation and therefore does not test the
   parent-relative hypothesis.
3. Complementary MapLight features and a pinned GIN representation add robust
   grouped-validation value. They provide the global comparator that the
   series-first model must beat.

These results narrow the scientific question. More generic ensembling is not
the next step; explicit chemical lineage is.

## Product expression

A useful series-aware prediction should eventually report:

- the predicted value or class;
- the measured parent and transformation used;
- the global and local estimates;
- the resolved blend or abstention;
- uncertainty and chemical-support diagnostics;
- assay context, provenance, and artifact hashes.

That is the intended distinction between `cypshift` and a structure-only
predictor. Until the controlled parent-relative experiment passes, it remains
a hypothesis and is described as such.

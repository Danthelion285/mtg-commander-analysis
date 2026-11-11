# MTG Commander Analysis

A reproducible research pipeline for evaluating MTG Commander theme and typal classification.

## Pilot

The initial pilot cohort is the **EDHREC Top 300 commanders by Past 2 Years popularity**. The cohort will be captured as a dated snapshot and treated as fixed during each experiment.

## Project principles

- Keep `Danthelion285/sylvan_librarian` as an upstream-derived fork; do not add classifier code to it.
- Keep raw source data, reference labels, predictions, and evaluation outputs separate.
- Preserve source provenance and retrieval timestamps.
- Prefer high-precision, explainable classifications. Store the exact query/rule and evidence for every prediction.
- Treat EDHREC labels as benchmark/reference labels, not unquestionable ground truth.
- Do not commit credentials, tokens, or other secrets.

## Planned pipeline

1. Capture and freeze the EDHREC Top 300 (Past 2 Years) ranking.
2. Resolve commanders to card records and Oracle text.
3. Collect EDHREC theme/typal reference labels.
4. Query Sylvan Librarian for supported syntax and Oracle Tags.
5. Compare baseline text matching, semantic/query-based classification, and a combined approach.
6. Evaluate precision, recall, F1, coverage, and manually adjudicated errors.

## Repository layout

```text
config/        Experiment configuration
data/raw/      Immutable source snapshots (not committed by default)
data/reference/ Benchmark labels and vocabulary
data/processed/ Normalized datasets
reports/       Evaluation reports
src/           Pipeline and classifier implementation
tests/         Automated tests
```

## Status

Initial project scaffold. Data acquisition and classifier implementation are not yet complete.

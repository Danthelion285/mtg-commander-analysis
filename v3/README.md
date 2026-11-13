# MTG Commander Theme Classifier — v3

This update expands the approved Oracle Tag mappings and direct rules, then applies them to the supplied SQLite database.

## Files

- `mtg_cards_tagged_oracle_classified.db` — updated database. The original `card_printings` table and its 20 columns are preserved.
- `theme_classifier.py` — classifier engine (same interface as v2).
- `theme_rules.json` — expanded, curated direct-text, Oracle Tag, and combined-pattern rules.
- `themes.json` — original user-maintained theme/typal vocabulary, unchanged.
- `classify_existing_db.py` — offline reclassification utility; it updates only `themes`, classifies once per Oracle ID, and leaves `typals` untouched.
- `test_classifier.py` — four regression tests for Tarland, Ulamog, Aurelia, and the untap-without-ramp guard.
- `classification_evidence_v3.json` — per-Oracle-ID scores and evidence trace.
- `remaining_uncategorized_v3.csv` — cards for which the current rules found no sufficiently strong theme evidence.
- `theme_coverage_v3.csv` — unique Oracle-card count by assigned theme.
- `main_oracletag_refactored.py` — recovered v2 main pipeline, included as the unchanged baseline.

## Run tests

From this folder:

```bash
python -m unittest test_classifier -v
```

## Reclassify an existing database

```bash
python classify_existing_db.py mtg_cards_tagged_oracle.db --themes themes.json --rules theme_rules.json
```

The script modifies only the `themes` column in `card_printings`. It does not download MTGJSON/Scryfall data, alter typals, or change the table schema.

## Results on the supplied database

- 35,488 total rows retained.
- 4,275 commander-eligible printings / 4,247 unique Oracle IDs processed.
- Before: 1,873 commander printings had no theme.
- After: 158 commander printings (157 unique Oracle IDs) remain without a theme.
- 1,715 of the previously unclassified printings now have at least one theme (about 91.6%).
- 105 theme categories are represented in the resulting classification.
- Typal values are unchanged; a row-by-row comparison found zero typal differences.
- SQLite integrity check and regression tests are run separately before delivery.

Cards remaining unclassified are not force-labelled. The residual list is dominated by vanilla/french-vanilla cards, legacy legends with no meaningful rules text, and digital/Un-set or unusual mechanics that do not clearly match the current theme vocabulary.

## Classification design

- Direct rules use templated rules-text patterns.
- Oracle Tag mappings use curated weights, confidence, relationship labels, and diminishing returns for related tags.
- Combined rules identify interactions that single tags cannot capture (for example, Annihilator plus permanent-sacrifice evidence → Control).
- Theme assignments retain evidence and scores in the JSON audit file.
- Statistical association candidates are not automatically promoted to approved mappings.

# Engine evaluation (synthetic data)

**All records are synthetic and the answer key was planted by the same seed script. These numbers detect regressions and
guide tuning; they are NOT evidence of accuracy on real AICTE complaints.** Reproduce: `python -m app.engine.evaluate`.

## Institution matcher (64 messy free-text references, no AICTE ID)
- Auto-linked: 43 (67%), wrong auto-links: **0**
- Sent to officer review: 16 (correct institution among the top 3 suggestions: 16)
- Left unresolved: 5

## Cross-Bureau overlap detection (14 planted RB+PGRC overlaps; English / Hinglish / Hindi)
| Threshold | Precision | Recall | F1 | TP | FP |
|---|---|---|---|---|---|
| 0.3 | 0.326 | 1.0 | 0.491 | 14 | 29 |
| 0.4 | 0.483 | 1.0 | 0.651 | 14 | 15 |
| 0.5 | 0.538 | 1.0 | 0.7 | 14 | 12 |
| 0.6 | 0.538 | 1.0 | 0.7 | 14 | 12 |
| 0.7 | 0.538 | 1.0 | 0.7 | 14 | 12 |

Operating threshold: 0.4 (Medium). Recall at operating threshold by complainant language: en: 7/7, hi-en: 4/4, hi: 3/3.

**Reading the precision honestly:** the 12 "false positives" were audited by hand: all are cross-Bureau pairs at the same
institution, in the same category, with 93-100% similar text. They are real overlaps created by chance by the random
background data, but the strict answer key only counts the 14 planted pairs. True precision is therefore higher than shown.

## Conflicting actions
Planted: 4, found: 4, other flags: 0.

## Known limits
Concept lexicon covers 7 complaint themes in 3 languages; real complaints need a larger lexicon or an embedding model
(plug-in point: `engine/concepts.py`). Evaluate on expert-labelled real cases before operational use.

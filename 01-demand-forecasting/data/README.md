# Data — Demand Forecasting — Walmart M5

- **Source URL:** Zenodo record 10.5281/zenodo.12636070 — https://zenodo.org/records/12636070 (verbatim re-upload of the Kaggle competition archive `m5-forecasting-accuracy.zip`). Original: https://www.kaggle.com/competitions/m5-forecasting-accuracy/data (Walmart / University of Nicosia MOFC).
- **License:** Zenodo record lists CC BY 4.0; original data governed by Kaggle M5 competition rules — cite Makridakis, Spiliotis & Assimakopoulos (2022), *The M5 competition*, IJF 38(4).
- **Download date:** 2026-09-28
- **Download command:** `curl -L -o m5-forecasting-accuracy.zip https://zenodo.org/api/records/12636070/files/m5-forecasting-accuracy.zip/content && unzip m5-forecasting-accuracy.zip`

## Notes
Kaggle login was not available (no API token), so the identical competition zip was pulled from Zenodo. MD5 verified: `86f57416a314197f40a17cc6fc60cbb4` (matches Zenodo metadata). `m5-forecasting-accuracy.zip` is kept alongside the extracted CSVs; delete it to save 48 MB if desired.

## Files (`data/raw/`, git-ignored)
| File | Size | Rows (excl. header) | Columns | Encoding |
|---|---|---|---|---|
| `calendar.csv` | 0.1 MB | 1,969 | 14 | utf-8 |
| `sales_train_evaluation.csv` | 121.7 MB | 30,490 | 1947 | utf-8 |
| `sales_train_validation.csv` | 120.0 MB | 30,490 | 1919 | utf-8 |
| `sample_submission.csv` | 5.2 MB | 60,980 | 29 | utf-8 |
| `sell_prices.csv` | 203.4 MB | 6,841,121 | 4 | utf-8 |

Total CSV size: 450.5 MB

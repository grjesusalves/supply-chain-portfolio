# data/raw

This folder is empty on GitHub by design, not by oversight: the M5 files are simply too large to upload. Anyone reproducing the work should download the following files from the M5 record on Zenodo (https://zenodo.org/records/12636070) and place them here:

- `sales_train_evaluation.csv`
- `sales_train_validation.csv`
- `calendar.csv`
- `sell_prices.csv`

Note that the code in `src/` reads them from this exact folder and from nowhere else, which means a misplaced file will stop the pipeline rather than quietly feed it the wrong data. The source and license are documented in `../README.md`.

# data/raw

This folder is empty on GitHub by design; the nine Olist CSVs are git-ignored.

Download them from the Olist repository (the same files as Kaggle `olistbr/brazilian-ecommerce`) and place them here:

```bash
git clone --depth 1 https://github.com/olist/work-at-olist-data.git
cp work-at-olist-data/datasets/*.csv data/raw/
```

The code in `src/` reads the CSVs from this exact folder. See `../README.md` for the file list, row counts, and license (non-commercial, with attribution).
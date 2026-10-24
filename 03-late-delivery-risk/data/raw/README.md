# data/raw

This folder is empty on GitHub by design; the DataCo files, at about 191 MB in total, are too large to upload.

Download them from the DataCo record on Mendeley Data (https://data.mendeley.com/datasets/8gx2fvg2k6/5, DOI 10.17632/8gx2fvg2k6.5) and place them here:

- `DataCoSupplyChainDataset.csv` (the only file the code reads; Latin-1 encoded)
- `DescriptionDataCoSupplyChain.csv` (column dictionary, optional)

`tokenized_access_logs.csv` belongs to the same record, but this project does not use it.

The code in `src/` reads the CSV from this exact folder. See `../README.md` for the source, the license (CC BY 4.0), and the file sizes.

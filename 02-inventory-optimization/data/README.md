# Data — Inventory Optimization (Reorder Point and Safety Stock)

**No new dataset is downloaded for this project, so there is no `data/raw/` folder.**

The project rests on a single input, the Project 1 forecast file, and that file is already committed:

- `../01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv`
- Columns: `item_id`, `day`, `actual`, `baseline`, `lgbm`
- Daily unit sales and forecasts for 1,437 FOODS items at store CA_3, 2016-04-25 through 2016-05-22 (40,236 rows)

Everything this project produces is written to `data/processed/`. The work stays in units from start to finish; no prices, holding rates or order costs are used, given that the data contains none of them, and inventing them would only lend false precision to the result. Note, too, that the 7-day lead time is a labeled assumption — not a fact drawn from the data.

- **Source:** derived from Project 1; see `../01-demand-forecasting/data/README.md`
- **License:** inherits Project 1 license

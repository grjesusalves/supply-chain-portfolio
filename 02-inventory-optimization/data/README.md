# Data — Inventory Optimization (Reorder Point and Safety Stock)

**No new dataset is downloaded for this project, so there is no `data/raw/` folder.**

The only input is the Project 1 forecast file, which is already committed:

- `../01-demand-forecasting/data/processed/ca3_foods_holdout_predictions.csv`
- Columns: `item_id`, `day`, `actual`, `baseline`, `lgbm`
- Daily unit sales and forecasts for 1,437 FOODS items at store CA_3, 2016-04-25 through 2016-05-22 (40,236 rows)

Everything this project produces is written to `data/processed/`. The work stays in units. No prices, holding rates, or order costs are used. The 7-day lead time is a labeled assumption, not a fact from the data.

- **Source:** derived from Project 1; see `../01-demand-forecasting/data/README.md`
- **License:** inherits Project 1 license

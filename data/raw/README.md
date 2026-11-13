# Raw data (not committed)

Place the 9 original Olist CSV files here (Kaggle: "Brazilian E-Commerce Public Dataset by Olist"):

olist_customers_dataset.csv · olist_orders_dataset.csv · olist_order_items_dataset.csv ·
olist_order_payments_dataset.csv · olist_order_reviews_dataset.csv · olist_products_dataset.csv ·
olist_sellers_dataset.csv · olist_geolocation_dataset.csv · product_category_name_translation.csv

Files are discovered by name pattern (the `olist_` prefix is optional) and are **never modified** by the pipeline.
They are git-ignored because of their size (~126 MB). A 2,000-order sample for demos/CI is in `data/sample/`.
Alternatively set `NEXUS_RAW_DIR` in `.env` to read them from another folder.

Checksums of the files used for the delivered build: `reports/data_quality/source_inventory.csv`.

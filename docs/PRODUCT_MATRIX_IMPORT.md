# Product Matrix Import

Campaign Autopilot supports CSV product matrix import.

Required columns:

```text
sku,product_name
```

Supported columns:

```text
sku,product_name,category,price,stock_qty,product_url,photo_1,photo_2,photo_3,priority
```

Rules:

- Missing `sku` or `product_name` skips only that row.
- Missing photos create `missing_photo` warnings and block real video readiness, but not demand or prompt preparation.
- Missing price creates `missing_price`.
- Missing stock creates `missing_stock`.
- Duplicate SKU rows in one import are skipped with a warning.
- One bad row never fails the whole file.

Example:

```csv
sku,product_name,category,price,stock_qty,product_url,photo_1,photo_2,photo_3,priority
BOMBAR-001,Acid Peel 30 ml,Skincare,799,120,https://example.com/products/bombar-001,https://example.com/packshot_001.png,,,5
```

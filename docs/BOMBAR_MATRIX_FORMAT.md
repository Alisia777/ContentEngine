# Bombar Matrix Format

Bombar matrix import supports CSV and XLSX.

Required columns:

```text
sku,product_name
```

Supported columns:

```text
sku,product_name,category,price,margin,stock_qty,product_url,photo_1,photo_2,photo_3
```

## Import Behavior

- Bombar rows are stored in the generic `ProductMatrixImport` / `ProductMatrixRow` tables.
- Bombar-only fields such as `margin` are preserved in `ProductMatrixRow.raw_json`.
- Rows with missing `sku` or `product_name` are skipped with row-level errors.
- Missing `photo_1`/`photo_2`/`photo_3` creates `missing_photo`.
- Missing `price` creates `missing_price`.
- Missing `margin` creates `missing_margin`.
- Missing `stock_qty` creates `missing_stock`.
- Missing `product_url` creates `missing_product_url`.
- One bad row does not fail the whole file.

Photo warnings are important: content preparation can still build demand, CreativeSpec, variants, and prompt packs, but real provider generation should stay blocked until an approved primary product reference exists.

## Example CSV

```csv
sku,product_name,category,price,margin,stock_qty,product_url,photo_1,photo_2,photo_3
BOMBAR-001,Acid Peel 30 ml,Skincare,799,0.42,120,https://example.com/p/1,https://example.com/packshot.png,,
```

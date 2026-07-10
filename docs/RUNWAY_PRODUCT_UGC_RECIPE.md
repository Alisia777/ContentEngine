# Runway Product UGC Recipe

ContentEngine uses the official Runway Product UGC recipe as the execution backend for creator-led product videos.

Official references:

- <https://docs.dev.runwayml.com/recipes/product-ugc/>
- <https://dev.runwayml.com/recipes/product_ugc>
- <https://docs.dev.runwayml.com/recipes/reference-media/>

## Ownership Boundary

Runway owns video synthesis. ContentEngine owns:

- SKU and exact-variant isolation;
- creator reference and likeness consent;
- three or four approved product references;
- structured product information and creative direction;
- spend gates, payload preview, result download and report;
- mandatory human review and publishing approval.

ContentEngine does not recreate Runway's storyboard or UGC synthesis engine.

## Official Wire Contract

`POST https://api.dev.runwayml.com/v1/recipes/product_ugc`

Pinned workflow version: `2026-06`.

The provider request contains only:

- `version`;
- `characterImage`;
- `productImage`;
- `productInfo` (maximum 2500 characters);
- `userConcept` (maximum 3500 characters);
- `duration` (4–15 seconds);
- `ratio` (`720:1280` or `1080:1920`);
- `audio`.

Runway accepts one `productImage` for Product UGC. ContentEngine deliberately requires three or four product references before the request:

1. front / primary product image;
2. second angle;
3. scale or product-in-hand image;
4. category-appropriate use/proof image when the brief asks the creator to use the product.

Only the approved front image is sent as `productImage`. The other references are evidence for variant identity, physical scale, scene permissions and human review. They are never added as unsupported provider fields.

## Hard Gates

A draft remains blocked when any condition is true:

- fewer than three or more than four product references;
- duplicate files reused as different angles;
- missing front, second-angle or scale role;
- primary reference is not an approved front view;
- references belong to different variants;
- SKU/variant confirmation is absent;
- creator likeness consent is absent;
- a use/application scene has no category-appropriate fourth proof image;
- required creative brief fields are empty;
- recipe text or output settings exceed official limits.

## Operator Flow

Open `/mvp-launch`, select a product and complete the Product UGC form. The first action only creates a recipe draft and payload preview. It never calls Runway.

After a draft is `ready_for_paid_preflight`, the explicit paid runner is:

```powershell
$env:QVF_GENERATION_MODE="real"
$env:QVF_ALLOW_REAL_SPEND="true"
$env:RUNWAYML_API_SECRET="..."

python scripts\run_product_ugc_recipe.py --draft-id <ID> --real-run
```

There is no mock fallback in this command. A successful result is downloaded locally, a generation report is written, and the draft becomes:

- `generated_needs_human_review`;
- `human_review_status = needs_human_review`;
- `publishing_readiness = blocked`.

Human review is recorded through `POST /api/runway-recipes/product-ugc/{draft_id}/review` with `status` equal to `approved`, `needs_regeneration` or `rejected`, plus mandatory notes. Review is rejected until a non-empty local output exists. Only an explicit `approved` decision changes `publishing_readiness` to `ready_for_package`.

API keys, image data URIs and signed output URLs are not persisted in the draft or report.

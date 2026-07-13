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

1. front identity image;
2. second angle;
3. scale or product-in-hand image;
4. category-appropriate use/proof image when the brief asks the creator to use the product.

The operator explicitly selects one provider-compatible reference as Runway `productImage`. It can be the exact front or a category-safe composite that shows the exact product in context. For food, a wrapper-plus-product or product-on-surface composite is preferred when the edible structure matters. The separate approved front remains mandatory identity evidence. Other references prove variant identity, physical scale, scene permissions and human-review expectations; they are never added as unsupported provider fields.

## Hard Gates

A draft remains blocked when any condition is true:

- fewer than three or more than four product references;
- duplicate files reused as different angles;
- missing front, second-angle or scale role;
- selected Runway `productImage` is not an approved exact front or category-safe product/use composite;
- references belong to different variants;
- SKU/variant confirmation is absent;
- creator likeness consent is absent;
- character image contains another product, package or logo that could contaminate product identity;
- a use/application scene has no category-appropriate fourth proof image;
- a food brief requests a bite, chewing or product near the mouth without an approved `bitten_product` reference;
- the form variant tries to override the variant stored on the selected SKU;
- neither the brief nor the product card records forbidden visuals or claims;
- required creative brief fields are empty;
- recipe text or output settings exceed official limits.

## Operator Flow

Open `/mvp-launch`, select a product and complete the Product UGC form. The first action only creates a recipe draft and payload preview. It never calls Runway.

The operator form mirrors the official recipe inputs without weakening ContentEngine controls:

- one clean creator image;
- exactly three or four distinct images of one SKU/variant;
- one explicit provider `productImage` selection;
- product information and a structured creator task;
- category-specific proof type for real use/application;
- explicit audio `yes/no`, 4–15 second duration and vertical ratio;
- a live seven-gate readiness panel that keeps draft submission disabled until the visible contract is complete.

Presentation can use three or four references. Product use requires a fourth proof reference. The proof selector changes by product profile: food, cosmetics, apparel, household or general. The same rules are re-evaluated server-side immediately before a paid task is reserved, so an old draft or a bypassed browser check cannot call Runway with stale readiness.

The same page then exposes paid preflight only when all of these are ready:

- draft gates;
- owner/admin role permission;
- `QVF_GENERATION_MODE=real`;
- `QVF_ALLOW_REAL_SPEND=true`;
- configured `RUNWAYML_API_SECRET`.

The operator must confirm one task, type the exact estimated credit count and acknowledge mandatory human review. The draft is atomically reserved before provider submission, so a repeated click cannot create a second task. While Runway is working, the page polls only safe draft status. After completion it renders the downloaded local MP4, task ID, safe report link and the manual approve/regenerate/reject form.

Before paid submission the page renders the exact two images that the official recipe will receive: `characterImage` and `productImage`. The character reference must show only the creator and neutral context. A different product or distorted package in that image is a hard blocker even when the selected product image is correct.

The CLI remains available for controlled operator use:

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

Human review is recorded through `POST /api/runway-recipes/product-ugc/{draft_id}/review` with `status` equal to `approved`, `needs_regeneration` or `rejected`, plus mandatory notes. Review is rejected until exactly one non-empty durable output exists in cloud mode (or one local output in local development). Only an explicit `approved` decision changes `publishing_readiness` to `ready_for_publishing_package`, and the exact reviewed artifact identity is persisted for package lineage.

API keys, image data URIs and signed output URLs are not persisted in the draft or report.

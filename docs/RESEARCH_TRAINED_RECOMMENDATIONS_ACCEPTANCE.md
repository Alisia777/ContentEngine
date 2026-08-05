# Research-trained editable recommendations — acceptance run

This release restores the intended AI-first product flow without taking editing control away from the operator.

## Exact acceptance source

- Project: `4f0fcfa2-7233-4c0c-9e16-2c20e0aae379`
- Input URL: `https://www.youtube.com/shorts/CXssfXBVInw`
- Canonical source key expected by the research provider: `https://youtube.com/watch?v=CXssfXBVInw`

The canonical form is an identity key only. The UI still shows the original source as a public YouTube link, and the research provider remains responsible for what it can actually verify.

## Required user flow

1. Open **Исследования** for the project.
2. Paste the Shorts URL into **Ролик, который ИИ должен разобрать**.
3. Fill the normal research scope/category and start the existing paid research run.
4. Wait for `completed`; the run must create the existing AI research receipt.
5. Open **ИИ-центр** and the matching product category.
6. Confirm that the rich queue shows:
   - exact source URL and title;
   - available source-level analysis and its limitations;
   - category analysis;
   - competitor structures and saturated patterns;
   - trend signals;
   - up to three scenario recommendations.
7. Select the useful analysis blocks and scenario variants.
8. Edit hook, script, shots, key message, visual direction or CTA as needed.
9. Confirm **Обучить на выбранном и сохранить рекомендации**.
10. Open **Создать** for the same project, product and category.
11. Confirm that an exact-product recommendation fills an empty **Замысел** automatically.
12. Edit any line and trigger a recommendation reload (change platform/category and back).
13. Confirm that the human-edited text is not overwritten.

## Non-negotiable safety/quality assertions

- A completed research run alone does not affect generation.
- An unreviewed receipt does not affect generation.
- Raw captions, transcripts or source text are never copied into the recommendation ledger.
- The AI-center decision is append-only and auditable.
- Generation reads only human-approved selections from the exact project/category.
- Category-only recommendations are shown, but are not silently auto-applied to another product.
- Recommendation lookup performs no provider call and starts no paid work.
- Manual generation remains available if recommendation lookup fails.

## Deployment order

1. Apply `202608050004_research_trained_recommendations.sql`.
2. Deploy the SPA assets from the same commit.
3. Hard-refresh the GitHub Pages build.
4. Run the exact acceptance source above.

The URL cannot be truthfully marked “analysed” until this acceptance run reaches the live provider and the resulting receipt appears in the deployed AI center.

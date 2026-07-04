# Video Creative Spec

Sprint 04 adds a hook-driven product layer before provider prompts.

The `VideoCreativeSpec` is built from:

1. Product data.
2. Marketplace metrics.
3. Review insights.
4. Market signals.
5. Brand rules.
6. Creative Intelligence Pack.

It contains:

- platform, format, aspect ratio, and duration
- creative objective and angle
- three hook candidates
- selected hook type, hook text, and viewer promise
- first-frame requirements
- scene plan with roles, captions, voiceover, claim refs, camera, composition, and lighting
- product display rules
- must include and must avoid lists
- allowed claim refs and source map
- reference images when product images exist
- metadata quality rubric
- validation report and warnings

The spec is not a generic script. It is the operating brief for a video model.

Validation checks include first-frame product visibility, captions, CTA, scene roles, claim refs, forbidden words/claims, duration consistency, explicit product display rules, and a quality rubric.

No image generation is called in Sprint 04. If `Product.images_json` is empty, the spec records a warning and prompts must not hallucinate packaging.

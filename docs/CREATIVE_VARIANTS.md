# Creative Variants

Sprint 05 turns one structured creative spec into several controllable video options.

Flow:

```text
Product
-> Product Asset Kit
-> Creative Intelligence Pack
-> VideoCreativeSpec
-> First Frame Options
-> Creative Variants
-> Variant Score
-> Selected Variant
-> PromptPack from variant
-> Video generation through Sprint 03 gates
```

`FirstFrameBuilder` creates three first-frame options from hook candidates, objective, platform, asset readiness, product display rules, and performance flags. Each option includes hook text, overlay, visual concept, product placement, camera motion, composition, required assets, risk flags, and product visibility timing.

`CreativeVariantBuilder` combines first-frame options with alternate pacing, CTA framing, visual style, and reveal timing. This step never calls paid video providers.

`VariantScorer` is transparent and metadata/rules-based. It scores hook strength, first-frame clarity, product visibility, claim safety, asset readiness, platform fit, CTA clarity, and risk penalty. It penalizes missing assets, late product reveal, forbidden/medical claims, and vague hooks. It boosts low-CTR matching hooks, buyer-language alignment, and short readable overlays.

`VariantSelector` chooses the highest safe score. If every variant is risky, the set is marked `needs_review` instead of silently choosing a bad option.

Prompt packs can be built from a selected variant:

```bash
python scripts/build_creative_variants.py --creative-spec-id 1 --count 5
python scripts/generate_from_variant.py --creative-variant-id 1 --build-prompts-only
```

Real generation remains out of scope for Sprint 05 CLI and still uses Sprint 03 spend gates through the normal video generator path.

# AI Brief Contract

v2.3 adds the final production contract before provider prompts.

The workflow is:

```text
ProductStrategySpec
-> OfferStrategy
-> BloggerMeaningSpec
-> UGCAdScript
-> CreativeQualityScore
-> AIProductionBrief
-> SceneBlueprint
-> DirectorPromptPack
-> PromptPack / provider payload
```

The contract answers:

- what the ad must say;
- what each scene must show;
- what each scene proves;
- where and how the real product asset appears;
- what must not be changed;
- what counts as failure.

## UI

Open:

```text
/ai-brief-studio
```

Sections:

- Final Brief Contract;
- Scene Blueprint;
- Product Visibility / Lock;
- Director Prompt Preview;
- Brief Quality Check;
- Export Markdown / JSON / Prompt Pack.

## CLI

```bash
python scripts/build_ai_production_brief.py --product-id 1 --platform "Instagram Reels"
python scripts/build_scene_blueprint.py --ai-production-brief-id 1
python scripts/build_director_prompt_pack.py --ai-production-brief-id 1
python scripts/check_ai_brief_quality.py --ai-production-brief-id 1
python scripts/export_ai_brief_markdown.py --ai-production-brief-id 1
```

The quality check blocks weak, empty, generic, or unsafe briefs before provider generation. It does not call paid providers.

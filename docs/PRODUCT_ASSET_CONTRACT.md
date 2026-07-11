# Product Asset Contract

For creator-led videos executed through the official Runway recipe, see [RUNWAY_PRODUCT_UGC_RECIPE.md](RUNWAY_PRODUCT_UGC_RECIPE.md). The Product Asset Contract remains the identity and scene-safety layer; it is not a replacement for Runway's synthesis workflow.

The one-video flow is product-agnostic. Its invariant is:

`blogger + exact product identity + category-appropriate real use + human review`

Bombbar is the first food acceptance case, not the domain model.

## Identity boundary

Identity and use references belong to one exact boundary:

`product_id + SKU + variant_key`

- Identity, geometry, handling, proof and interaction assets from another variant never raise readiness.
- Style and lifestyle references may be shared only as non-identity context.
- Multiple explicit variant keys on one product create a hard blocker.
- Cyrillic and Latin variant keys are supported.

For example, Mango & Kunafa references must not be combined with Raspberry & Pistachio references even when both products use the same brand and wrapper family.

## Category profiles

| Profile | Blogger interaction | Tier 4 proof |
| --- | --- | --- |
| `food_snack` | taste | bite/opening/near-mouth references |
| `cosmetic` | apply | application area, application demo and use video |
| `apparel` | try on | on-body movement and use video |
| `household` | demonstrate | approved operation, handling and use video |
| `general` | use case | approved interaction and use video |

A profile cannot borrow another profile's action. Cosmetics never unlock bite scenes; apparel does not use cosmetic application gates.

## Tiers

- `tier_0`: no approved identity reference. Strategy only.
- `tier_1`: exact front packshot. Static overlay/end card only.
- `tier_2`: identity plus another angle plus scale/handling context. Final-ad planning is allowed, but exact labels still use overlay/end card.
- `tier_3`: category-specific proof and use-case references. Approved inserts are allowed; unsupported interaction remains blocked.
- `tier_4`: category-specific interaction references. The matching real use can be planned, but output still requires human review.

One photo never unlocks provider-generated product handling. Style or lifestyle images never unlock product use.

## Runtime gates

The contract is evaluated before prompt generation and before any real provider call. It is included in:

- One Video Acceptance;
- reference and smoke readiness;
- EngineAudit and Control Room;
- AI production brief and DirectorPrompt;
- product compositing readiness.

Paid execution remains separately gated by generation mode, spend confirmation, provider credentials and operator approval.

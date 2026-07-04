# Demand Generator

Sprint 08 adds a product demand layer before creative spec generation.

Input:

```text
Product fields
+ marketplace metrics
+ creative performance
+ review insights
+ market signals
+ brand rules
```

Output:

- buyer need
- trigger situation
- pain point
- purchase objection
- safe promise
- blocked unsafe promises
- required proof
- recommended hook types
- recommended first frame
- source refs
- missing data

## Rules

- `low_ctr` -> awareness need with curiosity and benefit-first hooks.
- `low_conversion` -> trust and clarity need with objection/proof hooks.
- `high_returns` -> expectation-setting need.
- `competitor_price_pressure` -> comparison and value need.
- `stock_risk` -> soft education and no aggressive promo.
- no strong data -> simple product use-case introduction.

The generator is rules-based and source-backed. It does not use meeting notes or external business docs.

## Validation

`DemandValidator` checks:

- every safe product promise has source refs;
- missing proof marks the hypothesis as `needs_data`;
- medical, treatment, cure, and guaranteed-result promises are blocked;
- forbidden brand claims are blocked;
- stock risk blocks aggressive urgency language;
- blocked product references make real video generation ineligible.

Reference readiness does not block prompt-only creative work. It only blocks real smoke eligibility.

## Storage

Demand hypotheses are persisted in `DemandHypothesisRecord` with:

- `hypothesis_json`
- `signals_json`
- `validation_report_json`
- `source_summary_json`
- optional linked `creative_spec_id`

This gives the video generator an auditable reason for why a specific need, hook, and creative direction were selected.

from app import models
from app.intelligence.types import AllowedClaim, ProductFact


def product_facts(product: models.Product) -> tuple[list[ProductFact], list[AllowedClaim]]:
    facts: list[ProductFact] = []
    claims: list[AllowedClaim] = []
    if product.title:
        facts.append(ProductFact(fact=product.title, source="product.title"))
    if product.description:
        facts.append(ProductFact(fact=product.description, source="product.description"))
        claims.append(
            AllowedClaim(
                claim=product.description,
                source_type="product_field",
                source_key="description",
            )
        )
    for index, benefit in enumerate(product.benefits_json or []):
        facts.append(ProductFact(fact=str(benefit), source=f"product.benefits_json[{index}]"))
        claims.append(
            AllowedClaim(
                claim=str(benefit),
                source_type="product_field",
                source_key=f"benefits_json[{index}]",
            )
        )
    for key, value in (product.attributes_json or {}).items():
        facts.append(ProductFact(fact=f"{key}: {value}", source=f"product.attributes_json.{key}"))
    return facts, claims


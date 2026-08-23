"""Реестр маршрутов и словарь edge обязаны знать одних и тех же провайдеров.

ЧТО ЗДЕСЬ СТЕРЕЖЁТСЯ И ПОЧЕМУ ЭТО ВАЖНЕЕ, ЧЕМ ВЫГЛЯДИТ.

Витрина маршрутов отдаёт браузеру ВСЕ строки реестра, включая выключенные. Так
сделано намеренно и записано в самой миграции: экран должен уметь показать
«движок есть, но пока недоступен», а не молчать о нём. Выборка идёт без
`where route.enabled`.

Edge-функция проверяет каждую строку витрины набором известных провайдеров. Один
незнакомый провайдер в ЛЮБОЙ строке обнуляет ВЕСЬ ответ политики, и оба каталога
отвечают 503 generation_unavailable.

Отсюда следствие, которое легко упустить: строка ВЫКЛЮЧЕННОГО маршрута нового
провайдера гасит весь экран генерации — вместе с чужими работающими платными
маршрутами. Выключенность не защищает, потому что витрина отдаёт выключенные
строки специально.

Это уже случилось 22.08.2026: миграция `202608220011` завела выключенную строку
`provider = 'heygen'`, а набор в edge знал только runway, google и fal. Экран
стратегий и каталог моделей умерли бы целиком, включая работающую «Копию», и
падение произошло бы до первого нажатия — одним 503 без внятной причины.

ПРАВИЛО: провайдер попадает в словарь edge ОДНОВРЕМЕННО с появлением его первой
строки в реестре, а не тогда, когда маршрут включают.
"""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
EDGE = ROOT / "supabase" / "functions" / "creator-generate" / "index.ts"
CATALOG = ROOT / "supabase" / "functions" / "_shared" / "generation-strategy-catalog.js"


def _edge_set(name: str) -> set[str]:
    """Прочитать набор строковых значений из объявления в edge-функции."""

    source = EDGE.read_text(encoding="utf-8")
    body = source.split(f"const {name} = new Set([", 1)[1].split("]);", 1)[0]
    return set(re.findall(r'"([^"]+)"', body))


def _registry_providers() -> set[str]:
    """Провайдеры, у которых есть строка в реестре маршрутов.

    Берутся из вставок в таблицу: именно они и приедут в витрину, а оттуда — в
    проверку edge.
    """

    providers: set[str] = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        for block in sql.split(
            "insert into content_factory.generation_strategy_provider_routes"
        )[1:]:
            values = block.split("values", 1)[-1].split(";", 1)[0]
            # Провайдер — второе строковое значение в каждом кортеже, сразу за
            # идентификатором стратегии.
            for tuple_text in re.findall(r"'viral_[a-z_]+',\s*'([a-z]+)'", values):
                providers.add(tuple_text)
    return providers


def test_every_provider_in_the_registry_is_known_to_the_edge() -> None:
    """Незнакомый провайдер в реестре гасит ВЕСЬ экран, а не только свой маршрут."""

    registry = _registry_providers()
    known = _edge_set("GENERATION_ROUTE_PROVIDERS")

    assert registry, "не нашлось ни одной вставки в реестр маршрутов"
    unknown = registry - known
    assert not unknown, (
        f"провайдеры {sorted(unknown)} есть в реестре, но неизвестны edge — "
        "витрина отдаст их строки браузеру, и оба каталога ответят 503 "
        "generation_unavailable, включая работающие платные маршруты"
    )


def test_registry_providers_are_also_known_to_the_strategy_catalog() -> None:
    """Тот же словарь во втором месте: каталог подписывает им квитанции."""

    catalog = CATALOG.read_text(encoding="utf-8")
    block = catalog.split("GENERATION_STRATEGY_PROVIDERS = Object.freeze([", 1)[1]
    block = block.split("]);", 1)[0]
    declared = set(re.findall(r'"([^"]+)"', block))

    unknown = _registry_providers() - declared
    assert not unknown, (
        f"провайдеры {sorted(unknown)} есть в реестре, но каталог их не знает — "
        "квитанция готовности такому маршруту не выпишется"
    )


def test_price_kinds_and_tiers_used_by_the_registry_are_known() -> None:
    """Та же ловушка у соседних полей строки маршрута.

    Витрина отдаёт строку целиком, и незнакомым может оказаться не только
    провайдер: вид цены и ярус проверяются теми же наборами и роняют ответ так же
    целиком.
    """

    known_kinds = _edge_set("GENERATION_ROUTE_PRICE_KINDS")
    known_tiers = _edge_set("GENERATION_ROUTE_TIERS")

    used_kinds: set[str] = set()
    used_tiers: set[str] = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        for block in sql.split(
            "insert into content_factory.generation_strategy_provider_routes"
        )[1:]:
            values = block.split("values", 1)[-1].split(";", 1)[0]
            used_kinds.update(
                re.findall(r"'(usd_minor_per_run|usd_minor_per_second|runway_credit_tiers)'", values)
            )
            used_tiers.update(re.findall(r"'(cheap|medium|premium)'", values))

    assert used_kinds, "не нашлось ни одного вида цены во вставках реестра"
    assert not used_kinds - known_kinds, sorted(used_kinds - known_kinds)
    assert not used_tiers - known_tiers, sorted(used_tiers - known_tiers)


def test_the_showcase_deliberately_returns_disabled_routes() -> None:
    """Документирует ПРИЧИНУ, по которой выключенность не защищает.

    Если однажды витрину начнут фильтровать по `enabled`, этот тест упадёт — и
    тогда правило «провайдер в словарь одновременно со строкой реестра» можно
    будет ослабить осознанно, а не забыть о нём молча.
    """

    showcase = (
        MIGRATIONS / "202608180003_generation_strategy_catalog_provider_routes_v1.sql"
    ).read_text(encoding="utf-8")

    routes_block = showcase.split("generation_strategy_provider_routes as route", 1)[1]
    routes_block = routes_block.split("group by", 1)[0]
    assert "where" not in routes_block.lower(), (
        "витрина начала фильтровать маршруты — проверьте, не отпало ли правило "
        "про словарь провайдеров"
    )
    assert "'enabled', route.enabled" in showcase, (
        "витрина перестала отдавать признак включённости — экран не сможет "
        "показать «движок есть, но пока недоступен»"
    )

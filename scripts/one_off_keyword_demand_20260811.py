#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

STAMP = "2026-08-11"
OUTPUT_DIR = Path("docs/research")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SEEDS: list[tuple[str, str]] = [
    ("Продажи и продвижение", "продвижение на маркетплейсах"),
    ("Продажи и продвижение", "продвижение товаров на маркетплейсах"),
    ("Продажи и продвижение", "продвижение товара на wildberries"),
    ("Продажи и продвижение", "продвижение товара на wb"),
    ("Продажи и продвижение", "продвижение товара на ozon"),
    ("Продажи и продвижение", "раскрутка товара на wildberries"),
    ("Продажи и продвижение", "реклама товара на wildberries"),
    ("Продажи и продвижение", "реклама товара на ozon"),
    ("Продажи и продвижение", "увеличить продажи на wildberries"),
    ("Продажи и продвижение", "как увеличить продажи на wildberries"),
    ("Продажи и продвижение", "увеличить продажи на ozon"),
    ("Продажи и продвижение", "запуск товара на wildberries"),
    ("Продажи и продвижение", "вывод товара в топ wildberries"),
    ("Продажи и продвижение", "агентство по продвижению маркетплейсов"),
    ("Продажи и продвижение", "ведение маркетплейсов"),
    ("Продажи и продвижение", "ведение wildberries"),
    ("Продажи и продвижение", "ведение ozon"),
    ("Продажи и продвижение", "маркетплейс агентство"),
    ("Продажи и продвижение", "услуги для маркетплейсов"),
    ("Внешний трафик", "внешний трафик на маркетплейсы"),
    ("Внешний трафик", "внешний трафик wildberries"),
    ("Внешний трафик", "внешний трафик wb"),
    ("Внешний трафик", "внешний трафик ozon"),
    ("Внешний трафик", "внешний трафик на wildberries"),
    ("Внешний трафик", "внешний трафик на ozon"),
    ("Внешний трафик", "внешняя реклама wildberries"),
    ("Внешний трафик", "внешняя реклама ozon"),
    ("Внешний трафик", "внешняя реклама маркетплейсов"),
    ("Видео для товаров", "видео для маркетплейсов"),
    ("Видео для товаров", "видео для карточки товара"),
    ("Видео для товаров", "видео для wildberries"),
    ("Видео для товаров", "видео для ozon"),
    ("Видео для товаров", "видеосъемка для маркетплейсов"),
    ("Видео для товаров", "видеосъемка товара для маркетплейсов"),
    ("Видео для товаров", "продающее видео для маркетплейсов"),
    ("Видео для товаров", "видеообзор товара"),
    ("Видео для товаров", "распаковка товара видео"),
    ("Видео для товаров", "креативы для маркетплейсов"),
    ("Видео для товаров", "видео реклама товара"),
    ("Видео для товаров", "короткие видео для бизнеса"),
    ("Видео для товаров", "рилс для бизнеса"),
    ("Видео для товаров", "reels для бренда"),
    ("UGC и креаторы", "ugc для маркетплейсов"),
    ("UGC и креаторы", "ugc контент для бренда"),
    ("UGC и креаторы", "ugc контент заказать"),
    ("UGC и креаторы", "заказать ugc видео"),
    ("UGC и креаторы", "ugc агентство"),
    ("UGC и креаторы", "ugc студия"),
    ("UGC и креаторы", "креаторы для бренда"),
    ("UGC и креаторы", "креатор для маркетплейсов"),
    ("Контент-производство", "контент для маркетплейсов"),
    ("Контент-производство", "создание контента для маркетплейсов"),
    ("Контент-производство", "контент завод"),
    ("Контент-производство", "контент завод для бизнеса"),
    ("Контент-производство", "контент завод для бренда"),
    ("Контент-производство", "производство контента для соцсетей"),
    ("Контент-производство", "контент на аутсорсе"),
    ("Контент-производство", "отдел контента на аутсорсе"),
    ("Контент-производство", "внешний отдел маркетинга"),
    ("Контент-производство", "контент маркетинг для маркетплейсов"),
    ("AI-контент", "ai видео для товара"),
    ("AI-контент", "ии видео для товара"),
    ("AI-контент", "видео из фото товара"),
    ("AI-контент", "генерация видео для маркетплейсов"),
    ("AI-контент", "нейросеть для видео товара"),
    ("AI-контент", "нейросеть для видео маркетплейсов"),
    ("AI-контент", "нейрофотосессия товара"),
    ("AI-контент", "ai контент для маркетплейсов"),
    ("Блогеры и performance", "блогеры для wildberries"),
    ("Блогеры и performance", "блогеры для ozon"),
    ("Блогеры и performance", "реклама у блогеров wildberries"),
    ("Блогеры и performance", "продвижение товара через блогеров"),
    ("Блогеры и performance", "блогеры за процент от продаж"),
    ("Блогеры и performance", "реклама товара с оплатой за заказ"),
    ("Блогеры и performance", "cpo продвижение"),
    ("Блогеры и performance", "партнерская программа для бренда"),
    ("Система и аналитика", "автоматизация контента для маркетплейсов"),
    ("Система и аналитика", "система управления контентом"),
    ("Система и аналитика", "управление контентом товаров"),
    ("Система и аналитика", "аналитика контента"),
    ("Система и аналитика", "аналитика креативов"),
    ("Система и аналитика", "платформа для создания контента"),
    ("Система и аналитика", "контент платформа для бизнеса"),
]


def normalize(value: str) -> str:
    value = str(value or "").casefold().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def number(value: object) -> int:
    try:
        return int(float(str(value or 0).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def load_json(url: str, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ContentEngine-keyword-research/1.1",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8-sig", errors="replace"))
        except Exception as error:  # network collector; preserve diagnostics
            last_error = error
            time.sleep(1 + attempt)
    raise RuntimeError(f"request failed: {last_error}")


def parse_row(row: object) -> dict[str, object] | None:
    if isinstance(row, list) and len(row) >= 5:
        return {
            "keyword": str(row[0] or "").strip(),
            "words": number(row[1]),
            "characters": number(row[2]),
            "broad": number(row[3]),
            "exact": number(row[4]),
        }
    if isinstance(row, dict):
        keyword = row.get("keyword") or row.get("word") or row.get("query") or row.get("Ключевое слово")
        values = list(row.values())
        if not keyword and values:
            keyword = values[0]
        broad = row.get("broad") or row.get("frequency") or (values[3] if len(values) > 3 else 0)
        exact = row.get("exact") or row.get("exact_frequency") or (values[4] if len(values) > 4 else 0)
        return {
            "keyword": str(keyword or "").strip(),
            "words": number(row.get("words") or (values[1] if len(values) > 1 else 0)),
            "characters": number(row.get("characters") or (values[2] if len(values) > 2 else 0)),
            "broad": number(broad),
            "exact": number(exact),
        }
    return None


def bukvarix(seed: str) -> list[dict[str, object]]:
    params = urllib.parse.urlencode(
        {"q": seed, "api_key": "free", "num": 350, "format": "json", "json_type": "array"}
    )
    errors: list[str] = []
    for scheme in ("https", "http"):
        try:
            payload = load_json(f"{scheme}://api.bukvarix.com/v1/keywords/?{params}")
            if not isinstance(payload, list):
                raise TypeError(type(payload).__name__)
            return [parsed for parsed in (parse_row(row) for row in payload) if parsed and parsed["keyword"]]
        except Exception as error:
            errors.append(f"{scheme}: {error}")
    raise RuntimeError("; ".join(errors))


def suggestions(seed: str) -> list[str]:
    params = urllib.parse.urlencode({"part": seed, "lr": 225, "v": 4, "uil": "ru", "n": 10})
    try:
        payload = load_json(f"https://suggest.yandex.ru/suggest-ya.cgi?{params}", attempts=2)
        if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list):
            return [str(item).strip() for item in payload[1] if str(item).strip()]
    except Exception:
        pass
    return []


def escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    collected_at = datetime.now(timezone.utc).isoformat()
    seed_rows: list[dict[str, object]] = []
    raw_rows: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    for index, (cluster, seed) in enumerate(SEEDS, start=1):
        try:
            related = bukvarix(seed)
        except Exception as error:
            related = []
            errors.append({"cluster": cluster, "seed": seed, "error": str(error)})

        normalized_seed = normalize(seed)
        direct = [row for row in related if normalize(str(row["keyword"])) == normalized_seed]
        if not direct:
            tokens = sorted(normalized_seed.split())
            direct = [row for row in related if sorted(normalize(str(row["keyword"])).split()) == tokens]
        direct_row = max(direct, key=lambda row: (number(row["exact"]), number(row["broad"])), default=None)
        live_suggestions = suggestions(seed)
        top_related = sorted(related, key=lambda row: (number(row["exact"]), number(row["broad"])), reverse=True)[:10]

        seed_rows.append(
            {
                "cluster": cluster,
                "seed": seed,
                "broad_frequency_world": number(direct_row["broad"]) if direct_row else 0,
                "exact_frequency_world": number(direct_row["exact"]) if direct_row else 0,
                "direct_match": str(direct_row["keyword"]) if direct_row else "",
                "related_rows": len(related),
                "live_yandex_suggestions_count": len(live_suggestions),
                "live_yandex_suggestions": " | ".join(live_suggestions),
                "top_related": " | ".join(f"{row['keyword']} [{row['exact']}]" for row in top_related),
                "collected_at": collected_at,
            }
        )
        raw_rows.extend({"cluster": cluster, "seed": seed, **row} for row in related)
        print(
            json.dumps(
                {
                    "progress": f"{index}/{len(SEEDS)}",
                    "seed": seed,
                    "exact": seed_rows[-1]["exact_frequency_world"],
                    "related": len(related),
                    "suggestions": len(live_suggestions),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        time.sleep(0.1)

    seed_rows.sort(
        key=lambda row: (number(row["exact_frequency_world"]), number(row["broad_frequency_world"])),
        reverse=True,
    )

    csv_path = OUTPUT_DIR / f"contentengine_keyword_demand_{STAMP}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(seed_rows[0]))
        writer.writeheader()
        writer.writerows(seed_rows)

    raw_path = OUTPUT_DIR / f"contentengine_keyword_demand_raw_{STAMP}.json"
    raw_path.write_text(
        json.dumps(
            {
                "methodology": {
                    "collected_at": collected_at,
                    "bukvarix_region": "Весь мир",
                    "warning": "Не официальный текущий Wordstat. Bukvarix даёт broad/exact из своей базы; Yandex Suggest — живой языковой сигнал без частотности.",
                },
                "seeds": seed_rows,
                "raw": raw_rows,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in seed_rows:
        grouped[str(row["cluster"])].append(row)
    cluster_rows: list[dict[str, object]] = []
    for cluster, rows in grouped.items():
        exact = [number(row["exact_frequency_world"]) for row in rows]
        nonzero = [value for value in exact if value > 0]
        cluster_rows.append(
            {
                "cluster": cluster,
                "seeds": len(rows),
                "nonzero": len(nonzero),
                "max_exact": max(exact or [0]),
                "median_exact_nonzero": int(statistics.median(nonzero)) if nonzero else 0,
                "suggestion_seeds": sum(number(row["live_yandex_suggestions_count"]) > 0 for row in rows),
                "top_seed": max(
                    rows,
                    key=lambda row: (number(row["exact_frequency_world"]), number(row["broad_frequency_world"])),
                )["seed"],
            }
        )
    cluster_rows.sort(
        key=lambda row: (number(row["max_exact"]), number(row["median_exact_nonzero"]), number(row["suggestion_seeds"])),
        reverse=True,
    )

    commercial = re.compile(
        r"\b(заказать|агентство|услуг|под ключ|цена|стоимость|ведение|купить|студия|съемк|съёмк|продвижение|реклама|увеличить|как|вывести|запуск|топ)\w*",
        re.I,
    )
    deduped: dict[str, dict[str, object]] = {}
    for row in raw_rows:
        key = normalize(str(row["keyword"]))
        previous = deduped.get(key)
        if not previous or (number(row["exact"]), number(row["broad"])) > (
            number(previous["exact"]),
            number(previous["broad"]),
        ):
            deduped[key] = row
    commercial_rows = [row for row in deduped.values() if commercial.search(str(row["keyword"]))]
    commercial_rows.sort(key=lambda row: (number(row["exact"]), number(row["broad"])), reverse=True)

    lines = [
        "# ContentEngine — фактический срез поискового спроса",
        "",
        f"Дата сбора: **{STAMP}**  ",
        f"UTC-время: `{collected_at}`",
        "",
        "## Методика и границы",
        "",
        "- Частотности: Bukvarix free API — broad и `!exact`, регион базы «Весь мир».",
        "- Живой сигнал языка: Yandex Suggest, регион 225.",
        "- Это **не** авторизованная текущая выгрузка Wordstat по России; значения нельзя выдавать за официальный месячный Wordstat.",
        "- Пересекающиеся фразы не суммируются в размер рынка. Здесь сравнивается сила языка и коммерческий интент.",
        "",
        "## Рейтинг кластеров",
        "",
        "| Кластер | Фраз | Ненулевых exact | Max exact | Median exact | С живыми подсказками | Сильнейшая seed-фраза |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in cluster_rows:
        lines.append(
            f"| {escape(row['cluster'])} | {row['seeds']} | {row['nonzero']} | {row['max_exact']} | "
            f"{row['median_exact_nonzero']} | {row['suggestion_seeds']} | {escape(row['top_seed'])} |"
        )

    lines.extend(
        [
            "",
            "## Seed-фразы",
            "",
            "| Кластер | Запрос | Broad | Exact | Yandex suggestions |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in seed_rows:
        lines.append(
            f"| {escape(row['cluster'])} | {escape(row['seed'])} | {row['broad_frequency_world']} | "
            f"{row['exact_frequency_world']} | {row['live_yandex_suggestions_count']} |"
        )

    lines.extend(
        [
            "",
            "## Сильные коммерческие и проблемные формулировки из связанных запросов",
            "",
            "| Запрос | Exact | Broad | Кластер |",
            "|---|---:|---:|---|",
        ]
    )
    for row in commercial_rows[:100]:
        lines.append(
            f"| {escape(row['keyword'])} | {row['exact']} | {row['broad']} | {escape(row['cluster'])} |"
        )

    if errors:
        lines.extend(["", "## Ошибки источника", ""])
        lines.extend(f"- `{escape(row['seed'])}`: {escape(row['error'])}" for row in errors)

    lines.extend(
        [
            "",
            "## Как читать для позиционирования",
            "",
            "1. Высокочастотная общая фраза может содержать обучение, вакансии и услуги одновременно.",
            "2. Низкочастотная транзакционная фраза часто ценнее информационной, потому что ближе к покупке.",
            "3. Финальный медиаплан требует официального Wordstat по России/Москве/СПб и прогноза Direct.",
            "4. Этот срез уже показывает, какими словами рынок описывает боль и какой оффер не надо объяснять с нуля.",
            "",
            f"CSV: `contentengine_keyword_demand_{STAMP}.csv`  ",
            f"Raw JSON: `contentengine_keyword_demand_raw_{STAMP}.json`",
        ]
    )
    md_path = OUTPUT_DIR / f"contentengine_keyword_demand_{STAMP}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "seeds": len(SEEDS),
                "raw_rows": len(raw_rows),
                "errors": len(errors),
                "outputs": [str(md_path), str(csv_path), str(raw_path)],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

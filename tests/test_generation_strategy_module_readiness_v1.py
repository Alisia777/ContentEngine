"""Готовность модуля стратегии обязана совпадать с тем, что подпишет сервер.

До этих проверок состояние `ready` решалось только полнотой файлов: модуль не
знал ни про маршруты, ни про роли, которые форма собрать не умеет. Оператор
видел зелёное «готово» там, где сервер отказал бы — уже после десяти ТЗ, десяти
одобрений и подтверждения суммы.

Тесты исполняемые: тела чистых функций вырезаются из модуля и запускаются в
Node. Проверка на вхождение подстроки здесь не годится — она подтверждает, что
строка написана, а не что решение принято правильно.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
GUIDED = ROOT / "web" / "app" / "workspace-os-v4-generation-guided.js"


def _between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def _run_node(source: str, *, timeout: int = 20) -> dict[str, object]:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI regressions"
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _readiness_contract() -> str:
    guided = GUIDED.read_text(encoding="utf-8")
    control_map = "const STRATEGY_ASSET_CONTROL_BY_ROLE" + _between(
        guided,
        "const STRATEGY_ASSET_CONTROL_BY_ROLE",
        "// Фото товара — единственная роль",
    )
    product_roles = "const STRATEGY_PRODUCT_ROLES" + _between(
        guided,
        "const STRATEGY_PRODUCT_ROLES",
        "function strategyProductRole",
    )
    product_role = "function strategyProductRole" + _between(
        guided,
        "function strategyProductRole",
        "// Маршрут — часть готовности",
    )
    route_unavailable = "function strategyRouteUnavailable" + _between(
        guided,
        "function strategyRouteUnavailable",
        "// Роль, которую форма собрать не умеет",
    )
    unsupported = "function strategyUnsupportedRequiredRoles" + _between(
        guided,
        "function strategyUnsupportedRequiredRoles",
        "// Какие фото товара реально уйдут в наряд",
    )
    return "\n".join(
        [control_map, product_roles, product_role, route_unavailable, unsupported]
    )


COPY_ROLES = [
    {"role": "source_video", "min_count": 1, "max_count": 1},
    {"role": "original_product_image", "min_count": 1, "max_count": 1},
    {"role": "new_product_image", "min_count": 1, "max_count": 10},
]
# Актуальный контракт «Аватара»: товар ушёл 21.08.2026, фотография
# необязательна (аватара можно задать описанием), верхняя граница — предел
# ссылок на изображения у Kling.
AVATAR_ROLES = [
    {"role": "source_video", "min_count": 1, "max_count": 1},
    {"role": "avatar_image", "min_count": 0, "max_count": 4},
]
REBUILD_ROLES = [
    {"role": "source_video", "min_count": 1, "max_count": 1},
    {"role": "product_image", "min_count": 1, "max_count": 10},
    {"role": "style_image", "min_count": 0, "max_count": 4},
]


def test_strategy_without_an_enabled_route_can_never_be_ready() -> None:
    payload = _run_node(
        f"""
{_readiness_contract()}

// Реестр маршрутов сегодня заведён на одну стратегию из трёх.
const published = {{
  viral_product_swap: [
    {{ provider: "fal", model_key: "fal-ai/pika/v2/pikaswaps", enabled: true }},
    {{ provider: "runway", model_key: "aleph2", enabled: true }},
  ],
}};

process.stdout.write(JSON.stringify({{
  copyRuns: strategyRouteUnavailable(published, "viral_product_swap") === false,
  avatarBlocked: strategyRouteUnavailable(published, "viral_avatar_ugc"),
  rebuildBlocked: strategyRouteUnavailable(published, "viral_rebuild"),
  disabledOnlyBlocked: strategyRouteUnavailable(
    {{ viral_avatar_ugc: [{{ provider: "runway", enabled: false }}] }},
    "viral_avatar_ugc",
  ),
  emptyListBlocked: strategyRouteUnavailable({{ viral_rebuild: [] }}, "viral_rebuild"),
}}));
"""
    )
    assert payload == {
        # У «Копии» маршруты есть — она обязана продолжать работать.
        "copyRuns": True,
        # У двух других строк реестра нет вовсе.
        "avatarBlocked": True,
        "rebuildBlocked": True,
        # Выключенный маршрут — это тоже «нельзя запускать».
        "disabledOnlyBlocked": True,
        "emptyListBlocked": True,
    }


def test_absent_registry_field_is_unknown_and_must_not_block_a_working_route() -> None:
    """Поле каталога необязательное: старый сервер его не отдаёт вовсе.

    Трактовать это как «маршрутов нет» нельзя — иначе на первом же таком ответе
    заблокировали бы работающую «Копию» и оператор потерял бы рабочий маршрут
    из-за версии сервера.
    """

    payload = _run_node(
        f"""
{_readiness_contract()}

process.stdout.write(JSON.stringify({{
  undefinedField: strategyRouteUnavailable(undefined, "viral_product_swap"),
  nullField: strategyRouteUnavailable(null, "viral_product_swap"),
  emptyObjectStillBlocks: strategyRouteUnavailable({{}}, "viral_product_swap"),
}}));
"""
    )
    assert payload == {
        # Реестра нет как понятия — решаем по-старому, не блокируем.
        "undefinedField": False,
        "nullField": False,
        # А вот пустой реестр — это уже ответ «маршрутов нет».
        "emptyObjectStillBlocks": True,
    }


def test_required_role_the_form_cannot_collect_blocks_instead_of_staying_silent() -> None:
    payload = _run_node(
        f"""
{_readiness_contract()}

const copy = {COPY_ROLES!s}.map((role) => role);
const avatar = {AVATAR_ROLES!s}.map((role) => role);
const rebuild = {REBUILD_ROLES!s}.map((role) => role);

// Роль, которой нет ни в карте селектов, ни среди товарных, и она обязательна.
const invented = [
  {{ role: "source_video", min_count: 1, max_count: 1 }},
  {{ role: "voiceover_track", min_count: 1, max_count: 1 }},
];

process.stdout.write(JSON.stringify({{
  copySupported: strategyUnsupportedRequiredRoles(copy).length,
  avatarSupported: strategyUnsupportedRequiredRoles(avatar).length,
  rebuildSupported: strategyUnsupportedRequiredRoles(rebuild).length,
  inventedBlocked: strategyUnsupportedRequiredRoles(invented).map((r) => r.role),
  copyProductRole: strategyProductRole({{ asset_roles: copy }}),
  avatarProductRole: strategyProductRole({{ asset_roles: avatar }}),
  rebuildProductRole: strategyProductRole({{ asset_roles: rebuild }}),
}}));
""".replace("'", '"')
    )
    assert payload == {
        # Все три сегодняшние стратегии форма собрать умеет: фото товара идут
        # чекбоксами, поэтому отсутствие их в карте селектов — не пробел.
        "copySupported": 0,
        "avatarSupported": 0,
        # style_image необязательна (min_count 0) и потому не блокирует.
        "rebuildSupported": 0,
        # А вот обязательная роль, которую собрать нечем, обязана остановить.
        "inventedBlocked": ["voiceover_track"],
        # Имя товарной роли зависит от стратегии и берётся из каталога.
        "copyProductRole": "new_product_image",
        # Товарной роли у «Аватара» больше нет вовсе.
        "avatarProductRole": "",
        "rebuildProductRole": "product_image",
    }


INTAKE = ROOT / "web" / "app" / "generation-strategy-intake-v4.js"


def test_fal_engines_are_dimmed_when_the_avatar_has_no_photo() -> None:
    """Отказ должен приходить на экране выбора, а не после резервирования денег.

    Обе модели fal требуют ссылку на изображение: у Pika `image_url`
    обязателен, у Kling ссылки `@ImageN` в указании должны на что-то указывать.
    Режим «Описание аватара» исполняет только Runway Aleph — он принимает текст.

    Без этого гашения оператор мог выбрать Pika с одним описанием: деньги
    зарезервировались бы, сборка запроса упала бы на `avatar_prompt_context_invalid`,
    и снаружи это выглядело бы случайным сбоем провайдера.
    """

    intake = INTAKE.read_text(encoding="utf-8")
    gate = "function withAvatarPhotoGate" + _between(
        intake,
        "function withAvatarPhotoGate",
        "function avatarPhotoAvailable",
    )
    payload = _run_node(
        f"""
{gate}

const engines = [
  {{ id: "fal:pika", provider: "fal", enabled: true }},
  {{ id: "fal:kling", provider: "fal", enabled: true }},
  {{ id: "runway:aleph2", provider: "runway", enabled: true }},
];

const withPhoto = withAvatarPhotoGate(engines, false);
const withoutPhoto = withAvatarPhotoGate(engines, true);

process.stdout.write(JSON.stringify({{
  withPhotoEnabled: withPhoto.map((engine) => engine.enabled),
  withoutPhotoEnabled: withoutPhoto.map((engine) => engine.enabled),
  reasons: withoutPhoto.map((engine) => engine.unavailableReason || null),
  originalUntouched: engines.every((engine) => engine.enabled === true),
}}));
"""
    )
    assert payload == {
        # С фотографией доступны все три движка.
        "withPhotoEnabled": [True, True, True],
        # Без фотографии остаётся только Runway: он единственный принимает текст.
        "withoutPhotoEnabled": [False, False, True],
        # И причина названа, а не просто «пока недоступна».
        "reasons": ["нужна фотография аватара", "нужна фотография аватара", None],
        # Исходный список не мутируется: перерисовка не должна портить данные,
        # из которых её же и построили.
        "originalUntouched": True,
    }

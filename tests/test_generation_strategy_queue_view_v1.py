from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/app"
ASSETS_MODULE = APP / "generation-strategy-assets.js"
SOURCE_PICKER_MODULE = APP / "generation-strategy-source-picker.js"
RUNTIME_MODULE = APP / "generation-strategy-runtime.js"
QUEUE_MODULE = APP / "generation-strategy-queue.js"
VIEW_MODULE = APP / "generation-strategy-queue-view.js"
ASSETS_SOURCE = ASSETS_MODULE.read_text(encoding="utf-8")
SOURCE_PICKER_SOURCE = SOURCE_PICKER_MODULE.read_text(encoding="utf-8")
RUNTIME_SOURCE = RUNTIME_MODULE.read_text(encoding="utf-8")
QUEUE_SOURCE = QUEUE_MODULE.read_text(encoding="utf-8")
VIEW_SOURCE = VIEW_MODULE.read_text(encoding="utf-8")


JS_FIXTURE = r"""
import * as viewContract from './generation-strategy-queue-view.js';

const clone = (value) => JSON.parse(JSON.stringify(value));
const uuid = (kind, index) => {
  const head = (kind * 1000 + index + 1).toString(16).padStart(8, '0');
  const tail = (kind * 100 + index + 1).toString(16).padStart(12, '0');
  return `${head}-0000-4000-8000-${tail}`;
};
const hash = (kind, index) =>
  (kind * 1000 + index + 1).toString(16).padStart(64, '0');
const sourceId = (index) => uuid(10, index);

const sourceProjection = (count = 10, options = {}) => {
  const selected = Array.from({length: count}, (_, index) => {
    const needsProbe = index === options.probeIndex;
    return {
      position: index + 1,
      source_media_id: sourceId(index),
      filename: index === 0 && options.firstFilename
        ? options.firstFilename
        : `hit-${index + 1}.mp4`,
      duration_seconds: needsProbe ? null : 4 + index / 10,
      ready: !needsProbe,
      probe_required: needsProbe,
      blocking_codes: needsProbe
        ? ['server_duration_probe_required']
        : [],
    };
  });
  const probeIds = selected
    .filter((row) => row.probe_required)
    .map((row) => row.source_media_id);
  return {
    version: 'generation-strategy-source-picker-v1',
    strategy_id: 'viral_rebuild',
    revision: 12,
    selected_count: count,
    required_count: 10,
    exactly_ten_selected: count === 10,
    all_selected_ready: count === 10 && probeIds.length === 0,
    selected,
    probe_required_source_ids: probeIds,
    error: null,
  };
};

const price = (index) => {
  const minor = 192 + index;
  return {
    price_hash: hash(40, index),
    strategy_id: 'viral_rebuild',
    recipe: 'product_ad',
    duration_seconds: 4,
    resolution: '720p',
    ratio: '720:1280',
    audio: false,
    estimated_credits: minor,
    estimated_cost_minor: minor,
    estimated_cost_usd: (minor / 100).toFixed(2),
    currency: 'USD',
  };
};

const runtimeFor = (index, phase = 'preflight_ready', options = {}) => {
  const hasPrice = [
    'bound', 'preflight_ready', 'human_confirmed', 'start_once', 'status',
  ].includes(phase);
  const hasReadiness = [
    'preflight_ready', 'human_confirmed', 'start_once', 'status',
  ].includes(phase);
  const jobStatus = phase === 'status' ? (options.jobStatus || 'processing') : null;
  const hasJobError = ['failed', 'cancelled'].includes(jobStatus);
  return {
    version: '2026-08-14.v1',
    phase,
    fingerprint: ['idle', 'invalid'].includes(phase) ? null : hash(20, index),
    identity: ['idle', 'invalid'].includes(phase) ? null : {
      organization_id: uuid(1, 0),
      project_id: uuid(2, 0),
      spec_id: uuid(3, 0),
      spec_version: 7,
      spec_hash: hash(3, 0),
      catalog_version: '2026-08-14.v1',
      strategy_id: 'viral_rebuild',
      recipe_version: '2026-06',
    },
    binding: hasPrice ? {
      id: uuid(30, index),
      binding_hash: hash(30, index),
      selection_hash: hash(31, index),
      bound_at: '2026-08-14T08:00:00.000Z',
    } : null,
    price: hasPrice ? price(index) : null,
    readiness: hasReadiness ? {
      receipt_id: uuid(50, index),
      receipt_hash: hash(50, index),
      ready: true,
      checked_at: '2026-08-14T08:01:00.000Z',
      expires_at: '2026-08-14T08:06:00.000Z',
      provider_preflight: {
        credential_configured: true,
        provider_authentication_confirmed: true,
      },
      launch_enabled: true,
    } : null,
    campaign_id: ['human_confirmed', 'start_once', 'status'].includes(phase)
      ? uuid(60, 0)
      : null,
    start_context_fingerprint: [
      'human_confirmed', 'start_once', 'status',
    ].includes(phase) ? hash(60, index) : null,
    job: phase === 'status' ? {
      id: uuid(70, index),
      batch_id: uuid(71, index),
      status: jobStatus,
      provider_status: jobStatus,
      estimated_cost_minor: 192 + index,
      actual_cost_minor: 192 + index,
      currency: 'USD',
    } : null,
    reconciliation: options.reconciliationRequired
      ? {required: true, incident_id: uuid(72, index)}
      : null,
    output: jobStatus === 'succeeded'
      ? {media_id: uuid(73, index), mime_type: 'video/mp4', size_bytes: 4096}
      : null,
    error: phase === 'invalid'
      ? {code: 'generation_strategy_context_changed', field: 'context'}
      : hasJobError
      ? {code: 'provider_generation_failed', provider_billing_outcome: 'unknown'}
      : null,
    can_preflight: phase === 'bound',
    can_confirm: phase === 'preflight_ready',
    can_start: phase === 'human_confirmed',
    start_reserved: phase === 'start_once',
    can_poll: phase === 'status' && ['submitted', 'processing'].includes(jobStatus),
  };
};

const queueProjection = (phases = Array(10).fill('preflight_ready'), options = {}) => ({
  version: '2026-08-14.v1',
  revision: options.revision || 30,
  row_count: 10,
  rows: phases.map((phase, index) => ({
    source_media_id: sourceId(index),
    runtime: runtimeFor(index, phase, {
      jobStatus: options.jobStatuses?.[index],
      reconciliationRequired: options.reconciliationIndex === index,
    }),
  })),
});

const aggregateReview = (options = {}) => {
  const rows = Array.from({length: 10}, (_, index) => ({
    source_media_id: sourceId(index),
    runtime: runtimeFor(index, 'preflight_ready'),
  }));
  const total = rows.reduce(
    (sum, row) => sum + row.runtime.price.estimated_cost_minor,
    0,
  );
  const ready = options.ready ?? true;
  const serverPriced = options.serverPriced ?? ready;
  return {
    version: '2026-08-14.v1',
    display_only: options.displayOnly ?? true,
    confirmation: options.confirmation ?? false,
    queue_revision: 30,
    prior_review_current: false,
    ready,
    server_priced: serverPriced,
    row_count: 10,
    currency: ready && serverPriced ? 'USD' : null,
    total_estimated_cost_minor: ready && serverPriced ? total : null,
    rows,
  };
};
"""


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy queue view tests")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        sources = {
            "generation-strategy-assets.js": ASSETS_SOURCE,
            "generation-strategy-source-picker.js": SOURCE_PICKER_SOURCE,
            "generation-strategy-runtime.js": RUNTIME_SOURCE,
            "generation-strategy-queue.js": QUEUE_SOURCE,
            "generation-strategy-queue-view.js": VIEW_SOURCE,
        }
        for filename, source in sources.items():
            (directory / filename).write_text(source, encoding="utf-8")
        (directory / "contract.js").write_text(
            JS_FIXTURE
            + f"\nconst result = {expression};\n"
            + "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [node, "contract.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_view_pins_all_frozen_authorities_and_has_no_side_effect_channel() -> None:
    # Отпечатки обновлены 22.08.2026: в runtime переименован ярлык входа
    # «Аватара» (character_and_product_images → video_and_avatar_images), у
    # стратегии больше нет товара. Остальной дрейф — номера версий в адресах
    # импорта. Пин стережёт файл целиком, поэтому реагирует и на них.
    # Прежняя запись 21.08.2026: Причина дрейфа проверена по диффу: в обоих
    # файлах изменились ТОЛЬКО номера версий в адресах импорта (cache-busting),
    # ни одной строки логики. Пин при этом стережёт файл целиком, поэтому любое
    # обновление сборки роняет его — это известная слабость самой проверки, а не
    # признак правки поведения.
    #
    # Запись 23.08.2026 (вторая): пин сдвинут снова, и это ПОЧИНКА СОБСТВЕННОЙ
    # ошибки. Правя каталог провайдеров в edge, я не тронул его браузерного
    # двойника: PRICING_VERSIONS и STRATEGY_PROVIDERS не знали heygen, и
    # привязка дуэта отвергалась в браузере раньше всего остального. Ровно об
    # этом предупреждает комментарий над самими списками: «Расходиться им
    # нельзя: иначе одна из сторон молча отвергает то, что другая считает
    # верным». Три списка версий прайса (edge, этот модуль, app.js) обязаны
    # совпадать.
    #
    # Запись 23.08.2026: пин сдвинут ОСОЗНАННО, и это правка поведения.
    # generation-strategy-runtime.js перестал требовать длительность исходника
    # у одной лишь «Копии»: теперь её требует и «Дуэт», потому что у него
    # ставка посекундная и длина исходника — это цена запуска. Прежде браузер
    # отпускал дуэт без длительности, а сервер отвергал его на
    # generation_strategy_source_duration_mismatch — то есть уже после резерва
    # денег. Пределы вынесены в SOURCE_DURATION_BOUNDS: 1.8–15 с у «Копии»,
    # 1.8–60 с у «Дуэта», по строкам реестра маршрутов.
    # Запись 23.08.2026 (третья): пин очереди сдвинут только штампом сборки
    # `.40`–`.43` в строке импорта — cache-bust после починки зависания вкладки при
    # выборе MP4 (состояние каскада стало пострaтегийным, списки «Дуэта»
    # перестраиваются лишь при смене набора). Поведение очереди не менялось.
    # Запись 26.08.2026: пин пикера сдвинут ОСОЗНАННО, и это правка поведения.
    # «Создание» требует ОДИН референс-хит вместо десяти (владелец: «форма как
    # Копия, только без загрузки видео»); referencing MP4 провайдеру по-прежнему
    # не уходит (buildProductAd отвергает source_video). Кандидаты пикера
    # схлопываются по имени файла: повторные загрузки одного ролика давали
    # «файл ×3» и читались как поломка. Пины очереди/runtime сдвинуты только
    # штампом сборки login-rain.4.
    expected_hashes = {
        RUNTIME_MODULE: "b1a7f6a96ee575dc632d737a1f9436877f473a7c38861c27154fc26040a5393b",
        QUEUE_MODULE: "28f0be42434549de61712e0d47208981ac545cbcbe01a7a9dc3180ad4fb73b8d",
        SOURCE_PICKER_MODULE: "45aee917d6e3a7b83042b5cd38a563fce1a9c51c9a97263fc439d815c12a16a2",
    }
    for path, expected in expected_hashes.items():
        canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(canonical_bytes).hexdigest() == expected
    assert (
        'from "./generation-strategy-source-picker.js?v=20260826.rebuild-clean.29";'
        in VIEW_SOURCE
    )
    assert (
        'from "./generation-strategy-queue.js?v=20260826.rebuild-clean.29";'
        in VIEW_SOURCE
    )
    for forbidden in (
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "fetch(",
        "XMLHttpRequest",
        "Date(",
        "Date.",
        "Math.random",
        "crypto.",
        "setTimeout",
        "setInterval",
        "addEventListener",
        "innerHTML",
        "contentGenerationHandoff",
        "source_media_ids",
        "seedance",
        "veo",
    ):
        assert forbidden not in VIEW_SOURCE

    result = _evaluate(
        """
        ({
          exports: Object.keys(viewContract).sort(),
          version: viewContract.GENERATION_STRATEGY_QUEUE_VIEW_VERSION,
        })
        """
    )
    assert result == {
        "exports": [
            "GENERATION_STRATEGY_QUEUE_VIEW_VERSION",
            "createGenerationStrategyQueueViewModel",
            "renderGenerationStrategyQueueView",
        ],
        "version": "generation-strategy-queue-view-v1",
    }


@pytest.mark.parametrize("count", [0, 3, 9, 10])
def test_view_always_has_ten_rows_and_preserves_selected_order(count: int) -> None:
    result = _evaluate(
        f"""
        (() => {{
          const source = sourceProjection({count});
          const model = viewContract.createGenerationStrategyQueueViewModel(source);
          const markup = viewContract.renderGenerationStrategyQueueView(source);
          return {{
            model,
            markup,
            frozen: Object.isFrozen(model) && Object.isFrozen(model.rows) &&
              model.rows.every((row) => Object.isFrozen(row)),
          }};
        }})()
        """
    )
    model = result["model"]
    assert model["selected_count"] == count
    assert model["selection_count_text"] == f"{count} из 10"
    assert model["required_count"] == 10
    assert result["frozen"] is True
    assert len(model["rows"]) == 10
    assert [row["position"] for row in model["rows"]] == list(range(1, 11))
    assert [row["filename"] for row in model["rows"][:count]] == [
        f"hit-{index}.mp4" for index in range(1, count + 1)
    ]
    assert all(row["selected"] for row in model["rows"][:count])
    assert all(not row["selected"] for row in model["rows"][count:])
    assert f"Выбрано: {count} из 10" in result["markup"]
    assert result["markup"].count('class="generation-strategy-queue-view__row"') == 10


def test_renderer_escapes_xss_and_emits_only_inert_accessible_actions() -> None:
    result = _evaluate(
        r"""
        (() => {
          const payload = '<script>alert("x")</script> & \'quoted\'';
          const source = sourceProjection(10, {firstFilename: payload, probeIndex: 2});
          const model = viewContract.createGenerationStrategyQueueViewModel(source);
          const first = viewContract.renderGenerationStrategyQueueView(source);
          const second = viewContract.renderGenerationStrategyQueueView(source);
          return {payload, model, markup: first, deterministic: first === second};
        })()
        """
    )
    markup = result["markup"]
    assert result["deterministic"] is True
    assert result["model"]["rows"][0]["filename"] == result["payload"]
    assert result["payload"] not in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in markup
    assert "&#39;quoted&#39;" in markup
    assert '<section class="generation-strategy-queue-view" aria-labelledby=' in markup
    assert 'role="status" aria-live="polite"' in markup
    assert 'aria-label="Действия с очередью"' in markup
    assert 'type="button"' in markup
    assert "onclick=" not in markup
    assert "href=" not in markup
    assert "<script" not in markup
    actions = set(re.findall(r'data-action="([^"]+)"', markup))
    assert actions == {
        "toggle-generation-strategy-source",
        "probe-generation-strategy-media",
        "prepare-generation-strategy-queue-free",
        "review-generation-strategy-exact-ten",
        "start-generation-strategy-sequentially",
    }
    button_count = markup.count("<button ")
    assert markup.count("generation-strategy-queue-view__min-44") == button_count
    assert 'data-source-media-id="00002713-0000-4000-8000-0000000003eb"' in markup
    assert "Нужна бесплатная серверная проверка длительности MP4" in markup


def test_total_is_hidden_until_all_ten_have_valid_display_only_server_review() -> None:
    result = _evaluate(
        """
        (() => {
          const source = sourceProjection();
          const queue = queueProjection();
          const missing = viewContract.createGenerationStrategyQueueViewModel(
            source, queue, null,
          );
          const notReadyReview = aggregateReview({ready: false, serverPriced: false});
          const notReady = viewContract.createGenerationStrategyQueueViewModel(
            source, queue, notReadyReview,
          );
          const confirmedReview = aggregateReview({confirmation: true});
          const confirmationTrue = viewContract.createGenerationStrategyQueueViewModel(
            source, queue, confirmedReview,
          );
          const readyReview = aggregateReview();
          const ready = viewContract.createGenerationStrategyQueueViewModel(
            source, queue, readyReview,
          );
          const probePending = viewContract.createGenerationStrategyQueueViewModel(
            sourceProjection(10, {probeIndex: 0}), null, readyReview,
          );
          const markup = viewContract.renderGenerationStrategyQueueView(
            source, queue, readyReview,
          );
          return {missing, notReady, confirmationTrue, ready, probePending, markup};
        })()
        """
    )
    assert result["missing"]["aggregate"] == {
        "visible": False,
        "display_only": True,
        "confirmation": False,
        "total_text": None,
    }
    assert result["notReady"]["aggregate"]["visible"] is False
    assert result["confirmationTrue"]["aggregate"]["visible"] is False
    assert result["probePending"]["aggregate"]["visible"] is False
    assert result["ready"]["aggregate"] == {
        "visible": True,
        "display_only": True,
        "confirmation": False,
        "total_text": "19,65 USD",
    }
    assert "Итоговая серверная стоимость: <strong>19,65 USD</strong>." in result["markup"]
    assert "не является подтверждением платного запуска" in result["markup"]


def test_review_total_is_hidden_for_wrong_order_or_cost_drift() -> None:
    result = _evaluate(
        """
        (() => {
          const source = sourceProjection();
          const queue = queueProjection();
          const wrongOrder = aggregateReview();
          wrongOrder.rows.reverse();
          const wrongCost = aggregateReview();
          wrongCost.rows[4].runtime.price.estimated_cost_minor += 1;
          wrongCost.rows[4].runtime.price.estimated_cost_usd = '1.97';
          return {
            wrongOrder: viewContract.createGenerationStrategyQueueViewModel(
              source, queue, wrongOrder,
            ).aggregate,
            wrongCost: viewContract.createGenerationStrategyQueueViewModel(
              source, queue, wrongCost,
            ).aggregate,
          };
        })()
        """
    )
    assert result["wrongOrder"]["visible"] is False
    assert result["wrongOrder"]["total_text"] is None
    assert result["wrongCost"]["visible"] is False
    assert result["wrongCost"]["total_text"] is None


def test_view_model_and_markup_redact_all_non_display_authority() -> None:
    result = _evaluate(
        """
        (() => {
          const source = sourceProjection();
          const queue = queueProjection();
          queue.rows[0].runtime.price.spend_confirmation = 'PAY_THIS_SECRET_TOKEN';
          queue.rows[0].runtime.identity.raw_selection = {
            attestations: {rights: true},
            model: 'forbidden-model',
            provider: 'forbidden-provider',
            url: 'https://private.example/object',
            path: '/private/object/path',
          };
          queue.rows[0].runtime.readiness.request_keys = {
            start: 'strategy.start:secret-key',
          };
          const review = aggregateReview();
          review.rows[0].runtime.price.spend_confirmation = 'PAY_REVIEW_SECRET';
          const model = viewContract.createGenerationStrategyQueueViewModel(
            source, queue, review,
          );
          const markup = viewContract.renderGenerationStrategyQueueView(
            source, queue, review,
          );
          return {serialized: JSON.stringify(model), markup};
        })()
        """
    )
    combined = result["serialized"] + result["markup"]
    for forbidden in (
        "spend_confirmation",
        "PAY_THIS_SECRET_TOKEN",
        "PAY_REVIEW_SECRET",
        "request_keys",
        "strategy.start:secret-key",
        "raw_selection",
        "attestations",
        "forbidden-model",
        "forbidden-provider",
        "private.example",
        "/private/object/path",
        "price_hash",
        "receipt_hash",
        "binding_hash",
        "strategy_prompt_hash",
        "000000000000000000000000000000000000000000000000000000000000",
    ):
        assert forbidden not in combined


def test_rows_render_russian_phase_price_job_and_isolated_error_statuses() -> None:
    result = _evaluate(
        """
        (() => {
          const phases = [
            'selected', 'bound', 'preflight_ready', 'human_confirmed',
            'start_once', 'status', 'status', 'status', 'invalid', 'idle',
          ];
          const jobs = [null, null, null, null, null,
            'submitted', 'processing', 'failed', null, null];
          const source = sourceProjection();
          const queue = queueProjection(phases, {jobStatuses: jobs});
          const model = viewContract.createGenerationStrategyQueueViewModel(
            source, queue, aggregateReview(),
          );
          const markup = viewContract.renderGenerationStrategyQueueView(
            source, queue, aggregateReview(),
          );
          return {model, markup};
        })()
        """
    )
    rows = result["model"]["rows"]
    assert rows[0]["phase_text"] == "Выбор зафиксирован"
    assert rows[0]["free_readiness_text"] == "Можно бесплатно привязать ассеты"
    assert rows[1]["phase_text"] == "Ассеты проверены сервером"
    assert rows[1]["free_readiness_text"] == "Можно выполнить бесплатную проверку"
    assert rows[2]["phase_text"] == "Бесплатная проверка готова"
    assert rows[2]["price_text"] == "1,94 USD"
    assert rows[5]["job_status_text"] == "Передано в генерацию"
    assert rows[6]["job_status_text"] == "Генерируется"
    assert rows[7]["job_status_text"] == "Завершилось с ошибкой"
    assert "остальные ролики продолжают работу" in rows[7]["error_text"]
    assert rows[8]["phase_text"] == "Нужно подготовить заново"
    assert "только для этой строки" in rows[8]["error_text"]
    assert "Точная цена: 1,94 USD" in result["markup"]
    assert "Статус задачи: Генерируется" in result["markup"]
    assert 'role="alert"' in result["markup"]


def test_sequential_start_button_uses_only_safe_row_state_and_review() -> None:
    result = _evaluate(
        """
        (() => {
          const source = sourceProjection();
          const review = aggregateReview();
          const safePhases = [
            'status', 'human_confirmed', 'human_confirmed', 'human_confirmed',
            'human_confirmed', 'human_confirmed', 'human_confirmed',
            'human_confirmed', 'human_confirmed', 'human_confirmed',
          ];
          const safe = queueProjection(safePhases, {
            jobStatuses: ['processing'],
          });
          const startOnce = clone(safe);
          startOnce.rows[2].runtime = runtimeFor(2, 'start_once');
          const reconciliation = queueProjection(safePhases, {
            jobStatuses: ['starting'], reconciliationIndex: 0,
          });
          const noReview = viewContract.createGenerationStrategyQueueViewModel(
            source, safe, null,
          );
          return {
            safe: viewContract.createGenerationStrategyQueueViewModel(
              source, safe, review,
            ),
            startOnce: viewContract.createGenerationStrategyQueueViewModel(
              source, startOnce, review,
            ),
            reconciliation: viewContract.createGenerationStrategyQueueViewModel(
              source, reconciliation, review,
            ),
            noReview,
          };
        })()
        """
    )
    assert result["safe"]["controls"]["can_start_sequentially"] is True
    assert result["startOnce"]["controls"]["can_start_sequentially"] is False
    assert result["reconciliation"]["controls"]["can_start_sequentially"] is False
    assert result["noReview"]["controls"]["can_start_sequentially"] is False


def test_russian_scope_copy_preserves_advisor_and_untouched_product_areas() -> None:
    result = _evaluate(
        """
        (() => {
          const source = sourceProjection();
          const model = viewContract.createGenerationStrategyQueueViewModel(source);
          const markup = viewContract.renderGenerationStrategyQueueView(source);
          return {copy: model.scope_copy, markup};
        })()
        """
    )
    copy = result["copy"]
    assert "Каждый из 10 роликов" in copy["sequential"]
    assert "отдельным платным запросом" in copy["sequential"]
    assert "последовательно" in copy["sequential"]
    assert "Ошибка одного ролика" in copy["isolation"]
    assert "остальных" in copy["isolation"]
    assert "нескольким нейросетям" in copy["advisory"]
    assert "только рекомендацией" in copy["advisory"]
    assert "ничего не применяет автоматически" in copy["advisory"]
    assert "«Задумки»" in copy["untouched"]
    assert "«ИИ-центр»" in copy["untouched"]
    for text in copy.values():
        assert text in result["markup"]


def test_probe_and_top_controls_are_disabled_strictly_from_safe_state() -> None:
    result = _evaluate(
        """
        (() => {
          const incomplete = sourceProjection(9);
          const probe = sourceProjection(10, {probeIndex: 4});
          const ready = sourceProjection();
          const preflightQueue = queueProjection();
          return {
            incomplete: viewContract.createGenerationStrategyQueueViewModel(incomplete),
            probe: viewContract.createGenerationStrategyQueueViewModel(probe),
            ready: viewContract.createGenerationStrategyQueueViewModel(ready),
            reviewable: viewContract.createGenerationStrategyQueueViewModel(
              ready, preflightQueue,
            ),
          };
        })()
        """
    )
    assert result["incomplete"]["controls"] == {
        "can_prepare_free": False,
        "can_review_exact_ten": False,
        "can_start_sequentially": False,
    }
    assert result["probe"]["controls"]["can_prepare_free"] is False
    assert result["probe"]["rows"][4]["can_probe"] is True
    assert sum(row["can_probe"] for row in result["probe"]["rows"]) == 1
    assert result["ready"]["controls"]["can_prepare_free"] is True
    assert result["reviewable"]["controls"]["can_prepare_free"] is False
    assert result["reviewable"]["controls"]["can_review_exact_ten"] is True
    assert result["reviewable"]["controls"]["can_start_sequentially"] is False


def test_stale_queue_is_not_mixed_with_new_selection_and_invalid_source_fails_closed() -> None:
    result = _evaluate(
        """
        (() => {
          const source = sourceProjection();
          const queue = queueProjection();
          queue.rows.reverse();
          const stale = viewContract.createGenerationStrategyQueueViewModel(
            source, queue, aggregateReview(),
          );
          const invalidSource = sourceProjection();
          invalidSource.selected[0].source_media_id = 'not-a-uuid';
          return {
            stale,
            invalidModel: viewContract.createGenerationStrategyQueueViewModel(
              invalidSource,
            ),
            invalidMarkup: viewContract.renderGenerationStrategyQueueView(
              invalidSource,
            ),
          };
        })()
        """
    )
    assert result["stale"]["queue_matches_selection"] is False
    assert result["stale"]["aggregate"]["visible"] is False
    assert result["stale"]["controls"]["can_start_sequentially"] is False
    assert "Состав выбранных роликов изменился" in result["stale"]["notice"]
    assert all(
        row["phase"] == "queue_stale" for row in result["stale"]["rows"]
    )
    assert result["invalidModel"] is None
    assert result["invalidMarkup"] == ""

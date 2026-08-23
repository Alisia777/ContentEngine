"""Маршрут платного запуска стратегии: провайдер и цена берутся у задачи.

Оба проверяемых здесь дефекта оставляли ПОВИСШИЙ РЕЗЕРВ — деньги, списанные
резервом и не снятые ни успехом, ни отказом:

* опрос выбирал провайдера выражением `provider === "fal" ? "fal" : "runway"`,
  а оба вызывающих поле не передавали вовсе, поэтому задача fal опрашивалась
  рунвеевским ключом по рунвеевскому адресу и не завершалась никогда;
* публичный статус пересчитывал цену по СТАТИЧЕСКОМУ рунвеевскому каталогу,
  поэтому удачный запуск на fal (47 центов, версия прайса fal) выглядел как
  generation_unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "supabase/functions/_shared/generation-strategy-edge-contract.js"
CATALOG = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
ADAPTERS = ROOT / "supabase/functions/_shared/generation-recipe-adapters.js"
EDGE = ROOT / "supabase/functions/creator-generate/index.ts"


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy Edge contract tests")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        for source in (CONTRACT, CATALOG):
            (directory / source.name).write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
        (directory / "run.js").write_text(
            f"import * as subject from './{CONTRACT.name}';\n"
            f"const result = await ({expression});\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "run.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


_STATUS_FIXTURE = """
        (() => {
          const clone = (value) => JSON.parse(JSON.stringify(value));
          const ids = {
            project:'11111111-1111-4111-8111-111111111111',
            campaign:'22222222-2222-4222-8222-222222222222',
            job:'33333333-3333-4333-8333-333333333333',
            batch:'44444444-4444-4444-8444-444444444444',
            binding:'55555555-5555-4555-8555-555555555555',
            receipt:'66666666-6666-4666-8666-666666666666',
            source:'77777777-7777-4777-8777-777777777777',
            original:'88888888-8888-4888-8888-888888888888',
            product:'99999999-9999-4999-8999-999999999999',
            dispatch:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          };
          const h = (value) => value.repeat(64);
          // Платный запуск «Копии» на fal: Pika берёт фиксированные 47 центов
          // за ролик независимо от длительности, версия прайса своя.
          const fal = {
            ok:true, version:'generation-strategy-status-response-v1',
            job:{id:ids.job,batch_id:ids.batch,project_id:ids.project,
              campaign_id:ids.campaign,status:'submitted',
              provider_status:'processing',
              provider_task_id:'fal-request-0001',estimated_cost_minor:47,
              actual_cost_minor:null,currency:'USD',
              created_at:'2026-08-19T08:00:00.000Z',
              updated_at:'2026-08-19T08:00:01.000Z'},
            strategy:{version:'generation-strategy-immutable-execution-v1',
              strategy_id:'viral_product_swap',recipe:'product_swap',
              catalog_version:'2026-08-14.v1',recipe_version:'2026-06',
              pricing_version:'fal-usd-per-run-2026-08-18.v1',
              binding_id:ids.binding,binding_hash:h('a'),
              receipt_id:ids.receipt,receipt_hash:h('b'),
              selection_hash:h('c'),price_hash:h('d'),
              strategy_prompt_hash:h('e')},
            selection:{version:'2026-08-14.v1',
              strategy_id:'viral_product_swap',recipe_version:'2026-06',
              duration_seconds:10,resolution:'720p',audio:false,
              assets:[
                {role:'source_video',media_id:ids.source,duration_seconds:10},
                {role:'original_product_image',media_id:ids.original},
                {role:'new_product_image',media_id:ids.product},
              ],
              attestations:{source_media_rights_confirmed:true,
                transformative_use_confirmed:true,
                product_assets_rights_confirmed:true,
                depicted_people_consent_confirmed:true}},
            price:{version:'generation-strategy-price-snapshot-v1',
              strategy_id:'viral_product_swap',provider:'fal',
              recipe:'product_swap',input_mode:'video_and_product_images',
              duration_seconds:10,resolution:'720p',ratio:'source',
              audio:false,estimated_credits:47,
              estimated_pre_tax_usd_minor:47,estimated_cost_minor:47,
              estimated_cost_usd:'0.47',currency:'USD',
              credit_unit_cost_minor:1,catalog_version:'2026-08-14.v1',
              pricing_version:'fal-usd-per-run-2026-08-18.v1',
              recipe_version:'2026-06',price_hash:h('d')},
            dispatch:{result_id:ids.dispatch,result_hash:h('f'),
              outcome:'submitted',provider_post_started:true,
              provider_http_status:200,
              recorded_at:'2026-08-19T08:00:02.000Z'},
            reconciliation:null,output:null,error:null,
            contract:{recipe_aware:true,legacy_model_catalog_used:false,
              poll_provider_allowed:true,second_post_allowed:false,
              object_names_returned:false,media_hashes_returned:false,
              signed_urls_returned:false,manual_human_review_required:false},
          };
          // Тот же наряд на Runway: 212 базовых кредитов за первые четыре
          // секунды плюс 36 за каждую следующую, итого 428 за десять секунд.
          const runway = clone(fal);
          runway.job.estimated_cost_minor = 428;
          runway.job.provider_task_id = 'runway-task-0001';
          runway.strategy.pricing_version =
            'runway-recipe-credits-2026-08-14.v1';
          runway.price.provider = 'runway';
          runway.price.pricing_version =
            'runway-recipe-credits-2026-08-14.v1';
          runway.price.estimated_credits = 428;
          runway.price.estimated_pre_tax_usd_minor = 428;
          runway.price.estimated_cost_minor = 428;
          runway.price.estimated_cost_usd = '4.28';
          const read = (value) => subject.readPublicGenerationStrategyStatus(
            value, {projectId:ids.project,generationJobId:ids.job}
          ) !== null;
          return {ids, fal, runway, read};
        })()
"""


def _status_case(body: str) -> object:
    return _evaluate(
        "(() => {\n"
        f"  const fixture = {_STATUS_FIXTURE.strip()};\n"
        "  const {fal, runway, read} = fixture;\n"
        "  const clone = (value) => JSON.parse(JSON.stringify(value));\n"
        f"{body}\n"
        "})()"
    )


_PRODUCTION_E622_STATUS_FIXTURE = f"""
        (() => {{
          const base = {_STATUS_FIXTURE.strip()};
          const clone = (value) => JSON.parse(JSON.stringify(value));
          const status = clone(base.fal);
          const ids = {{
            project:'4f0fcfa2-7233-4c0c-9e16-2c20e0aae379',
            campaign:'fe0fd278-f885-4ce4-8a11-954d07f35580',
            job:'e62235c7-57c5-473f-88bf-c33bb319ee04',
            batch:'de0e24fe-746d-4f5c-8f50-e2b47529b174',
            binding:'4ede60aa-f4f0-4701-8ce3-35522bbefefc',
            receipt:'d8c73511-affc-4a6f-969a-12441228feaa',
            dispatch:'51e38d6e-8b12-4557-935e-395476d08b15',
            incident:'8a0bee41-7f53-4fb3-b986-bb59bdc6a261',
          }};

          // Точная публичная форма зависшего production-запуска e622:
          // POST к fal начался, но ни HTTP-ответа, ни request id не осталось.
          status.job.id = ids.job;
          status.job.batch_id = ids.batch;
          status.job.project_id = ids.project;
          status.job.campaign_id = ids.campaign;
          status.job.status = 'starting';
          status.job.provider_status = null;
          status.job.provider_task_id = null;
          status.job.estimated_cost_minor = 85;
          status.job.actual_cost_minor = 0;
          status.job.created_at = '2026-08-19T22:10:51.503119Z';
          status.job.updated_at = '2026-08-19T22:16:02.296268Z';

          status.strategy.pricing_version =
            'fal-usd-per-second-2026-08-18.v1';
          status.strategy.binding_id = ids.binding;
          status.strategy.receipt_id = ids.receipt;

          status.selection.duration_seconds = 5;
          status.selection.assets[0].duration_seconds = 5;

          status.price.provider = 'fal';
          status.price.duration_seconds = 5;
          status.price.estimated_credits = 85;
          status.price.estimated_pre_tax_usd_minor = 85;
          status.price.estimated_cost_minor = 85;
          status.price.estimated_cost_usd = '0.85';
          status.price.pricing_version =
            'fal-usd-per-second-2026-08-18.v1';

          status.dispatch.result_id = ids.dispatch;
          status.dispatch.outcome = 'ambiguous';
          status.dispatch.provider_post_started = true;
          status.dispatch.provider_http_status = null;
          status.dispatch.recorded_at = '2026-08-19T22:16:02.304924Z';

          status.reconciliation = {{
            required:true,
            incident_id:ids.incident,
            reason_code:'provider_create_response_unknown',
            required_at:'2026-08-19T22:16:02.307992Z',
          }};
          status.contract.poll_provider_allowed = false;
          status.contract.manual_human_review_required = false;

          const read = (value) => subject.readPublicGenerationStrategyStatus(
            value, {{projectId:ids.project,generationJobId:ids.job}}
          ) !== null;
          return {{status, read}};
        }})()
"""


def _production_e622_status_case(body: str) -> object:
    return _evaluate(
        "(() => {\n"
        f"  const fixture = {_PRODUCTION_E622_STATUS_FIXTURE.strip()};\n"
        "  const {status, read} = fixture;\n"
        "  const clone = (value) => JSON.parse(JSON.stringify(value));\n"
        f"{body}\n"
        "})()"
    )


_PRODUCTION_E2_KLING_SUBMITTED_FIXTURE = f"""
        (() => {{
          const base = {_STATUS_FIXTURE.strip()};
          const clone = (value) => JSON.parse(JSON.stringify(value));
          const status = clone(base.fal);

          // Production-shaped immediate projection for the paid Kling job.
          // The dispatch transaction wrote job.status and the first provider
          // event as `submitted` before the first GET-only provider poll.
          status.job.id = 'e2f56232-61b0-4dbd-84b7-3c43b15c447a';
          status.job.project_id = '4f0fcfa2-7233-4c0c-9e16-2c20e0aae379';
          status.job.campaign_id = '57fb020c-02ca-4805-b991-3acd0a722c56';
          status.job.status = 'submitted';
          status.job.provider_status = 'submitted';
          status.job.provider_task_id =
            '01a02064-7faa-70a3-b8ca-ab13c0de3f99';
          status.job.estimated_cost_minor = 85;
          status.job.actual_cost_minor = 85;
          status.job.updated_at = '2026-08-20T18:17:32.509Z';

          status.strategy.pricing_version =
            'fal-usd-per-second-2026-08-18.v1';
          status.selection.duration_seconds = 5;
          status.selection.assets[0].duration_seconds = 5;
          status.selection.resolution = '720p';
          status.selection.audio = false;

          status.price.provider = 'fal';
          status.price.duration_seconds = 5;
          status.price.resolution = '720p';
          status.price.audio = false;
          status.price.estimated_credits = 85;
          status.price.estimated_pre_tax_usd_minor = 85;
          status.price.estimated_cost_minor = 85;
          status.price.estimated_cost_usd = '0.85';
          status.price.pricing_version =
            'fal-usd-per-second-2026-08-18.v1';

          status.dispatch.outcome = 'submitted';
          status.dispatch.provider_post_started = true;
          status.dispatch.provider_http_status = 200;
          status.dispatch.recorded_at = '2026-08-20T18:17:32.509Z';
          status.reconciliation = null;
          status.output = null;
          status.error = null;
          status.contract.poll_provider_allowed = true;
          status.contract.manual_human_review_required = false;

          const expected = {{
            projectId: status.job.project_id,
            generationJobId: status.job.id,
          }};
          const read = (value) =>
            subject.readPublicGenerationStrategyStatus(value, expected);
          return {{status, read, clone}};
        }})()
"""


def _production_e2_kling_status_case(body: str) -> object:
    return _evaluate(
        "(() => {\n"
        f"  const fixture = {_PRODUCTION_E2_KLING_SUBMITTED_FIXTURE.strip()};\n"
        "  const {status, read, clone} = fixture;\n"
        f"{body}\n"
        "})()"
    )


def test_paid_fal_run_reads_as_a_run_and_not_as_a_refusal() -> None:
    """Снимок маршрута fal обязан читаться. Иначе резерв не снимет никто."""
    result = _status_case("  return {fal: read(fal), runway: read(runway)};")
    assert result == {"fal": True, "runway": True}


def test_production_e2_kling_first_submitted_event_is_a_durable_status() -> None:
    """HTTP 200 dispatch must project before the first provider status poll."""
    result = _production_e2_kling_status_case(
        """
        const parsed = read(status);
        return parsed === null ? null : {
          job_id: parsed.job.id,
          status: parsed.job.status,
          provider_status: parsed.job.provider_status,
          provider_task_id: parsed.job.provider_task_id,
          estimated_cost_minor: parsed.job.estimated_cost_minor,
          actual_cost_minor: parsed.job.actual_cost_minor,
          pricing_version: parsed.price.pricing_version,
          duration_seconds: parsed.price.duration_seconds,
          provider_http_status: parsed.dispatch.provider_http_status,
          second_post_allowed: parsed.contract.second_post_allowed,
          poll_provider_allowed: parsed.contract.poll_provider_allowed,
        };
        """
    )
    assert result == {
        "job_id": "e2f56232-61b0-4dbd-84b7-3c43b15c447a",
        "status": "submitted",
        "provider_status": "submitted",
        "provider_task_id": "01a02064-7faa-70a3-b8ca-ab13c0de3f99",
        "estimated_cost_minor": 85,
        "actual_cost_minor": 85,
        "pricing_version": "fal-usd-per-second-2026-08-18.v1",
        "duration_seconds": 5,
        "provider_http_status": 200,
        "second_post_allowed": False,
        "poll_provider_allowed": True,
    }


def test_submitted_provider_event_cannot_be_detached_from_its_dispatch_phase() -> None:
    """The new marker is narrow: stale/manufactured phase combinations fail."""
    result = _production_e2_kling_status_case(
        """
        const wrongJobPhase = clone(status);
        wrongJobPhase.job.status = 'processing';

        const noDispatch = clone(status);
        noDispatch.dispatch = null;

        const ambiguousDispatch = clone(status);
        ambiguousDispatch.dispatch.outcome = 'ambiguous';
        ambiguousDispatch.dispatch.provider_http_status = null;

        const pika = clone(status);
        pika.job.estimated_cost_minor = 47;
        pika.job.actual_cost_minor = 47;
        pika.strategy.pricing_version = 'fal-usd-per-run-2026-08-18.v1';
        pika.price.estimated_credits = 47;
        pika.price.estimated_pre_tax_usd_minor = 47;
        pika.price.estimated_cost_minor = 47;
        pika.price.estimated_cost_usd = '0.47';
        pika.price.pricing_version = 'fal-usd-per-run-2026-08-18.v1';

        return {
          exact: read(status) !== null,
          wrongJobPhase: read(wrongJobPhase) !== null,
          noDispatch: read(noDispatch) !== null,
          ambiguousDispatch: read(ambiguousDispatch) !== null,
          pika: read(pika) !== null,
        };
        """
    )
    assert result == {
        "exact": True,
        "wrongJobPhase": False,
        "noDispatch": False,
        "ambiguousDispatch": False,
        "pika": True,
    }


def test_production_e622_ambiguous_fal_status_is_readable() -> None:
    """e622 должен открыть fal-сверку, а не откатиться к форме Runway."""
    assert _production_e622_status_case("  return read(status);") is True


def test_production_e622_rejects_provider_pricing_and_cost_drift() -> None:
    """Маршрут и 85 центов e622 нельзя подменить отдельным полем ответа."""
    result = _production_e622_status_case(
        """
        const provider = clone(status);
        provider.price.provider = 'runway';

        const pricing = clone(status);
        pricing.price.pricing_version = 'fal-usd-per-run-2026-08-18.v1';

        const quotedCost = clone(status);
        quotedCost.price.estimated_cost_minor = 84;

        const jobCost = clone(status);
        jobCost.job.estimated_cost_minor = 84;

        const actualCost = clone(status);
        actualCost.job.actual_cost_minor = 1;

        return {
          provider: read(provider),
          pricing: read(pricing),
          quotedCost: read(quotedCost),
          jobCost: read(jobCost),
          actualCost: read(actualCost),
        };
        """
    )
    assert result == {
        "provider": False,
        "pricing": False,
        "quotedCost": False,
        "jobCost": False,
        "actualCost": False,
    }


def test_runway_credit_tiers_are_still_checked_against_the_calculator() -> None:
    """Строгость Runway не ослаблена: чужое число кредитов отвергается."""
    result = _status_case(
        """
        const cheaper = clone(runway);
        cheaper.job.estimated_cost_minor = 47;
        cheaper.price.estimated_credits = 47;
        cheaper.price.estimated_pre_tax_usd_minor = 47;
        cheaper.price.estimated_cost_minor = 47;
        cheaper.price.estimated_cost_usd = '0.47';
        const dearer = clone(runway);
        dearer.job.estimated_cost_minor = 429;
        dearer.price.estimated_credits = 429;
        dearer.price.estimated_pre_tax_usd_minor = 429;
        dearer.price.estimated_cost_minor = 429;
        dearer.price.estimated_cost_usd = '4.29';
        return {cheaper: read(cheaper), dearer: read(dearer)};
        """
    )
    assert result == {"cheaper": False, "dearer": False}


def test_price_snapshot_must_name_the_pricing_version_of_its_own_route() -> None:
    """Движок и версия прайса подписаны вместе — расходиться они не могут."""
    result = _status_case(
        """
        // Снимок цены называет версию прайса, которой нет в снимке стратегии.
        const drifted = clone(fal);
        drifted.price.pricing_version = 'fal-usd-per-second-2026-08-18.v1';
        // Маршрут fal, оценённый рунвеевскими ступенями.
        const falWithRunwayPricing = clone(fal);
        falWithRunwayPricing.strategy.pricing_version =
          'runway-recipe-credits-2026-08-14.v1';
        falWithRunwayPricing.price.pricing_version =
          'runway-recipe-credits-2026-08-14.v1';
        // Runway, оценённый прайсом за ролик: 47 центов вместо 428.
        const runwayWithFalPricing = clone(runway);
        runwayWithFalPricing.strategy.pricing_version =
          'fal-usd-per-run-2026-08-18.v1';
        runwayWithFalPricing.price.pricing_version =
          'fal-usd-per-run-2026-08-18.v1';
        return {
          drifted: read(drifted),
          falWithRunwayPricing: read(falWithRunwayPricing),
          runwayWithFalPricing: read(runwayWithFalPricing),
        };
        """
    )
    assert result == {
        "drifted": False,
        "falWithRunwayPricing": False,
        "runwayWithFalPricing": False,
    }


def test_poll_provider_has_no_default_and_every_call_carries_the_route() -> None:
    """Опрос не выбирает Runway молча: маршрут приходит в каждый вызов."""
    edge = EDGE.read_text(encoding="utf-8")

    assert 'identity.provider === "fal" ? "fal" : "runway"' not in edge
    assert "const provider = identity.route.provider;" in edge

    poll = edge.split("const pollGenerationStrategyProvider = async (", 1)[1]
    signature = poll.split("): Promise<string | null> => {", 1)[0]
    assert "route: { provider: string; modelKey: string | null };" in signature
    assert "provider?: string;" not in signature

    # Воркер, обычный browser poll и узкое GET-only recovery обязаны передать
    # маршрут и явно назвать режим записи: значения по умолчанию здесь нет.
    calls = edge.count("await pollGenerationStrategyProvider({")
    assert calls == 3
    assert edge.count("providerTaskId: worker.provider_task_id as string,\n          route,\n") == 1
    assert edge.count("providerTaskId: job.provider_task_id as string,\n        route,\n") == 1
    assert edge.count('recordMode: "record_status"') == 2
    assert "recordMode: recovery.failureCode ===" in edge
    assert '? "recover_fal_result_http_413"' in edge
    assert ': "recover_fal_result_http_405"' in edge

    # Нет маршрута — честный код, а не прежний статус и не молчаливый Runway.
    assert edge.count('code: "generation_route_unresolved"') == 3


def test_fal_poll_resolves_the_exact_model_of_this_job() -> None:
    """Маршрутов fal несколько; «первый включённый» собирал чужой адрес."""
    edge = EDGE.read_text(encoding="utf-8")

    resolver = edge.split(
        "const loadGenerationStrategyJobRoute = async (", 1
    )[1].split("const pollGenerationStrategyProvider = async (", 1)[0]

    # Провайдер — из подписанной квитанции этой задачи.
    assert '"generation_strategy_start_claims"' in resolver
    assert '"generation_strategy_readiness_receipts"' in resolver
    assert "receipt.receipt_hash !== receiptHash" in resolver
    assert "isKnownStrategyProvider(receipt.provider)" in resolver

    # Модель — по паре (провайдер, версия прайса), без «первого включённого».
    assert '.eq("strategy_id", strategyId)' in resolver
    assert '.eq("provider", provider)' in resolver
    assert '.eq("pricing_version", pricingVersion)' in resolver
    assert "routes.data.length !== 1" in resolver
    assert ".limit(1)" not in resolver

    # Отметка enabled в условие не входит: она про «продаём ли сейчас», а
    # опрашивают уже оплаченную задачу. Выключение маршрута обязано остановить
    # новые запуски, а не оборвать опрос старых — иначе резерв повиснет.
    assert '.eq("enabled", true)' not in resolver

    # Модель называет реестр — он же назвал цену, по которой запуск оплачен.
    # Код проверяет не совпадение с единственным зашитым именем, а способность
    # эту модель исполнить: моделей fal уже две.
    assert "route.provider_path !== route.model_key" in resolver
    assert "falModelExecutable(receipt.recipe, route.model_key)" in resolver
    assert "modelKey: route.model_key" in resolver

    # Формы запроса живут в общем каталоге рядом с адаптером, который эти
    # запросы собирает: отправка и опрос обязаны опираться на одно знание.
    catalog = CATALOG.read_text(encoding="utf-8")
    adapters = ADAPTERS.read_text(encoding="utf-8")
    assert "export const FAL_STRATEGY_MODEL_SHAPES = Object.freeze({" in catalog
    assert catalog.count('"fal-ai/pika/v2/pikaswaps"') == 1
    assert (
        catalog.count('"fal-ai/kling-video/o3/pro/video-to-video/edit"') == 1
    )
    assert '"fal-ai/pika/v2/pikaswaps"' not in adapters
    assert '"fal-ai/kling-video/o3/pro/video-to-video/edit"' not in adapters
    assert "falStrategyRequestShape(selection.recipe, modelKey)" in adapters
    assert "falStrategyRequestShape," in edge


def test_fal_completed_result_uses_exact_response_then_bare_fallbacks() -> None:
    """405/413 route mismatches never fail an already-completed paid task."""
    request_id = "018f8e00-7b4a-7abc-8def-0123456789ab"
    result = _evaluate(
        f"""
        (async () => {{
          const requestId = "{request_id}";
          const pikaModel = "fal-ai/pika/v2/pikaswaps";
          const klingModel =
            "fal-ai/kling-video/o3/pro/video-to-video/edit";
          const pikaCandidates = subject.falQueueUrlCandidates(
            pikaModel, requestId
          );
          const klingCandidates = subject.falQueueUrlCandidates(
            klingModel, requestId
          );

          const pikaCalls = [];
          const pikaResult = await subject.fetchFalQueueResult({{
            statusValue: {{
              status: "COMPLETED",
              // fal owns this URL. It must be validated and tried exactly
              // before any locally synthesized bare fallback.
              response_url:
                `https://queue.fal.run/fal-ai/pika/requests/${{requestId}}/response`,
            }},
            requestId,
            resultUrls: pikaCandidates.map((candidate) => candidate.resultUrl),
            fetchJson: async (url, init) => {{
              pikaCalls.push({{ url, method: init.method }});
              if (url.endsWith(`/requests/${{requestId}}/response`)) {{
                return {{
                  ok: true,
                  status: 200,
                  value: {{ video: {{ url: "https://v3.fal.media/pika.mp4" }} }},
                }};
              }}
              return {{ ok: false, status: 404, value: null }};
            }},
          }});

          const klingCalls = [];
          const klingResult = await subject.fetchFalQueueResult({{
            statusValue: {{
              status: "COMPLETED",
              response_url:
                `https://queue.fal.run/${{klingModel}}/requests/${{requestId}}/response`,
            }},
            requestId,
            resultUrls: klingCandidates.map((candidate) => candidate.resultUrl),
            fetchJson: async (url, init) => {{
              klingCalls.push({{ url, method: init.method }});
              return {{
                ok: true,
                status: 200,
                value: {{ video: {{ url: "https://v3.fal.media/kling.mp4" }} }},
              }};
            }},
          }});

          const mismatchCalls = [];
          const mismatch = await subject.fetchFalQueueResult({{
            statusValue: {{
              status: "COMPLETED",
              response_url:
                "https://queue.fal.run/fal-ai/pika/requests/wrong-id/response",
            }},
            requestId,
            resultUrls: pikaCandidates.map((candidate) => candidate.resultUrl),
            fetchJson: async (url, init) => {{
              mismatchCalls.push({{ url, method: init.method }});
              return {{
                ok: false,
                status: mismatchCalls.length === 1 ? 405 : 404,
                value: null,
              }};
            }},
          }});

          const refused = await subject.fetchFalQueueResult({{
            statusValue: {{}},
            requestId,
            resultUrls: pikaCandidates.map((candidate) => candidate.resultUrl),
            fetchJson: async () => ({{ ok: false, status: 401, value: null }}),
          }});

          const fallbackCalls = [];
          const fallback = await subject.fetchFalQueueResult({{
            statusValue: {{
              status: "COMPLETED",
              response_url:
                `https://queue.fal.run/fal-ai/pika/requests/${{requestId}}/response`,
            }},
            requestId,
            resultUrls: pikaCandidates.map((candidate) => candidate.resultUrl),
            fetchJson: async (url, init) => {{
              fallbackCalls.push({{ url, method: init.method }});
              if (url.includes("/fal-ai/pika/v2/pikaswaps/")) {{
                return {{
                  ok: true,
                  status: 200,
                  value: {{ video: {{ url: "https://v3.fal.media/fallback.mp4" }} }},
                }};
              }}
              return {{ ok: false, status: 413, value: null }};
            }},
          }});

          const exhaustedCalls = [];
          const exhausted = await subject.fetchFalQueueResult({{
            statusValue: {{
              status: "COMPLETED",
              response_url:
                `https://queue.fal.run/fal-ai/pika/requests/${{requestId}}/response`,
            }},
            requestId,
            resultUrls: pikaCandidates.map((candidate) => candidate.resultUrl),
            fetchJson: async (url, init) => {{
              exhaustedCalls.push({{ url, method: init.method }});
              return {{
                ok: false,
                status: exhaustedCalls.length === 1 ? 413
                  : exhaustedCalls.length === 2 ? 405 : 404,
                value: null,
              }};
            }},
          }});

          const retrievalFailures = {{}};
          let redirectAttempts = [];
          for (const status of [401, 403, 429, 500, 302]) {{
            const failure = await subject.fetchFalQueueResult({{
              statusValue: {{
                status: "COMPLETED",
                response_url:
                  `https://queue.fal.run/fal-ai/pika/requests/${{requestId}}/response`,
              }},
              requestId,
              resultUrls: pikaCandidates.map((candidate) => candidate.resultUrl),
              fetchJson: async () => ({{ ok: false, status, value: null }}),
            }});
            retrievalFailures[String(status)] = {{
              hasResponse: failure.response !== null,
              refusedStatus: failure.refusedStatus,
            }};
            if (status === 302) redirectAttempts = failure.attempts;
          }}
          const thrown = await subject.fetchFalQueueResult({{
            statusValue: {{
              status: "COMPLETED",
              response_url:
                `https://queue.fal.run/fal-ai/pika/requests/${{requestId}}/response`,
            }},
            requestId,
            resultUrls: pikaCandidates.map((candidate) => candidate.resultUrl),
            fetchJson: async () => {{ throw new Error("network"); }},
          }});
          retrievalFailures.throw = {{
            hasResponse: thrown.response !== null,
            refusedStatus: thrown.refusedStatus,
          }};

          return {{
            pikaCandidates,
            klingCandidates,
            pikaCalls,
            pikaVideo: pikaResult.response?.value?.video?.url || null,
            klingCalls,
            klingVideo: klingResult.response?.value?.video?.url || null,
            mismatchCalls,
            mismatchResponse: mismatch.response,
            mismatchRefusedStatus: mismatch.refusedStatus,
            fallbackCalls,
            fallbackVideo: fallback.response?.value?.video?.url || null,
            fallbackRefusedStatus: fallback.refusedStatus,
            exhaustedCalls,
            exhaustedResponse: exhausted.response,
            exhaustedRefusedStatus: exhausted.refusedStatus,
            exhaustedAttempts: exhausted.attempts,
            pikaAttempts: pikaResult.attempts,
            redirectAttempts,
            thrownAttempts: thrown.attempts,
            retrievalFailures,
            refusedStatus: refused.refusedStatus,
            exactProviderUrl: subject.falQueueResultUrl({{
              response_url:
                `https://queue.fal.run/fal-ai/pika/requests/${{requestId}}/response`,
            }}, requestId),
            wrongHost: subject.falQueueResultUrl({{
              response_url:
                `https://example.com/fal-ai/pika/requests/${{requestId}}/response`,
            }}, requestId),
            wrongRequest: subject.falQueueResultUrl({{
              response_url:
                "https://queue.fal.run/fal-ai/pika/requests/wrong-id/response",
            }}, requestId),
            credentials: subject.falQueueResultUrl({{
              response_url:
                `https://user:pass@queue.fal.run/fal-ai/pika/requests/${{requestId}}/response`,
            }}, requestId),
            nonDefaultPort: subject.falQueueResultUrl({{
              response_url:
                `https://queue.fal.run:444/fal-ai/pika/requests/${{requestId}}/response`,
            }}, requestId),
            unknownModel: subject.falQueueUrlCandidates(
              "fal-ai/unknown/model", requestId
            ),
          }};
        }})()
        """
    )


    pika_root = f"https://queue.fal.run/fal-ai/pika/requests/{request_id}"
    pika_full = (
        "https://queue.fal.run/fal-ai/pika/v2/pikaswaps/requests/"
        f"{request_id}"
    )
    kling_root = (
        "https://queue.fal.run/fal-ai/kling-video/requests/" f"{request_id}"
    )
    kling_full = (
        "https://queue.fal.run/fal-ai/kling-video/o3/pro/video-to-video/edit/"
        f"requests/{request_id}"
    )
    assert result == {
        "pikaCandidates": [
            {"statusUrl": f"{pika_root}/status", "resultUrl": pika_root},
            {"statusUrl": f"{pika_full}/status", "resultUrl": pika_full},
        ],
        "klingCandidates": [
            {"statusUrl": f"{kling_root}/status", "resultUrl": kling_root},
            {"statusUrl": f"{kling_full}/status", "resultUrl": kling_full},
        ],
        "pikaCalls": [{"url": f"{pika_root}/response", "method": "GET"}],
        "pikaVideo": "https://v3.fal.media/pika.mp4",
        "klingCalls": [{"url": f"{kling_full}/response", "method": "GET"}],
        "klingVideo": "https://v3.fal.media/kling.mp4",
        "mismatchCalls": [
            {"url": pika_root, "method": "GET"},
            {"url": pika_full, "method": "GET"},
        ],
        "mismatchResponse": None,
        "mismatchRefusedStatus": None,
        "fallbackCalls": [
            {"url": f"{pika_root}/response", "method": "GET"},
            {"url": pika_root, "method": "GET"},
            {"url": pika_full, "method": "GET"},
        ],
        "fallbackVideo": "https://v3.fal.media/fallback.mp4",
        "fallbackRefusedStatus": None,
        "exhaustedCalls": [
            {"url": f"{pika_root}/response", "method": "GET"},
            {"url": pika_root, "method": "GET"},
            {"url": pika_full, "method": "GET"},
        ],
        "exhaustedResponse": None,
        "exhaustedRefusedStatus": None,
        "exhaustedAttempts": [
            {
                "candidateClass": "provider_response_exact",
                "outcome": "http",
                "status": 413,
            },
            {
                "candidateClass": "provider_response_bare",
                "outcome": "http",
                "status": 405,
            },
            {
                "candidateClass": "full_model",
                "outcome": "http",
                "status": 404,
            },
        ],
        "pikaAttempts": [
            {
                "candidateClass": "provider_response_exact",
                "outcome": "ok",
                "status": 200,
            }
        ],
        "redirectAttempts": [
            {
                "candidateClass": "provider_response_exact",
                "outcome": "redirect",
                "status": 302,
            },
            {
                "candidateClass": "provider_response_bare",
                "outcome": "redirect",
                "status": 302,
            },
            {
                "candidateClass": "full_model",
                "outcome": "redirect",
                "status": 302,
            },
        ],
        "thrownAttempts": [
            {
                "candidateClass": "provider_response_exact",
                "outcome": "thrown",
                "status": None,
            },
            {
                "candidateClass": "provider_response_bare",
                "outcome": "thrown",
                "status": None,
            },
            {
                "candidateClass": "full_model",
                "outcome": "thrown",
                "status": None,
            },
        ],
        "retrievalFailures": {
            "401": {"hasResponse": False, "refusedStatus": 401},
            "403": {"hasResponse": False, "refusedStatus": 403},
            "429": {"hasResponse": False, "refusedStatus": 429},
            "500": {"hasResponse": False, "refusedStatus": 500},
            "302": {"hasResponse": False, "refusedStatus": None},
            "throw": {"hasResponse": False, "refusedStatus": None},
        },
        "refusedStatus": 401,
        "exactProviderUrl": f"{pika_root}/response",
        "wrongHost": None,
        "wrongRequest": None,
        "credentials": None,
        "nonDefaultPort": None,
        "unknownModel": [],
    }
    assert all(
        not candidate["resultUrl"].endswith("/response")
        for model_candidates in (
            result["pikaCandidates"],
            result["klingCandidates"],
        )
        for candidate in model_candidates
    )
    for attempt_group in (
        result["exhaustedAttempts"],
        result["pikaAttempts"],
        result["redirectAttempts"],
        result["thrownAttempts"],
    ):
        assert all(
            set(attempt) == {"candidateClass", "outcome", "status"}
            for attempt in attempt_group
        )

    edge = EDGE.read_text(encoding="utf-8")
    poll = edge.split("const pollGenerationStrategyProvider = async (", 1)[1]
    poll = poll.split("const evidenceHash = await sha256Hex", 1)[0]
    assert "fetchFalQueueResult({" in poll
    assert "provider_result_http_${providerRefusedStatus}" not in poll
    assert 'return recoveryExit("result_get_refused");' in poll
    assert 'return recoveryExit("result_routes_exhausted");' in poll
    assert 'fetchJson(candidate.url, { method: "GET" })' in CONTRACT.read_text(
        encoding="utf-8"
    )
    assert "`${RUNWAY_API_ORIGIN}/v1/tasks/${identity.providerTaskId}`" in poll
    assert '{ method: "GET", redirect: "manual", headers: statusHeaders }' in poll
    result_fetch = poll.split("fetchFalQueueResult({", 1)[1].split("});", 1)[0]
    assert 'redirect: "manual"' in result_fetch
    assert 'accept: "application/json"' in result_fetch
    assert '"content-type": "application/json"' in result_fetch
    assert 'authorization: `Key ${secret}`' in result_fetch
    assert '"strategy_recovery.result_get"' in poll
    assert 'upstreamStatus: typeof attempt.status === "number"' in poll
    for safe_class in (
        "provider_response_exact",
        "provider_response_bare",
        "app_root",
        "full_model",
    ):
        assert f'"{safe_class}"' in poll
    assert "attempt.url" not in poll
    assert "attempt.value" not in poll


def test_fal_completed_machine_error_type_is_failed_without_prose_leakage() -> None:
    """COMPLETED can be a terminal fal failure; only error_type is trusted."""
    hostile_prose = "https://evil.example/leak?secret=do-not-log"
    result = _evaluate(
        f"""
        (() => {{
          const read = (value) => subject.falStrategyProviderStatus(value);
          const hostileProse = {json.dumps(hostile_prose)};
          const values = {{
            normal: read({{status:"COMPLETED"}}),
            documented: read({{
              status:"COMPLETED",
              error_type:"runner_server_error",
              error:hostileProse,
            }}),
            punctuation: read({{
              status:"COMPLETED",
              error_type:"RUNNER.CONNECTION-TIMEOUT:v2",
              error:hostileProse,
            }}),
            humanOnly: read({{status:"COMPLETED",error:hostileProse}}),
            url: read({{status:"COMPLETED",error_type:hostileProse}}),
            sentence: read({{
              status:"COMPLETED",
              error_type:"runner server error",
            }}),
            markup: read({{
              status:"COMPLETED",
              error_type:"<script>alert(1)</script>",
            }}),
            tooLong: read({{status:"COMPLETED",error_type:"a".repeat(81)}}),
            opaqueSegment: read({{
              status:"COMPLETED",
              error_type:"a".repeat(25),
            }}),
            boundedFailureCode: read({{
              status:"COMPLETED",
              error_type:Array(27).fill("aa").join("_"),
            }}),
            nonString: read({{status:"COMPLETED",error_type:{{code:"x"}}}}),
          }};
          return {{
            values,
            serializedContainsHumanProse:
              JSON.stringify(values).includes(hostileProse),
          }};
        }})()
        """
    )

    succeeded = {
        "providerStatus": "succeeded",
        "outputUrl": None,
        "failureCode": None,
    }
    assert result == {
        "values": {
            "normal": succeeded,
            "documented": {
                "providerStatus": "failed",
                "outputUrl": None,
                "failureCode": "provider_runner_server_error",
            },
            "punctuation": {
                "providerStatus": "failed",
                "outputUrl": None,
                "failureCode": "provider_runner_connection_timeout_v2",
            },
            "humanOnly": succeeded,
            "url": succeeded,
            "sentence": succeeded,
            "markup": succeeded,
            "tooLong": succeeded,
            "opaqueSegment": succeeded,
            "boundedFailureCode": succeeded,
            "nonString": succeeded,
        },
        "serializedContainsHumanProse": False,
    }


def test_fal_http_result_route_recovery_candidates_and_replay_are_exact() -> None:
    """Only billed 405/413 shapes and the strict replay receipt can pass."""
    result = _evaluate(
        f"""
        (() => {{
          const fixture = {_STATUS_FIXTURE.strip()};
          const clone = (value) => JSON.parse(JSON.stringify(value));
          const requestId = "018f8e00-7b4a-7abc-8def-0123456789ab";
          const status = clone(fixture.fal);
          status.job.status = "failed";
          status.job.provider_status = "failed";
          status.job.provider_task_id = requestId;
          status.job.actual_cost_minor = status.job.estimated_cost_minor;
          status.error = {{
            code: "provider_result_http_405",
            provider_billing_outcome: "unknown",
          }};
          status.contract.poll_provider_allowed = false;
          const status413 = clone(status);
          status413.error.code = "provider_result_http_413";
          const runway = clone(fixture.runway);
          runway.job.status = "failed";
          runway.job.provider_status = "failed";
          runway.job.provider_task_id = requestId;
          runway.job.actual_cost_minor = runway.job.estimated_cost_minor;
          runway.error = clone(status.error);
          runway.contract.poll_provider_allowed = false;
          const expected = {{
            projectId: fixture.ids.project,
            generationJobId: fixture.ids.job,
          }};
          const candidate = (value) =>
            subject.readFalResultHttp405RecoveryCandidate(value, expected);
          const candidate413 = (value) =>
            subject.readFalResultHttp413RecoveryCandidate(value, expected);
          const rejected = (mutate) => {{
            const value = clone(status);
            mutate(value);
            return candidate(value) === null;
          }};

          const response = {{
            ok: true,
            version: "generation-strategy-provider-result-recovery-response-v1",
            replay: false,
            event: {{
              generation_job_id: fixture.ids.job,
              provider_task_id: requestId,
              previous_status: "failed",
              provider_status: "succeeded",
            }},
            output: {{
              media_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
              mime_type: "video/mp4",
              size_bytes: 4096,
            }},
            contract: {{
              provider_post_retried: false,
              ledger_mutated: false,
              manual_human_review_required: true,
            }},
          }};
          const readResponse = (value) =>
            subject.readGenerationStrategyProviderResultRecovery(value, {{
              generationJobId: fixture.ids.job,
              providerTaskId: requestId,
            }}) !== null;
          const responseRejected = (mutate) => {{
            const value = clone(response);
            mutate(value);
            return !readResponse(value);
          }};

          return {{
            candidate: candidate(status),
            candidate413: candidate413(status413),
            crossCodeRejected:
              candidate(status413) === null && candidate413(status) === null,
            publicStatusStillParses: fixture.read(status),
            runwayPublicStatusStillParses: fixture.read(runway),
            runwayRejected: candidate(runway) === null,
            rejects: [
              rejected((value) => {{ value.job.actual_cost_minor = 0; }}),
              rejected((value) => {{
                value.job.provider_task_id = "fal-request-not-uuid-v7";
              }}),
              rejected((value) => {{
                value.dispatch.provider_http_status = 201;
              }}),
              rejected((value) => {{
                value.error.code = "provider_result_http_401";
              }}),
              rejected((value) => {{
                value.reconciliation = {{
                  required: false,
                  incident_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                  resolution: "provider_task_attached",
                  reconciled_at: "2026-08-19T08:01:00.000Z",
                }};
              }}),
              rejected((value) => {{ value.price.provider = "runway"; }}),
              rejected((value) => {{ value.extra = true; }}),
            ],
            responseAccepted: readResponse(response),
            replayAccepted: readResponse({{ ...response, replay: true }}),
            responseRejects: [
              responseRejected((value) => {{ value.extra = true; }}),
              responseRejected((value) => {{
                value.event.generation_job_id =
                  "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
              }}),
              responseRejected((value) => {{
                value.event.provider_task_id =
                  "018f8e00-7b4a-7abc-8def-111111111111";
              }}),
              responseRejected((value) => {{
                value.event.previous_status = "processing";
              }}),
              responseRejected((value) => {{
                value.output.mime_type = "video/webm";
              }}),
              responseRejected((value) => {{
                value.contract.provider_post_retried = true;
              }}),
              responseRejected((value) => {{
                value.contract.ledger_mutated = true;
              }}),
              responseRejected((value) => {{
                value.contract.manual_human_review_required = false;
              }}),
            ],
          }};
        }})()
        """
    )

    assert result == {
        "candidate": {
            "providerTaskId": "018f8e00-7b4a-7abc-8def-0123456789ab",
            "recipe": "product_swap",
            "failureCode": "provider_result_http_405",
        },
        "candidate413": {
            "providerTaskId": "018f8e00-7b4a-7abc-8def-0123456789ab",
            "recipe": "product_swap",
            "failureCode": "provider_result_http_413",
        },
        "crossCodeRejected": True,
        "publicStatusStillParses": True,
        "runwayPublicStatusStillParses": True,
        "runwayRejected": True,
        "rejects": [True] * 7,
        "responseAccepted": True,
        "replayAccepted": True,
        "responseRejects": [True] * 8,
    }


def test_strategy_status_result_recovery_is_get_only_and_uses_its_writer() -> None:
    """Recovery cannot POST again or fall through to the normal recorder."""
    edge = EDGE.read_text(encoding="utf-8")
    poll = edge.split("const pollGenerationStrategyProvider = async (", 1)[1]
    poll = poll.split("// Diagnostic probe:", 1)[0]
    handler = edge.split("const handleGenerationStrategyStatus = async (", 1)[1]
    handler = handler.split("const handleGenerationStrategyStart = async (", 1)[0]

    assert 'recordMode: GenerationStrategyProviderPollMode;' in poll
    assert 'provider !== "fal"' in poll
    assert 'method: "POST"' not in poll
    assert "method: 'POST'" not in poll
    assert '"system_recover_generation_strategy_provider_result"' in poll
    recovery_call = poll.split(
        '"system_recover_generation_strategy_provider_result"', 1
    )[1].split("if (recovered.error", 1)[0]
    assert "input_payload: {" in recovery_call
    assert "p_payload: {" not in recovery_call
    assert '"system_record_generation_strategy_provider_status"' in poll
    assert poll.index('if (recoveryMode) {') < poll.index(
        '"system_record_generation_strategy_provider_status"'
    )
    assert '"FAL_RESULT_HTTP_405_RECOVERY_VERIFIED"' in poll
    assert '"FAL_RESULT_HTTP_413_RECOVERY_VERIFIED"' in poll
    assert (
        "`strategy-result-recovery:${identity.generationJobId}:`" in poll
    )
    assert "failed_event_id" not in poll

    candidate = "readFalResultHttp405RecoveryCandidate(current, recoveryExpected)"
    candidate413 = "readFalResultHttp413RecoveryCandidate(current, recoveryExpected)"
    normal_gate = "contract.poll_provider_allowed === true"
    assert candidate in handler
    assert candidate413 in handler
    assert handler.index(candidate) < handler.index(normal_gate)
    assert handler.index(candidate413) < handler.index(normal_gate)
    assert 'route.provider !== "fal"' in handler
    assert "recordMode: recovery.failureCode ===" in handler
    assert '? "recover_fal_result_http_413"' in handler
    assert ': "recover_fal_result_http_405"' in handler
    assert "`${RUNWAY_API_ORIGIN}/v1/tasks/${identity.providerTaskId}`" in poll
    assert "provider_result_http_${providerRefusedStatus}" not in poll
    assert 'return recoveryExit("result_get_refused");' in poll


def test_strategy_result_recovery_silent_exits_are_redacted_and_flushed() -> None:
    """A failed GET-only repair must identify its stage without leaking input."""
    edge = EDGE.read_text(encoding="utf-8")
    poll = edge.split("const pollGenerationStrategyProvider = async (", 1)[1]
    poll = poll.split("// Diagnostic probe:", 1)[0]
    handler = edge.split("const handleGenerationStrategyStatus = async (", 1)[1]
    handler = handler.split("const handleGenerationStrategyStart = async (", 1)[0]

    helper = poll.split("const recoveryExit = (code: string): null => {", 1)[1]
    helper = helper.split("// The recovery writer is deliberately fal-only.", 1)[0]
    assert (
        'noteGenerationRefusal(request, "strategy_recovery.poll", code, {'
        in helper
    )
    assert "jobId: identity.generationJobId" in helper
    for forbidden in (
        "response.value",
        "providerState",
        "outputUrl",
        "statusHeaders",
        "secret",
    ):
        assert forbidden not in helper

    stage_codes = (
        "provider_route_invalid",
        "provider_secret_unavailable",
        "model_route_unavailable",
        "status_candidates_exhausted",
        "status_unclassified",
        "result_routes_exhausted",
        "result_get_refused",
        "provider_processing",
        "provider_failed",
        "provider_cancelled",
        "result_shape_invalid",
        "output_url_rejected",
        "output_target_unavailable",
        "output_download_invalid",
        "storage_upload_failed",
        "recovery_rpc_rejected",
        "recovery_response_invalid",
    )
    for code in stage_codes:
        assert f'recoveryExit("{code}")' in poll
        # Match the production logger's closed, low-entropy word shape.
        assert len(code) <= 110
        assert all(
            segment.isalpha() and 1 <= len(segment) <= 24
            for segment in code.split("_")
        )

    assert '"strategy_recovery.provider"' in poll
    assert 'providerState.failureCode ?? "provider_task_failed"' in poll

    # The public status response remains HTTP 200 and unchanged. Only the
    # already-redacted trail is explicitly flushed for the silent null result.
    assert "const recoveryStatus = await pollGenerationStrategyProvider({" in handler
    assert "if (recoveryStatus === null) {" in handler
    assert "flushGenerationRefusal(request, responseBody, 200);" in handler
    assert "return json(request, responseBody);" in handler


def _adapters(expression: str) -> object:
    """Собрать провайдерский запрос настоящими адаптерами, а не по описанию.

    Отдельный помощник рядом с `_evaluate`: тот импортирует edge-контракт, а
    здесь нужен модуль адаптеров — именно он решает, что уйдёт провайдеру.
    """

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy adapter contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        for source in (ADAPTERS, CATALOG):
            (directory / source.name).write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
        (directory / "run.js").write_text(
            f"import * as subject from './{ADAPTERS.name}';\n"
            f"const result = await ({expression});\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "run.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


DUET_SOURCE_URI = (
    "https://project.supabase.co/storage/v1/object/sign/private/source.mp4?token=a"
)
DUET_FACE_URI = (
    "https://project.supabase.co/storage/v1/object/sign/private/face.jpg?token=b"
)

_DUET_FOREIGN_ENGINES_FIXTURE = """
(() => {
  const attempt = (callback) => {
    try { return { ok: true, value: callback() }; }
    catch (error) { return { ok: false, code: error?.code || String(error) }; }
  };
  const selection = {
    strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
    strategyId: "viral_avatar_ugc",
    recipe: "product_ugc",
    recipeVersion: subject.RUNWAY_RECIPE_VERSION,
    durationSeconds: 8,
    audio: true,
    resolution: "720p",
    promptText: "Смотрите, тут он показывает крепление.",
  };
  const source = { role: "source_video", uri: SOURCE_URI };
  const face = { role: "avatar", uri: FACE_URI };

  return {
    runway: attempt(() => subject.buildRunwayRecipeRequest(
      selection, [source, face],
    )),
    pika: attempt(() => subject.buildFalRecipeRequest(
      selection, [source, face], "fal-ai/pika/v2/pikaswaps",
    )),
    kling: attempt(() => subject.buildFalRecipeRequest(
      { ...selection, modifyRegion: "the person performing on camera" },
      [source, face],
      "fal-ai/kling-video/o3/pro/video-to-video/edit",
    )),
    // Те же движки для «Копии» работают: отказ именно про рецепт, а не про
    // сломанный маршрут вообще.
    swapStillWorks: attempt(() => subject.buildFalRecipeRequest(
      {
        ...selection,
        strategyId: "viral_product_swap",
        recipe: "product_swap",
        modifyRegion: "the product on camera",
      },
      [source, { role: "original_product", uri: FACE_URI },
       { role: "product_primary", uri: SOURCE_URI + "&b=1" }],
      "fal-ai/pika/v2/pikaswaps",
    )),
    // Компиляторы «замены человека в кадре» удалены вместе с маршрутами.
    removedCompilers: [
      "buildFalAvatarSelection",
      "buildRunwayAvatarPrompt",
    ].filter((name) => name in subject),
  };
})()
"""


def test_no_engine_but_heygen_can_build_a_duet_run() -> None:
    """Ни один движок, кроме HeyGen, «Дуэт» собрать не может — и это про деньги.

    До 22.08.2026 стратегия ездила на Runway Aleph, Pika Swaps и Kling O3 Pro:
    тогда она читалась как замена человека в кадре. Владелец переопределил её —
    исходный ролик НЕ трогается вовсе, ведущий врезается поверх него отдельным
    слоем.

    Прежние движки остались работать и остались платными. Отправить дуэт любому
    из них значит за настоящие деньги получить переписанный чужой ролик вместо
    комментария к нему — причём результат будет выглядеть «успешным»: провайдер
    вернёт видео, деньги спишутся, и только человек заметит, что сделано не то.

    Реестр маршрутов такие строки уже запрещает (миграция 202608220011). Здесь
    то же самое сказано кодом: защита не может держаться на одной таблице, из
    которой строку однажды вернут обратно.
    """

    payload = _adapters(
        _DUET_FOREIGN_ENGINES_FIXTURE
        .replace("SOURCE_URI", json.dumps(DUET_SOURCE_URI))
        .replace("FACE_URI", json.dumps(DUET_FACE_URI))
    )

    assert payload["runway"]["ok"] is False
    assert payload["runway"]["code"] == "runway_recipe_unsupported"
    assert payload["pika"]["ok"] is False
    assert payload["pika"]["code"] == "fal_recipe_unsupported"
    assert payload["kling"]["ok"] is False
    assert payload["kling"]["code"] == "fal_recipe_unsupported"

    # «Копия» на том же движке по-прежнему собирается.
    assert payload["swapStillWorks"]["ok"] is True, payload["swapStillWorks"]

    # Экспортов «замены человека в кадре» больше нет: держать готовое платное
    # тело запроса «на всякий случай» — приглашение вернуть его обратно.
    assert payload["removedCompilers"] == []


_HEYGEN_FIXTURE = """
(() => {
  const attempt = (callback) => {
    try { return { ok: true, value: callback() }; }
    catch (error) { return { ok: false, code: error?.code || String(error) }; }
  };
  const selection = {
    strategyVersion: subject.GENERATION_STRATEGY_CONTRACT_VERSION,
    strategyId: "viral_avatar_ugc",
    recipe: "product_ugc",
    recipeVersion: subject.RUNWAY_RECIPE_VERSION,
    durationSeconds: 15,
    audio: true,
    resolution: "720p",
    promptText: "Смотрите, тут он показывает крепление — вот на это и обратите внимание.",
  };
  const presenter = {
    avatarId: "avatar_look_abc123",
    voiceId: "voice_ru_female_01",
    aspectRatio: "9:16",
  };
  const SOURCE = "https://project.supabase.co/storage/v1/object/sign/private/source.mp4?token=opaque";
  const good = subject.buildHeygenRecipeRequest(selection, presenter, SOURCE);
  const placed = subject.buildHeygenRecipeRequest(
    selection,
    {
      ...presenter,
      avatarKind: "avatar",
      layout: { corner: "top_left", shape: "cutout", widthPercent: 50 },
    },
    SOURCE,
  );

  return {
    envelope: good,
    // Чужой рецепт: ведущего делает только «Дуэт».
    placed,
    swapRecipe: attempt(() => subject.buildHeygenRecipeRequest(
      { ...selection, strategyId: "viral_product_swap", recipe: "product_swap" },
      presenter, SOURCE,
    )),
    // Область замены — поле маршрутов, которые что-то заменяют. HeyGen не
    // заменяет ничего, и её присутствие означает выбор, собранный не для него.
    foreignField: attempt(() => subject.buildHeygenRecipeRequest(
      { ...selection, modifyRegion: "the person on camera" }, presenter, SOURCE,
    )),
    badResolution: attempt(() => subject.buildHeygenRecipeRequest(
      { ...selection, resolution: "480p" }, presenter, SOURCE,
    )),
    badRatio: attempt(() => subject.buildHeygenRecipeRequest(
      selection, { ...presenter, aspectRatio: "4:3" }, SOURCE,
    )),
    emptyAvatar: attempt(() => subject.buildHeygenRecipeRequest(
      selection, { ...presenter, avatarId: "" }, SOURCE,
    )),
    extraPresenterKey: attempt(() => subject.buildHeygenRecipeRequest(
      selection, { ...presenter, background: "#00ff00" }, SOURCE,
    )),
    emptyScript: attempt(() => subject.buildHeygenRecipeRequest(
      { ...selection, promptText: "" }, presenter, SOURCE,
    )),
    // Исходник — только подписанная ссылка нашего хранилища.
    foreignSource: attempt(() => subject.buildHeygenRecipeRequest(
      selection, presenter, "https://cdn.example.com/video.mp4",
    )),
    noSource: attempt(() => subject.buildHeygenRecipeRequest(
      selection, presenter, undefined,
    )),
  };
})()
"""


def test_heygen_duet_presenter_request_is_exact_and_always_transparent() -> None:
    """Тело платного запроса к HeyGen выписано целиком.

    С 23.08.2026 соединение ведущего с роликом делает сам провайдер: v2
    `POST /v2/video/generate` получает исходник ФОНОМ (подписанная ссылка нашего
    хранилища) и ставит ведущего поверх него кружком или вырезом в углу.
    Результат — готовый MP4, который принимает потоковый приём «Копии».
    Прежний замысел (прозрачный WebM + наш ffmpeg) не имел хоста для сборки.

    Схема v2 сверена 23.08.2026 по архиву docs.heygen.com/reference/
    create-an-avatar-video-v2; v1/v2 живут до 31.10.2026.
    """

    payload = _adapters(_HEYGEN_FIXTURE)
    source = (
        "https://project.supabase.co/storage/v1/object/sign/private/"
        "source.mp4?token=opaque"
    )

    assert payload["envelope"] == {
        "provider": "heygen",
        "endpointPath": "/v2/video/generate",
        "method": "POST",
        "body": {
            "video_inputs": [
                {
                    "character": {
                        # Фото-аватар по умолчанию; раскладка по умолчанию —
                        # кружок 34 % ширины в правом нижнем углу.
                        "type": "talking_photo",
                        "talking_photo_id": "avatar_look_abc123",
                        "scale": 0.34,
                        "offset": {"x": 0.29, "y": 0.29},
                        "talking_photo_style": "circle",
                        "circle_background_color": "#FFFFFF",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": (
                            "Смотрите, тут он показывает крепление — "
                            "вот на это и обратите внимание."
                        ),
                        "voice_id": "voice_ru_female_01",
                    },
                    "background": {
                        "type": "video",
                        "url": source,
                        "play_style": "freeze",
                        "fit": "cover",
                    },
                }
            ],
            "dimension": {"width": 720, "height": 1280},
            "title": "Duet presenter 15s 720p",
        },
        "pollKind": "heygen_video",
    }

    # Видеоаватар, вырез без окна, левый верхний угол на половину кадра.
    placed = payload["placed"]["body"]["video_inputs"][0]["character"]
    assert placed == {
        "type": "avatar",
        "avatar_id": "avatar_look_abc123",
        "scale": 0.5,
        "offset": {"x": -0.21, "y": -0.21},
        "matting": True,
    }
    assert payload["foreignSource"] == {"ok": False, "code": "signed_url_invalid"} or (
        payload["foreignSource"]["ok"] is False
    )
    assert payload["noSource"]["ok"] is False

    for case, code in (
        ("swapRecipe", "heygen_recipe_unsupported"),
        ("foreignField", "heygen_selection_foreign_field"),
        ("badResolution", "resolution_invalid"),
        ("badRatio", "heygen_presenter_invalid"),
        ("emptyAvatar", "heygen_presenter_invalid"),
        ("extraPresenterKey", "heygen_presenter_invalid"),
        # Пустая речь отбивается общей проверкой указания: ведущему нечего
        # сказать — значит платить не за что.
        ("emptyScript", "prompt_text_invalid"),
    ):
        assert payload[case]["ok"] is False, case
        assert payload[case]["code"] == code, case


_HEYGEN_POLL_FIXTURE = """
(() => {
  const VIDEO = "vid_xyz789abc";
  const created = subject.parseCreatedHeygenVideo(
    { data: { video_id: VIDEO } },
  );
  const status = (data) => subject.heygenStrategyProviderStatus({ data }, VIDEO);
  return {
    created,
    // Идентификатор в корне, как у Runway, — не наша форма.
    createdFlat: subject.parseCreatedHeygenVideo({ video_id: VIDEO }),
    createdEmpty: subject.parseCreatedHeygenVideo({ data: { video_id: "" } }),

    generating: status({ id: VIDEO, status: "generating" }),
    completed: status({
      id: VIDEO,
      status: "completed",
      video_url: "https://files.heygen.ai/video/vid_xyz789abc.webm",
      duration: 15.0,
    }),
    // Успех без ссылки успехом не является: платить за ролик, который некому
    // забрать, нельзя.
    completedNoUrl: status({ id: VIDEO, status: "completed" }),
    failed: status({
      id: VIDEO,
      status: "failed",
      failure_code: "AVATAR_NOT_FOUND",
      failure_message: "Avatar avatar_look_abc123 is not available for matting",
    }),
    failedNoCode: status({ id: VIDEO, status: "failed" }),
    // Ответ о ЧУЖОЙ задаче принимать нельзя.
    foreignTask: subject.heygenStrategyProviderStatus(
      { data: { id: "vid_someone_else", status: "completed",
                video_url: "https://files.heygen.ai/video/x.webm" } },
      VIDEO,
    ),
    // Форма другого провайдера не должна разбираться этим кодом.
    falShape: subject.heygenStrategyProviderStatus(
      { status: "COMPLETED" }, VIDEO,
    ),
    unknownStatus: status({ id: VIDEO, status: "cancelled_by_user" }),
  };
})()
"""


def test_heygen_poll_reads_its_own_response_shape_and_refuses_every_other() -> None:
    """Опрос HeyGen разбирает СВОЮ форму ответа и отвергает чужие.

    Три провайдера отвечают по-разному, и это не мелочь оформления. У Runway
    поля лежат в корне; очередь fal сообщает только статус, а готовый ролик
    забирается вторым запросом; HeyGen кладёт и статус, и ссылку сразу — но
    внутрь вложенного `data`.

    Разобрать чужую форму своим кодом значит не найти полей и оставить наряд «в
    работе» навсегда: деньги уже списаны, а опрос никогда не завершится. Именно
    так однажды повисла задача fal, опрошенная рунвеевским путём.

    Схема сверена 22.08.2026 по https://developers.heygen.com/docs/quick-start
    """

    payload = _evaluate(_HEYGEN_POLL_FIXTURE)

    # Создание задачи: идентификатор берётся из data.video_id и ниоткуда больше.
    assert payload["created"] == {"id": "vid_xyz789abc"}
    assert payload["createdFlat"] is None
    assert payload["createdEmpty"] is None

    assert payload["generating"] == {
        "providerStatus": "processing", "outputUrl": None, "failureCode": None,
    }
    assert payload["completed"] == {
        "providerStatus": "succeeded",
        "outputUrl": "https://files.heygen.ai/video/vid_xyz789abc.webm",
        "failureCode": None,
    }
    # Неразобранный ответ — это null, а не «готово»: наряд останется в работе и
    # будет опрошен снова, вместо того чтобы закрыться пустым результатом.
    assert payload["completedNoUrl"] is None

    # Код отказа приводится к низкоэнтропийному словарю; свободный текст
    # провайдера в журнал не переносится вовсе.
    assert payload["failed"] == {
        "providerStatus": "failed",
        "outputUrl": None,
        "failureCode": "avatar_not_found",
    }
    assert payload["failedNoCode"]["failureCode"] == "provider_task_failed"

    # Чужая задача и чужая форма ответа не разбираются.
    assert payload["foreignTask"] is None
    assert payload["falShape"] is None
    # Незнакомое состояние тоже не угадывается.
    assert payload["unknownStatus"] is None


_HEYGEN_AVATAR_FIXTURE = """
(() => {
  const attempt = (callback) => {
    try { return { ok: true, value: callback() }; }
    catch (error) { return { ok: false, code: error?.code || String(error) }; }
  };
  const photo = "https://project.supabase.co/storage/v1/object/sign/private/face.jpg?token=x";
  const good = subject.buildHeygenAvatarRequest({
    name: "Ведущая Аня",
    photoUrl: photo,
  });
  return {
    envelope: good,
    // Чужая ссылка означала бы, что провайдеру показывают файл, происхождение
    // которого мы не проверяли.
    foreignPhoto: attempt(() => subject.buildHeygenAvatarRequest({
      name: "Аня", photoUrl: "https://evil.example/face.jpg",
    })),
    emptyName: attempt(() => subject.buildHeygenAvatarRequest({
      name: "", photoUrl: photo,
    })),
    extraKey: attempt(() => subject.buildHeygenAvatarRequest({
      name: "Аня", photoUrl: photo, avatarGroupId: "grp_1",
    })),
  };
})()
"""


def test_creating_a_presenter_is_one_paid_call_with_our_signed_photo() -> None:
    """Ведущий заводится ОДНИМ вызовом, а фотография отдаётся ссылкой.

    Отдельная загрузка файла провайдеру не нужна: ссылка на наше хранилище
    короткоживущая и подписанная — тем же приёмом, что и ассеты генерации. Так у
    провайдера не остаётся нашего файла дольше, чем нужно на обучение.

    Это ОТДЕЛЬНЫЙ платный вызов, а не часть генерации: $1.00 за создание против
    посекундной оплаты ролика. Ведущий заводится один раз и живёт долго — отсюда
    и разовая оплата, и отдельная запись.

    Схема сверена 22.08.2026 по
    https://developers.heygen.com/reference/create-avatar.md
    """

    payload = _adapters(_HEYGEN_AVATAR_FIXTURE)

    assert payload["envelope"] == {
        "provider": "heygen",
        "endpointPath": "/v3/avatars",
        "method": "POST",
        "body": {
            # Только photo: digital_twin стоит столько же, но требует отснятого
            # материала, а у нас на входе одна фотография.
            "type": "photo",
            "name": "Ведущая Аня",
            "file": {
                "type": "url",
                "url": (
                    "https://project.supabase.co/storage/v1/object/sign/"
                    "private/face.jpg?token=x"
                ),
            },
        },
        # Своё ожидание: обучение аватара — не то же самое, что рендер ролика.
        "pollKind": "heygen_avatar",
    }

    assert payload["foreignPhoto"]["ok"] is False
    assert payload["emptyName"]["ok"] is False
    assert payload["emptyName"]["code"] == "heygen_avatar_input_invalid"
    assert payload["extraKey"]["ok"] is False
    assert payload["extraKey"]["code"] == "heygen_avatar_input_invalid"


_HEYGEN_AVATAR_STATUS_FIXTURE = """
(() => {
  const AVATAR = "avatar_look_abc123";
  const created = subject.parseCreatedHeygenAvatar({
    data: {
      avatar_item: { id: AVATAR, status: "processing" },
      avatar_group: { id: "avatar_group_xyz9" },
    },
  });
  const status = (item) => subject.heygenAvatarStatus({ data: { avatar_item: item } }, AVATAR);
  return {
    created,
    // Идентификатор ролика лежит в data.video_id, ведущего — в
    // data.avatar_item.id. Разобрать одно другим нельзя.
    createdVideoShape: subject.parseCreatedHeygenAvatar({ data: { video_id: AVATAR } }),

    training: status({ id: AVATAR, status: "processing" }),
    awaitingConsent: status({ id: AVATAR, status: "pending_consent" }),
    ready: status({ id: AVATAR, status: "completed" }),
    // Готовность без идентификатора готовностью не является.
    readyNoId: subject.heygenAvatarStatus(
      { data: { avatar_item: { status: "completed" } } }, null,
    ),
    failed: status({
      id: AVATAR, status: "failed", failure_code: "FACE_NOT_DETECTED",
    }),
    foreignAvatar: subject.heygenAvatarStatus(
      { data: { avatar_item: { id: "avatar_someone_else", status: "completed" } } },
      AVATAR,
    ),
    unknownStatus: status({ id: AVATAR, status: "queued_for_review" }),
  };
})()
"""


def test_presenter_training_states_are_kept_apart() -> None:
    """Три состояния обучения нельзя смешивать — каждое значит своё.

    `pending_consent` — это НЕ отказ и НЕ готовность: провайдер сам ждёт
    подтверждения на использование внешности. Смешать его с `failed` значило бы
    выбросить уже оплаченного ведущего; с `completed` — выдать за готового того,
    кем работать ещё нельзя.

    Проверено 22.08.2026 по документации: status ∈
    processing | pending_consent | completed | failed.
    """

    payload = _evaluate(_HEYGEN_AVATAR_STATUS_FIXTURE)

    assert payload["created"] == {
        "id": "avatar_look_abc123",
        "groupId": "avatar_group_xyz9",
        "status": "processing",
    }
    assert payload["createdVideoShape"] is None

    assert payload["training"] == {
        "avatarStatus": "training", "avatarId": None, "failureCode": None,
    }
    assert payload["awaitingConsent"] == {
        "avatarStatus": "awaiting_consent", "avatarId": None, "failureCode": None,
    }
    assert payload["ready"] == {
        "avatarStatus": "ready",
        "avatarId": "avatar_look_abc123",
        "failureCode": None,
    }
    assert payload["readyNoId"] is None

    assert payload["failed"]["avatarStatus"] == "failed"
    # Код отказа приводится к тому же низкоэнтропийному словарю, что у остальных
    # провайдеров; свободный текст провайдера в журнал не переносится.
    assert payload["failed"]["failureCode"] == "face_not_detected"

    # Ответ о чужом ведущем не разбирается, незнакомое состояние не угадывается.
    assert payload["foreignAvatar"] is None
    assert payload["unknownStatus"] is None

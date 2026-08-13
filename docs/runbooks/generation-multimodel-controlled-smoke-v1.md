# Controlled smoke: новые модели генерации v1

Дата: 2026-08-13
Назначение: один контролируемый платный smoke-run после интеграционного релиза.
Автоматический запуск запрещён: этот документ не является разрешением на расходы.

## Обязательные условия до первого запуска

- опубликованы единые browser build/cache bytes не ниже `20260813.os4.39`;
- применена exact migration authority для multi-model generation;
- опубликована соответствующая версия `creator-generate`;
- CI, security checks и production asset/API smoke зелёные для одного exact SHA;
- сотрудник вошёл вручную и открыл доступный ему проект;
- в проекте выбран ровно один товар с подтверждённой identity и правами на исходники;
- есть активная кампания с достаточным лимитом;
- server catalog показывает модель как `launchEnabled=true`;
- текущий acceptance может быть `unproven`: это честный smoke, а не доказанное качество.

Если любое условие не выполнено, запуск прекращается до платного шага.

## Модели Milestone A

Каждая строка проверяется отдельно. Нельзя запускать четыре модели одним пакетом.

| Provider | Model | Минимальный честный сценарий |
| --- | --- | --- |
| Runway | `gen4.5` | одно подтверждённое фото товара → короткое image-to-video без речи |
| Runway | `seedance2_mini` | подтверждённые фото одного товара → короткий ролик; звук только если UI и server catalog разрешают exact выбор |
| Runway | `veo3.1_fast` | один первый кадр; последний кадр только при разрешённой catalog длительности |
| Runway | `gemini_omni_flash` | один исходный кадр → короткий ролик; использовать только image-mode, который публикует server catalog |

Длительность, ratio, resolution, audio, reference count и стоимость не берутся
из этого документа. Их authority — текущий server catalog, exact generation spec и
свежая readiness receipt на открытом экране.

## Один контролируемый проход

1. Открыть `#/workspace/generation` на свежем build без старой вкладки.
2. Убедиться, что на странице ровно одна форма `#mock-batch-form` и один submit.
3. Выбрать результат и нужную модель вручную. Зафиксировать, что UI показывает
   `Выбрано вручную`; рекомендация ИИ остаётся отдельным советом.
4. Выбрать exact товар, назначение и разрешённые исходники. Не использовать
   чужой проект, неподтверждённый файл или временную provider-ссылку.
5. На финальном шаге нажать `Подготовить ТЗ и проверить стоимость бесплатно`.
   Это действие обязано дать:
   - платных provider POST: `0`;
   - generation jobs: `0`;
   - новое точное generation spec;
   - fresh receipt для того же project/spec/provider/model/settings scope;
   - server-derived стоимость и отдельный confirmation token.
6. Сверить на экране provider, public model label, model ID в технических
   деталях, input, duration, ratio/resolution, audio, цену и текущий проект.
7. Сотрудник вручную ставит флажок подтверждения этой свежей цены. Старое или
   заранее поставленное подтверждение недействительно.
8. Нажать платный submit ровно один раз. Ожидается одна idempotent command/job и
   один provider POST после server claim.
9. Если UI завис, сеть оборвалась или результат POST неоднозначен, **не нажимать
   submit повторно**. Открыть «Очередь и архив», прочитать exact job status и
   использовать только status/reconciliation path.
10. Дождаться terminal status. Успешный output обязан быть скачан сервером,
    проверен как MP4 и сохранён в существующее private durable storage. Provider
    URL не является архивным результатом.
11. Открыть output, просмотреть целиком и пройти существующие AI-QA/review gates.
    Provider success или непустой файл не переводят модель в `Проверено`.
12. Независимый сотрудник явно принимает или отклоняет результат. Записать
    причины, особенно fidelity товара, текст/логотип, движение и звук.
13. В «Очередь и архив» отфильтровать exact provider/model и проверить immutable
    snapshot: selection source, settings, estimated/actual cost, receipt lineage,
    catalog/pricing versions. Затем проверить, что `Повторить настройки` создаёт
    только новый черновик и очищает receipt/consent.

## Немедленная остановка

Не продолжать и не повторять платный вызов при любом из условий:

- route, actor, project, form, SKU, media, model или spec изменились после
  бесплатной проверки;
- receipt истекла, относится к другому scope или уже использована;
- UI показывает raw secret, signed provider URL или внутренний payload;
- модель стала disabled/blocked;
- server-derived цена или confirmation token изменились;
- budget reservation отсутствует или не соответствует цене;
- provider start имеет неоднозначный исход;
- job перешёл в terminal failure: разрешён только новый явный человеческий
  запуск с новой receipt, а не blind retry.

## Google и premium

`google:veo-3.1-lite-generate-preview`, `runway:veo3.1` и
`runway:seedance2` не входят в этот Milestone A spend-run. Карточки могут быть
видимы для сравнения, но платная кнопка должна оставаться заблокированной, пока
server policy, secret deployment, provider-specific reconciliation и отдельный
контролируемый runbook не доказаны.

## Что сохранить в отчёте

- exact release SHA/build и migration/Edge versions;
- actor role и project ID без персональных секретов;
- provider/model и exact technical selection;
- fresh receipt ID, job ID и batch ID (без hash/token в публичном отчёте);
- estimated и actual cost;
- terminal status и durable media ID;
- AI-QA outcome и независимое human decision;
- archive filter/snapshot proof;
- число provider POST для прохода — ожидается `1`.

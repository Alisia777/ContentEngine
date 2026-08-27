# Папка «Гипотезы» v1 (контур №3)

Состояние на 27.08.2026, сборка `.29`. Dock-приложение «Гипотезы» (∴,
`/workspace/hypotheses`, deep-link `?hypothesis=<uuid>`), секционный контур.

## Модель

- `content_hypotheses` — identity: код H-NNN (авто), название, жизненный цикл
  (draft → … → completed/archived), итог (untested/confirmed/disproved/
  inconclusive), ответственный. Код/проект/авторство неизменяемы.
- `content_hypothesis_versions` — append-only формулировки «Если X, то
  метрика Y, потому что Z» (≥20 символов) со снапшотом товара, метрикой,
  baseline/target и canonical hash; утверждённая — ровно одна; правка =
  новая версия.
- `content_hypothesis_decisions` — append-only решения ТОЛЬКО человека
  (owner/admin/producer), причина от 10 символов; итог identity ставит
  триггер решения. Никакой RPC не ставит confirmed автоматически.
- `content_hypothesis_source_bindings` — append-only источники-доказательства
  (снапшот canonical URL и хешей; raw-тексты не копируются).
- `content_hypothesis_operator_selections` — активная гипотеза оператора в
  проекте (выбор в формах генерации).

## Связка с запуском

Оператор выбирает утверждённую гипотезу в блоке «Гипотеза запуска» форм
«Создание»/«Копия» (закреплённому сотруднику его гипотеза подставляется
сама — один раз, собственный выбор не перекрывается). Триггер манифеста
происхождения читает выбор запускавшего (bound_by) в момент bind и вписывает
точную версию. Дальше: паспорт показывает «Зачем создан», гипотеза копит
«Варианты и результаты».

## Варианты и вывод

Варианты A/B/C по порядку создания: движок, счётчики, значение основной
метрики гипотезы по формуле, зрелость (72 ч). ★ — лучшее значение основной
метрики среди зрелых данных; победителя объявляет только человек — блок
«Вывод — только человек» с обязательной причиной, действия: подтвердить /
опровергнуть / данных недостаточно / доработка / архив.

## RPC

`creator_content_hypotheses` (список + approved + assigned + выбор),
`creator_content_hypothesis` (срез: версии, источники, варианты, решения,
участники), `creator_save_content_hypothesis`,
`creator_approve_content_hypothesis_version`,
`creator_decide_content_hypothesis`, `creator_select_content_hypothesis`,
`creator_assign_content_hypothesis_owner`,
`creator_bind_content_hypothesis_source`. Все volatile, ACL по проекту.

## Отображение у людей

«Команда → Люди»: колонка «Гипотезы» — коды закреплённых за участником
гипотез текущего проекта, ссылками в срез.

## Тесты

`tests/test_workspace_content_hypotheses_v1.py` (+ живые транзакционные
пробы в проде с RAISE-откатом на каждом этапе).

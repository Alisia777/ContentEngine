# Wildberries Seller Analytics: официальный коннектор

Контур получает историю воронки только по подтверждённым карточкам текущей
организации через официальный метод:

```text
POST https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history
```

## Авторизация

API использует схему `HeaderApiKey` и заголовок `Authorization`. В базе хранится
только ссылка вида `env:WB_SELLER_ANALYTICS_TOKEN`; значение ключа разрешается
из окружения непосредственно перед запросом. Raw API key не записывается в
connection, audit, snapshot, quarantine, dashboard или сообщение об ошибке.

## Границы запроса

- период — не более семи календарных дней включительно;
- один запрос содержит не более 20 `nmIds`;
- один sync содержит не более 1000 подтверждённых `nmIds`;
- большие наборы детерминированно сортируются и делятся на страницы;
- `nmIds` берутся только из `MarketplaceListing` со статусом `verified`, точной
  организацией, кабинетом продавца и пересекающимся периодом действия.

Тело страницы:

```json
{
  "selectedPeriod": {"start": "2026-07-01", "end": "2026-07-07"},
  "nmIds": [100001],
  "skipDeletedNm": true
}
```

## Проверка и хранение

Ответ принимается только при точной структуре official history schema,
неотрицательных целых счётчиках, суммах с точностью до копейки, процентах
`0..100` и уникальных датах внутри запрошенного периода.

Каждый `nmId` разрешается через точное org/seller-scoped сопоставление карточки.
Неизвестные, неоднозначные, неподтверждённые или незапрошенные значения не
угадываются и попадают в `wildberries_metric_quarantine`.

Суточные строки сохраняются в `wildberries_metric_snapshots` с fingerprint,
product/listing lineage и суммами в minor units. Повтор того же ответа не
создаёт второй snapshot. Один `idempotency_key` нельзя использовать для другого
периода или набора карточек.

`wildberries_analytics_sync_audits`, snapshots и quarantine неизменяемы на
уровне ORM и SQLite/PostgreSQL triggers. Ошибка второй страницы отклоняет sync
целиком, не оставляя частичных метрик.

## Readiness

Защищённый `/api/factory-dashboard` возвращает
`wildberries_seller_analytics`: наличие credential reference, возможность
проверки, успешность официального API, последний sync, число подтверждённых
карточек, snapshots и quarantine. Наличие кода не называется живым
подключением: статус `ready` появляется только после успешного official request.

Все автоматические тесты используют только fake HTTP gateway. Реальный API в
тестах не вызывается.

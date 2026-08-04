# Импорт исторических кейсов в ИИ-центр

Историческая таблица не является готовым обучающим правилом. Импорт сохраняет
точные KPI, период, платформу и строку-источник, а вывод относит к одному из
трёх состояний: `good`, `bad` или `review`. Сомнительные данные не превращаются
в «плохой пример» автоматически.

## Контракт безопасности

- CLI работает как `dry-run`, пока оператор явно не передаст `--commit`.
- Разрешены только `.xlsx` и `.csv`; macro-enabled форматы запрещены.
- Неизвестные поля, URL, формулы/CSV-injection и произвольная исходная проза
  отклоняются.
- `source_sha256`, `row_hash` и канонический `manifest_sha256` делают источник
  и каждую строку проверяемыми.
- В одном внутреннем RPC-пакете не более 100 кейсов. Lineage и идемпотентность
  вычисляются сервером для каждого физического пакета.
- Нормализованная запись идёт только через
  `creator_import_ai_historical_case_batch`: RPC доступен лишь service role и
  требует `actor_profile_id` пользователя, уже проверенного Edge-функцией.
  Браузер и CLI не могут вызывать этот RPC напрямую.
- Перед скачиванием Edge вызывает service-role-only
  `creator_authorize_ai_historical_case_import` для одного точного `source_id`.
  Авторизация не зависит от UI-списка последних источников; после проверки
  организации, категории, роли и прав файл читается admin-клиентом только по
  возвращённым bucket/object receipt.
- CLI не принимает service role. `--commit` вызывает authenticated
  `creator-ai-case-import` с `source_id`; Edge проверяет membership от имени
  пользователя, затем использует admin-клиент только для нормализованной записи.
- User access token не выводится в stdout/stderr и не включается в payload.

## Проверка манифеста

```powershell
python scripts/import_ai_historical_cases.py data\ai-historical-cases\manifest-v1.template.json
```

Команда возвращает хеш, число кейсов, пакетов, категорий и исходов. Сеть и
переменные Supabase для этого не нужны.

## Подтверждённая запись

Сначала зарегистрируйте исходный файл во вкладке «База знаний» ИИ-центра и
возьмите его `source_id`. Затем задайте секреты только в окружении процесса:

```powershell
$env:SUPABASE_URL = "https://PROJECT_REF.supabase.co"
$env:SUPABASE_PUBLISHABLE_KEY = "<publishable key>"
$env:CONTENTENGINE_USER_ACCESS_TOKEN = "<authenticated user access token>"
python scripts/import_ai_historical_cases.py path\to\reviewed-manifest.json `
  --commit `
  --organization-id 00000000-0000-4000-8000-000000000000 `
  --source-id 00000000-0000-4000-8000-000000000000
```

`--organization-id` и `--source-id` обязательны для записи. Access token должен
принадлежать активному owner/admin/producer этой организации; service role для
CLI запрещён. CLI отправляет только контракт `parse_and_import` с category из
манифеста, `adapter=auto` и детерминированным UUID idempotency key. Массив
`cases` из локального манифеста в сеть не отправляется: сервер заново скачивает
и разбирает зарегистрированный файл, проверяет его имя, размер и SHA-256, а
затем валидирует каждую нормализованную строку. Поэтому `--commit` импортирует
состояние зарегистрированного источника, а не ручные изменения JSON-манифеста.

## Правила классификации

- Категория задаётся для каждого кейса. Верхнеуровневая категория — только
  контекст/значение по умолчанию для источника.
- Товар связывается только по точному внутреннему `product_sku`, прямому
  `product_id` или однозначному точному совпадению marketplace-артикула с
  `current_wb_article`. Fuzzy/category-wide догадки запрещены; если передано
  несколько ссылок на товар, каждая обязана разрешиться в один и тот же товар,
  иначе строка уходит в карантин.
- Метрики — только числа с короткими snake_case-ключами; текстовые пояснения,
  действия и содержимое публикаций не импортируются.
- Недостаточная выборка, данные вне окна, конфликт сопоставления или неизвестная
  категория должны иметь `outcome=review` и соответствующее измерение
  `data_quality`/`attribution`.

Актуальная JSON Schema и шаблон находятся в
`data/ai-historical-cases/`.

## Production-парсер загруженного файла

Основной путь в интерфейсе — authenticated Edge Function
`creator-ai-case-import`. Она не принимает локальный путь и не получает файл
из тела запроса: сервер находит уже зарегистрированный `source_id`, повторно
проверяет организацию/category/права, скачивает объект из закрытого bucket
`contentengine-knowledge` и сам вычисляет SHA-256.

```json
{
  "action": "parse_and_import",
  "organization_id": "00000000-0000-4000-8000-000000000000",
  "source_id": "00000000-0000-4000-8000-000000000000",
  "product_category": "other",
  "adapter": "auto",
  "commit": true,
  "idempotency_key": "00000000-0000-4000-8000-000000000000"
}
```

Поддержаны три версии адаптера:

- Harley: `Эффект_контента`, строка заголовков 6; 18 строк конкретной
  Instagram→Wildberries выборки превращаются в good/bad/review без URL, хуков и
  текста публикаций. Кейсы получают категорию зарегистрированного источника;
  allowlisted контентный угол сохраняется и у `bad`, чтобы подтверждение могло
  научить ИИ не повторять неудачный подход.
- QEEP: первичный лист `SKU_итог`, пороги из `Пороги`, а `WB_воронка` и
  `Ozon_воронка` служат независимой сверкой; один mixed workbook сохраняет
  категорию каждого SKU (`baa`, `sports_food`, `cosmetics`, `food`).
- Canonical CSV/XLSX: только поля v1 и колонки `metric_*`; неизвестные колонки
  и формулы запрещены.

XLSX проходит ZIP preflight до разбора: 25 MB, ограниченное число entries,
листов/строк/колонок/ячеек и суммарный распакованный размер; запрещены
шифрование, ZIP64, macros/VBA, external links, binary entries, traversal и
опасные/volatile формулы. Закреплён SheetJS 0.20.3. Формулы никогда не
исполняются. В известных Harley/QEEP шаблонах разрешён только сохранённый
cached scalar; производные KPI и статус заново сверяются с исходными числами и
порогами. Canonical-формат не принимает формулы вообще.

Каждый RPC batch несёт собственный `parsed_row_count`; parser quarantine
назначается только одному пакету (обычно первому), поэтому сумма lineage по всем
пакетам равна числу строк источника без двойного счёта. Пакет содержит максимум
100 кейсов. Если все строки отклонены парсером, пустой batch всё равно
аудиторски сохраняется и возвращает `parser_rejected_all`, `retryable=true` и
`batch_persisted=true`. Ответ включает `parsed`, `imported`, `matched`,
parser/database quarantine, `per_category`, хеши и authoritative snapshot
ИИ-центра.
Каждый SQL receipt содержит `replayed`: Edge считает «добавлено» только для
свежих физических пакетов. Повтор уже сохранённого пакета возвращает тот же
authoritative batch, но не изображает повторную вставку в UI.
Логический manifest дополнительно фиксирует `parsed_row_count` и сводку причин
parser quarantine. Поэтому изменение даже отклонённых строк/причин даёт новый
receipt, а повтор незавершённого multi-batch импорта остаётся стабильным при
изменениях каталога товаров.

Локальные проверки Edge:

```powershell
npx -y deno@2.8.1 fmt --check supabase/functions/creator-ai-case-import
npx -y deno@2.8.1 lint supabase/functions/creator-ai-case-import
npx -y deno@2.8.1 check --allow-import=cdn.sheetjs.com `
  supabase/functions/creator-ai-case-import/index.ts `
  supabase/functions/creator-ai-case-import/index_test.ts
npx -y deno@2.8.1 test --allow-import=cdn.sheetjs.com `
  supabase/functions/creator-ai-case-import/index_test.ts
```

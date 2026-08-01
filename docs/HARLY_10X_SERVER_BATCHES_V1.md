# Harly 10× Server Batches v1

## Зачем

Первый Harly‑пилот больше не должен существовать как браузерный черновик или
таблица на десять строк. Сервер фиксирует всю причинную цепочку:

`5 принадлежащих бренду видео → 10 назначений → первые 2 результата → QA → ещё 8 → завершение`.

Эта версия создаёт authority для плана, прав на исходник, стоимости, состояния
внешней операции и решения человека. Она **не вызывает провайдера сама**.

## Жёсткая матрица первой версии

- ровно 5 исходных видео;
- каждый исходник относится к одному точному товару;
- каждый исходник имеет статус `owned` или `licensed`;
- права и исходный QA подтверждены owner/admin/producer;
- целевой язык отличается от языка исходника;
- на каждый исходник создаются:
  - версия с субтитрами;
  - версия с дубляжом без lip-sync;
- итого ровно 10 уникальных assignments;
- последовательности 1–2 — wave 1;
- последовательности 3–10 остаются `planned`, пока человек не примет wave 1.

Lip-sync уже существует как отдельный тип и rate-card capability, но не входит
в автоматическую матрицу Harly 5×2. Он станет отдельным premium-пакетом после
проверки дешёвых версий.

## Таблицы

### `video_source_approvals`

Снимок допуска конкретного `media_object`:

- exact product;
- SHA-256 исходного файла;
- owned/licensed relationship;
- язык и длительность;
- наличие речи и встроенного текста;
- rights confirmation;
- source QA;
- кто и когда одобрил;
- отзыв допуска через `revoked`.

Изменение файла после допуска ломает проверку SHA и не позволяет создать новый
batch по старому approval.

### `video_localization_batches`

Immutable planning snapshot:

- точный product;
- target language;
- десять outputs;
- QA gate после двух;
- versioned rate card;
- plan hash;
- estimated cost;
- baseline полной Seedance-генерации;
- idempotency key;
- status/version.

Одновременно для одного товара нельзя создать второй незавершённый batch.

### `video_localization_assignments`

Каждая версия имеет собственные:

- source media ID и source SHA;
- mode/provider;
- source/target language;
- sequence/wave;
- deterministic assignment hash;
- estimated/actual cost;
- output media ID;
- status/failure code;
- флаг обязательной ручной правки встроенного текста.

### `video_localization_qa_decisions`

Wave 2 открывается только после двух `succeeded` outputs и заполненного
чек-листа:

- product fidelity;
- language quality;
- no common defect;
- rights OK.

Отрицательное решение не удаляет факты: batch переходит в `paused`, оставшиеся
восемь assignments — в `blocked`.

### Private provider operations

`content_factory_private.video_localization_provider_operations` — доверенный
receipt внешней операции:

- один assignment → одна операция;
- exact idempotency key и request hash;
- зарезервированная стоимость;
- hash provider task reference вместо raw provider ID;
- actual cost;
- `reserved / submitted / processing / settled / released / frozen / failed`.

Browser не имеет доступа к таблице и system RPC.

## State machine

```text
ready
  → reserved
  → submitted
  → processing
  → succeeded
```

Допустимы безопасные отклонения:

```text
reserved → released → reserved
submitted/processing → failed
reserved/submitted/processing → unknown → frozen
```

`unknown` означает неопределённый исход внешнего POST. В этом состоянии:

- текущий assignment становится `unknown`;
- provider receipt становится `frozen`;
- batch ставится на паузу;
- оставшиеся `ready/planned` блокируются;
- автоматический повтор запрещён.

Одновременно в batch может быть только один `reserved/submitted/processing`
assignment. Это не даёт двум worker-ам запустить параллельные оплаты.

## Стоимость

Rate card `2026-08-01.public-provider-rate-card.v2` хранится внутри batch:

- internal captions envelope — 50,000 micro‑USD/min;
- ElevenLabs dubbing — 500,000 micro‑USD/min;
- HeyGen audio/speed lip-sync — 33,300 micro‑USD/sec;
- HeyGen precision lip-sync — 66,700 micro‑USD/sec;
- Seedance baseline — 290,000 micro‑USD/sec.

Rate card — planning snapshot, не invoice. Actual cost появляется только из
service-side receipt.

## Безопасность данных

В таблицах отсутствуют:

- raw URL;
- caption;
- transcript;
- prompt;
- чужое лицо, музыка, слоган или текст страницы;
- provider secret или raw provider task ID.

Источник и результат ссылаются только на закрытые `media_objects`. Внешние
идентификаторы сохраняются как SHA-256.

## Что уже можно после этого PR

- выбрать пять файлов Harly в Finder;
- подтвердить права и точный товар;
- получить immutable план на десять outputs и точный cost preview;
- безопасно выполнять assignments последовательно;
- остановиться после первых двух;
- принять или отклонить wave 1;
- при timeout не допустить повторной оплаты;
- связать готовый output с тем же товаром и assignment.

## Что ещё не входит

- Edge Function/provider adapter;
- автоматическая транскрибация;
- перевод текста;
- SRT/VTT и burn-in;
- ElevenLabs/HeyGen вызовы;
- автоматический upload итогового MP4;
- UI batch-панели в «Создании»;
- публикация и mature performance outcome;
- promotion результата в learning policy.

Следующий порядок:

1. internal captions pipeline;
2. dubbing adapter;
3. UI в существующем рабочем столе «Создание»;
4. два тестовых outputs Harly;
5. human QA;
6. ещё восемь;
7. публикация и outcome binding к server learning policy.

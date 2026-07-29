const REAL_MODES = new Set(["real_gen4", "real_seedance", "real_photo"]);

export function evaluateGenerationFormReadiness(value = {}) {
  const mode = String(value.mode || "mock");
  const real = REAL_MODES.has(mode);
  const photo = mode === "real_photo";
  const mediaCount = Math.max(0, Number(value.mediaCount) || 0);
  const count = Number(value.count);
  const maxMockCount = Math.max(1, Number(value.maxMockCount) || 10);
  const steps = [
    step(
      "product",
      "Точный товар",
      Boolean(clean(value.sku) && clean(value.productName)),
      "Укажите артикул и точное название товара.",
    ),
    step(
      "destination",
      "Место публикации",
      Boolean(clean(value.platform) && clean(value.destinationRef).length >= 2),
      "Выберите площадку и укажите точный аккаунт, канал или карточку.",
    ),
    step(
      "media",
      "Фото и ракурсы товара",
      real ? mediaCount >= 1 && mediaCount <= 5 : mediaCount >= 1,
      real && mediaCount > 5
        ? "Оставьте до пяти ракурсов одного и того же товара."
        : "Выберите от одного до пяти точных фото товара ниже.",
    ),
  ];

  if (real) {
    steps.push(
      step(
        "category",
        "Категория товара",
        Boolean(clean(value.productCategory)),
        "Один раз выберите категорию товара для правил QA и обязательных предупреждений.",
      ),
      step(
        "brief",
        photo ? "Композиция" : "Сценарий",
        Boolean(clean(value.brief)),
        photo
          ? "Опишите фон, свет и композицию; потребуйте сохранить точную упаковку и текст."
          : "Опишите один ролик и главную мысль без неподтверждённых обещаний.",
      ),
      step(
        "safe_brief",
        "Проверенное авто-ТЗ",
        value.safeBriefReady === true,
        clean(value.safeBriefHint)
          || "Дождитесь бесплатной проверки авто-ТЗ для выбранной категории, модели и длительности.",
      ),
      step(
        "budget",
        "Бюджет кампании",
        Boolean(clean(value.campaignId) && value.spendAllowed === true),
        clean(value.campaignId)
          ? "Обновите остаток или выберите кампанию с доступным лимитом."
          : "Выберите активную кампанию.",
      ),
      step(
        "confirmation",
        "Подтверждение стоимости",
        value.confirmationMatches === true,
        photo
          ? "Подтвердите создание одного платного фото."
          : "Подтвердите создание одного платного видео.",
      ),
    );
  } else {
    steps.push(
      step(
        "count",
        "Количество dry-run задач",
        Number.isInteger(count) && count >= 1 && count <= maxMockCount,
        `Укажите от 1 до ${maxMockCount} задач без медиафайлов.`,
      ),
    );
  }

  const completed = steps.filter((item) => item.complete).length;
  const next = steps.find((item) => !item.complete) || null;
  const safeBriefState = clean(value.safeBriefState)
    .toLowerCase()
    .replace(/[^a-z0-9_]/gu, "")
    .slice(0, 32);
  const signature = [
    ...steps.map((item) => `${item.key}:${item.complete ? 1 : 0}`),
    ...(real ? [`safe_state:${safeBriefState || "pending"}`] : []),
  ].join("|");
  return {
    real,
    ready: next === null,
    completed,
    total: steps.length,
    next,
    steps,
    signature,
  };
}

export function generationReadinessMarkup(evaluation = {}) {
  const steps = Array.isArray(evaluation.steps) ? evaluation.steps : [];
  const completed = Math.max(0, Number(evaluation.completed) || 0);
  const total = Math.max(steps.length, Number(evaluation.total) || 0);
  const ready = evaluation.ready === true;
  const next = evaluation.next || steps.find((item) => !item.complete) || null;
  const signature = String(evaluation.signature || "");
  return `
    <aside class="generation-readiness" id="generation-readiness" data-ready="${ready ? "true" : "false"}" data-signature="${signature}" role="status" aria-live="polite" aria-atomic="false">
      <div class="generation-readiness__header">
        <div>
          <p class="eyebrow">Готовность запуска</p>
          <strong data-generation-readiness-title>${ready ? (evaluation.real ? "Можно запускать" : "Можно создать dry-run") : `Следующий шаг: ${next?.label || "заполните форму"}`}</strong>
          <small data-generation-readiness-next>${ready ? (evaluation.real ? "Все обязательные данные проверены." : "Будут созданы задачи без фото или видео.") : (next?.hint || "Заполните обязательные поля.")}</small>
        </div>
        <span class="generation-readiness__count">${completed} из ${total}</span>
      </div>
      <ol class="generation-readiness__steps">
        ${steps.map((item, index) => `
          <li data-step="${item.key}" data-complete="${item.complete ? "true" : "false"}">
            <i aria-hidden="true">${item.complete ? "✓" : index + 1}</i>
            <span><strong>${item.label}</strong><small>${item.complete ? "Готово" : item.hint}</small></span>
          </li>
        `).join("")}
      </ol>
    </aside>
  `;
}

function step(key, label, complete, hint) {
  return { key, label, complete: complete === true, hint };
}

function clean(value) {
  return String(value ?? "").trim();
}

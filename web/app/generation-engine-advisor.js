/*
 * ИИ-центр: совет по движку «Копии».
 *
 * Единственное общее место у раздельных движков — этот совет. Движки живут
 * отдельными строками реестра (content_factory.generation_strategy_provider_
 * routes) и ничего друг о друге не знают; советчик читает их свойства
 * (семейство, профиль входа, цену, окно длительности) и факты о конкретном
 * запуске — длительность и размер исходника, число фото товара, категорию,
 * замысел из разбора — и называет один движок с причинами, запасные варианты
 * и то, что отсеяно и почему.
 *
 * Совет — подсказка, не приговор: экран предлагает его по умолчанию, а человек
 * может выбрать любой другой включённый движок до бесплатной проверки. Модуль
 * чистый: ни DOM, ни сети, ни состояния — его можно исполнить в Node и
 * проверить таблицей случаев.
 */

export const GENERATION_ENGINE_ADVISOR_VERSION = "generation-engine-advisor-v1";

// Признаки крупного или сложного объекта: такой товар правится по нескольким
// ракурсам, одного фото для точного артикула не хватает.
const LARGE_OBJECT_SIGNAL =
  /(?:\b(?:grill|barbecue|bbq|rotisserie|cart|furniture|sofa|chair|table|cabinet|appliance|machine|stroller|bike|bicycle|scooter|tent|treadmill)\b|мангал|грил|мебел|диван|кресл|стол|шкаф|коляск|велосипед|самокат|палатк|тренаж|кофемашин|машин|плит|холодильник|стирал|пылесос)/iu;
// Признаки, что кадр живёт сам по себе: быстрый монтаж, ручная камера,
// несколько планов. Редактор такое удерживает, пересборщик — нет.
const DYNAMIC_SCENE_SIGNAL =
  /(?:\b(?:handheld|fast cuts|quick cuts|multiple shots|many shots|whip|tracking|dolly|orbit)\b|быстр(?:ый|ые) (?:монтаж|склейк)|ручн(?:ая|ой) камер|много планов|несколько планов|облёт|проезд|трекинг)/iu;

function text(value, limit) {
  return typeof value === "string" ? value.trim().slice(0, limit) : "";
}

function positive(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function estimateCostMinor(route, durationSeconds) {
  if (route.priceKind === "usd_minor_per_run" && route.priceRateMinor) {
    return route.priceRateMinor;
  }
  if (route.priceKind === "usd_minor_per_second" && route.priceRateMinor) {
    const seconds = durationSeconds ?? 5;
    return route.priceRateMinor * seconds;
  }
  // Ступени кредитов Runway считает только сервер; для сравнения берётся
  // известная ступень: 10 секунд ≈ $4.28, дальше по секундам.
  if (route.priceKind === "runway_credit_tiers") {
    const seconds = durationSeconds ?? 5;
    return Math.round(428 * Math.max(seconds, 4) / 10);
  }
  return null;
}

function usd(minor) {
  return `$${(minor / 100).toFixed(2)}`;
}

function normalizeRoute(route) {
  if (!route || typeof route !== "object") return null;
  const id = text(route.id, 200);
  if (!id || route.enabled !== true) return null;
  const profile = route.inputProfile && typeof route.inputProfile === "object"
    ? route.inputProfile
    : null;
  return {
    id,
    label: text(route.label, 80) || id,
    family: ["edit", "regenerate", "overlay"].includes(route.engineFamily)
      ? route.engineFamily
      : "edit",
    tier: text(route.tier, 20),
    priceKind: text(route.priceKind, 40),
    priceRateMinor: positive(route.priceRateMinor),
    minDuration: positive(route.minDurationSeconds),
    maxDuration: positive(route.maxDurationSeconds),
    durationSource: route.durationSource === "operator_choice"
      ? "operator_choice"
      : "source_video",
    // Окно референса из профиля входа: у пересборщиков (MiniMax) оно про
    // ВХОДНОЕ видео, а min/maxDuration реестра — про выход, который выбирает
    // оператор. Исходник длиннее окна референса модель отвергнет.
    referenceMin: profile ? positive(profile.video?.min_seconds) : null,
    referenceMax: profile ? positive(profile.video?.max_seconds) : null,
    imagesMax: profile ? Number(profile.images?.max) : null,
    minShortSide: profile ? positive(profile.video?.min_short_side_px) : null,
    keepsAudio: profile ? profile.keeps_source_audio === true : null,
    recommended: route.recommended === true,
  };
}

/*
 * routes — движки стратегии в форме engineRoutesFor() экрана (id, label,
 *   tier, priceKind, priceRateMinor, min/maxDurationSeconds, durationSource,
 *   engineFamily, inputProfile, recommended, enabled).
 * facts — что известно о запуске:
 *   sourceDurationSeconds — измеренная сервером длительность исходника, либо null;
 *   requestedDurationSeconds — длительность, выбранная оператором (для движков,
 *     у которых её выбирает он: «Создание», MiniMax), либо null;
 *   sourceShortSidePx — короткая сторона исходника в пикселях, либо null;
 *   productImageCount — сколько фото товара выбрано (0 — ещё не выбраны);
 *   productCategory — категория товара из формы;
 *   brief — замысел / совет ИИ-центра по копии (свободный текст);
 *   budgetMinorPerRun — потолок одного запуска в центах, либо null.
 */
export function adviseGenerationEngine({ routes, facts } = {}) {
  const candidates = (Array.isArray(routes) ? routes : [])
    .map(normalizeRoute)
    .filter(Boolean);
  const duration = positive(facts?.sourceDurationSeconds);
  const seconds = duration === null ? null : Math.ceil(duration);
  const requested = positive(facts?.requestedDurationSeconds);
  const requestedSeconds = requested === null ? null : Math.ceil(requested);
  const shortSide = positive(facts?.sourceShortSidePx);
  const imageCount = Math.max(0, Math.trunc(Number(facts?.productImageCount) || 0));
  const category = text(facts?.productCategory, 40).toLowerCase();
  const brief = text(facts?.brief, 2_000);
  const budget = positive(facts?.budgetMinorPerRun);
  const signalText = `${category} ${brief}`;
  const wantsAngles = imageCount >= 3 || LARGE_OBJECT_SIGNAL.test(signalText);
  const dynamicScene = DYNAMIC_SCENE_SIGNAL.test(brief);

  const excluded = [];
  const fitting = [];
  const editAvailable = candidates.some((route) => route.family === "edit");
  for (const route of candidates) {
    // Сколько секунд оплатится: у правки видео — длина исходника, у движков с
    // выбором оператора — выбранная длительность.
    const billable = route.durationSource === "operator_choice"
      ? (requestedSeconds ?? seconds)
      : seconds;
    const cost = estimateCostMinor(route, billable);
    if (
      requestedSeconds !== null && route.durationSource === "operator_choice" &&
      ((route.maxDuration !== null && requestedSeconds > route.maxDuration) ||
        (route.minDuration !== null && requestedSeconds < route.minDuration))
    ) {
      excluded.push({
        engineId: route.id,
        reason: `выбрано ${requestedSeconds} с, а движок делает ${route.minDuration ?? 1}–${route.maxDuration ?? "…"} с`,
      });
      continue;
    }
    if (
      seconds !== null && route.durationSource === "source_video" &&
      ((route.maxDuration !== null && seconds > route.maxDuration) ||
        (route.minDuration !== null && seconds < route.minDuration))
    ) {
      excluded.push({
        engineId: route.id,
        reason: `исходник ${seconds} с, а движок принимает ${route.minDuration ?? 1}–${route.maxDuration ?? "…"} с`,
      });
      continue;
    }
    if (
      seconds !== null && route.durationSource === "operator_choice" &&
      route.referenceMax !== null && seconds > route.referenceMax
    ) {
      excluded.push({
        engineId: route.id,
        reason: `исходник ${seconds} с, а референс для этого движка не длиннее ${route.referenceMax} с`,
      });
      continue;
    }
    if (shortSide !== null && route.minShortSide !== null && shortSide < route.minShortSide) {
      excluded.push({
        engineId: route.id,
        reason: `исходник ${shortSide}px по короткой стороне, движку нужно от ${route.minShortSide}px`,
      });
      continue;
    }
    if (budget !== null && cost !== null && cost > budget) {
      excluded.push({
        engineId: route.id,
        reason: `≈${usd(cost)} за запуск при потолке ${usd(budget)}`,
      });
      continue;
    }
    fitting.push({ route, cost });
  }

  if (!fitting.length) {
    return Object.freeze({
      version: GENERATION_ENGINE_ADVISOR_VERSION,
      engineId: null,
      reasons: Object.freeze([
        "ни один включённый движок не подходит под этот исходник и бюджет",
      ]),
      alternatives: Object.freeze([]),
      excluded: Object.freeze(excluded),
      basis: Object.freeze({ seconds, requestedSeconds, shortSide, imageCount, wantsAngles, dynamicScene, budget }),
    });
  }

  // Оценка: редакторы сохраняют кадр — они впереди пересборщиков всегда, пока
  // хоть один из них подходит. Среди редакторов: ракурсы важнее цены, если
  // товар крупный или фото несколько; дальше — дешевле лучше. Премиальная
  // пересборка с сохранением камеры (Seedance) — только запасной вариант.
  const scored = fitting.map(({ route, cost }) => {
    let score = 0;
    const reasons = [];
    if (route.family === "edit") {
      score += 1_000;
      reasons.push("правит кадр исходника, движение и монтаж остаются");
    } else if (route.family === "regenerate") {
      reasons.push(editAvailable
        ? "пересобирает ролик заново — движение будет похожим, не тем же"
        : "собирает ролик с нуля по фото товара и замыслу");
    }
    const images = Number.isFinite(route.imagesMax) ? route.imagesMax : 0;
    if (wantsAngles) {
      if (images >= 4) {
        score += 300;
        reasons.push(`берёт до ${images} фото — крупный товар лучше держится по нескольким ракурсам`);
      } else if (images === 1) {
        score -= 200;
        reasons.push("принимает одно фото — для крупного товара этого мало");
      }
    } else if (images === 1) {
      score += 50;
      reasons.push("одного фото достаточно: товар небольшой");
    }
    if (dynamicScene && route.family === "edit" && images >= 4) {
      score += 100;
      reasons.push("сцена динамичная — редактор с несколькими ракурсами удержит товар в движении");
    }
    if (route.tier === "premium") {
      score -= 400;
      reasons.push("дорогой уровень — только если остальные не справились");
    }
    if (cost !== null) {
      // Чем дешевле, тем выше: 1 балл за каждый цент ниже $5.
      score += Math.max(0, 500 - cost) / 5;
      const billableSeconds = route.durationSource === "operator_choice"
        ? (requestedSeconds ?? seconds ?? 5)
        : (seconds ?? 5);
      reasons.push(
        route.priceKind === "usd_minor_per_run"
          ? `${usd(cost)} за ролик целиком`
          : `≈${usd(cost)} за ${billableSeconds} с`,
      );
    }
    if (route.keepsAudio === true) reasons.push("звук исходника сохраняется");
    return { route, cost, score, reasons };
  }).sort((left, right) => right.score - left.score || (left.cost ?? 0) - (right.cost ?? 0));

  const best = scored[0];
  const alternatives = scored.slice(1, 3).map((item) => ({
    engineId: item.route.id,
    reason: item.reasons.slice(0, 2).join(" · "),
  }));
  return Object.freeze({
    version: GENERATION_ENGINE_ADVISOR_VERSION,
    engineId: best.route.id,
    reasons: Object.freeze(best.reasons.slice(0, 4)),
    alternatives: Object.freeze(alternatives),
    excluded: Object.freeze(excluded),
    basis: Object.freeze({ seconds, requestedSeconds, shortSide, imageCount, wantsAngles, dynamicScene, budget }),
  });
}

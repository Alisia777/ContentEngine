const TRACK_STORAGE_PREFIX = "contentengine.learning-track.v1";
const LESSON_STORAGE_PREFIX = "contentengine.lesson-journey.v2";
const ACHIEVEMENT_STORAGE_PREFIX = "contentengine.course-achievement.v1";

export const LEARNING_TRACKS = Object.freeze({
  all: Object.freeze({
    id: "all",
    shortLabel: "Пока не знаю",
    title: "Сначала разберитесь во всём маршруте",
    description: "Покажем общий путь без профессионального уклона. Выбор можно изменить в любой момент.",
    focus: "товар → производство → проверка → публикация → выплата",
    optionalTitle: "Полная учебная смена",
    optionalHref: "#/learn/first-shift",
  }),
  self: Object.freeze({
    id: "self",
    shortLabel: "Снимаю сам",
    title: "Ваш акцент — снять точный товар на телефон",
    description: "Особенно внимательно пройдите подготовку товара, вертикальный кадр 9:16 и проверку качества перед передачей.",
    focus: "задание → товар → съёмка → проверка → передача",
    optionalTitle: "Репетиция полной смены",
    optionalHref: "#/learn/first-shift",
  }),
  ai: Object.freeze({
    id: "ai",
    shortLabel: "Создаю с ИИ",
    title: "Ваш акцент — сохранить товар узнаваемым",
    description: "Сверяйте упаковку и артикул, собирайте точное задание для генерации и отклоняйте ролик, если товар искажён.",
    focus: "исходники → задание ИИ → генерация → проверка → передача",
    optionalTitle: "Репетиция полной смены",
    optionalHref: "#/learn/first-shift",
  }),
  publish: Object.freeze({
    id: "publish",
    shortLabel: "Публикую",
    title: "Ваш акцент — безопасно разместить одобренный ролик",
    description: "Разберите запуск аккаунта, правила площадок, рекламную проверку, фиксацию ссылки и передачу результата.",
    focus: "одобрение → площадка → публикация → ссылка → метрики",
    optionalTitle: "Центр запуска аккаунтов",
    optionalHref: "#/learn/account-launch",
  }),
  review: Object.freeze({
    id: "review",
    shortLabel: "Проверяю ролики",
    title: "Ваш акцент — найти риск до передачи или публикации",
    description: "Сверяйте точный товар, смотрите весь файл, проверяйте права и обещания и возвращайте воспроизводимую причину доработки.",
    focus: "товар → полный просмотр → права и факты → решение → доказательство",
    optionalTitle: "Репетиция полной смены",
    optionalHref: "#/learn/first-shift",
  }),
});

export const COURSE_ACHIEVEMENTS = Object.freeze({
  factory_basics: Object.freeze({
    icon: "✦",
    name: "Навигатор портала",
    description: "Вы знаете путь товара от задания до подтверждённого результата.",
  }),
  video_quality: Object.freeze({
    icon: "◉",
    name: "Создатель ролика",
    description: "Вы умеете подготовить, создать и проверить вертикальный ролик.",
  }),
  publishing_funnel: Object.freeze({
    icon: "↗",
    name: "Безопасная публикация",
    description: "Вы знаете, когда публикацию можно выпускать и что вернуть в портал.",
  }),
  security_wb: Object.freeze({
    icon: "◆",
    name: "Контроль товара и выплаты",
    description: "Вы умеете сверить артикул, сумму, статус и остановить рискованную задачу.",
  }),
});

function cleanPart(value) {
  return encodeURIComponent(String(value ?? "").trim());
}

function scopedKey(prefix, parts) {
  const normalized = parts.map((value) => String(value ?? "").trim());
  if (normalized.some((value) => !value)) return null;
  return `${prefix}:${normalized.map(cleanPart).join(":")}`;
}

export function normalizeLearningTrack(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return Object.hasOwn(LEARNING_TRACKS, normalized) ? normalized : "all";
}

export function roleAwareLessonPath(moduleCode, rawLessons, rawGroups, trackValue) {
  const selectedTrack = normalizeLearningTrack(trackValue);
  const lessons = (Array.isArray(rawLessons) ? rawLessons : []).map((lesson, index) => {
    const audiences = (Array.isArray(lesson?.audiences) ? lesson.audiences : ["all"])
      .map((value) => normalizeLearningTrack(value))
      .filter(Boolean);
    return {
      ...lesson,
      id: String(lesson?.id || `${moduleCode}-lesson-${index + 1}`),
      audiences: audiences.length ? [...new Set(audiences)] : ["all"],
      phase: String(lesson?.phase || "reference"),
      platform: String(lesson?.platform || ""),
      requiredCore: lesson?.required_core !== false,
    };
  });
  const byId = new Map(lessons.map((lesson) => [lesson.id, lesson]));
  const groups = (Array.isArray(rawGroups) ? rawGroups : [])
    .map((group, index) => ({
      id: String(group?.id || `group-${index + 1}`),
      title: String(group?.title || `Этап ${index + 1}`),
      lessonIds: (Array.isArray(group?.lesson_ids) ? group.lesson_ids : [])
        .map(String)
        .filter((id) => byId.has(id)),
    }))
    .filter((group) => group.lessonIds.length);
  const groupByLessonId = new Map();
  groups.forEach((group) => group.lessonIds.forEach((id) => groupByLessonId.set(id, group)));
  const used = new Set();
  const ordered = [];
  groups.forEach((group) => group.lessonIds.forEach((id) => {
    if (used.has(id)) return;
    used.add(id);
    ordered.push(byId.get(id));
  }));
  lessons.forEach((lesson) => {
    if (used.has(lesson.id)) return;
    used.add(lesson.id);
    ordered.push(lesson);
  });
  const recommendedLessonIds = ordered
    .filter((lesson) => (
      selectedTrack === "all"
      || lesson.requiredCore
      || lesson.audiences.includes("all")
      || lesson.audiences.includes(selectedTrack)
    ))
    .map((lesson) => lesson.id);
  const recommended = new Set(recommendedLessonIds);
  let previousGroupId = "";
  return {
    allLessons: ordered,
    lessons: ordered.map((lesson) => {
      const group = groupByLessonId.get(lesson.id) || null;
      const groupStart = Boolean(group && group.id !== previousGroupId);
      if (group) previousGroupId = group.id;
      return {
        ...lesson,
        trackRecommended: recommended.has(lesson.id),
        groupId: group?.id || "",
        groupTitle: group?.title || "",
        groupStart,
      };
    }),
    recommendedLessonIds,
    groups,
  };
}

export function learningTrackStorageKey(userId) {
  return scopedKey(TRACK_STORAGE_PREFIX, [userId]);
}

export function lessonJourneyStorageKey(userId, courseCode, curriculumVersion = 1) {
  return scopedKey(LESSON_STORAGE_PREFIX, [userId, courseCode, `curriculum-${curriculumVersion}`]);
}

export function achievementStorageKey(userId, courseCode) {
  return scopedKey(ACHIEVEMENT_STORAGE_PREFIX, [userId, courseCode]);
}

function lessonCatalog(lessonsOrTotal) {
  if (Array.isArray(lessonsOrTotal)) {
    const seen = new Set();
    return lessonsOrTotal.map((lesson, index) => {
      const base = String(lesson?.id || `lesson-${index + 1}`).trim() || `lesson-${index + 1}`;
      let id = base;
      let suffix = 2;
      while (seen.has(id)) {
        id = `${base}-${suffix}`;
        suffix += 1;
      }
      seen.add(id);
      return id;
    });
  }
  const total = Math.max(0, Math.trunc(Number(lessonsOrTotal) || 0));
  return Array.from({ length: total }, (_, index) => `lesson-${index + 1}`);
}

export function normalizeLessonJourney(raw, lessonsOrTotal) {
  const lessonIds = lessonCatalog(lessonsOrTotal);
  const total = lessonIds.length;
  const source = raw && typeof raw === "object" ? raw : {};
  const requestedActiveId = String(source.activeLessonId || "").trim();
  const activeById = lessonIds.indexOf(requestedActiveId);
  const activeIndex = total ? (
    activeById >= 0
      ? activeById
      : Math.max(0, Math.min(total - 1, Math.trunc(Number(source.activeIndex) || 0)))
  ) : 0;
  const understoodById = (Array.isArray(source.understoodLessonIds) ? source.understoodLessonIds : [])
    .map((value) => lessonIds.indexOf(String(value || "").trim()))
    .filter((value) => value >= 0);
  const understood = [...new Set(
    (understoodById.length ? understoodById : Array.isArray(source.understood) ? source.understood : [])
      .map((value) => Math.trunc(Number(value)))
      .filter((value) => Number.isInteger(value) && value >= 0 && value < total),
  )].sort((left, right) => left - right);
  return {
    activeIndex,
    understood,
    activeLessonId: lessonIds[activeIndex] || "",
    understoodLessonIds: understood.map((index) => lessonIds[index]),
  };
}

export function reduceLessonJourney(current, event, lessonsOrTotal) {
  const normalized = normalizeLessonJourney(current, lessonsOrTotal);
  const total = lessonCatalog(lessonsOrTotal).length;
  const type = String(event?.type || "open");
  const requestedIndex = Math.trunc(Number(event?.index));
  const index = total
    ? Math.max(0, Math.min(total - 1, Number.isFinite(requestedIndex) ? requestedIndex : normalized.activeIndex))
    : 0;
  const understood = new Set(normalized.understood);
  if (type === "understand") understood.add(index);
  if (type === "reopen") understood.delete(index);
  const moveNext = type === "understand" && event?.moveNext === true && index < total - 1;
  return normalizeLessonJourney({
    activeIndex: moveNext ? index + 1 : index,
    understood: [...understood],
  }, lessonsOrTotal);
}

export function lessonJourneyPercent(journey, lessonsOrTotal) {
  const total = lessonCatalog(lessonsOrTotal).length;
  if (!total) return 0;
  return Math.round((normalizeLessonJourney(journey, lessonsOrTotal).understood.length / total) * 100);
}

export function courseAchievement(courseCode) {
  return COURSE_ACHIEVEMENTS[String(courseCode || "")] || Object.freeze({
    icon: "✦",
    name: "Блок освоен",
    description: "Результат подтверждён и сохранён в вашем учебном профиле.",
  });
}

export function shouldCelebrateCourse({ wasCompleted, serverCompleted, alreadyCelebrated }) {
  return wasCompleted !== true && serverCompleted === true && alreadyCelebrated !== true;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function achievementMarkup(courseCode, override = {}) {
  const fallback = courseAchievement(courseCode);
  const source = override && typeof override === "object" ? override : {};
  const achievement = {
    icon: String(source.icon || fallback.icon).slice(0, 8),
    name: String(source.name || source.title || fallback.name).slice(0, 120),
    description: String(source.description || fallback.description).slice(0, 420),
  };
  const petals = Array.from({ length: 14 }, (_, index) => `<i style="--petal:${index}" aria-hidden="true"></i>`).join("");
  return `
    <section class="training-achievement" data-training-achievement data-course-code="${escapeHtml(courseCode)}" role="dialog" aria-modal="true" aria-labelledby="training-achievement-title" aria-describedby="training-achievement-description">
      <div class="training-achievement__petals" aria-hidden="true">${petals}</div>
      <div class="training-achievement__card">
        <p class="eyebrow">Новая ачивка</p>
        <div class="training-achievement__badge" aria-hidden="true"><span>${escapeHtml(achievement.icon)}</span></div>
        <p class="training-achievement__kicker">Блок завершён и сохранён</p>
        <h2 id="training-achievement-title">${escapeHtml(achievement.name)}</h2>
        <p id="training-achievement-description">${escapeHtml(achievement.description)}</p>
        <div class="training-achievement__actions">
          <button class="btn" type="button" data-action="close-training-achievement">Продолжить обучение <span aria-hidden="true">→</span></button>
          <button class="btn btn-secondary" type="button" data-action="play-training-fanfare"><span aria-hidden="true">♫</span> Сыграть фанфары</button>
        </div>
        <p class="training-achievement__note">Звук включается только по вашему нажатию. Учебная ачивка не заменяет итоговый экзамен, сертификацию или назначение рабочей роли.</p>
      </div>
    </section>
  `;
}

export function playTrainingFanfare() {
  const AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext;
  if (!AudioContextClass) return false;
  const context = new AudioContextClass();
  const gain = context.createGain();
  gain.gain.setValueAtTime(0.0001, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.16, context.currentTime + 0.03);
  gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 1.05);
  gain.connect(context.destination);
  [523.25, 659.25, 783.99, 1046.5].forEach((frequency, index) => {
    const oscillator = context.createOscillator();
    oscillator.type = index === 3 ? "triangle" : "sine";
    oscillator.frequency.value = frequency;
    oscillator.connect(gain);
    const startsAt = context.currentTime + index * 0.16;
    oscillator.start(startsAt);
    oscillator.stop(startsAt + 0.42);
  });
  globalThis.setTimeout(() => void context.close(), 1300);
  return true;
}

const QUALITY_TRAINING_TARGETS = Object.freeze({
  product_fidelity: Object.freeze({
    courseCode: "video_quality",
    lessonId: "reference_pack",
    label: "точность товара и упаковки",
    title: "Сверьте референсы точного SKU",
    tip: "Проверьте packshot, второй ракурс и масштаб товара; исключите похожие варианты и размытые этикетки.",
  }),
  technical_stability: Object.freeze({
    courseCode: "video_quality",
    lessonId: "full_video_qa",
    label: "техническая стабильность",
    title: "Повторите полный QA файла",
    tip: "Просмотрите точный результат целиком и отдельно проверьте стабильность кадра, руки, лицо, звук и титры.",
  }),
  hook_clarity: Object.freeze({
    courseCode: "video_quality",
    lessonId: "eight_second_storyboard",
    label: "ясность первых секунд",
    title: "Упростите первые секунды",
    tip: "Оставьте один понятный вход, одно действие с товаром и один чистый финал без лишних смен сцены.",
  }),
  visual_quality: Object.freeze({
    courseCode: "video_quality",
    lessonId: "prompt_anatomy",
    label: "визуальное качество",
    title: "Уточните кадр и визуальные запреты",
    tip: "Зафиксируйте камеру, свет, действие и запреты на изменение упаковки, этикетки, цвета и формы товара.",
  }),
  trust: Object.freeze({
    courseCode: "security_wb",
    lessonId: "rights_and_claims",
    label: "доверие и доказательность",
    title: "Перепроверьте обещания и права",
    tip: "Оставьте только проверяемые утверждения и убедитесь, что права покрывают исходники, лицо, музыку и площадку.",
  }),
  platform_fit: Object.freeze({
    courseCode: "publishing_funnel",
    lessonId: "publication_sequence",
    label: "формат площадки",
    title: "Сверьте маршрут публикации",
    tip: "Проверьте формат, назначенный аккаунт, рекламный контекст, финальную ссылку и обязательные действия площадки.",
  }),
});

function cleanCode(value) {
  return String(value || "").trim().toLowerCase();
}

export function generationQualityTrainingRecommendation(policy) {
  const guardCodes = Array.isArray(policy?.qualityGuardCodes)
    ? policy.qualityGuardCodes
    : Array.isArray(policy?.guardCodes)
      ? policy.guardCodes
      : [];
  const dimensionCode = guardCodes
    .map(cleanCode)
    .find((code) => Object.hasOwn(QUALITY_TRAINING_TARGETS, code));
  if (!dimensionCode) return null;
  const target = QUALITY_TRAINING_TARGETS[dimensionCode];
  const courseCode = target.courseCode;
  const lessonId = target.lessonId;
  return Object.freeze({
    dimensionCode,
    courseCode,
    lessonId,
    label: target.label,
    title: target.title,
    tip: target.tip,
    href: `#/learn/${encodeURIComponent(courseCode)}?lesson=${encodeURIComponent(lessonId)}&source=generation_qa`,
  });
}

export function targetedGenerationQualityLesson(course, query) {
  if (!course || String(query?.get?.("source") || "") !== "generation_qa") {
    return null;
  }
  const lessonId = cleanCode(query.get("lesson"));
  if (!lessonId) return null;
  const lessonIndex = (Array.isArray(course.lessons) ? course.lessons : [])
    .findIndex((lesson) => cleanCode(lesson?.id) === lessonId);
  if (lessonIndex < 0) return null;
  return Object.freeze({
    lessonId,
    lessonIndex,
    lesson: course.lessons[lessonIndex],
  });
}

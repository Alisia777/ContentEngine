/**
 * Stable navigation identifiers only.
 *
 * Course copy, lessons, exam prompts and answer options are deliberately not
 * bundled into the browser. Supabase is the sole source of the learning
 * catalog, and the SPA fails closed when that catalog is incomplete.
 */

export const FINAL_EXAM_CODE = "operator_final_exam";

export const REQUIRED_MODULE_CODES = Object.freeze([
  "factory_basics",
  "video_quality",
  "publishing_funnel",
  "security_wb",
]);

export const WORKSPACE_TABS = Object.freeze([
  ["generation", "Генерация", "✦"],
  ["placement", "Размещение", "↗"],
  ["stats", "Статистика", "◫"],
  ["payouts", "Выплаты", "₽"],
  ["tasks", "Задачи", "✓"],
  ["media", "Медиатека", "▧"],
  ["feedback", "Что добавить", "+"],
  ["team", "Команда", "◎"],
]);

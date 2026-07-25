from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log1p
import re
from statistics import median

from app.intelligence.types import ContentLearning, CreativeLearningPolicy


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_SAFE_ANGLE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9 _-]{1,64}$")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class _Observation:
    index: int
    source_id: int | None
    platform: str
    angle: str | None
    hook_patterns: tuple[str, ...]
    metrics: dict[str, float]


class CreativeLearningPolicyBuilder:
    """Derive conservative creative guidance from SKU-level performance history.

    The policy intentionally uses ranks rather than raw metric magnitude. That
    prevents a single large order count or malformed rate from dominating the
    next brief. Historical hook copy is never carried into the policy; only
    structural patterns are retained, so past text cannot become a new claim
    source.
    """

    def build(
        self,
        learnings: list[ContentLearning],
        *,
        target_platform: str | None = None,
        source_ids: list[int] | None = None,
    ) -> CreativeLearningPolicy:
        observations, invalid_values = self._observations(learnings, source_ids or [])
        normalized_target = self._clean_platform(target_platform)
        platform_rows = [
            row for row in observations if normalized_target and row.platform.casefold() == normalized_target.casefold()
        ]
        selected = platform_rows if len(platform_rows) >= 3 else observations
        reason_codes: list[str] = []
        if invalid_values:
            reason_codes.append("invalid_metric_values_ignored")
        if normalized_target and len(platform_rows) >= 3:
            reason_codes.append("platform_specific_evidence")
        elif normalized_target and platform_rows:
            reason_codes.append("platform_evidence_too_sparse_for_isolation")

        if not selected:
            return CreativeLearningPolicy(
                target_platform=normalized_target,
                reason_codes=[*reason_codes, "no_valid_performance_evidence"],
            )

        metric_names = sorted({name for row in selected for name in row.metrics})
        confidence = self._confidence(len(selected), len(metric_names))
        benchmarks = {
            name: round(median([row.metrics[name] for row in selected if name in row.metrics]), 6)
            for name in metric_names
        }
        ranked_scores = self._ranked_scores(selected, metric_names)
        angle_scores = self._angle_scores(selected, ranked_scores)
        preferred_angles, avoid_angles = self._angle_policy(angle_scores, confidence)
        applied = bool(preferred_angles and confidence in {"medium", "high"})

        if confidence == "low":
            reason_codes.append("insufficient_evidence")
        elif len(angle_scores) < 2:
            reason_codes.append("insufficient_angle_comparison")
        elif not preferred_angles:
            reason_codes.append("no_stable_angle_separation")
        else:
            reason_codes.append("stable_relative_performance_signal")

        preferred_patterns: list[str] = []
        avoid_patterns: list[str] = []
        instructions: list[str] = []
        if applied:
            preferred_patterns = self._patterns_for_angles(selected, preferred_angles)
            avoid_patterns = [
                pattern
                for pattern in self._patterns_for_angles(selected, avoid_angles)
                if pattern not in preferred_patterns
            ]
            instructions.append(
                f"Prefer the '{preferred_angles[0]}' creative angle; it is associated with stronger "
                "observed outcomes for this SKU."
            )
            if preferred_patterns:
                instructions.append(
                    "Use these winning hook structures without copying historical wording or claims: "
                    + ", ".join(preferred_patterns)
                    + "."
                )
            if avoid_angles:
                instructions.append(
                    "Deprioritize the following weaker observed creative angles unless current product "
                    "evidence requires them: "
                    + ", ".join(avoid_angles)
                    + "."
                )
            instructions.append("Historical performance is directional evidence, never a source for product claims.")

        return CreativeLearningPolicy(
            confidence=confidence,
            applied=applied,
            evidence_count=len(selected),
            target_platform=normalized_target,
            preferred_angles=preferred_angles,
            avoid_angles=avoid_angles,
            preferred_hook_patterns=preferred_patterns,
            avoid_hook_patterns=avoid_patterns,
            instructions=instructions,
            reason_codes=list(dict.fromkeys(reason_codes)),
            benchmark_summary=benchmarks,
            angle_scores=angle_scores,
            source_ids=[row.source_id for row in selected if row.source_id is not None],
        )

    def _observations(
        self,
        learnings: list[ContentLearning],
        source_ids: list[int],
    ) -> tuple[list[_Observation], int]:
        observations: list[_Observation] = []
        invalid_values = 0
        for index, learning in enumerate(learnings):
            metrics: dict[str, float] = {}
            ctr, ctr_invalid = self._rate(learning.ctr)
            retention, retention_invalid = self._rate(learning.retention_rate)
            orders, orders_invalid = self._orders(learning.orders)
            invalid_values += int(ctr_invalid) + int(retention_invalid) + int(orders_invalid)
            if ctr is not None:
                metrics["ctr"] = ctr
            if retention is not None:
                metrics["retention_rate"] = retention
            if orders is not None:
                metrics["orders_log"] = orders
            if not metrics:
                continue
            observations.append(
                _Observation(
                    index=index,
                    source_id=source_ids[index] if index < len(source_ids) and isinstance(source_ids[index], int) else None,
                    platform=self._clean_platform(learning.platform) or "unknown",
                    angle=self._clean_angle(learning.creative_angle),
                    hook_patterns=tuple(self._hook_patterns(learning.hook_text)),
                    metrics=metrics,
                )
            )
        return observations, invalid_values

    @staticmethod
    def _rate(value: float | None) -> tuple[float | None, bool]:
        if value is None:
            return None, False
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None, True
        if not isfinite(number) or number < 0 or number > 1:
            return None, True
        return number, False

    @staticmethod
    def _orders(value: int | None) -> tuple[float | None, bool]:
        if value is None:
            return None, False
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None, True
        if not isfinite(number) or number < 0:
            return None, True
        capped = min(number, 1_000_000)
        return log1p(capped), number != capped

    @staticmethod
    def _confidence(evidence_count: int, metric_count: int) -> str:
        if evidence_count == 0:
            return "none"
        if evidence_count >= 6 and metric_count >= 3:
            return "high"
        if evidence_count >= 3 and metric_count >= 2:
            return "medium"
        return "low"

    @staticmethod
    def _ranked_scores(observations: list[_Observation], metric_names: list[str]) -> dict[int, float]:
        ranks_by_metric: dict[str, dict[int, float]] = {}
        for metric in metric_names:
            values = [(row.index, row.metrics[metric]) for row in observations if metric in row.metrics]
            sorted_values = sorted(values, key=lambda item: (item[1], item[0]))
            ranks: dict[int, float] = {}
            if len(sorted_values) == 1:
                ranks[sorted_values[0][0]] = 0.5
            else:
                position = 0
                while position < len(sorted_values):
                    end = position
                    while end + 1 < len(sorted_values) and sorted_values[end + 1][1] == sorted_values[position][1]:
                        end += 1
                    average_position = (position + end) / 2
                    rank = average_position / (len(sorted_values) - 1)
                    for tied_position in range(position, end + 1):
                        ranks[sorted_values[tied_position][0]] = rank
                    position = end + 1
            ranks_by_metric[metric] = ranks

        scores: dict[int, float] = {}
        for row in observations:
            row_ranks = [ranks_by_metric[name][row.index] for name in metric_names if row.index in ranks_by_metric[name]]
            scores[row.index] = sum(row_ranks) / len(row_ranks)
        return scores

    @staticmethod
    def _angle_scores(observations: list[_Observation], ranked_scores: dict[int, float]) -> dict[str, float]:
        grouped: dict[str, list[float]] = {}
        for row in observations:
            if row.angle:
                grouped.setdefault(row.angle, []).append(ranked_scores[row.index])
        ordered = sorted(
            ((angle, sum(scores) / len(scores)) for angle, scores in grouped.items()),
            key=lambda item: (-item[1], item[0]),
        )
        return {angle: round(score, 4) for angle, score in ordered}

    @staticmethod
    def _angle_policy(angle_scores: dict[str, float], confidence: str) -> tuple[list[str], list[str]]:
        if confidence not in {"medium", "high"} or len(angle_scores) < 2:
            return [], []
        ordered = list(angle_scores.items())
        top_angle, top_score = ordered[0]
        second_score = ordered[1][1]
        bottom_angle, bottom_score = ordered[-1]
        preferred = [top_angle] if top_score >= 0.6 and top_score - second_score >= 0.1 else []
        avoid = [bottom_angle] if preferred and bottom_score <= 0.4 and top_score - bottom_score >= 0.2 else []
        return preferred, avoid

    @staticmethod
    def _patterns_for_angles(observations: list[_Observation], angles: list[str]) -> list[str]:
        counts: dict[str, int] = {}
        for row in observations:
            if row.angle not in angles:
                continue
            for pattern in row.hook_patterns:
                counts[pattern] = counts.get(pattern, 0) + 1
        return [
            pattern
            for pattern, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ][:4]

    @staticmethod
    def _clean_platform(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = _SPACE.sub(" ", _CONTROL_CHARACTERS.sub("", str(value))).strip()
        return cleaned[:80] or None

    @staticmethod
    def _clean_angle(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = _SPACE.sub(" ", _CONTROL_CHARACTERS.sub("", str(value))).strip()
        if not _SAFE_ANGLE.fullmatch(cleaned):
            return None
        return cleaned

    @staticmethod
    def _hook_patterns(value: str | None) -> list[str]:
        if not value:
            return []
        cleaned = _SPACE.sub(" ", _CONTROL_CHARACTERS.sub("", str(value))).strip()[:160]
        if not cleaned:
            return []
        lowered = cleaned.casefold()
        patterns: list[str] = []
        if "?" in cleaned:
            patterns.append("question_led")
        if re.search(r"\b(why|почему|зачем)\b", lowered):
            patterns.append("why_explanation")
        if re.search(r"\b(before|до покупки|перед покупкой)\b", lowered):
            patterns.append("before_buying")
        if re.search(r"\b(compare|versus|vs|сравн|дешев)\w*", lowered):
            patterns.append("comparison")
        if re.search(r"\b(watch|show|see|смотр|покаж)\w*", lowered):
            patterns.append("demonstration")
        if re.search(r"\b(i|my|я|мой|моя|мне)\b", lowered):
            patterns.append("first_person")
        if re.search(r"\d", lowered) or re.search(r"\b(one|один|одна|три|three)\b", lowered):
            patterns.append("numbered")
        if len(cleaned) <= 72:
            patterns.append("concise")
        return list(dict.fromkeys(patterns))

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.training_academy.errors import TrainingAcademyDataError


DEFAULT_COURSES: list[dict[str, Any]] = [
    {
        "code": "creator_basics",
        "title": "Creator Basics",
        "role": "creator",
        "sort_order": 10,
        "summary": "Read video briefs, preserve product identity, submit work, and understand review statuses.",
        "learning_path": [
            "Read the assignment brief before creating content.",
            "Keep product packaging, label color, geometry, and scale locked to the reference.",
            "Submit files or URLs through Participant Portal so review can happen in-system.",
        ],
        "checklist": [
            "Assignment exists.",
            "Product reference is followed.",
            "No medical or dangerous claims are added.",
            "Submission is attached to the assignment.",
        ],
        "lessons": [
            {
                "code": "briefs",
                "title": "How to read a video brief",
                "body": "Every content task starts from an assignment. Use SKU, product name, buyer need, safe promise, hook, first-frame logic, format, platform, CTA, tracking link, deadline, payout rule, and review checklist from the brief. Do not replace the brief with a chat instruction.",
                "checklist": ["Find SKU and product reference.", "Check platform and duration.", "Read the safe promise and forbidden claims."],
                "examples": [{"label": "Bad handoff", "value": "A video uploaded without assignment context cannot be measured or paid correctly."}],
            },
            {
                "code": "identity",
                "title": "Product identity rules",
                "body": "The product must not be visually rewritten. Do not change bottle shape, label color, cap/dropper style, visible size, or key packshot details. If identity drifts, the correct review status is needs_regeneration or needs_human_review.",
                "checklist": ["Bottle geometry preserved.", "Label and packshot details preserved.", "No fake product variant added."],
                "examples": [{"label": "Correct status", "value": "Distorted label means needs_regeneration / needs_human_review."}],
            },
        ],
        "quiz": {
            "code": "creator_basics_quiz",
            "title": "Creator Basics Quiz",
            "passing_score": 0.8,
            "questions": [
                {
                    "id": "distorted_label_status",
                    "prompt": "What status is appropriate if the product label is distorted?",
                    "correct_answers": ["needs_regeneration", "needs_human_review"],
                    "explanation": "Visual identity is not auto-approved when packaging drifts.",
                },
                {
                    "id": "brief_source",
                    "prompt": "Where should the creator read the task from?",
                    "correct_answers": ["assignment", "brief", "participant portal"],
                    "explanation": "Work must stay tied to a system assignment.",
                },
            ],
        },
    },
    {
        "code": "publisher_basics",
        "title": "Publisher Basics",
        "role": "publisher",
        "sort_order": 20,
        "summary": "Publish only approved videos, use tracking links, and submit final_url after posting.",
        "learning_path": [
            "Open the publishing assignment.",
            "Use the approved video and caption package.",
            "Place tracking_link in the post instead of a direct product URL.",
            "Submit final_url after publishing.",
        ],
        "checklist": [
            "Video is approved.",
            "Destination is assigned.",
            "tracking_link is used.",
            "final_url is submitted.",
        ],
        "lessons": [
            {
                "code": "approved_only",
                "title": "Publish only approved video",
                "body": "A video in needs_human_review, rejected, or needs_regeneration status is not ready for publishing. Publishing unapproved content breaks quality control and attribution.",
                "checklist": ["Review status is approved.", "Caption and CTA are present."],
                "examples": [{"label": "Blocked", "value": "needs_human_review cannot be published."}],
            },
            {
                "code": "tracking_and_final_url",
                "title": "Tracking link and final URL",
                "body": "The tracking_link captures clicks through /r/{slug}. The final_url is the public URL of the published post. Both are needed: tracking_link measures traffic, final_url ties the social post back to the publishing task.",
                "checklist": ["Use tracking_link in caption/comment/link field.", "Paste the final_url after publishing."],
                "examples": [{"label": "Correct link", "value": "Use https://our-domain.com/r/abc123, not the direct marketplace URL."}],
            },
        ],
        "quiz": {
            "code": "publisher_basics_quiz",
            "title": "Publisher Basics Quiz",
            "passing_score": 0.8,
            "questions": [
                {
                    "id": "publish_needs_review",
                    "prompt": "Can you publish a video with status needs_human_review?",
                    "correct_answers": ["no"],
                    "explanation": "Only approved video should be published.",
                },
                {
                    "id": "post_link",
                    "prompt": "What link must be placed in the post?",
                    "correct_answers": ["tracking_link", "tracking link"],
                    "explanation": "The tracking link lets ContentEngine count clicks.",
                },
                {
                    "id": "post_back_reference",
                    "prompt": "What field connects the public social post back to the system?",
                    "correct_answers": ["final_url", "publishing_task", "publishing_task_id"],
                    "explanation": "The final URL and publishing task make the post traceable.",
                },
            ],
        },
    },
    {
        "code": "metrics_basics",
        "title": "Metrics Basics",
        "role": "operator",
        "sort_order": 30,
        "summary": "Submit CSV metrics safely, understand tracking links vs final_url, and resolve unmatched rows.",
        "learning_path": [
            "Collect platform metrics through official connectors or CSV/manual report.",
            "Include posted_url or tracking_slug for social rows.",
            "Use normalized columns so attribution can feed dashboards and payouts.",
        ],
        "checklist": [
            "posted_url or tracking_slug exists.",
            "period_start and period_end are present.",
            "views/clicks/orders/revenue columns are normalized.",
            "Unmatched rows are reviewed.",
        ],
        "lessons": [
            {
                "code": "metric_sources",
                "title": "Where statistics come from",
                "body": "Metrics can come from official connectors, CSV/manual reports, tracking clicks, and marketplace conversion reports. Social platforms usually provide views, reach, and engagement; marketplaces provide orders and revenue.",
                "checklist": ["Know source type.", "Do not scrape private platform pages.", "Use CSV fallback when OAuth is not configured."],
                "examples": [{"label": "Fallback", "value": "TikTok without official access uses CSV/manual metrics plus tracking link clicks."}],
            },
            {
                "code": "csv_attribution",
                "title": "CSV attribution rules",
                "body": "A social metric row without posted_url, tracking_slug, or publishing_task_id cannot be attributed safely. It must stay unmatched with a warning instead of silently matching by SKU.",
                "checklist": ["posted_url or tracking_slug supplied.", "SKU and platform supplied.", "Warnings reviewed."],
                "examples": [{"label": "Unmatched", "value": "A row missing posted_url and tracking_slug becomes unmatched."}],
            },
        ],
        "quiz": {
            "code": "metrics_basics_quiz",
            "title": "Metrics Basics Quiz",
            "passing_score": 0.8,
            "questions": [
                {
                    "id": "missing_traceability",
                    "prompt": "What happens if CSV has no posted_url and no tracking_slug?",
                    "correct_answers": ["unmatched warning", "unmatched", "warning"],
                    "explanation": "The row is not safely attributable.",
                },
                {
                    "id": "tracking_vs_final_url",
                    "prompt": "What captures clicks: tracking_link or final_url?",
                    "correct_answers": ["tracking_link", "tracking link"],
                    "explanation": "The tracking link redirects through ContentEngine and records clicks.",
                },
            ],
        },
    },
    {
        "code": "payout_basics",
        "title": "Payout Basics",
        "role": "partner",
        "sort_order": 40,
        "summary": "Understand payout rules, statuses, and why traceability is mandatory before money is owed.",
        "learning_path": [
            "Read the payout rule attached to the assignment.",
            "Check whether payout is per video, per approved post, per published post, CPA, revenue share, or hybrid.",
            "Use final_url and metrics so ledger entries can be calculated.",
        ],
        "checklist": [
            "Payout rule exists.",
            "Assignment/submission/publishing task exists.",
            "final_url exists for published-post payouts.",
            "Metrics exist for CPA/revenue share.",
        ],
        "lessons": [
            {
                "code": "ledger_statuses",
                "title": "Payout ledger statuses",
                "body": "Payouts are ledger-only until reviewed: pending, approved, payable, paid, rejected, or disputed. The system records what the amount is for, but it does not execute payments.",
                "checklist": ["Reason is clear.", "Status is visible.", "No payment secret is stored."],
                "examples": [{"label": "Manual payment", "value": "mark_paid only records that payment was handled outside the system."}],
            },
            {
                "code": "traceable_payouts",
                "title": "Traceability before payout",
                "body": "A per_published_post payout requires a publishing task with final_url. Without final_url, the system cannot prove the post exists and should not calculate that payout.",
                "checklist": ["final_url present.", "Metrics or review result present.", "Payout rule applies."],
                "examples": [{"label": "Blocked", "value": "No final_url means no per_published_post payout."}],
            },
        ],
        "quiz": {
            "code": "payout_basics_quiz",
            "title": "Payout Basics Quiz",
            "passing_score": 0.8,
            "questions": [
                {
                    "id": "payout_without_final_url",
                    "prompt": "Can payout be calculated for per_published_post without final_url?",
                    "correct_answers": ["no"],
                    "explanation": "Published-post payouts need a traceable public post.",
                },
                {
                    "id": "payment_execution",
                    "prompt": "Does ContentEngine execute real payments?",
                    "correct_answers": ["no"],
                    "explanation": "It keeps ledger entries; real payment execution stays outside this MVP.",
                },
            ],
        },
    },
    {
        "code": "reviewer_basics",
        "title": "Reviewer Basics",
        "role": "reviewer",
        "sort_order": 50,
        "summary": "Approve, reject, or request regeneration based on product identity, safety, and brief compliance.",
        "learning_path": [
            "Compare the video to the product reference.",
            "Check geometry, scale, label, and package color.",
            "Reject forbidden claims and request regeneration for visual drift.",
        ],
        "checklist": [
            "Product identity is preserved.",
            "Brief and safe promise are followed.",
            "No prohibited claims are present.",
            "Human review decision is stored.",
        ],
        "lessons": [
            {
                "code": "review_decisions",
                "title": "Review decisions",
                "body": "Approve only when the product is recognizable and the brief is followed. Reject unsafe or off-brief content. Use needs_regeneration when the concept is right but product visual identity or scene execution needs repair.",
                "checklist": ["Identity checked.", "Claims checked.", "Status chosen deliberately."],
                "examples": [{"label": "Regenerate", "value": "Product label changed or bottle shape drifted."}],
            }
        ],
        "quiz": {
            "code": "reviewer_basics_quiz",
            "title": "Reviewer Basics Quiz",
            "passing_score": 0.8,
            "questions": [
                {
                    "id": "distorted_label_review",
                    "prompt": "What status if product label is distorted?",
                    "correct_answers": ["needs_regeneration", "needs_human_review"],
                    "explanation": "Identity drift cannot be auto-approved.",
                },
                {
                    "id": "approval_gate",
                    "prompt": "Can a reviewer approve a video with unsafe claims?",
                    "correct_answers": ["no"],
                    "explanation": "Safety boundaries are mandatory.",
                },
            ],
        },
    },
]


class CurriculumService:
    def __init__(self, db: Session):
        self.db = db

    def seed_defaults(self) -> list[models.TrainingCourse]:
        courses = [self._upsert_course(course_data) for course_data in DEFAULT_COURSES]
        self.db.commit()
        for course in courses:
            self.db.refresh(course)
        return courses

    def list_courses(self, *, status: str | None = "active") -> list[models.TrainingCourse]:
        statement = select(models.TrainingCourse)
        if status:
            statement = statement.where(models.TrainingCourse.status == status)
        return self.db.scalars(statement.order_by(models.TrainingCourse.sort_order, models.TrainingCourse.id)).all()

    def get_course(self, course_id: int) -> models.TrainingCourse:
        course = self.db.get(models.TrainingCourse, course_id)
        if not course:
            raise TrainingAcademyDataError(f"TrainingCourse {course_id} not found.")
        return course

    def get_course_by_code(self, course_code: str) -> models.TrainingCourse:
        course = self.db.scalar(select(models.TrainingCourse).where(models.TrainingCourse.code == course_code))
        if not course:
            raise TrainingAcademyDataError(f"TrainingCourse {course_code} not found.")
        return course

    def course_payload(self, course: models.TrainingCourse, *, include_answers: bool = False) -> dict[str, Any]:
        lessons = sorted(course.lessons, key=lambda item: (item.sort_order, item.id))
        quizzes = sorted(course.quizzes, key=lambda item: (item.id,))
        return {
            "id": course.id,
            "code": course.code,
            "title": course.title,
            "role": course.role,
            "status": course.status,
            "summary": course.summary,
            "sort_order": course.sort_order,
            "learning_path": course.learning_path_json or [],
            "checklist": course.checklist_json or [],
            "lessons": [
                {
                    "id": lesson.id,
                    "code": lesson.code,
                    "title": lesson.title,
                    "body": lesson.body,
                    "checklist": lesson.checklist_json or [],
                    "examples": lesson.examples_json or [],
                }
                for lesson in lessons
            ],
            "quizzes": [
                {
                    "id": quiz.id,
                    "code": quiz.code,
                    "title": quiz.title,
                    "passing_score": quiz.passing_score,
                    "questions": [self._question_payload(question, include_answers=include_answers) for question in (quiz.questions_json or [])],
                }
                for quiz in quizzes
            ],
        }

    @staticmethod
    def _question_payload(question: dict[str, Any], *, include_answers: bool = False) -> dict[str, Any]:
        payload = {
            "id": question.get("id"),
            "prompt": question.get("prompt"),
        }
        if include_answers:
            payload["correct_answers"] = question.get("correct_answers", [])
            payload["explanation"] = question.get("explanation")
        return payload

    def _upsert_course(self, course_data: dict[str, Any]) -> models.TrainingCourse:
        course = self.db.scalar(select(models.TrainingCourse).where(models.TrainingCourse.code == course_data["code"]))
        if not course:
            course = models.TrainingCourse(
                code=course_data["code"],
                title=course_data["title"],
                role=course_data["role"],
                status="active",
                summary=course_data["summary"],
                sort_order=course_data["sort_order"],
                learning_path_json=course_data["learning_path"],
                checklist_json=course_data["checklist"],
            )
            self.db.add(course)
            self.db.flush()
        else:
            course.title = course_data["title"]
            course.role = course_data["role"]
            course.status = "active"
            course.summary = course_data["summary"]
            course.sort_order = course_data["sort_order"]
            course.learning_path_json = course_data["learning_path"]
            course.checklist_json = course_data["checklist"]
        self._upsert_lessons(course, course_data.get("lessons", []))
        self._upsert_quiz(course, course_data["quiz"])
        return course

    def _upsert_lessons(self, course: models.TrainingCourse, lessons: list[dict[str, Any]]) -> None:
        existing = {lesson.code: lesson for lesson in course.lessons}
        for index, lesson_data in enumerate(lessons, start=1):
            lesson = existing.get(lesson_data["code"])
            if not lesson:
                lesson = models.TrainingLesson(course_id=course.id, code=lesson_data["code"])
                self.db.add(lesson)
            lesson.title = lesson_data["title"]
            lesson.body = lesson_data["body"]
            lesson.sort_order = index * 10
            lesson.checklist_json = lesson_data.get("checklist", [])
            lesson.examples_json = lesson_data.get("examples", [])

    def _upsert_quiz(self, course: models.TrainingCourse, quiz_data: dict[str, Any]) -> None:
        quiz = next((item for item in course.quizzes if item.code == quiz_data["code"]), None)
        if not quiz:
            quiz = models.TrainingQuiz(course_id=course.id, code=quiz_data["code"])
            self.db.add(quiz)
        quiz.title = quiz_data["title"]
        quiz.passing_score = float(quiz_data.get("passing_score", 0.8))
        quiz.questions_json = quiz_data.get("questions", [])

from __future__ import annotations

from typing import Any


COURSE_BADGE_BY_CODE = {
    "publisher_basics": "publisher_basics_certified",
    "metrics_basics": "metrics_operator_certified",
    "reviewer_basics": "reviewer_assistant_certified",
    "creator_basics": "creator_editor_certified",
    "destination_owner_track": "destination_owner_certified",
    "instagram_reels_playbook": "instagram_reels_certified",
    "facebook_playbook": "facebook_certified",
    "youtube_shorts_playbook": "youtube_shorts_certified",
    "tiktok_playbook": "tiktok_certified",
    "telegram_playbook": "telegram_certified",
    "vk_playbook": "vk_certified",
    "marketplace_metrics_playbook": "marketplace_metrics_certified",
    "partner_slot_playbook": "partner_slot_certified",
}


PLATFORM_COURSE_BY_PLATFORM = {
    "instagram": "instagram_reels_playbook",
    "instagram reels": "instagram_reels_playbook",
    "reels": "instagram_reels_playbook",
    "facebook": "facebook_playbook",
    "meta": "facebook_playbook",
    "youtube": "youtube_shorts_playbook",
    "youtube shorts": "youtube_shorts_playbook",
    "shorts": "youtube_shorts_playbook",
    "tiktok": "tiktok_playbook",
    "telegram": "telegram_playbook",
    "vk": "vk_playbook",
    "vkontakte": "vk_playbook",
    "ozon": "marketplace_metrics_playbook",
    "wildberries": "marketplace_metrics_playbook",
    "wb": "marketplace_metrics_playbook",
    "marketplace": "marketplace_metrics_playbook",
    "marketplaces": "marketplace_metrics_playbook",
    "partner": "partner_slot_playbook",
    "partner slots": "partner_slot_playbook",
}


BEGINNER_TRACKS = [
    {
        "code": "publisher_operator_track",
        "title": "Publisher / Placement Operator",
        "earning": "Paid for traceable published posts, verified final URLs, stats handoff, and result bonuses when enabled.",
        "daily_work": [
            "Open assigned publishing tasks.",
            "Download approved video and copy caption/hashtags.",
            "Publish only to the assigned destination.",
            "Use tracking_link and submit final_url.",
            "Return platform stats later when requested.",
            "Check payout status after final_url and metrics are accepted.",
        ],
        "must_submit": ["final_url", "tracking_link usage", "posted stats with posted_url or tracking_slug"],
        "rejected_if": ["video is not approved", "wrong destination", "direct product URL replaces tracking_link", "final_url is missing"],
        "required_badges": ["publisher_basics_certified", "platform badge for the assigned network"],
    },
    {
        "code": "metrics_operator_track",
        "title": "Metrics Operator",
        "earning": "Paid for valid reports by destination, campaign, or correctly attributed metric rows.",
        "daily_work": [
            "Open Metrics Intake.",
            "Collect platform report or official connector export.",
            "Fill CSV with posted_url or tracking_slug.",
            "Check period, SKU, destination and metric columns.",
            "Resolve unmatched rows before payout decisions.",
        ],
        "must_submit": ["CSV/manual report", "period_start", "period_end", "posted_url or tracking_slug"],
        "rejected_if": ["no posted_url/tracking_slug", "no period", "wrong SKU", "manual numbers without source report"],
        "required_badges": ["metrics_operator_certified", "platform or marketplace metrics badge"],
    },
    {
        "code": "reviewer_assistant_track",
        "title": "Reviewer Assistant",
        "earning": "Paid for valid review decisions and clean approve/reject/regenerate calls.",
        "daily_work": [
            "Open video/package needing review.",
            "Compare product to reference.",
            "Check label, geometry, scale and forbidden claims.",
            "Choose approve, reject, or needs_regeneration.",
        ],
        "must_submit": ["review status", "review notes when blocked", "reason for regeneration/rejection"],
        "rejected_if": ["approves distorted product", "misses forbidden claim", "approves pretty but wrong product"],
        "required_badges": ["reviewer_assistant_certified"],
    },
    {
        "code": "creator_editor_track",
        "title": "Creator / Editor",
        "earning": "Paid for approved video, accepted revisions, published output, or performance bonuses when enabled.",
        "daily_work": [
            "Read the brief card.",
            "Keep buyer_need, hook and safe promise.",
            "Preserve product identity, geometry and scale.",
            "Submit file or external URL through the assignment.",
            "Fix revision requests.",
        ],
        "must_submit": ["video file or URL", "assignment-linked submission", "revision response when requested"],
        "rejected_if": ["changes packaging", "changes product promise", "removes CTA", "creates a beautiful video that ignores the brief"],
        "required_badges": ["creator_editor_certified"],
    },
    {
        "code": "destination_owner_track",
        "title": "Channel / Destination Owner",
        "earning": "Paid for placement, CPA, revenue share, or hybrid models when destination and reports are traceable.",
        "daily_work": [
            "Keep owned destination linked in ContentEngine.",
            "Respect capacity and warmup rules.",
            "Publish assigned approved content.",
            "Submit final_url and metrics.",
            "Track payout ledger status.",
        ],
        "must_submit": ["destination readiness", "final_url", "stats/report", "payout rule evidence"],
        "rejected_if": ["publishes outside assignment", "exceeds capacity", "does not return stats", "uses untraceable links"],
        "required_badges": ["destination_owner_certified", "platform badge"],
    },
]


PLATFORM_PLAYBOOKS = [
    {
        "code": "instagram_reels_playbook",
        "title": "Instagram / Reels Playbook",
        "platform": "Instagram Reels",
        "summary": "Publish assigned Reels with tracking links, final_url, and social engagement stats.",
        "metrics": ["views", "reach", "impressions", "likes", "comments", "shares", "saves", "clicks if visible or from tracking_link"],
        "rules": [
            "Publish only approved assignment video.",
            "Use tracking_link in caption, bio link, comment, or assigned link location.",
            "Submit final_url after the Reel is live.",
            "Return posted_url or tracking_slug when uploading stats.",
        ],
        "dont": [
            "Do not publish needs_human_review video.",
            "Do not replace tracking_link with direct marketplace URL.",
            "Do not submit stats without posted_url or tracking_slug.",
        ],
        "quiz": [
            ("instagram_link", "Which link must be used for click tracking?", ["tracking_link", "tracking link"]),
            ("instagram_final_url", "What proves the Reel is live and traceable?", ["final_url", "posted_url"]),
        ],
    },
    {
        "code": "facebook_playbook",
        "title": "Facebook Playbook",
        "platform": "Facebook",
        "summary": "Understand page/profile destination mapping, Meta official access when available, and CSV/manual fallback.",
        "metrics": ["views", "reach", "impressions", "likes", "comments", "shares", "clicks"],
        "rules": [
            "Use the destination assigned in ContentEngine, whether it maps to a page, profile, or partner placement.",
            "Use official Meta connection when authorized; otherwise use CSV/manual report.",
            "Submit final_url and keep tracking_link in the post.",
            "Stats connect to payouts only when matched by posted_url, tracking_slug, or task.",
        ],
        "dont": ["Do not scrape private Facebook pages.", "Do not invent manual numbers.", "Do not omit posted_url in reports."],
        "quiz": [
            ("facebook_fallback", "What should you use when official Meta access is not configured?", ["csv", "manual", "csv/manual"]),
            ("facebook_payout", "What lets Facebook stats connect to payouts?", ["posted_url", "tracking_slug", "final_url"]),
        ],
    },
    {
        "code": "youtube_shorts_playbook",
        "title": "YouTube Shorts Playbook",
        "platform": "YouTube Shorts",
        "summary": "Use YouTube Analytics OAuth when configured, CSV/manual fallback otherwise, and tracking links for clicks.",
        "metrics": ["views", "likes", "comments", "watch_time_seconds", "retention_rate", "clicks via tracking_link"],
        "rules": [
            "Publish the assigned Short and keep the CTA/tracking link in description or pinned comment.",
            "Use YouTube Analytics connector when OAuth is configured.",
            "Use CSV/manual fallback when OAuth is not configured.",
            "Watch time and retention are important quality signals when available.",
        ],
        "dont": ["Do not claim YouTube clicks without tracking_link.", "Do not skip watch time when it is available."],
        "quiz": [
            ("youtube_oauth", "What is preferred when YouTube OAuth is configured?", ["youtube analytics", "oauth", "connector"]),
            ("youtube_fallback", "What is the fallback if OAuth is not configured?", ["csv", "manual", "csv/manual"]),
        ],
    },
    {
        "code": "tiktok_playbook",
        "title": "TikTok Playbook",
        "platform": "TikTok",
        "summary": "Work only through authorized connector or CSV/manual fallback. No unofficial login, scraping, or private API.",
        "metrics": ["views", "likes", "comments", "shares", "saves if available", "clicks via tracking_link"],
        "rules": [
            "Open TikTok assignment and use assigned destination.",
            "Use official connector only when authorized.",
            "Use CSV/manual fallback when authorized access is missing.",
            "Submit final_url and tracking_slug/post URL for attribution.",
        ],
        "dont": ["Do not use unofficial login flows.", "Do not scrape private TikTok data.", "Do not bypass permissions."],
        "quiz": [
            ("tiktok_scraping", "Can you use unofficial login or scraping to collect TikTok stats?", ["no"]),
            ("tiktok_clicks", "How are TikTok clicks safely counted?", ["tracking_link", "tracking link"]),
        ],
    },
    {
        "code": "telegram_playbook",
        "title": "Telegram Playbook",
        "platform": "Telegram",
        "summary": "Publish through bot when configured or manual post, keep chat/message IDs when available, and track clicks.",
        "metrics": ["views if available", "reactions if available", "comments if available", "clicks via tracking_link"],
        "rules": [
            "If bot posts, preserve chat_id and message_id.",
            "If manual, submit final_url/message link.",
            "Put tracking_link in post text.",
            "Use manual stats fallback when platform stats are limited.",
        ],
        "dont": ["Do not publish without assignment.", "Do not hide product link outside tracking_link."],
        "quiz": [
            ("telegram_bot_ids", "What IDs matter when a Telegram bot posts?", ["chat_id", "message_id"]),
            ("telegram_link", "Where should tracking_link go?", ["post text", "caption", "message"]),
        ],
    },
    {
        "code": "vk_playbook",
        "title": "VK Playbook",
        "platform": "VK",
        "summary": "Use official VK token/permissions when available, CSV/manual fallback otherwise, and trace every post.",
        "metrics": ["views", "likes", "comments", "shares", "clicks"],
        "rules": [
            "Use official VK connector only with token/permissions.",
            "Use CSV/manual fallback when token is not configured.",
            "Submit final_url and tracking link.",
            "Attach stats to posted_url or tracking_slug.",
        ],
        "dont": ["Do not use someone else's destination.", "Do not bypass VK permissions."],
        "quiz": [
            ("vk_connector", "What is required for official VK connector?", ["token", "permissions"]),
            ("vk_trace", "What makes a VK post traceable?", ["final_url", "tracking_link", "posted_url"]),
        ],
    },
    {
        "code": "marketplace_metrics_playbook",
        "title": "Marketplace Playbook: Ozon / Wildberries",
        "platform": "Ozon / Wildberries",
        "summary": "Marketplace reports are the conversion source of truth for orders, revenue, returns and bottom-funnel payout logic.",
        "metrics": ["orders", "revenue", "returns", "conversion", "sku performance"],
        "rules": [
            "Social platforms provide top-funnel views/reach/clicks.",
            "Marketplace reports provide bottom-funnel orders, revenue and returns.",
            "Use SKU, period, coupon, UTM or tracking link to connect reports.",
            "Missing marketplace data weakens payouts and recommendations.",
        ],
        "dont": ["Do not treat social views as orders.", "Do not calculate CPA without orders/revenue source."],
        "quiz": [
            ("marketplace_source", "What is the source of truth for orders and revenue?", ["marketplace report", "ozon/wb report", "reports"]),
            ("marketplace_missing", "What happens if marketplace conversion data is missing?", ["payout blocked", "recommendations weaker", "blocked"]),
        ],
    },
    {
        "code": "partner_slot_playbook",
        "title": "Partner Slot Playbook",
        "platform": "Partner Slots",
        "summary": "Partner/operator publishes assigned content, returns final_url, tracking_link evidence and partner report CSV.",
        "metrics": ["posted_url", "tracking_slug", "views", "clicks", "orders", "revenue", "partner payout fields"],
        "rules": [
            "Receive the task in ContentEngine.",
            "Publish with assigned tracking_link.",
            "Submit final_url.",
            "Submit partner report CSV with posted_url or tracking_slug.",
            "Payout depends on traceable publication and agreed rule.",
        ],
        "dont": ["Do not submit partner report without posted_url/tracking_slug.", "Do not publish outside assigned slot."],
        "quiz": [
            ("partner_report_key", "What must partner report include for attribution?", ["posted_url", "tracking_slug"]),
            ("partner_payout", "What does partner payout depend on?", ["final_url", "tracking_link", "payout rule"]),
        ],
    },
]


SCENARIO_SIMULATORS: list[dict[str, Any]] = [
    {
        "code": "publish_approved_reel",
        "title": "Publish approved Reel",
        "prompt": "You have an assignment, approved video, caption, tracking_link and Instagram destination.",
        "required_answers": {
            "video_status": ["approved"],
            "link_used": ["tracking_link"],
            "destination": ["assigned"],
            "final_url": ["provided", "yes"],
        },
        "failure_reasons": {
            "video_status": "Publishing needs_human_review content fails.",
            "link_used": "Direct product URLs hide clicks; use tracking_link.",
            "destination": "Wrong destination breaks ownership and payout.",
            "final_url": "Publication is incomplete until final_url is saved.",
        },
    },
    {
        "code": "submit_facebook_stats",
        "title": "Submit Facebook stats",
        "prompt": "Fill a Facebook report with posted_url, period, SKU, views, reach, likes, comments and clicks.",
        "required_answers": {
            "posted_url": ["provided", "yes"],
            "tracking_slug": ["provided", "yes"],
            "period": ["provided", "yes"],
            "sku": ["matches", "provided"],
        },
        "failure_reasons": {
            "posted_url": "Rows without posted_url or tracking_slug stay unmatched.",
            "tracking_slug": "Rows without posted_url or tracking_slug stay unmatched.",
            "period": "Missing period makes reporting weak.",
            "sku": "Wrong SKU makes attribution unreliable.",
        },
        "any_of": [["posted_url", "tracking_slug"]],
    },
    {
        "code": "youtube_shorts_stats",
        "title": "YouTube Shorts stats",
        "prompt": "Decide between OAuth connector and CSV/manual fallback; include watch time/retention when available.",
        "required_answers": {
            "oauth_available": ["connector", "youtube analytics"],
            "oauth_missing": ["csv", "manual", "csv/manual"],
            "clicks": ["tracking_link"],
        },
    },
    {
        "code": "tiktok_task",
        "title": "TikTok task",
        "prompt": "Use official connector when authorized, otherwise CSV/manual. Never use unofficial login or scraping.",
        "required_answers": {
            "authorized_path": ["official connector", "connector"],
            "fallback_path": ["csv", "manual", "csv/manual"],
            "unofficial_scraping": ["no"],
        },
    },
    {
        "code": "product_identity_review",
        "title": "Product identity review",
        "prompt": "The label drifted, cap color changed and product scale changed.",
        "required_answers": {"review_status": ["needs_regeneration", "needs_human_review"]},
        "failure_reasons": {"review_status": "Pretty video still fails when product identity drifts."},
    },
    {
        "code": "payout_without_final_url",
        "title": "Payout scenario",
        "prompt": "The post is published, but final_url is not saved.",
        "required_answers": {"payout_status": ["blocked", "not calculated", "not payable"]},
        "failure_reasons": {"payout_status": "Published-post payout cannot be calculated before final_url exists."},
    },
]


def beginner_track_courses() -> list[dict[str, Any]]:
    courses = []
    for index, track in enumerate(BEGINNER_TRACKS, start=1):
        if track["code"] == "publisher_operator_track":
            continue
        if track["code"] == "metrics_operator_track":
            continue
        if track["code"] == "reviewer_assistant_track":
            continue
        if track["code"] == "creator_editor_track":
            continue
        courses.append(_track_course(track, sort_order=100 + index))
    return courses


def platform_playbook_courses() -> list[dict[str, Any]]:
    return [_platform_course(playbook, sort_order=200 + index) for index, playbook in enumerate(PLATFORM_PLAYBOOKS, start=1)]


def _track_course(track: dict[str, Any], *, sort_order: int) -> dict[str, Any]:
    return {
        "code": track["code"],
        "title": track["title"],
        "role": "owner",
        "sort_order": sort_order,
        "summary": f"{track['title']} path: what you do, how you earn, what you submit, and what blocks payout.",
        "learning_path": [
            f"How this role earns: {track['earning']}",
            "Daily work: " + "; ".join(track["daily_work"]),
            "Required badges: " + ", ".join(track["required_badges"]),
        ],
        "checklist": track["must_submit"],
        "lessons": [
            {
                "code": "how_to_earn",
                "title": "How this role earns",
                "body": track["earning"],
                "checklist": track["daily_work"],
                "examples": [{"label": "Rejected if", "value": "; ".join(track["rejected_if"])}],
            },
            {
                "code": "must_submit",
                "title": "What must be submitted",
                "body": "Payment and recommendations depend on traceable proof inside ContentEngine.",
                "checklist": track["must_submit"],
                "examples": [{"label": "Required badges", "value": ", ".join(track["required_badges"])}],
            },
        ],
        "quiz": {
            "code": f"{track['code']}_quiz",
            "title": f"{track['title']} Quiz",
            "passing_score": 0.8,
            "questions": [
                {
                    "id": "assignment_required",
                    "prompt": "Can work be paid if it was done without a ContentEngine assignment?",
                    "correct_answers": ["no"],
                    "explanation": "Traceable assignments are the start of payable work.",
                },
                {
                    "id": "proof_required",
                    "prompt": "What proof must be returned to make work traceable?",
                    "correct_answers": track["must_submit"],
                    "explanation": "The exact proof depends on role, but it must be stored in ContentEngine.",
                },
            ],
        },
    }


def _platform_course(playbook: dict[str, Any], *, sort_order: int) -> dict[str, Any]:
    question_defs = [
        {"id": item[0], "prompt": item[1], "correct_answers": item[2], "explanation": "This is required for safe platform work."}
        for item in playbook["quiz"]
    ]
    return {
        "code": playbook["code"],
        "title": playbook["title"],
        "role": "platform",
        "sort_order": sort_order,
        "summary": playbook["summary"],
        "learning_path": playbook["rules"],
        "checklist": playbook["metrics"],
        "lessons": [
            {
                "code": "how_to_work",
                "title": f"How to work on {playbook['platform']}",
                "body": playbook["summary"] + " Work only through assignment, destination, tracking_link, final_url and approved content.",
                "checklist": playbook["rules"],
                "examples": [{"label": "Do not", "value": "; ".join(playbook["dont"])}],
            },
            {
                "code": "required_metrics",
                "title": "Required data and metrics",
                "body": "These fields are needed so ContentEngine can connect the post to campaign, SKU, participant, payout and recommendations.",
                "checklist": playbook["metrics"],
                "examples": [{"label": "Traceability", "value": "posted_url, tracking_slug or publishing_task_id must be present where applicable."}],
            },
        ],
        "quiz": {
            "code": f"{playbook['code']}_quiz",
            "title": f"{playbook['title']} Quiz",
            "passing_score": 0.8,
            "questions": question_defs,
        },
    }


BEGINNER_TRACK_COURSES = beginner_track_courses()
PLATFORM_PLAYBOOK_COURSES = platform_playbook_courses()

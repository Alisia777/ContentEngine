PUBLIC_PILOT_TRAINING_MODULES: list[dict] = [
    {
        "code": "contentengine_overview",
        "title": "ContentEngine Overview",
        "description": "How ALTEA content moves from product data to brief, generation, QA, publishing, metrics, and next action.",
        "order_index": 10,
        "required_for_roles": ["trainee", "operator", "producer", "reviewer"],
        "required_for_permissions": [],
        "lessons": [
            {
                "title": "Factory Workflow",
                "content_markdown": "ContentEngine is a controlled workflow: product data, creative brief, selected variant, generation, QA, publishing package, metrics, and next action.",
            },
            {
                "title": "Human Responsibility",
                "content_markdown": "AI can draft and render. Humans approve product identity, claims, QA verdicts, spend decisions, and publishing readiness.",
            },
        ],
        "questions": [
            {
                "question_text": "What is ContentEngine primarily?",
                "question_type": "single_choice",
                "options": ["A video button", "An operating contour for content production", "A social network", "A password manager"],
                "correct_answer": ["An operating contour for content production"],
                "explanation": "The product is a controlled workflow, not just a generation button.",
            }
        ],
    },
    {
        "code": "review_qa",
        "title": "Review, QA And Regeneration",
        "description": "Contact sheet, product identity, claims, output verdicts, and regeneration reasons.",
        "order_index": 20,
        "required_for_roles": ["reviewer", "admin", "owner"],
        "required_for_permissions": ["output_review", "video_approve", "video_reject"],
        "lessons": [
            {
                "title": "Technical Success Is Not Approval",
                "content_markdown": "Provider success only means a file exists. Commercial approval requires human review of product identity, style, claims, and artifacts.",
            }
        ],
        "questions": [
            {
                "question_text": "Video generated, but product identity drifted. What is the verdict?",
                "question_type": "single_choice",
                "options": ["Approve", "Publish manually", "Mark needs_regeneration and block publishing", "Ignore"],
                "correct_answer": ["Mark needs_regeneration and block publishing"],
                "explanation": "Product identity drift blocks approval even when a file was generated.",
            }
        ],
    },
    {
        "code": "publishing_manual_upload",
        "title": "Publishing Package And Manual Upload",
        "description": "Approved video, destination, caption, UTM, final URL, analytics, and traceability.",
        "order_index": 30,
        "required_for_roles": ["operator", "admin", "owner"],
        "required_for_permissions": ["publishing_approve", "metrics_import"],
        "lessons": [
            {
                "title": "Traceable Publishing",
                "content_markdown": "A publishing package is not complete until destination, schedule, caption, tracking link, final URL, and metrics path are traceable.",
            }
        ],
        "questions": [
            {
                "question_text": "Can an unreviewed generated video become publishing-ready?",
                "question_type": "true_false",
                "options": ["true", "false"],
                "correct_answer": ["false"],
                "explanation": "Publishing requires review approval and traceability.",
            }
        ],
    },
]

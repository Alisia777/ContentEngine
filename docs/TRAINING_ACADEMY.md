# Training Academy

v1.9 adds an in-product onboarding layer for creators, publishers, partners, reviewers, operators, and admins.

```text
participant
-> role course
-> lessons and checklist
-> quiz attempt
-> certification
-> advisory or strict operational gate
```

The Training Academy does not duplicate Participant Portal, Metrics Intake, Publishing Workflow, or Destination Control Tower. It teaches people how to use those layers safely.

## UI

Open:

```text
/training-academy
```

The page shows:

- course catalog;
- "I have zero experience" start flow;
- earning tracks;
- platform playbooks;
- scenario simulator;
- role-based learning path;
- lesson viewer;
- quiz/test form;
- certification result;
- participant progress;
- advisory training gates.

## Courses

Default courses are seeded by code:

- `creator_basics`
- `publisher_basics`
- `metrics_basics`
- `payout_basics`
- `reviewer_basics`

Each course has lessons, checklists, examples, a quiz, and a passing score.

## Beginner Earning Tracks

Training Academy explains how a newcomer can earn inside ContentEngine:

- Publisher / Placement Operator: publish approved videos and return final URLs.
- Metrics Operator: submit valid platform or marketplace reports.
- Reviewer Assistant: make correct approve/reject/regenerate decisions.
- Creator / Editor: create or fix videos from brief cards.
- Channel / Destination Owner: run owned destinations and submit placement proof.

Each track explains daily work, required proof, rejection reasons, payout blockers, and required certifications.

## Platform Playbooks

Platform playbooks cover Instagram/Reels, Facebook, YouTube Shorts, TikTok, Telegram, VK, marketplace metrics, and partner slots.

Each playbook answers:

1. What should I do on this platform?
2. What data must I submit?
3. What happens if links or stats are submitted incorrectly?

See `docs/PLATFORM_PLAYBOOKS.md`.

## Scenario Simulator

Scenario simulator covers common mistakes before real work:

- publish approved Reel;
- submit Facebook stats;
- YouTube Shorts stats;
- TikTok task;
- product identity review;
- payout without final URL.

## CLI

```bash
python scripts/seed_training_academy.py
python scripts/training_progress.py --participant-id 1
python scripts/submit_training_quiz.py --participant-id 1 --course-code metrics_basics --answers sample_data/training_answers.json
```

## API

```text
GET  /api/training/courses
GET  /api/training/courses/{id}
GET  /api/training/participants/{participant_id}/progress
POST /api/training/courses/{id}/start
POST /api/training/quizzes/{id}/submit
GET  /api/training/participants/{participant_id}/certifications
```

## Gates

Gates are advisory by default:

- publishing role -> `publisher_basics`;
- metrics submission -> `metrics_basics`;
- reviewer approval -> `reviewer_basics`.

Operators can call strict gate checks from services when a workflow needs to block an action until certification exists.

## Safety

Training Academy does not:

- create external accounts;
- automate unsafe publishing;
- bypass approval gates;
- store payment secrets;
- run paid providers in tests.

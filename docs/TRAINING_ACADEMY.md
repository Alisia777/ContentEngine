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

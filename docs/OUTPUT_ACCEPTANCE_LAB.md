# Real Output Acceptance Lab

v2.4 adds the layer after prompt and provider output: actual video acceptance.

The workflow is:

```text
AIProductionBrief
-> DirectorPromptPack
-> video_job output
-> frame extraction
-> contact sheet
-> manual/rules output checklist
-> approve / needs_regeneration / reject
```

The lab intentionally does not claim computer vision. Product identity, packaging, geometry, scene match, proof moment, CTA, and blogger authenticity are stored as human-review statuses.

## CLI

```bash
python scripts/extract_video_frames.py --video-job-id 21
python scripts/review_video_output.py --video-job-id 21 --ai-production-brief-id 1
python scripts/request_output_regeneration.py --acceptance-id 1 --reason product_identity_mismatch
```

## UI

Open:

```text
/output-acceptance
```

Sections:

- Video artifact;
- Contact sheet;
- AIProductionBrief summary;
- Scene blueprint checklist;
- Product identity checklist;
- Blogger authenticity checklist;
- Decision: approve / needs_regeneration / reject.

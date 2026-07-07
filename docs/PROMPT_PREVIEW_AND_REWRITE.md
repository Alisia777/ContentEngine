# Prompt Preview And Rewrite

Prompt preview shows what will be sent to the video provider before a paid call can happen.

It includes:

- scene prompt;
- negative prompt;
- product lock mode;
- reference count;
- identity constraints;
- geometry constraints;
- blogger persona;
- scene role;
- spoken line;
- caption.

## Rewrite Flow

When `CreativeQualityScore` is not passed, the workbench can:

1. create a rewrite request from score reasons;
2. build a rewritten `UGCAdScript`;
3. rescore the new script;
4. show before and after lines;
5. keep real smoke blocked until readiness passes.

This flow never calls paid video providers and never silently falls back to mock output.

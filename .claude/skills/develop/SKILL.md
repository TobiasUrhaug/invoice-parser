---
name: develop
description: Start the developer workflow — check for review comments and implement the next task using TDD.
---

Check if `comments.md` exists and has unaddressed comments (comment blocks without an `**Addressed:**` field).

- If it does, read it in full and address every unaddressed comment following the developer workflow in `.claude/profiles/developer.md` (step 5).
- If it does not exist, is empty, or all comments are already addressed, move to step 1 of the developer workflow: pick up the next task and implement it using TDD as described in `.claude/profiles/developer.md` and `CLAUDE.md`.

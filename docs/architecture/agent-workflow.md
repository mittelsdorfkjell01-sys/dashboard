# Cost-aware agent workflow

Use the least expensive configuration that reliably completes the task. Model selection is a user/client setting; repository instructions do not force a model.

| Task | Suggested model | Reasoning | Validation |
|---|---|---|---|
| Locate a symbol, explain code, edit copy, update one fixture | GPT-5.6 Luna | low | closest syntax/unit check |
| Normal bug fix or bounded feature | GPT-5.6 Terra | low or medium | focused area check |
| Cross-layer contract change or moderate refactor | GPT-5.6 Terra | medium | focused checks plus build |
| Architecture, migration, data-loss risk, difficult production failure | GPT-5.6 Sol | medium or high | explicit acceptance and rollback checks |

Start a new session for a new feature or unrelated bug. A good task request names:

1. outcome,
2. affected area or known files,
3. non-goals and safety boundaries,
4. success criteria,
5. required focused check.

Example:

```text
Fix the public map catalogue so a cold page load issues at most one list request.
Scope: app/api/spots.py and frontend/src/pages/MapView.tsx.
No schema changes. Success: focused spot and public-map tests pass.
```

Use `scripts/context.ps1` before broad exploration, `scripts/check.ps1` during iteration, and `scripts/repo-drift.ps1` before synchronizing the public repository.

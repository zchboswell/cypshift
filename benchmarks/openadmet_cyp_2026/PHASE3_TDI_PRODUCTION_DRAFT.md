# Paused production draft — September 5, 2026

Preserved at the user's request to pause; no production fits or test-set
prediction occurred. This branch contains the proposed production driver and
its synthetic qualification/validation tests. All 25 combined TDI tests passed
before pause; lint and formatting passed. It is not ready to run or merge.

The driver still pins independent audit V2. The completed first-seed audit is
V3; update the audit script/plan pins and corresponding qualification tests,
review the independent replay boundary, then require the unchanged second seed,
its audit and root-sealed both-seed qualification before any production fits.
A positive first seed alone does not authorize release. No qualification receipt
has been sealed and no submission CSV was created.

The root results branch `codex/phase3-next-results` holds the authoritative
`docs/strategy/RESUME_AFTER_PAUSE_2026-09-05.md` with exact private artifacts,
passed audit identities, failure disclosure, budgets and restart order.
Do not start work until the user explicitly resumes.

## Shared skills and tool routing

- Before implementing or planning a feature, use `.claude/skills/check-before-build/SKILL.md` to inspect the current repository, Git history, and active remote issues/pull requests for reusable or overlapping work.
- For ordinary frontend or backend implementation, infer the owner's lane after the reuse report and run `scripts/start-work.sh <backend|frontend> "<short-task-name>"` before editing. Do not ask the founder to create a branch or supply Git commands; the helper creates the correct owned branch from clean `main`. Stop for dirty worktrees, an existing work branch, or a shared-contract boundary.
- Use Agent Browser for public pages, headless testing, and general browser automation.
- Use Ego Browser only for the user's authenticated local browser session or when explicitly requested.
- Keep credentials and browser-session data local. Never commit them.
- Graphify is installed, but do not generate its knowledge graph until source code exists.

## Pull request and auto-merge policy

- Work on short-lived branches and use pull requests; do not push feature work directly to `main` after bootstrap.
- Run `/greploop` until the PR has Greptile 5/5 confidence and zero unresolved actionable comments.
- Auto-merge is safe to enable only when `repository-policy` and Greptile are required checks and `AUTO_MERGE_ENABLED=true`.
- Sensitive paths excluded by `.greptile/config.json` still require human approval.
- Squash-merge successful PRs and delete their source branches.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

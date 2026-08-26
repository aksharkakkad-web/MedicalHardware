---
name: check-before-build
description: Use when asked to build, add, implement, scaffold, replace, or redesign a project feature, API, component, service, schema, integration, workflow, or other substantial behavior.
---

# Check Before Build

Do not start a new implementation until existing work has been investigated and a reuse verdict has been recorded.

## Preflight

1. Restate the requested capability and likely names, synonyms, routes, schemas, and directories.
2. Read the applicable `AGENTS.md`, `CLAUDE.md`, requirements, architecture, contracts, ownership rules, and build plans.
3. Keep discovery read-only. When the request may touch more than one file/module or mentions prior/parallel work, assign each independently available lane to a host-native read-only subagent when capacity permits. Otherwise run the lanes sequentially.

| Lane | Required evidence |
|---|---|
| Current repository | Search paths, symbols, tests, docs, dependencies, generated clients, and neighboring abstractions with `rg`/structural search. |
| Git history | Locate the Git root; inspect status, worktrees, all branches, logs, renames, deletions, and content history with `git log --all`, `-S`, `-G`, `git show`, and path history. |
| Active remote work | Inspect remotes. When GitHub and authenticated `gh` are available, search open and closed issues and pull requests for the capability and its synonyms. |

Each scout returns evidence with file paths, symbols, commit IDs, branch names, issue/PR numbers, and uncertainties. Scouts do not edit, fetch, pull, switch branches, or create worktrees. The coordinating agent reconciles the evidence and respects contract-editor and directory-ownership boundaries.

If Git, a remote, or authentication is unavailable, run every available lane and label only the missing evidence lane `unavailable`. Subagent unavailability changes execution mode to sequential; it does not make an evidence lane unavailable. Without a remote or explicit repository identifier, do not guess which GitHub project to search. Missing history is not proof that prior work never existed.

## Required Reuse Report

Produce this report before implementation:

```text
Requested capability:
Current implementation matches:
Contract/documentation matches:
History matches:
Issue/PR matches:
Verdict: reuse | extend | revive | coordinate | build-new | blocked
Recommended implementation boundary:
Evidence gaps:
```

Proceed only when the evidence supports `reuse`, `extend`, `revive`, or `build-new` and the implementation boundary is clear. If the requester credibly identifies prior or parallel work that cannot be located and inspected, use `blocked`, not `build-new`. For `coordinate` or `blocked`, stop and request the missing decision. Never create a parallel abstraction merely because adapting existing work is less convenient.

## Example

For “build the resident event API,” search `MonitoringEvent`, lifecycle verbs, routes, contracts, history, branches, issues, and PRs. If contracts exist but code does not, report `build-new` against the existing contract—not “nothing exists.”

## Rationalizations to Reject

| Rationalization | Response |
|---|---|
| “The deadline is too close.” | A focused preflight is cheaper than duplicate implementation. |
| “The lead says none exists.” | Treat that as a hypothesis and verify it. |
| “An agent already spent hours on the new version.” | Sunk cost does not establish the right boundary. |

Red flags: coding before the report, checking only the current branch, ignoring closed PRs/issues, equating missing local Git with no prior work, or dispatching multiple agents to edit the same contract.

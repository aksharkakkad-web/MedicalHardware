#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/start-work.sh <backend|frontend> <short-task-name>

Creates a clean, up-to-date work branch for an owned product lane.
  backend  -> akshar/backend-<short-task-name>
  frontend -> cofounder/frontend-<short-task-name>

The helper never commits, pushes, opens a PR, reuses an existing branch, or
switches away from uncommitted work.
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$#" -ne 2 ]]; then
  usage >&2
  exit 2
fi

lane="$1"
task_name="$2"

case "$lane" in
  backend) prefix="akshar/backend" ;;
  frontend) prefix="cofounder/frontend" ;;
  *)
    printf 'Unknown lane: %s\n' "$lane" >&2
    usage >&2
    exit 2
    ;;
esac

slug=$(printf '%s' "$task_name" \
  | tr '[:upper:]' '[:lower:]' \
  | tr -cs 'a-z0-9' '-' \
  | sed -e 's/^-*//' -e 's/-*$//')

if [[ -z "$slug" ]]; then
  printf 'Task name must contain at least one letter or number.\n' >&2
  exit 2
fi

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
  printf 'Run this helper inside a Git repository.\n' >&2
  exit 2
}
cd "$repo_root"

if [[ -n "$(git status --porcelain)" ]]; then
  printf 'Working tree is not clean. Commit, stash, or hand off existing work first.\n' >&2
  exit 3
fi

current_branch=$(git branch --show-current)
if [[ -z "$current_branch" ]]; then
  printf 'Detached HEAD is not supported. Switch to main or an owned work branch first.\n' >&2
  exit 3
fi

if [[ "$current_branch" != "main" ]]; then
  printf 'Current branch is %s. Finish or hand off that work before starting a new branch.\n' "$current_branch" >&2
  exit 3
fi

branch="$prefix-$slug"
if git show-ref --verify --quiet "refs/heads/$branch"; then
  printf 'Branch already exists locally: %s\n' "$branch" >&2
  exit 4
fi

if ! git fetch origin refs/heads/main:refs/remotes/origin/main --quiet; then
  printf 'Cannot verify origin/main. Check remote access before creating a branch.\n' >&2
  exit 3
fi

if ! remote_branch=$(git ls-remote --heads origin "refs/heads/$branch"); then
  printf 'Cannot verify remote branch availability. Check remote access before creating a branch.\n' >&2
  exit 3
fi

if [[ -n "$remote_branch" ]]; then
  printf 'Branch already exists on origin: %s\n' "$branch" >&2
  exit 4
fi

if ! git pull --ff-only origin main --quiet; then
  printf 'Cannot fast-forward main from origin/main. Resolve the local branch before creating a branch.\n' >&2
  exit 3
fi

if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  printf 'Local main does not match origin/main. Push or discard local commits before creating a branch.\n' >&2
  exit 3
fi

git switch -c "$branch"
printf 'Ready to work on %s (%s lane).\n' "$branch" "$lane"

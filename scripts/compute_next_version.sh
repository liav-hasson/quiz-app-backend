#!/usr/bin/env bash
set -euo pipefail

# compute_next_version.sh
# Compute the next semantic version tag based on commit-message prefixes or explicit bump
# Usage:
#   compute_next_version.sh <repo-dir> <mode>
# Modes:
#   auto   - scan commit messages since the last semver tag for prefixes (major:/minor:/patch:)
#   major  - bump major
#   minor  - bump minor
#   patch  - bump patch (default)
# Environment:
#   If COMMIT_MESSAGES is set, the script will use that value (newline-separated) instead of running git.
# Output:
#   Prints the new tag (e.g. v1.2.3) to stdout. Also prints diagnostic info to stderr.

REPO_DIR="${1:-.}"
MODE="${2:-patch}"

cd "$REPO_DIR"

# Helper: get latest semver tag from git repository
get_latest_tag() {
  # Get all semver tags and sort by version to find the highest
  # Use sort -V for proper version sorting (v1.0.0 > v0.0.1)
  local git_tag=$(git tag -l "v[0-9]*.[0-9]*.[0-9]*" | sort -V | tail -n1 || echo "")
  
  if [[ -n "$git_tag" ]]; then
    echo "$git_tag"
    return
  fi
  
  # No git tags found - return empty (will cause error in main script)
  echo ""
}

# Parse tag into MAJOR MINOR PATCH
parse_tag() {
  local tag="${1:-v0.0.0}"
  tag=${tag#v}
  IFS='.' read -r MAJOR MINOR PATCH <<< "$tag"
  MAJOR=${MAJOR:-0}
  MINOR=${MINOR:-0}
  PATCH=${PATCH:-0}
}

# Determine bump from commit messages (prioritise major > minor > patch)
decide_bump_from_commits() {
  local messages="$1"
  local found_major=0
  local found_minor=0
  local found_patch=0

  # iterate lines
  while IFS= read -r line; do
    # trim leading whitespace
    line="$(echo "$line" | sed -e 's/^\s*//')"
    shopt -s nocasematch 2>/dev/null || true
    if [[ "$line" =~ ^major: ]]; then
      found_major=1
    elif [[ "$line" =~ ^minor: ]]; then
      found_minor=1
    elif [[ "$line" =~ ^patch: ]]; then
      found_patch=1
    fi
  done <<< "$messages"

  if [ $found_major -eq 1 ]; then
    echo major
  elif [ $found_minor -eq 1 ]; then
    echo minor
  else
    echo patch
  fi
}

LATEST_TAG=$(get_latest_tag)
if [[ -z "$LATEST_TAG" ]] || [[ "$LATEST_TAG" == "v0.0.0" ]]; then
  echo "[compute_next_version] ERROR: No semantic version tag found in repository!" >&2
  echo "[compute_next_version] Please create an initial tag (e.g., git tag -a v1.0.0 -m 'Initial release')" >&2
  exit 1
fi
echo "[compute_next_version] Using git tag: $LATEST_TAG as baseline" >&2
parse_tag "$LATEST_TAG"
case "$MODE" in
  auto)
    # Get current branch name
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")
    echo "[compute_next_version] Current branch: $CURRENT_BRANCH" >&2
    
    # Use COMMIT_MESSAGES env if set, otherwise collect via git
    if [[ -n "${COMMIT_MESSAGES:-}" ]]; then
      COMMITS="$COMMIT_MESSAGES"
      echo "[compute_next_version] Using COMMIT_MESSAGES env (length=$(echo -n "$COMMITS" | wc -c))" >&2
    else
      # Get commits since the latest tag on current branch only
      # This prevents counting commits from other branches
      COMMITS=$(git log --pretty=%s --no-merges "$LATEST_TAG"..HEAD --first-parent 2>/dev/null || true)
      
      # Count commits for diagnostics
      COMMIT_COUNT=$(echo "$COMMITS" | grep -c . || echo "0")
      echo "[compute_next_version] Collected $COMMIT_COUNT commit(s) on current branch since $LATEST_TAG" >&2
    fi

    # Trim whitespace and check if we have actual commits
    COMMITS_TRIMMED=$(echo "$COMMITS" | xargs)
    if [[ -z "$COMMITS_TRIMMED" ]]; then
      # No new commits - use patch bump for dev environments to avoid conflicts
      BUMP=patch
      echo "[compute_next_version] No new commits found; defaulting to patch bump" >&2
    else
      BUMP=$(decide_bump_from_commits "$COMMITS")
      echo "[compute_next_version] Determined bump: $BUMP (based on commit prefixes)" >&2
      echo "[compute_next_version] Sample commits: $(echo "$COMMITS" | head -n 3)" >&2
    fi
    ;;
  major|minor|patch)
    BUMP="$MODE"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac

# compute new version
case "$BUMP" in
  major)
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
    ;;
  minor)
    MINOR=$((MINOR + 1))
    PATCH=0
    ;;
  patch)
    PATCH=$((PATCH + 1))
    ;;
esac

NEW_TAG="v${MAJOR}.${MINOR}.${PATCH}"

echo "[compute_next_version] Computed version: $LATEST_TAG → $NEW_TAG (bump: $BUMP)" >&2
echo "$NEW_TAG"
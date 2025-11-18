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
  # First, try to get the latest tag from git
  local git_tag=$(git describe --tags --abbrev=0 --match "v[0-9]*.[0-9]*.[0-9]*" 2>/dev/null || echo "")
  
  if [[ -n "$git_tag" ]]; then
    echo "$git_tag"
    return
  fi
  
  # Fallback: try to find any semver tag in git
  git_tag=$(git tag -l "v[0-9]*.[0-9]*.[0-9]*" | sort -V | tail -n1 || echo "")
  
  if [[ -n "$git_tag" ]]; then
    echo "$git_tag"
    return
  fi
  
  # No git tags found - start from v0.0.0
  echo "v0.0.0"
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
if [[ -z "$LATEST_TAG" ]]; then
  LATEST_TAG="v0.0.0"
fi
parse_tag "$LATEST_TAG"

case "$MODE" in
  auto)
    # Use COMMIT_MESSAGES env if set, otherwise collect via git
    if [[ -n "${COMMIT_MESSAGES:-}" ]]; then
      COMMITS="$COMMIT_MESSAGES"
      echo "[compute_next_version] Using COMMIT_MESSAGES env (length=$(echo -n "$COMMITS" | wc -c))" >&2
    else
      # Collect commit subjects since the last tag
      if [ "$LATEST_TAG" = "v0.0.0" ]; then
        # No previous tag in git - look at recent commits only (last 7 days or 50 commits max)
        COMMITS=$(git log --pretty=%s --no-merges --since="7 days ago" -n 50 2>/dev/null || true)
        echo "[compute_next_version] No git tag found; collecting recent commits (last 7 days or 50 max)" >&2
      else
        # Tag exists in git - get commits since that tag
        COMMITS=$(git log --pretty=%s --no-merges "$LATEST_TAG"..HEAD 2>/dev/null || true)
        echo "[compute_next_version] Using git tag $LATEST_TAG as baseline" >&2
      fi
      
      # Count commits for diagnostics
      COMMIT_COUNT=$(echo "$COMMITS" | grep -c . || echo "0")
      echo "[compute_next_version] Collected $COMMIT_COUNT commit messages since $LATEST_TAG" >&2
    fi

    # Trim whitespace and check if we have actual commits
    COMMITS_TRIMMED=$(echo "$COMMITS" | xargs)
    if [[ -z "$COMMITS_TRIMMED" ]]; then
      # fallback to patch if no commits/messages
      BUMP=patch
      echo "[compute_next_version] No new commits found; defaulting to patch bump" >&2
    else
      BUMP=$(decide_bump_from_commits "$COMMITS")
      echo "[compute_next_version] Determined bump: $BUMP" >&2
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

echo "$NEW_TAG"

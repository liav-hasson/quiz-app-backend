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

# Helper: get latest semver tag from Docker Hub
get_latest_tag() {
  DOCKER_USER="${DOCKERHUB_CREDENTIALS_USR:-}"
  DOCKER_IMAGE="${DOCKER_IMAGE_NAME:-}"
  
  if [[ -n "$DOCKER_USER" ]] && [[ -n "$DOCKER_IMAGE" ]]; then
    curl -s "https://hub.docker.com/v2/repositories/${DOCKER_USER}/${DOCKER_IMAGE}/tags?page_size=100" \
      | grep -o '"name":"v[0-9]\+\.[0-9]\+\.[0-9]\+"' \
      | cut -d'"' -f4 \
      | sort -V \
      | tail -n1 || echo "v0.0.0"
  else
    echo "v0.0.0"
  fi
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
        COMMITS=$(git log --pretty=%s --no-merges 2>/dev/null || true)
      else
        COMMITS=$(git log --pretty=%s --no-merges "$LATEST_TAG"..HEAD 2>/dev/null || true)
      fi
      echo "[compute_next_version] Collected commit messages (count=$(echo "$COMMITS" | wc -l))" >&2
    fi

    if [[ -z "${COMMITS// /}" ]]; then
      # fallback to patch if no commits/messages
      BUMP=patch
      echo "[compute_next_version] No commit messages found; defaulting to patch" >&2
    else
      BUMP=$(decide_bump_from_commits "$COMMITS")
      echo "[compute_next_version] Determined bump: $BUMP" >&2
      echo "[compute_next_version] Sample commits:\n$COMMITS" >&2
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

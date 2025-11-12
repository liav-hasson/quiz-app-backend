#!/bin/bash
# GitOps updater for quiz-app Helm chart
# Updates image tag in values.yaml and appVersion in Chart.yaml
# Commits changes back to the GitOps repository

set -e

# Parameters passed explicitly from Jenkins
DOCKER_USERNAME="$1"
DOCKER_IMAGE_NAME="$2"
IMAGE_TAG="$3"
BUILD_NUMBER="$4"
GITOPS_REPO_URL="${5:-https://github.com/liav-hasson/quiz-app-gitops.git}"
GIT_USER_NAME="$6"
GIT_USER_EMAIL="$7"
GITHUB_USERNAME="$8"
GITHUB_PASSWORD="$9"

# Validation
if [ -z "$DOCKER_USERNAME" ] || [ -z "$DOCKER_IMAGE_NAME" ] || [ -z "$IMAGE_TAG" ] || [ -z "$GITOPS_REPO_URL" ] || [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
    echo "Usage: $0 <docker_username> <docker_image_name> <image_tag> <build_number> <gitops_repo_url> <git_user_name> <git_user_email> [github_username] [github_password]"
    echo "ERROR: Missing required parameters:"
    echo "   DOCKER_USERNAME: '$DOCKER_USERNAME'"
    echo "   DOCKER_IMAGE_NAME: '$DOCKER_IMAGE_NAME'"
    echo "   IMAGE_TAG: '$IMAGE_TAG'"  
    echo "   BUILD_NUMBER: '$BUILD_NUMBER'"
    echo "   GITOPS_REPO_URL: '$GITOPS_REPO_URL'"
    echo "   GIT_USER_NAME: '$GIT_USER_NAME'"
    echo "   GIT_USER_EMAIL: '$GIT_USER_EMAIL'"
    exit 1
fi

echo "Updating GitOps configuration..."
echo "Image: ${DOCKER_USERNAME}/${DOCKER_IMAGE_NAME}:${IMAGE_TAG}"

# Create temp workspace
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"


# Clone GitOps repo with authentication
echo "--------- Cloning GitOps repository ---------"
echo "   Repository: $GITOPS_REPO_URL"
echo "   Git user: $GIT_USER_NAME <$GIT_USER_EMAIL>"

# Build authenticated URL if credentials provided
if [ -n "$GITHUB_USERNAME" ] && [ -n "$GITHUB_PASSWORD" ]; then
    # Extract repo path from URL (remove https:// prefix)
    REPO_PATH=$(echo "$GITOPS_REPO_URL" | sed 's|https://||')
    AUTHENTICATED_URL="https://${GITHUB_USERNAME}:${GITHUB_PASSWORD}@${REPO_PATH}"
    git clone --depth=1 "$AUTHENTICATED_URL" .
else
    git clone --depth=1 "$GITOPS_REPO_URL" .
fi

git config user.name "$GIT_USER_NAME"
git config user.email "$GIT_USER_EMAIL"


# Update Helm chart values
echo "--------- Updating Helm chart ---------"
cd quiz-backend

# Update image repository and tag in values.yaml
sed -i "s|repository: .*|repository: ${DOCKER_USERNAME}/${DOCKER_IMAGE_NAME}|g" values.yaml
sed -i "s|tag: \".*\"|tag: \"${IMAGE_TAG}\"|g" values.yaml

# Update appVersion in Chart.yaml
sed -i "s|appVersion: \".*\"|appVersion: \"${IMAGE_TAG}\"|g" Chart.yaml

# Show the changes
echo "Changes made:"
git diff values.yaml Chart.yaml


# Commit and push
echo "--------- Committing changes ---------"
git add values.yaml Chart.yaml
git commit -m "Deploy ${DOCKER_IMAGE_NAME}:${IMAGE_TAG}

- Updated from Jenkins build #${BUILD_NUMBER:-unknown}
- Image: ${DOCKER_USERNAME}/${DOCKER_IMAGE_NAME}:${IMAGE_TAG}
- Updated values.yaml image tag
- Updated Chart.yaml appVersion" || {
    echo "No changes to commit (image tag might already be up to date)"
    rm -rf "$TEMP_DIR"
    exit 0
}

echo "Pushing changes to GitHub..."
# Use the authenticated remote URL for push
if [ -n "$GITHUB_USERNAME" ] && [ -n "$GITHUB_PASSWORD" ]; then
    REPO_PATH=$(echo "$GITOPS_REPO_URL" | sed 's|https://||')
    AUTHENTICATED_URL="https://${GITHUB_USERNAME}:${GITHUB_PASSWORD}@${REPO_PATH}"

    git remote set-url origin "$AUTHENTICATED_URL"
fi

git push origin main


# Tag the release version for next build's version calculation
echo "--------- Tagging release version ---------"
cd "$TEMP_DIR"
git tag -a "${IMAGE_TAG}" -m "Release ${DOCKER_IMAGE_NAME} ${IMAGE_TAG} - Build #${BUILD_NUMBER:-unknown}" 2>/dev/null || {
    echo "Tag ${IMAGE_TAG} already exists, skipping tag creation"
}

# Push the tag (use same authenticated remote if available)
if [ -n "$GITHUB_USERNAME" ] && [ -n "$GITHUB_PASSWORD" ]; then
    REPO_PATH=$(echo "$GITOPS_REPO_URL" | sed 's|https://||')
    AUTHENTICATED_URL="https://${GITHUB_USERNAME}:${GITHUB_PASSWORD}@${REPO_PATH}"
    git remote set-url origin "$AUTHENTICATED_URL"
fi
git push origin "${IMAGE_TAG}" 2>/dev/null || {
    echo "Tag ${IMAGE_TAG} already exists on remote, skipping tag push"
}
echo "Tagged release: ${IMAGE_TAG}"

# Cleanup
rm -rf "$TEMP_DIR"

echo "GitOps update complete!"
echo "ArgoCD will detect the changes and sync automatically"
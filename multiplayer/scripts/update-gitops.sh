#!/bin/bash
# GitOps updater for quiz-multiplayer Helm chart
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
DEPLOY_ENV="${10:-prod}"  # Default to prod if not specified

# Validation
if [ -z "$DOCKER_USERNAME" ] || [ -z "$DOCKER_IMAGE_NAME" ] || [ -z "$IMAGE_TAG" ] || [ -z "$GITOPS_REPO_URL" ] || [ -z "$GIT_USER_NAME" ] || [ -z "$GIT_USER_EMAIL" ]; then
    echo "Usage: $0 <docker_username> <docker_image_name> <image_tag> <build_number> <gitops_repo_url> <git_user_name> <git_user_email> [github_username] [github_password] [deploy_env]"
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

# Determine values file based on environment
if [ "$DEPLOY_ENV" = "dev" ]; then
    VALUES_FILE="values-dev.yaml"
    echo "Updating GitOps configuration for DEV environment..."
else
    VALUES_FILE="values.yaml"
    echo "Updating GitOps configuration for PRODUCTION environment..."
fi

echo "Environment: ${DEPLOY_ENV}"
echo "Values file: ${VALUES_FILE}"
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
cd quiz-multiplayer

# Update image repository and tag in the appropriate values file
sed -i "s|repository: .*|repository: ${DOCKER_USERNAME}/${DOCKER_IMAGE_NAME}|g" "$VALUES_FILE"
sed -i "s|tag: \".*\"|tag: \"${IMAGE_TAG}\"|g" "$VALUES_FILE"

# Update appVersion in Chart.yaml (only for production)
if [ "$DEPLOY_ENV" = "prod" ]; then
    sed -i "s|appVersion: \".*\"|appVersion: \"${IMAGE_TAG}\"|g" Chart.yaml
    FILES_TO_COMMIT="${VALUES_FILE} Chart.yaml"
else
    FILES_TO_COMMIT="${VALUES_FILE}"
fi

# Show the changes
echo "Changes made:"
git diff $FILES_TO_COMMIT


# Commit and push
echo "--------- Committing changes ---------"
git add $FILES_TO_COMMIT
git commit -m "Deploy ${DOCKER_IMAGE_NAME}:${IMAGE_TAG} [${DEPLOY_ENV}]

- Environment: ${DEPLOY_ENV}
- Updated from Jenkins build #${BUILD_NUMBER:-unknown}
- Image: ${DOCKER_USERNAME}/${DOCKER_IMAGE_NAME}:${IMAGE_TAG}
- Updated ${VALUES_FILE} image tag" || {
    echo "No changes to commit"
    exit 0
}

git push origin main

echo "--------- GitOps update complete ---------"

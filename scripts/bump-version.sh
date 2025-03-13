#!/bin/bash -eu

VERSION=${1:-}
if [ -z "${VERSION}" ]; then
  echo "VERSION must be set."
  exit -1
fi

# Exit if not in git repository
if [[ ! -d .git ]]; then
  echo 'Not in a git repository.'
  exit -1
fi

# Exit if not in the base branch
BASE_BRANCH=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "${CURRENT_BRANCH}" != "${BASE_BRANCH}" ]]; then
  echo "Not in ${BASE_BRANCH} branch."
  exit -1
fi

# Exit if working tree is dirty
if [[ $(git diff --stat) != '' ]]; then
  echo 'Git working tree is dirty.'
  exit -1
fi

echo "Set version to pyproject.toml"
# Update version in pyproject.toml manually since uv doesn't have a version command
sed -i "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml
CURRENT_VERSION=${VERSION}

echo "Add and commit pyproject.toml"
git add pyproject.toml
git commit -m "Version ${CURRENT_VERSION}"

GIT_TAG="v${CURRENT_VERSION}"
echo "Set git tag as ${GIT_TAG}"
git tag -a ${GIT_TAG} -m ${CURRENT_VERSION}
